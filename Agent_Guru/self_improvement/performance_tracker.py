"""Performance Tracker for Self-Improvement Engine.

Measures and tracks agent improvement over time with statistical rigor.
Implements baseline calculation and improvement reporting.

**Validates: Requirements 4.1-4.7, 7.1-7.7**

Performance Requirements:
- Time Complexity: O(1) for metric recording
- Space Complexity: O(n) where n is number of task executions
- Metric Calculation Latency: <10ms (95th percentile)

Schema Alignment:
- Uses existing metrics table from database_schema.py
- Columns: metric_id, task_id, task_type, strategy_id, timestamp, success,
  execution_time_ms, reasoning_quality, tool_selection_correct,
  hallucination_detected, task_sequence_number, window_start, window_end

Author: Agent Guru Team
Date: 2026-02-28
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import numpy as np
from scipy import stats

if TYPE_CHECKING:
    from Agent_Guru.self_improvement.connection_pool import ConnectionPool


@dataclass
class TaskMetrics:
    """Metrics for a single task execution."""

    task_id: str
    task_type: str
    strategy_id: str
    success: bool
    execution_time_ms: float
    reasoning_quality: float  # 0.0-1.0 (1.0 = perfect reasoning)
    tool_selection_correct: bool
    hallucination_detected: bool
    task_sequence_number: int
    timestamp: datetime


@dataclass
class AggregateMetrics:
    """Aggregate metrics over a window of tasks."""

    success_rate: float
    avg_execution_time_ms: float
    avg_reasoning_quality: float
    tool_selection_rate: float
    hallucination_rate: float
    total_tasks: int
    window_start: datetime
    window_end: datetime


class PerformanceTracker:
    """Tracks agent performance metrics over time.

    Measures improvement by comparing baseline (first 10 tasks) to
    current performance. Provides statistical evidence of improvement.

    Time Complexity: O(1) for metric recording
    Space Complexity: O(n) where n is number of task executions

    Example:
        >>> tracker = PerformanceTracker(pool)
        >>> tracker.record_task_metrics(
        ...     task_id="task_1",
        ...     task_type="analysis",
        ...     strategy_id="strategy_1",
        ...     success=True,
        ...     execution_time_ms=150.0,
        ...     reasoning_quality=0.95,
        ...     tool_selection_correct=True,
        ...     hallucination_detected=False,
        ...     task_sequence_number=1
        ... )
        >>> metrics = tracker.get_current_metrics()

    """

    def __init__(self, pool: "ConnectionPool") -> None:
        """Initialize performance tracker.

        Args:
            pool: ConnectionPool for database access

        Raises:
            RuntimeError: If metrics table doesn't exist

        """
        self.pool = pool
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema for metrics.

        Note: DatabaseSchema.create_schema() should be called first.
        This method only verifies the table exists.
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Verify metrics table exists
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='metrics'
            """,
            )

            if not cursor.fetchone():
                msg = "Metrics table not found. Call DatabaseSchema.create_schema() first."
                raise RuntimeError(
                    msg,
                )

    def record_task_metrics(
        self,
        task_id: str,
        task_type: str,
        strategy_id: str,
        success: bool,
        execution_time_ms: float,
        reasoning_quality: float,
        tool_selection_correct: bool,
        hallucination_detected: bool,
        task_sequence_number: int,
    ) -> None:
        """Record metrics for a task execution.

        Time Complexity: O(1) - single database insert

        Args:
            task_id: Unique task identifier
            task_type: Type of task
            strategy_id: Strategy used for this task
            success: Whether task succeeded
            execution_time_ms: Execution time in milliseconds
            reasoning_quality: Reasoning quality (0.0-1.0, 1.0 = perfect)
            tool_selection_correct: Whether correct tools were selected
            hallucination_detected: Whether hallucination was detected
            task_sequence_number: Sequential task number

        Raises:
            ValueError: If reasoning_quality not in [0.0, 1.0]

        """
        if not 0.0 <= reasoning_quality <= 1.0:
            msg = f"Reasoning quality must be in [0.0, 1.0], got {reasoning_quality}"
            raise ValueError(msg)

        with self.pool.connection() as conn:
            cursor = conn.cursor()

            now = datetime.now(tz=UTC).isoformat()
            metric_id = f"metric_{task_id}_{task_sequence_number}"

            cursor.execute(
                """
                INSERT INTO metrics (
                    metric_id, task_id, task_type, strategy_id, timestamp,
                    success, execution_time_ms, reasoning_quality,
                    tool_selection_correct, hallucination_detected,
                    task_sequence_number, window_start, window_end
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metric_id,
                    task_id,
                    task_type,
                    strategy_id,
                    now,
                    1 if success else 0,
                    execution_time_ms,
                    reasoning_quality,
                    1 if tool_selection_correct else 0,
                    1 if hallucination_detected else 0,
                    task_sequence_number,
                    task_sequence_number,  # window_start = current task number
                    task_sequence_number,  # window_end = current task number
                ),
            )

            conn.commit()

    def get_current_metrics(self) -> AggregateMetrics:
        """Get current aggregate metrics.

        Time Complexity: O(n) where n is total tasks

        Returns:
            Aggregate metrics for all tasks

        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(success) as successes,
                    AVG(execution_time_ms) as avg_time,
                    AVG(reasoning_quality) as avg_reasoning,
                    SUM(tool_selection_correct) as tool_correct,
                    SUM(hallucination_detected) as hallucinations,
                    MIN(timestamp) as start_time,
                    MAX(timestamp) as end_time
                FROM metrics
            """,
            )

            row = cursor.fetchone()
            if not row or row[0] == 0:
                # No data yet
                return AggregateMetrics(
                    success_rate=0.0,
                    avg_execution_time_ms=0.0,
                    avg_reasoning_quality=0.0,
                    tool_selection_rate=0.0,
                    hallucination_rate=0.0,
                    total_tasks=0,
                    window_start=datetime.now(tz=UTC),
                    window_end=datetime.now(tz=UTC),
                )

            total, successes, avg_time, avg_reasoning, tool_correct, hallucinations, start, end = (
                row
            )

            success_rate = successes / total if total > 0 else 0.0
            tool_selection_rate = tool_correct / total if total > 0 else 0.0
            hallucination_rate = hallucinations / total if total > 0 else 0.0

            return AggregateMetrics(
                success_rate=success_rate,
                avg_execution_time_ms=avg_time or 0.0,
                avg_reasoning_quality=avg_reasoning or 0.0,
                tool_selection_rate=tool_selection_rate,
                hallucination_rate=hallucination_rate,
                total_tasks=total,
                window_start=datetime.fromisoformat(start) if start else datetime.now(tz=UTC),
                window_end=datetime.fromisoformat(end) if end else datetime.now(tz=UTC),
            )

    def get_baseline_metrics(self, baseline_size: int = 10) -> AggregateMetrics | None:
        """Get baseline metrics from first N tasks.

        Time Complexity: O(n) where n is baseline_size

        Args:
            baseline_size: Number of tasks to use for baseline (default: 10)

        Returns:
            Aggregate metrics for baseline tasks, or None if insufficient data

        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(success) as successes,
                    AVG(execution_time_ms) as avg_time,
                    AVG(reasoning_quality) as avg_reasoning,
                    SUM(tool_selection_correct) as tool_correct,
                    SUM(hallucination_detected) as hallucinations,
                    MIN(timestamp) as start_time,
                    MAX(timestamp) as end_time
                FROM (
                    SELECT * FROM metrics
                    ORDER BY task_sequence_number ASC
                    LIMIT ?
                )
            """,
                (baseline_size,),
            )

            row = cursor.fetchone()
            if not row or row[0] < baseline_size:
                return None  # Not enough data for baseline

            total, successes, avg_time, avg_reasoning, tool_correct, hallucinations, start, end = (
                row
            )

            success_rate = successes / total if total > 0 else 0.0
            tool_selection_rate = tool_correct / total if total > 0 else 0.0
            hallucination_rate = hallucinations / total if total > 0 else 0.0

            return AggregateMetrics(
                success_rate=success_rate,
                avg_execution_time_ms=avg_time or 0.0,
                avg_reasoning_quality=avg_reasoning or 0.0,
                tool_selection_rate=tool_selection_rate,
                hallucination_rate=hallucination_rate,
                total_tasks=total,
                window_start=datetime.fromisoformat(start) if start else datetime.now(tz=UTC),
                window_end=datetime.fromisoformat(end) if end else datetime.now(tz=UTC),
            )

    def get_recent_metrics(self, window_size: int = 10) -> AggregateMetrics | None:
        """Get metrics from most recent N tasks.

        Time Complexity: O(n) where n is window_size

        Args:
            window_size: Number of recent tasks to analyze (default: 10)

        Returns:
            Aggregate metrics for recent tasks, or None if insufficient data

        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(success) as successes,
                    AVG(execution_time_ms) as avg_time,
                    AVG(reasoning_quality) as avg_reasoning,
                    SUM(tool_selection_correct) as tool_correct,
                    SUM(hallucination_detected) as hallucinations,
                    MIN(timestamp) as start_time,
                    MAX(timestamp) as end_time
                FROM (
                    SELECT * FROM metrics
                    ORDER BY task_sequence_number DESC
                    LIMIT ?
                )
            """,
                (window_size,),
            )

            row = cursor.fetchone()
            if not row or row[0] < window_size:
                return None  # Not enough data

            total, successes, avg_time, avg_reasoning, tool_correct, hallucinations, start, end = (
                row
            )

            success_rate = successes / total if total > 0 else 0.0
            tool_selection_rate = tool_correct / total if total > 0 else 0.0
            hallucination_rate = hallucinations / total if total > 0 else 0.0

            return AggregateMetrics(
                success_rate=success_rate,
                avg_execution_time_ms=avg_time or 0.0,
                avg_reasoning_quality=avg_reasoning or 0.0,
                tool_selection_rate=tool_selection_rate,
                hallucination_rate=hallucination_rate,
                total_tasks=total,
                window_start=datetime.fromisoformat(start) if start else datetime.now(tz=UTC),
                window_end=datetime.fromisoformat(end) if end else datetime.now(tz=UTC),
            )

    def calculate_improvement(
        self,
        baseline_size: int = 10,
        recent_size: int = 10,
    ) -> dict[str, float] | None:
        """Calculate improvement from baseline to recent performance.

        Time Complexity: O(n) where n is baseline_size + recent_size

        Args:
            baseline_size: Number of tasks for baseline
            recent_size: Number of recent tasks to compare

        Returns:
            Dictionary with improvement metrics, or None if insufficient data:
            - success_rate_improvement: Absolute improvement in success rate
            - execution_time_improvement: Relative improvement in execution time
            - accuracy_improvement: Absolute improvement in accuracy
            - tool_selection_improvement: Absolute improvement in tool selection
            - reasoning_quality_improvement: Absolute improvement in reasoning
            - relative_improvement: Relative improvement in success rate (%)

        """
        baseline = self.get_baseline_metrics(baseline_size)
        recent = self.get_recent_metrics(recent_size)

        if not baseline or not recent:
            return None

        success_rate_improvement = recent.success_rate - baseline.success_rate

        # Execution time improvement (negative means faster)
        execution_time_improvement = (
            (baseline.avg_execution_time_ms - recent.avg_execution_time_ms)
            / baseline.avg_execution_time_ms
            if baseline.avg_execution_time_ms > 0
            else 0.0
        )

        reasoning_quality_improvement = (
            recent.avg_reasoning_quality - baseline.avg_reasoning_quality
        )
        tool_selection_improvement = recent.tool_selection_rate - baseline.tool_selection_rate
        hallucination_improvement = (
            baseline.hallucination_rate - recent.hallucination_rate
        )  # Lower is better

        # Relative improvement in success rate (percentage)
        # Handle edge case where baseline is 0 or very close to 1
        if baseline.success_rate == 0:
            # If baseline is 0%, any improvement is infinite
            relative_improvement = 100.0 if recent.success_rate > 0 else 0.0
        elif baseline.success_rate >= 0.99:  # noqa: PLR2004 - Threshold value

            # If baseline is already near perfect (>=99%), calculate improvement
            # based on error rate reduction instead
            baseline_error_rate = 1.0 - baseline.success_rate
            recent_error_rate = 1.0 - recent.success_rate
            error_reduction = baseline_error_rate - recent_error_rate
            relative_improvement = (
                (error_reduction / baseline_error_rate * 100) if baseline_error_rate > 0 else 0.0
            )
        else:
            # Standard relative improvement calculation
            relative_improvement = success_rate_improvement / baseline.success_rate * 100

        return {
            "success_rate_improvement": round(success_rate_improvement, 4),
            "execution_time_improvement": round(execution_time_improvement, 4),
            "reasoning_quality_improvement": round(reasoning_quality_improvement, 4),
            "tool_selection_improvement": round(tool_selection_improvement, 4),
            "hallucination_improvement": round(hallucination_improvement, 4),
            "relative_improvement": round(relative_improvement, 2),
            "baseline_success_rate": round(baseline.success_rate, 4),
            "recent_success_rate": round(recent.success_rate, 4),
        }

    def get_task_count(self) -> int:
        """Get total number of tasks recorded.

        Time Complexity: O(1)

        Returns:
            Number of tasks

        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM metrics")
            result = cursor.fetchone()
            return int(result[0]) if result else 0

    def calculate_statistical_significance(
        self,
        baseline_size: int = 10,
        recent_size: int = 10,
    ) -> dict[str, Any] | None:
        """Calculate statistical significance of improvement.

        Uses t-test to determine if improvement is statistically significant.

        Time Complexity: O(n) where n is baseline_size + recent_size

        Args:
            baseline_size: Number of tasks for baseline
            recent_size: Number of recent tasks to compare

        Returns:
            Dictionary with statistical test results, or None if insufficient data:
            - t_statistic: T-test statistic
            - p_value: P-value (< 0.05 indicates significance)
            - is_significant: Whether improvement is statistically significant
            - confidence_interval_95: 95% confidence interval for improvement

        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Get baseline success values
            cursor.execute(
                """
                SELECT success FROM metrics
                ORDER BY task_sequence_number ASC
                LIMIT ?
            """,
                (baseline_size,),
            )
            baseline_successes = [row[0] for row in cursor.fetchall()]

            if len(baseline_successes) < baseline_size:
                return None

            # Get recent success values
            cursor.execute(
                """
                SELECT success FROM metrics
                ORDER BY task_sequence_number DESC
                LIMIT ?
            """,
                (recent_size,),
            )
            recent_successes = [row[0] for row in cursor.fetchall()]

            if len(recent_successes) < recent_size:
                return None

        # Perform t-test
        t_statistic, p_value = stats.ttest_ind(recent_successes, baseline_successes)

        # Calculate confidence interval
        baseline_mean = np.mean(baseline_successes)
        recent_mean = np.mean(recent_successes)
        improvement = recent_mean - baseline_mean

        # Standard error of the difference
        baseline_std = np.std(baseline_successes, ddof=1)
        recent_std = np.std(recent_successes, ddof=1)
        se_diff = np.sqrt((baseline_std**2 / baseline_size) + (recent_std**2 / recent_size))

        # 95% confidence interval
        ci_95 = 1.96 * se_diff  # z-score for 95% CI

        return {
            "t_statistic": round(float(t_statistic), 4),
            "p_value": round(float(p_value), 4),
            "is_significant": p_value < 0.05,  # noqa: PLR2004 - Threshold value

            "confidence_interval_95": (
                round(improvement - ci_95, 4),
                round(improvement + ci_95, 4),
            ),
            "improvement": round(improvement, 4),
        }
