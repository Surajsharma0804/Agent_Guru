#!/usr/bin/env python3

import sys
sys.path.append('.')

# Fresh import without any caching
from src.failure.failure_detector import FailureDetector, FailureType, FailureSeverity
from datetime import datetime

# Create detector
detector = FailureDetector()

# Test data
indicators = {
    'failed': True,
    'security_violation': True,
    'security_message': 'Test security violation'
}

class MockComponent:
    def is_critical_component(self):
        return False

component = MockComponent()

print("=== Fresh Test - Security Violation Detection ===")
print(f"Input indicators: {indicators}")

# Call the method
result = detector._analyze_failure_indicators("test_component", indicators, component)

print(f"Result: {result}")
if result:
    print(f"Failure type: {result.failure_type}")
    print(f"Expected: {FailureType.SECURITY_VIOLATION}")
    print(f"Match: {result.failure_type == FailureType.SECURITY_VIOLATION}")
    
    if result.failure_type == FailureType.SECURITY_VIOLATION:
        print("✅ SUCCESS: Security violation correctly detected!")
    else:
        print("❌ FAILURE: Security violation not detected correctly")
else:
    print("❌ FAILURE: No result returned")