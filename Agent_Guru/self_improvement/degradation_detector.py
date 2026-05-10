"""Performance Degradation Detector for Self-Improvement Engine.

Detects sudden performance degradation and triggers alerts for rollback.
Implements statistical monitoring to identify when recent performance
significantly degrades compared to historical performance.

**Validates: Requirements 9.4 (Adversarial Robustness)**

Performance Requirements:
- Time Complexity: O(n) where n is window size for degradation check
- Space Complexity: O(1) - no persistent state beyond database
- Detection Latency: <50ms (95th percentile)

Design:
- Uses sliding window comparison (recent vs historical)
- Statistical significance testing (t-test, z-test)
- Multiple metric monitoring (success rate, execution time, reasoning quality)
- Configurable thresholds and sensitivity

Author: Agent Guru Team
Date: 2026-02-28
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import numpy as np
from scipy import stats

if TYPE_CHECKING:
    from Agent_Guru.self_improvement.connection_pool import ConnectionPool


class DegradationSeverity(Enum):
    """Severity levels for performance degradation."""

    NONE = "none"  # No degradation detected
    MINOR = "minor"  # Small degradation, monitor closely
    MODERATE = "moderate"  # Significant degradation, investigate
    SEVERE = "severe"  # Critical degradation, rollback recommended


class DegradationMetric(Enum):
    """Metrics that can degrade."""

    SUCCESS_RATE = "success_rate"
    EXECUTION_TIME = "execution_time"
    REASONING_QUALITY = "reasoning_quality"
    TOOL_SELECTION = "tool_selection"
    HALLUCINATION_RATE = "hallucination_rate"


@dataclass
class DegradationAlert:
    """Alert for detected performance degradation."""

    severity: DegradationSeverity
    degraded_metrics: list[DegradationMetric]
    detection_timestamp: datetime
    recent_window_start: datetime
    recent_window_end: datetime
    historical_window_start: datetime
    historical_window_end: datetime
    metric_changes: dict[str, float]  # Metric name -> change value
    statistical_significance: dict[str, Any]  # Statistical test results
    recommended_action: str
    diagnostic_info: dict[str, Any]


@dataclass
class PerformanceWindow:
    """Performance metrics for a time window."""

    success_rate: float
    avg_execution_time_ms: float
    avg_reasoning_quality: float
    tool_selection_rate: float
    hallucination_rate: float
    total_tasks: int
    window_start: datetime
    window_end: datetime
    success_values: list[int]  # For statistical testing


class DegradationDetector:
    """Detects performance degradation using statistical monitoring.

    Compares recent performance to historical baseline to identify
    sudden drops in performance that may indicate bad updates or
    adversarial conditions.

    Time Complexity: O(n) where n is window size
    Space Complexity: O(1) - no persistent state

    Example:
        >>> detector = DegradationDetector(pool)
        >>> alert = detector.check_for_degradation(
        ...     recent_window_size=20,
        ...     historical_window_size=100
        ... )
        >>> if alert and alert.severity != DegradationSeverity.NONE:
        ...     print(f"Degradation detected: {alert.severity}")
        ...     print(f"Affected metrics: {alert.degraded_metrics}")

    """

    def __init__(
        self,
        pool: "ConnectionPool",
        success_rate_threshold: float = 0.10,  # 10% drop triggers alert
        execution_time_threshold: float = 0.20,  # 20% increase triggers alert
        reasoning_quality_threshold: float = 0.10,  # 10% drop triggers alert
        tool_selection_threshold: float = 0.10,  # 10% drop triggers alert
        hallucination_threshold: float = 0.10,  # 10% increase triggers alert
        significance_level: float = 0.05,  # p-value threshold
    ) -> None:
        """Initialize degradation detector.

        Args:
            pool: ConnectionPool for database access
            success_rate_threshold: Minimum drop in success rate to trigger alert
            execution_time_threshold: Maximum increase in execution time to trigger
            reasoning_quality_threshold: Minimum drop in reasoning quality
            tool_selection_threshold: Minimum drop in tool selection rate
            hallucination_threshold: Maximum increase in hallucination rate
            significance_level: P-value threshold for statistical significance

        Raises:
            ValueError: If thresholds are not in valid ranges

        """
        if not 0.0 < success_rate_threshold < 1.0:
            msg = "success_rate_threshold must be in (0.0, 1.0)"
            raise ValueError(msg)
        if not 0.0 < execution_time_threshold < 1.0:
            msg = "execution_time_threshold must be in (0.0, 1.0)"
            raise ValueError(msg)
        if not 0.0 < reasoning_quality_threshold < 1.0:
            msg = "reasoning_quality_threshold must be in (0.0, 1.0)"
            raise ValueError(msg)
        if not 0.0 < tool_selection_threshold < 1.0:
            msg = "tool_selection_threshold must be in (0.0, 1.0)"
            raise ValueError(msg)
        if not 0.0 < hallucination_threshold < 1.0:
            msg = "hallucination_threshold must be in (0.0, 1.0)"
            raise ValueError(msg)
        if not 0.0 < significance_level < 1.0:
            msg = "significance_level must be in (0.0, 1.0)"
            raise ValueError(msg)

        self.pool = pool
        self.success_rate_threshold = success_rate_threshold
        self.execution_time_threshold = execution_time_threshold
        self.reasoning_quality_threshold = reasoning_quality_threshold
        self.tool_selection_threshold = tool_selection_threshold
        self.hallucination_threshold = hallucination_threshold
        self.significance_level = significance_level

    def check_for_degradation(
        self,
        recent_window_size: int = 20,
        historical_window_size: int = 100,
        min_tasks_required: int = 50,
    ) -> DegradationAlert | None:
        """Check for performance degradation.

        Compares recent performance window to historical baseline.
        Returns alert if significant degradation is detected.

        Time Complexity: O(n) where n is historical_window_size

        Args:
            recent_window_size: Number of recent tasks to analyze
            historical_window_size: Number of historical tasks for baseline
            min_tasks_required: Minimum total tasks before checking

        Returns:
            DegradationAlert if degradation detected, None otherwise

        """
        # Check if we have enough data
        total_tasks = self._get_total_tasks()
        if total_tasks < min_tasks_required:
            return None  # Not enough data yet

        # Get recent and historical windows
        recent = self._get_recent_window(recent_window_size)
        if not recent:
            return None

        # Historical window excludes recent window
        historical = self._get_historical_window(
            historical_window_size,
            exclude_recent=recent_window_size,
        )
        if not historical:
            return None

        # Detect degraded metrics
        degraded_metrics: list[DegradationMetric] = []
        metric_changes: dict[str, float] = {}

        # Check success rate
        success_rate_change = recent.success_rate - historical.success_rate
        if success_rate_change < -self.success_rate_threshold:
            degraded_metrics.append(DegradationMetric.SUCCESS_RATE)
            metric_changes["success_rate"] = success_rate_change

        # Check execution time (increase is bad)
        if historical.avg_execution_time_ms > 0:
            execution_time_change = (
                recent.avg_execution_time_ms - historical.avg_execution_time_ms
            ) / historical.avg_execution_time_ms
            if execution_time_change > self.execution_time_threshold:
                degraded_metrics.append(DegradationMetric.EXECUTION_TIME)
                metric_changes["execution_time_change_pct"] = execution_time_change * 100

        # Check reasoning quality
        reasoning_change = recent.avg_reasoning_quality - historical.avg_reasoning_quality
        if reasoning_change < -self.reasoning_quality_threshold:
            degraded_metrics.append(DegradationMetric.REASONING_QUALITY)
            metric_changes["reasoning_quality"] = reasoning_change

        # Check tool selection rate
        tool_selection_change = recent.tool_selection_rate - historical.tool_selection_rate
        if tool_selection_change < -self.tool_selection_threshold:
            degraded_metrics.append(DegradationMetric.TOOL_SELECTION)
            metric_changes["tool_selection_rate"] = tool_selection_change

        # Check hallucination rate (increase is bad)
        hallucination_change = recent.hallucination_rate - historical.hallucination_rate
        if hallucination_change > self.hallucination_threshold:
            degraded_metrics.append(DegradationMetric.HALLUCINATION_RATE)
            metric_changes["hallucination_rate"] = hallucination_change

        # If no degradation, return None
        if not degraded_metrics:
            return None

        # Perform statistical significance testing
        statistical_significance = self._test_statistical_significance(recent, historical)

        # Determine severity
        severity = self._determine_severity(degraded_metrics, metric_changes)

        # Generate recommended action
        recommended_action = self._generate_recommendation(severity, degraded_metrics)

        # Collect diagnostic info
        diagnostic_info = self._collect_diagnostic_info(recent, historical, degraded_metrics)

        return DegradationAlert(
            severity=severity,
            degraded_metrics=degraded_metrics,
            detection_timestamp=datetime.now(tz=UTC),
            recent_window_start=recent.window_start,
            recent_window_end=recent.window_end,
            historical_window_start=historical.window_start,
            historical_window_end=historical.window_end,
            metric_changes=metric_changes,
            statistical_significance=statistical_significance,
            recommended_action=recommended_action,
            diagnostic_info=diagnostic_info,
        )

    def _get_total_tasks(self) -> int:
        """Get total number of tasks recorded."""
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM metrics")
            result = cursor.fetchone()
            return int(result[0]) if result else 0

    def _get_recent_window(self, window_size: int) -> PerformanceWindow | None:
        """Get performance metrics for recent window."""
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    success,
                    execution_time_ms,
                    reasoning_quality,
                    tool_selection_correct,
                    hallucination_detected,
                    timestamp
                FROM metrics
                ORDER BY task_sequence_number DESC
                LIMIT ?
            """,
                (window_size,),
            )

            rows = cursor.fetchall()
            if len(rows) < window_size:
                return None

            return self._calculate_window_metrics(rows)

    def _get_historical_window(
        self,
        window_size: int,
        exclude_recent: int,
    ) -> PerformanceWindow | None:
        """Get performance metrics for historical window, excluding recent tasks."""
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    success,
                    execution_time_ms,
                    reasoning_quality,
                    tool_selection_correct,
                    hallucination_detected,
                    timestamp
                FROM (
                    SELECT * FROM metrics
                    ORDER BY task_sequence_number DESC
                    LIMIT ? OFFSET ?
                )
            """,
                (window_size, exclude_recent),
            )

            rows = cursor.fetchall()
            if len(rows) < window_size:
                return None

            return self._calculate_window_metrics(rows)

    def _calculate_window_metrics(self, rows: list[tuple]) -> PerformanceWindow:
        """Calculate aggregate metrics from raw data rows."""
        success_values = [row[0] for row in rows]
        execution_times = [row[1] for row in rows]
        reasoning_qualities = [row[2] for row in rows]
        tool_selections = [row[3] for row in rows]
        hallucinations = [row[4] for row in rows]
        timestamps = [datetime.fromisoformat(row[5]) for row in rows]

        total = len(rows)
        success_rate = sum(success_values) / total if total > 0 else 0.0
        avg_execution_time = sum(execution_times) / total if total > 0 else 0.0
        avg_reasoning_quality = sum(reasoning_qualities) / total if total > 0 else 0.0
        tool_selection_rate = sum(tool_selections) / total if total > 0 else 0.0
        hallucination_rate = sum(hallucinations) / total if total > 0 else 0.0

        return PerformanceWindow(
            success_rate=success_rate,
            avg_execution_time_ms=avg_execution_time,
            avg_reasoning_quality=avg_reasoning_quality,
            tool_selection_rate=tool_selection_rate,
            hallucination_rate=hallucination_rate,
            total_tasks=total,
            window_start=min(timestamps),
            window_end=max(timestamps),
            success_values=success_values,
        )

    def _test_statistical_significance(
        self,
        recent: PerformanceWindow,
        historical: PerformanceWindow,
    ) -> dict[str, Any]:
        """Test statistical significance of performance difference.

        Uses t-test to determine if degradation is statistically significant.
        """
        # T-test on success rates
        t_statistic, p_value = stats.ttest_ind(recent.success_values, historical.success_values)

        # Calculate effect size (Cohen's d)
        recent_mean = np.mean(recent.success_values)
        historical_mean = np.mean(historical.success_values)
        pooled_std = np.sqrt(
            (
                np.var(recent.success_values, ddof=1) * (recent.total_tasks - 1)
                + np.var(historical.success_values, ddof=1) * (historical.total_tasks - 1)
            )
            / (recent.total_tasks + historical.total_tasks - 2),
        )

        cohens_d = (recent_mean - historical_mean) / pooled_std if pooled_std > 0 else 0.0

        return {
            "t_statistic": round(float(t_statistic), 4),
            "p_value": round(float(p_value), 4),
            "is_significant": p_value < self.significance_level,
            "cohens_d": round(float(cohens_d), 4),
            "effect_size": self._interpret_effect_size(cohens_d),
        }

    def _interpret_effect_size(self, cohens_d: float) -> str:
        """Interpret Cohen's d effect size."""
        abs_d = abs(cohens_d)
        if abs_d < 0.2:  # noqa: PLR2004 - Threshold value

            return "negligible"
        if abs_d < 0.5:  # noqa: PLR2004 - Threshold value

            return "small"
        if abs_d < 0.8:  # noqa: PLR2004 - Threshold value

            return "medium"
        return "large"

    def _determine_severity(
        self,
        degraded_metrics: list[DegradationMetric],
        metric_changes: dict[str, float],
    ) -> DegradationSeverity:
        """Determine severity of degradation.

        Severity based on:
        - Number of degraded metrics
        - Magnitude of changes
        - Critical metrics (success rate, reasoning quality)
        """
        num_degraded = len(degraded_metrics)

        # Check for critical metric degradation
        critical_degradation = (
            DegradationMetric.SUCCESS_RATE in degraded_metrics
            or DegradationMetric.REASONING_QUALITY in degraded_metrics
        )

        # Check magnitude of changes
        max_change = max(abs(v) for v in metric_changes.values()) if metric_changes else 0.0

        # Determine severity
        if critical_degradation and max_change > 0.25:  # >25% change in critical metric  # noqa: PLR2004 (Threshold value)

            return DegradationSeverity.SEVERE
        if num_degraded >= 3 or (critical_degradation and max_change > 0.15):  # noqa: PLR2004 - Small integer threshold

            return DegradationSeverity.MODERATE
        if num_degraded >= 2 or max_change > 0.10:  # noqa: PLR2004 - Small integer threshold

            return DegradationSeverity.MINOR
        return DegradationSeverity.NONE

    def _generate_recommendation(
        self,
        severity: DegradationSeverity,
        degraded_metrics: list[DegradationMetric],
    ) -> str:
        """Generate recommended action based on severity."""
        if severity == DegradationSeverity.SEVERE:
            return (
                "CRITICAL: Immediate rollback recommended. "
                "Performance has severely degraded. "
                "Investigate recent changes and revert to last known good state."
            )
        if severity == DegradationSeverity.MODERATE:
            return (
                "WARNING: Significant degradation detected. "
                "Review recent strategy updates and prompt changes. "
                "Consider rollback if degradation continues."
            )
        if severity == DegradationSeverity.MINOR:
            return (
                "NOTICE: Minor degradation detected. "
                "Monitor closely for continued degradation. "
                "Review recent changes for potential issues."
            )
        return "No action required."

    def _collect_diagnostic_info(
        self,
        recent: PerformanceWindow,
        historical: PerformanceWindow,
        degraded_metrics: list[DegradationMetric],
    ) -> dict[str, Any]:
        """Collect diagnostic information for investigation."""
        return {
            "recent_performance": {
                "success_rate": round(recent.success_rate, 4),
                "avg_execution_time_ms": round(recent.avg_execution_time_ms, 2),
                "avg_reasoning_quality": round(recent.avg_reasoning_quality, 4),
                "tool_selection_rate": round(recent.tool_selection_rate, 4),
                "hallucination_rate": round(recent.hallucination_rate, 4),
                "total_tasks": recent.total_tasks,
            },
            "historical_performance": {
                "success_rate": round(historical.success_rate, 4),
                "avg_execution_time_ms": round(historical.avg_execution_time_ms, 2),
                "avg_reasoning_quality": round(historical.avg_reasoning_quality, 4),
                "tool_selection_rate": round(historical.tool_selection_rate, 4),
                "hallucination_rate": round(historical.hallucination_rate, 4),
                "total_tasks": historical.total_tasks,
            },
            "degraded_metrics_list": [m.value for m in degraded_metrics],
            "time_range": {
                "recent_start": recent.window_start.isoformat(),
                "recent_end": recent.window_end.isoformat(),
                "historical_start": historical.window_start.isoformat(),
                "historical_end": historical.window_end.isoformat(),
            },
        }

    def get_recent_degradation_history(self, days: int = 7) -> list[dict[str, Any]]:
        """Get history of degradation checks for recent period.

        This would require a degradation_alerts table to store historical alerts.
        For now, returns empty list as this is a stateless detector.

        Args:
            days: Number of days to look back

        Returns:
            List of historical degradation alerts

        """
        # TODO: Implement degradation alert storage and retrieval
        # This would require adding a degradation_alerts table
        return []
