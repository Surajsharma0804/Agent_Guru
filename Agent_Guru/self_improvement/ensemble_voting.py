"""
Ensemble Voting System for Critical Tasks.

Uses multiple strategies to execute critical tasks and votes on the best result.
Improves reliability by reducing the impact of any single strategy failure.

**Validates: Requirements 9.5 (Adversarial Robustness - Ensemble Voting)**

Performance Requirements:
- Time Complexity: O(k * n) where k is ensemble size, n is task complexity
- Space Complexity: O(k) for storing k results
- Voting Latency: <50ms (95th percentile)

Design:
- Executes task with top N strategies in parallel
- Collects results and votes on best outcome
- Handles disagreements using confidence scoring
- Tracks ensemble performance vs single-strategy
- Automatically adjusts ensemble size based on task criticality

Author: Agent Guru Team
Date: 2026-02-28
"""

import asyncio
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from Agent_Guru.self_improvement.connection_pool import ConnectionPool
    from Agent_Guru.self_improvement.strategy_optimizer import Strategy


class VotingMethod(Enum):
    """Methods for voting on ensemble results."""

    MAJORITY = "majority"  # Simple majority vote
    WEIGHTED = "weighted"  # Weighted by strategy success rate
    CONFIDENCE = "confidence"  # Based on result confidence scores
    UNANIMOUS = "unanimous"  # Requires all strategies to agree


class TaskCriticality(Enum):
    """Criticality levels for tasks."""

    LOW = "low"  # Standard tasks, single strategy sufficient
    MEDIUM = "medium"  # Important tasks, use 3 strategies
    HIGH = "high"  # Critical tasks, use 5 strategies
    CRITICAL = "critical"  # Mission-critical, use 7+ strategies


@dataclass
class EnsembleResult:
    """Result from ensemble execution."""

    task_id: str
    task_type: str
    criticality: TaskCriticality
    strategies_used: list[str]
    individual_results: list[dict[str, Any]]
    voted_result: dict[str, Any]
    voting_method: VotingMethod
    agreement_score: float  # 0.0-1.0, how much strategies agreed
    execution_time_ms: float
    timestamp: datetime
    success: bool
    confidence: float  # 0.0-1.0, confidence in voted result


@dataclass
class EnsemblePerformanceMetrics:
    """Performance metrics for ensemble vs single-strategy."""

    total_ensemble_executions: int
    total_single_executions: int
    ensemble_success_rate: float
    single_success_rate: float
    ensemble_avg_time_ms: float
    single_avg_time_ms: float
    improvement_over_single: float  # Percentage improvement
    disagreement_rate: float  # How often strategies disagree


class EnsembleVotingSystem:
    """
    Manages ensemble voting for critical tasks.

    Executes tasks with multiple strategies and votes on the best result.
    Tracks performance to demonstrate reliability improvement.

    Time Complexity: O(k * n) where k is ensemble size
    Space Complexity: O(k) for storing results

    Example:
        >>> system = EnsembleVotingSystem(pool, strategy_optimizer)
        >>>
        >>> # Execute critical task with ensemble
        >>> result = await system.execute_with_ensemble(
        ...     task_id="critical_task_1",
        ...     task_type="security_validation",
        ...     task_executor=my_task_function,
        ...     criticality=TaskCriticality.HIGH,
        ...     voting_method=VotingMethod.WEIGHTED
        ... )
        >>>
        >>> print(f"Agreement: {result.agreement_score:.1%}")
        >>> print(f"Confidence: {result.confidence:.1%}")
        >>>
        >>> # Get performance metrics
        >>> metrics = system.get_performance_metrics()
        >>> print(f"Ensemble improvement: {metrics.improvement_over_single:.1%}")
    """

    def __init__(
        self,
        pool: "ConnectionPool",
        strategy_optimizer: Any,  # StrategyOptimizer
        default_voting_method: VotingMethod = VotingMethod.WEIGHTED,
        min_agreement_threshold: float = 0.6,
    ) -> None:
        """
        Initialize ensemble voting system.

        Args:
            pool: ConnectionPool for database access
            strategy_optimizer: StrategyOptimizer for getting strategies
            default_voting_method: Default voting method to use
            min_agreement_threshold: Minimum agreement score to accept result

        Raises:
            ValueError: If min_agreement_threshold not in [0.0, 1.0]
        """
        if not 0.0 <= min_agreement_threshold <= 1.0:
            raise ValueError(
                f"min_agreement_threshold must be in [0.0, 1.0], got {min_agreement_threshold}"
            )

        self.pool = pool
        self.strategy_optimizer = strategy_optimizer
        self.default_voting_method = default_voting_method
        self.min_agreement_threshold = min_agreement_threshold
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema for ensemble tracking."""
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ensemble_executions (
                    execution_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    criticality TEXT NOT NULL,
                    strategies_used TEXT NOT NULL,
                    individual_results TEXT NOT NULL,
                    voted_result TEXT NOT NULL,
                    voting_method TEXT NOT NULL,
                    agreement_score REAL NOT NULL,
                    execution_time_ms REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    confidence REAL NOT NULL
                )
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ensemble_timestamp
                ON ensemble_executions(timestamp)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ensemble_task_type
                ON ensemble_executions(task_type)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ensemble_criticality
                ON ensemble_executions(criticality)
            """
            )

            conn.commit()

    async def execute_with_ensemble(
        self,
        task_id: str,
        task_type: str,
        task_executor: Callable[[str, dict[str, Any]], Any],
        criticality: TaskCriticality = TaskCriticality.MEDIUM,
        voting_method: VotingMethod | None = None,
        task_context: dict[str, Any] | None = None,
    ) -> EnsembleResult:
        """
        Execute task with ensemble of strategies.

        Time Complexity: O(k * n) where k is ensemble size, n is task complexity
        Performance Target: <50ms voting overhead

        Args:
            task_id: Unique task identifier
            task_type: Type of task to execute
            task_executor: Async function that executes task with strategy
            criticality: Task criticality level
            voting_method: Voting method to use (default: weighted)
            task_context: Optional context for task execution

        Returns:
            EnsembleResult with voted outcome

        Example:
            >>> async def execute_task(strategy_id: str, params: dict) -> dict:
            ...     # Execute task with given strategy
            ...     return {"result": "success", "confidence": 0.9}
            >>>
            >>> result = await system.execute_with_ensemble(
            ...     task_id="task_1",
            ...     task_type="analysis",
            ...     task_executor=execute_task,
            ...     criticality=TaskCriticality.HIGH
            ... )
        """
        start_time = datetime.now()
        voting_method = voting_method or self.default_voting_method
        task_context = task_context or {}

        # Determine ensemble size based on criticality
        ensemble_size = self._get_ensemble_size(criticality)

        # Get top N strategies for this task type
        strategies = self._get_top_strategies(task_type, ensemble_size)

        if not strategies:
            raise ValueError(f"No strategies available for task type: {task_type}")

        # Execute task with each strategy in parallel
        individual_results = await self._execute_parallel(
            strategies, task_executor, task_context
        )

        # Vote on best result
        voted_result, agreement_score, confidence = self._vote_on_results(
            individual_results, strategies, voting_method
        )

        # Calculate execution time
        execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Determine success
        success = voted_result.get("success", False) and agreement_score >= self.min_agreement_threshold

        # Create result
        result = EnsembleResult(
            task_id=task_id,
            task_type=task_type,
            criticality=criticality,
            strategies_used=[s.strategy_id for s in strategies],
            individual_results=individual_results,
            voted_result=voted_result,
            voting_method=voting_method,
            agreement_score=agreement_score,
            execution_time_ms=execution_time_ms,
            timestamp=datetime.now(),
            success=success,
            confidence=confidence,
        )

        # Store result
        self._store_ensemble_result(result)

        return result

    def _get_ensemble_size(self, criticality: TaskCriticality) -> int:
        """
        Get ensemble size based on task criticality.

        Args:
            criticality: Task criticality level

        Returns:
            Number of strategies to use in ensemble
        """
        size_map = {
            TaskCriticality.LOW: 1,  # Single strategy
            TaskCriticality.MEDIUM: 3,  # 3 strategies
            TaskCriticality.HIGH: 5,  # 5 strategies
            TaskCriticality.CRITICAL: 7,  # 7 strategies
        }
        return size_map[criticality]

    def _get_top_strategies(self, task_type: str, count: int) -> list["Strategy"]:
        """
        Get top N strategies for task type.

        Args:
            task_type: Type of task
            count: Number of strategies to get

        Returns:
            List of top strategies sorted by success rate
        """
        strategies = self.strategy_optimizer.get_strategies_for_task_type(task_type)

        if not strategies:
            return []

        # Sort by success rate (descending), then by total executions
        strategies.sort(key=lambda s: (s.success_rate, s.total_executions), reverse=True)

        # Return top N
        return strategies[:count]

    async def _execute_parallel(
        self,
        strategies: list["Strategy"],
        task_executor: Callable[[str, dict[str, Any]], Any],
        task_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Execute task with multiple strategies in parallel.

        Time Complexity: O(k * n) where k is number of strategies

        Args:
            strategies: List of strategies to use
            task_executor: Function to execute task
            task_context: Context for task execution

        Returns:
            List of results from each strategy
        """
        tasks = []
        for strategy in strategies:
            # Create task for each strategy
            task = self._execute_with_strategy(strategy, task_executor, task_context)
            tasks.append(task)

        # Execute all in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "strategy_id": strategies[i].strategy_id,
                        "success": False,
                        "error": str(result),
                        "confidence": 0.0,
                    }
                )
            else:
                processed_results.append(result)

        return processed_results

    async def _execute_with_strategy(
        self,
        strategy: "Strategy",
        task_executor: Callable[[str, dict[str, Any]], Any],
        task_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute task with a single strategy.

        Args:
            strategy: Strategy to use
            task_executor: Function to execute task
            task_context: Context for task execution

        Returns:
            Result dictionary with strategy_id, success, and result data
        """
        try:
            # Execute task with strategy parameters
            result = await task_executor(strategy.strategy_id, strategy.parameters)

            # Ensure result is a dictionary
            if not isinstance(result, dict):
                result = {"result": result}

            # Add strategy metadata
            result["strategy_id"] = strategy.strategy_id
            if "success" not in result:
                result["success"] = True
            if "confidence" not in result:
                result["confidence"] = 0.8  # Default confidence

            return result

        except Exception as e:
            return {
                "strategy_id": strategy.strategy_id,
                "success": False,
                "error": str(e),
                "confidence": 0.0,
            }

    def _vote_on_results(
        self,
        results: list[dict[str, Any]],
        strategies: list["Strategy"],
        voting_method: VotingMethod,
    ) -> tuple[dict[str, Any], float, float]:
        """
        Vote on best result from ensemble.

        Time Complexity: O(k) where k is number of results
        Performance Target: <50ms

        Args:
            results: List of results from strategies
            strategies: List of strategies used
            voting_method: Method to use for voting

        Returns:
            Tuple of (voted_result, agreement_score, confidence)
        """
        if voting_method == VotingMethod.MAJORITY:
            return self._majority_vote(results)
        elif voting_method == VotingMethod.WEIGHTED:
            return self._weighted_vote(results, strategies)
        elif voting_method == VotingMethod.CONFIDENCE:
            return self._confidence_vote(results)
        elif voting_method == VotingMethod.UNANIMOUS:
            return self._unanimous_vote(results)
        else:
            raise ValueError(f"Unknown voting method: {voting_method}")

    def _majority_vote(
        self, results: list[dict[str, Any]]
    ) -> tuple[dict[str, Any], float, float]:
        """
        Simple majority vote on results.

        Args:
            results: List of results

        Returns:
            Tuple of (voted_result, agreement_score, confidence)
        """
        # Count successful results
        successful_results = [r for r in results if r.get("success", False)]

        if not successful_results:
            # All failed, return first failure
            return results[0], 0.0, 0.0

        # Find most common result (by serialized representation, excluding strategy_id)
        result_strings = []
        for r in successful_results:
            # Create copy without strategy_id for comparison
            r_copy = {k: v for k, v in r.items() if k != "strategy_id"}
            result_strings.append(json.dumps(r_copy, sort_keys=True))

        counter = Counter(result_strings)
        most_common_str, count = counter.most_common(1)[0]

        # Calculate agreement score
        agreement_score = count / len(results)

        # Deserialize most common result (use original with strategy_id)
        # Find first result that matches
        voted_result = None
        for r in successful_results:
            r_copy = {k: v for k, v in r.items() if k != "strategy_id"}
            if json.dumps(r_copy, sort_keys=True) == most_common_str:
                voted_result = r
                break

        if voted_result is None:
            voted_result = successful_results[0]

        # Calculate average confidence
        confidence = sum(r.get("confidence", 0.5) for r in successful_results) / len(
            successful_results
        )

        return voted_result, agreement_score, confidence

    def _weighted_vote(
        self, results: list[dict[str, Any]], strategies: list["Strategy"]
    ) -> tuple[dict[str, Any], float, float]:
        """
        Weighted vote based on strategy success rates.

        Args:
            results: List of results
            strategies: List of strategies (for weights)

        Returns:
            Tuple of (voted_result, agreement_score, confidence)
        """
        # Create strategy_id to success_rate mapping
        strategy_weights = {s.strategy_id: s.success_rate for s in strategies}

        # Weight each result by strategy success rate
        weighted_results = []
        total_weight = 0.0

        for result in results:
            if result.get("success", False):
                strategy_id = result.get("strategy_id")
                weight = strategy_weights.get(strategy_id, 0.5)
                weighted_results.append((result, weight))
                total_weight += weight

        if not weighted_results:
            # All failed
            return results[0], 0.0, 0.0

        # Find result with highest cumulative weight (excluding strategy_id)
        result_weights: dict[str, float] = {}
        result_map: dict[str, dict[str, Any]] = {}

        for result, weight in weighted_results:
            # Create copy without strategy_id for comparison
            result_copy = {k: v for k, v in result.items() if k != "strategy_id"}
            result_str = json.dumps(result_copy, sort_keys=True)
            result_weights[result_str] = result_weights.get(result_str, 0.0) + weight
            if result_str not in result_map:
                result_map[result_str] = result

        # Get result with highest weight
        best_result_str = max(result_weights.keys(), key=lambda k: result_weights[k])
        voted_result = result_map[best_result_str]

        # Calculate agreement score (weighted)
        agreement_score = result_weights[best_result_str] / total_weight

        # Calculate weighted average confidence
        confidence = sum(r.get("confidence", 0.5) * w for r, w in weighted_results) / total_weight

        return voted_result, agreement_score, confidence

    def _confidence_vote(
        self, results: list[dict[str, Any]]
    ) -> tuple[dict[str, Any], float, float]:
        """
        Vote based on result confidence scores.

        Args:
            results: List of results

        Returns:
            Tuple of (voted_result, agreement_score, confidence)
        """
        # Filter successful results
        successful_results = [r for r in results if r.get("success", False)]

        if not successful_results:
            return results[0], 0.0, 0.0

        # Sort by confidence (descending)
        successful_results.sort(key=lambda r: r.get("confidence", 0.0), reverse=True)

        # Return highest confidence result
        voted_result = successful_results[0]
        confidence = voted_result.get("confidence", 0.5)

        # Calculate agreement score (how many results have similar confidence)
        high_confidence_count = sum(
            1 for r in successful_results if r.get("confidence", 0.0) >= confidence * 0.9
        )
        agreement_score = high_confidence_count / len(results)

        return voted_result, agreement_score, confidence

    def _unanimous_vote(
        self, results: list[dict[str, Any]]
    ) -> tuple[dict[str, Any], float, float]:
        """
        Require unanimous agreement on result.

        Args:
            results: List of results

        Returns:
            Tuple of (voted_result, agreement_score, confidence)
        """
        # Check if all results are successful
        all_successful = all(r.get("success", False) for r in results)

        if not all_successful:
            return results[0], 0.0, 0.0

        # Check if all results are identical (excluding strategy_id)
        result_strings = []
        for r in results:
            r_copy = {k: v for k, v in r.items() if k != "strategy_id"}
            result_strings.append(json.dumps(r_copy, sort_keys=True))

        unique_results = set(result_strings)

        if len(unique_results) == 1:
            # Unanimous agreement
            voted_result = results[0]
            agreement_score = 1.0
            confidence = sum(r.get("confidence", 0.5) for r in results) / len(results)
            return voted_result, agreement_score, confidence
        else:
            # No unanimous agreement, return most common
            return self._majority_vote(results)

    def _store_ensemble_result(self, result: EnsembleResult) -> None:
        """
        Store ensemble result in database.

        Args:
            result: EnsembleResult to store
        """
        execution_id = f"ensemble_{result.task_id}_{result.timestamp.timestamp()}"

        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO ensemble_executions (
                    execution_id, task_id, task_type, criticality,
                    strategies_used, individual_results, voted_result,
                    voting_method, agreement_score, execution_time_ms,
                    timestamp, success, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    execution_id,
                    result.task_id,
                    result.task_type,
                    result.criticality.value,
                    json.dumps(result.strategies_used),
                    json.dumps(result.individual_results),
                    json.dumps(result.voted_result),
                    result.voting_method.value,
                    result.agreement_score,
                    result.execution_time_ms,
                    result.timestamp.isoformat(),
                    1 if result.success else 0,
                    result.confidence,
                ),
            )

            conn.commit()

    def get_performance_metrics(
        self, task_type: str | None = None, hours: int = 168
    ) -> EnsemblePerformanceMetrics:
        """
        Get performance metrics comparing ensemble vs single-strategy.

        Time Complexity: O(n) where n is executions in window

        Args:
            task_type: Optional filter by task type
            hours: Number of hours to analyze (default: 7 days)

        Returns:
            EnsemblePerformanceMetrics with comparison data

        Example:
            >>> metrics = system.get_performance_metrics(task_type="security_validation")
            >>> print(f"Ensemble success rate: {metrics.ensemble_success_rate:.1%}")
            >>> print(f"Single success rate: {metrics.single_success_rate:.1%}")
            >>> print(f"Improvement: {metrics.improvement_over_single:.1%}")
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_iso = cutoff.isoformat()

        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Get ensemble execution stats
            query = """
                SELECT COUNT(*), AVG(success), AVG(execution_time_ms), AVG(agreement_score)
                FROM ensemble_executions
                WHERE timestamp >= ?
            """
            params: list[Any] = [cutoff_iso]

            if task_type:
                query += " AND task_type = ?"
                params.append(task_type)

            cursor.execute(query, params)
            ensemble_row = cursor.fetchone()

            ensemble_count = ensemble_row[0] or 0
            ensemble_success_rate = ensemble_row[1] or 0.0
            ensemble_avg_time = ensemble_row[2] or 0.0
            disagreement_rate = 1.0 - (ensemble_row[3] or 1.0)

            # Get single-strategy execution stats from task_executions table if it exists
            single_count = 0
            single_success_rate = 0.0
            single_avg_time = 0.0

            try:
                # Check if task_executions table exists
                cursor.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='task_executions'
                """
                )

                if cursor.fetchone():
                    query = """
                        SELECT COUNT(*), AVG(success), AVG(execution_time_ms)
                        FROM task_executions
                        WHERE timestamp >= ?
                    """
                    params = [cutoff_iso]

                    if task_type:
                        query += " AND task_type = ?"
                        params.append(task_type)

                    cursor.execute(query, params)
                    single_row = cursor.fetchone()

                    single_count = single_row[0] or 0
                    single_success_rate = single_row[1] or 0.0
                    single_avg_time = single_row[2] or 0.0
            except Exception:
                # Table doesn't exist or query failed, use defaults
                pass

        # Calculate improvement
        if single_success_rate > 0:
            improvement = (ensemble_success_rate - single_success_rate) / single_success_rate
        else:
            improvement = 0.0

        return EnsemblePerformanceMetrics(
            total_ensemble_executions=ensemble_count,
            total_single_executions=single_count,
            ensemble_success_rate=ensemble_success_rate,
            single_success_rate=single_success_rate,
            ensemble_avg_time_ms=ensemble_avg_time,
            single_avg_time_ms=single_avg_time,
            improvement_over_single=improvement,
            disagreement_rate=disagreement_rate,
        )

    def should_use_ensemble(
        self, task_type: str, task_context: dict[str, Any] | None = None
    ) -> tuple[bool, TaskCriticality]:
        """
        Determine if ensemble should be used for a task.

        Uses heuristics to determine task criticality and whether
        ensemble voting would be beneficial.

        Args:
            task_type: Type of task
            task_context: Optional context for criticality assessment

        Returns:
            Tuple of (should_use_ensemble, criticality_level)

        Example:
            >>> use_ensemble, criticality = system.should_use_ensemble(
            ...     task_type="security_validation",
            ...     task_context={"user_data": True, "financial": True}
            ... )
            >>> if use_ensemble:
            ...     result = await system.execute_with_ensemble(...)
        """
        task_context = task_context or {}

        # Determine criticality based on task type and context
        criticality = TaskCriticality.LOW

        # High criticality task types
        high_criticality_types = [
            "security_validation",
            "financial_transaction",
            "medical_diagnosis",
            "safety_check",
        ]

        if task_type in high_criticality_types:
            criticality = TaskCriticality.HIGH

        # Check context for criticality indicators
        # Use value comparison for enum ordering
        criticality_values = {
            TaskCriticality.LOW: 0,
            TaskCriticality.MEDIUM: 1,
            TaskCriticality.HIGH: 2,
            TaskCriticality.CRITICAL: 3,
        }

        if task_context.get("user_data", False):
            if criticality_values[criticality] < criticality_values[TaskCriticality.MEDIUM]:
                criticality = TaskCriticality.MEDIUM

        if task_context.get("financial", False):
            if criticality_values[criticality] < criticality_values[TaskCriticality.HIGH]:
                criticality = TaskCriticality.HIGH

        if task_context.get("safety_critical", False):
            criticality = TaskCriticality.CRITICAL

        # Use ensemble for medium criticality and above
        should_use = criticality != TaskCriticality.LOW

        return should_use, criticality
