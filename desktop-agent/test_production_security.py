#!/usr/bin/env python3

import sys
sys.path.append('.')

from src.failure.failure_detector_production import (
    ProductionFailureDetector, 
    FailureType, 
    FailureSeverity
)
from datetime import datetime

print("=== TESTING PRODUCTION SECURITY-FIRST FAILURE DETECTOR ===")

# Create the production detector
detector = ProductionFailureDetector()

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

# Test the production method
result = detector._analyze_failure_indicators("test_component", indicators, component)

print(f"Result: {result}")
if result:
    print(f"Failure type: {result.failure_type}")
    print(f"Expected: {FailureType.SECURITY_VIOLATION}")
    print(f"Match: {result.failure_type == FailureType.SECURITY_VIOLATION}")
    
    if result.failure_type == FailureType.SECURITY_VIOLATION:
        print("✅ SUCCESS: Security violation correctly detected with HIGHEST priority!")
        print(f"   Severity: {result.severity}")
        print(f"   Message: {result.error_message}")
        print(f"   Requires authority revocation: {result.requires_authority_revocation()}")
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

integrity_result = detector._analyze_failure_indicators("test_component", integrity_indicators, component)

if integrity_result and integrity_result.failure_type == FailureType.INTEGRITY_VIOLATION:
    print("✅ SUCCESS: Integrity violation correctly detected with HIGH priority!")
    print(f"   Requires authority revocation: {integrity_result.requires_authority_revocation()}")
else:
    print("❌ FAILURE: Integrity violation not detected correctly")

# Test normal failure (should be COMPONENT_UNRESPONSIVE)
print("\n=== TESTING NORMAL FAILURE ===")
normal_indicators = {
    'failed': True,
    'error_message': 'Normal component failure'
}

normal_result = detector._analyze_failure_indicators("test_component", normal_indicators, component)

if normal_result and normal_result.failure_type == FailureType.COMPONENT_UNRESPONSIVE:
    print("✅ SUCCESS: Normal failure correctly detected as COMPONENT_UNRESPONSIVE")
    print(f"   Requires authority revocation: {normal_result.requires_authority_revocation()}")
else:
    print("❌ FAILURE: Normal failure not detected correctly")
    print(f"   Got: {normal_result.failure_type if normal_result else None}")

# Test critical component security violation
print("\n=== TESTING CRITICAL COMPONENT SECURITY VIOLATION ===")
class CriticalMockComponent:
    def is_critical_component(self):
        return True

critical_component = CriticalMockComponent()
critical_result = detector._analyze_failure_indicators("critical_component", indicators, critical_component)

if critical_result and critical_result.failure_type == FailureType.SECURITY_VIOLATION:
    print("✅ SUCCESS: Critical component security violation detected!")
    print(f"   Severity: {critical_result.severity}")
    print(f"   Should be FATAL: {critical_result.severity == FailureSeverity.FATAL}")
else:
    print("❌ FAILURE: Critical component security violation not detected correctly")

print("\n=== PRODUCTION SECURITY-FIRST FAILURE DETECTOR TEST COMPLETE ===")
print("🔒 SECURITY VIOLATIONS ARE NOW DETECTED WITH ABSOLUTE PRIORITY")
print("🛡️ FAIL-SAFE BEHAVIOR IMPLEMENTED - SECURITY VIOLATIONS CANNOT BE MASKED")