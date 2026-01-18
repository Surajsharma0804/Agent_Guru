"""
Component Failure Detection System

Implements sophisticated failure detection with classification, severity assessment,
and cascade failure prevention for all GURU core components.

This system provides:
- Real-time failure detection across all components
- Failure classification and severity assessment
- Cascade failure prevention through dependency analysis
- Immediate security response for critical failures
- Comprehensive audit logging of all failure events
- Recovery coordination and safe degradation management

Security Principles:
- Fail-safe, never fail-open
- Immediate authority revocation on critical failures
- No silent degradation of security boundaries
- Comprehensive audit trail of all failure events
"""

import logging
import threading
import time
import weakref
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Set

from .health_monitor import ComponentHealth, ComponentHealthMonitor, HealthStatus


class FailureType(Enum):
    """Types of component failures."""

    HEALTH_CHECK_TIMEOUT = "health_check_timeout"
    COMPONENT_UNRESPONSIVE = "component_unresponsive"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SECURITY_VIOLATION = "security_violation"
    INTEGRITY_VIOLATION = "integrity_violation"
    DEPENDENCY_FAILURE = "dependency_failure"
    CASCADE_FAILURE = "cascade_failure"
    RECOVERY_FAILURE = "recovery_failure"
    CONFIGURATION_ERROR = "configuration_error"
    EXTERNAL_DEPENDENCY_FAILURE = "external_dependency_failure"


class FailureSeverity(Enum):
    """Severity levels for component failures."""

    LOW = "low"  # Minor issues, system continues normally
    MEDIUM = "medium"  # Degraded performance, monitoring required
    HIGH = "high"  # Significant impact, immediate attention needed
    CRITICAL = "critical"  # System security compromised, immediate halt required
    FATAL = "fatal"  # Complete system failure, emergency shutdown


@dataclass(frozen=True)
class ComponentFailure:
    """Immutable record of a component failure."""

    component_name: str
    failure_type: FailureType
    severity: FailureSeverity
    timestamp: datetime
    error_message: str
    context: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    affected_components: List[str] = field(default_factory=list)
    recovery_actions: List[str] = field(default_factory=list)

    def is_critical(self) -> bool:
        """Check if this failure is critical and requires immediate halt."""
        return self.severity in [FailureSeverity.CRITICAL, FailureSeverity.FATAL]

    def requires_authority_revocation(self) -> bool:
        """Check if this failure requires immediate authority revocation."""
        return self.is_critical() or self.failure_type in [
            FailureType.SECURITY_VIOLATION,
            FailureType.INTEGRITY_VIOLATION,
            FailureType.CASCADE_FAILURE,
        ]


@dataclass
class FailureDetectionConfig:
    """Configuration for failure detection system."""

    detection_interval_seconds: float = 1.0
    max_consecutive_failures: int = 3
    cascade_detection_timeout_seconds: float = 10.0
    critical_component_timeout_seconds: float = 5.0
    recovery_attempt_timeout_seconds: float = 30.0
    enable_predictive_detection: bool = True
    enable_cascade_prevention: bool = True
    max_concurrent_detections: int = 10


class FailureDetectable(Protocol):
    """Protocol for components that can be monitored for failures."""

    def get_failure_indicators(self) -> Dict[str, Any]:
        """Get current failure indicators for the component."""
        ...

    def is_critical_component(self) -> bool:
        """Check if this component is critical for system security."""
        ...


class FailureDetector:
    """
    Comprehensive failure detection system for GURU components.

    Monitors all registered components for failures, classifies failures by
    severity, detects cascade failures, and coordinates immediate response
    for critical failures that compromise system security.
    """

    def __init__(
        self, config: Optional[FailureDetectionConfig] = None, health_monitor: Optional[ComponentHealthMonitor] = None
    ):
        self.config = config or FailureDetectionConfig()
        self.health_monitor = health_monitor or ComponentHealthMonitor()
        self.logger = logging.getLogger(__name__)

        # Component registry
        self._components: Dict[str, weakref.ReferenceType] = {}
        self._critical_components: Set[str] = set()
        self._component_dependencies: Dict[str, Set[str]] = {}

        # Failure tracking
        self._active_failures: Dict[str, ComponentFailure] = {}
        self._failure_history: List[ComponentFailure] = []
        self._consecutive_failures: Dict[str, int] = {}
        self._last_failure_time: Dict[str, datetime] = {}

        # Detection control
        self._detecting = False
        self._detection_thread: Optional[threading.Thread] = None
        self._detection_lock = threading.RLock()
        self._detection_executor = ThreadPoolExecutor(
            max_workers=self.config.max_concurrent_detections, thread_name_prefix="FailureDetector"
        )

        # Callbacks
        self._failure_callbacks: List[Callable[[ComponentFailure], None]] = []
        self._critical_failure_callbacks: List[Callable[[ComponentFailure], None]] = []
        self._cascade_failure_callbacks: List[Callable[[List[ComponentFailure]], None]] = []

        # Cascade detection
        self._cascade_detection_window: Dict[str, List[datetime]] = {}
        self._cascade_in_progress: Set[str] = set()

        # Performance tracking
        self._detection_performance: List[float] = []

    def register_component(
        self,
        name: str,
        component: FailureDetectable,
        is_critical: bool = False,
        dependencies: Optional[Set[str]] = None,
    ) -> None:
        """Register a component for failure detection."""
        with self._detection_lock:
            self._components[name] = weakref.ref(component)
            self._consecutive_failures[name] = 0
            self._cascade_detection_window[name] = []

            if is_critical:
                self._critical_components.add(name)

            if dependencies:
                self._component_dependencies[name] = dependencies

        self.logger.info(
            f"Registered component '{name}' for failure detection "
            f"(critical: {is_critical}, dependencies: {dependencies or 'none'})"
        )

    def unregister_component(self, name: str) -> None:
        """Unregister a component from failure detection."""
        with self._detection_lock:
            self._components.pop(name, None)
            self._critical_components.discard(name)
            self._component_dependencies.pop(name, None)
            self._active_failures.pop(name, None)
            self._consecutive_failures.pop(name, None)
            self._last_failure_time.pop(name, None)
            self._cascade_detection_window.pop(name, None)
            self._cascade_in_progress.discard(name)

        self.logger.info(f"Unregistered component '{name}' from failure detection")

    def add_failure_callback(self, callback: Callable[[ComponentFailure], None]) -> None:
        """Add callback for all component failures."""
        self._failure_callbacks.append(callback)

    def add_critical_failure_callback(self, callback: Callable[[ComponentFailure], None]) -> None:
        """Add callback for critical failures only."""
        self._critical_failure_callbacks.append(callback)

    def add_cascade_failure_callback(self, callback: Callable[[List[ComponentFailure]], None]) -> None:
        """Add callback for cascade failures."""
        self._cascade_failure_callbacks.append(callback)

    def start_detection(self) -> None:
        """Start failure detection for all registered components."""
        if self._detecting:
            return

        self._detecting = True
        self._detection_thread = threading.Thread(target=self._detection_loop, daemon=True, name="FailureDetector")
        self._detection_thread.start()

        # Start health monitoring if not already started
        self.health_monitor.start_monitoring()

        self.logger.info("Started component failure detection")

    def stop_detection(self) -> None:
        """Stop failure detection."""
        self._detecting = False
        if self._detection_thread and self._detection_thread.is_alive():
            self._detection_thread.join(timeout=5.0)

        self._detection_executor.shutdown(wait=True)
        self.health_monitor.stop_monitoring()

        self.logger.info("Stopped component failure detection")

    def _detection_loop(self) -> None:
        """Main failure detection loop."""
        while self._detecting:
            try:
                start_time = time.time()

                # Detect failures in all registered components
                self._detect_component_failures()

                # Analyze cascade failures
                if self.config.enable_cascade_prevention:
                    self._detect_cascade_failures()

                # Clean up old cascade detection windows
                self._cleanup_cascade_windows()

                # Record performance
                elapsed = time.time() - start_time
                self._detection_performance.append(elapsed)
                if len(self._detection_performance) > 100:
                    self._detection_performance = self._detection_performance[-100:]

                # Calculate sleep time
                sleep_time = max(0, self.config.detection_interval_seconds - elapsed)
                time.sleep(sleep_time)

            except Exception as e:
                self.logger.error(f"Error in failure detection loop: {e}")
                time.sleep(self.config.detection_interval_seconds)

    def _detect_component_failures(self) -> None:
        """Detect failures in all registered components."""
        with self._detection_lock:
            components_to_check = list(self._components.items())

        # Submit detection tasks to thread pool
        futures: Dict[str, Future] = {}
        for name, component_ref in components_to_check:
            future = self._detection_executor.submit(self._detect_single_component_failure, name, component_ref)
            futures[name] = future

        # Collect results
        for name, future in futures.items():
            try:
                failure = future.result(timeout=self.config.critical_component_timeout_seconds)
                if failure:
                    self._handle_detected_failure(failure)
            except Exception as e:
                self.logger.error(f"Error detecting failure in component '{name}': {e}")
                # Create a failure for the detection failure itself
                detection_failure = ComponentFailure(
                    component_name=name,
                    failure_type=FailureType.HEALTH_CHECK_TIMEOUT,
                    severity=FailureSeverity.HIGH,
                    timestamp=datetime.now(),
                    error_message=f"Failure detection error: {e}",
                    context={"detection_error": True},
                )
                self._handle_detected_failure(detection_failure)

    def _detect_single_component_failure(
        self, name: str, component_ref: weakref.ReferenceType
    ) -> Optional[ComponentFailure]:
        """
        PRODUCTION-GRADE SECURITY-FIRST FAILURE DETECTION

        This method implements the corrected security-first failure detection logic
        where security and integrity violations are detected with absolute priority
        before any other failure analysis.

        CRITICAL SECURITY FLOW:
        1. Get component failure indicators
        2. IMMEDIATELY analyze for security/integrity violations with absolute priority
        3. Only if no security violations, check health monitor
        4. Only if no health failures, analyze other failure types

        This ensures security violations can NEVER be masked by other failure types.
        """
        self.logger.debug(f"_detect_single_component_failure called for {name}")
        try:
            component = component_ref()
            if component is None:
                # Component has been garbage collected
                self.unregister_component(name)
                return None

            # Get failure indicators from component
            indicators = component.get_failure_indicators()
            self.logger.debug(f"Component {name} indicators: {indicators}")

            # SECURITY-FIRST ANALYSIS - ABSOLUTE PRIORITY
            # This call handles ALL failure analysis with security-first logic
            failure = self._analyze_failure_indicators(name, indicators, component)
            if failure:
                self.logger.debug(f"Failure analysis result: {failure.failure_type.value} ({failure.severity.value})")
                return failure

            # If no failure detected from indicators, check health monitor as fallback
            health = self.health_monitor.get_component_health(name)
            self.logger.debug(f"Health monitor status for {name}: {health.status if health else 'None'}")
            if health and health.status in [HealthStatus.FAILED, HealthStatus.CRITICAL]:
                self.logger.debug(f"Health monitor detected failure in {name}: {health.status}")
                return self._create_failure_from_health(name, health)

            # No failure detected
            return None

        except Exception as e:
            self.logger.error(f"Exception in _detect_single_component_failure for {name}: {e}")
            return ComponentFailure(
                component_name=name,
                failure_type=FailureType.COMPONENT_UNRESPONSIVE,
                severity=FailureSeverity.HIGH,
                timestamp=datetime.now(),
                error_message=f"Component failure detection error: {e}",
                context={"exception": str(e)},
            )

    def _create_failure_from_health(self, name: str, health: ComponentHealth) -> ComponentFailure:
        """Create a failure record from health status."""
        severity = FailureSeverity.HIGH
        if health.status == HealthStatus.CRITICAL:
            severity = FailureSeverity.CRITICAL
        elif health.status == HealthStatus.FAILED:
            severity = FailureSeverity.FATAL

        failure_type = FailureType.COMPONENT_UNRESPONSIVE
        if health.metrics.response_time_ms > 5000:
            failure_type = FailureType.HEALTH_CHECK_TIMEOUT
        elif health.metrics.cpu_usage_percent > 90 or health.metrics.memory_usage_mb > 1000:
            failure_type = FailureType.RESOURCE_EXHAUSTION

        return ComponentFailure(
            component_name=name,
            failure_type=failure_type,
            severity=severity,
            timestamp=datetime.now(),
            error_message=f"Health monitor detected failure: {', '.join(health.issues)}",
            context={
                "health_score": health.health_score,
                "consecutive_failures": health.consecutive_failures,
                "error_count": health.error_count,
                "metrics": {
                    "cpu_percent": health.metrics.cpu_usage_percent,
                    "memory_mb": health.metrics.memory_usage_mb,
                    "response_time_ms": health.metrics.response_time_ms,
                    "error_rate_percent": health.metrics.error_rate_percent,
                },
            },
        )

    def _analyze_failure_indicators(
        self, name: str, indicators: Dict[str, Any], component: FailureDetectable
    ) -> Optional[ComponentFailure]:
        """
        SECURITY-FIRST FAILURE ANALYSIS - PRODUCTION IMPLEMENTATION

        This method implements the corrected logic where security and integrity
        violations are checked with absolute priority before any other failure types.

        CRITICAL SECURITY FLOW:
        1. Security violations - HIGHEST PRIORITY
        2. Integrity violations - SECOND HIGHEST PRIORITY
        3. All other failure types - LOWER PRIORITY

        This ensures that security violations can NEVER be masked by other failures.
        """
        self.logger.debug(f"_analyze_failure_indicators called for {name}: {indicators}")

        # PRIORITY 1: SECURITY VIOLATIONS (ABSOLUTE HIGHEST PRIORITY)
        if indicators.get("security_violation", False):
            self.logger.critical(f"SECURITY VIOLATION DETECTED in {name}")
            return ComponentFailure(
                component_name=name,
                failure_type=FailureType.SECURITY_VIOLATION,
                severity=FailureSeverity.CRITICAL,
                timestamp=datetime.now(),
                error_message=indicators.get("security_message", "Security violation detected"),
                context=indicators,
            )

        # PRIORITY 2: INTEGRITY VIOLATIONS (SECOND HIGHEST PRIORITY)
        if indicators.get("integrity_violation", False):
            self.logger.critical(f"INTEGRITY VIOLATION DETECTED in {name}")
            return ComponentFailure(
                component_name=name,
                failure_type=FailureType.INTEGRITY_VIOLATION,
                severity=FailureSeverity.CRITICAL,
                timestamp=datetime.now(),
                error_message=indicators.get("integrity_message", "Data integrity violation detected"),
                context=indicators,
            )

        # PRIORITY 3: RESOURCE EXHAUSTION (HIGH PRIORITY)
        cpu_usage = indicators.get("cpu_usage_percent", 0)
        memory_usage = indicators.get("memory_usage_mb", 0)
        if cpu_usage > 95 or memory_usage > 2000:
            return ComponentFailure(
                component_name=name,
                failure_type=FailureType.RESOURCE_EXHAUSTION,
                severity=FailureSeverity.HIGH,
                timestamp=datetime.now(),
                error_message=f"Resource exhaustion: CPU {cpu_usage}%, Memory {memory_usage}MB",
                context=indicators,
            )

        # PRIORITY 4: GENERAL FAILURE INDICATORS (LOWER PRIORITY)
        if indicators.get("failed", False):
            self.logger.debug(f"General failure detected in {name}")
            error_message = indicators.get("error_message", "Component reported failure")
            failure_type = self._determine_failure_type(indicators)
            severity = self._determine_failure_severity(name, failure_type, component)

            return ComponentFailure(
                component_name=name,
                failure_type=failure_type,
                severity=severity,
                timestamp=datetime.now(),
                error_message=error_message,
                context=indicators,
                stack_trace=indicators.get("stack_trace"),
            )

        return None

    def _determine_failure_type(self, indicators: Dict[str, Any]) -> FailureType:
        """Determine the type of failure from indicators."""
        failure_type_str = indicators.get("failure_type", "").lower()

        # Security and integrity violations should never reach this method
        # due to the security-first analysis, but double-check for safety
        if "security" in failure_type_str:
            self.logger.warning("Security violation reached _determine_failure_type - this should not happen")
            return FailureType.SECURITY_VIOLATION

        if "integrity" in failure_type_str:
            self.logger.warning("Integrity violation reached _determine_failure_type - this should not happen")
            return FailureType.INTEGRITY_VIOLATION

        type_mapping = {
            "timeout": FailureType.HEALTH_CHECK_TIMEOUT,
            "unresponsive": FailureType.COMPONENT_UNRESPONSIVE,
            "resource": FailureType.RESOURCE_EXHAUSTION,
            "dependency": FailureType.DEPENDENCY_FAILURE,
            "cascade": FailureType.CASCADE_FAILURE,
            "recovery": FailureType.RECOVERY_FAILURE,
            "config": FailureType.CONFIGURATION_ERROR,
            "external": FailureType.EXTERNAL_DEPENDENCY_FAILURE,
        }

        for key, failure_type in type_mapping.items():
            if key in failure_type_str:
                return failure_type

        return FailureType.COMPONENT_UNRESPONSIVE

    def _determine_failure_severity(
        self, name: str, failure_type: FailureType, component: FailureDetectable
    ) -> FailureSeverity:
        """Determine the severity of a failure."""
        # Critical components always get higher severity
        if name in self._critical_components or component.is_critical_component():
            if failure_type in [FailureType.SECURITY_VIOLATION, FailureType.INTEGRITY_VIOLATION]:
                return FailureSeverity.FATAL
            else:
                return FailureSeverity.CRITICAL

        # Security and integrity violations are always critical
        if failure_type in [FailureType.SECURITY_VIOLATION, FailureType.INTEGRITY_VIOLATION]:
            return FailureSeverity.CRITICAL

        # Cascade failures are high severity
        if failure_type == FailureType.CASCADE_FAILURE:
            return FailureSeverity.HIGH

        # Check consecutive failures
        consecutive = self._consecutive_failures.get(name, 0)
        if consecutive >= self.config.max_consecutive_failures:
            return FailureSeverity.HIGH

        # Default severity based on failure type
        severity_mapping = {
            FailureType.HEALTH_CHECK_TIMEOUT: FailureSeverity.MEDIUM,
            FailureType.COMPONENT_UNRESPONSIVE: FailureSeverity.HIGH,
            FailureType.RESOURCE_EXHAUSTION: FailureSeverity.HIGH,
            FailureType.DEPENDENCY_FAILURE: FailureSeverity.MEDIUM,
            FailureType.RECOVERY_FAILURE: FailureSeverity.HIGH,
            FailureType.CONFIGURATION_ERROR: FailureSeverity.LOW,
            FailureType.EXTERNAL_DEPENDENCY_FAILURE: FailureSeverity.MEDIUM,
        }

        return severity_mapping.get(failure_type, FailureSeverity.MEDIUM)

    def _handle_detected_failure(self, failure: ComponentFailure) -> None:
        """Handle a detected component failure."""
        with self._detection_lock:
            # Update failure tracking
            self._active_failures[failure.component_name] = failure
            self._failure_history.append(failure)
            self._consecutive_failures[failure.component_name] = (
                self._consecutive_failures.get(failure.component_name, 0) + 1
            )
            self._last_failure_time[failure.component_name] = failure.timestamp

            # Add to cascade detection window
            self._cascade_detection_window[failure.component_name].append(failure.timestamp)

            # Keep history manageable
            if len(self._failure_history) > 1000:
                self._failure_history = self._failure_history[-1000:]

        self.logger.error(
            f"Component failure detected: {failure.component_name} - "
            f"{failure.failure_type.value} ({failure.severity.value}): "
            f"{failure.error_message}"
        )

        # Notify callbacks
        self._notify_failure_callbacks(failure)

        # Handle critical failures immediately
        if failure.is_critical():
            self._handle_critical_failure(failure)

    def _handle_critical_failure(self, failure: ComponentFailure) -> None:
        """Handle critical failures that require immediate response."""
        self.logger.critical(f"CRITICAL FAILURE DETECTED: {failure.component_name} - " f"{failure.error_message}")

        # Notify critical failure callbacks
        for callback in self._critical_failure_callbacks:
            try:
                callback(failure)
            except Exception as e:
                self.logger.error(f"Error in critical failure callback: {e}")

        # If this is a security or integrity violation, trigger immediate system halt
        if failure.failure_type in [FailureType.SECURITY_VIOLATION, FailureType.INTEGRITY_VIOLATION]:
            self._trigger_emergency_halt(failure)

    def _trigger_emergency_halt(self, failure: ComponentFailure) -> None:
        """Trigger emergency system halt for security violations."""
        self.logger.critical(f"EMERGENCY HALT TRIGGERED: {failure.error_message}")

        # This would integrate with the authority system to immediately revoke all authority
        # and halt all automation. For now, we log the critical event.
        try:
            # Import here to avoid circular dependencies
            from ..authority.authority_state_machine import AuthorityStateMachine, RevocationReason
            
            # Get the authority state machine and trigger emergency halt
            # This integrates with the dependency injection system
            authority_machine = AuthorityStateMachine.get_instance()
            if authority_machine:
                authority_machine.revoke_authority(
                    reason=RevocationReason.SYSTEM_FAILURE,
                    metadata={"cascade_failure_count": len(self.cascade_failures)}
                )
                self.logger.critical("Emergency authority revocation triggered due to cascade failures")
            else:
                self.logger.error("Authority state machine not available for emergency halt")
                
        except ImportError as e:
            self.logger.warning(f"Authority system not available for emergency halt: {e}")

    def _detect_cascade_failures(self) -> None:
        """Detect cascade failures across components."""
        if not self.config.enable_cascade_prevention:
            return

        current_time = datetime.now()
        cascade_threshold = timedelta(seconds=self.config.cascade_detection_timeout_seconds)

        # Find components with multiple recent failures
        cascade_candidates = []

        with self._detection_lock:
            for component_name, failure_times in self._cascade_detection_window.items():
                # Filter to recent failures only
                recent_failures = [t for t in failure_times if current_time - t <= cascade_threshold]

                # Update the window
                self._cascade_detection_window[component_name] = recent_failures

                # Check for cascade pattern
                if len(recent_failures) >= 2:
                    cascade_candidates.append(component_name)

        # Analyze cascade patterns
        if len(cascade_candidates) >= 2:
            self._analyze_cascade_pattern(cascade_candidates)

    def _analyze_cascade_pattern(self, candidates: List[str]) -> None:
        """Analyze potential cascade failure pattern."""
        # Check if these components are related through dependencies
        related_components = set()

        for component in candidates:
            dependencies = self._component_dependencies.get(component, set())
            related_components.update(dependencies)

            # Also check reverse dependencies
            for other_component, other_deps in self._component_dependencies.items():
                if component in other_deps:
                    related_components.add(other_component)

        # If we have related components failing together, it's likely a cascade
        cascade_components = [c for c in candidates if c in related_components]

        if len(cascade_components) >= 2:
            self._handle_cascade_failure(cascade_components)

    def _handle_cascade_failure(self, components: List[str]) -> None:
        """Handle detected cascade failure."""
        self.logger.critical(f"CASCADE FAILURE DETECTED: {', '.join(components)}")

        # Create cascade failure records
        cascade_failures = []
        for component in components:
            active_failure = self._active_failures.get(component)
            if active_failure:
                # Create a new failure record indicating cascade
                cascade_failure = ComponentFailure(
                    component_name=component,
                    failure_type=FailureType.CASCADE_FAILURE,
                    severity=FailureSeverity.HIGH,
                    timestamp=datetime.now(),
                    error_message=f"Component failed as part of cascade: {active_failure.error_message}",
                    context=active_failure.context,
                    affected_components=components,
                )
                cascade_failures.append(cascade_failure)

        # Notify cascade failure callbacks
        for callback in self._cascade_failure_callbacks:
            try:
                callback(cascade_failures)
            except Exception as e:
                self.logger.error(f"Error in cascade failure callback: {e}")

        # Mark components as in cascade to prevent further cascade detection
        with self._detection_lock:
            self._cascade_in_progress.update(components)

    def _cleanup_cascade_windows(self) -> None:
        """Clean up old entries from cascade detection windows."""
        current_time = datetime.now()
        cleanup_threshold = timedelta(seconds=self.config.cascade_detection_timeout_seconds * 2)

        with self._detection_lock:
            for component_name in list(self._cascade_detection_window.keys()):
                # Remove old failure times
                self._cascade_detection_window[component_name] = [
                    t for t in self._cascade_detection_window[component_name] if current_time - t <= cleanup_threshold
                ]

    def _notify_failure_callbacks(self, failure: ComponentFailure) -> None:
        """Notify all failure callbacks."""
        for callback in self._failure_callbacks:
            try:
                callback(failure)
            except Exception as e:
                self.logger.error(f"Error in failure callback: {e}")

    # Public API methods

    def get_active_failures(self) -> Dict[str, ComponentFailure]:
        """Get all currently active failures."""
        with self._detection_lock:
            return self._active_failures.copy()

    def get_failure_history(self, limit: Optional[int] = None) -> List[ComponentFailure]:
        """Get failure history."""
        with self._detection_lock:
            if limit:
                return self._failure_history[-limit:]
            return self._failure_history.copy()

    def get_component_failure_count(self, component_name: str) -> int:
        """Get failure count for a specific component."""
        with self._detection_lock:
            return self._consecutive_failures.get(component_name, 0)

    def clear_component_failures(self, component_name: str) -> None:
        """Clear failure tracking for a component (after successful recovery)."""
        with self._detection_lock:
            self._active_failures.pop(component_name, None)
            self._consecutive_failures[component_name] = 0
            self._cascade_in_progress.discard(component_name)
            self._cascade_detection_window[component_name] = []

        self.logger.info(f"Cleared failure tracking for component '{component_name}'")

    def is_system_failing(self) -> bool:
        """Check if the system has critical failures."""
        with self._detection_lock:
            return any(failure.is_critical() for failure in self._active_failures.values())

    def get_critical_failures(self) -> List[ComponentFailure]:
        """Get all critical failures."""
        with self._detection_lock:
            return [failure for failure in self._active_failures.values() if failure.is_critical()]

    def get_detection_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics for failure detection."""
        if not self._detection_performance:
            return {}

        return {
            "avg_detection_time_ms": sum(self._detection_performance) / len(self._detection_performance) * 1000,
            "max_detection_time_ms": max(self._detection_performance) * 1000,
            "min_detection_time_ms": min(self._detection_performance) * 1000,
            "total_detections": len(self._detection_performance),
        }

    def get_failure_tracking(self, component_name: str) -> Dict[str, Any]:
        """Get failure tracking information for a component."""
        with self._detection_lock:
            return {
                "component_name": component_name,
                "consecutive_failures": self._consecutive_failures.get(component_name, 0),
                "last_failure_time": self._last_failure_time.get(component_name),
                "active_failure": self._active_failures.get(component_name),
                "is_in_cascade": component_name in self._cascade_in_progress,
                "recent_failure_count": len(self._cascade_detection_window.get(component_name, [])),
            }
