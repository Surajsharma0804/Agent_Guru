#!/usr/bin/env python3

import sys
import os
import importlib

# Clear all cached modules
for module_name in list(sys.modules.keys()):
    if 'failure' in module_name:
        del sys.modules[module_name]

sys.path.insert(0, '.')

# Force fresh import
from src.failure.failure_detector import FailureDetector, FailureType, FailureSeverity
from datetime import datetime

print("=== FINAL SECURITY VIOLATION TEST ===")

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

print(f"Input indicators: {indicators}")
print(f"Detector class: {detector.__class__}")
print(f"Detector module: {detector.__class__.__module__}")

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
        print(f"   Got: {result.failure_type}")
        print(f"   Context: {result.context}")
else:
    print("❌ FAILURE: No result returned")