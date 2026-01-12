"""
Component Communication and Integration Layer

Production-grade inter-component communication system for GURU Personal Assistant.
Implements secure message passing, component discovery, and communication health monitoring.

This module provides the foundation for all inter-component communication within GURU,
ensuring secure, reliable, and auditable message exchange between system components.
"""

from .message_bus import MessageBus, Message, MessageType, MessagePriority
from .component_registry import ComponentRegistry, ComponentInfo, ComponentStatus
from .secure_channel import SecureChannel, ChannelSecurity, EncryptionMode
from .health_monitor import CommunicationHealthMonitor, ChannelHealth, CommunicationMetrics
from .exceptions import (
    CommunicationError,
    ComponentNotFoundError,
    MessageDeliveryError,
    ChannelSecurityError,
    RegistrationError
)

__all__ = [
    # Core communication
    "MessageBus",
    "Message", 
    "MessageType",
    "MessagePriority",
    
    # Component registry
    "ComponentRegistry",
    "ComponentInfo",
    "ComponentStatus",
    
    # Secure channels
    "SecureChannel",
    "ChannelSecurity", 
    "EncryptionMode",
    
    # Health monitoring
    "CommunicationHealthMonitor",
    "ChannelHealth",
    "CommunicationMetrics",
    
    # Exceptions
    "CommunicationError",
    "ComponentNotFoundError", 
    "MessageDeliveryError",
    "ChannelSecurityError",
    "RegistrationError"
]