"""
Strategy Optimizer for Self-Improvement Engine.

Tracks strategy performance and selects optimal strategies for tasks.
Implements exploration-exploitation tradeoff for continuous learning.

**Validates: Requirements 2.1, 2.2, 2.3**

Performance Requirements:
- Time Complexity: O(log n) for strategy selection
- Space Complexity: O(n) where n is number of strategies
- Selection Latency: <10ms (95th percentile)

Author: Agent Guru Team
Date: 2026-02-27
"""

import json
import math
import random
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from Agent_Guru.self_improvement.connection_pool import ConnectionPool


@dataclass
class Strategy:
    """A strategy for executing tasks."""

    strategy_id: str
    name: str
    description: str
    task_types: list[str]
    parameters: dict[str, Any]
    success_rate: float
    total_executions: int
    success_count: int
    failure_count: int
    avg_execution_time_ms: float
    created_at: datetime
    last_updated: datetime
    last_used: datetime | None = None


class StrategyOptimizer:
    """
    Optimizes strategy selection based on performance tracking.

    Uses epsilon-greedy exploration to balance exploitation of known
    good strategies with exploration of potentially better strategies.

    Time Complexity: O(log n) for strategy selection
    Space Complexity: O(n) where n is number of strategies

    Example:
        >>> optimizer = StrategyOptimizer(pool)
        >>> optimizer.register_strategy(
        ...     strategy_id="reasoning_chain",
        ...     name="Chain of Thought",
        ...     description="Step-by-step reasoning",
        ...     task_types=["analysis", "problem_solving"],
        ...     parameters={"max_steps": 5}
        ... )
        >>> optimizer.update_strategy_performance("reasoning_chain", True, 150.0)
        >>> best = optimizer.get_best_strategy("analysis")
    """

    def __init__(
        self, pool: "ConnectionPool", epsilon: float = 0.1, min_executions_for_confidence: int = 10
    ) -> None:
        """
        Initialize strategy optimizer.

        Args:
            pool: ConnectionPool for database access
            epsilon: Exploration rate (0.0-1.0), default 0.1 (10% exploration)
            min_executions_for_confidence: Minimum executions before trusting success rate

        Raises:
            ValueError: If epsilon not in [0.0, 1.0]
        """
        if not 0.0 <= epsilon <= 1.0:
            raise ValueError(f"Epsilon must be in [0.0, 1.0], got {epsilon}")

        self.pool = pool
        self.epsilon = epsilon
        self.min_executions_for_confidence = min_executions_for_confidence
        self._init_database()

    def _init_database(self) -> None:
        """
        Initialize database schema for strategies.

        Note: DatabaseSchema.create_schema() should be called first.
        This method only verifies the table exists.
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Verify strategies table exists
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='strategies'
            """
            )

            if not cursor.fetchone():
                raise RuntimeError(
                    "Strategies table not found. " "Call DatabaseSchema.create_schema() first."
                )

    def register_strategy(
        self,
        strategy_id: str,
        name: str,
        description: str,
        task_types: list[str],
        parameters: dict[str, Any],
    ) -> None:
        """
        Register a new strategy.

        Args:
            strategy_id: Unique strategy identifier
            name: Human-readable strategy name
            description: Strategy description
            task_types: List of task types this strategy applies to
            parameters: Strategy configuration parameters

        Raises:
            ValueError: If strategy_id already exists
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Check if strategy already exists
            cursor.execute(
                "SELECT strategy_id FROM strategies WHERE strategy_id = ?", (strategy_id,)
            )
            if cursor.fetchone():
                raise ValueError(f"Strategy '{strategy_id}' already exists")

            now = datetime.now().isoformat()

            cursor.execute(
                """
                INSERT INTO strategies (
                    strategy_id, name, description, task_types, parameters,
                    success_rate, total_executions, success_count,
                    failure_count, avg_execution_time_ms,
                    created_at, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    strategy_id,
                    name,
                    description,
                    json.dumps(task_types),
                    json.dumps(parameters),
                    0.0,
                    0,
                    0,
                    0,
                    0.0,
                    now,
                    now,
                ),
            )

            conn.commit()

    def update_strategy_performance(
        self, strategy_id: str, success: bool, execution_time_ms: float
    ) -> None:
        """
        Update strategy performance after execution.

        Time Complexity: O(1) - single database update

        Args:
            strategy_id: Strategy that was used
            success: Whether execution succeeded
            execution_time_ms: Execution time in milliseconds

        Raises:
            ValueError: If strategy_id doesn't exist
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Get current stats
            cursor.execute(
                """
                SELECT total_executions, success_count,
                       failure_count, avg_execution_time_ms
                FROM strategies
                WHERE strategy_id = ?
            """,
                (strategy_id,),
            )

            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Strategy '{strategy_id}' not found")

            total, success_count, failure_count, avg_time = row

            # Update stats
            new_total = total + 1
            new_success_count = success_count + (1 if success else 0)
            new_failure_count = failure_count + (0 if success else 1)
            new_success_rate = new_success_count / new_total if new_total > 0 else 0.0

            # Update average execution time (running average)
            new_avg_time = (
                (avg_time * total + execution_time_ms) / new_total
                if new_total > 0
                else execution_time_ms
            )

            now = datetime.now().isoformat()

            cursor.execute(
                """
                UPDATE strategies
                SET total_executions = ?,
                    success_count = ?,
                    failure_count = ?,
                    success_rate = ?,
                    avg_execution_time_ms = ?,
                    last_updated = ?,
                    last_used = ?
                WHERE strategy_id = ?
            """,
                (
                    new_total,
                    new_success_count,
                    new_failure_count,
                    new_success_rate,
                    new_avg_time,
                    now,
                    now,
                    strategy_id,
                ),
            )

            conn.commit()

    def get_best_strategy(self, task_type: str, min_success_rate: float = 0.0) -> Strategy | None:
        """
        Get the best performing strategy for a task type.

        Time Complexity: O(n) where n is strategies for task_type

        Args:
            task_type: Type of task
            min_success_rate: Minimum success rate threshold

        Returns:
            Best strategy or None if no strategies available
        """
        strategies = self.get_strategies_for_task_type(task_type)

        if not strategies:
            return None

        # Filter by minimum success rate
        candidates = [s for s in strategies if s.success_rate >= min_success_rate]

        if not candidates:
            return None

        # Sort by success rate (descending), then by total executions (descending)
        candidates.sort(key=lambda s: (s.success_rate, s.total_executions), reverse=True)

        return candidates[0]

    def select_strategy_with_exploration(self, task_type: str) -> Strategy | None:
        """
        Select strategy using epsilon-greedy exploration.

        With probability epsilon, selects random strategy (exploration).
        With probability 1-epsilon, selects best strategy (exploitation).

        Time Complexity: O(n) where n is strategies for task_type

        Args:
            task_type: Type of task

        Returns:
            Selected strategy or None if no strategies available
        """
        strategies = self.get_strategies_for_task_type(task_type)

        if not strategies:
            return None

        # Exploration: select random strategy
        if random.random() < self.epsilon:
            return random.choice(strategies)

        # Exploitation: select best strategy
        return self.get_best_strategy(task_type)

    def get_strategies_for_task_type(self, task_type: str) -> list[Strategy]:
        """
        Get all strategies applicable to a task type.

        Time Complexity: O(n) where n is total strategies

        Args:
            task_type: Type of task

        Returns:
            List of applicable strategies
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT strategy_id, name, description, task_types, parameters,
                       success_rate, total_executions, success_count,
                       failure_count, avg_execution_time_ms,
                       created_at, last_updated, last_used
                FROM strategies
            """
            )

            strategies = []
            for row in cursor.fetchall():
                task_types = json.loads(row[3])

                # Check if task_type matches any of the strategy's task types
                if task_type in task_types or "*" in task_types:
                    strategies.append(
                        Strategy(
                            strategy_id=row[0],
                            name=row[1],
                            description=row[2],
                            task_types=task_types,
                            parameters=json.loads(row[4]),
                            success_rate=row[5],
                            total_executions=row[6],
                            success_count=row[7],
                            failure_count=row[8],
                            avg_execution_time_ms=row[9],
                            created_at=datetime.fromisoformat(row[10]),
                            last_updated=datetime.fromisoformat(row[11]),
                            last_used=datetime.fromisoformat(row[12]) if row[12] else None,
                        )
                    )

            return strategies

    def get_strategy(self, strategy_id: str) -> Strategy | None:
        """
        Get a specific strategy by ID.

        Time Complexity: O(1) - indexed lookup

        Args:
            strategy_id: Strategy identifier

        Returns:
            Strategy or None if not found
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT strategy_id, name, description, task_types, parameters,
                       success_rate, total_executions, success_count,
                       failure_count, avg_execution_time_ms,
                       created_at, last_updated, last_used
                FROM strategies
                WHERE strategy_id = ?
            """,
                (strategy_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return Strategy(
                strategy_id=row[0],
                name=row[1],
                description=row[2],
                task_types=json.loads(row[3]),
                parameters=json.loads(row[4]),
                success_rate=row[5],
                total_executions=row[6],
                success_count=row[7],
                failure_count=row[8],
                avg_execution_time_ms=row[9],
                created_at=datetime.fromisoformat(row[10]),
                last_updated=datetime.fromisoformat(row[11]),
                last_used=datetime.fromisoformat(row[12]) if row[12] else None,
            )

    def rank_strategies(
        self, task_type: str, strategy_ids: list[str] | None = None
    ) -> list[Strategy]:
        """
        Rank strategies by performance for a task type.

        Uses Upper Confidence Bound (UCB) for ranking to balance
        exploitation and exploration.

        Time Complexity: O(n log n) where n is number of strategies

        Args:
            task_type: Type of task
            strategy_ids: Optional list of strategy IDs to rank (if None, ranks all)

        Returns:
            List of strategies ranked by UCB score (descending)
        """
        if strategy_ids:
            strategies = [
                s
                for s in self.get_strategies_for_task_type(task_type)
                if s.strategy_id in strategy_ids
            ]
        else:
            strategies = self.get_strategies_for_task_type(task_type)

        if not strategies:
            return []

        # Calculate total executions across all strategies
        total_executions = sum(s.total_executions for s in strategies)

        # Calculate UCB score for each strategy
        scored_strategies = []
        for strategy in strategies:
            if strategy.total_executions < self.min_executions_for_confidence:
                # Boost strategies with few executions to encourage exploration
                ucb_score = float("inf")
            else:
                # UCB1 formula: mean + sqrt(2 * ln(total) / executions)
                exploration_bonus = math.sqrt(
                    2 * math.log(total_executions + 1) / strategy.total_executions
                )
                ucb_score = strategy.success_rate + exploration_bonus

            scored_strategies.append((strategy, ucb_score))

        # Sort by UCB score (descending)
        scored_strategies.sort(key=lambda x: x[1], reverse=True)

        return [s for s, _ in scored_strategies]

    def get_strategy_count(self) -> int:
        """
        Get total number of registered strategies.

        Time Complexity: O(1)

        Returns:
            Number of strategies
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM strategies")
            result = cursor.fetchone()
            return int(result[0]) if result else 0

    def get_all_strategies(self) -> list[Strategy]:
        """
        Get all registered strategies.

        Time Complexity: O(n) where n is number of strategies

        Returns:
            List of all strategies
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT strategy_id, name, description, task_types, parameters,
                       success_rate, total_executions, success_count,
                       failure_count, avg_execution_time_ms,
                       created_at, last_updated, last_used
                FROM strategies
                ORDER BY success_rate DESC, total_executions DESC
            """
            )

            strategies = []
            for row in cursor.fetchall():
                strategies.append(
                    Strategy(
                        strategy_id=row[0],
                        name=row[1],
                        description=row[2],
                        task_types=json.loads(row[3]),
                        parameters=json.loads(row[4]),
                        success_rate=row[5],
                        total_executions=row[6],
                        success_count=row[7],
                        failure_count=row[8],
                        avg_execution_time_ms=row[9],
                        created_at=datetime.fromisoformat(row[10]),
                        last_updated=datetime.fromisoformat(row[11]),
                        last_used=datetime.fromisoformat(row[12]) if row[12] else None,
                    )
                )

            return strategies

    # ========================================================================
    # Strategy Learning and Discovery
    # ========================================================================

    def discover_strategy_from_execution(
        self,
        task_type: str,
        execution_context: dict[str, Any],
        success: bool,
        execution_time_ms: float,
    ) -> str | None:
        """
        Discover new strategy from successful execution.

        Analyzes successful task executions to extract reusable strategies.
        If a novel approach is detected, registers it as a new strategy.

        Time Complexity: O(n) where n is existing strategies
        Space Complexity: O(1)

        Args:
            task_type: Type of task that was executed
            execution_context: Full execution context including approach used
            success: Whether execution succeeded
            execution_time_ms: Execution time in milliseconds

        Returns:
            Strategy ID if new strategy discovered, None otherwise

        Example:
            >>> context = {
            ...     "approach": "chain_of_thought",
            ...     "steps": 5,
            ...     "tools_used": ["search", "calculator"]
            ... }
            >>> strategy_id = optimizer.discover_strategy_from_execution(
            ...     "analysis", context, True, 150.0
            ... )
        """
        # Only discover from successful executions
        if not success:
            return None

        # Extract strategy signature from execution context
        approach = execution_context.get("approach")
        if not approach:
            return None

        # Check if this approach already exists as a strategy
        existing_strategies = self.get_strategies_for_task_type(task_type)
        for strategy in existing_strategies:
            if strategy.parameters.get("approach") == approach:
                # Strategy already exists, just update performance
                self.update_strategy_performance(strategy.strategy_id, success, execution_time_ms)
                return None

        # New strategy discovered - register it
        strategy_id = f"discovered_{approach}_{task_type}_{datetime.now().timestamp()}"
        strategy_name = f"Discovered: {approach.replace('_', ' ').title()}"
        strategy_description = (
            f"Automatically discovered strategy from successful {task_type} execution"
        )

        # Extract parameters from execution context
        parameters = {
            "approach": approach,
            "discovered_from": "successful_execution",
            "original_context": execution_context,
        }

        try:
            self.register_strategy(
                strategy_id=strategy_id,
                name=strategy_name,
                description=strategy_description,
                task_types=[task_type],
                parameters=parameters,
            )

            # Initialize with the successful execution
            self.update_strategy_performance(strategy_id, success, execution_time_ms)

            return strategy_id

        except ValueError:
            # Strategy already exists (race condition)
            return None

    def validate_strategy(
        self, strategy_id: str, validation_tasks: list[tuple[str, bool, float]]
    ) -> bool:
        """
        Validate strategy against held-out test set.

        Tests strategy performance on validation tasks to ensure it generalizes.
        Strategy is considered valid if it achieves >50% success rate on validation.

        Time Complexity: O(n) where n is validation tasks
        Space Complexity: O(1)

        Args:
            strategy_id: Strategy to validate
            validation_tasks: List of (task_type, success, execution_time_ms) tuples

        Returns:
            True if strategy is valid (>50% success rate), False otherwise

        Raises:
            ValueError: If strategy_id doesn't exist

        Example:
            >>> validation_data = [
            ...     ("analysis", True, 100.0),
            ...     ("analysis", True, 150.0),
            ...     ("analysis", False, 200.0),
            ... ]
            >>> is_valid = optimizer.validate_strategy("strategy1", validation_data)
        """
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy '{strategy_id}' not found")

        if not validation_tasks:
            return False

        # Calculate validation success rate
        successes = sum(1 for _, success, _ in validation_tasks if success)
        validation_success_rate = successes / len(validation_tasks)

        # Strategy is valid if it achieves >50% success rate
        return validation_success_rate > 0.5

    def merge_similar_strategies(
        self, strategy_ids: list[str], similarity_threshold: float = 0.8
    ) -> str | None:
        """
        Merge similar strategies into a single strategy.

        Combines strategies with similar parameters and performance into one.
        The merged strategy inherits the best characteristics of both.

        Time Complexity: O(n) where n is strategies to merge
        Space Complexity: O(1)

        Args:
            strategy_ids: List of strategy IDs to potentially merge
            similarity_threshold: Minimum similarity score (0.0-1.0) to merge

        Returns:
            ID of merged strategy if merge occurred, None otherwise

        Raises:
            ValueError: If any strategy_id doesn't exist

        Example:
            >>> merged_id = optimizer.merge_similar_strategies(
            ...     ["strategy1", "strategy2"],
            ...     similarity_threshold=0.8
            ... )
        """
        if len(strategy_ids) < 2:
            return None

        # Get all strategies
        strategies = []
        for strategy_id in strategy_ids:
            strategy = self.get_strategy(strategy_id)
            if not strategy:
                raise ValueError(f"Strategy '{strategy_id}' not found")
            strategies.append(strategy)

        # Check if strategies are similar enough to merge
        if not self._are_strategies_similar(strategies, similarity_threshold):
            return None

        # Create merged strategy
        merged_id = f"merged_{datetime.now().timestamp()}"
        merged_name = f"Merged: {' + '.join(s.name for s in strategies[:2])}"
        merged_description = (
            f"Merged from {len(strategies)} similar strategies: "
            f"{', '.join(s.strategy_id for s in strategies)}"
        )

        # Combine task types
        merged_task_types = list({tt for s in strategies for tt in s.task_types})

        # Merge parameters (take union of all parameters)
        merged_parameters = {}
        for strategy in strategies:
            merged_parameters.update(strategy.parameters)
        merged_parameters["merged_from"] = strategy_ids

        # Register merged strategy
        self.register_strategy(
            strategy_id=merged_id,
            name=merged_name,
            description=merged_description,
            task_types=merged_task_types,
            parameters=merged_parameters,
        )

        # Initialize with combined performance data
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Sum up all executions from merged strategies
            total_success = sum(s.success_count for s in strategies)
            total_failure = sum(s.failure_count for s in strategies)
            total_executions = total_success + total_failure
            success_rate = total_success / total_executions if total_executions > 0 else 0.0

            # Weighted average of execution times
            total_time = sum(s.avg_execution_time_ms * s.total_executions for s in strategies)
            avg_time = total_time / total_executions if total_executions > 0 else 0.0

            now = datetime.now().isoformat()

            cursor.execute(
                """
                UPDATE strategies
                SET total_executions = ?,
                    success_count = ?,
                    failure_count = ?,
                    success_rate = ?,
                    avg_execution_time_ms = ?,
                    last_updated = ?
                WHERE strategy_id = ?
            """,
                (
                    total_executions,
                    total_success,
                    total_failure,
                    success_rate,
                    avg_time,
                    now,
                    merged_id,
                ),
            )

            conn.commit()

        return merged_id

    def prune_poor_performers(
        self,
        min_executions: int = 20,
        max_failure_rate: float = 0.8,
    ) -> list[str]:
        """
        Remove strategies that consistently perform poorly.

        Identifies and removes strategies with high failure rates after
        sufficient trials. This prevents the system from wasting time
        on ineffective strategies.

        Time Complexity: O(n) where n is total strategies
        Space Complexity: O(k) where k is strategies to prune

        Args:
            min_executions: Minimum executions before considering for pruning
            max_failure_rate: Maximum failure rate (0.0-1.0) to tolerate

        Returns:
            List of pruned strategy IDs

        Example:
            >>> pruned = optimizer.prune_poor_performers(
            ...     min_executions=20,
            ...     max_failure_rate=0.8
            ... )
            >>> print(f"Pruned {len(pruned)} poor performers")
        """
        pruned_ids = []

        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Find strategies with high failure rates
            cursor.execute(
                """
                SELECT strategy_id, success_rate, total_executions
                FROM strategies
                WHERE total_executions >= ?
                AND success_rate < ?
            """,
                (min_executions, 1.0 - max_failure_rate),
            )

            for row in cursor.fetchall():
                strategy_id = row[0]
                pruned_ids.append(strategy_id)

                # Delete the strategy
                cursor.execute("DELETE FROM strategies WHERE strategy_id = ?", (strategy_id,))

            conn.commit()

        return pruned_ids

    def _are_strategies_similar(self, strategies: list[Strategy], threshold: float) -> bool:
        """
        Check if strategies are similar enough to merge.

        Compares strategies based on:
        - Task types overlap
        - Parameter similarity
        - Performance similarity

        Args:
            strategies: List of strategies to compare
            threshold: Similarity threshold (0.0-1.0)

        Returns:
            True if strategies are similar above threshold
        """
        if len(strategies) < 2:
            return False

        # Compare first strategy with all others
        base_strategy = strategies[0]

        for strategy in strategies[1:]:
            # Check task type overlap
            task_overlap = len(set(base_strategy.task_types) & set(strategy.task_types))
            task_union = len(set(base_strategy.task_types) | set(strategy.task_types))
            task_similarity = task_overlap / task_union if task_union > 0 else 0.0

            # Check parameter similarity
            base_params = set(base_strategy.parameters.keys())
            strategy_params = set(strategy.parameters.keys())
            param_overlap = len(base_params & strategy_params)
            param_union = len(base_params | strategy_params)
            param_similarity = param_overlap / param_union if param_union > 0 else 0.0

            # Check performance similarity (within 20% of each other)
            perf_diff = abs(base_strategy.success_rate - strategy.success_rate)
            perf_similarity = 1.0 - min(perf_diff / 0.2, 1.0)

            # Overall similarity is weighted average
            overall_similarity = (
                0.4 * task_similarity + 0.3 * param_similarity + 0.3 * perf_similarity
            )

            if overall_similarity < threshold:
                return False

        return True
