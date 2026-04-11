"""
Latency optimization dashboard.

Provides visualization and analysis of latency metrics:
- P50/P95/P99 latency per stage
- Latency trends over time
- Timeout rate per component
- Degraded mode activation frequency
- Budget comparison
"""

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from Agent_Guru.reasoning.latency.tracker import (
    LATENCY_BUDGETS,
    DegradedModeManager,
    LatencyTracker,
    PipelineStage,
)


@dataclass
class LatencySnapshot:
    """Snapshot of latency metrics at a point in time."""

    timestamp: datetime
    stage: PipelineStage
    p50: float
    p95: float
    p99: float
    mean: float
    timeout_rate: float
    degraded_rate: float
    count: int


class LatencyDashboard:
    """Dashboard for latency visualization and analysis."""

    def __init__(
        self,
        tracker: LatencyTracker,
        degraded_manager: DegradedModeManager,
        history_duration: int = 3600,  # 1 hour
        snapshot_interval: int = 60,  # 1 minute
    ):
        """Initialize latency dashboard.

        Args:
            tracker: Latency tracker instance
            degraded_manager: Degraded mode manager instance
            history_duration: Duration to keep history in seconds
            snapshot_interval: Interval between snapshots in seconds
        """
        self.tracker = tracker
        self.degraded_manager = degraded_manager
        self.history_duration = history_duration
        self.snapshot_interval = snapshot_interval

        # History storage
        self._snapshots: dict[PipelineStage, deque[LatencySnapshot]] = defaultdict(
            lambda: deque(maxlen=history_duration // snapshot_interval)
        )
        self._last_snapshot_time = time.time()

    def capture_snapshot(self) -> None:
        """Capture current latency metrics snapshot."""
        now = datetime.now(tz=timezone.utc)

        for stage in PipelineStage:
            stats = self.tracker.get_statistics(stage)
            if not stats:
                continue

            snapshot = LatencySnapshot(
                timestamp=now,
                stage=stage,
                p50=stats.p50,
                p95=stats.p95,
                p99=stats.p99,
                mean=stats.mean,
                timeout_rate=stats.timeout_rate,
                degraded_rate=stats.degraded_rate,
                count=stats.count,
            )

            self._snapshots[stage].append(snapshot)

        self._last_snapshot_time = time.time()

    def get_latency_trends(
        self, stage: PipelineStage, duration_minutes: int = 60
    ) -> dict[str, list[tuple[datetime, float]]]:
        """Get latency trends for a stage.

        Args:
            stage: Pipeline stage
            duration_minutes: Duration to analyze in minutes

        Returns:
            Dictionary of metric trends
        """
        cutoff_time = datetime.now(tz=timezone.utc) - timedelta(minutes=duration_minutes)
        snapshots = [
            s for s in self._snapshots[stage] if s.timestamp >= cutoff_time
        ]

        if not snapshots:
            return {
                "p50": [],
                "p95": [],
                "p99": [],
                "mean": [],
            }

        return {
            "p50": [(s.timestamp, s.p50) for s in snapshots],
            "p95": [(s.timestamp, s.p95) for s in snapshots],
            "p99": [(s.timestamp, s.p99) for s in snapshots],
            "mean": [(s.timestamp, s.mean) for s in snapshots],
        }

    def get_timeout_trends(
        self, stage: PipelineStage, duration_minutes: int = 60
    ) -> list[tuple[datetime, float]]:
        """Get timeout rate trends for a stage.

        Args:
            stage: Pipeline stage
            duration_minutes: Duration to analyze in minutes

        Returns:
            List of (timestamp, timeout_rate) tuples
        """
        cutoff_time = datetime.now(tz=timezone.utc) - timedelta(minutes=duration_minutes)
        snapshots = [
            s for s in self._snapshots[stage] if s.timestamp >= cutoff_time
        ]

        return [(s.timestamp, s.timeout_rate) for s in snapshots]

    def get_degraded_trends(
        self, stage: PipelineStage, duration_minutes: int = 60
    ) -> list[tuple[datetime, float]]:
        """Get degraded mode rate trends for a stage.

        Args:
            stage: Pipeline stage
            duration_minutes: Duration to analyze in minutes

        Returns:
            List of (timestamp, degraded_rate) tuples
        """
        cutoff_time = datetime.now(tz=timezone.utc) - timedelta(minutes=duration_minutes)
        snapshots = [
            s for s in self._snapshots[stage] if s.timestamp >= cutoff_time
        ]

        return [(s.timestamp, s.degraded_rate) for s in snapshots]

    def get_budget_comparison(self) -> dict[str, dict[str, Any]]:
        """Get comparison of current latency vs budget targets.

        Returns:
            Dictionary of budget comparisons per stage
        """
        comparison = {}

        for stage in PipelineStage:
            stats = self.tracker.get_statistics(stage)
            if not stats:
                continue

            budget = LATENCY_BUDGETS.get(stage, {})
            target = budget.get("target", 0)
            maximum = budget.get("maximum", 0)

            comparison[stage.value] = {
                "current": {
                    "p50": stats.p50,
                    "p95": stats.p95,
                    "p99": stats.p99,
                    "mean": stats.mean,
                },
                "budget": {
                    "target": target,
                    "maximum": maximum,
                },
                "status": {
                    "meets_target": stats.p95 <= target,
                    "meets_maximum": stats.p95 <= maximum,
                    "target_margin": target - stats.p95,
                    "maximum_margin": maximum - stats.p95,
                },
                "performance": {
                    "vs_target_percent": (stats.p95 / target * 100) if target > 0 else 0,
                    "vs_maximum_percent": (stats.p95 / maximum * 100) if maximum > 0 else 0,
                },
            }

        return comparison

    def get_stage_summary(self, stage: PipelineStage) -> dict[str, Any]:
        """Get comprehensive summary for a stage.

        Args:
            stage: Pipeline stage

        Returns:
            Summary dictionary
        """
        stats = self.tracker.get_statistics(stage)
        if not stats:
            return {}

        budget = LATENCY_BUDGETS.get(stage, {})
        target = budget.get("target", 0)
        maximum = budget.get("maximum", 0)

        # Get recent trends
        latency_trends = self.get_latency_trends(stage, duration_minutes=60)
        timeout_trends = self.get_timeout_trends(stage, duration_minutes=60)
        degraded_trends = self.get_degraded_trends(stage, duration_minutes=60)

        return {
            "stage": stage.value,
            "current_metrics": {
                "latency": {
                    "p50": stats.p50,
                    "p95": stats.p95,
                    "p99": stats.p99,
                    "mean": stats.mean,
                    "min": stats.min,
                    "max": stats.max,
                },
                "timeout": {
                    "rate": stats.timeout_rate,
                    "count": stats.timeout_count,
                },
                "degraded": {
                    "rate": stats.degraded_rate,
                    "count": stats.degraded_count,
                    "is_active": self.degraded_manager.is_degraded(stage),
                },
                "total_requests": stats.count,
            },
            "budget": {
                "target": target,
                "maximum": maximum,
                "meets_target": stats.p95 <= target,
                "meets_maximum": stats.p95 <= maximum,
            },
            "trends": {
                "latency": latency_trends,
                "timeout": timeout_trends,
                "degraded": degraded_trends,
            },
        }

    def get_overall_summary(self) -> dict[str, Any]:
        """Get overall system latency summary.

        Returns:
            Overall summary dictionary
        """
        all_stats = self.tracker.get_all_statistics()

        total_requests = sum(s.count for s in all_stats.values())
        total_timeouts = sum(s.timeout_count for s in all_stats.values())
        total_degraded = sum(s.degraded_count for s in all_stats.values())

        # Calculate average latency across all stages
        avg_p50 = sum(s.p50 for s in all_stats.values()) / len(all_stats) if all_stats else 0
        avg_p95 = sum(s.p95 for s in all_stats.values()) / len(all_stats) if all_stats else 0
        avg_p99 = sum(s.p99 for s in all_stats.values()) / len(all_stats) if all_stats else 0

        # Count stages meeting targets
        stages_meeting_target = 0
        stages_meeting_maximum = 0

        for stage, stats in all_stats.items():
            budget = LATENCY_BUDGETS.get(stage, {})
            target = budget.get("target", 0)
            maximum = budget.get("maximum", 0)

            if stats.p95 <= target:
                stages_meeting_target += 1
            if stats.p95 <= maximum:
                stages_meeting_maximum += 1

        return {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "overall_metrics": {
                "total_requests": total_requests,
                "total_timeouts": total_timeouts,
                "total_degraded": total_degraded,
                "timeout_rate": total_timeouts / total_requests if total_requests > 0 else 0,
                "degraded_rate": total_degraded / total_requests if total_requests > 0 else 0,
            },
            "average_latency": {
                "p50": avg_p50,
                "p95": avg_p95,
                "p99": avg_p99,
            },
            "budget_compliance": {
                "stages_meeting_target": stages_meeting_target,
                "stages_meeting_maximum": stages_meeting_maximum,
                "total_stages": len(all_stats),
                "target_compliance_rate": stages_meeting_target / len(all_stats) if all_stats else 0,
                "maximum_compliance_rate": stages_meeting_maximum / len(all_stats) if all_stats else 0,
            },
            "degraded_stages": [
                stage.value for stage in self.degraded_manager.get_degraded_stages()
            ],
        }

    def generate_text_report(self) -> str:
        """Generate human-readable text report.

        Returns:
            Text report
        """
        summary = self.get_overall_summary()
        budget_comparison = self.get_budget_comparison()

        # Type assertions for mypy
        overall_metrics = summary.get('overall_metrics', {})
        average_latency = summary.get('average_latency', {})
        budget_compliance = summary.get('budget_compliance', {})
        degraded_stages = summary.get('degraded_stages', [])

        lines = [
            "=" * 80,
            "LATENCY OPTIMIZATION DASHBOARD",
            "=" * 80,
            "",
            f"Timestamp: {summary.get('timestamp', '')}",
            "",
            "OVERALL METRICS:",
            f"  Total Requests: {overall_metrics.get('total_requests', 0)}",
            f"  Timeout Rate: {overall_metrics.get('timeout_rate', 0) * 100:.2f}%",
            f"  Degraded Rate: {overall_metrics.get('degraded_rate', 0) * 100:.2f}%",
            "",
            "AVERAGE LATENCY:",
            f"  P50: {average_latency.get('p50', 0):.1f}ms",
            f"  P95: {average_latency.get('p95', 0):.1f}ms",
            f"  P99: {average_latency.get('p99', 0):.1f}ms",
            "",
            "BUDGET COMPLIANCE:",
            f"  Stages Meeting Target: {budget_compliance.get('stages_meeting_target', 0)}/{budget_compliance.get('total_stages', 0)}",
            f"  Stages Meeting Maximum: {budget_compliance.get('stages_meeting_maximum', 0)}/{budget_compliance.get('total_stages', 0)}",
            f"  Target Compliance Rate: {budget_compliance.get('target_compliance_rate', 0) * 100:.1f}%",
            "",
        ]

        if degraded_stages:
            lines.append("DEGRADED STAGES:")
            for stage in degraded_stages:
                lines.append(f"  - {stage}")
            lines.append("")

        lines.append("PER-STAGE METRICS:")
        lines.append("")

        for stage_name, comparison in budget_comparison.items():
            comp_status = comparison.get('status', {})
            comp_current = comparison.get('current', {})
            comp_budget = comparison.get('budget', {})
            comp_performance = comparison.get('performance', {})

            status_icon = "✓" if comp_status.get('meets_target', False) else "✗"
            lines.extend([
                f"{status_icon} {stage_name.upper()}:",
                f"  Current P95: {comp_current.get('p95', 0):.1f}ms",
                f"  Target: {comp_budget.get('target', 0):.1f}ms",
                f"  Maximum: {comp_budget.get('maximum', 0):.1f}ms",
                f"  Performance: {comp_performance.get('vs_target_percent', 0):.1f}% of target",
                "",
            ])

        lines.append("=" * 80)

        return "\n".join(lines)


# Global dashboard instance
_global_dashboard: Optional[LatencyDashboard] = None


def get_latency_dashboard(
    tracker: Optional[LatencyTracker] = None,
    degraded_manager: Optional[DegradedModeManager] = None,
) -> LatencyDashboard:
    """Get the global latency dashboard instance.

    Args:
        tracker: Optional latency tracker (uses global if not provided)
        degraded_manager: Optional degraded mode manager (uses global if not provided)

    Returns:
        Global LatencyDashboard instance
    """
    global _global_dashboard

    if _global_dashboard is None:
        from Agent_Guru.reasoning.latency.tracker import (
            get_degraded_mode_manager,
            get_latency_tracker,
        )

        if tracker is None:
            tracker = get_latency_tracker()
        if degraded_manager is None:
            degraded_manager = get_degraded_mode_manager()

        _global_dashboard = LatencyDashboard(
            tracker=tracker,
            degraded_manager=degraded_manager,
        )

    return _global_dashboard
