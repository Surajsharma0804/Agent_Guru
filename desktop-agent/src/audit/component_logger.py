"""
Component Audit Logger

Base class for component-specific audit logging with unified interface.
Provides standardized audit logging capabilities for all GURU components
while maintaining component-specific context and requirements.

This enables each component to have specialized audit logging while
ensuring consistency and comprehensive coverage across the system.
"""

import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from .audit_logger import AuditLogger, AuditEvent, AuditEventType, AuditSeverity


class ComponentAuditLogger(ABC):
    """
    Base class for component-specific audit loggers.
    
    This class provides a standardized interface for component-specific
    audit logging while allowing customization for each component's
    specific requirements and event types.
    
    Each component should inherit from this class and implement
    component-specific logging methods while using the unified
    audit infrastructure.
    """
    
    def __init__(self, 
                 component_name: str,
                 audit_logger: AuditLogger,
                 default_session_id: Optional[str] = None,
                 default_user_id: Optional[str] = None):
        """
        Initialize component audit logger.
        
        Args:
            component_name: Name of the component for audit context
            audit_logger: Main audit logger instance
            default_session_id: Default session ID for this component
            default_user_id: Default user ID for this component
        """
        self.component_name = component_name
        self.audit_logger = audit_logger
        self.default_session_id = default_session_id
        self.default_user_id = default_user_id
        self.logger = logging.getLogger(f"{__name__}.{component_name}")
    
    def _create_event(self,
                     event_type: AuditEventType,
                     action: str,
                     details: Dict[str, Any],
                     severity: AuditSeverity = AuditSeverity.INFO,
                     session_id: Optional[str] = None,
                     user_id: Optional[str] = None,
                     device_id: Optional[str] = None,
                     correlation_id: Optional[str] = None) -> AuditEvent:
        """Create audit event with component context"""
        return AuditEvent(
            event_type=event_type,
            severity=severity,
            component=self.component_name,
            action=action,
            details=details,
            session_id=session_id or self.default_session_id,
            user_id=user_id or self.default_user_id,
            device_id=device_id,
            correlation_id=correlation_id
        )
    
    def log_event(self,
                  event_type: AuditEventType,
                  action: str,
                  details: Dict[str, Any],
                  severity: AuditSeverity = AuditSeverity.INFO,
                  session_id: Optional[str] = None,
                  user_id: Optional[str] = None,
                  device_id: Optional[str] = None,
                  correlation_id: Optional[str] = None) -> str:
        """Log audit event through main audit logger"""
        event = self._create_event(
            event_type=event_type,
            action=action,
            details=details,
            severity=severity,
            session_id=session_id,
            user_id=user_id,
            device_id=device_id,
            correlation_id=correlation_id
        )
        
        return self.audit_logger.log_event(event)
    
    def log_info(self, action: str, details: Dict[str, Any], **kwargs) -> str:
        """Log informational event"""
        return self.log_event(
            event_type=self._get_default_event_type(),
            action=action,
            details=details,
            severity=AuditSeverity.INFO,
            **kwargs
        )
    
    def log_warning(self, action: str, details: Dict[str, Any], **kwargs) -> str:
        """Log warning event"""
        return self.log_event(
            event_type=self._get_default_event_type(),
            action=action,
            details=details,
            severity=AuditSeverity.WARNING,
            **kwargs
        )
    
    def log_error(self, action: str, details: Dict[str, Any], **kwargs) -> str:
        """Log error event"""
        return self.log_event(
            event_type=self._get_default_event_type(),
            action=action,
            details=details,
            severity=AuditSeverity.ERROR,
            **kwargs
        )
    
    def log_critical(self, action: str, details: Dict[str, Any], **kwargs) -> str:
        """Log critical event"""
        return self.log_event(
            event_type=self._get_default_event_type(),
            action=action,
            details=details,
            severity=AuditSeverity.CRITICAL,
            **kwargs
        )
    
    def log_security_violation(self, action: str, details: Dict[str, Any], **kwargs) -> str:
        """Log security violation event"""
        return self.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            action=action,
            details=details,
            severity=AuditSeverity.ERROR,
            **kwargs
        )
    
    def log_emergency(self, action: str, details: Dict[str, Any], **kwargs) -> str:
        """Log emergency event"""
        return self.log_event(
            event_type=AuditEventType.EMERGENCY_SHUTDOWN,
            action=action,
            details=details,
            severity=AuditSeverity.EMERGENCY,
            **kwargs
        )
    
    @abstractmethod
    def _get_default_event_type(self) -> AuditEventType:
        """Get default event type for this component"""
        pass
    
    # Component-specific methods to be implemented by subclasses
    
    @abstractmethod
    def log_component_startup(self, details: Dict[str, Any] = None) -> str:
        """Log component startup event"""
        pass
    
    @abstractmethod
    def log_component_shutdown(self, details: Dict[str, Any] = None) -> str:
        """Log component shutdown event"""
        pass
    
    @abstractmethod
    def log_configuration_change(self, details: Dict[str, Any]) -> str:
        """Log configuration change event"""
        pass


class AuthorityAuditLogger(ComponentAuditLogger):
    """Audit logger for authority management component"""
    
    def __init__(self, audit_logger: AuditLogger, **kwargs):
        super().__init__("authority", audit_logger, **kwargs)
    
    def _get_default_event_type(self) -> AuditEventType:
        return AuditEventType.AUTHORITY_STATE_CHANGE
    
    def log_component_startup(self, details: Dict[str, Any] = None) -> str:
        return self.log_info("authority_system_startup", details or {})
    
    def log_component_shutdown(self, details: Dict[str, Any] = None) -> str:
        return self.log_info("authority_system_shutdown", details or {})
    
    def log_configuration_change(self, details: Dict[str, Any]) -> str:
        return self.log_warning("authority_config_change", details)
    
    def log_state_transition(self, from_state: str, to_state: str, reason: str, **kwargs) -> str:
        """Log authority state transition"""
        details = {
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason
        }
        return self.log_info("state_transition", details, **kwargs)
    
    def log_biometric_verification(self, factor_type: str, success: bool, confidence: float = None, **kwargs) -> str:
        """Log biometric verification attempt"""
        details = {
            "factor_type": factor_type,
            "success": success,
            "confidence_score": confidence
        }
        event_type = AuditEventType.BIOMETRIC_VERIFICATION
        severity = AuditSeverity.INFO if success else AuditSeverity.WARNING
        return self.log_event(event_type, "biometric_verification", details, severity, **kwargs)


class InputAuditLogger(ComponentAuditLogger):
    """Audit logger for input simulation component"""
    
    def __init__(self, audit_logger: AuditLogger, **kwargs):
        super().__init__("input", audit_logger, **kwargs)
    
    def _get_default_event_type(self) -> AuditEventType:
        return AuditEventType.INPUT_SIMULATION
    
    def log_component_startup(self, details: Dict[str, Any] = None) -> str:
        return self.log_info("input_engine_startup", details or {})
    
    def log_component_shutdown(self, details: Dict[str, Any] = None) -> str:
        return self.log_info("input_engine_shutdown", details or {})
    
    def log_configuration_change(self, details: Dict[str, Any]) -> str:
        return self.log_warning("input_config_change", details)
    
    def log_keyboard_input(self, text_length: int, key_count: int, **kwargs) -> str:
        """Log keyboard input simulation"""
        details = {
            "text_length": text_length,
            "key_count": key_count,
            "input_type": "keyboard"
        }
        return self.log_event(AuditEventType.KEYBOARD_INPUT, "keyboard_simulation", details, **kwargs)
    
    def log_mouse_input(self, action_type: str, coordinates: tuple = None, **kwargs) -> str:
        """Log mouse input simulation"""
        details = {
            "action_type": action_type,
            "coordinates": coordinates,
            "input_type": "mouse"
        }
        return self.log_event(AuditEventType.MOUSE_INPUT, "mouse_simulation", details, **kwargs)


class SecurityAuditLogger(ComponentAuditLogger):
    """Audit logger for security events"""
    
    def __init__(self, audit_logger: AuditLogger, **kwargs):
        super().__init__("security", audit_logger, **kwargs)
    
    def _get_default_event_type(self) -> AuditEventType:
        return AuditEventType.SECURITY_VIOLATION
    
    def log_component_startup(self, details: Dict[str, Any] = None) -> str:
        return self.log_info("security_system_startup", details or {})
    
    def log_component_shutdown(self, details: Dict[str, Any] = None) -> str:
        return self.log_info("security_system_shutdown", details or {})
    
    def log_configuration_change(self, details: Dict[str, Any]) -> str:
        return self.log_error("security_config_change", details)
    
    def log_intrusion_detected(self, intrusion_type: str, details: Dict[str, Any], **kwargs) -> str:
        """Log intrusion detection event"""
        audit_details = {
            "intrusion_type": intrusion_type,
            **details
        }
        return self.log_event(
            AuditEventType.INTRUSION_DETECTED,
            "intrusion_detected",
            audit_details,
            AuditSeverity.CRITICAL,
            **kwargs
        )
    
    def log_workstation_locked(self, reason: str, **kwargs) -> str:
        """Log workstation lock event"""
        details = {"lock_reason": reason}
        return self.log_event(
            AuditEventType.WORKSTATION_LOCKED,
            "workstation_locked",
            details,
            AuditSeverity.WARNING,
            **kwargs
        )


class SkillAuditLogger(ComponentAuditLogger):
    """Audit logger for skill execution component"""
    
    def __init__(self, audit_logger: AuditLogger, **kwargs):
        super().__init__("skills", audit_logger, **kwargs)
    
    def _get_default_event_type(self) -> AuditEventType:
        return AuditEventType.SKILL_EXECUTION
    
    def log_component_startup(self, details: Dict[str, Any] = None) -> str:
        return self.log_info("skill_system_startup", details or {})
    
    def log_component_shutdown(self, details: Dict[str, Any] = None) -> str:
        return self.log_info("skill_system_shutdown", details or {})
    
    def log_configuration_change(self, details: Dict[str, Any]) -> str:
        return self.log_warning("skill_config_change", details)
    
    def log_skill_execution(self, skill_id: str, success: bool, execution_time_ms: int, **kwargs) -> str:
        """Log skill execution event"""
        details = {
            "skill_id": skill_id,
            "success": success,
            "execution_time_ms": execution_time_ms
        }
        severity = AuditSeverity.INFO if success else AuditSeverity.WARNING
        return self.log_event(AuditEventType.SKILL_EXECUTION, "skill_executed", details, severity, **kwargs)
    
    def log_sandbox_violation(self, skill_id: str, violation_type: str, details: Dict[str, Any], **kwargs) -> str:
        """Log sandbox violation event"""
        audit_details = {
            "skill_id": skill_id,
            "violation_type": violation_type,
            **details
        }
        return self.log_event(
            AuditEventType.SANDBOX_VIOLATION,
            "sandbox_violation",
            audit_details,
            AuditSeverity.ERROR,
            **kwargs
        )


class MemoryAuditLogger(ComponentAuditLogger):
    """Audit logger for memory service component"""
    
    def __init__(self, audit_logger: AuditLogger, **kwargs):
        super().__init__("memory", audit_logger, **kwargs)
    
    def _get_default_event_type(self) -> AuditEventType:
        return AuditEventType.MEMORY_ACCESS
    
    def log_component_startup(self, details: Dict[str, Any] = None) -> str:
        return self.log_info("memory_service_startup", details or {})
    
    def log_component_shutdown(self, details: Dict[str, Any] = None) -> str:
        return self.log_info("memory_service_shutdown", details or {})
    
    def log_configuration_change(self, details: Dict[str, Any]) -> str:
        return self.log_warning("memory_config_change", details)
    
    def log_memory_access(self, operation: str, memory_type: str, record_count: int, **kwargs) -> str:
        """Log memory access event"""
        details = {
            "operation": operation,
            "memory_type": memory_type,
            "record_count": record_count
        }
        return self.log_info("memory_access", details, **kwargs)
    
    def log_data_encryption(self, operation: str, data_size: int, **kwargs) -> str:
        """Log data encryption event"""
        details = {
            "operation": operation,
            "data_size_bytes": data_size
        }
        return self.log_event(AuditEventType.DATA_ENCRYPTION, "data_encryption", details, **kwargs)
    
    def log_data_deletion(self, memory_type: str, record_count: int, **kwargs) -> str:
        """Log data deletion event"""
        details = {
            "memory_type": memory_type,
            "deleted_records": record_count
        }
        return self.log_event(AuditEventType.DATA_DELETION, "data_deletion", details, **kwargs)