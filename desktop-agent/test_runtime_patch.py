#!/usr/bin/env python3

import sys
sys.path.append('.')

from src.failure.failure_detector import FailureDetector, FailureType, FailureSeverity, ComponentFailure
from datetime import datetime
from typing import Dict, Any, Optional

# Create a minimal test
detector = FailureDetector()

# Define the correct method implementation
def correct_analyze_failure_indicators(self, name: str, indicators: Dict[str, Any], component) -> Optional[ComponentFailure]:
    """Analyze failure indicators to detect component failures - CORRECTED VERSION."""
    print(f"CORRECTED METHOD CALLED for {name}")
    
    # Check for security violations FIRST (highest priority)
    if indicators.get('security_violation', False):
        print(f"SECURITY VIOLATION DETECTED in {name}")
        return ComponentFailure(
            component_name=name,
            failure_type=FailureType.SECURITY_VIOLATION,
            severity=FailureSeverity.CRITICAL,
            timestamp=datetime.now(),
            error_message=indicators.get('security_message', 'Security violation detected'),
            context=indicators
        )
    
    # Check for integrity violations SECOND (highest priority)
    if indicators.get('integrity_violation', False):
        print(f"INTEGRITY VIOLATION DETECTED in {name}")
        return ComponentFailure(
            component_name=name,
            failure_type=FailureType.INTEGRITY_VIOLATION,
            severity=FailureSeverity.CRITICAL,
            timestamp=datetime.now(),
            error_message=indicators.get('integrity_message', 'Data integrity violation detected'),
            context=indicators
        )
    
    # Check for explicit failure indicators
    if indicators.get('failed', False):
        print(f"General failure detected in {name}")
        error_message = indicators.get('error_message', 'Component reported failure')
        failure_type = self._determine_failure_type(indicators)
        severity = self._determine_failure_severity(name, failure_type, component)
        
        return ComponentFailure(
            component_name=name,
            failure_type=failure_type,
            severity=severity,
            timestamp=datetime.now(),
            error_message=error_message,
            context=indicators,
            stack_trace=indicators.get('stack_trace')
        )
    
    return None

# Monkey patch the method
detector._analyze_failure_indicators = correct_analyze_failure_indicators.__get__(detector, FailureDetector)

print("=== Testing with corrected method ===")

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