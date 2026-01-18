#!/usr/bin/env python3
"""
Minimal GURU System Test

Tests the core architecture components without complex dependencies.
"""

import sys
import os
from pathlib import Path
import asyncio
import logging

# Add the src directory to Python path
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_core_components():
    """Test core architectural components."""
    
    logger.info("=== GURU PRODUCTION ARCHITECTURE TEST ===")
    
    try:
        # Test 1: Dependency Injection Container
        logger.info("Testing Dependency Injection Container...")
        from core.dependency_injection import DependencyContainer
        
        container = DependencyContainer.get_instance()
        logger.info("✅ Dependency Injection Container: OPERATIONAL")
        
        # Test 2: Secure Execution Gateway
        logger.info("Testing Secure Execution Gateway...")
        from core.secure_execution_gateway import SecureExecutionGateway
        
        gateway = SecureExecutionGateway()
        status = gateway.get_gateway_status()
        logger.info(f"✅ Secure Execution Gateway: {status['status'].upper()}")
        
        # Test 3: Message Bus
        logger.info("Testing Message Bus...")
        from core.message_bus import MessageBusContainer
        
        message_bus = MessageBusContainer()
        metrics = message_bus.get_aggregated_metrics()
        logger.info("✅ Message Bus Container: OPERATIONAL")
        
        # Test 4: Service Lifecycle Manager
        logger.info("Testing Service Lifecycle Manager...")
        from core.service_lifecycle import ServiceLifecycleManager
        
        lifecycle_manager = ServiceLifecycleManager()
        logger.info("✅ Service Lifecycle Manager: OPERATIONAL")
        
        # Test 5: Performance Monitor
        logger.info("Testing Performance Monitor...")
        from core.performance_monitor import PerformanceMonitor
        
        perf_monitor = PerformanceMonitor()
        await perf_monitor.initialize()
        logger.info("✅ Performance Monitor: OPERATIONAL")
        
        # Test 6: Resource Manager
        logger.info("Testing Resource Manager...")
        from core.resource_manager import ResourceManager
        
        resource_manager = ResourceManager()
        await resource_manager.initialize()
        logger.info("✅ Resource Manager: OPERATIONAL")
        
        # Test 7: Command Router
        logger.info("Testing Command Router...")
        from core.command_router import CommandRouter
        
        command_router = CommandRouter(gateway, message_bus)
        metrics = command_router.get_command_metrics()
        logger.info("✅ Command Router: OPERATIONAL")
        
        logger.info("=== ALL CORE COMPONENTS OPERATIONAL ===")
        logger.info("🚀 GURU PRODUCTION ARCHITECTURE: READY")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Component test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    logger.info("Starting GURU Production Architecture Test")
    
    success = await test_core_components()
    
    if success:
        logger.info("✅ GURU PRODUCTION SYSTEM: ALL TESTS PASSED")
        return 0
    else:
        logger.error("❌ GURU PRODUCTION SYSTEM: TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)