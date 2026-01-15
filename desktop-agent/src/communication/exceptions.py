"""
Communication System Exceptions

Comprehensive exception hierarchy for the GURU component communication system.
Provides specific error types for different failure modes with detailed context.
"""

from typing import Any, Dict, Optional


class CommunicationError(Exception):
    """Base exception for all communication system errors."""
    
    def __init__(self, message: str, component: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.component = component
        self.details = details or {}
        
    def __str__(self) -> str:
        base_msg = super().__str__()
        if self.component:
            base_msg = f"[{self.component}] {base_msg}"
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            base_msg = f"{base_msg} ({details_str})"
        return base_msg


class ComponentNotFoundError(CommunicationError):
    """Exception raised when a component cannot be found in the registry."""
    
    def __init__(self, component_name: str, registry_size: int = 0):
        super().__init__(
            f"Component '{component_name}' not found in registry",
            component=component_name,
            details={"registry_size": registry_size}
        )
        self.component_name = component_name


class MessageDeliveryError(CommunicationError):
    """Exception raised when message delivery fails."""
    
    def __init__(self, message_id: str, target_component: str, 
                 reason: str, retry_count: int = 0):
        super().__init__(
            f"Failed to deliver message {message_id} to {target_component}: {reason}",
            component=target_component,
            details={"message_id": message_id, "retry_count": retry_count, "reason": reason}
        )
        self.message_id = message_id
        self.target_component = target_component
        self.reason = reason


class ChannelSecurityError(CommunicationError):
    """Exception raised when channel security is compromised."""
    
    def __init__(self, channel_id: str, security_violation: str, 
                 source_component: Optional[str] = None):
        super().__init__(
            f"Security violation in channel {channel_id}: {security_violation}",
            component=source_component,
            details={"channel_id": channel_id, "violation": security_violation}
        )
        self.channel_id = channel_id
        self.security_violation = security_violation


class RegistrationError(CommunicationError):
    """Exception raised when component registration fails."""
    
    def __init__(self, component_name: str, reason: str, 
                 existing_component: Optional[str] = None):
        super().__init__(
            f"Failed to register component '{component_name}': {reason}",
            component=component_name,
            details={"reason": reason, "existing_component": existing_component}
        )
        self.component_name = component_name
        self.reason = reason


class MessageTimeoutError(CommunicationError):
    """Exception raised when message processing times out."""
    
    def __init__(self, message_id: str, timeout_seconds: float, 
                 target_component: Optional[str] = None):
        super().__init__(
            f"Message {message_id} timed out after {timeout_seconds}s",
            component=target_component,
            details={"message_id": message_id, "timeout_seconds": timeout_seconds}
        )
        self.message_id = message_id
        self.timeout_seconds = timeout_seconds


class ChannelClosedError(CommunicationError):
    """Exception raised when attempting to use a closed channel."""
    
    def __init__(self, channel_id: str, reason: str = "Channel closed"):
        super().__init__(
            f"Channel {channel_id} is closed: {reason}",
            details={"channel_id": channel_id, "reason": reason}
        )
        self.channel_id = channel_id


class MessageValidationError(CommunicationError):
    """Exception raised when message validation fails."""
    
    def __init__(self, message_id: str, validation_error: str, 
                 message_type: Optional[str] = None):
        super().__init__(
            f"Message {message_id} validation failed: {validation_error}",
            details={
                "message_id": message_id, 
                "validation_error": validation_error,
                "message_type": message_type
            }
        )
        self.message_id = message_id
        self.validation_error = validation_error


class ComponentUnavailableError(CommunicationError):
    """Exception raised when a component is temporarily unavailable."""
    
    def __init__(self, component_name: str, reason: str, 
                 retry_after_seconds: Optional[float] = None):
        super().__init__(
            f"Component '{component_name}' is unavailable: {reason}",
            component=component_name,
            details={"reason": reason, "retry_after_seconds": retry_after_seconds}
        )
        self.component_name = component_name
        self.retry_after_seconds = retry_after_seconds


class CommunicationSecurityError(CommunicationError):
    """Exception raised for general communication security violations."""
    
    def __init__(self, violation_type: str, description: str, 
                 source_component: Optional[str] = None,
                 target_component: Optional[str] = None):
        super().__init__(
            f"Communication security violation ({violation_type}): {description}",
            component=source_component,
            details={
                "violation_type": violation_type,
                "description": description,
                "source_component": source_component,
                "target_component": target_component
            }
        )
        self.violation_type = violation_type
        self.source_component = source_component
        self.target_component = target_component


class MessageQueueFullError(CommunicationError):
    """Exception raised when message queue is full."""
    
    def __init__(self, component_name: str, queue_size: int, max_size: int):
        super().__init__(
            f"Message queue for '{component_name}' is full ({queue_size}/{max_size})",
            component=component_name,
            details={"queue_size": queue_size, "max_size": max_size}
        )
        self.component_name = component_name
        self.queue_size = queue_size
        self.max_size = max_size


class ComponentLifecycleError(CommunicationError):
    """Exception raised during component lifecycle operations."""
    
    def __init__(self, component_name: str, operation: str, reason: str):
        super().__init__(
            f"Component '{component_name}' {operation} failed: {reason}",
            component=component_name,
            details={"operation": operation, "reason": reason}
        )
        self.component_name = component_name
        self.operation = operation