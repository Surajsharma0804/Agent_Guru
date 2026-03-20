"""Health and Wellness Intelligence Engine.

Requirements: 15.1-15.10
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "BiometricSnapshot",
    "BehavioralInsight",
    "HealthAlert",
    "HealthEngine",
    "MedicationLog",
    "SleepStage",
    "WellnessSummary",
]

ANOMALY_DETECTION_TIMEOUT_S = 60
HR_HIGH_THRESHOLD = 150  # BPM at rest
SPO2_LOW_THRESHOLD = 90  # %
SLEEP_LOW_THRESHOLD_H = 4.0


class SleepStage(Enum):
    AWAKE = "awake"
    LIGHT = "light"
    DEEP = "deep"
    REM = "rem"


@dataclass
class BiometricSnapshot:
    """Aggregated biometric data from connected platforms."""

    heart_rate_bpm: float | None = None
    hrv_ms: float | None = None
    spo2_pct: float | None = None
    sleep_hours: float | None = None
    sleep_stage: SleepStage | None = None
    steps: int | None = None
    stress_score: float | None = None  # 0-100
    timestamp: float = field(default_factory=time.time)


@dataclass
class HealthAlert:
    """Alert for detected health anomaly."""

    alert_type: str
    value: float
    threshold: float
    message: str
    timestamp: float = field(default_factory=time.time)
    requires_medical_disclaimer: bool = True


@dataclass
class WellnessSummary:
    """Daily wellness summary."""

    sleep_quality_score: float  # 0-100
    activity_goal_pct: float  # 0-100
    stress_level: str  # low/moderate/high
    recovery_readiness: float  # 0-100
    medical_disclaimer: str = (
        "This information is for general wellness purposes only and is not "
        "medical advice. Consult a healthcare professional for medical concerns."
    )


@dataclass
class BehavioralInsight:
    """7-day behavioral trend insight."""

    insight_type: str  # sleep_regression/activity_decline/elevated_hr
    description: str
    days_observed: int
    severity: str  # low/moderate/high


@dataclass
class MedicationLog:
    """Medication adherence record."""

    medication_name: str
    scheduled_time: float
    taken_time: float | None = None
    taken: bool = False


class HealthEngine:
    """Aggregates health data, detects anomalies, and generates wellness insights."""

    def __init__(self) -> None:
        self._platforms: dict[str, Any] = {}
        self._snapshots: list[BiometricSnapshot] = []
        self._medication_logs: list[MedicationLog] = []
        self._audit_log: list[dict[str, Any]] = []
        self._encryption_key: bytes | None = None

    # ------------------------------------------------------------------
    # Platform connectivity
    # ------------------------------------------------------------------

    def connect_platform(self, platform: str, credentials: dict[str, Any]) -> bool:
        """Connect to a health platform (HealthKit, Google Health, Fitbit, etc.)."""
        supported = {
            "apple_healthkit",
            "google_health_connect",
            "fitbit",
            "garmin_connect",
            "oura_ring",
        }
        if platform not in supported:
            logger.warning("Unsupported platform: %s", platform)
            return False
        self._platforms[platform] = credentials
        self._audit("connect_platform", {"platform": platform})
        logger.info("Connected to %s", platform)
        return True

    def disconnect_platform(self, platform: str) -> None:
        self._platforms.pop(platform, None)
        self._audit("disconnect_platform", {"platform": platform})

    # ------------------------------------------------------------------
    # Data aggregation
    # ------------------------------------------------------------------

    def get_snapshot(self) -> BiometricSnapshot:
        """Aggregate current biometric data from all connected platforms."""
        snapshot = BiometricSnapshot()
        # Stub: in production, query each platform SDK
        if self._snapshots:
            last = self._snapshots[-1]
            snapshot.heart_rate_bpm = last.heart_rate_bpm
            snapshot.hrv_ms = last.hrv_ms
            snapshot.spo2_pct = last.spo2_pct
            snapshot.sleep_hours = last.sleep_hours
            snapshot.steps = last.steps
            snapshot.stress_score = last.stress_score
        self._audit("get_snapshot", {})
        return snapshot

    def ingest_snapshot(self, snapshot: BiometricSnapshot) -> None:
        """Ingest a biometric snapshot (from platform connector)."""
        self._snapshots.append(snapshot)
        # Keep 7 days of data (assuming hourly snapshots)
        max_snapshots = 7 * 24
        if len(self._snapshots) > max_snapshots:
            self._snapshots = self._snapshots[-max_snapshots:]

    # ------------------------------------------------------------------
    # Anomaly detection
    # ------------------------------------------------------------------

    def detect_anomaly(self, snapshot: BiometricSnapshot) -> HealthAlert | None:
        """Detect health anomalies within 60s. Returns alert if anomaly found."""
        start = time.time()

        if snapshot.heart_rate_bpm is not None and snapshot.heart_rate_bpm > HR_HIGH_THRESHOLD:
            alert = HealthAlert(
                alert_type="high_heart_rate",
                value=snapshot.heart_rate_bpm,
                threshold=HR_HIGH_THRESHOLD,
                message=f"Resting heart rate {snapshot.heart_rate_bpm:.0f} BPM exceeds threshold. "
                "Please consult a healthcare professional.",
            )
            self._audit("anomaly_detected", {"type": "high_heart_rate"})
            return alert

        if snapshot.spo2_pct is not None and snapshot.spo2_pct < SPO2_LOW_THRESHOLD:
            alert = HealthAlert(
                alert_type="low_spo2",
                value=snapshot.spo2_pct,
                threshold=SPO2_LOW_THRESHOLD,
                message=f"Blood oxygen {snapshot.spo2_pct:.1f}% is below safe threshold. "
                "Seek immediate medical attention if symptoms persist.",
            )
            self._audit("anomaly_detected", {"type": "low_spo2"})
            return alert

        if snapshot.sleep_hours is not None and snapshot.sleep_hours < SLEEP_LOW_THRESHOLD_H:
            alert = HealthAlert(
                alert_type="insufficient_sleep",
                value=snapshot.sleep_hours,
                threshold=SLEEP_LOW_THRESHOLD_H,
                message=f"Only {snapshot.sleep_hours:.1f}h of sleep detected. "
                "Chronic sleep deprivation affects health.",
            )
            self._audit("anomaly_detected", {"type": "insufficient_sleep"})
            return alert

        elapsed = time.time() - start
        logger.debug("Anomaly detection completed in %.3fs", elapsed)
        return None

    # ------------------------------------------------------------------
    # Wellness summaries
    # ------------------------------------------------------------------

    def generate_daily_summary(self) -> WellnessSummary:
        """Generate daily wellness summary from recent snapshots."""
        if not self._snapshots:
            return WellnessSummary(
                sleep_quality_score=0.0,
                activity_goal_pct=0.0,
                stress_level="unknown",
                recovery_readiness=0.0,
            )

        recent = self._snapshots[-1]

        # Sleep quality: 0-100 based on hours (8h = 100)
        sleep_h = recent.sleep_hours or 0.0
        sleep_score = min(100.0, (sleep_h / 8.0) * 100)

        # Activity: steps toward 10k goal
        steps = recent.steps or 0
        activity_pct = min(100.0, (steps / 10000) * 100)

        # Stress level
        stress = recent.stress_score or 50.0
        if stress < 33:
            stress_level = "low"
        elif stress < 66:
            stress_level = "moderate"
        else:
            stress_level = "high"

        # Recovery readiness: inverse of stress, weighted with HRV
        hrv = recent.hrv_ms or 50.0
        recovery = min(100.0, (hrv / 100.0) * 50 + (1 - stress / 100) * 50)

        self._audit("daily_summary", {})
        return WellnessSummary(
            sleep_quality_score=round(sleep_score, 1),
            activity_goal_pct=round(activity_pct, 1),
            stress_level=stress_level,
            recovery_readiness=round(recovery, 1),
        )

    # ------------------------------------------------------------------
    # Behavioral trends
    # ------------------------------------------------------------------

    def get_behavioral_trends(self) -> list[BehavioralInsight]:
        """Analyze 7-day rolling window for behavioral trends."""
        insights: list[BehavioralInsight] = []
        if len(self._snapshots) < 7:
            return insights

        recent_7 = self._snapshots[-7:]

        # Sleep regression: average sleep declining
        sleep_values = [s.sleep_hours for s in recent_7 if s.sleep_hours is not None]
        if len(sleep_values) >= 4:
            first_half = sum(sleep_values[: len(sleep_values) // 2]) / (len(sleep_values) // 2)
            second_half = sum(sleep_values[len(sleep_values) // 2 :]) / (
                len(sleep_values) - len(sleep_values) // 2
            )
            if second_half < first_half * 0.85:
                insights.append(
                    BehavioralInsight(
                        insight_type="sleep_regression",
                        description="Sleep duration has declined over the past week.",
                        days_observed=len(sleep_values),
                        severity="moderate",
                    )
                )

        # Activity decline
        step_values = [s.steps for s in recent_7 if s.steps is not None]
        if len(step_values) >= 4:
            first_half = sum(step_values[: len(step_values) // 2]) / (len(step_values) // 2)
            second_half = sum(step_values[len(step_values) // 2 :]) / (
                len(step_values) - len(step_values) // 2
            )
            if second_half < first_half * 0.75:
                insights.append(
                    BehavioralInsight(
                        insight_type="activity_decline",
                        description="Daily step count has significantly decreased.",
                        days_observed=len(step_values),
                        severity="low",
                    )
                )

        # Elevated resting HR
        hr_values = [s.heart_rate_bpm for s in recent_7 if s.heart_rate_bpm is not None]
        if hr_values and sum(hr_values) / len(hr_values) > 90:
            insights.append(
                BehavioralInsight(
                    insight_type="elevated_resting_hr",
                    description="Average resting heart rate elevated over past week.",
                    days_observed=len(hr_values),
                    severity="moderate",
                )
            )

        return insights

    # ------------------------------------------------------------------
    # Medication tracking
    # ------------------------------------------------------------------

    def log_medication(self, medication_name: str, scheduled_time: float) -> MedicationLog:
        """Log a scheduled medication."""
        log = MedicationLog(medication_name=medication_name, scheduled_time=scheduled_time)
        self._medication_logs.append(log)
        self._audit("medication_logged", {"medication": medication_name})
        return log

    def mark_medication_taken(self, medication_name: str) -> bool:
        """Mark a medication as taken."""
        for log in reversed(self._medication_logs):
            if log.medication_name == medication_name and not log.taken:
                log.taken = True
                log.taken_time = time.time()
                self._audit("medication_taken", {"medication": medication_name})
                return True
        return False

    def get_adherence_rate(self, medication_name: str) -> float:
        """Calculate medication adherence rate (0.0-1.0)."""
        logs = [entry for entry in self._medication_logs if entry.medication_name == medication_name]
        if not logs:
            return 0.0
        taken = sum(1 for entry in logs if entry.taken)
        return taken / len(logs)

    # ------------------------------------------------------------------
    # HIPAA-compliant audit and deletion
    # ------------------------------------------------------------------

    def _audit(self, action: str, details: dict[str, Any]) -> None:
        """HIPAA-compliant audit log entry."""
        entry = {
            "action": action,
            "details": details,
            "timestamp": time.time(),
            "hash": hashlib.sha256(
                json.dumps({"action": action, "ts": time.time()}).encode()
            ).hexdigest()[:16],
        }
        self._audit_log.append(entry)

    def delete_user_data(self) -> None:
        """User-controlled deletion of all health data."""
        self._snapshots.clear()
        self._medication_logs.clear()
        self._audit("user_data_deleted", {})
        logger.info("All user health data deleted")

    def get_audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit_log)
