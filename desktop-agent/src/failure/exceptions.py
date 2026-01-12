"""
Failure Handling Exceptions

Defines all exceptions used in the failure handling system with clear
categorization and context for different failure scenarios.
"""

from typing import Optional, Dict, Any
from datetime import datetime


class ComponentFailureError(Exception):
    """Base exception for component failures."""
    
    def __init__(self, component_name: str, failure_reason: str, 
                 context: Optional[Dict[str, Any]] = None):
        self.component_name = component_name
        self.failure_reason = failure_reason
        self.context = context or {}
        self.timestamp = datetime.now()
        
        super().__init__(f"Component '{component_name}' failed: {failure_reason}")


class CriticalSystemFailureError(ComponentFailureError):
    """Exception for critical system failures that require immediate halt."""
    
    def __init__(self, component_name: str, failure_reason: str, 
                 affected_components: Optional[list] = None,
                 context: Optional[Dict[str, Any]] = None):
        self.affected_components = affected_components or []
        super().__init__(component_name, failure_reason, context)


class RecoveryFailedError(Exception):
    """Exception for failed recovery attempts."""
    
    def __init__(self, component_name: str, recovery_action: str, 
                 failure_reason: str, attempts: int = 1):
        self.component_name = component_name
        self.recovery_action = recovery_action
        self.failure_reason = failure_reason
        self.attempts = attempts
        self.timestamp = datetime.now()
        
        super().__init__(
            f"Recovery failed for '{component_name}' after {attempts} attempts: "
            f"Action '{recovery_action}' failed - {failure_reason}"
        )


class DegradationNotAllowedError(Exception):
    """Exception for when degradation would compromise security."""
    
    def __init__(self, component_name: str, reason: str, 
                 security_impact: str):
        self.component_name = component_name
        self.reason = reason
        self.security_impact = security_impact
        self.timestamp = datetime.now()
        
        super().__init__(
            f"Degradation not allowed for '{component_name}': {reason}. "
            f"Security impact: {security_impact}"
        )


class CascadeFailureError(ComponentFailureError):
    """Exception for cascade failures affecting multiple components."""
    
    def __init__(self, root_component: str, failure_reason: str,
                 cascade_components: list, context: Optional[Dict[str, Any]] = None):
        self.root_component = root_component
        self.cascade_components = cascade_components
        
        super().__init__(
            root_component, 
            f"{failure_reason} (cascade affecting: {', '.join(cascade_components)})",
            context
        )


class HealthCheckTimeoutError(ComponentFailureError):
    """Exception for health check timeouts."""
    
    def __init__(self, component_name: str, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds
        super().__init__(
            component_name,
            f"Health check timed out after {timeout_seconds} seconds"
        )


class ComponentNotRespondingError(ComponentFailureError):
    """Exception for components that stop responding."""
    
    def __init__(self, component_name: str, last_response_time: datetime,
                 max_silence_seconds: float):
        self.last_response_time = last_response_time
        self.max_silence_seconds = max_silence_seconds
        
        silence_duration = (datetime.now() - last_response_time).total_seconds()
        super().__init__(
            component_name,
            f"Component not responding for {silence_duration:.1f}s "
            f"(max allowed: {max_silence_seconds}s)"
        )


class ResourceExhaustionError(ComponentFailureError):
    """Exception for resource exhaustion failures."""
    
    def __init__(self, component_name: str, resource_type: str, 
                 current_usage: float, limit: float, unit: str = ""):
        self.resource_type = resource_type
        self.current_usage = current_usage
        self.limit = limit
        self.unit = unit
        
        super().__init__(
            component_name,
            f"Resource exhaustion: {resource_type} usage {current_usage}{unit} "
            f"exceeds limit {limit}{unit}"
        )


class SecurityViolationError(ComponentFailureError):
    """Exception for security violations that trigger failures."""
    
    def __init__(self, component_name: str, violation_type: str,
                 violation_details: str, severity: str = "high"):
        self.violation_type = violation_type
        self.violation_details = violation_details
        self.severity = severity
        
        super().__init__(
            component_name,
            f"Security violation ({severity}): {violation_type} - {violation_details}"
        )


class IntegrityViolationError(ComponentFailureError):
    """Exception for data integrity violations."""
    
    def __init__(self, component_name: str, data_type: str,
                 integrity_check: str, expected: str, actual: str):
        self.data_type = data_type
        self.integrity_check = integrity_check
        self.expected = expected
        self.actual = actual
        
        super().__init__(
            component_name,
            f"Integrity violation in {data_type}: {integrity_check} check failed. "
            f"Expected: {expected}, Actual: {actual}"
        )

class DegradationNotAllowedError(Exception):
    """Exception for when system degradation is not allowed."""
    
    def __init__(self, component_name: str, reason: str):
        self.component_name = component_name
        self.reason = reason
        self.timestamp = datetime.now()
        
        super().__init__(f"Degradation not allowed for '{component_name}': {reason}")


class CascadeFailureError(ComponentFailureError):
    """Exception for cascade failures affecting multiple components."""
    
    def __init__(self, root_component: str, affected_components: list, 
                 failure_reason: str, context: Optional[Dict[str, Any]] = None):
        self.root_component = root_component
        self.affected_components = affected_components
        super().__init__(root_component, failure_reason, context)


class SecurityViolationError(CriticalSystemFailureError):
    """Exception for security violations that require immediate system halt."""
    
    def __init__(self, component_name: str, violation_type: str, 
                 security_context: Optional[Dict[str, Any]] = None):
        self.violation_type = violation_type
        self.security_context = security_context or {}
        
        super().__init__(
            component_name, 
            f"Security violation: {violation_type}",
            context=security_context
        )


class IntegrityViolationError(CriticalSystemFailureError):
    """Exception for data integrity violations."""
    
    def __init__(self, component_name: str, integrity_check: str, 
                 expected_value: str, actual_value: str,
                 context: Optional[Dict[str, Any]] = None):
        self.integrity_check = integrity_check
        self.expected_value = expected_value
        self.actual_value = actual_value
        
        super().__init__(
            component_name,
            f"Integrity violation in {integrity_check}: expected '{expected_value}', got '{actual_value}'",
            context=context
        )


class HealthCheckTimeoutError(ComponentFailureError):
    """Exception for health check timeouts."""
    
    def __init__(self, component_name: str, timeout_seconds: float,
                 context: Optional[Dict[str, Any]] = None):
        self.timeout_seconds = timeout_seconds
        
        super().__init__(
            component_name,
            f"Health check timeout after {timeout_seconds} seconds",
            context=context
        )