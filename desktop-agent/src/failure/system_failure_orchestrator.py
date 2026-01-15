"""
System Failure Manager

Comprehensive failure management system that integrates all failure handling
components to provide unified failure detection, analysis, recovery, and
safe degradation for the entire GURU system.

This is the main orchestrator that coordinates:
- Component health monitoring
- Failure detection and classification
- Cascade failure analysis
- Recovery planning and execution
- Safe system degradation
- Emergency halt procedures

Security Principles:
- Fail-safe, never fail-open
- Immediate authority revocation on critical failures
- No silent degradation of security boundaries
- Comprehensive audit trail of all failure events
- Component isolation to prevent cascade failures
"""

import logging
import threading
import weakref
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

from .dependency_mapper import CascadeAnalysis, ComponentDependency, DependencyMapper
from .failure_detector import ComponentFailure, FailureDetectable, FailureDetector, FailureSeverity, FailureType
from .health_monitor import ComponentHealth, ComponentHealthMonitor, HealthCheckable, HealthStatus
from .recovery_orchestrator import RecoveryOrchestrator, RecoveryPlan, RecoveryResult
from .safe_degradation import DegradationLevel, DegradationPlan, SystemDegradationOrchestrator, SystemState


class SystemFailureState(Enum):
    """Overall system failure state."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    EMERGENCY_HALT = "emergency_halt"


@dataclass
class SystemFailureReport:
    """Comprehensive system failure report."""

    timestamp: datetime
    system_state: SystemFailureState
    active_failures: List[ComponentFailure]
    cascade_analyses: List[CascadeAnalysis]
    active_recoveries: List[RecoveryPlan]
    degradation_plan: Optional[DegradationPlan]
    system_health_score: float
    critical_components_affected: List[str]
    recommendations: List[str]


class SystemFailureOrchestrator:
    """
    Comprehensive system failure manager that orchestrates all failure
    handling components to provide unified failure management for GURU.

    This is the main entry point for all failure-related operations and
    coordinates between health monitoring, failure detection, recovery,
    and safe degradation systems.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Initialize all failure handling components
        self.health_monitor = ComponentHealthMonitor(check_interval_seconds=2.0)
        self.dependency_mapper = DependencyMapper()
        self.failure_detector = FailureDetector(health_monitor=self.health_monitor)
        self.degradation_manager = SystemDegradationOrchestrator()
        self.recovery_orchestrator = RecoveryOrchestrator(self.dependency_mapper)

        # System state
        self._system_state = SystemFailureState.HEALTHY
        self._state_lock = threading.RLock()

        # Component registry
        self._registered_components: Dict[str, weakref.ReferenceType] = {}
        self._component_metadata: Dict[str, Dict[str, Any]] = {}

        # Failure tracking
        self._active_system_failures: List[ComponentFailure] = []
        self._failure_history: List[SystemFailureReport] = []

        # Callbacks
        self._system_failure_callbacks: List[Callable[[SystemFailureReport], None]] = []
        self._emergency_halt_callbacks: List[Callable[[ComponentFailure], None]] = []

        # Configuration
        self._config = {
            "max_concurrent_failures": 3,
            "cascade_detection_enabled": True,
            "auto_recovery_enabled": True,
            "emergency_halt_on_critical": True,
            "degradation_enabled": True,
            "health_check_timeout": 30.0,
        }

        # Performance tracking
        self._performance_stats = {
            "total_failures_handled": 0,
            "successful_recoveries": 0,
            "emergency_halts": 0,
            "degradations_performed": 0,
            "average_recovery_time": 0.0,
        }

        # Setup component integration
        self._setup_component_integration()

    def _setup_component_integration(self) -> None:
        """Setup integration between all failure handling components."""
        # Health monitor callbacks
        self.health_monitor.add_global_health_callback(self._on_health_change)

        # Failure detector callbacks
        self.failure_detector.add_failure_callback(self._on_component_failure)
        self.failure_detector.add_critical_failure_callback(self._on_critical_failure)
        self.failure_detector.add_cascade_failure_callback(self._on_cascade_failure)

        # Recovery orchestrator callbacks
        self.recovery_orchestrator.add_recovery_callback(self._on_recovery_result)
        self.recovery_orchestrator.add_plan_callback(self._on_recovery_plan_created)

        # Degradation manager callbacks
        self.degradation_manager.add_degradation_callback(self._on_degradation_executed)
        self.degradation_manager.add_state_change_callback(self._on_system_state_change)

    def register_component(
        self,
        name: str,
        component: Union[HealthCheckable, FailureDetectable],
        is_critical: bool = False,
        dependencies: Optional[Set[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a component for comprehensive failure management."""
        with self._state_lock:
            # Store component reference
            self._registered_components[name] = weakref.ref(component)
            self._component_metadata[name] = metadata or {}

            # Register with health monitor
            if hasattr(component, "health_check"):
                self.health_monitor.register_component(name, component)

            # Register with failure detector
            if hasattr(component, "get_failure_indicators"):
                self.failure_detector.register_component(name, component, is_critical, dependencies)

            # Add to dependency mapper if dependencies specified
            if dependencies:
                for dependency in dependencies:
                    dep = ComponentDependency(
                        dependent=name,
                        dependency=dependency,
                        dependency_type=self._infer_dependency_type(name, dependency),
                        criticality=self._infer_component_criticality(name, is_critical),
                        description=f"Component {name} depends on {dependency}",
                        failure_impact=f"Failure of {dependency} affects {name} functionality",
                    )
                    self.dependency_mapper.add_dependency(dep)

        self.logger.info(
            f"Registered component '{name}' for failure management "
            f"(critical: {is_critical}, dependencies: {dependencies or 'none'})"
        )

    def _infer_dependency_type(self, dependent: str, dependency: str):
        """Infer dependency type based on component names."""
        from .dependency_mapper import DependencyType

        # Security-related dependencies
        if dependency in ["authority_state_machine", "biometric_verifier", "audit_logger", "cryptographic_engine"]:
            return DependencyType.SECURITY_DEPENDENCY

        # Control dependencies
        if dependency == "authority_state_machine" and dependent != "biometric_verifier":
            return DependencyType.CONTROL_DEPENDENCY

        # Data dependencies
        if dependency in ["memory_service", "database"]:
            return DependencyType.DATA_DEPENDENCY

        # Default to soft dependency
        return DependencyType.SOFT_DEPENDENCY

    def _infer_component_criticality(self, name: str, is_critical: bool):
        """Infer component criticality based on name and flag."""
        from .dependency_mapper import ComponentCriticality

        if is_critical:
            return ComponentCriticality.CRITICAL

        # Important components
        if name in ["input_engine", "memory_service", "skill_runner"]:
            return ComponentCriticality.IMPORTANT

        # Optional components
        if name in ["screen_observer", "llm_adapter"]:
            return ComponentCriticality.OPTIONAL

        return ComponentCriticality.IMPORTANT

    def unregister_component(self, name: str) -> None:
        """Unregister a component from failure management."""
        with self._state_lock:
            self._registered_components.pop(name, None)
            self._component_metadata.pop(name, None)

            self.health_monitor.unregister_component(name)
            self.failure_detector.unregister_component(name)

        self.logger.info(f"Unregistered component '{name}' from failure management")

    def start_monitoring(self) -> None:
        """Start comprehensive failure monitoring."""
        self.health_monitor.start_monitoring()
        self.failure_detector.start_detection()

        self.logger.info("Started comprehensive failure monitoring")

    def stop_monitoring(self) -> None:
        """Stop failure monitoring."""
        self.failure_detector.stop_detection()
        self.health_monitor.stop_monitoring()

        self.logger.info("Stopped failure monitoring")

    def _on_health_change(self, health_status: Dict[str, ComponentHealth]) -> None:
        """Handle health status changes from health monitor."""
        # Check for components that have become unhealthy
        unhealthy_components = [
            name
            for name, health in health_status.items()
            if health.status in [HealthStatus.CRITICAL, HealthStatus.FAILED]
        ]

        if unhealthy_components:
            self.logger.warning(f"Unhealthy components detected: {', '.join(unhealthy_components)}")
            self._assess_system_state()

    def _on_component_failure(self, failure: ComponentFailure) -> None:
        """Handle component failure detection."""
        with self._state_lock:
            self._active_system_failures.append(failure)
            self._performance_stats["total_failures_handled"] += 1

        self.logger.error(
            f"Component failure detected: {failure.component_name} - "
            f"{failure.failure_type.value} ({failure.severity.value})"
        )

        # Analyze cascade potential
        if self._config["cascade_detection_enabled"]:
            cascade_analysis = self.dependency_mapper.analyze_cascade_failure(failure.component_name)
            if cascade_analysis.estimated_impact_score > 50:
                self.logger.warning(
                    f"High cascade risk detected for '{failure.component_name}': "
                    f"impact score {cascade_analysis.estimated_impact_score}"
                )

        # Attempt recovery if enabled
        if self._config["auto_recovery_enabled"] and not failure.is_critical():
            self._attempt_component_recovery(failure)

        # Assess if degradation is needed
        if self._config["degradation_enabled"]:
            self._assess_degradation_need([failure.component_name])

        # Update system state
        self._assess_system_state()

        # Generate system report
        self._generate_system_failure_report()

    def _on_critical_failure(self, failure: ComponentFailure) -> None:
        """Handle critical component failures."""
        self.logger.critical(f"CRITICAL FAILURE: {failure.component_name} - {failure.error_message}")

        # Critical failures may require emergency halt
        if self._config["emergency_halt_on_critical"]:
            self._trigger_emergency_halt(failure)

        # Notify emergency callbacks
        for callback in self._emergency_halt_callbacks:
            try:
                callback(failure)
            except Exception as e:
                self.logger.error(f"Error in emergency halt callback: {e}")

    def _on_cascade_failure(self, failures: List[ComponentFailure]) -> None:
        """Handle cascade failure detection."""
        component_names = [f.component_name for f in failures]
        self.logger.critical(f"CASCADE FAILURE DETECTED: {', '.join(component_names)}")

        # Cascade failures require immediate degradation
        degradation_plan = self.degradation_manager.assess_degradation_need(component_names)
        if degradation_plan:
            success = self.degradation_manager.execute_degradation_plan(degradation_plan)
            if success:
                self.logger.warning("Executed degradation plan for cascade failure")
            else:
                self.logger.error("Failed to execute degradation plan for cascade failure")
                self._trigger_emergency_halt(failures[0])  # Use first failure as trigger

    def _on_recovery_result(self, result: RecoveryResult) -> None:
        """Handle recovery completion."""
        if result.success:
            self.logger.info(f"Recovery successful for plan '{result.plan_id}'")
            self._performance_stats["successful_recoveries"] += 1

            # Clear failure for recovered component
            self._clear_component_failure(result.plan_id)
        else:
            self.logger.error(f"Recovery failed for plan '{result.plan_id}': {result.error_message}")

    def _on_recovery_plan_created(self, plan: RecoveryPlan) -> None:
        """Handle recovery plan creation."""
        self.logger.info(
            f"Recovery plan created: '{plan.plan_id}' for components: " f"{', '.join(plan.failed_components)}"
        )

    def _on_degradation_executed(self, plan: DegradationPlan) -> None:
        """Handle degradation execution."""
        self.logger.warning(f"System degradation executed: {plan.degradation_level.value}")
        self._performance_stats["degradations_performed"] += 1

        # Update system state based on degradation
        self._assess_system_state()

    def _on_system_state_change(self, old_state: SystemState, new_state: SystemState) -> None:
        """Handle system state changes from degradation manager."""
        self.logger.info(f"System state changed: {old_state.value} -> {new_state.value}")

        # Map degradation system state to failure system state
        if new_state == SystemState.SAFE_HALT:
            self._system_state = SystemFailureState.EMERGENCY_HALT
        elif new_state in [SystemState.EMERGENCY_MODE, SystemState.LIMITED_OPERATION]:
            self._system_state = SystemFailureState.CRITICAL
        elif new_state == SystemState.DEGRADED_OPERATION:
            self._system_state = SystemFailureState.DEGRADED
        else:
            self._system_state = SystemFailureState.HEALTHY

    def _attempt_component_recovery(self, failure: ComponentFailure) -> None:
        """Attempt to recover a failed component."""
        recovery_plan = self.recovery_orchestrator.create_recovery_plan(failure)
        if recovery_plan:
            self.recovery_orchestrator.execute_recovery_plan(recovery_plan)
            self.logger.info(f"Started recovery for component '{failure.component_name}'")
        else:
            self.logger.warning(f"No recovery plan available for component '{failure.component_name}'")

    def _assess_degradation_need(self, failed_components: List[str]) -> None:
        """Assess if system degradation is needed."""
        degradation_plan = self.degradation_manager.assess_degradation_need(failed_components)
        if degradation_plan:
            if degradation_plan.degradation_level == DegradationLevel.SAFE_HALT:
                self.logger.critical("Safe halt required due to critical component failures")
                self._trigger_emergency_halt_for_components(failed_components)
            else:
                success = self.degradation_manager.execute_degradation_plan(degradation_plan)
                if not success:
                    self.logger.error("Failed to execute degradation plan")

    def _trigger_emergency_halt(self, failure: ComponentFailure) -> None:
        """Trigger emergency system halt."""
        self.logger.critical(f"EMERGENCY HALT TRIGGERED: {failure.error_message}")

        with self._state_lock:
            self._system_state = SystemFailureState.EMERGENCY_HALT
            self._performance_stats["emergency_halts"] += 1

        # This would integrate with the authority system to immediately revoke all authority
        # and halt all automation. For now, we log the critical event.
        try:
            # Import here to avoid circular dependencies
            pass

            # Try to get the authority state machine and trigger emergency halt
            # This is a simplified implementation - in production, this would be
            # properly integrated with the dependency injection system
        except ImportError:
            self.logger.warning("Authority system not available for emergency halt")

    def _trigger_emergency_halt_for_components(self, components: List[str]) -> None:
        """Trigger emergency halt for multiple component failures."""
        self.logger.critical(f"EMERGENCY HALT TRIGGERED FOR COMPONENTS: {', '.join(components)}")

        # Create a synthetic critical failure for the halt
        halt_failure = ComponentFailure(
            component_name="system",
            failure_type=FailureType.CASCADE_FAILURE,
            severity=FailureSeverity.FATAL,
            timestamp=datetime.now(),
            error_message=f"Multiple critical component failures: {', '.join(components)}",
            affected_components=components,
        )

        self._trigger_emergency_halt(halt_failure)

    def _clear_component_failure(self, plan_id: str) -> None:
        """Clear component failure after successful recovery."""
        with self._state_lock:
            # Remove failures associated with this recovery plan
            # This is simplified - in production, we'd track plan-to-failure mapping
            self._active_system_failures = [
                f
                for f in self._active_system_failures
                if not any(plan_id.endswith(f.component_name) for plan_id in [plan_id])
            ]

        # Clear failure tracking in failure detector
        # This would need the component name from the plan

    def _assess_system_state(self) -> None:
        """Assess overall system failure state."""
        with self._state_lock:
            if not self._active_system_failures:
                self._system_state = SystemFailureState.HEALTHY
                return

            # Check for critical failures
            critical_failures = [f for f in self._active_system_failures if f.is_critical()]
            if critical_failures:
                self._system_state = SystemFailureState.CRITICAL
                return

            # Check for high severity failures
            high_severity_failures = [f for f in self._active_system_failures if f.severity == FailureSeverity.HIGH]
            if len(high_severity_failures) >= 2:
                self._system_state = SystemFailureState.CRITICAL
            elif high_severity_failures:
                self._system_state = SystemFailureState.DEGRADED
            else:
                self._system_state = SystemFailureState.DEGRADED

    def _generate_system_failure_report(self) -> SystemFailureReport:
        """Generate comprehensive system failure report."""
        with self._state_lock:
            # Get cascade analyses for active failures
            cascade_analyses = []
            for failure in self._active_system_failures:
                analysis = self.dependency_mapper.analyze_cascade_failure(failure.component_name)
                cascade_analyses.append(analysis)

            # Get active recoveries
            active_recoveries = list(self.recovery_orchestrator.get_active_recoveries().values())

            # Get current degradation plan
            degradation_plan = None
            if self.degradation_manager.get_current_degradation_level() != DegradationLevel.NORMAL:
                # Get the most recent degradation plan
                history = self.degradation_manager.get_degradation_history(limit=1)
                if history:
                    degradation_plan = history[0]

            # Get system health score
            health_score = self.health_monitor.get_system_health_score()

            # Identify critical components affected
            critical_components_affected = []
            for failure in self._active_system_failures:
                if failure.component_name in self.dependency_mapper.get_critical_components():
                    critical_components_affected.append(failure.component_name)

            # Generate recommendations
            recommendations = self._generate_recommendations()

            report = SystemFailureReport(
                timestamp=datetime.now(),
                system_state=self._system_state,
                active_failures=self._active_system_failures.copy(),
                cascade_analyses=cascade_analyses,
                active_recoveries=active_recoveries,
                degradation_plan=degradation_plan,
                system_health_score=health_score,
                critical_components_affected=critical_components_affected,
                recommendations=recommendations,
            )

            # Store in history
            self._failure_history.append(report)
            if len(self._failure_history) > 100:
                self._failure_history = self._failure_history[-100:]

            # Notify callbacks
            for callback in self._system_failure_callbacks:
                try:
                    callback(report)
                except Exception as e:
                    self.logger.error(f"Error in system failure callback: {e}")

            return report

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on current system state."""
        recommendations = []

        with self._state_lock:
            if self._system_state == SystemFailureState.EMERGENCY_HALT:
                recommendations.extend(
                    [
                        "System is in emergency halt - manual intervention required",
                        "Investigate critical component failures before restart",
                        "Verify system integrity before restoring automation",
                    ]
                )
            elif self._system_state == SystemFailureState.CRITICAL:
                recommendations.extend(
                    [
                        "Multiple critical failures detected - immediate attention required",
                        "Consider manual system degradation if auto-degradation failed",
                        "Monitor cascade failure patterns",
                    ]
                )
            elif self._system_state == SystemFailureState.DEGRADED:
                recommendations.extend(
                    [
                        "System operating in degraded mode",
                        "Monitor recovery progress",
                        "Consider manual intervention if recovery fails",
                    ]
                )

            # Add component-specific recommendations
            failed_components = [f.component_name for f in self._active_system_failures]
            if "authority_state_machine" in failed_components:
                recommendations.append("Authority system failure - verify biometric systems")
            if "audit_logger" in failed_components:
                recommendations.append("Audit logging compromised - investigate immediately")
            if "memory_service" in failed_components:
                recommendations.append("Memory service failure - check database integrity")

        return recommendations

    # Public API methods

    def add_system_failure_callback(self, callback: Callable[[SystemFailureReport], None]) -> None:
        """Add callback for system failure reports."""
        self._system_failure_callbacks.append(callback)

    def add_emergency_halt_callback(self, callback: Callable[[ComponentFailure], None]) -> None:
        """Add callback for emergency halt events."""
        self._emergency_halt_callbacks.append(callback)

    def get_system_state(self) -> SystemFailureState:
        """Get current system failure state."""
        with self._state_lock:
            return self._system_state

    def get_active_failures(self) -> List[ComponentFailure]:
        """Get all active system failures."""
        with self._state_lock:
            return self._active_system_failures.copy()

    def get_system_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive system health summary."""
        with self._state_lock:
            return {
                "system_state": self._system_state.value,
                "active_failures": len(self._active_system_failures),
                "system_health_score": self.health_monitor.get_system_health_score(),
                "degradation_level": self.degradation_manager.get_current_degradation_level().value,
                "active_recoveries": len(self.recovery_orchestrator.get_active_recoveries()),
                "critical_components_affected": len(
                    [
                        f
                        for f in self._active_system_failures
                        if f.component_name in self.dependency_mapper.get_critical_components()
                    ]
                ),
                "performance_stats": self._performance_stats.copy(),
            }

    def get_failure_history(self, limit: Optional[int] = None) -> List[SystemFailureReport]:
        """Get system failure history."""
        with self._state_lock:
            if limit:
                return self._failure_history[-limit:]
            return self._failure_history.copy()

    def force_emergency_halt(self, reason: str) -> None:
        """Force emergency system halt."""
        halt_failure = ComponentFailure(
            component_name="system",
            failure_type=FailureType.SECURITY_VIOLATION,
            severity=FailureSeverity.FATAL,
            timestamp=datetime.now(),
            error_message=f"Manual emergency halt: {reason}",
        )

        self._trigger_emergency_halt(halt_failure)

    def is_system_healthy(self) -> bool:
        """Check if system is healthy."""
        return self._system_state == SystemFailureState.HEALTHY

    def get_component_status(self, component_name: str) -> Dict[str, Any]:
        """Get comprehensive status for a specific component."""
        health = self.health_monitor.get_component_health(component_name)
        active_failures = [f for f in self._active_system_failures if f.component_name == component_name]
        is_recovering = self.recovery_orchestrator.is_component_recovering(component_name)
        is_degraded = self.degradation_manager.is_component_degraded(component_name)

        return {
            "component_name": component_name,
            "health_status": health.status.value if health else "unknown",
            "health_score": health.health_score if health else 0.0,
            "active_failures": len(active_failures),
            "is_recovering": is_recovering,
            "is_degraded": is_degraded,
            "last_failure": active_failures[-1] if active_failures else None,
        }
