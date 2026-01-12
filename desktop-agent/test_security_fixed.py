#!/usr/bin/env python3

import sys
sys.path.append('.')

from src.failure.failure_detector_fixed import SecurityFirstFailureDetector
from src.failure.failure_detector import FailureType, FailureSeverity
from datetime import datetime

print("=== TESTING SECURITY-FIRST FAILURE DETECTOR ===")

# Create the corrected detector
detector = SecurityFirstFailureDetector()

# Test data with both failed and security_violation
indicators = {
    'failed': True,
    'security_violation': True,
    'security_message': 'Test security violation'
}

class MockComponent:
    def is_critical_component(self):
        return False

component = MockComponent()

print(f"Input indicators: {indicators}")

# Test the corrected method
result = detector.analyze_failure_indicators_security_first("test_component", indicators, component)

print(f"Result: {result}")
if result:
    print(f"Failure type: {result.failure_type}")
    print(f"Expected: {FailureType.SECURITY_VIOLATION}")
    print(f"Match: {result.failure_type == FailureType.SECURITY_VIOLATION}")
    
    if result.failure_type == FailureType.SECURITY_VIOLATION:
        print("✅ SUCCESS: Security violation correctly detected with HIGHEST priority!")
        print(f"   Severity: {result.severity}")
        print(f"   Message: {result.error_message}")
    else:
        print("❌ FAILURE: Security violation not detected correctly")
        print(f"   Got: {result.failure_type}")
else:
    print("❌ FAILURE: No result returned")

# Test integrity violation
print("\n=== TESTING INTEGRITY VIOLATION ===")
integrity_indicators = {
    'failed': True,
    'integrity_violation': True,
    'integrity_message': 'Test integrity violation'
}

integrity_result = detector.analyze_failure_indicators_security_first("test_component", integrity_indicators, component)

if integrity_result and integrity_result.failure_type == FailureType.INTEGRITY_VIOLATION:
    print("✅ SUCCESS: Integrity violation correctly detected with HIGH priority!")
else:
    print("❌ FAILURE: Integrity violation not detected correctly")

# Test normal failure (should be COMPONENT_UNRESPONSIVE)
print("\n=== TESTING NORMAL FAILURE ===")
normal_indicators = {
    'failed': True,
    'error_message': 'Normal component failure'
}

normal_result = detector.analyze_failure_indicators_security_first("test_component", normal_indicators, component)

if normal_result and normal_result.failure_type == FailureType.COMPONENT_UNRESPONSIVE:
    print("✅ SUCCESS: Normal failure correctly detected as COMPONENT_UNRESPONSIVE")
else:
    print("❌ FAILURE: Normal failure not detected correctly")
    print(f"   Got: {normal_result.failure_type if normal_result else None}")

print("\n=== SECURITY-FIRST FAILURE DETECTOR TEST COMPLETE ===")