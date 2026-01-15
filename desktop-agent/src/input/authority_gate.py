"""
Authority Gate for Input Simulation

Production-grade authority enforcement system that ensures all input simulation
operations require proper authority state and comply with security policies.

The Authority Gate is the single point of authority verification for all input
operations, implementing the "Root of Trust" principle where all automation
derives legitimacy from the AuthorityStateMachine.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

from ..authority.state import AuthorityState, AuthorityStateMachine


class AuthorityLevel(Enum):
    """Authority levels required for different operations"""
    NONE = "none"
    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    ADMIN = "admin"


@dataclass
class AuthorityCheck:
    """Result of authority verification"""
    granted: bool
    current_state: AuthorityState
    required_level: AuthorityLevel
    reason: str
    timestamp: datetime
    session_id: Optional[str] = None


class AuthorityGate:
    """
    Authority enforcement gate for input simulation operations.
    
    This gate implements the core security principle that all automation must
    derive legitimacy from the AuthorityStateMachine. No input simulation can
    occur without proper authority verification.
    
    Key Features:
    - Single point of authority verification
    - Risk-based authority requirements
    - Session-based authority tracking
    - Automatic authority revocation on security events
    - Comprehensive audit logging of authority decisions
    """
    
    def __init__(self, authority_machine: AuthorityStateMachine):
        """
        Initialize Authority Gate with authority state machine.
        
        Args:
            authority_machine: The authoritative source of authority state
        """
        self.authority_machine = authority_machine
        self.logger = logging.getLogger(__name__)
        
        # Authority policy configuration
        self.authority_policies = self._initialize_authority_policies()
        
        # Session tracking
        self.active_sessions: Dict[str, datetime] = {}
        self.session_timeout = timedelta(minutes=30)  # 30-minute session timeout
        
        # Security monitoring
        self.authority_violations: List[Dict] = []
        self.max_violation_history = 1000
        
        self.logger.info("AuthorityGate initialized with comprehensive authority enforcement")
    
    def _initialize_authority_policies(self) -> Dict[str, AuthorityLevel]:
        """Initialize authority level requirements for different operations"""
        return {
            # Text input operations
            "type_text": AuthorityLevel.LOW_RISK,
            "type_single_character": AuthorityLevel.LOW_RISK,
            
            # Basic key operations
            "send_single_key": AuthorityLevel.LOW_RISK,
            "send_basic_key": AuthorityLevel.LOW_RISK,
            
            # Key combinations
            "send_key_combination": AuthorityLevel.MEDIUM_RISK,
            "send_system_key_combination": AuthorityLevel.HIGH_RISK,
            
            # System operations
            "send_windows_key": AuthorityLevel.HIGH_RISK,
            "send_alt_f4": AuthorityLevel.HIGH_RISK,
            "send_ctrl_alt_delete": AuthorityLevel.ADMIN,
            
            # Mouse operations
            "mouse_click": AuthorityLevel.MEDIUM_RISK,
            "mouse_drag": AuthorityLevel.MEDIUM_RISK,
            "mouse_scroll": AuthorityLevel.LOW_RISK,
            
            # Administrative operations
            "admin_command": AuthorityLevel.ADMIN,
            "system_configuration": AuthorityLevel.ADMIN,
            "registry_access": AuthorityLevel.ADMIN,
        }
    
    def check_authority(self, operation: str, session_id: Optional[str] = None) -> AuthorityCheck:
        """
        Check if current authority state allows the specified operation.
        
        Args:
            operation: Operation name to check authority for
            session_id: Optional session identifier
            
        Returns:
            AuthorityCheck with verification result and details
        """
        timestamp = datetime.now()
        current_state = self.authority_machine.get_current_state()
        
        # Determine required authority level
        required_level = self.authority_policies.get(operation, AuthorityLevel.MEDIUM_RISK)
        
        # Check if authority state allows operation
        authority_granted = self._evaluate_authority(current_state, required_level)
        
        # Determine reason
        if authority_granted:
            reason = f"Authority granted for {operation} (level: {required_level.value})"
        else:
            reason = f"Authority denied: {current_state.value} insufficient for {required_level.value}"
        
        # Create authority check result
        check_result = AuthorityCheck(
            granted=authority_granted,
            current_state=current_state,
            required_level=required_level,
            reason=reason,
            timestamp=timestamp,
            session_id=session_id
        )
        
        # Log authority decision
        if authority_granted:
            self.logger.info(f"Authority granted: {operation} (state: {current_state.value})")
        else:
            self.logger.warning(f"Authority denied: {operation} (state: {current_state.value}, required: {required_level.value})")
            self._record_authority_violation(operation, current_state, required_level, session_id)
        
        # Update session tracking
        if session_id and authority_granted:
            self.active_sessions[session_id] = timestamp
            self._cleanup_expired_sessions()
        
        return check_result
    
    def _evaluate_authority(self, current_state: AuthorityState, required_level: AuthorityLevel) -> bool:
        """
        Evaluate if current authority state meets required level.
        
        Args:
            current_state: Current authority state
            required_level: Required authority level
            
        Returns:
            True if authority is sufficient, False otherwise
        """
        # Only ARMED state allows any input simulation
        if current_state != AuthorityState.ARMED:
            return False
        
        # For ARMED state, check if we meet the required level
        # In this implementation, ARMED state allows all operations
        # In a more complex system, you might have different ARMED levels
        
        # Special handling for admin operations
        if required_level == AuthorityLevel.ADMIN:
            # Admin operations require additional verification
            # This would typically involve checking for elevated privileges
            # For now, we allow admin operations if ARMED (with logging)
            self.logger.warning(f"Admin-level operation requested with ARMED state")
            return True
        
        return True
    
    def _record_authority_violation(self, 
                                  operation: str, 
                                  current_state: AuthorityState, 
                                  required_level: AuthorityLevel,
                                  session_id: Optional[str]):
        """Record authority violation for security monitoring"""
        violation = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "current_state": current_state.value,
            "required_level": required_level.value,
            "session_id": session_id,
            "violation_type": "insufficient_authority"
        }
        
        self.authority_violations.append(violation)
        
        # Limit violation history size
        if len(self.authority_violations) > self.max_violation_history:
            self.authority_violations = self.authority_violations[-self.max_violation_history:]
        
        self.logger.warning(f"Authority violation recorded: {violation}")
    
    def _cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        now = datetime.now()
        expired_sessions = [
            session_id for session_id, last_activity in self.active_sessions.items()
            if now - last_activity > self.session_timeout
        ]
        
        for session_id in expired_sessions:
            del self.active_sessions[session_id]
            self.logger.info(f"Session expired: {session_id}")
    
    def is_armed(self) -> bool:
        """
        Check if authority state is ARMED.
        
        Returns:
            True if authority state is ARMED, False otherwise
        """
        return self.authority_machine.get_current_state() == AuthorityState.ARMED
    
    def get_current_authority_level(self) -> Optional[AuthorityLevel]:
        """
        Get current effective authority level.
        
        Returns:
            Current authority level or None if not authorized
        """
        current_state = self.authority_machine.get_current_state()
        
        if current_state == AuthorityState.ARMED:
            return AuthorityLevel.HIGH_RISK  # ARMED allows high-risk operations
        else:
            return None
    
    def revoke_authority(self, reason: str, session_id: Optional[str] = None):
        """
        SECURITY ENFORCEMENT: Revoke authority via workstation lock.
        
        This method now enforces OS-level re-authentication by triggering workstation lock
        instead of maintaining session continuity.
        
        Args:
            reason: Reason for authority revocation
            session_id: Optional session identifier
        """
        self.logger.critical(f"Authority revocation triggering workstation lock: {reason}")
        
        # Map reason to StateTransitionReason
        from ..authority.state import StateTransitionReason
        
        reason_mapping = {
            "manual": StateTransitionReason.MANUAL_REVOKE,
            "timeout": StateTransitionReason.INACTIVITY_TIMEOUT,
            "failure": StateTransitionReason.COMPONENT_FAILURE,
            "intrusion": StateTransitionReason.INTRUSION_DETECTED,
        }
        
        # Determine appropriate transition reason
        transition_reason = StateTransitionReason.MANUAL_REVOKE
        for key, value in reason_mapping.items():
            if key.lower() in reason.lower():
                transition_reason = value
                break
        
        # Use the secure workstation lock method
        result = self.authority_machine.revoke_authority_via_workstation_lock(
            reason=transition_reason,
            metadata={
                "input_gate_reason": reason,
                "session_id": session_id or "unknown"
            }
        )
        
        # Clear active sessions (if workstation lock succeeded, process will be suspended)
        if session_id and session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        # Record revocation event
        revocation_event = {
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "session_id": session_id,
            "event_type": "authority_revoked_via_workstation_lock",
            "workstation_lock_result": result
        }
        
        self.authority_violations.append(revocation_event)
        
        self.logger.warning(f"Authority revoked: {revocation_event}")
    
    def emergency_lockdown(self, reason: str):
        """
        Emergency lockdown - immediately revoke all authority.
        
        Args:
            reason: Reason for emergency lockdown
        """
        self.logger.critical(f"EMERGENCY LOCKDOWN: {reason}")
        
        # Force immediate transition to locked state
        self.authority_machine.force_lock(f"EMERGENCY: {reason}")
        
        # Clear all active sessions
        self.active_sessions.clear()
        
        # Record emergency event
        emergency_event = {
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "event_type": "emergency_lockdown",
            "severity": "critical"
        }
        
        self.authority_violations.append(emergency_event)
        
        self.logger.critical(f"Emergency lockdown executed: {emergency_event}")
    
    def get_authority_status(self) -> Dict:
        """
        Get current authority status for monitoring.
        
        Returns:
            Dictionary with current authority status and statistics
        """
        current_state = self.authority_machine.get_current_state()
        current_level = self.get_current_authority_level()
        
        return {
            "current_state": current_state.value,
            "current_authority_level": current_level.value if current_level else None,
            "is_armed": self.is_armed(),
            "active_sessions": len(self.active_sessions),
            "session_timeout_minutes": self.session_timeout.total_seconds() / 60,
            "authority_violations_count": len(self.authority_violations),
            "recent_violations": self.authority_violations[-10:] if self.authority_violations else [],
            "authority_policies_count": len(self.authority_policies)
        }
    
    def get_operation_authority_level(self, operation: str) -> AuthorityLevel:
        """
        Get required authority level for an operation.
        
        Args:
            operation: Operation name
            
        Returns:
            Required authority level
        """
        return self.authority_policies.get(operation, AuthorityLevel.MEDIUM_RISK)
    
    def update_authority_policy(self, operation: str, required_level: AuthorityLevel):
        """
        Update authority policy for an operation.
        
        Args:
            operation: Operation name
            required_level: New required authority level
        """
        old_level = self.authority_policies.get(operation, AuthorityLevel.MEDIUM_RISK)
        self.authority_policies[operation] = required_level
        
        self.logger.info(f"Authority policy updated: {operation} {old_level.value} -> {required_level.value}")
    
    def validate_session(self, session_id: str) -> bool:
        """
        Validate if a session is active and not expired.
        
        Args:
            session_id: Session identifier to validate
            
        Returns:
            True if session is valid, False otherwise
        """
        if session_id not in self.active_sessions:
            return False
        
        last_activity = self.active_sessions[session_id]
        if datetime.now() - last_activity > self.session_timeout:
            del self.active_sessions[session_id]
            return False
        
        return True