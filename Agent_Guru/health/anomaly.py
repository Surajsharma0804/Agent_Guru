"""Anomaly detection for health metrics."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Agent_Guru.health.engine import BiometricSnapshot, HealthAlert, HealthEngine


class AnomalyDetector:
    """Wraps HealthEngine anomaly detection with continuous monitoring."""

    def __init__(self, engine: HealthEngine) -> None:
        self._engine = engine
        self._last_alert_time: float = 0.0
        self._alert_cooldown_s: float = 300.0  # 5 minutes between same alerts

    def check(self, snapshot: BiometricSnapshot) -> HealthAlert | None:
        """Check snapshot for anomalies, respecting cooldown."""
        now = time.time()
        if now - self._last_alert_time < self._alert_cooldown_s:
            return None
        alert = self._engine.detect_anomaly(snapshot)
        if alert:
            self._last_alert_time = now
        return alert
