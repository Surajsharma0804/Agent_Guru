"""
Intrusion Detection Engine

This module implements the core intrusion detection logic for GURU, monitoring
biometric verification failures, analyzing patterns, and triggering appropriate
security responses using platform-agnostic PAL interfaces.

Security Features:
- Real-time failure pattern analysis
- Adaptive threshold management
- Comprehensive event logging
- Immediate response triggering via PAL SecurityEnforcer
- Thread-safe operation
- Cross-platform security enforcement

Architecture:
- Uses PAL SecurityEnforcer for platform-agnostic workstation locking
- Maintains pattern analysis and threat detection logic
- Delegates platform-specific security operations to PAL backends
"""

import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Dict, List, Optional

import structlog

# PAL imports - platform-agnostic interfaces
from pal.interfaces import SecurityEnforcer

from ..biometric.providers import BiometricFactor
from .patterns import (
    FailurePattern,
    PatternAnalysisConfig,
    PatternSeverity,
    create_failure_pattern_analyzer,
)

logger = structlog.get_logger(__name__)


class IntrusionEventType(Enum):
    """Types of intrusion events that can be detected."""

    BIOMETRIC_FAILURE = "biometric_failure"
    REPEATED_FAILURES = "repeated_failures"
    RAPID_ATTEMPTS = "rapid_attempts"
    UNUSUAL_TIMING = "unusual_timing"
    MULTIPLE_FACTORS_FAILED = "multiple_factors_failed"
    THRESHOLD_EXCEEDED = "threshold_exceeded"
    PATTERN_ANOMALY = "pattern_anomaly"
    SYSTEM_TAMPERING = "system_tampering"


class IntrusionSeverity(Enum):
    """Severity levels for intrusion events."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class IntrusionEvent:
    """Immutable record of an intrusion detection event."""

    event_id: str
    event_type: IntrusionEventType
    severity: IntrusionSeverity
    timestamp: datetime
    source_factor: Optional[BiometricFactor]
    failure_count: int
    time_window_seconds: float
    metadata: Dict[str, str]
    session_id: str

    def __post_init__(self):
        """Set event ID if not provided."""
        if not self.event_id:
            object.__setattr__(self, "event_id", str(uuid.uuid4()))


@dataclass
class IntrusionDetectionConfig:
    """Configuration for intrusion detection system."""

    # Failure thresholds
    max_failures_per_factor: int = 3
    max_total_failures: int = 5
    max_failures_per_minute: int = 10
    max_failures_per_hour: int = 20

    # Time windows for analysis
    rapid_attempt_window_seconds: int = 30
    pattern_analysis_window_minutes: int = 15
    cooldown_period_minutes: int = 5

    # Pattern detection thresholds
    unusual_timing_threshold_seconds: int = 2  # Attempts faster than human reaction
    multiple_factor_failure_threshold: int = 2  # Different factors failing

    # Response configuration
    enable_automatic_lockdown: bool = True
    lockdown_on_critical_events: bool = True
    lockdown_on_high_severity_count: int = 3

    # Security enforcement configuration (via PAL)
    enable_security_enforcement: bool = True
    lock_on_critical_events: bool = True
    lock_on_high_severity_events: bool = True
    lock_on_multiple_failures: bool = True

    # Monitoring settings
    enable_pattern_analysis: bool = True
    enable_timing_analysis: bool = True
    enable_behavioral_analysis: bool = True

    # Pattern analysis configuration
    pattern_analysis_config: Optional[PatternAnalysisConfig] = None

    # Logging and audit
    log_all_events: bool = True
    log_pattern_analysis: bool = True
    retain_events_hours: int = 24


class IntrusionDetectionError(Exception):
    """Base exception for intrusion detection errors."""

    pass


class IntrusionDetector:
    """
    Advanced intrusion detection system for GURU using PAL SecurityEnforcer.

    This class monitors biometric verification attempts, analyzes failure patterns,
    and triggers appropriate security responses when suspicious activity is detected.

    Key Features:
    - Real-time failure monitoring
    - Pattern-based anomaly detection
    - Adaptive threshold management
    - Comprehensive event logging
    - Integration with authority state machine
    - Platform-agnostic security enforcement via PAL

    Architecture:
    - Uses PAL SecurityEnforcer for cross-platform session locking
    - Maintains pattern analysis and threat detection logic
    - Thread-safe operation with proper resource management
    """

    def __init__(
        self,
        security_enforcer: SecurityEnforcer,
        config: Optional[IntrusionDetectionConfig] = None
    ):
        """
        Initialize the intrusion detection system with PAL interface.
        
        Args:
            security_enforcer: Platform-specific SecurityEnforcer implementation
            config: Optional configuration (uses defaults if None)
        """
        self.config = config or IntrusionDetectionConfig()
        self.security_enforcer = security_enforcer

        # Thread safety
        self._lock = threading.RLock()

        # Event tracking
        self._events: List[IntrusionEvent] = []
        self._failure_counts: Dict[BiometricFactor, int] = defaultdict(int)
        self._total_failures: int = 0
        self._last_failure_time: Optional[datetime] = None

        # Pattern analysis
        self._recent_attempts: deque = deque(maxlen=100)  # Recent attempt timestamps
        self._factor_failure_history: Dict[BiometricFactor, deque] = defaultdict(lambda: deque(maxlen=50))

        # Initialize pattern analyzer
        pattern_config = self.config.pattern_analysis_config or PatternAnalysisConfig()
        self._pattern_analyzer = create_failure_pattern_analyzer(pattern_config)

        # Get security enforcer capabilities
        self.security_capabilities = security_enforcer.get_capabilities()

        # Response callbacks
        self._response_callbacks: List[Callable[[IntrusionEvent], None]] = []
        self._pattern_callbacks: List[Callable[[FailurePattern], None]] = []

        # Monitoring state
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(target=self._monitor_patterns, daemon=True)
        self._monitor_thread.start()

        # Session tracking
        self._current_session_id = str(uuid.uuid4())

        logger.info(
            "Intrusion detection system initialized",
            config=self.config.__dict__,
            session_id=self._current_session_id,
            pattern_analysis_enabled=self.config.enable_pattern_analysis,
            security_enforcement_enabled=self.config.enable_security_enforcement,
            security_capabilities=self.security_capabilities,
        )

    def __del__(self):
        """Cleanup resources on destruction."""
        self._monitoring_active = False
        if hasattr(self, "_monitor_thread") and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)

    def register_response_callback(self, callback: Callable[[IntrusionEvent], None]) -> None:
        """
        Register a callback function to be called when intrusion events occur.

        Args:
            callback: Function to call with IntrusionEvent parameter
        """
        with self._lock:
            self._response_callbacks.append(callback)
            logger.info("Response callback registered", callback_count=len(self._response_callbacks))

    def register_pattern_callback(self, callback: Callable[[FailurePattern], None]) -> None:
        """
        Register a callback function to be called when failure patterns are detected.

        Args:
            callback: Function to call with FailurePattern parameter
        """
        with self._lock:
            self._pattern_callbacks.append(callback)
            logger.info("Pattern callback registered", callback_count=len(self._pattern_callbacks))

    def record_biometric_failure(
        self, factor: BiometricFactor, failure_reason: str, confidence_score: float = 0.0, provider: str = "unknown"
    ) -> Optional[IntrusionEvent]:
        """
        Record a biometric verification failure and analyze for intrusion patterns.

        Args:
            factor: The biometric factor that failed
            failure_reason: Reason for the failure
            confidence_score: Confidence score of the failed attempt
            provider: Biometric provider that reported the failure

        Returns:
            IntrusionEvent if suspicious activity detected, None otherwise
        """
        with self._lock:
            current_time = datetime.utcnow()

            # Update failure counters
            self._failure_counts[factor] += 1
            self._total_failures += 1
            self._last_failure_time = current_time

            # Record attempt timing
            self._recent_attempts.append(current_time)
            self._factor_failure_history[factor].append(
                {
                    "timestamp": current_time,
                    "reason": failure_reason,
                    "confidence": confidence_score,
                    "provider": provider,
                }
            )

            logger.warning(
                "Biometric verification failure recorded",
                factor=factor.value,
                reason=failure_reason,
                confidence=confidence_score,
                provider=provider,
                factor_failures=self._failure_counts[factor],
                total_failures=self._total_failures,
                session_id=self._current_session_id,
            )

            # Analyze for intrusion patterns
            intrusion_event = self._analyze_failure_patterns(
                factor, failure_reason, confidence_score, provider, current_time
            )

            # Perform advanced pattern analysis if enabled
            detected_patterns = []
            if self.config.enable_pattern_analysis:
                detected_patterns = self._pattern_analyzer.analyze_failure(
                    factor=factor,
                    failure_time=current_time,
                    confidence_score=confidence_score,
                    failure_reason=failure_reason,
                    session_id=self._current_session_id,
                )

                # Handle detected patterns
                for pattern in detected_patterns:
                    self._enforce_immediate_security_response_for_failure_pattern(pattern)

            if intrusion_event:
                self._handle_intrusion_event(intrusion_event)
                return intrusion_event

            return None

    def record_successful_verification(self, factor: BiometricFactor) -> None:
        """
        Record a successful biometric verification.

        This helps establish normal usage patterns and can reset certain
        failure counters based on configuration.

        Args:
            factor: The biometric factor that succeeded
        """
        with self._lock:
            logger.info(
                "Successful biometric verification recorded", factor=factor.value, session_id=self._current_session_id
            )

            # Optionally reset failure count for this factor on success
            # This implements a "forgiveness" policy for isolated failures
            if self._failure_counts[factor] > 0:
                logger.info(
                    "Resetting failure count for successful factor",
                    factor=factor.value,
                    previous_failures=self._failure_counts[factor],
                )
                self._failure_counts[factor] = 0

    def get_current_threat_level(self) -> IntrusionSeverity:
        """
        Get the current threat level based on recent activity.

        Returns:
            Current threat severity level
        """
        with self._lock:
            current_time = datetime.utcnow()

            # Count recent high-severity events
            recent_critical = sum(
                1
                for event in self._events
                if event.severity == IntrusionSeverity.CRITICAL
                and (current_time - event.timestamp).total_seconds() < 300
            )  # 5 minutes

            recent_high = sum(
                1
                for event in self._events
                if event.severity == IntrusionSeverity.HIGH and (current_time - event.timestamp).total_seconds() < 600
            )  # 10 minutes

            # Determine threat level
            if recent_critical > 0:
                return IntrusionSeverity.CRITICAL
            elif recent_high >= 2:
                return IntrusionSeverity.HIGH
            elif self._total_failures >= self.config.max_total_failures:
                return IntrusionSeverity.MEDIUM
            else:
                return IntrusionSeverity.LOW

    def get_failure_statistics(self) -> Dict[str, any]:
        """
        Get comprehensive failure statistics for monitoring.

        Returns:
            Dictionary with failure statistics and analysis
        """
        with self._lock:
            current_time = datetime.utcnow()

            # Calculate recent failure rates
            recent_failures_1min = sum(
                1 for timestamp in self._recent_attempts if (current_time - timestamp).total_seconds() <= 60
            )

            recent_failures_5min = sum(
                1 for timestamp in self._recent_attempts if (current_time - timestamp).total_seconds() <= 300
            )

            # Factor-specific statistics
            factor_stats = {}
            for factor, count in self._failure_counts.items():
                recent_factor_failures = sum(
                    1
                    for attempt in self._factor_failure_history[factor]
                    if (current_time - attempt["timestamp"]).total_seconds() <= 300
                )

                factor_stats[factor.value] = {
                    "total_failures": count,
                    "recent_failures_5min": recent_factor_failures,
                    "last_failure": max(
                        (attempt["timestamp"] for attempt in self._factor_failure_history[factor]), default=None
                    ),
                }

            # Get pattern analysis statistics
            pattern_stats = {}
            if self.config.enable_pattern_analysis:
                pattern_stats = self._pattern_analyzer.get_pattern_statistics()

            # Get security enforcer statistics
            security_enforcer_stats = {}
            if self.config.enable_security_enforcement:
                security_enforcer_stats = {
                    "lock_scope": self.security_enforcer.get_lock_scope(),
                    "capabilities": self.security_capabilities
                }

            return {
                "total_failures": self._total_failures,
                "recent_failures_1min": recent_failures_1min,
                "recent_failures_5min": recent_failures_5min,
                "factor_statistics": factor_stats,
                "threat_level": self.get_current_threat_level().value,
                "total_events": len(self._events),
                "last_failure_time": self._last_failure_time.isoformat() if self._last_failure_time else None,
                "monitoring_active": self._monitoring_active,
                "session_id": self._current_session_id,
                "pattern_analysis": pattern_stats,
                "security_enforcement": security_enforcer_stats,
            }

    def get_recent_events(self, limit: int = 10) -> List[IntrusionEvent]:
        """
        Get recent intrusion events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent intrusion events, most recent first
        """
        with self._lock:
            return list(reversed(self._events[-limit:]))

    def reset_failure_counters(self, factor: Optional[BiometricFactor] = None) -> None:
        """
        Reset failure counters (administrative function).

        Args:
            factor: Specific factor to reset, or None to reset all
        """
        with self._lock:
            if factor:
                old_count = self._failure_counts[factor]
                self._failure_counts[factor] = 0
                logger.info(
                    "Failure counter reset for factor",
                    factor=factor.value,
                    previous_count=old_count,
                    session_id=self._current_session_id,
                )
            else:
                old_total = self._total_failures
                self._failure_counts.clear()
                self._total_failures = 0
                self._recent_attempts.clear()
                self._factor_failure_history.clear()
                logger.info("All failure counters reset", previous_total=old_total, session_id=self._current_session_id)

    def _enforce_immediate_security_response_for_failure_pattern(self, pattern: FailurePattern) -> None:
        """Handle a detected failure pattern by triggering appropriate responses."""

        # Log the pattern with appropriate severity
        if pattern.severity == PatternSeverity.CRITICAL:
            logger.critical(
                "CRITICAL FAILURE PATTERN DETECTED",
                pattern_id=pattern.pattern_id,
                pattern_type=pattern.pattern_type.value,
                metadata=pattern.metadata,
            )
        elif pattern.severity == PatternSeverity.HIGH:
            logger.error(
                "HIGH SEVERITY FAILURE PATTERN DETECTED",
                pattern_id=pattern.pattern_id,
                pattern_type=pattern.pattern_type.value,
                metadata=pattern.metadata,
            )
        elif pattern.severity == PatternSeverity.MEDIUM:
            logger.warning(
                "MEDIUM SEVERITY FAILURE PATTERN DETECTED",
                pattern_id=pattern.pattern_id,
                pattern_type=pattern.pattern_type.value,
                metadata=pattern.metadata,
            )

        # Trigger pattern callbacks
        for callback in self._pattern_callbacks:
            try:
                callback(pattern)
            except Exception as e:
                logger.error(
                    "Error in pattern response callback",
                    callback=str(callback),
                    error=str(e),
                    pattern_id=pattern.pattern_id,
                )

        # Convert high-severity patterns to intrusion events
        if pattern.severity in [PatternSeverity.HIGH, PatternSeverity.CRITICAL]:
            intrusion_event = self._create_intrusion_event(
                IntrusionEventType.PATTERN_ANOMALY,
                IntrusionSeverity.HIGH if pattern.severity == PatternSeverity.HIGH else IntrusionSeverity.CRITICAL,
                list(pattern.affected_factors)[0] if pattern.affected_factors else None,
                pattern.failure_count,
                pattern.time_window.total_seconds(),
                {
                    "pattern_id": pattern.pattern_id,
                    "pattern_type": pattern.pattern_type.value,
                    "pattern_confidence": str(pattern.confidence_score),
                    **pattern.metadata,
                },
                pattern.detection_time,
            )

            self._handle_intrusion_event(intrusion_event)

    def get_recent_patterns(self, limit: int = 10) -> List[FailurePattern]:
        """
        Get recent failure patterns from the pattern analyzer.

        Args:
            limit: Maximum number of patterns to return

        Returns:
            List of recent patterns, most recent first
        """
        if self.config.enable_pattern_analysis:
            return self._pattern_analyzer.get_recent_patterns(limit)
        return []

    def trigger_emergency_session_lock(self, reason: str = "Manual emergency lock") -> bool:
        """
        Manually trigger emergency session lock using PAL SecurityEnforcer.

        Args:
            reason: Reason for emergency lock

        Returns:
            True if lock successful, False otherwise
        """
        if not self.config.enable_security_enforcement:
            logger.warning("Emergency lock requested but security enforcement disabled", reason=reason)
            return False

        logger.critical("MANUAL EMERGENCY LOCK TRIGGERED", reason=reason, session_id=self._current_session_id)

        try:
            # Use PAL SecurityEnforcer to lock session
            success = self.security_enforcer.lock_session(reason)

            logger.critical(
                "EMERGENCY LOCK EXECUTED",
                lock_result="success" if success else "failed",
                lock_scope=self.security_enforcer.get_lock_scope(),
                reason=reason,
            )

            return success

        except Exception as e:
            logger.critical("EMERGENCY LOCK FAILED", reason=reason, error=str(e), security_status="COMPROMISED")
            return False

    def get_security_enforcer_statistics(self) -> Dict[str, any]:
        """
        Get security enforcer statistics.

        Returns:
            Dictionary with security enforcer statistics
        """
        if self.config.enable_security_enforcement:
            return {
                "lock_scope": self.security_enforcer.get_lock_scope(),
                "capabilities": self.security_capabilities,
                "enforcement_enabled": True
            }
        return {"security_enforcement_disabled": True}

    def test_security_enforcer_capability(self) -> Dict[str, any]:
        """
        Test security enforcement capability without actually locking.

        Returns:
            Dictionary with capability test results
        """
        if self.config.enable_security_enforcement:
            return {
                "lock_scope": self.security_enforcer.get_lock_scope(),
                "capabilities": self.security_capabilities,
                "enforcement_enabled": True,
                "platform_support": True
            }
        return {"security_enforcement_disabled": True}

    def _analyze_failure_patterns(
        self, factor: BiometricFactor, failure_reason: str, confidence_score: float, provider: str, timestamp: datetime
    ) -> Optional[IntrusionEvent]:
        """
        Analyze failure patterns to detect intrusion attempts.
        
        CRITICAL SECURITY FIX: Check ALL conditions and return the most severe event,
        not return early. This prevents attackers from bypassing threshold limits
        by triggering other detection patterns.
        """
        detected_events = []
        
        # Check for rapid attempts FIRST - this is the most immediate threat
        rapid_window = timedelta(seconds=self.config.rapid_attempt_window_seconds)
        recent_attempts = [t for t in self._recent_attempts if timestamp - t <= rapid_window]

        if len(recent_attempts) >= self.config.max_failures_per_minute:
            detected_events.append(self._create_intrusion_event(
                IntrusionEventType.RAPID_ATTEMPTS,
                IntrusionSeverity.HIGH,
                factor,
                len(recent_attempts),
                self.config.rapid_attempt_window_seconds,
                {
                    "attempts_in_window": str(len(recent_attempts)),
                    "window_seconds": str(self.config.rapid_attempt_window_seconds),
                    "failure_reason": failure_reason,
                    "provider": provider,
                },
                timestamp,
            ))

        # Check for unusual timing patterns (only if timing analysis is enabled)
        if self.config.enable_timing_analysis and len(self._recent_attempts) >= 2:
            last_attempt = self._recent_attempts[-2]
            time_between = (timestamp - last_attempt).total_seconds()

            if time_between < self.config.unusual_timing_threshold_seconds:
                detected_events.append(self._create_intrusion_event(
                    IntrusionEventType.UNUSUAL_TIMING,
                    IntrusionSeverity.MEDIUM,
                    factor,
                    2,
                    time_between,
                    {
                        "time_between_attempts": str(time_between),
                        "threshold": str(self.config.unusual_timing_threshold_seconds),
                        "failure_reason": failure_reason,
                        "provider": provider,
                    },
                    timestamp,
                ))

        # Check for multiple factor failures
        failed_factors = [f for f, count in self._failure_counts.items() if count > 0]
        if len(failed_factors) >= self.config.multiple_factor_failure_threshold:
            detected_events.append(self._create_intrusion_event(
                IntrusionEventType.MULTIPLE_FACTORS_FAILED,
                IntrusionSeverity.HIGH,
                factor,
                len(failed_factors),
                0,
                {
                    "failed_factors": ",".join(f.value for f in failed_factors),
                    "threshold": str(self.config.multiple_factor_failure_threshold),
                    "failure_reason": failure_reason,
                    "provider": provider,
                },
                timestamp,
            ))

        # Check for threshold violations - CRITICAL SECURITY BOUNDARY
        if self._failure_counts[factor] >= self.config.max_failures_per_factor:
            detected_events.append(self._create_intrusion_event(
                IntrusionEventType.THRESHOLD_EXCEEDED,
                IntrusionSeverity.HIGH,
                factor,
                self._failure_counts[factor],
                0,
                {
                    "threshold_type": "per_factor",
                    "threshold_value": str(self.config.max_failures_per_factor),
                    "actual_value": str(self._failure_counts[factor]),
                    "failure_reason": failure_reason,
                    "provider": provider,
                },
                timestamp,
            ))

        if self._total_failures >= self.config.max_total_failures:
            detected_events.append(self._create_intrusion_event(
                IntrusionEventType.THRESHOLD_EXCEEDED,
                IntrusionSeverity.CRITICAL,
                factor,
                self._total_failures,
                0,
                {
                    "threshold_type": "total_failures",
                    "threshold_value": str(self.config.max_total_failures),
                    "actual_value": str(self._total_failures),
                    "failure_reason": failure_reason,
                    "provider": provider,
                },
                timestamp,
            ))

        # Return the most severe event (CRITICAL > HIGH > MEDIUM > LOW)
        if not detected_events:
            return None
            
        # Sort by severity (CRITICAL first, then HIGH, etc.)
        severity_order = {
            IntrusionSeverity.CRITICAL: 0,
            IntrusionSeverity.HIGH: 1,
            IntrusionSeverity.MEDIUM: 2,
            IntrusionSeverity.LOW: 3
        }
        
        most_severe_event = min(detected_events, key=lambda e: severity_order[e.severity])
        
        # Log all detected events for forensic analysis
        if len(detected_events) > 1:
            logger.warning(
                "Multiple intrusion patterns detected simultaneously",
                total_events=len(detected_events),
                most_severe=most_severe_event.event_type.value,
                all_events=[e.event_type.value for e in detected_events],
                session_id=self._current_session_id
            )
        
        return most_severe_event

    def _create_intrusion_event(
        self,
        event_type: IntrusionEventType,
        severity: IntrusionSeverity,
        source_factor: Optional[BiometricFactor],
        failure_count: int,
        time_window: float,
        metadata: Dict[str, str],
        timestamp: datetime,
    ) -> IntrusionEvent:
        """Create an intrusion event with proper logging."""

        event = IntrusionEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            severity=severity,
            timestamp=timestamp,
            source_factor=source_factor,
            failure_count=failure_count,
            time_window_seconds=time_window,
            metadata=metadata,
            session_id=self._current_session_id,
        )

        self._events.append(event)

        logger.warning(
            "Intrusion event detected",
            event_id=event.event_id,
            event_type=event_type.value,
            severity=severity.value,
            source_factor=source_factor.value if source_factor else None,
            failure_count=failure_count,
            time_window=time_window,
            metadata=metadata,
            session_id=self._current_session_id,
        )

        return event

    def _handle_intrusion_event(self, event: IntrusionEvent) -> None:
        """
        Handle an intrusion event by triggering appropriate responses via PAL SecurityEnforcer.
        
        This method analyzes intrusion events and triggers platform-agnostic security
        enforcement through the PAL SecurityEnforcer interface.
        """

        # Log the event with appropriate severity
        if event.severity == IntrusionSeverity.CRITICAL:
            logger.critical(
                "CRITICAL INTRUSION EVENT",
                event_id=event.event_id,
                event_type=event.event_type.value,
                metadata=event.metadata,
            )
        elif event.severity == IntrusionSeverity.HIGH:
            logger.error(
                "HIGH SEVERITY INTRUSION EVENT",
                event_id=event.event_id,
                event_type=event.event_type.value,
                metadata=event.metadata,
            )

        # Trigger security enforcement for high-severity events
        if self.config.enable_security_enforcement:
            should_lock = False
            lock_reason = None

            # Determine if session should be locked
            if event.severity == IntrusionSeverity.CRITICAL and self.config.lock_on_critical_events:
                should_lock = True
                lock_reason = f"Critical intrusion detected: {event.event_type.value}"
            elif event.severity == IntrusionSeverity.HIGH and self.config.lock_on_high_severity_events:
                should_lock = True
                lock_reason = f"High severity intrusion: {event.event_type.value}"
            elif (
                event.event_type == IntrusionEventType.MULTIPLE_FACTORS_FAILED and self.config.lock_on_multiple_failures
            ):
                should_lock = True
                lock_reason = "Multiple biometric factors failed"
            elif event.event_type == IntrusionEventType.RAPID_ATTEMPTS:
                should_lock = True
                lock_reason = "Rapid authentication attempts detected"

            # Execute session lock if required
            if should_lock and lock_reason:
                try:
                    logger.critical(
                        "TRIGGERING SESSION LOCK DUE TO INTRUSION",
                        intrusion_event_id=event.event_id,
                        lock_reason=lock_reason,
                        lock_scope=self.security_enforcer.get_lock_scope(),
                        immediate_action=True,
                    )

                    # Use PAL SecurityEnforcer to lock session
                    success = self.security_enforcer.lock_session(lock_reason)

                    logger.critical(
                        "SESSION LOCK EXECUTED",
                        intrusion_event_id=event.event_id,
                        lock_result="success" if success else "failed",
                        lock_scope=self.security_enforcer.get_lock_scope(),
                    )

                except Exception as e:
                    logger.critical(
                        "FAILED TO EXECUTE WORKSTATION LOCK",
                        intrusion_event_id=event.event_id,
                        error=str(e),
                        security_status="COMPROMISED",
                    )

        # Trigger response callbacks
        for callback in self._response_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(
                    "Error in intrusion response callback",
                    callback=str(callback),
                    error=str(e),
                    event_id=event.event_id,
                )

    def _monitor_patterns(self) -> None:
        """Background thread for continuous pattern monitoring."""
        while self._monitoring_active:
            try:
                with self._lock:
                    current_time = datetime.utcnow()

                    # Clean up old events
                    cutoff_time = current_time - timedelta(hours=self.config.retain_events_hours)
                    self._events = [event for event in self._events if event.timestamp > cutoff_time]

                    # Additional pattern analysis could go here
                    # For now, we rely on real-time analysis in record_biometric_failure

                # Sleep between monitoring cycles
                time.sleep(1.0)

            except Exception as e:
                logger.error("Error in pattern monitoring", error=str(e), session_id=self._current_session_id)
                time.sleep(5.0)  # Longer sleep on error


# Factory function for easy instantiation


def create_intrusion_detector(
    security_enforcer: Optional[SecurityEnforcer] = None,
    config: Optional[IntrusionDetectionConfig] = None
) -> IntrusionDetector:
    """
    Factory function to create an intrusion detector with PAL interface.

    Args:
        security_enforcer: Optional SecurityEnforcer (creates default if None)
        config: Optional configuration (uses defaults if None)

    Returns:
        Configured IntrusionDetector instance
    
    Note:
        If SecurityEnforcer interface is not provided, this function will attempt to
        create a platform-specific implementation automatically.
    """
    # If no PAL interface provided, create platform-specific one
    if security_enforcer is None:
        from pal.platform_detector import PlatformDetector
        from pal.backend_factory import PlatformBackendFactory
        
        # Detect platform
        platform = PlatformDetector.detect()
        factory = PlatformBackendFactory(platform)
        
        # Create PAL interface
        security_enforcer = factory.create_security_enforcer()
    
    return IntrusionDetector(security_enforcer, config)


# Export public interface
__all__ = [
    "IntrusionEventType",
    "IntrusionSeverity",
    "IntrusionEvent",
    "IntrusionDetectionConfig",
    "IntrusionDetectionError",
    "IntrusionDetector",
    "create_intrusion_detector",
]
