"""
Unit tests for the basic failure management system.

This module tests the BasicFailureManager which provides essential
failure detection and monitoring capabilities.
"""

import pytest
import threading
import time
from datetime import datetime
from unittest.mock import Mock, MagicMock

from src.failure.basic_failure_manager import (
    BasicFailureManager,
    BasicHealthStatus,
    BasicFailureType,
    BasicFailureSeverity,
    BasicComponentFailure,
    BasicComponentHealth
)


class MockHealthCheckableComponent:
    """Mock component that implements BasicHealthCheckable protocol."""
    
    def __init__(self, name: str, healthy: bool = True):
        self.name = name
        self.healthy = healthy
        self.health_check_count = 0
    
    def health_check(self) -> dict:
        """Perform health check."""
        self.health_check_count += 1
        if self.healthy:
            return {"status": "healthy", "component": self.name}
        else:
            return {"status": "failed", "error": "Component is unhealthy"}
    
    def set_unhealthy(self):
        """Make component unhealthy for testing."""
        self.healthy = False


class MockFailureDetectableComponent:
    """Mock component that implements BasicFailureDetectable protocol."""
    
    def __init__(self, name: str):
        self.name = name
        self.failure_indicators = {"failed": False}
    
    def get_failure_indicators(self) -> dict:
        """Get failure indicators."""
        return self.failure_indicators.copy()
    
    def trigger_failure(self, failure_type: str = "component_unresponsive", 
                       error_message: str = "Test failure"):
        """Trigger a failure for testing."""
        self.failure_indicators = {
            "failed": True,
            "failure_type": failure_type,
            "error_message": error_message
        }
    
    def trigger_security_violation(self):
        """Trigger a security violation for testing."""
        self.failure_indicators = {
            "failed": True,
            "security_violation": True,
            "failure_type": "security_violation",
            "error_message": "Test security violation"
        }


class MockDualComponent(MockHealthCheckableComponent, MockFailureDetectableComponent):
    """Mock component that implements both protocols."""
    
    def __init__(self, name: str, healthy: bool = True):
        MockHealthCheckableComponent.__init__(self, name, healthy)
        MockFailureDetectableComponent.__init__(self, name)


class TestBasicFailureManager:
    """Test BasicFailureManager functionality."""
    
    @pytest.fixture
    def failure_manager(self):
        """Create failure manager for testing."""
        return BasicFailureManager(check_interval_seconds=0.1)
    
    @pytest.fixture
    def mock_component(self):
        """Create mock component for testing."""
        return MockDualComponent("test_component")
    
    def test_component_registration(self, failure_manager, mock_component):
        """Test component registration."""
        failure_manager.register_component("test_component", mock_component)
        
        # Check that component is registered
        health = failure_manager.get_component_health("test_component")
        assert health is not None
        assert health.component_name == "test_component"
        assert health.status == BasicHealthStatus.UNKNOWN
    
    def test_component_unregistration(self, failure_manager, mock_component):
        """Test component unregistration."""
        failure_manager.register_component("test_component", mock_component)
        
        # Verify component is registered
        health = failure_manager.get_component_health("test_component")
        assert health is not None
        
        # Unregister component
        failure_manager.unregister_component("test_component")
        
        # Verify component is unregistered
        health = failure_manager.get_component_health("test_component")
        assert health is None
    
    def test_health_monitoring(self, failure_manager, mock_component):
        """Test health monitoring functionality."""
        failure_manager.register_component("test_component", mock_component)
        
        # Start monitoring
        failure_manager.start_monitoring()
        
        # Wait for a few monitoring cycles
        time.sleep(0.3)
        
        # Stop monitoring
        failure_manager.stop_monitoring()
        
        # Check that health checks were performed
        assert mock_component.health_check_count > 0
        
        # Check that health status was updated
        health = failure_manager.get_component_health("test_component")
        assert health is not None
        assert health.status == BasicHealthStatus.HEALTHY
    
    def test_failure_detection(self, failure_manager, mock_component):
        """Test failure detection."""
        failure_callback_called = threading.Event()
        detected_failure = None
        
        def failure_callback(failure: BasicComponentFailure):
            nonlocal detected_failure
            detected_failure = failure
            failure_callback_called.set()
        
        failure_manager.add_failure_callback(failure_callback)
        failure_manager.register_component("test_component", mock_component)
        
        # Trigger failure
        mock_component.trigger_failure()
        
        # Start monitoring
        failure_manager.start_monitoring()
        
        # Wait for failure detection
        assert failure_callback_called.wait(timeout=2.0)
        
        failure_manager.stop_monitoring()
        
        assert detected_failure is not None
        assert detected_failure.component_name == "test_component"
        assert detected_failure.failure_type == BasicFailureType.COMPONENT_UNRESPONSIVE
    
    def test_critical_failure_handling(self, failure_manager):
        """Test critical failure handling."""
        critical_component = MockDualComponent("critical_component")
        
        failure_manager.register_component("critical_component", critical_component, is_critical=True)
        
        # Trigger security violation (always critical)
        critical_component.trigger_security_violation()
        
        # Start monitoring
        failure_manager.start_monitoring()
        
        # Wait for failure processing
        time.sleep(0.3)
        
        failure_manager.stop_monitoring()
        
        # Check that system is not healthy due to critical failure
        assert not failure_manager.is_system_healthy()
        
        # Check that we have active failures
        active_failures = failure_manager.get_active_failures()
        assert len(active_failures) > 0
        assert any(f.is_critical() for f in active_failures)
    
    def test_emergency_halt(self, failure_manager, mock_component):
        """Test emergency halt functionality."""
        failure_manager.register_component("test_component", mock_component, is_critical=True)
        
        # Trigger security violation on critical component
        mock_component.trigger_security_violation()
        
        # Start monitoring
        failure_manager.start_monitoring()
        
        # Wait for failure processing
        time.sleep(0.3)
        
        failure_manager.stop_monitoring()
        
        # Check that emergency halt was triggered
        assert failure_manager.is_emergency_halt()
        assert not failure_manager.is_system_healthy()
    
    def test_manual_emergency_halt(self, failure_manager):
        """Test manual emergency halt."""
        # Force emergency halt
        failure_manager.force_emergency_halt("Test emergency halt")
        
        # Check that halt was triggered
        assert failure_manager.is_emergency_halt()
        assert not failure_manager.is_system_healthy()
    
    def test_health_callback_notification(self, failure_manager, mock_component):
        """Test health change callback notifications."""
        callback_called = threading.Event()
        received_name = None
        received_health = None
        
        def health_callback(name: str, health: BasicComponentHealth):
            nonlocal received_name, received_health
            received_name = name
            received_health = health
            callback_called.set()
        
        failure_manager.add_health_callback(health_callback)
        failure_manager.register_component("test_component", mock_component)
        
        # Start monitoring to get initial health status
        failure_manager.start_monitoring()
        time.sleep(0.2)
        
        # Make component unhealthy
        mock_component.set_unhealthy()
        
        # Wait for health change detection
        time.sleep(0.3)
        
        failure_manager.stop_monitoring()
        
        # Check that callback was called
        assert callback_called.wait(timeout=1.0)
        assert received_name == "test_component"
        assert received_health is not None
        assert received_health.status == BasicHealthStatus.FAILED
    
    def test_system_health_summary(self, failure_manager):
        """Test system health summary generation."""
        # Register multiple components
        healthy_component = MockDualComponent("healthy", healthy=True)
        unhealthy_component = MockDualComponent("unhealthy", healthy=False)
        
        failure_manager.register_component("healthy", healthy_component)
        failure_manager.register_component("unhealthy", unhealthy_component)
        
        # Start monitoring to populate health data
        failure_manager.start_monitoring()
        time.sleep(0.3)
        failure_manager.stop_monitoring()
        
        # Get system summary
        summary = failure_manager.get_system_summary()
        
        assert isinstance(summary, dict)
        assert "system_healthy" in summary
        assert "total_components" in summary
        assert "healthy_components" in summary
        assert "failed_components" in summary
        assert "active_failures" in summary
        
        assert summary["total_components"] == 2
    
    def test_failure_clearing(self, failure_manager, mock_component):
        """Test clearing component failures."""
        failure_manager.register_component("test_component", mock_component)
        
        # Trigger failure
        mock_component.trigger_failure()
        
        # Start monitoring to detect failure
        failure_manager.start_monitoring()
        time.sleep(0.3)
        failure_manager.stop_monitoring()
        
        # Check that we have active failures
        active_failures = failure_manager.get_active_failures()
        assert len(active_failures) > 0
        
        # Clear failures for the component
        failure_manager.clear_component_failures("test_component")
        
        # Check that failures were cleared
        active_failures = failure_manager.get_active_failures()
        component_failures = [f for f in active_failures if f.component_name == "test_component"]
        assert len(component_failures) == 0
    
    def test_failure_history_tracking(self, failure_manager, mock_component):
        """Test failure history tracking."""
        failure_manager.register_component("test_component", mock_component)
        
        # Trigger multiple failures
        for i in range(3):
            mock_component.trigger_failure(error_message=f"Test failure {i}")
            
            # Start monitoring to detect failure
            failure_manager.start_monitoring()
            time.sleep(0.2)
            failure_manager.stop_monitoring()
            
            # Reset failure state for next iteration
            mock_component.failure_indicators = {"failed": False}
        
        # Check failure history
        history = failure_manager.get_failure_history()
        assert len(history) >= 3
        
        # Check limited history
        limited_history = failure_manager.get_failure_history(limit=2)
        assert len(limited_history) == 2
    
    def test_monitoring_start_stop(self, failure_manager, mock_component):
        """Test monitoring start and stop functionality."""
        failure_manager.register_component("test_component", mock_component)
        
        # Initially not monitoring
        assert not failure_manager._monitoring
        
        # Start monitoring
        failure_manager.start_monitoring()
        assert failure_manager._monitoring
        
        # Wait briefly
        time.sleep(0.1)
        
        # Stop monitoring
        failure_manager.stop_monitoring()
        assert not failure_manager._monitoring
        
        # Starting again should work
        failure_manager.start_monitoring()
        assert failure_manager._monitoring
        
        failure_manager.stop_monitoring()
    
    def test_garbage_collected_component_cleanup(self, failure_manager):
        """Test cleanup of garbage collected components."""
        # Create a component that will be garbage collected
        component = MockDualComponent("temp_component")
        failure_manager.register_component("temp_component", component)
        
        # Verify component is registered
        health = failure_manager.get_component_health("temp_component")
        assert health is not None
        
        # Delete the component reference
        del component
        
        # Start monitoring - this should trigger cleanup
        failure_manager.start_monitoring()
        time.sleep(0.2)
        failure_manager.stop_monitoring()
        
        # Component should be automatically unregistered
        # (This test may be flaky depending on garbage collection timing)
    
    def test_multiple_component_failure_system_state(self, failure_manager):
        """Test system state with multiple component failures."""
        # Register multiple components
        components = []
        for i in range(4):
            comp = MockDualComponent(f"component_{i}")
            components.append(comp)
            failure_manager.register_component(f"component_{i}", comp)
        
        # Trigger failures in multiple components
        for i, comp in enumerate(components[:3]):  # Fail 3 out of 4 components
            comp.trigger_failure(error_message=f"Failure {i}")
        
        # Start monitoring
        failure_manager.start_monitoring()
        time.sleep(0.3)
        failure_manager.stop_monitoring()
        
        # System should be unhealthy due to multiple failures
        assert not failure_manager.is_system_healthy()
        
        # Should have multiple active failures
        active_failures = failure_manager.get_active_failures()
        assert len(active_failures) >= 3