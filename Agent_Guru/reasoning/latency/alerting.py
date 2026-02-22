"""
Latency monitoring and alerting system.

Provides real-time monitoring and alerting for latency violations:
- P50/P95/P99 percentile tracking
- Timeout rate monitoring
- Degraded mode frequency tracking
- Automatic alerting on threshold violations
"""

import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional

from Agent_Guru.reasoning.latency.tracker import (
    PipelineStage,
    LATENCY_BUDGETS,
    LatencyStatistics,
    LatencyTracker,
    DegradedModeManager,
)


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Alert type categories."""

    LATENCY_EXCEEDED = "latency_exceeded"
    TIMEOUT_RATE_HIGH = "timeout_rate_high"
    DEGRADED_MODE_HIGH = "degraded_mode_high"
    STAGE_UNAVAILABLE = "stage_unavailable"


@dataclass
class Alert:
    """Alert for latency violations."""

    alert_type: AlertType
    severity: AlertSeverity
    stage: PipelineStage
    message: str
    timestamp: datetime
    metrics: Dict[str, float]


class LatencyMonitor:
    """Monitor for latency metrics and alerting."""

    def __init__(
        self,
        tracker: LatencyTracker,
        degraded_manager: DegradedModeManager,
        alert_callback: Optional[Callable[[Alert], None]] = None,
    ):
        """Initialize latency monitor.

        Args:
            tracker: Latency tracker instance
            degraded_manager: Degraded mode manager instance
            alert_callback: Optional callback for alerts
        """
        self.tracker = tracker
        self.degraded_manager = degraded_manager
        self.alert_callback = alert_callback
        self._alerts: List[Alert] = []
        self._last_check_time = time.time()

    def check_latency_budgets(self) -> List[Alert]:
        """Check all stages against latency budgets.

        Returns:
            List of alerts for violations
        """
        alerts = []

        for stage in PipelineStage:
            stats = self.tracker.get_statistics(stage)
            if not stats:
                continue

            budget = LATENCY_BUDGETS.get(stage, {})
            target = budget.get("target", 0)

            # Check P95 latency against 2x target
            if stats.p95 > target * 2:
                alert = Alert(
                    alert_type=AlertType.LATENCY_EXCEEDED,
                    severity=AlertSeverity.CRITICAL,
                    stage=stage,
                    message=f"P95 latency {stats.p95:.1f}ms exceeds 2x target {target * 2:.1f}ms",
                    timestamp=datetime.now(),
                    metrics={
                        "p95": stats.p95,
                        "target": target,
                        "threshold": target * 2,
                        "exceeded_by": stats.p95 - (target * 2),
                    },
                )
                alerts.append(alert)
                self._fire_alert(alert)

        return alerts

    def check_timeout_rates(self) -> List[Alert]:
        """Check timeout rates for all stages.

        Returns:
            List of alerts for high timeout rates
        """
        alerts = []

        for stage in PipelineStage:
            stats = self.tracker.get_statistics(stage)
            if not stats:
                continue

            # Check timeout rate against 5% threshold
            if stats.timeout_rate > 0.05:
                alert = Alert(
                    alert_type=AlertType.TIMEOUT_RATE_HIGH,
                    severity=AlertSeverity.WARNING,
                    stage=stage,
                    message=f"Timeout rate {stats.timeout_rate * 100:.1f}% exceeds 5% threshold",
                    timestamp=datetime.now(),
                    metrics={
                        "timeout_rate": stats.timeout_rate,
                        "timeout_count": stats.timeout_count,
                        "total_count": stats.count,
                        "threshold": 0.05,
                    },
                )
                alerts.append(alert)
                self._fire_alert(alert)

        return alerts

    def check_degraded_mode_frequency(self) -> List[Alert]:
        """Check degraded mode activation frequency.

        Returns:
            List of alerts for high degraded mode frequency
        """
        alerts = []

        for stage in PipelineStage:
            stats = self.tracker.get_statistics(stage)
            if not stats:
                continue

            # Check degraded rate against 10% threshold
            if stats.degraded_rate > 0.10:
                alert = Alert(
                    alert_type=AlertType.DEGRADED_MODE_HIGH,
                    severity=AlertSeverity.WARNING,
                    stage=stage,
                    message=f"Degraded mode rate {stats.degraded_rate * 100:.1f}% exceeds 10% threshold",
                    timestamp=datetime.now(),
                    metrics={
                        "degraded_rate": stats.degraded_rate,
                        "degraded_count": stats.degraded_count,
                        "total_count": stats.count,
                        "threshold": 0.10,
                    },
                )
                alerts.append(alert)
                self._fire_alert(alert)

        return alerts

    def check_all(self) -> List[Alert]:
        """Run all monitoring checks.

        Returns:
            List of all alerts
        """
        alerts = []
        alerts.extend(self.check_latency_budgets())
        alerts.extend(self.check_timeout_rates())
        alerts.extend(self.check_degraded_mode_frequency())

        self._last_check_time = time.time()
        return alerts

    def get_monitoring_summary(self) -> Dict[str, any]:
        """Get monitoring summary for all stages.

        Returns:
            Summary dictionary
        """
        summary = {
            "timestamp": datetime.now().isoformat(),
            "stages": {},
            "alerts": len(self._alerts),
            "degraded_stages": self.degraded_manager.get_degraded_stages(),
        }

        for stage in PipelineStage:
            stats = self.tracker.get_statistics(stage)
            if not stats:
                continue

            budget = LATENCY_BUDGETS.get(stage, {})
            target = budget.get("target", 0)
            maximum = budget.get("maximum", 0)

            summary["stages"][stage.value] = {
                "latency": {
                    "p50": stats.p50,
                    "p95": stats.p95,
                    "p99": stats.p99,
                    "mean": stats.mean,
                    "target": target,
                    "maximum": maximum,
                    "meets_target": stats.p95 <= target,
                    "meets_maximum": stats.p95 <= maximum,
                },
                "timeout": {
                    "rate": stats.timeout_rate,
                    "count": stats.timeout_count,
                    "threshold_exceeded": stats.timeout_rate > 0.05,
                },
                "degraded": {
                    "rate": stats.degraded_rate,
                    "count": stats.degraded_count,
                    "threshold_exceeded": stats.degraded_rate > 0.10,
                    "is_degraded": self.degraded_manager.is_degraded(stage),
                },
                "total_requests": stats.count,
            }

        return summary

    def _fire_alert(self, alert: Alert) -> None:
        """Fire an alert.

        Args:
            alert: Alert to fire
        """
        self._alerts.append(alert)

        # Keep only last 1000 alerts
        if len(self._alerts) > 1000:
            self._alerts = self._alerts[-1000:]

        # Call alert callback if provided
        if self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception:
                # Don't let alert callback failures break monitoring
                pass

    def get_recent_alerts(self, limit: int = 100) -> List[Alert]:
        """Get recent alerts.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of recent alerts
        """
        return self._alerts[-limit:]

    def clear_alerts(self) -> None:
        """Clear all alerts."""
        self._alerts.clear()


# Global monitor instance
_global_monitor: Optional[LatencyMonitor] = None


def get_latency_monitor(
    tracker: Optional[LatencyTracker] = None,
    degraded_manager: Optional[DegradedModeManager] = None,
    alert_callback: Optional[Callable[[Alert], None]] = None,
) -> LatencyMonitor:
    """Get the global latency monitor instance.

    Args:
        tracker: Optional latency tracker (uses global if not provided)
        degraded_manager: Optional degraded mode manager (uses global if not provided)
        alert_callback: Optional alert callback

    Returns:
        Global LatencyMonitor instance
    """
    global _global_monitor

    if _global_monitor is None:
        from Agent_Guru.reasoning.latency.tracker import (
            get_latency_tracker,
            get_degraded_mode_manager,
        )

        if tracker is None:
            tracker = get_latency_tracker()
        if degraded_manager is None:
            degraded_manager = get_degraded_mode_manager()

        _global_monitor = LatencyMonitor(
            tracker=tracker,
            degraded_manager=degraded_manager,
            alert_callback=alert_callback,
        )

    return _global_monitor
