"""
Safe System Degradation Management

Implements controlled system degradation when components fail, ensuring that
security boundaries are never compromised and the system fails safely.

Core Principles:
- Fail-safe, never fail-open
- No degraded security state operation
- Immediate safe halt for critical failures
- Graceful degradation only for non-security components
- Complete audit trail of all degradation decisions
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class DegradationLevel(Enum):
    """System degradation levels"""

    NORMAL = "normal"
    REDUCED_FUNCTIONALITY = "reduced_functionality"
    MINIMAL_OPERATION = "minimal_operation"
    SAFE_HALT = "safe_halt"
    EMERGENCY_SHUTDOWN = "emergency_shutdown"


class SystemState(Enum):
    """Overall system state"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    HALTED = "halted"
    SHUTDOWN = "shutdown"


@dataclass
class DegradationAction:
    """Action to take during system degradation"""

    action_type: str
    component_name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    rollback_possible: bool = True
    security_impact: str = "none"

    def execute(self) -> bool:
        """Execute the degradation action"""
        logger.info(
            "Executing degradation action",
            action_type=self.action_type,
            component=self.component_name,
            description=self.description,
        )

        # Implementation would depend on action type
        # For now, return success
        return True

    def rollback(self) -> bool:
        """Rollback the degradation action"""
        if not self.rollback_possible:
            logger.warning(
                "Rollback not possible for action", action_type=self.action_type, component=self.component_name
            )
            return False

        logger.info("Rolling back degradation action", action_type=self.action_type, component=self.component_name)

        # Implementation would depend on action type
        return True


@dataclass
class DegradationPlan:
    """Plan for system degradation"""

    degradation_level: DegradationLevel
    affected_components: List[str]
    actions: List[DegradationAction] = field(default_factory=list)
    estimated_duration: Optional[float] = None
    recovery_criteria: List[str] = field(default_factory=list)
    security_implications: str = "none"
    user_notification_required: bool = True
    
    # Additional fields for test compatibility
    plan_id: Optional[str] = None
    trigger_reason: Optional[str] = None
    degradation_actions: List[DegradationAction] = field(default_factory=list)
    estimated_duration_seconds: Optional[float] = None

    def is_security_safe(self) -> bool:
        """Check if this degradation plan maintains security boundaries"""
        # Plans that maintain or improve security are always safe
        safe_implications = {
            "none",
            "maintains_security", 
            "safe_halt_maintains_security",
            "no_security_impact"
        }
        
        if self.security_implications in safe_implications:
            return True
            
        # Check individual actions
        for action in self.actions:
            if action.security_impact not in safe_implications:
                return False
                
        return True
    created_at: Optional[datetime] = None

    def __post_init__(self):
        """Post-initialization to handle field compatibility"""
        # Ensure degradation_actions is synchronized with actions
        if not self.degradation_actions and self.actions:
            self.degradation_actions = self.actions
        elif self.degradation_actions and not self.actions:
            self.actions = self.degradation_actions
        
        # Ensure duration fields are synchronized
        if self.estimated_duration_seconds is not None and self.estimated_duration is None:
            self.estimated_duration = self.estimated_duration_seconds
        elif self.estimated_duration is not None and self.estimated_duration_seconds is None:
            self.estimated_duration_seconds = self.estimated_duration
            
        # Set created_at if not provided
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    def is_security_safe(self) -> bool:
        """Check if degradation plan maintains security"""
        # Security violations and integrity violations require safe halt
        if self.degradation_level in [DegradationLevel.SAFE_HALT, DegradationLevel.EMERGENCY_SHUTDOWN]:
            return True

        # Check if any actions have security impact
        for action in self.actions:
            if action.security_impact != "none":
                return False

        return True


class SystemDegradationOrchestrator:
    """
    Manages safe system degradation when components fail

    Ensures that system degradation never compromises security boundaries
    and always fails safely when critical components are affected.
    """

    def __init__(self):
        """Initialize degradation manager"""
        self._lock = threading.RLock()
        self.current_state = SystemState.HEALTHY
        self.current_degradation_level = DegradationLevel.NORMAL
        self.active_degradation_plan: Optional[DegradationPlan] = None
        self.degradation_history: List[Dict[str, Any]] = []

        # Callback lists
        self._degradation_callbacks: List[Any] = []
        self._state_change_callbacks: List[Any] = []

        # Critical components that require safe halt on failure
        self.critical_components = {
            "authentication_authority",
            "encryption_boundary",
            "security_monitor",
            "audit_logger",
            "access_control",
            "cryptographic_authority",
        }

        # Components that can be degraded safely
        self.degradable_components = {
            "ui_renderer",
            "notification_system",
            "performance_monitor",
            "analytics_collector",
            "cache_manager",
        }

        self.logger = structlog.get_logger(__name__).bind(component="SystemDegradationOrchestrator")
        self.logger.info("System degradation orchestrator initialized")

    def assess_degradation_need(self, failed_components: List[str]) -> Optional[DegradationPlan]:
        """
        Assess if system degradation is needed for failed components

        Args:
            failed_components: List of component names that have failed

        Returns:
            Degradation plan or None if no degradation needed
        """
        with self._lock:
            if not failed_components:
                return None

            # Check for critical component failures
            critical_failures = [comp for comp in failed_components if comp in self.critical_components]

            if critical_failures:
                # Critical components require immediate safe halt
                return self._create_safe_halt_plan(critical_failures)

            # Check for degradable component failures
            degradable_failures = [comp for comp in failed_components if comp in self.degradable_components]

            if degradable_failures:
                return self._create_degradation_plan(degradable_failures)

            # Unknown components - err on side of caution
            return self._create_safe_halt_plan(failed_components)

    def _create_safe_halt_plan(self, failed_components: List[str]) -> DegradationPlan:
        """Create plan for safe system halt"""
        actions = [
            DegradationAction(
                action_type="halt_component",
                component_name=comp,
                description=f"Safe halt of critical component {comp}",
                rollback_possible=False,
                security_impact="maintains_security",
            )
            for comp in failed_components
        ]

        actions.append(
            DegradationAction(
                action_type="system_halt",
                component_name="system",
                description="Safe system halt due to critical component failure",
                rollback_possible=False,
                security_impact="maintains_security",
            )
        )

        plan = DegradationPlan(
            degradation_level=DegradationLevel.SAFE_HALT,
            affected_components=failed_components,
            actions=actions,
            security_implications="safe_halt_maintains_security",
            user_notification_required=True,
            recovery_criteria=[
                "Critical components must be restored",
                "Security verification must pass",
                "Manual administrator approval required",
            ],
        )

        self.logger.critical("Created safe halt plan for critical failures", failed_components=failed_components)

        return plan

    def _create_degradation_plan(self, failed_components: List[str]) -> DegradationPlan:
        """Create plan for graceful degradation"""
        actions = []

        for comp in failed_components:
            if comp == "ui_renderer":
                actions.append(
                    DegradationAction(
                        action_type="disable_animations",
                        component_name=comp,
                        description="Disable UI animations to reduce load",
                        security_impact="none",
                    )
                )
            elif comp == "notification_system":
                actions.append(
                    DegradationAction(
                        action_type="reduce_notifications",
                        component_name=comp,
                        description="Reduce non-critical notifications",
                        security_impact="none",
                    )
                )
            elif comp == "performance_monitor":
                actions.append(
                    DegradationAction(
                        action_type="disable_monitoring",
                        component_name=comp,
                        description="Disable performance monitoring",
                        security_impact="none",
                    )
                )
            else:
                # Default degradation action
                actions.append(
                    DegradationAction(
                        action_type="disable_component",
                        component_name=comp,
                        description=f"Disable non-critical component {comp}",
                        security_impact="none",
                    )
                )

        # Determine degradation level based on number of failures
        if len(failed_components) == 1:
            level = DegradationLevel.REDUCED_FUNCTIONALITY
        elif len(failed_components) <= 3:
            level = DegradationLevel.MINIMAL_OPERATION
        else:
            level = DegradationLevel.SAFE_HALT

        plan = DegradationPlan(
            degradation_level=level,
            affected_components=failed_components,
            actions=actions,
            security_implications="no_security_impact",
            user_notification_required=True,
            recovery_criteria=["Failed components must be restored", "System health check must pass"],
        )

        self.logger.warning(
            "Created degradation plan for non-critical failures",
            failed_components=failed_components,
            degradation_level=level.value,
        )

        return plan

    def execute_degradation_plan(self, plan: DegradationPlan) -> bool:
        """
        Execute a degradation plan

        Args:
            plan: Degradation plan to execute

        Returns:
            True if plan executed successfully
        """
        with self._lock:
            if not plan.is_security_safe():
                self.logger.error(
                    "Refusing to execute unsafe degradation plan", plan_level=plan.degradation_level.value
                )
                return False

            self.logger.info(
                "Executing degradation plan",
                level=plan.degradation_level.value,
                affected_components=plan.affected_components,
            )

            # Execute all actions
            executed_actions = []
            try:
                for action in plan.actions:
                    if action.execute():
                        executed_actions.append(action)
                    else:
                        # Action failed, rollback previous actions
                        self.logger.error(
                            "Degradation action failed, rolling back",
                            action_type=action.action_type,
                            component=action.component_name,
                        )

                        for rollback_action in reversed(executed_actions):
                            rollback_action.rollback()

                        self._notify_degradation_callbacks(plan, False)
                        return False

                # All actions succeeded
                old_state = self.current_state
                self.active_degradation_plan = plan
                self.current_degradation_level = plan.degradation_level

                # Update system state
                if plan.degradation_level == DegradationLevel.SAFE_HALT:
                    self.current_state = SystemState.HALTED
                elif plan.degradation_level == DegradationLevel.EMERGENCY_SHUTDOWN:
                    self.current_state = SystemState.SHUTDOWN
                else:
                    self.current_state = SystemState.DEGRADED

                # Notify state change
                if old_state != self.current_state:
                    self._notify_state_change_callbacks(old_state, self.current_state)

                # Record in history
                self.degradation_history.append(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "plan": plan,
                        "result": "success",
                        "executed_actions": len(executed_actions),
                    }
                )

                self.logger.info(
                    "Degradation plan executed successfully",
                    level=plan.degradation_level.value,
                    new_state=self.current_state.value,
                )

                # Notify callbacks
                self._notify_degradation_callbacks(plan, True)
                return True

            except Exception as e:
                self.logger.error("Exception during degradation plan execution", error=str(e))

                # Attempt rollback
                for rollback_action in reversed(executed_actions):
                    try:
                        rollback_action.rollback()
                    except Exception as rollback_error:
                        self.logger.error(
                            "Rollback failed", action=rollback_action.action_type, error=str(rollback_error)
                        )

                return False

    def get_current_degradation_level(self) -> DegradationLevel:
        """Get current degradation level"""
        with self._lock:
            return self.current_degradation_level

    def get_current_state(self) -> Dict[str, Any]:
        """Get current system degradation state"""
        with self._lock:
            return {
                "system_state": self.current_state.value,
                "degradation_level": self.current_degradation_level.value,
                "active_plan": self.active_degradation_plan is not None,
                "affected_components": (
                    self.active_degradation_plan.affected_components if self.active_degradation_plan else []
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def get_current_degradation_state(self) -> Dict[str, Any]:
        """Alias for get_current_state for test compatibility"""
        return self.get_current_state()

    def can_recover(self) -> bool:
        """Check if system can recover from current degradation"""
        with self._lock:
            if not self.active_degradation_plan:
                return True

            # Safe halt and emergency shutdown require manual intervention
            if self.current_degradation_level in [DegradationLevel.SAFE_HALT, DegradationLevel.EMERGENCY_SHUTDOWN]:
                return False

            # Other degradation levels can potentially recover
            return True

    def attempt_recovery(self) -> bool:
        """
        Attempt to recover from current degradation

        Returns:
            True if recovery successful
        """
        with self._lock:
            if not self.active_degradation_plan:
                self.logger.info("No active degradation plan, system already healthy")
                return True

            if not self.can_recover():
                self.logger.warning(
                    "Recovery not possible for current degradation level", level=self.current_degradation_level.value
                )
                return False

            self.logger.info("Attempting recovery from degradation", level=self.current_degradation_level.value)

            # Rollback all actions in reverse order
            recovery_success = True
            for action in reversed(self.active_degradation_plan.actions):
                if not action.rollback():
                    recovery_success = False
                    self.logger.error(
                        "Failed to rollback action during recovery",
                        action_type=action.action_type,
                        component=action.component_name,
                    )

            if recovery_success:
                # Recovery successful
                self.active_degradation_plan = None
                self.current_degradation_level = DegradationLevel.NORMAL
                self.current_state = SystemState.HEALTHY

                # Record recovery in history
                self.degradation_history.append(
                    {"timestamp": datetime.now(timezone.utc).isoformat(), "action": "recovery", "result": "success"}
                )

                self.logger.info("Recovery from degradation successful")
                return True
            else:
                self.logger.error("Recovery from degradation failed")
                return False

    def get_degradation_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get history of degradation events."""
        with self._lock:
            history = self.degradation_history.copy()
            if limit:
                return history[-limit:]
            return history

    def is_component_critical(self, component_name: str) -> bool:
        """Check if a component is considered critical"""
        return component_name in self.critical_components

    def is_component_degradable(self, component_name: str) -> bool:
        """Check if a component can be safely degraded"""
        return component_name in self.degradable_components

    def is_component_degraded(self, component_name: str) -> bool:
        """Check if a specific component is currently degraded."""
        with self._lock:
            if not self.active_degradation_plan:
                return False
            return component_name in self.active_degradation_plan.affected_components

    def add_critical_component(self, component_name: str) -> None:
        """Add a component to the critical components list"""
        with self._lock:
            self.critical_components.add(component_name)
            self.logger.info("Added critical component", component=component_name)

    def add_degradable_component(self, component_name: str) -> None:
        """Add a component to the degradable components list"""
        with self._lock:
            self.degradable_components.add(component_name)
            self.logger.info("Added degradable component", component=component_name)

    def add_degradation_callback(self, callback: Any) -> None:
        """
        Register callback for degradation events.

        Args:
            callback: Function to call when degradation is executed
        """
        with self._lock:
            self._degradation_callbacks.append(callback)
            self.logger.info("Registered degradation callback", callback_count=len(self._degradation_callbacks))

    def add_state_change_callback(self, callback: Any) -> None:
        """
        Register callback for system state changes.

        Args:
            callback: Function to call when system state changes
        """
        with self._lock:
            self._state_change_callbacks.append(callback)
            self.logger.info("Registered state change callback", callback_count=len(self._state_change_callbacks))

    def _notify_degradation_callbacks(self, plan: DegradationPlan, success: bool = True) -> None:
        """Notify all registered degradation callbacks."""
        for callback in self._degradation_callbacks:
            try:
                callback(plan)
            except Exception as e:
                self.logger.error("Error in degradation callback", error=str(e))

    def _notify_state_change_callbacks(self, old_state: SystemState, new_state: SystemState) -> None:
        """Notify all registered state change callbacks."""
        for callback in self._state_change_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                self.logger.error("Error in state change callback", error=str(e))


# Alias for test compatibility
SafeDegradationManager = SystemDegradationOrchestrator
