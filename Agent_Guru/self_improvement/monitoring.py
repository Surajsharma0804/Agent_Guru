"""Monitoring and alerting for self-improvement engine.

Tracks improvement metrics and triggers alerts when thresholds are not met.
"""

import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class AlertLevel(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Alert notification."""

    level: AlertLevel
    title: str
    message: str
    details: dict[str, Any]
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class ImprovementMonitor:
    """Monitors improvement metrics and triggers alerts.

    Tracks learning progress and alerts when improvement targets are not met.
    """

    def __init__(
        self,
        storage_path: str,
        config: Any | None = None,
        alert_callback: Callable[[Alert], None] | None = None,
    ) -> None:
        """Initialize improvement monitor.

        Args:
            storage_path: Path to SQLite database
            config: Optional deployment configuration
            alert_callback: Optional callback function for alerts

        """
        self.storage_path = storage_path
        self.config = config
        self.alert_callback = alert_callback or self._default_alert_handler
        self.logger = logging.getLogger(__name__)

    def check_improvement(self) -> Alert | None:
        """Check if improvement targets are being met.

        Returns:
            Alert if improvement is insufficient, None otherwise

        """
        try:
            with sqlite3.connect(self.storage_path) as conn:
                cursor = conn.cursor()

                # Get latest improvement report
                cursor.execute("""
                    SELECT
                        relative_improvement,
                        baseline_success_rate,
                        final_success_rate,
                        task_count,
                        timestamp
                    FROM improvement_reports
                    ORDER BY timestamp DESC
                    LIMIT 1
                """)

                result = cursor.fetchone()

            if not result:
                return None  # No reports yet

            improvement, baseline, final, task_count, timestamp = result
            threshold = self.config.improvement_threshold if self.config else 0.15

            if improvement < threshold:
                alert = Alert(
                    level=AlertLevel.WARNING,
                    title="Insufficient Improvement",
                    message=f"Improvement ({improvement:.1%}) below threshold ({threshold:.1%})",
                    details={
                        "improvement": improvement,
                        "threshold": threshold,
                        "baseline_success_rate": baseline,
                        "final_success_rate": final,
                        "task_count": task_count,
                        "report_timestamp": timestamp,
                    },
                    timestamp=datetime.now(tz=UTC),
                )

                self.alert_callback(alert)
                return alert

            return None

        except Exception:
            self.logger.exception("Error checking improvement")
            return None

    def check_performance_degradation(self) -> Alert | None:
        """Check for performance degradation.

        Returns:
            Alert if degradation detected, None otherwise

        """
        try:
            with sqlite3.connect(self.storage_path) as conn:
                cursor = conn.cursor()

                # Get success rate for last 10 tasks vs previous 10 tasks
                cursor.execute("""
                    WITH recent AS (
                        SELECT AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as rate
                        FROM (
                            SELECT success FROM task_executions
                            ORDER BY timestamp DESC
                            LIMIT 10
                        )
                    ),
                    previous AS (
                        SELECT AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as rate
                        FROM (
                            SELECT success FROM task_executions
                            ORDER BY timestamp DESC
                            LIMIT 20
                            OFFSET 10
                        )
                    )
                    SELECT recent.rate, previous.rate
                    FROM recent, previous
                """)

                result = cursor.fetchone()

            if not result or result[0] is None or result[1] is None:
                return None  # Insufficient data

            recent_rate, previous_rate = result

            if previous_rate == 0:
                return None  # Avoid division by zero

            degradation = (previous_rate - recent_rate) / previous_rate
            max_degradation = self.config.max_degradation_percent / 100 if self.config else 0.20

            if degradation > max_degradation:
                alert = Alert(
                    level=AlertLevel.ERROR,
                    title="Performance Degradation Detected",
                    message=f"Performance degraded by {degradation:.1%} (threshold: {max_degradation:.1%})",
                    details={
                        "degradation": degradation,
                        "threshold": max_degradation,
                        "recent_success_rate": recent_rate,
                        "previous_success_rate": previous_rate,
                    },
                    timestamp=datetime.now(tz=UTC),
                )

                self.alert_callback(alert)
                return alert

            return None

        except Exception:
            self.logger.exception("Error checking degradation")
            return None

    def check_failure_rate(self) -> Alert | None:
        """Check if failure rate is too high.

        Returns:
            Alert if failure rate is high, None otherwise

        """
        try:
            with sqlite3.connect(self.storage_path) as conn:
                cursor = conn.cursor()

                # Get failure rate for last 100 tasks
                cursor.execute("""
                    SELECT
                        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
                    FROM (
                        SELECT success FROM task_executions
                        ORDER BY timestamp DESC
                        LIMIT 100
                    )
                """)

                failure_rate = cursor.fetchone()[0]

            if failure_rate is None:
                return None

            min_success_rate = self.config.min_success_rate if self.config else 0.5
            max_failure_rate = (1 - min_success_rate) * 100

            if failure_rate > max_failure_rate:
                alert = Alert(
                    level=AlertLevel.WARNING,
                    title="High Failure Rate",
                    message=f"Failure rate ({failure_rate:.1f}%) exceeds threshold ({max_failure_rate:.1f}%)",
                    details={
                        "failure_rate": failure_rate,
                        "threshold": max_failure_rate,
                        "success_rate": 100 - failure_rate,
                    },
                    timestamp=datetime.now(tz=UTC),
                )

                self.alert_callback(alert)
                return alert

            return None

        except Exception:
            self.logger.exception("Error checking failure rate")
            return None

    def check_all(self) -> list[Alert]:
        """Run all monitoring checks.

        Returns:
            List of alerts (empty if all checks pass)

        """
        alerts = []

        # Check improvement
        alert = self.check_improvement()
        if alert:
            alerts.append(alert)

        # Check degradation
        alert = self.check_performance_degradation()
        if alert:
            alerts.append(alert)

        # Check failure rate
        alert = self.check_failure_rate()
        if alert:
            alerts.append(alert)

        return alerts

    def get_dashboard_metrics(self) -> dict[str, Any]:
        """Get metrics for monitoring dashboard.

        Returns:
            Dictionary with dashboard metrics

        """
        try:
            with sqlite3.connect(self.storage_path) as conn:
                cursor = conn.cursor()

                # Overall statistics
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_tasks,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate,
                        AVG(execution_time_ms) as avg_time
                    FROM task_executions
                """)
                total_tasks, success_rate, avg_time = cursor.fetchone()

                # Recent performance (last 100 tasks)
                cursor.execute("""
                    SELECT
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate,
                        AVG(execution_time_ms) as avg_time
                    FROM (
                        SELECT success, execution_time_ms FROM task_executions
                        ORDER BY timestamp DESC
                        LIMIT 100
                    )
                """)
                recent_success, recent_time = cursor.fetchone()

                # Latest improvement
                cursor.execute("""
                    SELECT relative_improvement, timestamp
                    FROM improvement_reports
                    ORDER BY timestamp DESC
                    LIMIT 1
                """)
                improvement_result = cursor.fetchone()
                latest_improvement = improvement_result[0] if improvement_result else None
                improvement_timestamp = improvement_result[1] if improvement_result else None

                # Failure breakdown
                cursor.execute("""
                    SELECT failure_type, COUNT(*) as count
                    FROM failures
                    GROUP BY failure_type
                    ORDER BY count DESC
                """)
                failure_breakdown = dict(cursor.fetchall())

                # Top strategies
                cursor.execute("""
                    SELECT strategy_id, success_rate, total_executions
                    FROM strategies
                    ORDER BY success_rate DESC
                    LIMIT 5
                """)
                top_strategies = [
                    {"strategy": row[0], "success_rate": row[1], "executions": row[2]}
                    for row in cursor.fetchall()
                ]

            return {
                "overall": {
                    "total_tasks": total_tasks,
                    "success_rate": success_rate,
                    "avg_execution_time_ms": avg_time,
                },
                "recent": {"success_rate": recent_success, "avg_execution_time_ms": recent_time},
                "improvement": {"latest": latest_improvement, "timestamp": improvement_timestamp},
                "failures": failure_breakdown,
                "top_strategies": top_strategies,
                "timestamp": datetime.now(tz=UTC).isoformat(),
            }

        except Exception as e:
            self.logger.exception("Error getting dashboard metrics")
            return {"error": str(e), "timestamp": datetime.now(tz=UTC).isoformat()}

    def _default_alert_handler(self, alert: Alert) -> None:
        """Default alert handler that logs alerts."""
        log_level = {
            AlertLevel.INFO: logging.INFO,
            AlertLevel.WARNING: logging.WARNING,
            AlertLevel.ERROR: logging.ERROR,
            AlertLevel.CRITICAL: logging.CRITICAL,
        }[alert.level]

        self.logger.log(log_level, f"{alert.title}: {alert.message} | Details: {alert.details}")
