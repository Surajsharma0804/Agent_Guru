"""
Unit Tests for Communication Integration Layer

Comprehensive test suite for the GURU communication system integration layer.
Tests component registration, message passing, secure channels, and health monitoring.
"""

import pytest
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch, MagicMock

from src.communication.integration_layer import (
    ComponentIntegrationLayer,
    IntegrationConfig,
    IntegrationMode
)
from src.communication.message_bus import Message, MessageType, MessagePriority, MessageHandler
from src.communication.component_registry import ComponentInfo, ComponentType, ComponentStatus, ComponentLifecycle
from src.communication.secure_channel import ChannelSecurity, EncryptionMode
from src.communication.exceptions import (
    CommunicationError,
    ComponentNotFoundError,
    RegistrationError
)


class MockComponent(MessageHandler, ComponentLifecycle):
    """Mock component for testing."""
    
    def __init__(self, name: str):
        self.name = name
        self.initialized = False
        self.started = False
        self.stopped = False
        self.messages_received = []
        self.health_status = {"status": "healthy", "health_score": 100.0}
    
    def handle_message(self, message: Message) -> Optional[Message]:
        """Handle incoming message."""
        self.messages_received.append(message)
        
        # Return response for query messages
        if message.type == MessageType.QUERY:
            return Message(
                type=MessageType.RESPONSE,
                source_component=self.name,
                target_component=message.source_component,
                payload={"response": f"Response from {self.name}"}
            )
        
        return None
    
    def initialize(self) -> bool:
        """Initialize component."""
        self.initialized = True
        return True
    
    def start(self) -> bool:
        """Start component."""
        if not self.initialized:
            return False
        self.started = True
        return True
    
    def stop(self) -> bool:
        """Stop component."""
        self.stopped = True
        self.started = False
        return True
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        return self.health_status


class TestComponentIntegrationLayer:
    """Test suite for ComponentIntegrationLayer."""
    
    def _wait_for_messages(self, component, expected_count: int = 1, timeout: float = 5.0) -> None:
        """Wait for messages to be received by component with timeout."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if len(component.messages_received) >= expected_count:
                return
            time.sleep(0.01)
        
        # If we get here, timeout occurred
        actual_count = len(component.messages_received)
        raise AssertionError(
            f"Expected {expected_count} messages, got {actual_count} after {timeout} seconds"
        )
    
    @pytest.fixture
    def integration_config(self):
        """Create test integration configuration."""
        return IntegrationConfig(
            mode=IntegrationMode.TESTING,
            max_queue_size=100,
            worker_threads=2,
            enable_comprehensive_audit=False,  # Disable for testing
            monitoring_interval_seconds=0.1
        )
    
    @pytest.fixture
    def integration_layer(self, integration_config):
        """Create integration layer for testing."""
        layer = ComponentIntegrationLayer(integration_config)
        yield layer
        # Cleanup
        if layer._running:
            layer.stop()
    
    @pytest.fixture
    def mock_components(self):
        """Create mock components for testing."""
        return {
            "component_a": MockComponent("component_a"),
            "component_b": MockComponent("component_b"),
            "component_c": MockComponent("component_c")
        }
    
    def test_initialization(self, integration_layer):
        """Test integration layer initialization."""
        assert not integration_layer._initialized
        assert not integration_layer._running
        
        integration_layer.initialize()
        
        assert integration_layer._initialized
        assert integration_layer.message_bus is not None
        assert integration_layer.component_registry is not None
        assert integration_layer.health_monitor is not None
        # Channel manager and audit logger may be None in testing mode
    
    def test_start_stop(self, integration_layer):
        """Test integration layer start and stop."""
        integration_layer.initialize()
        
        assert not integration_layer._running
        
        integration_layer.start()
        assert integration_layer._running
        
        integration_layer.stop()
        assert not integration_layer._running
    
    def test_component_registration(self, integration_layer, mock_components):
        """Test component registration."""
        integration_layer.initialize()
        integration_layer.start()
        
        component_a = mock_components["component_a"]
        
        # Register component
        integration_layer.register_component(
            component_name="component_a",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_a,
            version="1.0.0",
            description="Test component A",
            trusted=True,
            lifecycle_handler=component_a
        )
        
        # Verify registration
        assert "component_a" in integration_layer._registered_components
        assert integration_layer._integration_stats["components_registered"] == 1
        
        # Check component info
        component_info = integration_layer.get_component_info("component_a")
        assert component_info is not None
        assert component_info.name == "component_a"
        assert component_info.component_type == ComponentType.CORE_SERVICE
        assert component_info.trusted is True
    
    def test_component_unregistration(self, integration_layer, mock_components):
        """Test component unregistration."""
        integration_layer.initialize()
        integration_layer.start()
        
        component_a = mock_components["component_a"]
        
        # Register and then unregister
        integration_layer.register_component(
            component_name="component_a",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_a
        )
        
        assert "component_a" in integration_layer._registered_components
        
        integration_layer.unregister_component("component_a")
        
        assert "component_a" not in integration_layer._registered_components
        assert integration_layer.get_component_info("component_a") is None
    
    def test_message_sending(self, integration_layer, mock_components):
        """Test message sending between components."""
        integration_layer.initialize()
        integration_layer.start()
        
        component_a = mock_components["component_a"]
        component_b = mock_components["component_b"]
        
        # Register components
        integration_layer.register_component(
            component_name="component_a",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_a
        )
        integration_layer.register_component(
            component_name="component_b",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_b
        )
        
        # Send message
        success = integration_layer.send_message(
            source_component="component_a",
            target_component="component_b",
            message_type=MessageType.COMMAND,
            payload={"test": "data"},
            priority=MessagePriority.NORMAL
        )
        
        assert success
        
        # Wait for message processing with proper synchronization
        self._wait_for_messages(component_b, expected_count=1)
        
        # Verify message was received
        received_message = component_b.messages_received[0]
        assert received_message.source_component == "component_a"
        assert received_message.target_component == "component_b"
        assert received_message.payload["test"] == "data"
    
    def test_secure_channel_creation(self, integration_layer, mock_components):
        """Test secure channel creation."""
        # Enable channel encryption for this test
        integration_layer.config.enable_channel_encryption = True
        integration_layer.initialize()
        integration_layer.start()
        
        component_a = mock_components["component_a"]
        component_b = mock_components["component_b"]
        
        # Register components
        integration_layer.register_component(
            component_name="component_a",
            component_type=ComponentType.SECURITY_SERVICE,
            component_ref=component_a,
            security_level="critical"
        )
        integration_layer.register_component(
            component_name="component_b",
            component_type=ComponentType.SECURITY_SERVICE,
            component_ref=component_b,
            security_level="critical"
        )
        
        # Create secure channel
        channel_id = integration_layer.create_secure_channel(
            local_component="component_a",
            remote_component="component_b",
            security_level=ChannelSecurity.HIGH
        )
        
        assert channel_id is not None
        assert channel_id in integration_layer.channel_manager.get_all_channels()
        assert integration_layer._integration_stats["channels_created"] == 1
    
    def test_component_lifecycle_management(self, integration_layer, mock_components):
        """Test component lifecycle management."""
        integration_layer.initialize()
        integration_layer.start()
        
        component_a = mock_components["component_a"]
        
        # Register component with lifecycle handler
        integration_layer.register_component(
            component_name="component_a",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_a,
            lifecycle_handler=component_a
        )
        
        # Test component lifecycle
        assert integration_layer.component_registry.start_component("component_a")
        assert component_a.initialized
        assert component_a.started
        
        assert integration_layer.component_registry.stop_component("component_a")
        assert component_a.stopped
        assert not component_a.started
    
    def test_health_monitoring(self, integration_layer, mock_components):
        """Test health monitoring integration."""
        integration_layer.initialize()
        integration_layer.start()
        
        component_a = mock_components["component_a"]
        
        # Register component
        integration_layer.register_component(
            component_name="component_a",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_a
        )
        
        # Wait for health monitoring to start
        time.sleep(0.2)
        
        # Check health monitoring
        health_info = integration_layer.get_system_health()
        assert "communication_health" in health_info
        assert health_info["registered_components"] == 1
    
    def test_system_health_reporting(self, integration_layer, mock_components):
        """Test comprehensive system health reporting."""
        integration_layer.initialize()
        integration_layer.start()
        
        component_a = mock_components["component_a"]
        
        # Register component
        integration_layer.register_component(
            component_name="component_a",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_a
        )
        
        # Get system health
        health = integration_layer.get_system_health()
        
        assert "integration_layer" in health
        assert "statistics" in health
        assert "registered_components" in health
        assert health["integration_layer"]["initialized"] is True
        assert health["integration_layer"]["running"] is True
        assert health["registered_components"] == 1
    
    def test_system_integrity_validation(self, integration_layer, mock_components):
        """Test system integrity validation."""
        integration_layer.initialize()
        integration_layer.start()
        
        component_a = mock_components["component_a"]
        component_b = mock_components["component_b"]
        
        # Register components with dependencies
        integration_layer.register_component(
            component_name="component_a",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_a
        )
        integration_layer.register_component(
            component_name="component_b",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_b,
            dependencies={"component_a"}
        )
        
        # Validate system integrity
        issues = integration_layer.validate_system_integrity()
        
        # Should have no issues with properly registered dependencies
        assert len(issues) == 0 or "dependency_issues" not in issues
    
    def test_error_handling(self, integration_layer):
        """Test error handling in integration layer."""
        # Test operations before initialization
        with pytest.raises(CommunicationError):
            integration_layer.register_component(
                component_name="test",
                component_type=ComponentType.CORE_SERVICE,
                component_ref=Mock()
            )
        
        integration_layer.initialize()
        integration_layer.start()
        
        # Test sending message to non-existent component
        with pytest.raises(CommunicationError):
            integration_layer.send_message(
                source_component="non_existent",
                target_component="also_non_existent",
                message_type=MessageType.COMMAND,
                payload={}
            )
    
    def test_duplicate_component_registration(self, integration_layer, mock_components):
        """Test handling of duplicate component registration."""
        integration_layer.initialize()
        integration_layer.start()
        
        component_a = mock_components["component_a"]
        
        # Register component
        integration_layer.register_component(
            component_name="component_a",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_a
        )
        
        # Try to register same component again
        with pytest.raises(RegistrationError):
            integration_layer.register_component(
                component_name="component_a",
                component_type=ComponentType.CORE_SERVICE,
                component_ref=component_a
            )
    
    def test_message_priority_handling(self, integration_layer, mock_components):
        """Test message priority handling."""
        integration_layer.initialize()
        integration_layer.start()
        
        component_a = mock_components["component_a"]
        component_b = mock_components["component_b"]
        
        # Register components
        integration_layer.register_component(
            component_name="component_a",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_a
        )
        integration_layer.register_component(
            component_name="component_b",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_b
        )
        
        # Send high priority message
        success = integration_layer.send_message(
            source_component="component_a",
            target_component="component_b",
            message_type=MessageType.EMERGENCY,
            payload={"urgent": "data"},
            priority=MessagePriority.EMERGENCY
        )
        
        assert success
        
        # Wait for processing with proper synchronization
        self._wait_for_messages(component_b, expected_count=1)
        
        # Verify message was received
        received_message = component_b.messages_received[0]
        assert received_message.priority == MessagePriority.EMERGENCY
    
    def test_component_discovery(self, integration_layer, mock_components):
        """Test component discovery functionality."""
        integration_layer.initialize()
        integration_layer.start()
        
        component_a = mock_components["component_a"]
        component_b = mock_components["component_b"]
        
        # Register components of different types
        integration_layer.register_component(
            component_name="component_a",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_a
        )
        integration_layer.register_component(
            component_name="component_b",
            component_type=ComponentType.SECURITY_SERVICE,
            component_ref=component_b
        )
        
        # Test component discovery
        all_components = integration_layer.get_all_components()
        assert len(all_components) == 2
        assert "component_a" in all_components
        assert "component_b" in all_components
        
        # Test discovery by type
        core_services = integration_layer.get_components_by_type(ComponentType.CORE_SERVICE)
        assert len(core_services) == 1
        assert core_services[0].name == "component_a"
        
        security_services = integration_layer.get_components_by_type(ComponentType.SECURITY_SERVICE)
        assert len(security_services) == 1
        assert security_services[0].name == "component_b"
    
    def test_integration_statistics(self, integration_layer, mock_components):
        """Test integration statistics collection."""
        integration_layer.initialize()
        integration_layer.start()
        
        component_a = mock_components["component_a"]
        component_b = mock_components["component_b"]
        
        # Register components
        integration_layer.register_component(
            component_name="component_a",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_a
        )
        integration_layer.register_component(
            component_name="component_b",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_b
        )
        
        # Send some messages
        integration_layer.send_message(
            source_component="component_a",
            target_component="component_b",
            message_type=MessageType.COMMAND,
            payload={"test": "data"}
        )
        
        # Wait for processing with proper synchronization
        self._wait_for_messages(component_b, expected_count=1)
        
        # Get statistics
        stats = integration_layer.get_integration_statistics()
        
        assert "integration_stats" in stats
        assert "system_health" in stats
        assert "configuration" in stats
        assert stats["integration_stats"]["components_registered"] == 2
        assert stats["integration_stats"]["messages_processed"] >= 1
    
    def test_concurrent_operations(self, integration_layer, mock_components):
        """Test concurrent operations on integration layer."""
        integration_layer.initialize()
        integration_layer.start()
        
        components = [mock_components[f"component_{c}"] for c in ["a", "b", "c"]]
        
        def register_component(comp, index):
            integration_layer.register_component(
                component_name=f"component_{chr(ord('a') + index)}",
                component_type=ComponentType.CORE_SERVICE,
                component_ref=comp
            )
        
        # Register components concurrently
        threads = []
        for i, comp in enumerate(components):
            thread = threading.Thread(target=register_component, args=(comp, i))
            threads.append(thread)
            thread.start()
        
        # Wait for all registrations
        for thread in threads:
            thread.join()
        
        # Verify all components registered
        all_components = integration_layer.get_all_components()
        assert len(all_components) == 3
        assert integration_layer._integration_stats["components_registered"] == 3
    
    def test_configuration_modes(self):
        """Test different integration configuration modes."""
        # Test development mode
        dev_config = IntegrationConfig(mode=IntegrationMode.DEVELOPMENT)
        dev_layer = ComponentIntegrationLayer(dev_config)
        assert dev_layer.config.mode == IntegrationMode.DEVELOPMENT
        
        # Test production mode
        prod_config = IntegrationConfig(mode=IntegrationMode.PRODUCTION)
        prod_layer = ComponentIntegrationLayer(prod_config)
        assert prod_layer.config.mode == IntegrationMode.PRODUCTION
        assert prod_layer.config.enable_comprehensive_audit is True
        assert prod_layer.config.enable_channel_encryption is True
        
        # Cleanup
        if dev_layer._running:
            dev_layer.stop()
        if prod_layer._running:
            prod_layer.stop()


class TestMessageBusIntegration:
    """Test message bus integration specifically."""
    
    def _wait_for_messages(self, component, expected_count: int = 1, timeout: float = 5.0) -> None:
        """Wait for messages to be received by component with timeout."""
        import time
        start_time = time.time()
        while time.time() - start_time < timeout:
            if len(component.messages_received) >= expected_count:
                return
            time.sleep(0.01)
        
        # If we get here, timeout occurred
        actual_count = len(component.messages_received)
        raise AssertionError(
            f"Expected {expected_count} messages, got {actual_count} after {timeout} seconds"
        )
    
    @pytest.fixture
    def integration_layer(self):
        """Create integration layer for message bus testing."""
        config = IntegrationConfig(
            mode=IntegrationMode.TESTING,
            enable_comprehensive_audit=False
        )
        layer = ComponentIntegrationLayer(config)
        layer.initialize()
        layer.start()
        yield layer
        layer.stop()
    
    def test_message_bus_statistics(self, integration_layer):
        """Test message bus statistics integration."""
        component_a = MockComponent("component_a")
        component_b = MockComponent("component_b")
        
        # Register components
        integration_layer.register_component(
            component_name="component_a",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_a
        )
        integration_layer.register_component(
            component_name="component_b",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_b
        )
        
        # Send messages
        for i in range(5):
            integration_layer.send_message(
                source_component="component_a",
                target_component="component_b",
                message_type=MessageType.COMMAND,
                payload={"message": i}
            )
        
        # Wait for processing with proper synchronization
        self._wait_for_messages(component_b, expected_count=5)
        
        # Check message bus statistics
        health = integration_layer.get_system_health()
        bus_stats = health.get("message_bus", {})
        
        assert bus_stats.get("registered_components", 0) >= 2
        assert bus_stats.get("running", False) is True
    
    def test_dead_letter_queue_handling(self, integration_layer):
        """Test dead letter queue integration."""
        component_a = MockComponent("component_a")
        
        # Register only source component (target doesn't exist)
        integration_layer.register_component(
            component_name="component_a",
            component_type=ComponentType.CORE_SERVICE,
            component_ref=component_a
        )
        
        # Try to send message to non-existent component
        with pytest.raises(CommunicationError):
            integration_layer.send_message(
                source_component="component_a",
                target_component="non_existent",
                message_type=MessageType.COMMAND,
                payload={"test": "data"}
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])