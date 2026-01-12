#!/usr/bin/env python3

import sys
import logging
sys.path.append('.')

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

from src.failure import FailureDetector, FailureType, FailureSeverity
from tests.property.test_failure_safety import MockFailureDetectableComponent
import time

def test_security_detection():
    """Debug security violation detection."""
    
    # Set up more detailed logging
    logger = logging.getLogger('src.failure.failure_detector')
    logger.setLevel(logging.DEBUG)
    
    detector = FailureDetector()
    
    # Create component
    component = MockFailureDetectableComponent("test_component", is_critical=False)
    detector.register_component("test_component", component, is_critical=False)
    
    # Set up callbacks
    failures = []
    critical_failures = []
    
    def on_failure(failure):
        failures.append(failure)
        print(f"FAILURE DETECTED: {failure.component_name} - {failure.failure_type.value} ({failure.severity.value})")
        print(f"  Message: {failure.error_message}")
        print(f"  Context: {failure.context}")
    
    def on_critical_failure(failure):
        critical_failures.append(failure)
        print(f"CRITICAL FAILURE: {failure.component_name} - {failure.failure_type.value}")
    
    detector.add_failure_callback(on_failure)
    detector.add_critical_failure_callback(on_critical_failure)
    
    detector.start_detection()
    
    print("=== Testing Security Violation ===")
    
    # Trigger security violation
    component.trigger_security_violation()
    
    print(f"Component indicators after security violation: {component.get_failure_indicators()}")
    
    # Test the detection method directly
    print("=== Direct Detection Test ===")
    component_ref = detector._components.get("test_component")
    if component_ref:
        # Check what health monitor returns
        health = detector.health_monitor.get_component_health("test_component")
        print(f"Health monitor result: {health}")
        if health:
            print(f"Health status: {health.status}")
        
        direct_failure = detector._detect_single_component_failure("test_component", component_ref)
        print(f"Direct detection result: {direct_failure}")
        if direct_failure:
            print(f"Direct failure type: {direct_failure.failure_type}")
    
    # Test the analyze method directly
    print("=== Direct Analysis Test ===")
    indicators = component.get_failure_indicators()
    print(f"Indicators: {indicators}")
    try:
        analysis_result = detector._analyze_failure_indicators("test_component", indicators, component)
        print(f"Analysis result: {analysis_result}")
        if analysis_result:
            print(f"Analysis failure type: {analysis_result.failure_type}")
    except Exception as e:
        print(f"Exception in analysis: {e}")
        import traceback
        traceback.print_exc()
    
    # Wait for detection
    time.sleep(1.0)  # Increased wait time
    
    print(f"Failures detected: {len(failures)}")
    print(f"Critical failures detected: {len(critical_failures)}")
    
    # Check if component is registered
    print(f"Registered components: {list(detector._components.keys())}")
    
    # Force a manual detection
    print("=== Manual Detection Test ===")
    active_failures = detector.get_active_failures()
    print(f"Active failures: {active_failures}")
    
    if failures:
        failure = failures[0]
        print(f"First failure type: {failure.failure_type}")
        print(f"Expected: {FailureType.SECURITY_VIOLATION}")
        print(f"Match: {failure.failure_type == FailureType.SECURITY_VIOLATION}")
    else:
        print("No failures detected - this indicates a problem with the detection system")
    
    detector.stop_detection()

if __name__ == "__main__":
    test_security_detection()