"""
Component Integration Layer

Production-grade integration layer that orchestrates all GURU communication components.
Provides unified interface for component registration, discovery, and secure communication.

This is the main entry point for the GURU communication system, integrating:
- Component registry and discovery
- Secure message bus
- Encrypted communication channels
- Health monitoring and failure detection
- Audit logging and security monitoring
"""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

# Import audit logger from existing audit system
from ..audit.audit_logger import AuditLogger
from .component_registry import ComponentInfo, ComponentLifecycle, ComponentRegistry, ComponentStatus, ComponentType
from .exceptions import CommunicationError, RegistrationError
from .health_monitor import ChannelHealth, ChannelHealthStatus, CommunicationHealthMonitor
from .message_bus import ComponentMessageProtocol, Message, MessageBus, MessagePriority, MessageType
from .secure_channel import ChannelSecurity, EncryptionMode, SecureChannelOrchestrator


class IntegrationMode(Enum):
    """Integration layer operation modes."""

    DEVELOPMENT = "development"  # Development mode with relaxed security
    TESTING = "testing"  # Testing mode with mock components
    PRODUCTION = "production"  # Production mode with full security


@dataclass
class IntegrationConfig:
    """Configuration for integration layer."""

    mode: IntegrationMode = IntegrationMode.PRODUCTION

    # Message bus configuration
    max_queue_size: int = 10000
    worker_threads: int = 4
    enable_message_audit: bool = True

    # Registry configuration
    heartbeat_timeout_seconds: float = 60.0
    enable_dependency_checking: bool = True

    # Security configuration
    default_security_level: ChannelSecurity = ChannelSecurity.STANDARD
    default_encryption_mode: EncryptionMode = EncryptionMode.AES_256_GCM
    enable_channel_encryption: bool = True

    # Health monitoring configuration
    monitoring_interval_seconds: float = 5.0
    enable_health_monitoring: bool = True
    enable_trend_analysis: bool = True

    # Audit configuration
    audit_log_directory: Optional[str] = None
    enable_comprehensive_audit: bool = True


class ComponentIntegrationLayer:
    """
    Production-grade component integration layer for GURU.

    Orchestrates all communication components to provide:
    - Unified component registration and discovery
    - Secure inter-component messaging
    - Encrypted communication channels
    - Comprehensive health monitoring
    - Security audit logging
    - Failure detection and recovery
    - Performance monitoring and optimization
    """

    def __init__(self, config: Optional[IntegrationConfig] = None):
        """
        Initialize component integration layer.

        Args:
            config: Integration configuration (uses defaults if None)
        """
        self.config = config or IntegrationConfig()
        self.logger = logging.getLogger(__name__)

        # Core components
        self.message_bus: Optional[MessageBus] = None
        self.component_registry: Optional[ComponentRegistry] = None
        self.channel_manager: Optional[SecureChannelOrchestrator] = None
        self.health_monitor: Optional[CommunicationHealthMonitor] = None
        self.audit_logger: Optional[AuditLogger] = None

        # Integration state
        self._integration_lock = threading.RLock()
        self._initialized = False
        self._running = False
        self._startup_time: Optional[datetime] = None

        # Component tracking
        self._registered_components: Dict[str, Dict[str, Any]] = {}
        self._active_channels: Dict[str, str] = {}  # component_pair -> channel_id
        self._integration_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

        # Performance and statistics
        self._integration_stats = {
            "components_registered": 0,
            "channels_created": 0,
            "messages_processed": 0,
            "security_events": 0,
            "health_checks_performed": 0,
            "failures_detected": 0,
        }

        self.logger.info(f"ComponentIntegrationLayer initialized in {self.config.mode.value} mode")

    def initialize(self) -> None:
        """Initialize all integration components."""
        if self._initialized:
            return

        with self._integration_lock:
            try:
                self._startup_time = datetime.now()

                # Initialize audit logger first (required for security logging)
                if self.config.enable_comprehensive_audit:
                    self._initialize_audit_logger()

                # Initialize component registry
                self._initialize_component_registry()

                # Initialize message bus
                self._initialize_message_bus()

                # Initialize channel manager
                self._initialize_channel_manager()

                # Initialize health monitor
                if self.config.enable_health_monitoring:
                    self._initialize_health_monitor()

                # Set up integration callbacks
                self._setup_integration_callbacks()

                self._initialized = True

                self.logger.info("Component integration layer initialized successfully")

                if self.audit_logger:
                    self.audit_logger.log_system_event(
                        "integration_layer_initialized",
                        {
                            "mode": self.config.mode.value,
                            "startup_time": self._startup_time.isoformat(),
                            "components_enabled": self._get_enabled_components(),
                        },
                    )

            except Exception as e:
                self.logger.error(f"Failed to initialize integration layer: {e}")
                raise CommunicationError(f"Integration layer initialization failed: {e}")

    def start(self) -> None:
        """Start all integration components."""
        if not self._initialized:
            self.initialize()

        if self._running:
            return

        with self._integration_lock:
            try:
                # Start message bus
                if self.message_bus:
                    self.message_bus.start()

                # Start component registry monitoring
                if self.component_registry:
                    self.component_registry.start_monitoring()

                # Start health monitoring
                if self.health_monitor:
                    self.health_monitor.start_monitoring()

                self._running = True

                self.logger.info("Component integration layer started")

                if self.audit_logger:
                    self.audit_logger.log_system_event(
                        "integration_layer_started",
                        {"startup_duration_ms": (datetime.now() - self._startup_time).total_seconds() * 1000},
                    )

            except Exception as e:
                self.logger.error(f"Failed to start integration layer: {e}")
                raise CommunicationError(f"Integration layer startup failed: {e}")

    def stop(self) -> None:
        """Stop all integration components."""
        if not self._running:
            return

        with self._integration_lock:
            try:
                self._running = False

                # Stop health monitoring
                if self.health_monitor:
                    self.health_monitor.stop_monitoring()

                # Stop component registry monitoring
                if self.component_registry:
                    self.component_registry.stop_monitoring()

                # Stop message bus
                if self.message_bus:
                    self.message_bus.stop()

                # Close all channels
                if self.channel_manager:
                    for channel_id in list(self.channel_manager.get_all_channels().keys()):
                        self.channel_manager.close_channel(channel_id)

                self.logger.info("Component integration layer stopped")

                if self.audit_logger:
                    self.audit_logger.log_system_event(
                        "integration_layer_stopped", {"shutdown_time": datetime.now().isoformat()}
                    )

            except Exception as e:
                self.logger.error(f"Error stopping integration layer: {e}")

    def register_component(
        self,
        component_name: str,
        component_type: ComponentType,
        component_ref: Any,
        version: str = "1.0.0",
        description: str = "",
        dependencies: Optional[Set[str]] = None,
        capabilities: Optional[List[str]] = None,
        security_level: str = "standard",
        trusted: bool = False,
        lifecycle_handler: Optional[ComponentLifecycle] = None,
    ) -> None:
        """
        Register component with full integration.

        Args:
            component_name: Unique component identifier
            component_type: Type of component
            component_ref: Reference to component instance
            version: Component version
            description: Component description
            dependencies: Set of component dependencies
            capabilities: List of component capabilities
            security_level: Security level (standard, elevated, critical)
            trusted: Whether component is trusted for security operations
            lifecycle_handler: Optional lifecycle management handler
        """
        if not self._initialized:
            raise CommunicationError("Integration layer not initialized")

        with self._integration_lock:
            try:
                # Create component info
                component_info = ComponentInfo(
                    name=component_name,
                    component_type=component_type,
                    version=version,
                    description=description,
                    dependencies=dependencies or set(),
                    security_level=security_level,
                    trusted=trusted,
                )

                # Register with component registry
                if self.component_registry:
                    self.component_registry.register_component(
                        component_info=component_info, component_ref=component_ref, lifecycle_handler=lifecycle_handler
                    )

                # Register with message bus if component handles messages
                if isinstance(component_ref, ComponentMessageProtocol) and self.message_bus:
                    self.message_bus.register_component(
                        component_name=component_name,
                        handler=component_ref,
                        component_ref=component_ref,
                        trusted=trusted,
                    )

                # Register with health monitor
                if self.health_monitor:
                    # Create initial channel health for component
                    channel_health = ChannelHealth(
                        channel_id=f"{component_name}_health", status=ChannelHealthStatus.HEALTHY
                    )
                    self.health_monitor.register_channel(f"{component_name}_health", channel_health)

                # Track registration
                self._registered_components[component_name] = {
                    "component_info": component_info,
                    "registered_at": datetime.now(),
                    "message_handler": isinstance(component_ref, ComponentMessageProtocol),
                    "lifecycle_handler": lifecycle_handler is not None,
                    "health_monitored": True,
                }

                self._integration_stats["components_registered"] += 1

                self.logger.info(f"Component '{component_name}' registered successfully")

                # Audit log registration
                if self.audit_logger:
                    self.audit_logger.log_system_event(
                        "component_registered",
                        {
                            "component_name": component_name,
                            "component_type": component_type.value,
                            "version": version,
                            "security_level": security_level,
                            "trusted": trusted,
                            "dependencies": list(dependencies) if dependencies else [],
                            "capabilities": capabilities or [],
                        },
                    )

                # Notify integration callbacks
                self._notify_integration_callbacks(
                    "component_registered", {"component_name": component_name, "component_info": component_info}
                )

            except Exception as e:
                self.logger.error(f"Failed to register component '{component_name}': {e}")
                raise RegistrationError(component_name, str(e))

    def unregister_component(self, component_name: str) -> None:
        """Unregister component from all integration systems."""
        with self._integration_lock:
            try:
                # Unregister from message bus
                if self.message_bus:
                    self.message_bus.unregister_component(component_name)

                # Unregister from component registry
                if self.component_registry:
                    self.component_registry.unregister_component(component_name)

                # Unregister from health monitor
                if self.health_monitor:
                    self.health_monitor.unregister_channel(f"{component_name}_health")

                # Remove from tracking
                component_info = self._registered_components.pop(component_name, None)

                self.logger.info(f"Component '{component_name}' unregistered successfully")

                # Audit log unregistration
                if self.audit_logger:
                    self.audit_logger.log_system_event("component_unregistered", {"component_name": component_name})

                # Notify integration callbacks
                self._notify_integration_callbacks(
                    "component_unregistered", {"component_name": component_name, "component_info": component_info}
                )

            except Exception as e:
                self.logger.error(f"Failed to unregister component '{component_name}': {e}")
                raise CommunicationError(f"Component unregistration failed: {e}")

    def send_message(
        self,
        source_component: str,
        target_component: str,
        message_type: MessageType,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        timeout_seconds: float = 30.0,
        use_secure_channel: bool = None,
    ) -> bool:
        """
        Send message between components with optional encryption.

        Args:
            source_component: Source component name
            target_component: Target component name
            message_type: Type of message
            payload: Message payload
            priority: Message priority
            timeout_seconds: Timeout for message delivery
            use_secure_channel: Use encrypted channel (auto-detect if None)

        Returns:
            True if message sent successfully
        """
        if not self._running:
            raise CommunicationError("Integration layer not running")

        try:
            # Determine if secure channel should be used
            if use_secure_channel is None:
                use_secure_channel = self._should_use_secure_channel(source_component, target_component, message_type)

            if use_secure_channel and self.channel_manager:
                # Use secure channel
                return self._send_secure_message(
                    source_component, target_component, message_type, payload, priority, timeout_seconds
                )
            else:
                # Use regular message bus
                return self._send_regular_message(
                    source_component, target_component, message_type, payload, priority, timeout_seconds
                )

        except Exception as e:
            self.logger.error(f"Failed to send message from {source_component} to {target_component}: {e}")

            # Record error in health monitor
            if self.health_monitor:
                self.health_monitor.record_message_error(
                    f"{source_component}_{target_component}", "send_failure", {"error": str(e)}
                )

            raise CommunicationError(f"Message send failed: {e}")

    def create_secure_channel(
        self, local_component: str, remote_component: str, security_level: Optional[ChannelSecurity] = None
    ) -> str:
        """
        Create secure communication channel between components.

        Args:
            local_component: Local component name
            remote_component: Remote component name
            security_level: Security level for channel

        Returns:
            Channel ID of created channel
        """
        if not self.channel_manager:
            raise CommunicationError("Channel manager not available")

        try:
            security_level = security_level or self.config.default_security_level

            channel_id = self.channel_manager.create_channel(
                local_component=local_component,
                remote_component=remote_component,
                security_level=security_level,
                encryption_mode=self.config.default_encryption_mode,
            )

            # Track channel
            component_pair = f"{local_component}_{remote_component}"
            self._active_channels[component_pair] = channel_id
            self._integration_stats["channels_created"] += 1

            # Register channel with health monitor
            if self.health_monitor:
                self.health_monitor.register_channel(channel_id)

            # Open channel
            channel = self.channel_manager.get_channel(channel_id)
            if channel:
                channel.open_channel()

            self.logger.info(f"Secure channel created: {channel_id} ({local_component} <-> {remote_component})")

            # Audit log channel creation
            if self.audit_logger:
                self.audit_logger.log_security_event(
                    "secure_channel_created",
                    {
                        "channel_id": channel_id,
                        "local_component": local_component,
                        "remote_component": remote_component,
                        "security_level": security_level.value,
                    },
                )

            return channel_id

        except Exception as e:
            self.logger.error(f"Failed to create secure channel: {e}")
            raise CommunicationError(f"Secure channel creation failed: {e}")

    def get_component_info(self, component_name: str) -> Optional[ComponentInfo]:
        """Get component information."""
        if self.component_registry:
            return self.component_registry.get_component(component_name)
        return None

    def get_all_components(self) -> Dict[str, ComponentInfo]:
        """Get all registered components."""
        if self.component_registry:
            return self.component_registry.get_all_components()
        return {}

    def get_components_by_type(self, component_type: ComponentType) -> List[ComponentInfo]:
        """Get components by type."""
        if self.component_registry:
            return self.component_registry.get_components_by_type(component_type)
        return []

    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health information."""
        health_info = {
            "integration_layer": {
                "initialized": self._initialized,
                "running": self._running,
                "startup_time": self._startup_time.isoformat() if self._startup_time else None,
                "uptime_seconds": (datetime.now() - self._startup_time).total_seconds() if self._startup_time else 0,
            },
            "statistics": self._integration_stats.copy(),
            "registered_components": len(self._registered_components),
            "active_channels": len(self._active_channels),
        }

        # Add component registry health
        if self.component_registry:
            health_info["component_registry"] = self.component_registry.get_registry_statistics()

        # Add message bus health
        if self.message_bus:
            health_info["message_bus"] = self.message_bus.get_bus_statistics()

        # Add channel manager health
        if self.channel_manager:
            health_info["channel_manager"] = self.channel_manager.get_manager_statistics()

        # Add communication health
        if self.health_monitor:
            health_info["communication_health"] = {
                "system_metrics": self.health_monitor.get_system_metrics(),
                "monitoring_stats": self.health_monitor.get_monitoring_statistics(),
                "unhealthy_channels": self.health_monitor.get_unhealthy_channels(),
            }

        return health_info

    def validate_system_integrity(self) -> Dict[str, List[str]]:
        """Validate system integrity and return issues."""
        issues = {}

        # Validate component dependencies
        if self.component_registry:
            dependency_issues = self.component_registry.validate_system_dependencies()
            if dependency_issues:
                issues["dependency_issues"] = dependency_issues

        # Validate message bus health
        if self.message_bus:
            bus_stats = self.message_bus.get_bus_statistics()
            if not bus_stats["running"]:
                issues.setdefault("system_issues", []).append("Message bus not running")
            if bus_stats["dead_letter_queue_size"] > 100:
                issues.setdefault("system_issues", []).append(
                    f"High dead letter queue size: {bus_stats['dead_letter_queue_size']}"
                )

        # Validate communication health
        if self.health_monitor:
            unhealthy_channels = self.health_monitor.get_unhealthy_channels()
            if unhealthy_channels:
                issues["unhealthy_channels"] = unhealthy_channels

        return issues

    # Private implementation methods

    def _initialize_audit_logger(self) -> None:
        """Initialize audit logger."""
        self.audit_logger = AuditLogger(
            log_directory=self.config.audit_log_directory,
            enable_real_time_verification=True,
            testing_mode=(self.config.mode == IntegrationMode.TESTING),
        )
        self.logger.info("Audit logger initialized")

    def _initialize_component_registry(self) -> None:
        """Initialize component registry."""
        self.component_registry = ComponentRegistry(
            heartbeat_timeout_seconds=self.config.heartbeat_timeout_seconds,
            enable_dependency_checking=self.config.enable_dependency_checking,
            enable_health_monitoring=self.config.enable_health_monitoring,
        )
        self.logger.info("Component registry initialized")

    def _initialize_message_bus(self) -> None:
        """Initialize message bus."""
        self.message_bus = MessageBus(
            max_queue_size=self.config.max_queue_size,
            worker_threads=self.config.worker_threads,
            enable_audit_logging=self.config.enable_message_audit,
        )
        self.logger.info("Message bus initialized")

    def _initialize_channel_manager(self) -> None:
        """Initialize channel manager."""
        if self.config.enable_channel_encryption:
            self.channel_manager = SecureChannelOrchestrator()
            self.logger.info("Channel manager initialized")

    def _initialize_health_monitor(self) -> None:
        """Initialize health monitor."""
        self.health_monitor = CommunicationHealthMonitor(
            monitoring_interval_seconds=self.config.monitoring_interval_seconds,
            enable_trend_analysis=self.config.enable_trend_analysis,
        )
        self.logger.info("Health monitor initialized")

    def _setup_integration_callbacks(self) -> None:
        """Set up callbacks between integration components."""
        # Component registry callbacks
        if self.component_registry:
            self.component_registry.add_lifecycle_callback(self._handle_component_lifecycle_change)
            self.component_registry.add_health_callback(self._handle_component_health_change)

        # Health monitor callbacks
        if self.health_monitor:
            self.health_monitor.add_health_callback(self._handle_channel_health_change)
            self.health_monitor.add_alert_callback(self._handle_health_alert)

    def _handle_component_lifecycle_change(
        self, component_name: str, old_status: ComponentStatus, new_status: ComponentStatus
    ) -> None:
        """Handle component lifecycle changes."""
        self.logger.info(f"Component '{component_name}' status: {old_status.value} -> {new_status.value}")

        if self.audit_logger:
            self.audit_logger.log_system_event(
                "component_lifecycle_change",
                {"component_name": component_name, "old_status": old_status.value, "new_status": new_status.value},
            )

    def _handle_component_health_change(self, component_name: str, health_data: Dict[str, Any]) -> None:
        """Handle component health changes."""
        if health_data.get("health_score", 100) < 50:
            self.logger.warning(f"Component '{component_name}' health degraded: {health_data}")

    def _handle_channel_health_change(self, channel_id: str, channel_health: ChannelHealth) -> None:
        """Handle channel health changes."""
        if not channel_health.is_healthy():
            self.logger.warning(f"Channel '{channel_id}' health degraded: {channel_health.status.value}")

    def _handle_health_alert(self, alert_type: str, alert_data: Dict[str, Any]) -> None:
        """Handle health monitoring alerts."""
        self.logger.warning(f"Health alert: {alert_type} - {alert_data}")

        if self.audit_logger:
            self.audit_logger.log_security_event("health_alert", {"alert_type": alert_type, "alert_data": alert_data})

    def _should_use_secure_channel(
        self, source_component: str, target_component: str, message_type: MessageType
    ) -> bool:
        """Determine if secure channel should be used."""
        # Use secure channels for security-sensitive message types
        secure_message_types = {MessageType.SECURITY_ALERT, MessageType.EMERGENCY, MessageType.AUDIT_LOG}

        if message_type in secure_message_types:
            return True

        # Check if components require secure communication
        source_info = self.get_component_info(source_component)
        target_info = self.get_component_info(target_component)

        if source_info and source_info.security_level == "critical":
            return True
        if target_info and target_info.security_level == "critical":
            return True

        return False

    def _send_secure_message(
        self,
        source_component: str,
        target_component: str,
        message_type: MessageType,
        payload: Dict[str, Any],
        priority: MessagePriority,
        timeout_seconds: float,
    ) -> bool:
        """Send message using secure channel."""
        # Get or create secure channel
        component_pair = f"{source_component}_{target_component}"
        channel_id = self._active_channels.get(component_pair)

        if not channel_id:
            channel_id = self.create_secure_channel(source_component, target_component)

        channel = self.channel_manager.get_channel(channel_id)
        if not channel:
            raise CommunicationError(f"Secure channel not found: {channel_id}")

        # Create message
        message = Message(
            type=message_type,
            priority=priority,
            source_component=source_component,
            target_component=target_component,
            payload=payload,
        )

        # Encrypt and send message
        import json

        plaintext = json.dumps(message.to_dict()).encode("utf-8")
        secure_msg = channel.encrypt_message(plaintext, target_component)

        # For now, we'll use the message bus to deliver the encrypted message
        # In a full implementation, this would use a separate secure transport
        encrypted_payload = {"secure_message": secure_msg.to_bytes().hex(), "channel_id": channel_id}

        encrypted_message = Message(
            type=MessageType.COMMAND,
            priority=priority,
            source_component=source_component,
            target_component=target_component,
            payload=encrypted_payload,
        )

        success = self.message_bus.send_message(encrypted_message, timeout_seconds)

        if success and self.health_monitor:
            self.health_monitor.record_message_sent(channel_id)

        return success

    def _send_regular_message(
        self,
        source_component: str,
        target_component: str,
        message_type: MessageType,
        payload: Dict[str, Any],
        priority: MessagePriority,
        timeout_seconds: float,
    ) -> bool:
        """Send message using regular message bus."""
        message = self.message_bus.create_message(
            message_type=message_type,
            source_component=source_component,
            target_component=target_component,
            payload=payload,
            priority=priority,
        )

        success = self.message_bus.send_message(message, timeout_seconds)

        if success:
            self._integration_stats["messages_processed"] += 1

            if self.health_monitor:
                self.health_monitor.record_message_sent(f"{source_component}_{target_component}")

        return success

    def _get_enabled_components(self) -> List[str]:
        """Get list of enabled integration components."""
        enabled = []
        if self.message_bus:
            enabled.append("message_bus")
        if self.component_registry:
            enabled.append("component_registry")
        if self.channel_manager:
            enabled.append("channel_manager")
        if self.health_monitor:
            enabled.append("health_monitor")
        if self.audit_logger:
            enabled.append("audit_logger")
        return enabled

    def _notify_integration_callbacks(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Notify integration event callbacks."""
        for callback in self._integration_callbacks:
            try:
                callback(event_type, event_data)
            except Exception as e:
                self.logger.error(f"Error in integration callback: {e}")

    # Public API for callbacks

    def add_integration_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Add integration event callback."""
        self._integration_callbacks.append(callback)

    def get_integration_statistics(self) -> Dict[str, Any]:
        """Get comprehensive integration statistics."""
        return {
            "integration_stats": self._integration_stats.copy(),
            "system_health": self.get_system_health(),
            "integrity_issues": self.validate_system_integrity(),
            "configuration": {
                "mode": self.config.mode.value,
                "security_level": self.config.default_security_level.value,
                "encryption_enabled": self.config.enable_channel_encryption,
                "health_monitoring_enabled": self.config.enable_health_monitoring,
                "audit_enabled": self.config.enable_comprehensive_audit,
            },
        }
