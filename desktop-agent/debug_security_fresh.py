#!/usr/bin/env python3
"""
Fresh debug script to test security violation detection with forced module reload.
"""

import sys
import os
import importlib
import time
import logging

# Clear any cached modules
modules_to_clear = [k for k in sys.modules.keys() if k.startswith('failure')]
for module in modules_to_clear:
    del sys.modules[module]

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import failure.failure_detector
importlib.reload(failure.failure_detector)

from failure.failure_detector import FailureDetector, FailureDetectionConfig, FailureType, FailureSeverity

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

class MockComponent:
    def __init__(self, name: str):
        self.name = name
        self._security_violation = False
        
    def get_failure_indicators(self):
        indicators = {
            "failed": self._security_violation,
            "security_violation": self._security_violation,
            "security_message": "Test security violation"
        } if self._security_violation else {"failed": False}
        print(f"MockComponent.get_failure_indicators() returning: {indicators}")
        return indicators
    
    def is_critical_component(self):
        return True
    
    def trigger_security_violation(self):
        print("MockComponent.trigger_security_violation() called")
        self._security_violation = True

def main():
    print("=== FRESH SECURITY VIOLATION DEBUG TEST ===")
    print(f"Using FailureDetector from: {FailureDetector.__module__}")
    
    # Enable more detailed logging
    logging.getLogger('failure.failure_detector').setLevel(logging.DEBUG)
    
    detector = FailureDetector(
        config=FailureDetectionConfig(detection_interval_seconds=0.1)
    )
    
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
    
    # Create and register component
    component = MockComponent("test-component")
    detector.register_component("test-component", component, is_critical=True)
    
    print("Starting detection...")
    detector.start_detection()
    
    # Wait a bit
    time.sleep(0.2)
    
    print("Triggering security violation...")
    component.trigger_security_violation()
    
    # Wait for detection
    time.sleep(0.5)
    
    print(f"\nResults:")
    print(f"Total failures detected: {len(failures)}")
    print(f"Critical failures detected: {len(critical_failures)}")
    
    if failures:
        failure = failures[0]
        print(f"First failure type: {failure.failure_type.value}")
        print(f"Expected: {FailureType.SECURITY_VIOLATION.value}")
        print(f"Match: {failure.failure_type == FailureType.SECURITY_VIOLATION}")
    else:
        print("No failures detected!")
    
    detector.stop_detection()

if __name__ == "__main__":
    main()