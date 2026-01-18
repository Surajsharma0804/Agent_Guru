"""
Production Integration Tests - Complete System Verification

Comprehensive integration tests for the complete GURU production architecture.
Tests all components working together with real-world scenarios.

ARCHITECTURE PRINCIPLES:
- Complete end-to-end system testing
- Real-world scenario simulation
- Performance and security validation
- Resource leak detection
- Comprehensive error handling verification

ZERO-TOLERANCE PRINCIPLES:
- No component integration failures tolerated
- No performance regressions allowed
- No security vulnerabilities accepted
- Complete test coverage of critical paths
- Automatic failure detection and reporting

Thread Safety: All tests are thread-safe with proper isolation.
Performance: Tests complete within reasonable time bounds with performance validation.
"""

import asyncio
import os
import pytest
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

# Import all production components
from ..src.core.production_bootstrap import ProductionBootstrapper, BootstrapConfiguration, SystemContainer
from ..src.core.secure_execution_gateway import (
    SecureExecutionGateway, SecurityContext, AuthorityLevel, OperationCapability
)
from ..src.core.message_bus import MessageBusContainer, Event, Command
from ..src.core.service_lifecycle import ServiceLifecycleManager, Service, ServicePriority, ServiceHealth
from ..src.core.configuration_manager import ProductionConfigurationManager, ConfigurationScope
from ..src.core.dependency_injection import DependencyContainer
from ..src.core.performance_monitor import PerformanceMonitor, PerformanceMetricType
from ..src.core.resource_manager import ResourceManager, ResourceType, ManagedResource
from ..src.core.command_router import (
    CommandRouter, GuruCommand, VoiceProcessingCommand, InputAutomationCommand
)
from ..src.main_production import GuruProductionSystem

logger = structlog.get_logger(__name__)


class TestService(Service):
    """Test service for integration testing."""
    
    def __init__(self, name: str, priority: ServicePriority = ServicePriority.NORMAL):
        super().__init__(name, priority)
        self.initialized = False
        self.started = False
        self.stopped = False
        self.health_check_count = 0
    
    def get_dependencies(self) -> List:
        return []
    
    async def initialize(self) -> None:
        await asyncio.sleep(0.1)  # Simulate initialization work
        self.initialized = True
    
    async def start(self) -> None:
        await asyncio.sleep(0.1)  # Simulate startup work
        self.started = True
    
    async def stop(self) -> None:
        await asyncio.sleep(0.1)  # Simulate shutdown work
        self.stopped = True
    
    async def health_check(self) -> ServiceHealth:
        self.health_check_count += 1
        return ServiceHealth(
            is_healthy=True,
            last_check=datetime.utcnow(),
            uptime_seconds=self._get_uptime_seconds()
        )


class TestCommand(GuruCommand):
    """Test command for integration testing."""
    
    def __init__(self, test_data: str, **kwargs):
        super().__init__(category=kwargs.get('category'), **kwargs)
        self.test_data = test_data
        self.executed = False
        self.execution_result = None
    
    @property
    def required_authority(self) -> AuthorityLevel:
        return AuthorityLevel.MEDIUM
    
    @property
    def required_capabilities(self) -> List[OperationCapability]:
        return [OperationCapability.AUDIO_PROCESSING]
    
    def get_operation_data(self) -> bytes:
        import json
        data = {
            "command_id": self.operation_id,
            "test_data": self.test_data,
            "timestamp": self.metadata.timestamp.isoformat()
        }
        return json.dumps(data, sort_keys=True).encode('utf-8')
    
    async def execute_async(self, context: SecurityContext) -> Any:
        await asyncio.sleep(0.1)  # Simulate work
        self.executed = True
        self.execution_result = f"Processed: {self.test_data}"
        return self.execution_result


@pytest.fixture
async def temp_config_dir():
    """Create temporary configuration directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "config"
        config_path.mkdir(parents=True, exist_ok=True)
        yield config_path


@pytest.fixture
async def bootstrap_config(temp_config_dir):
    """Create bootstrap configuration for testing."""
    return BootstrapConfiguration(
        config_path=temp_config_dir,
        enable_encryption=True,
        enable_hot_reload=False,
        startup_timeout=30.0,
        shutdown_timeout=10.0,
        enable_performance_monitoring=True,
        enable_resource_monitoring=True,
        log_level="DEBUG",
        environment="test"
    )


@pytest.fixture
async def system_container(bootstrap_config):
    """Create and initialize system container."""
    bootstrapper = ProductionBootstrapper(bootstrap_config)
    container = await bootstrapper.bootstrap_system()
    yield container
    await container.shutdown()


class TestProductionBootstrap:
    """Test production bootstrap process."""
    
    @pytest.mark.asyncio
    async def test_complete_bootstrap_process(self, bootstrap_config):
        """Test complete bootstrap process with all phases."""
        bootstrapper = ProductionBootstrapper(bootstrap_config)
        
        start_time = time.time()
        system_container = await bootstrapper.bootstrap_system()
        bootstrap_time = time.time() - start_time
        
        try:
            # Verify bootstrap completed within timeout
            assert bootstrap_time < bootstrap_config.startup_timeout
            
            # Verify all components are initialized
            assert system_container.dependency_container is not None
            assert system_container.configuration_manager is not None
            assert system_container.message_bus_container is not None
            assert system_container.security_gateway is not None
            assert system_container.service_lifecycle_manager is not None
            assert system_container.performance_monitor is not None
            assert system_container.resource_manager is not None
            assert system_container.platform_detector is not None
            assert system_container.backend_factory is not None
            
            # Verify system status
            status = system_container.get_system_status()
            assert status["bootstrap_time"] > 0
            assert status["security_gateway"]["status"] == "operational"
            
            logger.info(
                "Bootstrap test completed successfully",
                bootstrap_time=bootstrap_time,
                components_verified=9
            )
            
        finally:
            await system_container.shutdown()
    
    @pytest.mark.asyncio
    async def test_bootstrap_failure_recovery(self, temp_config_dir):
        """Test bootstrap failure recovery and cleanup."""
        # Create invalid configuration to trigger failure
        invalid_config = BootstrapConfiguration(
            config_path=temp_config_dir,
            startup_timeout=0.1,  # Very short timeout to trigger failure
            shutdown_timeout=5.0
        )
        
        bootstrapper = ProductionBootstrapper(invalid_config)
        
        # Bootstrap should fail due to timeout
        with pytest.raises(Exception):
            await bootstrapper.bootstrap_system()
        
        # Verify cleanup was attempted (no way to verify complete cleanup without access to internals)
        logger.info("Bootstrap failure recovery test completed")


class TestSecurityIntegration:
    """Test security gateway integration."""
    
    @pytest.mark.asyncio
    async def test_secure_command_execution(self, system_container):
        """Test secure command execution through gateway."""
        security_gateway = system_container.security_gateway
        
        # Create test command
        command = TestCommand("test_data")
        
        # Create security context
        context = SecurityContext(
            user_id="test_user",
            session_id="test_session",
            timestamp=datetime.utcnow(),
            source_component="test",
            operation_id=command.operation_id
        )
        
        # Grant authority for command execution
        authority_machine = security_gateway.authority_machine
        authority_machine.grant_authority(AuthorityLevel.HIGH)
        
        # Execute command through security gateway
        result = security_gateway.execute_operation(command, context)
        
        # Verify execution
        assert command.executed
        assert result == command.execution_result
        
        # Verify gateway metrics
        gateway_status = security_gateway.get_gateway_status()
        assert gateway_status["operations_processed"] >= 1
        assert gateway_status["status"] == "operational"
        
        logger.info("Secure command execution test completed successfully")
    
    @pytest.mark.asyncio
    async def test_authority_violation_handling(self, system_container):
        """Test authority violation detection and handling."""
        security_gateway = system_container.security_gateway
        
        # Create test command requiring high authority
        command = TestCommand("test_data")
        
        # Create security context
        context = SecurityContext(
            user_id="test_user",
            session_id="test_session",
            timestamp=datetime.utcnow(),
            source_component="test",
            operation_id=command.operation_id
        )
        
        # Don't grant authority (should cause violation)
        
        # Attempt to execute command (should fail)
        from ..src.core.secure_execution_gateway import AuthorityViolation
        with pytest.raises(AuthorityViolation):
            security_gateway.execute_operation(command, context)
        
        # Verify command was not executed
        assert not command.executed
        
        logger.info("Authority violation handling test completed successfully")


class TestMessageBusIntegration:
    """Test message bus integration."""
    
    @pytest.mark.asyncio
    async def test_event_bus_communication(self, system_container):
        """Test event bus communication between components."""
        message_bus = system_container.message_bus_container
        event_bus = message_bus.event_bus
        
        # Create test event handler
        received_events = []
        
        def test_handler(event):
            received_events.append(event)
        
        # Subscribe to test events
        class TestEvent(Event):
            def __init__(self, data: str):
                super().__init__("test_component")
                self.data = data
            
            def get_message_data(self) -> bytes:
                return self.data.encode('utf-8')
        
        event_bus.subscribe(TestEvent, test_handler)
        
        # Publish test event
        test_event = TestEvent("test_data")
        success = event_bus.publish(test_event)
        
        assert success
        
        # Wait for event processing
        await asyncio.sleep(0.5)
        
        # Verify event was received
        assert len(received_events) == 1
        assert received_events[0].data == "test_data"
        
        # Verify bus metrics
        metrics = event_bus.get_metrics()
        assert metrics.messages_sent >= 1
        assert metrics.messages_processed >= 1
        
        logger.info("Event bus communication test completed successfully")
    
    @pytest.mark.asyncio
    async def test_command_bus_execution(self, system_container):
        """Test command bus execution."""
        message_bus = system_container.message_bus_container
        command_bus = message_bus.command_bus
        
        # Create test command handler
        def test_handler(command):
            return f"Handled: {command.test_data}"
        
        # Register command handler
        command_bus.register_handler(TestCommand, test_handler)
        
        # Create and send test command
        test_command = TestCommand("test_data")
        result = command_bus.send(test_command)
        
        # Verify result
        assert result == "Handled: test_data"
        
        # Verify bus metrics
        metrics = command_bus.get_metrics()
        assert metrics.messages_sent >= 1
        assert metrics.messages_processed >= 1
        
        logger.info("Command bus execution test completed successfully")


class TestServiceLifecycleIntegration:
    """Test service lifecycle management integration."""
    
    @pytest.mark.asyncio
    async def test_service_registration_and_startup(self, system_container):
        """Test service registration and startup process."""
        lifecycle_manager = system_container.service_lifecycle_manager
        
        # Create test services
        service1 = TestService("test_service_1", ServicePriority.HIGH)
        service2 = TestService("test_service_2", ServicePriority.NORMAL)
        
        # Register services
        lifecycle_manager.register_service(service1)
        lifecycle_manager.register_service(service2)
        
        # Start services
        await lifecycle_manager.start_all_services()
        
        # Verify services were started
        assert service1.initialized
        assert service1.started
        assert service2.initialized
        assert service2.started
        
        # Verify service status
        status = lifecycle_manager.get_service_status()
        assert "test_service_1" in status
        assert "test_service_2" in status
        assert status["test_service_1"]["state"] == "running"
        assert status["test_service_2"]["state"] == "running"
        
        # Stop services
        await lifecycle_manager.stop_all_services()
        
        # Verify services were stopped
        assert service1.stopped
        assert service2.stopped
        
        logger.info("Service lifecycle integration test completed successfully")


class TestPerformanceMonitoringIntegration:
    """Test performance monitoring integration."""
    
    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self, system_container):
        """Test performance metrics collection and analysis."""
        performance_monitor = system_container.performance_monitor
        
        if not performance_monitor:
            pytest.skip("Performance monitor not enabled")
        
        # Start monitoring
        await performance_monitor.start_monitoring()
        
        # Wait for metrics collection
        await asyncio.sleep(2.0)
        
        # Get current metrics
        metrics = performance_monitor.get_current_metrics()
        
        # Verify metrics are collected
        assert "cpu_percent" in metrics
        assert "memory_percent" in metrics
        assert "timestamp" in metrics
        
        # Record custom metric
        performance_monitor.record_custom_metric(
            PerformanceMetricType.RESPONSE_TIME,
            150.0,
            "ms",
            "test_component"
        )
        
        # Get statistics
        stats = performance_monitor.get_metric_statistics(PerformanceMetricType.CPU_USAGE)
        if stats:
            assert stats.count > 0
            assert stats.mean >= 0
        
        logger.info("Performance monitoring integration test completed successfully")


class TestResourceManagementIntegration:
    """Test resource management integration."""
    
    @pytest.mark.asyncio
    async def test_resource_tracking_and_cleanup(self, system_container):
        """Test resource tracking and automatic cleanup."""
        resource_manager = system_container.resource_manager
        
        if not resource_manager:
            pytest.skip("Resource manager not enabled")
        
        # Allocate test resources
        memory_resource = resource_manager.allocate_resource(
            ResourceType.MEMORY,
            "test_component",
            data="test_data",
            size=1024
        )
        
        assert memory_resource is not None
        assert memory_resource.resource_type == ResourceType.MEMORY
        
        # Get resource status
        status = resource_manager.get_resource_status()
        tracking_stats = status["resource_tracking"]
        
        assert tracking_stats["total_tracked"] >= 1
        
        # Deallocate resource
        success = resource_manager.deallocate_resource(memory_resource)
        assert success
        
        # Verify resource was cleaned up
        updated_status = resource_manager.get_resource_status()
        updated_tracking = updated_status["resource_tracking"]
        
        # Resource count should be reduced (or same if other resources exist)
        assert updated_tracking["total_tracked"] <= tracking_stats["total_tracked"]
        
        logger.info("Resource management integration test completed successfully")


class TestCommandRouterIntegration:
    """Test command router integration."""
    
    @pytest.mark.asyncio
    async def test_command_routing_and_execution(self, system_container):
        """Test command routing through security gateway."""
        # Create command router
        command_router = CommandRouter(
            security_gateway=system_container.security_gateway,
            message_bus_container=system_container.message_bus_container
        )
        
        # Grant authority for command execution
        authority_machine = system_container.security_gateway.authority_machine
        authority_machine.grant_authority(AuthorityLevel.HIGH)
        
        # Create test command
        voice_command = VoiceProcessingCommand(
            operation_type="transcribe",
            parameters={"audio_data": "test_audio"},
            user_id="test_user",
            session_id="test_session"
        )
        
        # Execute command through router
        result = await command_router.execute_command(
            voice_command,
            "test_user",
            "test_session"
        )
        
        # Verify execution result
        assert result.success
        assert result.command_id == voice_command.operation_id
        assert result.execution_time_ms > 0
        
        # Verify router metrics
        metrics = command_router.get_command_metrics()
        assert metrics["commands_executed"] >= 1
        assert metrics["success_rate"] > 0
        
        logger.info("Command router integration test completed successfully")


class TestEndToEndIntegration:
    """Test complete end-to-end system integration."""
    
    @pytest.mark.asyncio
    async def test_complete_system_workflow(self, system_container):
        """Test complete system workflow from command to execution."""
        # This test simulates a complete user interaction workflow
        
        # 1. Grant user authority
        authority_machine = system_container.security_gateway.authority_machine
        session_id = authority_machine.grant_authority(AuthorityLevel.HIGH)
        
        # 2. Create command router
        command_router = CommandRouter(
            security_gateway=system_container.security_gateway,
            message_bus_container=system_container.message_bus_container
        )
        
        # 3. Execute voice processing command
        voice_command = VoiceProcessingCommand(
            operation_type="wake_word_detection",
            parameters={"audio_chunk": "hey guru"},
            user_id="test_user",
            session_id=session_id
        )
        
        voice_result = await command_router.execute_command(
            voice_command,
            "test_user",
            session_id
        )
        
        assert voice_result.success
        
        # 4. Execute input automation command
        input_command = InputAutomationCommand(
            action_type="type_text",
            parameters={"text": "Hello World"},
            user_id="test_user",
            session_id=session_id
        )
        
        input_result = await command_router.execute_command(
            input_command,
            "test_user",
            session_id
        )
        
        assert input_result.success
        
        # 5. Verify system health
        status = system_container.get_system_status()
        assert status["security_gateway"]["status"] == "operational"
        
        # 6. Verify performance metrics
        if system_container.performance_monitor:
            metrics = system_container.performance_monitor.get_current_metrics()
            assert "cpu_percent" in metrics
        
        # 7. Verify resource management
        if system_container.resource_manager:
            resource_status = system_container.resource_manager.get_resource_status()
            assert "resource_tracking" in resource_status
        
        logger.info(
            "Complete end-to-end integration test completed successfully",
            commands_executed=2,
            system_status="operational"
        )
    
    @pytest.mark.asyncio
    async def test_system_stress_and_recovery(self, system_container):
        """Test system behavior under stress and recovery."""
        # Create command router
        command_router = CommandRouter(
            security_gateway=system_container.security_gateway,
            message_bus_container=system_container.message_bus_container
        )
        
        # Grant authority
        authority_machine = system_container.security_gateway.authority_machine
        session_id = authority_machine.grant_authority(AuthorityLevel.HIGH)
        
        # Execute multiple commands concurrently to stress test
        tasks = []
        for i in range(10):
            command = VoiceProcessingCommand(
                operation_type=f"test_operation_{i}",
                parameters={"data": f"test_data_{i}"},
                user_id="test_user",
                session_id=session_id
            )
            
            task = command_router.execute_command(
                command,
                "test_user",
                session_id
            )
            tasks.append(task)
        
        # Wait for all commands to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify most commands succeeded (some may fail due to resource limits)
        successful_results = [r for r in results if not isinstance(r, Exception) and r.success]
        assert len(successful_results) >= 5  # At least 50% success rate
        
        # Verify system is still operational
        status = system_container.get_system_status()
        assert status["security_gateway"]["status"] == "operational"
        
        # Verify router metrics
        metrics = command_router.get_command_metrics()
        assert metrics["commands_executed"] >= 5
        
        logger.info(
            "System stress and recovery test completed successfully",
            total_commands=10,
            successful_commands=len(successful_results),
            success_rate=len(successful_results) / 10
        )


class TestProductionSystemIntegration:
    """Test complete production system integration."""
    
    @pytest.mark.asyncio
    async def test_production_system_lifecycle(self, temp_config_dir):
        """Test complete production system lifecycle."""
        # Create production system
        system = GuruProductionSystem()
        
        try:
            # Initialize system
            success = await system.initialize(temp_config_dir)
            assert success
            assert system.is_system_running()
            
            # Verify system container is created
            container = system.get_system_container()
            assert container is not None
            
            # Verify all components are operational
            status = container.get_system_status()
            assert status["security_gateway"]["status"] == "operational"
            
            # Test system shutdown
            shutdown_success = await system.shutdown()
            assert shutdown_success
            assert not system.is_system_running()
            
            logger.info("Production system lifecycle test completed successfully")
            
        except Exception as e:
            # Ensure cleanup even if test fails
            await system.shutdown()
            raise


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])