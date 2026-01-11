import statistics
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

# Forward declaration to avoid circular imports
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import structlog
from src.authority.state import BiometricFactor
from src.biometric.providers import BiometricProviderType, BiometricResult

if TYPE_CHECKING:
    from src.intrusion.detection import IntrusionDetector

logger = structlog.get_logger(__name__)


class BiometricFailureType(Enum):
    """Types of biometric verification failures."""

    LOW_CONFIDENCE = "low_confidence"
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    HARDWARE_FAILURE = "hardware_failure"
    USER_CANCELLED = "user_cancelled"
    SPOOFING_DETECTED = "spoofing_detected"
    ENROLLMENT_MISSING = "enrollment_missing"
    SYSTEM_ERROR = "system_error"


class BiometricFailureSeverity(Enum):
    """Severity levels for biometric failures."""

    BENIGN = "benign"  # Normal user error
    SUSPICIOUS = "suspicious"  # Potentially malicious
    MALICIOUS = "malicious"  # Likely attack attempt
    CRITICAL = "critical"  # Definite security breach


@dataclass(frozen=True)
class BiometricFailureEvent:
    """Immutable record of a biometric verification failure."""

    event_id: str
    timestamp: datetime
    factor: BiometricFactor
    failure_type: BiometricFailureType
    failure_severity: BiometricFailureSeverity
    confidence_score: float
    provider_type: BiometricProviderType
    failure_reason: str
    session_id: str
    user_context: Dict[str, str]
    provider_metadata: Optional[Dict[str, str]] = None

    def __post_init__(self):
        """Set event ID if not provided."""
        if not self.event_id:
            object.__setattr__(self, "event_id", str(uuid.uuid4()))


@dataclass
class BiometricFailureDetectionConfig:
    """Configuration for enhanced biometric failure detection."""

    # Failure classification thresholds
    low_confidence_threshold: float = 0.5
    suspicious_failure_rate: float = 0.7  # Failures per minute
    malicious_failure_rate: float = 1.5  # Failures per minute

    # Pattern detection settings
    confidence_degradation_threshold: float = 0.3
    rapid_failure_window_seconds: int = 30
    behavioral_analysis_window_minutes: int = 15

    # Adaptive thresholds
    enable_adaptive_thresholds: bool = True
    baseline_learning_period_hours: int = 24
    threshold_adaptation_rate: float = 0.1

    # Provider-specific settings
    provider_failure_correlation: bool = True
    cross_provider_analysis: bool = True

    # Advanced detection features
    enable_spoofing_detection: bool = True
    enable_timing_analysis: bool = True
    enable_confidence_trend_analysis: bool = True
    enable_behavioral_profiling: bool = True

    # Integration settings
    integrate_with_intrusion_detector: bool = True
    auto_escalate_to_intrusion_events: bool = True

    # Forensic and audit settings
    detailed_forensic_logging: bool = True
    retain_failure_events_hours: int = 72
    max_failure_events_stored: int = 10000


class BiometricFailureDetectionError(Exception):
    """Base exception for biometric failure detection errors."""

    pass


class EnhancedBiometricFailureDetector:
    """
    Enhanced biometric verification failure detector.

    This class provides sophisticated analysis of biometric verification failures,
    including pattern recognition, anomaly detection, and adaptive threshold
    management. It integrates with the GURU intrusion detection system to
    provide comprehensive security monitoring.

    Key Features:
    - Real-time failure classification and analysis
    - Adaptive threshold management based on user behavior
    - Advanced pattern recognition for attack detection
    - Cross-provider correlation analysis
    - Behavioral profiling and anomaly detection
    - Integration with authority state machine
    - Comprehensive forensic logging
    """

    def __init__(
        self,
        config: Optional[BiometricFailureDetectionConfig] = None,
        intrusion_detector: Optional["IntrusionDetector"] = None,
    ):
        """
        Initialize the enhanced biometric failure detector.

        Args:
            config: Configuration for failure detection
            intrusion_detector: Optional intrusion detector for integration
        """
        self.config = config or BiometricFailureDetectionConfig()
        self.intrusion_detector = intrusion_detector

        # Thread safety
        self._lock = threading.RLock()

        # Failure event storage
        self._failure_events: List[BiometricFailureEvent] = []
        self._failure_history: deque = deque(maxlen=1000)

        # Statistical tracking
        self._failure_rates: Dict[BiometricFactor, deque] = defaultdict(lambda: deque(maxlen=100))
        self._confidence_trends: Dict[BiometricFactor, deque] = defaultdict(lambda: deque(maxlen=50))
        self._provider_failures: Dict[BiometricProviderType, int] = defaultdict(int)

        # Adaptive thresholds
        self._adaptive_thresholds: Dict[BiometricFactor, float] = {}
        self._baseline_data: Dict[BiometricFactor, List[float]] = defaultdict(list)
        self._learning_start_time = datetime.utcnow()

        # Behavioral profiling
        self._user_behavior_profile: Dict[str, Any] = {
            "typical_attempt_intervals": [],
            "typical_confidence_ranges": {},
            "preferred_factors": defaultdict(int),
            "time_of_day_patterns": defaultdict(list),
        }

        # Pattern analysis integration
        if self.config.integrate_with_intrusion_detector and self.intrusion_detector:
            self._setup_intrusion_integration()

        # Background monitoring
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(target=self._background_monitor, daemon=True)
        self._monitor_thread.start()

        logger.info(
            "Enhanced biometric failure detector initialized",
            config=self.config.__dict__,
            intrusion_integration=self.intrusion_detector is not None,
            adaptive_thresholds=self.config.enable_adaptive_thresholds,
        )

    def __del__(self):
        """Cleanup resources on destruction."""
        self._monitoring_active = False
        if hasattr(self, "_monitor_thread") and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)

    def analyze_biometric_failure(
        self, biometric_result: BiometricResult, user_context: Optional[Dict[str, str]] = None
    ) -> BiometricFailureEvent:
        """
        Analyze a biometric verification failure and classify its severity.

        Args:
            biometric_result: Result from biometric verification attempt
            user_context: Optional context about the user/session

        Returns:
            BiometricFailureEvent with detailed analysis
        """
        with self._lock:
            current_time = datetime.utcnow()
            user_context = user_context or {}

            # Classify the failure type
            failure_type = self._classify_failure_type(biometric_result)

            # Determine failure severity
            failure_severity = self._assess_failure_severity(biometric_result, failure_type, current_time)

            # Create failure event
            failure_event = BiometricFailureEvent(
                event_id=str(uuid.uuid4()),
                timestamp=current_time,
                factor=biometric_result.factor_type,
                failure_type=failure_type,
                failure_severity=failure_severity,
                confidence_score=biometric_result.confidence_score,
                provider_type=biometric_result.provider_type,
                failure_reason=biometric_result.failure_reason or "Unknown failure",
                session_id=biometric_result.session_id or str(uuid.uuid4()),
                user_context=user_context,
                provider_metadata=biometric_result.provider_data,
            )

            # Store the failure event
            self._failure_events.append(failure_event)
            self._failure_history.append(failure_event)

            # Update statistical tracking
            self._update_failure_statistics(failure_event)

            # Update behavioral profile
            self._update_behavioral_profile(failure_event)

            # Update adaptive thresholds if enabled
            if self.config.enable_adaptive_thresholds:
                self._update_adaptive_thresholds(failure_event)

            # Perform advanced analysis
            self._perform_advanced_analysis(failure_event)

            # Integrate with intrusion detector if configured
            if (
                self.config.integrate_with_intrusion_detector
                and self.intrusion_detector
                and failure_severity
                in [
                    BiometricFailureSeverity.SUSPICIOUS,
                    BiometricFailureSeverity.MALICIOUS,
                    BiometricFailureSeverity.CRITICAL,
                ]
            ):

                self._escalate_to_intrusion_detector(failure_event)

            # Log the failure event
            self._log_failure_event(failure_event)

            return failure_event

    def analyze_successful_verification(
        self, biometric_result: BiometricResult, user_context: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Analyze a successful biometric verification for behavioral profiling.

        Args:
            biometric_result: Result from successful biometric verification
            user_context: Optional context about the user/session
        """
        with self._lock:
            current_time = datetime.utcnow()
            user_context = user_context or {}

            # Update behavioral profile with successful attempt
            self._user_behavior_profile["preferred_factors"][biometric_result.factor_type] += 1

            # Update confidence ranges for this factor
            factor_key = biometric_result.factor_type.value
            if factor_key not in self._user_behavior_profile["typical_confidence_ranges"]:
                self._user_behavior_profile["typical_confidence_ranges"][factor_key] = []

            self._user_behavior_profile["typical_confidence_ranges"][factor_key].append(
                biometric_result.confidence_score
            )

            # Keep only recent confidence scores
            if len(self._user_behavior_profile["typical_confidence_ranges"][factor_key]) > 50:
                self._user_behavior_profile["typical_confidence_ranges"][factor_key] = self._user_behavior_profile[
                    "typical_confidence_ranges"
                ][factor_key][-50:]

            # Update time-of-day patterns
            hour_of_day = current_time.hour
            self._user_behavior_profile["time_of_day_patterns"][hour_of_day].append(current_time)

            # Notify intrusion detector of successful verification
            if self.intrusion_detector:
                self.intrusion_detector.record_successful_verification(biometric_result.factor_type)

            logger.debug(
                "Successful biometric verification analyzed",
                factor=biometric_result.factor_type.value,
                confidence=biometric_result.confidence_score,
                provider=biometric_result.provider_type.value,
            )

    def get_failure_analysis_report(self) -> Dict[str, Any]:
        """
        Get comprehensive failure analysis report.

        Returns:
            Dictionary with detailed failure analysis and statistics
        """
        with self._lock:
            current_time = datetime.utcnow()

            # Calculate failure rates
            recent_failures_1min = self._count_recent_failures(timedelta(minutes=1))
            recent_failures_5min = self._count_recent_failures(timedelta(minutes=5))
            recent_failures_1hour = self._count_recent_failures(timedelta(hours=1))

            # Analyze failure types
            failure_type_counts = defaultdict(int)
            severity_counts = defaultdict(int)

            for event in self._failure_events[-100:]:  # Last 100 events
                failure_type_counts[event.failure_type.value] += 1
                severity_counts[event.failure_severity.value] += 1

            # Factor-specific analysis
            factor_analysis = {}
            for factor in BiometricFactor:
                factor_failures = [e for e in self._failure_events[-100:] if e.factor == factor]

                if factor_failures:
                    confidences = [e.confidence_score for e in factor_failures]
                    factor_analysis[factor.value] = {
                        "failure_count": len(factor_failures),
                        "avg_confidence": statistics.mean(confidences),
                        "min_confidence": min(confidences),
                        "max_confidence": max(confidences),
                        "confidence_std": statistics.stdev(confidences) if len(confidences) > 1 else 0.0,
                    }

            # Provider analysis
            provider_analysis = {}
            for provider_type, failure_count in self._provider_failures.items():
                provider_analysis[provider_type.value] = {
                    "total_failures": failure_count,
                    "failure_rate": failure_count / max(len(self._failure_events), 1),
                }

            # Behavioral analysis
            behavioral_analysis = {
                "preferred_factors": dict(self._user_behavior_profile["preferred_factors"]),
                "typical_confidence_ranges": {
                    factor: {
                        "mean": statistics.mean(scores) if scores else 0.0,
                        "std": statistics.stdev(scores) if len(scores) > 1 else 0.0,
                        "samples": len(scores),
                    }
                    for factor, scores in self._user_behavior_profile["typical_confidence_ranges"].items()
                },
                "active_hours": list(self._user_behavior_profile["time_of_day_patterns"].keys()),
            }

            # Adaptive threshold status
            adaptive_threshold_status = {}
            if self.config.enable_adaptive_thresholds:
                learning_progress = min(
                    1.0,
                    (current_time - self._learning_start_time).total_seconds()
                    / (self.config.baseline_learning_period_hours * 3600),
                )

                adaptive_threshold_status = {
                    "learning_progress": learning_progress,
                    "current_thresholds": {f.value: t for f, t in self._adaptive_thresholds.items()},
                    "baseline_samples": {f.value: len(data) for f, data in self._baseline_data.items()},
                }

            return {
                "total_failure_events": len(self._failure_events),
                "recent_failures": {
                    "1_minute": recent_failures_1min,
                    "5_minutes": recent_failures_5min,
                    "1_hour": recent_failures_1hour,
                },
                "failure_rates": {"per_minute": recent_failures_1min, "per_hour": recent_failures_1hour},
                "failure_type_distribution": dict(failure_type_counts),
                "severity_distribution": dict(severity_counts),
                "factor_analysis": factor_analysis,
                "provider_analysis": provider_analysis,
                "behavioral_analysis": behavioral_analysis,
                "adaptive_thresholds": adaptive_threshold_status,
                "current_threat_assessment": self._assess_current_threat_level(),
                "monitoring_status": {
                    "active": self._monitoring_active,
                    "events_stored": len(self._failure_events),
                    "history_size": len(self._failure_history),
                },
            }

    def get_recent_failure_events(self, limit: int = 20) -> List[BiometricFailureEvent]:
        """
        Get recent failure events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent failure events, most recent first
        """
        with self._lock:
            if not self._failure_events:
                return []
            return list(reversed(self._failure_events[-limit:]))

    def reset_failure_tracking(self, factor: Optional[BiometricFactor] = None) -> None:
        """
        Reset failure tracking (administrative function).

        Args:
            factor: Specific factor to reset, or None to reset all
        """
        with self._lock:
            if factor:
                # Reset specific factor
                self._failure_rates[factor].clear()
                self._confidence_trends[factor].clear()
                if factor in self._adaptive_thresholds:
                    del self._adaptive_thresholds[factor]
                if factor in self._baseline_data:
                    self._baseline_data[factor].clear()

                logger.info("Failure tracking reset for factor", factor=factor.value)
            else:
                # Reset all tracking
                self._failure_events.clear()
                self._failure_history.clear()
                self._failure_rates.clear()
                self._confidence_trends.clear()
                self._provider_failures.clear()
                self._adaptive_thresholds.clear()
                self._baseline_data.clear()
                self._user_behavior_profile = {
                    "typical_attempt_intervals": [],
                    "typical_confidence_ranges": {},
                    "preferred_factors": defaultdict(int),
                    "time_of_day_patterns": defaultdict(list),
                }

                logger.info("All failure tracking reset")

    def _classify_failure_type(self, biometric_result: BiometricResult) -> BiometricFailureType:
        """Classify the type of biometric failure."""
        if biometric_result.confidence_score < self.config.low_confidence_threshold:
            return BiometricFailureType.LOW_CONFIDENCE

        failure_reason = biometric_result.failure_reason or ""
        failure_reason_lower = failure_reason.lower()

        if "timeout" in failure_reason_lower:
            return BiometricFailureType.TIMEOUT
        elif "hardware" in failure_reason_lower or "device" in failure_reason_lower:
            return BiometricFailureType.HARDWARE_FAILURE
        elif "cancelled" in failure_reason_lower or "user" in failure_reason_lower:
            return BiometricFailureType.USER_CANCELLED
        elif "spoof" in failure_reason_lower or "fake" in failure_reason_lower:
            return BiometricFailureType.SPOOFING_DETECTED
        elif "enrollment" in failure_reason_lower or "not enrolled" in failure_reason_lower:
            return BiometricFailureType.ENROLLMENT_MISSING
        elif "provider" in failure_reason_lower or "api" in failure_reason_lower:
            return BiometricFailureType.PROVIDER_ERROR
        else:
            return BiometricFailureType.SYSTEM_ERROR

    def _assess_failure_severity(
        self, biometric_result: BiometricResult, failure_type: BiometricFailureType, current_time: datetime
    ) -> BiometricFailureSeverity:
        """Assess the severity of a biometric failure."""

        # Calculate recent failure rate
        recent_failures = self._count_recent_failures(timedelta(minutes=1))
        failure_rate_per_minute = recent_failures

        # Critical severity conditions
        if (
            failure_type == BiometricFailureType.SPOOFING_DETECTED
            or failure_rate_per_minute >= self.config.malicious_failure_rate
        ):
            return BiometricFailureSeverity.CRITICAL

        # Malicious severity conditions
        if failure_rate_per_minute >= self.config.malicious_failure_rate or self._detect_attack_patterns(
            biometric_result, current_time
        ):
            return BiometricFailureSeverity.MALICIOUS

        # Suspicious severity conditions
        suspicious_conditions = [
            failure_rate_per_minute >= self.config.suspicious_failure_rate,
            self._detect_suspicious_patterns(biometric_result, current_time),
            # Very low confidence scores are inherently suspicious
            biometric_result.confidence_score < 0.2,
            # Multiple rapid low-confidence attempts
            (failure_rate_per_minute >= 2 and biometric_result.confidence_score < 0.3),
        ]

        if any(suspicious_conditions):
            return BiometricFailureSeverity.SUSPICIOUS

        # Default to benign for normal user errors
        return BiometricFailureSeverity.BENIGN

    def _detect_attack_patterns(self, biometric_result: BiometricResult, current_time: datetime) -> bool:
        """Detect patterns indicative of attack attempts."""

        # Check for rapid successive attempts
        recent_attempts = [e for e in self._failure_history if (current_time - e.timestamp).total_seconds() <= 30]

        if len(recent_attempts) >= 5:
            return True

        # Check for cross-factor attacks
        if self.config.cross_provider_analysis:
            recent_factors = set(e.factor for e in recent_attempts)
            if len(recent_factors) >= 2:
              # Multiple factors being attacked
                return True

        # Check for confidence manipulation patterns
        if len(recent_attempts) >= 3:
            confidences = [e.confidence_score for e in recent_attempts]
            if all(c < 0.3 for c in confidences):
              # All very low confidence
                return True

        return False

    def _detect_suspicious_patterns(self, biometric_result: BiometricResult, current_time: datetime) -> bool:
        """Detect patterns that are suspicious but not definitively malicious."""

        # Check for unusual timing patterns
        if len(self._failure_history) >= 2:
            last_failure = self._failure_history[-1]
            time_diff = (current_time - last_failure.timestamp).total_seconds()

            # Very rapid attempts (less than human reaction time)
            if time_diff < 2.0:
                return True

        # Check for provider switching patterns
        if self.config.provider_failure_correlation:
            # Convert deque to list for slicing
            recent_events = list(self._failure_history)[-5:]
            recent_providers = [e.provider_type for e in recent_events]
            unique_providers = set(recent_providers)
            if len(unique_providers) >= 2:
              # Switching between providers
                return True

        # Check against behavioral baseline
        if self._is_outside_behavioral_baseline(biometric_result, current_time):
            return True

        return False

    def _is_outside_behavioral_baseline(self, biometric_result: BiometricResult, current_time: datetime) -> bool:
        """Check if the failure is outside normal behavioral patterns."""

        # Check time-of-day patterns
        hour_of_day = current_time.hour
        typical_hours = set(self._user_behavior_profile["time_of_day_patterns"].keys())

        if typical_hours and hour_of_day not in typical_hours:
            # Activity outside typical hours
            return True

        # Check confidence score against typical ranges
        factor_key = biometric_result.factor_type.value
        typical_confidences = self._user_behavior_profile["typical_confidence_ranges"].get(factor_key, [])

        if typical_confidences:
            mean_confidence = statistics.mean(typical_confidences)
            std_confidence = statistics.stdev(typical_confidences) if len(typical_confidences) > 1 else 0.1

            # Check if confidence is significantly below typical range
            if biometric_result.confidence_score < (mean_confidence - 2 * std_confidence):
                return True

        return False

    def _update_failure_statistics(self, failure_event: BiometricFailureEvent) -> None:
        """Update failure statistics with new event."""

        # Update failure rates
        self._failure_rates[failure_event.factor].append(failure_event.timestamp)

        # Update confidence trends
        self._confidence_trends[failure_event.factor].append(failure_event.confidence_score)

        # Update provider failure counts
        self._provider_failures[failure_event.provider_type] += 1

    def _update_behavioral_profile(self, failure_event: BiometricFailureEvent) -> None:
        """Update behavioral profile with failure event."""

        # Update attempt intervals
        if len(self._failure_history) >= 2:
            last_event = self._failure_history[-2]  # Second to last event
            interval = (failure_event.timestamp - last_event.timestamp).total_seconds()
            self._user_behavior_profile["typical_attempt_intervals"].append(interval)

            # Keep only recent intervals
            if len(self._user_behavior_profile["typical_attempt_intervals"]) > 100:
                self._user_behavior_profile["typical_attempt_intervals"] = self._user_behavior_profile[
                    "typical_attempt_intervals"
                ][-100:]

    def _update_adaptive_thresholds(self, failure_event: BiometricFailureEvent) -> None:
        """Update adaptive thresholds based on failure patterns."""

        factor = failure_event.factor

        # Add to baseline data during learning period
        learning_elapsed = (datetime.utcnow() - self._learning_start_time).total_seconds()
        learning_period_seconds = self.config.baseline_learning_period_hours * 3600

        if learning_elapsed < learning_period_seconds:
            self._baseline_data[factor].append(failure_event.confidence_score)

        # Update adaptive threshold if we have enough baseline data
        if len(self._baseline_data[factor]) >= 10:
            baseline_mean = statistics.mean(self._baseline_data[factor])
            baseline_std = statistics.stdev(self._baseline_data[factor])

            # Calculate adaptive threshold
            adaptive_threshold = baseline_mean - (2 * baseline_std)
            adaptive_threshold = max(0.1, min(0.9, adaptive_threshold))  # Clamp to reasonable range

            # Update with adaptation rate
            if factor in self._adaptive_thresholds:
                current_threshold = self._adaptive_thresholds[factor]
                new_threshold = (
                    current_threshold * (1 - self.config.threshold_adaptation_rate)
                    + adaptive_threshold * self.config.threshold_adaptation_rate
                )
                self._adaptive_thresholds[factor] = new_threshold
            else:
                self._adaptive_thresholds[factor] = adaptive_threshold

    def _perform_advanced_analysis(self, failure_event: BiometricFailureEvent) -> None:
        """Perform advanced analysis on the failure event."""

        # Confidence trend analysis
        if self.config.enable_confidence_trend_analysis:
            self._analyze_confidence_trends(failure_event)

        # Timing analysis
        if self.config.enable_timing_analysis:
            self._analyze_timing_patterns(failure_event)

        # Behavioral profiling
        if self.config.enable_behavioral_profiling:
            self._analyze_behavioral_patterns(failure_event)

    def _analyze_confidence_trends(self, failure_event: BiometricFailureEvent) -> None:
        """Analyze confidence score trends for anomalies."""

        factor = failure_event.factor
        recent_confidences = list(self._confidence_trends[factor])[-10:]  # Last 10 attempts

        if len(recent_confidences) >= 5:
            # Check for degrading trend
            if len(recent_confidences) >= 3:
                trend_slope = (recent_confidences[-1] - recent_confidences[0]) / len(recent_confidences)

                if trend_slope < -self.config.confidence_degradation_threshold:
                    logger.warning(
                        "Confidence degradation trend detected",
                        factor=factor.value,
                        trend_slope=trend_slope,
                        recent_confidences=recent_confidences,
                    )

    def _analyze_timing_patterns(self, failure_event: BiometricFailureEvent) -> None:
        """Analyze timing patterns for anomalies."""

        if len(self._failure_history) >= 2:
            recent_intervals = []
            failure_history_list = list(self._failure_history)

            for i in range(1, min(6, len(failure_history_list))):
                interval = (failure_history_list[-i].timestamp - failure_history_list[-i - 1].timestamp).total_seconds()
                recent_intervals.append(interval)

            if recent_intervals:
                avg_interval = statistics.mean(recent_intervals)

                # Check for unusually rapid attempts
                if avg_interval < 5.0:  # Less than 5 seconds average
                    logger.warning(
                        "Rapid attempt pattern detected",
                        average_interval=avg_interval,
                        recent_intervals=recent_intervals,
                    )

    def _analyze_behavioral_patterns(self, failure_event: BiometricFailureEvent) -> None:
        """Analyze behavioral patterns for anomalies."""

        # Check for unusual factor usage patterns
        failure_history_list = list(self._failure_history)
        recent_factors = [e.factor for e in failure_history_list[-10:]]
        factor_counts = defaultdict(int)
        for factor in recent_factors:
            factor_counts[factor] += 1

        # Check for factor switching behavior
        unique_factors = len(set(recent_factors))
        if unique_factors >= 3:
            # Using 3+ different factors recently
            logger.warning(
                "Factor switching pattern detected",
                unique_factors=unique_factors,
                factor_distribution=dict(factor_counts),
            )

    def _escalate_to_intrusion_detector(self, failure_event: BiometricFailureEvent) -> None:
        """Escalate failure event to intrusion detector."""

        if not self.intrusion_detector:
            return

        # Convert failure event to intrusion detector format
        intrusion_event = self.intrusion_detector.record_biometric_failure(
            factor=failure_event.factor,
            failure_reason=failure_event.failure_reason,
            confidence_score=failure_event.confidence_score,
            provider=failure_event.provider_type.value,
        )

        if intrusion_event:
            logger.warning(
                "Biometric failure escalated to intrusion detector",
                failure_event_id=failure_event.event_id,
                intrusion_event_id=intrusion_event.event_id,
                severity=failure_event.failure_severity.value,
            )

    def _setup_intrusion_integration(self) -> None:
        """Setup integration with intrusion detector."""

        if not self.intrusion_detector:
            return

        # Register callback for intrusion events
        def on_intrusion_event(event):
            logger.info(
                "Intrusion event received from detector",
                event_type=event.event_type.value,
                severity=event.severity.value,
            )

        self.intrusion_detector.register_response_callback(on_intrusion_event)

    def _count_recent_failures(self, time_window: timedelta) -> int:
        """Count failures within the specified time window."""

        current_time = datetime.utcnow()
        cutoff_time = current_time - time_window

        return sum(1 for event in self._failure_events if event.timestamp > cutoff_time)

    def _assess_current_threat_level(self) -> str:
        """Assess current threat level based on recent activity."""

        recent_failures_1min = self._count_recent_failures(timedelta(minutes=1))
        recent_failures_5min = self._count_recent_failures(timedelta(minutes=5))

        # Count high-severity events
        recent_critical = sum(
            1 for event in self._failure_events[-20:] if event.failure_severity == BiometricFailureSeverity.CRITICAL
        )

        recent_malicious = sum(
            1 for event in self._failure_events[-20:] if event.failure_severity == BiometricFailureSeverity.MALICIOUS
        )

        if recent_critical > 0:
            return "CRITICAL"
        elif recent_malicious >= 2 or recent_failures_1min >= 5:
            return "HIGH"
        elif recent_failures_5min >= 3:
            return "MEDIUM"
        else:
            return "LOW"

    def _log_failure_event(self, failure_event: BiometricFailureEvent) -> None:
        """Log failure event with appropriate severity."""

        log_data = {
            "event_id": failure_event.event_id,
            "factor": failure_event.factor.value,
            "failure_type": failure_event.failure_type.value,
            "severity": failure_event.failure_severity.value,
            "confidence": failure_event.confidence_score,
            "provider": failure_event.provider_type.value,
            "session_id": failure_event.session_id,
        }

        if failure_event.failure_severity == BiometricFailureSeverity.CRITICAL:
            logger.critical("CRITICAL biometric failure detected", **log_data)
        elif failure_event.failure_severity == BiometricFailureSeverity.MALICIOUS:
            logger.error("MALICIOUS biometric failure detected", **log_data)
        elif failure_event.failure_severity == BiometricFailureSeverity.SUSPICIOUS:
            logger.warning("SUSPICIOUS biometric failure detected", **log_data)
        else:
            logger.info("Biometric failure recorded", **log_data)

    def _background_monitor(self) -> None:
        """Background monitoring thread for continuous analysis."""

        while self._monitoring_active:
            try:
                with self._lock:
                    current_time = datetime.utcnow()

                    # Clean up old events
                    cutoff_time = current_time - timedelta(hours=self.config.retain_failure_events_hours)
                    self._failure_events = [event for event in self._failure_events if event.timestamp > cutoff_time]

                    # Limit total events stored
                    if len(self._failure_events) > self.config.max_failure_events_stored:
                        self._failure_events = self._failure_events[-self.config.max_failure_events_stored:]

                    # Perform periodic analysis
                    self._periodic_analysis()

                # Sleep between monitoring cycles
                time.sleep(10.0)  # 10 second monitoring cycle

            except Exception as e:
                logger.error("Error in background monitoring", error=str(e))
                time.sleep(30.0)  # Longer sleep on error

    def _periodic_analysis(self) -> None:
        """Perform periodic analysis of failure patterns."""

        # Update adaptive thresholds
        if self.config.enable_adaptive_thresholds:
            self._update_periodic_adaptive_thresholds()

        # Analyze long-term trends
        self._analyze_long_term_trends()

    def _update_periodic_adaptive_thresholds(self) -> None:
        """Update adaptive thresholds during periodic analysis."""

        # This could include more sophisticated threshold updates
        # based on long-term patterns and user behavior
        pass

    def _analyze_long_term_trends(self) -> None:
        """Analyze long-term failure trends."""

        # Analyze trends over longer time periods
        # This could include weekly/monthly pattern analysis
        pass


# Factory function for easy instantiation


def create_enhanced_biometric_failure_detector(
    config: Optional[BiometricFailureDetectionConfig] = None,
    intrusion_detector: Optional["IntrusionDetector"] = None
) -> EnhancedBiometricFailureDetector:
    """
    Factory function to create an enhanced biometric failure detector.

    Args:
        config: Optional configuration, uses defaults if None
        intrusion_detector: Optional intrusion detector for integration

    Returns:
        Configured EnhancedBiometricFailureDetector instance
    """
    return EnhancedBiometricFailureDetector(config, intrusion_detector)


# Export public interface
__all__ = [
    "BiometricFailureType",
    "BiometricFailureSeverity",
    "BiometricFailureEvent",
    "BiometricFailureDetectionConfig",
    "BiometricFailureDetectionError",
    "EnhancedBiometricFailureDetector",
    "create_enhanced_biometric_failure_detector",
]
