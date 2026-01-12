#!/usr/bin/env python3

import sys
sys.path.append('.')

# Import directly from the specific file
from src.failure.failure_detector import FailureDetector as MainFailureDetector
from src.failure.failure_detector_simple import FailureDetector as SimpleFailureDetector
from src.failure.failure_detector import FailureType, FailureSeverity
from datetime import datetime

print("=== Testing Both Implementations ===")

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

# Test main implementation
print("\n--- Main FailureDetector ---")
main_detector = MainFailureDetector()
main_result = main_detector._analyze_failure_indicators("test_component", indicators, component)
print(f"Main result: {main_result.failure_type if main_result else None}")

# Test simple implementation
print("\n--- Simple FailureDetector ---")
simple_detector = SimpleFailureDetector()
simple_result = simple_detector._analyze_failure_indicators("test_component", indicators, component)
print(f"Simple result: {simple_result.failure_type if simple_result else None}")

# Check which one is being imported by default
print("\n--- Default Import ---")
from src.failure import FailureDetector
default_detector = FailureDetector()
print(f"Default detector class: {default_detector.__class__}")
print(f"Default detector module: {default_detector.__class__.__module__}")
default_result = default_detector._analyze_failure_indicators("test_component", indicators, component)
print(f"Default result: {default_result.failure_type if default_result else None}")

# Check if they're the same class
print(f"\nMain == Default: {MainFailureDetector is FailureDetector}")
print(f"Simple == Default: {SimpleFailureDetector is FailureDetector}")