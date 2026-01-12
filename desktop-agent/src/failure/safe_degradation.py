"""
Safe Degradation Manager

Implements safe system degradation policies that ensure security boundaries
are never compromised. When components fail, the system degrades safely
by disabling non-critical functionality while maintaining security invariants.

Core Principles:
- Security boundaries are never weakened
- Critical components cannot be degraded
- All degradation is explicit and auditable
- Recovery is always possible
- User is always informed of degradation state
"""

import threading
import logging
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

from .exceptions import (
    DegradationNotAllowedError,
    ComponentFailureError,
    CriticalSystemFailureError
)


class DegradationLevel(Enum):
    """Levels of system degradation."""
    NORMAL = "normal"                    # Full functionality
    REDUCED_PERFORMANCE = "reduced"      # Slower but full functionality
    LIMITED_FUNCTIONALITY = "limited"   # Some features disabled
    ESSENTIAL_ONLY = "essential"        # Only critical security functions
    SAFE_HALT = "safe_halt"            # Complete automation halt


class SystemState(Enum):
    """Overall system operational state."""
    FULLY_OPERATIONAL = "fully_operational"
    DEGRADED_OPERATION = "degraded_operation"
    LIMITED_OPERATION = "limited_operation"
    EMERGENCY_MODE = "emergency_mode"
    SAFE_HALT = "safe_halt"


@dataclass
class DegradationAction:
    """Represents a specific degradation action."""
    component_name: str
    action_type: str  # "disable", "reduce_performance", "limit_functionality"
    description: str
    security_impact: str
    reversible: bool = True
    requires_user_approval: bool = False
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DegradationPlan:
    """Plan for degrading system functionality."""
    degradation_level: DegradationLevel
    actions: List[DegradationAction]
    affected_components: Set[str]
    security_assessment: str
    user_notification: str
    recovery_plan: List[str]
    created_at: datetime = field(default_factory=datetime.now)


class SafeDegradationManager:
    """
    Manages safe system degradation when components fail.
    
    Ensures that system degradation never compromises security boundaries
    and that all degradation is explicit, auditable, and recoverable.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Current system state
        self._current_state = SystemState.FULLY_OPERATIONAL
        self._current_degradation_level = DegradationLevel.NORMAL
        self._active_degradations: Dict[str, DegradationAction] = {}
        
        # Degradation policies
        self._degradation_policies = self._initialize_degradation_policies()
        self._critical_components = self._initialize_critical_components()
        self._security_boundaries = self._initialize_security_boundaries()
        
        # State management
        self._state_lock = threading.RLock()
        self._degradation_history: List[DegradationPlan] = []
        
        # Callbacks
        self._degradation_callbacks: List[Callable[[DegradationPlan], None]] = []
        self._state_change_callbacks: List[Callable[[SystemState, SystemState], None]] = []
        
    def _initialize_degradation_policies(self) -> Dict[str, Dict[str, Any]]:
        """Initialize degradation policies for different components."""
        return {
            # Authority system - NEVER degrade
            "authority_state_machine": {
                "degradable": False,
                "reason": "Authority system is root of trust - cannot be degraded"
            },
            "biometric_verifier": {
                "degradable": False,
                "reason": "Biometric verification is security boundary - cannot be degraded"
            },
            
            # Audit system - NEVER degrade
            "audit_logger": {
                "degradable": False,
                "reason": "Audit logging is security requirement - cannot be degraded"
            },
            
            # Input system - Can be degraded by disabling
            "input_engine": {
                "degradable": True,
                "degradation_actions": [
                    {
                        "level": DegradationLevel.LIMITED_FUNCTIONALITY,
                        "action": "disable_complex_input",
                        "description": "Disable complex input sequences, keep basic typing"
                    },
                    {
                        "level": DegradationLevel.ESSENTIAL_ONLY,
                        "action": "disable_all_input",
                        "description": "Disable all input simulation"
                    }
                ]
            },
            
            # Memory system - Can be degraded
            "memory_service": {
                "degradable": True,
                "degradation_actions": [
                    {
                        "level": DegradationLevel.REDUCED_PERFORMANCE,
                        "action": "reduce_memory_operations",
                        "description": "Reduce memory operation frequency"
                    },
                    {
                        "level": DegradationLevel.LIMITED_FUNCTIONALITY,
                        "action": "disable_non_critical_memory",
                        "description": "Disable episodic and semantic memory, keep core only"
                    },
                    {
                        "level": DegradationLevel.ESSENTIAL_ONLY,
                        "action": "disable_memory_service",
                        "description": "Disable all memory operations"
                    }
                ]
            },
            
            # LLM system - Can be degraded
            "llm_adapter": {
                "degradable": True,
                "degradation_actions": [
                    {
                        "level": DegradationLevel.REDUCED_PERFORMANCE,
                        "action": "reduce_llm_requests",
                        "description": "Reduce LLM request frequency and complexity"
                    },
                    {
                        "level": DegradationLevel.LIMITED_FUNCTIONALITY,
                        "action": "local_llm_only",
                        "description": "Disable cloud LLM providers, use local only"
                    },
                    {
                        "level": DegradationLevel.ESSENTIAL_ONLY,
                        "action": "disable_llm",
                        "description": "Disable all LLM functionality"
                    }
                ]
            },
            
            # Skill system - Can be degraded
            "skill_runner": {
                "degradable": True,
                "degradation_actions": [
                    {
                        "level": DegradationLevel.LIMITED_FUNCTIONALITY,
                        "action": "disable_high_risk_skills",
                        "description": "Disable skills with high security risk"
                    },
                    {
                        "level": DegradationLevel.ESSENTIAL_ONLY,
                        "action": "disable_all_skills",
                        "description": "Disable all skill execution"
                    }
                ]
            },
            
            # Screen observation - Can be degraded
            "screen_observer": {
                "degradable": True,
                "degradation_actions": [
                    {
                        "level": DegradationLevel.REDUCED_PERFORMANCE,
                        "action": "reduce_capture_frequency",
                        "description": "Reduce screen capture frequency"
                    },
                    {
                        "level": DegradationLevel.LIMITED_FUNCTIONALITY,
                        "action": "disable_screen_capture",
                        "description": "Disable screen observation"
                    }
                ]
            }
        }
    
    def _initialize_critical_components(self) -> Set[str]:
        """Initialize set of critical components that cannot be degraded."""
        return {
            "authority_state_machine",
            "biometric_verifier",
            "audit_logger",
            "intrusion_detector",
            "cryptographic_engine"
        }
    
    def _initialize_security_boundaries(self) -> Dict[str, str]:
        """Initialize security boundaries that must be preserved."""
        return {
            "authority_enforcement": "Authority state machine must always enforce access control",
            "audit_integrity": "All actions must be auditable with cryptographic integrity",
            "biometric_verification": "Biometric verification must remain secure and accurate",
            "input_validation": "All input must be validated and sanitized",
            "skill_sandboxing": "Skills must remain sandboxed and isolated",
            "cryptographic_operations": "Cryptographic operations must maintain security standards"
        }
    
    def add_degradation_callback(self, callback: Callable[[DegradationPlan], None]) -> None:
        """Add callback for degradation events."""
        self._degradation_callbacks.append(callback)
    
    def add_state_change_callback(self, callback: Callable[[SystemState, SystemState], None]) -> None:
        """Add callback for system state changes."""
        self._state_change_callbacks.append(callback)
    
    def assess_degradation_need(self, failed_components: List[str]) -> Optional[DegradationPlan]:
        """Assess if degradation is needed based on failed components."""
        if not failed_components:
            return None
        
        # Check if any critical components have failed
        critical_failures = [c for c in failed_components if c in self._critical_components]
        if critical_failures:
            # Critical components cannot be degraded - system must halt
            return self._create_safe_halt_plan(critical_failures)
        
        # Determine appropriate degradation level
        degradation_level = self._determine_degradation_level(failed_components)
        
        # Create degradation plan
        return self._create_degradation_plan(failed_components, degradation_level)
    
    def _determine_degradation_level(self, failed_components: List[str]) -> DegradationLevel:
        """Determine appropriate degradation level based on failed components."""
        # Count degradable vs non-degradable failures
        degradable_failures = []
        non_degradable_failures = []
        
        for component in failed_components:
            policy = self._degradation_policies.get(component, {})
            if policy.get("degradable", False):
                degradable_failures.append(component)
            else:
                non_degradable_failures.append(component)
        
        # If any non-degradable components failed, we need safe halt
        if non_degradable_failures:
            return DegradationLevel.SAFE_HALT
        
        # Determine level based on number and importance of failures
        if len(degradable_failures) >= 3:
            return DegradationLevel.ESSENTIAL_ONLY
        elif len(degradable_failures) >= 2:
            return DegradationLevel.LIMITED_FUNCTIONALITY
        elif any(comp in ["input_engine", "memory_service"] for comp in degradable_failures):
            return DegradationLevel.LIMITED_FUNCTIONALITY
        else:
            return DegradationLevel.REDUCED_PERFORMANCE
    
    def _create_degradation_plan(self, failed_components: List[str], 
                                level: DegradationLevel) -> DegradationPlan:
        """Create a degradation plan for the given components and level."""
        actions = []
        affected_components = set(failed_components)
        
        for component in failed_components:
            policy = self._degradation_policies.get(component, {})
            if not policy.get("degradable", False):
                continue
            
            # Find appropriate degradation action for this level
            component_actions = policy.get("degradation_actions", [])
            for action_config in component_actions:
                if action_config["level"] == level:
                    action = DegradationAction(
                        component_name=component,
                        action_type=action_config["action"],
                        description=action_config["description"],
                        security_impact="No security impact - functionality reduced only",
                        reversible=True,
                        requires_user_approval=level in [DegradationLevel.ESSENTIAL_ONLY, DegradationLevel.SAFE_HALT]
                    )
                    actions.append(action)
                    break
        
        # Assess security impact
        security_assessment = self._assess_security_impact(actions)
        
        # Create user notification
        user_notification = self._create_user_notification(level, failed_components)
        
        # Create recovery plan
        recovery_plan = self._create_recovery_plan(failed_components, actions)
        
        return DegradationPlan(
            degradation_level=level,
            actions=actions,
            affected_components=affected_components,
            security_assessment=security_assessment,
            user_notification=user_notification,
            recovery_plan=recovery_plan
        )
    
    def _create_safe_halt_plan(self, critical_failures: List[str]) -> DegradationPlan:
        """Create a safe halt plan for critical component failures."""
        halt_action = DegradationAction(
            component_name="system",
            action_type="safe_halt",
            description="Complete system halt due to critical component failure",
            security_impact="System security maintained through complete automation halt",
            reversible=False,
            requires_user_approval=True,
            context={"critical_failures": critical_failures}
        )
        
        return DegradationPlan(
            degradation_level=DegradationLevel.SAFE_HALT,
            actions=[halt_action],
            affected_components=set(critical_failures),
            security_assessment="CRITICAL: System security compromised, immediate halt required",
            user_notification=f"CRITICAL SYSTEM FAILURE: {', '.join(critical_failures)} failed. "
                             f"System automation has been completely disabled for security.",
            recovery_plan=[
                "Investigate and resolve critical component failures",
                "Verify system integrity",
                "Manually restart system after verification",
                "Perform comprehensive security audit"
            ]
        )
    
    def _assess_security_impact(self, actions: List[DegradationAction]) -> str:
        """Assess the security impact of degradation actions."""
        if not actions:
            return "No security impact"
        
        # Check if any actions affect security boundaries
        security_affecting_actions = []
        for action in actions:
            if action.component_name in ["input_engine", "skill_runner"]:
                security_affecting_actions.append(action)
        
        if security_affecting_actions:
            return (f"SECURITY IMPACT: {len(security_affecting_actions)} actions affect "
                   f"system functionality but maintain security boundaries")
        else:
            return "No security impact - only performance and functionality affected"
    
    def _create_user_notification(self, level: DegradationLevel, 
                                 failed_components: List[str]) -> str:
        """Create user notification for degradation."""
        component_list = ", ".join(failed_components)
        
        notifications = {
            DegradationLevel.REDUCED_PERFORMANCE: 
                f"System performance reduced due to issues with: {component_list}. "
                f"All functionality remains available but may be slower.",
            
            DegradationLevel.LIMITED_FUNCTIONALITY:
                f"Some system features disabled due to failures in: {component_list}. "
                f"Core security and basic functionality remain operational.",
            
            DegradationLevel.ESSENTIAL_ONLY:
                f"System operating in essential mode only due to failures in: {component_list}. "
                f"Only critical security functions are active.",
            
            DegradationLevel.SAFE_HALT:
                f"SYSTEM HALT: Critical failures in: {component_list}. "
                f"All automation disabled for security. Manual intervention required."
        }
        
        return notifications.get(level, f"System degraded due to failures in: {component_list}")
    
    def _create_recovery_plan(self, failed_components: List[str], 
                            actions: List[DegradationAction]) -> List[str]:
        """Create recovery plan for degraded system."""
        plan = [
            "1. Investigate root cause of component failures",
            "2. Resolve underlying issues causing failures",
            "3. Verify component health and functionality",
            "4. Gradually restore degraded functionality",
            "5. Monitor system stability after recovery"
        ]
        
        # Add component-specific recovery steps
        for component in failed_components:
            if component == "input_engine":
                plan.append("- Verify input simulation APIs and permissions")
            elif component == "memory_service":
                plan.append("- Check database integrity and storage availability")
            elif component == "llm_adapter":
                plan.append("- Verify LLM provider connectivity and authentication")
            elif component == "skill_runner":
                plan.append("- Check skill sandboxing and execution environment")
        
        return plan
    
    def execute_degradation_plan(self, plan: DegradationPlan) -> bool:
        """Execute a degradation plan."""
        with self._state_lock:
            try:
                self.logger.warning(f"Executing degradation plan: {plan.degradation_level.value}")
                
                # Check if degradation is allowed
                self._validate_degradation_plan(plan)
                
                # Execute each action
                for action in plan.actions:
                    self._execute_degradation_action(action)
                    self._active_degradations[action.component_name] = action
                
                # Update system state
                old_state = self._current_state
                self._current_degradation_level = plan.degradation_level
                self._current_state = self._determine_system_state(plan.degradation_level)
                
                # Record in history
                self._degradation_history.append(plan)
                
                # Notify callbacks
                self._notify_degradation_callbacks(plan)
                if old_state != self._current_state:
                    self._notify_state_change_callbacks(old_state, self._current_state)
                
                self.logger.warning(f"Degradation plan executed successfully. "
                                  f"System state: {self._current_state.value}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to execute degradation plan: {e}")
                return False
    
    def _validate_degradation_plan(self, plan: DegradationPlan) -> None:
        """Validate that a degradation plan is safe to execute."""
        # Check for attempts to degrade critical components
        for action in plan.actions:
            if action.component_name in self._critical_components:
                raise DegradationNotAllowedError(
                    action.component_name,
                    "Component is critical for system security",
                    "Would compromise security boundaries"
                )
        
        # Check security boundaries
        for boundary, description in self._security_boundaries.items():
            if self._would_violate_security_boundary(plan, boundary):
                raise DegradationNotAllowedError(
                    "system",
                    f"Plan would violate security boundary: {boundary}",
                    description
                )
    
    def _would_violate_security_boundary(self, plan: DegradationPlan, boundary: str) -> bool:
        """Check if a plan would violate a security boundary."""
        # This is a simplified check - in production, this would be more sophisticated
        boundary_components = {
            "authority_enforcement": ["authority_state_machine", "biometric_verifier"],
            "audit_integrity": ["audit_logger"],
            "biometric_verification": ["biometric_verifier"],
            "input_validation": ["input_engine"],
            "skill_sandboxing": ["skill_runner"],
            "cryptographic_operations": ["cryptographic_engine"]
        }
        
        protected_components = boundary_components.get(boundary, [])
        
        for action in plan.actions:
            if (action.component_name in protected_components and 
                action.action_type in ["disable", "disable_all"]):
                return True
        
        return False
    
    def _execute_degradation_action(self, action: DegradationAction) -> None:
        """Execute a single degradation action."""
        self.logger.info(f"Executing degradation action: {action.component_name} - {action.action_type}")
        
        # This would integrate with the actual components to perform degradation
        # For now, we just log the action
        
        # In production, this would call methods on the actual components:
        # - component.reduce_performance()
        # - component.disable_functionality()
        # - component.enter_safe_mode()
        
        pass
    
    def _determine_system_state(self, degradation_level: DegradationLevel) -> SystemState:
        """Determine system state based on degradation level."""
        state_mapping = {
            DegradationLevel.NORMAL: SystemState.FULLY_OPERATIONAL,
            DegradationLevel.REDUCED_PERFORMANCE: SystemState.DEGRADED_OPERATION,
            DegradationLevel.LIMITED_FUNCTIONALITY: SystemState.LIMITED_OPERATION,
            DegradationLevel.ESSENTIAL_ONLY: SystemState.EMERGENCY_MODE,
            DegradationLevel.SAFE_HALT: SystemState.SAFE_HALT
        }
        
        return state_mapping.get(degradation_level, SystemState.DEGRADED_OPERATION)
    
    def _notify_degradation_callbacks(self, plan: DegradationPlan) -> None:
        """Notify degradation callbacks."""
        for callback in self._degradation_callbacks:
            try:
                callback(plan)
            except Exception as e:
                self.logger.error(f"Error in degradation callback: {e}")
    
    def _notify_state_change_callbacks(self, old_state: SystemState, new_state: SystemState) -> None:
        """Notify state change callbacks."""
        for callback in self._state_change_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                self.logger.error(f"Error in state change callback: {e}")
    
    def recover_from_degradation(self, component_name: str) -> bool:
        """Recover a component from degradation."""
        with self._state_lock:
            if component_name not in self._active_degradations:
                return True  # Already recovered
            
            try:
                action = self._active_degradations[component_name]
                
                if not action.reversible:
                    self.logger.warning(f"Cannot recover component '{component_name}' - "
                                      f"degradation is not reversible")
                    return False
                
                # Execute recovery
                self._execute_recovery_action(component_name, action)
                
                # Remove from active degradations
                del self._active_degradations[component_name]
                
                # Check if we can improve system state
                self._reassess_system_state()
                
                self.logger.info(f"Successfully recovered component '{component_name}' from degradation")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to recover component '{component_name}': {e}")
                return False
    
    def _execute_recovery_action(self, component_name: str, action: DegradationAction) -> None:
        """Execute recovery action for a component."""
        self.logger.info(f"Recovering component '{component_name}' from degradation")
        
        # This would integrate with actual components to restore functionality
        # For now, we just log the recovery
        pass
    
    def _reassess_system_state(self) -> None:
        """Reassess system state after recovery."""
        if not self._active_degradations:
            # No active degradations - return to normal
            old_state = self._current_state
            self._current_state = SystemState.FULLY_OPERATIONAL
            self._current_degradation_level = DegradationLevel.NORMAL
            
            if old_state != self._current_state:
                self._notify_state_change_callbacks(old_state, self._current_state)
                self.logger.info("System fully recovered - returned to normal operation")
        else:
            # Determine best possible state with remaining degradations
            remaining_levels = [
                action.context.get("degradation_level", DegradationLevel.REDUCED_PERFORMANCE)
                for action in self._active_degradations.values()
            ]
            
            # Use the most severe remaining degradation level
            if DegradationLevel.SAFE_HALT in remaining_levels:
                new_level = DegradationLevel.SAFE_HALT
            elif DegradationLevel.ESSENTIAL_ONLY in remaining_levels:
                new_level = DegradationLevel.ESSENTIAL_ONLY
            elif DegradationLevel.LIMITED_FUNCTIONALITY in remaining_levels:
                new_level = DegradationLevel.LIMITED_FUNCTIONALITY
            else:
                new_level = DegradationLevel.REDUCED_PERFORMANCE
            
            old_state = self._current_state
            self._current_degradation_level = new_level
            self._current_state = self._determine_system_state(new_level)
            
            if old_state != self._current_state:
                self._notify_state_change_callbacks(old_state, self._current_state)
    
    # Public API methods
    
    def get_current_state(self) -> SystemState:
        """Get current system state."""
        with self._state_lock:
            return self._current_state
    
    def get_current_degradation_level(self) -> DegradationLevel:
        """Get current degradation level."""
        with self._state_lock:
            return self._current_degradation_level
    
    def get_active_degradations(self) -> Dict[str, DegradationAction]:
        """Get all active degradations."""
        with self._state_lock:
            return self._active_degradations.copy()
    
    def get_degradation_history(self, limit: Optional[int] = None) -> List[DegradationPlan]:
        """Get degradation history."""
        with self._state_lock:
            if limit:
                return self._degradation_history[-limit:]
            return self._degradation_history.copy()
    
    def is_component_degraded(self, component_name: str) -> bool:
        """Check if a component is currently degraded."""
        with self._state_lock:
            return component_name in self._active_degradations
    
    def can_component_be_degraded(self, component_name: str) -> bool:
        """Check if a component can be safely degraded."""
        return (component_name not in self._critical_components and
                self._degradation_policies.get(component_name, {}).get("degradable", False))
    
    def get_system_status_summary(self) -> Dict[str, Any]:
        """Get comprehensive system status summary."""
        with self._state_lock:
            return {
                "system_state": self._current_state.value,
                "degradation_level": self._current_degradation_level.value,
                "active_degradations": len(self._active_degradations),
                "degraded_components": list(self._active_degradations.keys()),
                "total_degradation_events": len(self._degradation_history),
                "is_fully_operational": self._current_state == SystemState.FULLY_OPERATIONAL,
                "requires_attention": self._current_state in [
                    SystemState.EMERGENCY_MODE, 
                    SystemState.SAFE_HALT
                ]
            }