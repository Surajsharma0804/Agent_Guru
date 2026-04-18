"""
Improvement Reporter for Self-Improvement Engine.

Generates comprehensive improvement reports after every 100 tasks with
statistical analysis, confidence intervals, and threshold checking.

**Validates: Requirements 7.1-7.7**

Performance Requirements:
- Time Complexity: O(n) where n is measurement window size
- Space Complexity: O(1) for report generation
- Report Generation Latency: <100ms

Author: Agent Guru Team
Date: 2026-02-28
"""

import logging
_logger = logging.getLogger(__name__)

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from Agent_Guru.self_improvement.performance_tracker import PerformanceTracker


@dataclass
class ImprovementReport:
    """Comprehensive improvement report."""

    # Metadata
    report_id: str
    timestamp: datetime
    total_tasks: int
    measurement_window: int

    # Performance Metrics
    baseline_success_rate: float
    recent_success_rate: float
    success_rate_improvement: float
    relative_improvement_percent: float

    baseline_execution_time_ms: float
    recent_execution_time_ms: float
    execution_time_improvement: float

    baseline_reasoning_quality: float
    recent_reasoning_quality: float
    reasoning_quality_improvement: float

    baseline_tool_selection_rate: float
    recent_tool_selection_rate: float
    tool_selection_improvement: float

    baseline_hallucination_rate: float
    recent_hallucination_rate: float
    hallucination_improvement: float

    # Statistical Analysis
    is_statistically_significant: bool
    p_value: float
    confidence_interval_95: tuple[float, float]
    t_statistic: float

    # Threshold Checking
    meets_improvement_threshold: bool
    improvement_threshold: float
    threshold_gap: float

    # Alert Status
    requires_alert: bool
    alert_reason: Optional[str]


class ImprovementReporter:
    """
    Generates improvement reports after every 100 tasks.

    Provides statistical analysis, confidence intervals, and threshold checking
    to verify the 15% improvement guarantee.

    Time Complexity: O(n) where n is measurement window
    Space Complexity: O(1) for report generation

    Example:
        >>> reporter = ImprovementReporter(tracker, improvement_threshold=0.15)
        >>> report = reporter.generate_report(measurement_window=100)
        >>> print(f"Improvement: {report.relative_improvement_percent}%")
    """

    def __init__(
        self,
        performance_tracker: "PerformanceTracker",
        improvement_threshold: float = 0.15,
    ) -> None:
        """
        Initialize improvement reporter.

        Args:
            performance_tracker: PerformanceTracker instance
            improvement_threshold: Minimum relative improvement required (default: 15%)

        Raises:
            ValueError: If improvement_threshold not in [0.0, 1.0]
        """
        if not 0.0 <= improvement_threshold <= 1.0:
            raise ValueError(
                f"Improvement threshold must be in [0.0, 1.0], got {improvement_threshold}"
            )

        self.tracker = performance_tracker
        self.improvement_threshold = improvement_threshold

    def generate_report(
        self, measurement_window: int = 100, baseline_size: int = 10, recent_size: int = 10
    ) -> Optional[ImprovementReport]:
        """
        Generate comprehensive improvement report.

        Time Complexity: O(n) where n is measurement_window

        Args:
            measurement_window: Total tasks for measurement (default: 100)
            baseline_size: Number of tasks for baseline (default: 10)
            recent_size: Number of recent tasks to compare (default: 10)

        Returns:
            ImprovementReport if sufficient data, None otherwise
        """
        # Check if we have enough data
        total_tasks = self.tracker.get_task_count()
        if total_tasks < measurement_window:
            return None

        # Get baseline and recent metrics
        baseline = self.tracker.get_baseline_metrics(baseline_size)
        recent = self.tracker.get_recent_metrics(recent_size)

        if not baseline or not recent:
            return None

        # Calculate improvement metrics
        improvement = self.tracker.calculate_improvement(baseline_size, recent_size)
        if not improvement:
            return None

        # Calculate statistical significance
        significance = self.tracker.calculate_statistical_significance(
            baseline_size, recent_size
        )
        if not significance:
            return None

        # Calculate threshold checking
        # relative_improvement from tracker is already in percentage (e.g., 20.0 for 20%)
        # Convert to decimal for comparison (e.g., 20.0 -> 0.20)
        relative_improvement_decimal = improvement["relative_improvement"] / 100.0
        meets_threshold = relative_improvement_decimal >= self.improvement_threshold
        threshold_gap = relative_improvement_decimal - self.improvement_threshold

        # Determine alert status
        requires_alert = not meets_threshold
        alert_reason = None
        if requires_alert:
            alert_reason = (
                f"Improvement {relative_improvement_decimal:.1%} below threshold "
                f"{self.improvement_threshold:.1%} (gap: {threshold_gap:.1%})"
            )

        # Create report
        report = ImprovementReport(
            # Metadata
            report_id=f"report_{datetime.now(tz=timezone.utc).timestamp()}",
            timestamp=datetime.now(tz=timezone.utc),
            total_tasks=total_tasks,
            measurement_window=measurement_window,
            # Performance Metrics
            baseline_success_rate=baseline.success_rate,
            recent_success_rate=recent.success_rate,
            success_rate_improvement=improvement["success_rate_improvement"],
            relative_improvement_percent=improvement["relative_improvement"],
            baseline_execution_time_ms=baseline.avg_execution_time_ms,
            recent_execution_time_ms=recent.avg_execution_time_ms,
            execution_time_improvement=improvement["execution_time_improvement"],
            baseline_reasoning_quality=baseline.avg_reasoning_quality,
            recent_reasoning_quality=recent.avg_reasoning_quality,
            reasoning_quality_improvement=improvement["reasoning_quality_improvement"],
            baseline_tool_selection_rate=baseline.tool_selection_rate,
            recent_tool_selection_rate=recent.tool_selection_rate,
            tool_selection_improvement=improvement["tool_selection_improvement"],
            baseline_hallucination_rate=baseline.hallucination_rate,
            recent_hallucination_rate=recent.hallucination_rate,
            hallucination_improvement=improvement["hallucination_improvement"],
            # Statistical Analysis
            is_statistically_significant=significance["is_significant"],
            p_value=significance["p_value"],
            confidence_interval_95=significance["confidence_interval_95"],
            t_statistic=significance["t_statistic"],
            # Threshold Checking
            meets_improvement_threshold=meets_threshold,
            improvement_threshold=self.improvement_threshold,
            threshold_gap=threshold_gap,
            # Alert Status
            requires_alert=requires_alert,
            alert_reason=alert_reason,
        )

        return report

    def format_report(self, report: ImprovementReport) -> str:
        """
        Format improvement report as human-readable text.

        Args:
            report: ImprovementReport to format

        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 80)
        lines.append("SELF-IMPROVEMENT ENGINE - IMPROVEMENT REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Metadata
        lines.append(f"Report ID: {report.report_id}")
        lines.append(f"Timestamp: {report.timestamp.isoformat()}")
        lines.append(f"Total Tasks: {report.total_tasks}")
        lines.append(f"Measurement Window: {report.measurement_window}")
        lines.append("")

        # Summary
        status_icon = "✅" if report.meets_improvement_threshold else "⚠️"
        lines.append(f"OVERALL STATUS: {status_icon}")
        lines.append(
            f"Relative Improvement: {report.relative_improvement_percent:+.2f}% "
            f"(Threshold: {report.improvement_threshold * 100:.0f}%)"
        )
        lines.append("")

        # Performance Metrics
        lines.append("PERFORMANCE METRICS")
        lines.append("-" * 80)
        lines.append("")

        lines.append("Success Rate:")
        lines.append(f"  Baseline: {report.baseline_success_rate:.2%}")
        lines.append(f"  Recent:   {report.recent_success_rate:.2%}")
        lines.append(f"  Change:   {report.success_rate_improvement:+.2%}")
        lines.append("")

        lines.append("Execution Time:")
        lines.append(f"  Baseline: {report.baseline_execution_time_ms:.2f}ms")
        lines.append(f"  Recent:   {report.recent_execution_time_ms:.2f}ms")
        lines.append(f"  Change:   {report.execution_time_improvement:+.2%}")
        lines.append("")

        lines.append("Reasoning Quality:")
        lines.append(f"  Baseline: {report.baseline_reasoning_quality:.2f}")
        lines.append(f"  Recent:   {report.recent_reasoning_quality:.2f}")
        lines.append(f"  Change:   {report.reasoning_quality_improvement:+.2f}")
        lines.append("")

        lines.append("Tool Selection Rate:")
        lines.append(f"  Baseline: {report.baseline_tool_selection_rate:.2%}")
        lines.append(f"  Recent:   {report.recent_tool_selection_rate:.2%}")
        lines.append(f"  Change:   {report.tool_selection_improvement:+.2%}")
        lines.append("")

        lines.append("Hallucination Rate:")
        lines.append(f"  Baseline: {report.baseline_hallucination_rate:.2%}")
        lines.append(f"  Recent:   {report.recent_hallucination_rate:.2%}")
        lines.append(f"  Change:   {report.hallucination_improvement:+.2%} (lower is better)")
        lines.append("")

        # Statistical Analysis
        lines.append("STATISTICAL ANALYSIS")
        lines.append("-" * 80)
        lines.append("")

        sig_status = "YES" if report.is_statistically_significant else "NO"
        lines.append(f"Statistically Significant: {sig_status}")
        lines.append(f"P-value: {report.p_value:.4f} (threshold: 0.05)")
        lines.append(f"T-statistic: {report.t_statistic:.4f}")
        lines.append(
            f"95% Confidence Interval: "
            f"[{report.confidence_interval_95[0]:+.4f}, {report.confidence_interval_95[1]:+.4f}]"
        )
        lines.append("")

        # Alert Status
        if report.requires_alert:
            lines.append("ALERT")
            lines.append("-" * 80)
            lines.append("")
            lines.append(f"⚠️  {report.alert_reason}")
            lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)

    def format_report_for_commit(self, report: ImprovementReport) -> str:
        """
        Format improvement report for Git commit message.

        Args:
            report: ImprovementReport to format

        Returns:
            Formatted commit message
        """
        status_icon = "✅" if report.meets_improvement_threshold else "⚠️"
        threshold_pct = report.improvement_threshold * 100

        message = (
            f"📈 Improvement Report: {report.relative_improvement_percent:+.1f}% "
            f"after {report.measurement_window} tasks "
            f"(Target: +{threshold_pct:.0f}% {status_icon})"
        )

        return message

    def check_improvement_threshold(self, report: ImprovementReport) -> bool:
        """
        Check if improvement meets threshold.

        Args:
            report: ImprovementReport to check

        Returns:
            True if threshold met, False otherwise
        """
        return report.meets_improvement_threshold

    def trigger_alert(self, report: ImprovementReport) -> None:
        """
        Trigger alert if improvement targets not met.

        Args:
            report: ImprovementReport with alert status
        """
        if not report.requires_alert:
            return

        # Log alert
        _logger.info("=" * 80)
        _logger.info("⚠️  IMPROVEMENT ALERT")
        _logger.info("=" * 80)
        _logger.info("Reason: %s", report.alert_reason)
        _logger.info("")
        _logger.info("Current Improvement: %+.2f%%", report.relative_improvement_percent)
        _logger.info("Required Threshold: %.0f%%", report.improvement_threshold * 100)
        _logger.info("Gap: %+.2f%%", report.threshold_gap * 100)
        _logger.info("")
        _logger.info("Recommendations:")
        _logger.info("1. Review failure patterns in Failure Analyzer")
        _logger.info("2. Check strategy performance in Strategy Optimizer")
        _logger.info("3. Verify prompt evolution is working correctly")
        _logger.info("4. Analyze recent task types for difficulty changes")
        _logger.info("=" * 80)
