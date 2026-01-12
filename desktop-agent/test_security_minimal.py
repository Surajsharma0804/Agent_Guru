#!/usr/bin/env python3

import sys
import importlib
import inspect
sys.path.append('.')

# Force reload of the module
import src.failure.failure_detector
importlib.reload(src.failure.failure_detector)

from src.failure.failure_detector import FailureDetector, FailureType, FailureSeverity
from datetime import datetime

print(f"Module file: {src.failure.failure_detector.__file__}")

# Create a minimal test
detector = FailureDetector()

print(f"Detector class: {detector.__class__}")
print(f"Detector module: {detector.__class__.__module__}")

# Get the actual method source
method = detector._analyze_failure_indicators
print(f"Method: {method}")

# Get the full source code
try:
    source = inspect.getsource(method)
    print("=== FULL METHOD SOURCE ===")
    print(source)
except Exception as e:
    print(f"Could not get source: {e}")

print("=== Testing _analyze_failure_indicators directly ===")

# Test the method directly with explicit parameters
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

# Call the method directly
result = detector._analyze_failure_indicators("test_component", indicators, component)

print(f"Result: {result}")
if result:
    print(f"Failure type: {result.failure_type}")
    print(f"Expected: {FailureType.SECURITY_VIOLATION}")
    print(f"Match: {result.failure_type == FailureType.SECURITY_VIOLATION}")
else:
    print("No result returned")