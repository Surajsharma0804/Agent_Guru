"""
Component Communication and Integration Layer

Production-grade inter-component communication system for GURU Personal Assistant.
Implements secure message passing, component discovery, and communication health monitoring.

This module provides the foundation for all inter-component communication within GURU,
ensuring secure, reliable, and auditable message exchange between system components.
"""

from .component_registry import ComponentInfo, ComponentRegistry, ComponentStatus
from .exceptions import (
    ChannelSecurityError,
    CommunicationError,
    ComponentNotFoundError,
    MessageDeliveryError,
    RegistrationError,
)
from .health_monitor import ChannelHealth, CommunicationHealthMonitor, CommunicationMetrics
from .message_bus import Message, MessageBus, MessagePriority, MessageType
from .secure_channel import ChannelSecurity, EncryptionMode, SecureChannel

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
    "RegistrationError",
]
