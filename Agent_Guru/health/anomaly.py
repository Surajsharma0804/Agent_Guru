"""Anomaly detection for health metrics."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Agent_Guru.health.engine import BiometricSnapshot, HealthAlert, HealthEngine


class AnomalyDetector:
    """Wraps HealthEngine anomaly detection with continuous monitoring.

    Uses per-alert-type cooldowns so that a heart rate alert does not
    suppress unrelated SpO2 or sleep alerts.
    """

    def __init__(self, engine: HealthEngine, cooldown_s: float = 300.0) -> None:
        self._engine = engine
        self._cooldown_s = cooldown_s
        # Per-alert-type cooldown: {alert_type: last_alert_timestamp}
        self._last_alert_times: dict[str, float] = {}

    def check(self, snapshot: BiometricSnapshot) -> HealthAlert | None:
        """Check snapshot for anomalies, respecting per-type cooldown."""
        alert = self._engine.detect_anomaly(snapshot)
        if alert is None:
            return None

        now = time.time()
        last_time = self._last_alert_times.get(alert.alert_type, 0.0)
        if now - last_time < self._cooldown_s:
            return None  # Same alert type still in cooldown

        self._last_alert_times[alert.alert_type] = now
        return alert

    def reset_cooldown(self, alert_type: str | None = None) -> None:
        """Reset cooldown for a specific alert type or all types.

        Args:
            alert_type: Specific type to reset, or None to reset all.

        """
        if alert_type is None:
            self._last_alert_times.clear()
        else:
            self._last_alert_times.pop(alert_type, None)
