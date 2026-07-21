"""Self-Improvement Engine - Main API for Agent Guru.

This is the core interface for all self-improvement operations. It coordinates
all learning components and provides a unified API for the agent orchestration
system to record task executions and retrieve optimized strategies.

**Validates: Requirements 1-10, All acceptance criteria**

Performance Requirements:
- Time Complexity: O(1) for task recording, O(log n) for strategy selection
- Space Complexity: O(n) where n is number of task executions
- Latency: <50ms for record_task_execution (95th percentile)
- Latency: <10ms for get_optimal_strategy (95th percentile)

Architecture:
- Coordinates: FailureAnalyzer, StrategyOptimizer, PromptEvolutionSystem,
  PerformanceTracker, MetaLearner, GitIntegration
- Provides: Unified API for task execution recording and strategy selection
- Implements: Improvement measurement and reporting every 100 tasks

Author: Agent Guru Team
Date: 2026-02-28
Version: 1.0.0
"""

import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

from Agent_Guru.self_improvement.connection_pool import ConnectionPool  # noqa: E402
from Agent_Guru.self_improvement.database_schema import DatabaseSchema  # noqa: E402
from Agent_Guru.self_improvement.failure_analyzer import (  # noqa: E402
    FailureAnalyzer,
    FailureType,
    TaskExecution,
)
from Agent_Guru.self_improvement.meta_learner import (  # noqa: E402
    MetaLearner,
)
from Agent_Guru.self_improvement.performance_tracker import (  # noqa: E402
    PerformanceTracker,
)
from Agent_Guru.self_improvement.prompt_evolution import (  # noqa: E402
    PromptEvolutionSystem,
)
from Agent_Guru.self_improvement.strategy_optimizer import (  # noqa: E402
    Strategy,
    StrategyOptimizer,
)


class SelfImprovementEngine:
    """Main interface for self-improvement operations.

    Coordinates all learning components and provides unified API for
    Agent Orchestration to record task executions and retrieve optimized
    strategies and prompts.

    Time Complexity:
        - record_task_execution: O(1) amortized
        - get_optimal_strategy: O(log n) where n is strategies
        - get_evolved_prompt: O(1)
        - get_improvement_metrics: O(1)

    Space Complexity: O(n) where n is number of task executions

    Example:
        >>> engine = SelfImprovementEngine(
        ...     storage_path="data/self_improvement.db",
        ...     improvement_threshold=0.15,
        ...     measurement_window=100
        ... )
        >>>
        >>> # Record task execution
        >>> engine.record_task_execution(
        ...     task_id="task_1",
        ...     task_type="analysis",
        ...     strategy_used="chain_of_thought",
        ...     success=True,
        ...     execution_time_ms=150.0
        ... )
        >>>
        >>> # Get optimal strategy for next task
        >>> strategy = engine.get_optimal_strategy("analysis")
        >>> print(f"Use strategy: {strategy.name}")
        >>>
        >>> # Get improvement metrics
        >>> metrics = engine.get_improvement_metrics()
        >>> print(f"Success rate: {metrics['success_rate']:.2%}")

    """

    def __init__(
        self,
        storage_path: str,
        improvement_threshold: float = 0.15,
        measurement_window: int = 100,
        enable_git_commits: bool = False,
        git_repo_path: str | None = None,
    ) -> None:
        """Initialize self-improvement engine.

        Args:
            storage_path: Path to SQLite database
            improvement_threshold: Minimum relative improvement required (15%)
            measurement_window: Number of tasks for improvement measurement (100)
            enable_git_commits: Whether to enable Git commits (default: False)
            git_repo_path: Path to Git repository (required if enable_git_commits=True)

        Raises:
            ValueError: If enable_git_commits=True but git_repo_path is None

        Time Complexity: O(1)
        Space Complexity: O(1)

        """
        if enable_git_commits and not git_repo_path:
            msg = "git_repo_path required when enable_git_commits=True"
            raise ValueError(msg)

        self.storage_path = storage_path
        self.improvement_threshold = improvement_threshold
        self.measurement_window = measurement_window
        self.enable_git_commits = enable_git_commits
        self.git_repo_path = git_repo_path

        # Initialize database schema
        DatabaseSchema.create_schema(storage_path)

        # Initialize connection pool
        self.pool = ConnectionPool(storage_path, min_size=2, max_size=10)

        # Initialize components
        self.failure_analyzer = FailureAnalyzer(self.pool)
        self.strategy_optimizer = StrategyOptimizer(self.pool)
        self.prompt_evolution = PromptEvolutionSystem(self.pool)
        self.performance_tracker = PerformanceTracker(self.pool)
        self.meta_learner = MetaLearner(storage_path)

        # Conflict resolution
        from Agent_Guru.self_improvement.conflict_resolution import ConflictResolver
        self.conflict_resolver = ConflictResolver(self.pool)

        # Git integration (optional)
        self.git_integration = None
        if enable_git_commits and git_repo_path:
            # Import only if needed
            from Agent_Guru.self_improvement.git_integration import GitIntegration

            self.git_integration = GitIntegration(git_repo_path)

        # P2-53: Lock protects _task_sequence from concurrent mutation
        self._lock = threading.Lock()
        # Task sequence counter
        self._task_sequence = self._get_current_task_sequence()

    def _get_current_task_sequence(self) -> int:
        """Get current task sequence number.

        Returns:
            Current task sequence number

        Time Complexity: O(1)

        """
        return self.performance_tracker.get_task_count()

    def record_task_execution(
        self,
        task_id: str,
        task_type: str,
        strategy_used: str,
        success: bool,
        execution_time_ms: float,
        error_details: dict | None = None,
        context: dict | None = None,
        reasoning_quality: float | None = None,
        tool_selection_correct: bool | None = None,
        hallucination_detected: bool | None = None,
    ) -> None:
        """Record task execution outcome for learning.

        This is the main entry point called by Agent Orchestration after
        each task execution. It triggers all learning components.

        Args:
            task_id: Unique task identifier
            task_type: Type of task executed
            strategy_used: Strategy ID that was used
            success: Whether task succeeded
            execution_time_ms: Task execution time in milliseconds
            error_details: Details if task failed (optional)
            context: Additional context about execution (optional)
            reasoning_quality: Quality of reasoning 0.0-1.0 (optional)
            tool_selection_correct: Whether tools were selected correctly (optional)
            hallucination_detected: Whether hallucination was detected (optional)

        Time Complexity: O(1) amortized
        Performance Target: <50ms (95th percentile)

        Validates: Requirements 1.1, 2.1, 4.1, 6.1

        """
        start_time = time.time()

        # Increment task sequence
        self._task_sequence += 1

        # Classify failure type if task failed
        failure_type = None
        if not success:
            failure_type = self._classify_failure(error_details)

        # Create execution record
        execution = TaskExecution(
            task_id=task_id,
            task_type=task_type,
            strategy_id=strategy_used,
            timestamp=datetime.now(tz=UTC),
            success=success,
            execution_time_ms=execution_time_ms,
            failure_type=failure_type,
            error_details=error_details,
            context=context or {},
        )

        # Infer quality metrics if not provided
        if reasoning_quality is None:
            reasoning_quality = 1.0 if success else 0.0
        if tool_selection_correct is None:
            tool_selection_correct = success
        if hallucination_detected is None:
            hallucination_detected = False

        # Record in performance tracker
        self.performance_tracker.record_task_metrics(
            task_id=task_id,
            task_type=task_type,
            strategy_id=strategy_used,
            success=success,
            execution_time_ms=execution_time_ms,
            reasoning_quality=reasoning_quality,
            tool_selection_correct=tool_selection_correct,
            hallucination_detected=hallucination_detected,
            task_sequence_number=self._task_sequence,
        )

        # If failed, analyze failure
        if not success:
            self.failure_analyzer.analyze_failure(execution)

        # Update strategy performance
        self.strategy_optimizer.update_strategy_performance(
            strategy_used,
            success,
            execution_time_ms,
        )

        # Feed to meta-learner
        self.meta_learner.process_execution(execution)

        # Commit to Git if enabled
        if self.git_integration:
            self._commit_execution_data(execution)

        # Check if we've hit measurement window
        if self._task_sequence % self.measurement_window == 0:
            self._generate_improvement_report()

        # Performance monitoring
        elapsed_ms = (time.time() - start_time) * 1000
        if elapsed_ms > 50:
            logger.warning("record_task_execution took %.2fms (target: <50ms)", elapsed_ms)

    def get_optimal_strategy(self, task_type: str, context: dict | None = None) -> Strategy | None:
        """Get the optimal strategy for a task type.

        Uses meta-learner to match context patterns and strategy optimizer
        to select highest-performing strategy with exploration.

        Args:
            task_type: Type of task to execute
            context: Optional context for pattern matching

        Returns:
            Strategy with highest success rate for this task type, or None

        Time Complexity: O(log n) where n is strategies for task_type
        Performance Target: <10ms (95th percentile)

        Validates: Requirements 2.3, 5.4

        """
        start_time = time.time()

        # Get pattern-based recommendations from meta-learner
        recommended_strategy_ids = self.meta_learner.recommend_strategies(task_type, context)

        # Get performance-based ranking from strategy optimizer
        if recommended_strategy_ids:
            ranked_strategies = self.strategy_optimizer.rank_strategies(
                task_type,
                recommended_strategy_ids,
            )
        else:
            # No pattern recommendations, use all strategies
            ranked_strategies = self.strategy_optimizer.rank_strategies(task_type)

        # Select with exploration (epsilon-greedy)
        if ranked_strategies:
            strategy = self.strategy_optimizer.select_strategy_with_exploration(task_type)
        else:
            strategy = None

        # Performance monitoring
        elapsed_ms = (time.time() - start_time) * 1000
        if elapsed_ms > 10:
            logger.warning("get_optimal_strategy took %.2fms (target: <10ms)", elapsed_ms)

        return strategy

    def get_evolved_prompt(
        self,
        prompt_type: str,
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """Get evolved prompt for LLM Runtime.

        Returns the current best-performing prompt version for the given type.

        Args:
            prompt_type: Type of prompt needed
            context: Context for prompt generation (optional, not used yet)

        Returns:
            Evolved prompt text, or None if no prompt registered

        Time Complexity: O(1)
        Performance Target: <5ms

        Validates: Requirements 3.4

        """
        prompt_version = self.prompt_evolution.get_active_prompt(prompt_type)

        if prompt_version:
            return prompt_version.content
        return None

    def record_llm_response(
        self,
        prompt_id: str,
        response: str,
        was_successful: bool,
        hallucination_detected: bool,
    ) -> None:
        """Record LLM response quality for prompt evolution.

        Called by LLM Runtime after each LLM invocation to track prompt
        performance and trigger prompt evolution if needed.

        Args:
            prompt_id: ID of prompt that was used
            response: LLM response text
            was_successful: Whether response led to successful task
            hallucination_detected: Whether hallucination was detected

        Time Complexity: O(1)

        Validates: Requirements 3.2, 3.5

        """
        # Record prompt outcome
        self.prompt_evolution.record_prompt_outcome(
            prompt_id,
            was_successful,
            hallucination_detected,
        )

        # If hallucination detected, record in failure analyzer
        if hallucination_detected:
            self.failure_analyzer.record_hallucination(prompt_id, response)

    def get_improvement_metrics(self) -> dict[str, Any]:
        """Get current improvement metrics.

        Returns comprehensive metrics including success rate, reasoning
        accuracy, efficiency, and improvement over baseline.

        Returns:
            Dictionary with current metrics:
            - success_rate: Current success rate (0.0-1.0)
            - avg_execution_time_ms: Average execution time
            - avg_reasoning_quality: Average reasoning quality (0.0-1.0)
            - tool_selection_rate: Tool selection accuracy (0.0-1.0)
            - hallucination_rate: Hallucination rate (0.0-1.0)
            - total_tasks: Total tasks executed
            - improvement: Improvement metrics vs baseline (if available)

        Time Complexity: O(1)
        Performance Target: <10ms

        Validates: Requirements 4.7, 7.6

        """
        # Get current aggregate metrics
        current = self.performance_tracker.get_current_metrics()

        # Calculate improvement if enough data
        improvement = None
        if self._task_sequence >= 20:  # Need at least 20 tasks
            improvement = self.performance_tracker.calculate_improvement(
                baseline_size=10,
                recent_size=10,
            )

        # Build metrics dictionary
        metrics: dict[str, Any] = {
            "success_rate": current.success_rate,
            "avg_execution_time_ms": current.avg_execution_time_ms,
            "avg_reasoning_quality": current.avg_reasoning_quality,
            "tool_selection_rate": current.tool_selection_rate,
            "hallucination_rate": current.hallucination_rate,
            "total_tasks": current.total_tasks,
            "task_sequence": self._task_sequence,
        }

        if improvement:
            metrics["improvement"] = improvement

        return metrics

    def inject_test_failure(
        self,
        failure_type: FailureType,
        task_type: str,
        context: dict[str, Any],
        strategy_id: str = "test_strategy",
        record_in_tracker: bool = False,
    ) -> str:
        """Inject a test failure for validation.

        Used by testing framework to verify learning effectiveness.
        Test failures are processed identically to real failures but
        are not committed to Git by default.

        Args:
            failure_type: Type of failure to inject
            task_type: Task type for the failure
            context: Failure context
            strategy_id: Strategy ID to associate with failure (default: "test_strategy")
            record_in_tracker: Whether to record in performance tracker (default: False)

        Returns:
            Task ID of injected failure

        Time Complexity: O(1)

        Validates: Requirements 8.1, 8.2, 8.3

        """
        # Generate unique task ID with more precision
        import secrets

        task_id = f"test_{int(time.time() * 1000000)}_{secrets.randbelow(9999 - 1000 + 1) + 1000}"

        # Create appropriate error details based on failure type
        error_details: dict[str, Any] = {"test": True, "context": context}

        if failure_type == FailureType.REASONING_ERROR:
            error_details.update(
                {
                    "type": "reasoning_error",
                    "reasoning_step": context.get("reasoning_step", "unknown"),
                    "logical_error": context.get("logical_error", "test_error"),
                },
            )
        elif failure_type == FailureType.TOOL_ERROR:
            error_details.update(
                {
                    "type": "tool_error",
                    "tool_name": context.get("tool_name", "test_tool"),
                    "misuse_pattern": context.get("misuse_pattern", "incorrect_parameters"),
                },
            )
        elif failure_type == FailureType.HALLUCINATION:
            error_details.update(
                {
                    "type": "hallucination",
                    "hallucination_content": context.get(
                        "hallucination_content",
                        "fabricated_data",
                    ),
                    "correct_content": context.get("correct_content", "actual_data"),
                },
            )
        elif failure_type == FailureType.TIMEOUT:
            error_details.update(
                {
                    "type": "timeout",
                    "timeout_ms": context.get("timeout_ms", 5000),
                    "operation": context.get("operation", "test_operation"),
                },
            )
        elif failure_type == FailureType.RESOURCE_ERROR:
            error_details.update(
                {
                    "type": "resource_error",
                    "resource_type": context.get("resource_type", "memory"),
                    "limit_exceeded": context.get("limit_exceeded", True),
                },
            )
        else:
            error_details.update(
                {"type": "unknown", "description": context.get("description", "unknown_error")},
            )

        # Create test execution
        test_execution = TaskExecution(
            task_id=task_id,
            task_type=task_type,
            strategy_id=strategy_id,
            timestamp=datetime.now(tz=UTC),
            success=False,
            execution_time_ms=context.get("execution_time_ms", 0.0),
            failure_type=failure_type,
            error_details=error_details,
            context=context,
        )

        # Analyze failure
        self.failure_analyzer.analyze_failure(test_execution)

        # Optionally record in performance tracker
        if record_in_tracker:
            self.performance_tracker.record_task_metrics(
                task_id=task_id,
                task_type=task_type,
                strategy_id=strategy_id,
                success=False,
                execution_time_ms=test_execution.execution_time_ms,
                reasoning_quality=0.0,
                tool_selection_correct=False,
                hallucination_detected=(failure_type == FailureType.HALLUCINATION),
                task_sequence_number=self._task_sequence + 1,
            )

            # Update strategy performance
            self.strategy_optimizer.update_strategy_performance(
                strategy_id,
                False,
                test_execution.execution_time_ms,
            )

            # Increment task sequence
            self._task_sequence += 1

        return task_id

    def inject_multiple_failures(
        self,
        failure_configs: list[dict[str, Any]],
        record_in_tracker: bool = False,
    ) -> list[str]:
        """Inject multiple test failures in batch.

        Useful for testing learning convergence with many failures.

        Args:
            failure_configs: List of failure configurations, each containing:
                - failure_type: FailureType
                - task_type: str
                - context: Dict[str, Any]
                - strategy_id: str (optional)
            record_in_tracker: Whether to record in performance tracker

        Returns:
            List of task IDs for injected failures

        Time Complexity: O(n) where n is number of failures

        Validates: Requirements 8.3, 8.6

        """
        task_ids = []

        for config in failure_configs:
            task_id = self.inject_test_failure(
                failure_type=config["failure_type"],
                task_type=config["task_type"],
                context=config.get("context", {}),
                strategy_id=config.get("strategy_id", "test_strategy"),
                record_in_tracker=record_in_tracker,
            )
            task_ids.append(task_id)

        return task_ids

    def _classify_failure(self, error_details: dict | None) -> FailureType:
        """Classify failure type from error details.

        Args:
            error_details: Error details dictionary

        Returns:
            Classified failure type

        Time Complexity: O(1)

        """
        if not error_details:
            return FailureType.UNKNOWN

        error_type = error_details.get("type", "").lower()

        if "reasoning" in error_type or "logic" in error_type:
            return FailureType.REASONING_ERROR
        if "tool" in error_type or "function" in error_type:
            return FailureType.TOOL_ERROR
        if "hallucination" in error_type or "fabrication" in error_type:
            return FailureType.HALLUCINATION
        if "timeout" in error_type:
            return FailureType.TIMEOUT
        if "resource" in error_type or "memory" in error_type:
            return FailureType.RESOURCE_ERROR
        return FailureType.UNKNOWN

    def _generate_improvement_report(self) -> None:
        """Generate improvement report after measurement window.

        Calculates improvement metrics, checks against threshold,
        and commits report to Git if enabled.

        Time Complexity: O(1)

        Validates: Requirements 4.2, 4.3, 7.2, 7.3
        """
        # Calculate improvement
        improvement = self.performance_tracker.calculate_improvement(
            baseline_size=10,
            recent_size=10,
        )

        if not improvement:
            logger.warning("Insufficient data for improvement calculation")
            return

        # Calculate statistical significance
        significance = self.performance_tracker.calculate_statistical_significance(
            baseline_size=10,
            recent_size=10,
        )

        # Build report
        report = {
            "measurement_window": self.measurement_window,
            "total_tasks": self._task_sequence,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "improvement": improvement,
            "statistical_significance": significance,
            "threshold_met": improvement["relative_improvement"]
            >= (self.improvement_threshold * 100),
        }

        # Commit report to Git if enabled
        if self.git_integration:
            self._commit_improvement_report(report)

        # Check if improvement threshold met
        if not report["threshold_met"]:
            self._trigger_improvement_alert(report)

    def _trigger_improvement_alert(self, report: dict[str, Any]) -> None:
        """Trigger alert if improvement targets not met.

        Args:
            report: Improvement report

        Time Complexity: O(1)

        Validates: Requirements 7.5

        """
        logger.warning(
            "Improvement target not met! Target: %.1f%%, Actual: %.1f%%, Tasks: %d",
            self.improvement_threshold * 100,
            report["improvement"]["relative_improvement"],
            report["total_tasks"],
        )
        # Could integrate with monitoring system here
        # For now, just log the alert

    def _commit_execution_data(self, execution: TaskExecution) -> None:
        """Commit execution data to Git.

        Args:
            execution: Task execution to commit

        Time Complexity: O(1)

        """
        if not self.git_integration:
            return

        # Prepare commit data
        commit_data = {
            "task_id": execution.task_id,
            "task_type": execution.task_type,
            "strategy_id": execution.strategy_id,
            "success": execution.success,
            "execution_time_ms": execution.execution_time_ms,
            "timestamp": execution.timestamp.isoformat(),
        }

        # Commit to Git
        try:
            self.git_integration.commit_execution_data(
                execution=commit_data,
            )
        except Exception as e:
            logger.warning("Git commit failed for task %s: %s", execution.task_id, e)
            # Don't fail the task execution if Git commit fails

    def _commit_improvement_report(self, report: dict[str, Any]) -> None:
        """Commit improvement report to Git.

        Args:
            report: Improvement report

        Time Complexity: O(1)

        """
        if not self.git_integration:
            return

        try:
            self.git_integration.commit_improvement_report(
                report=report,
            )
        except Exception as e:
            logger.warning("Git commit failed for improvement report: %s", e)

    def close(self) -> None:
        """Close all resources.

        Should be called when engine is no longer needed.

        Time Complexity: O(1)
        """
        # Meta-learner uses context-managed sqlite3 connections (no close needed)

        # Close connection pool
        if hasattr(self, "pool") and self.pool:
            try:
                self.pool.close_all()
            except Exception as e:
                logger.warning("Error closing connection pool: %s", e)

        # Small delay to ensure Windows releases file locks
        import time

        time.sleep(0.05)

    def detect_contradictory_feedback(
        self,
        task_type: str,
        strategy_id: str,
        recent_window: int = 20,
        min_executions: int = 5,
    ):
        """Detect contradictory feedback for a task type and strategy.

        Fetches recent execution data and passes to conflict resolver.

        Args:
            task_type: Type of task to analyze
            strategy_id: Strategy ID to analyze
            recent_window: Number of recent executions to analyze
            min_executions: Minimum executions required

        Returns:
            ConflictDetection result

        Validates: Requirements 9.1

        """
        # Import here to avoid circular dependency
        from Agent_Guru.self_improvement.conflict_resolution import TaskExecutionData

        # Fetch recent executions from database
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT task_id, task_type, strategy_id, success, execution_time_ms,
                       timestamp, reasoning_quality, tool_selection_correct, hallucination_detected
                FROM metrics
                WHERE task_type = ? AND strategy_id = ?
                ORDER BY task_sequence_number DESC
                LIMIT ?
            """,
                (task_type, strategy_id, recent_window),
            )

            executions = []
            for row in cursor.fetchall():
                executions.append(
                    TaskExecutionData(
                        task_id=row[0],
                        task_type=row[1],
                        strategy_id=row[2],
                        success=bool(row[3]),
                        execution_time_ms=row[4],
                        timestamp=datetime.fromisoformat(row[5]),
                        reasoning_quality=row[6],
                        tool_selection_correct=bool(row[7]) if row[7] is not None else None,
                        hallucination_detected=bool(row[8]),
                    ),
                )

        # Detect conflicts using conflict resolver
        return self.conflict_resolver.detect_contradictory_feedback(
            executions=executions,
            min_executions=min_executions,
        )

    def detect_data_poisoning(
        self,
        task_type: str,
        lookback_window: int = 50,
        anomaly_threshold: float = 3.0,
    ):
        """Detect data poisoning for a task type.

        Fetches recent execution data and passes to conflict resolver.

        Args:
            task_type: Type of task to analyze
            lookback_window: Number of recent executions to analyze
            anomaly_threshold: Z-score threshold for anomaly detection

        Returns:
            ConflictDetection result

        Validates: Requirements 9.3

        """
        # Import here to avoid circular dependency
        from Agent_Guru.self_improvement.conflict_resolution import TaskExecutionData

        # Fetch recent executions from database
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT task_id, task_type, strategy_id, success, execution_time_ms,
                       timestamp, reasoning_quality, tool_selection_correct, hallucination_detected
                FROM metrics
                WHERE task_type = ?
                ORDER BY task_sequence_number DESC
                LIMIT ?
            """,
                (task_type, lookback_window),
            )

            executions = []
            for row in cursor.fetchall():
                executions.append(
                    TaskExecutionData(
                        task_id=row[0],
                        task_type=row[1],
                        strategy_id=row[2],
                        success=bool(row[3]),
                        execution_time_ms=row[4],
                        timestamp=datetime.fromisoformat(row[5]),
                        reasoning_quality=row[6],
                        tool_selection_correct=bool(row[7]) if row[7] is not None else None,
                        hallucination_detected=bool(row[8]),
                    ),
                )

        # Detect poisoning using conflict resolver
        return self.conflict_resolver.detect_data_poisoning(
            executions=executions,
            anomaly_threshold=anomaly_threshold,
        )
