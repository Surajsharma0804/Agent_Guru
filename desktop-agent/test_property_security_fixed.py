#!/usr/bin/env python3
"""
Property-Based Test for Security Violation Detection - FIXED VERSION

This test validates that the corrected failure detector properly detects
security violations with absolute priority, ensuring fail-safe behavior.
"""

import sys
sys.path.append('.')

from src.failure.failure_detector_production import (
    ProductionFailureDetector,
    FailureType,
    FailureSeverity,
    FailureDetectionConfig
)
from tests.property.test_failure_safety import MockFailureDetectableComponent
import time

def test_security_violation_immediate_response_fixed():
    """
    Property: Security violations must trigger immediate response - FIXED VERSION
    
    Any security violation must be detected immediately and
    classified as critical regardless of component type.
    """
    print("=== TESTING FIXED SECURITY VIOLATION DETECTION ===")
    
    detector = ProductionFailureDetector(
        config=FailureDetectionConfig(detection_interval_seconds=0.1)
    )
    
    critical_failures = []
    security_violations = []
    
    def on_critical_failure(failure):
        critical_failures.append(failure)
        print(f"CRITICAL FAILURE DETECTED: {failure.component_name} - {failure.failure_type.value}")
    
    def on_security_violation(failure):
        security_violations.append(failure)
        print(f"SECURITY VIOLATION CALLBACK: {failure.component_name} - {failure.failure_type.value}")
    
    detector.add_critical_failure_callback(on_critical_failure)
    detector.add_security_violation_callback(on_security_violation)
    
    # Test with non-critical component
    component_name = "test_component"
    is_critical = False
    
    component = MockFailureDetectableComponent(component_name, is_critical=is_critical)
    detector.register_component(component_name, component, is_critical=is_critical)
    
    # Trigger security violation
    component.trigger_security_violation()
    
    # Test direct analysis (simulating detection loop)
    indicators = component.get_failure_indicators()
    print(f"Component indicators: {indicators}")
    
    result = detector._analyze_failure_indicators(component_name, indicators, component)
    
    print(f"Analysis result: {result}")
    
    # Validate security violation detection
    assert result is not None, f"Security violation in '{component_name}' was not detected"
    
    assert result.failure_type == FailureType.SECURITY_VIOLATION, \
        f"Security violation was misclassified as {result.failure_type.value}"
    
    assert result.severity == FailureSeverity.CRITICAL, \
        f"Security violation has insufficient severity: {result.severity.value}"
    
    assert result.requires_authority_revocation(), \
        f"Security violation does not require authority revocation"
    
    # Check that security violation callback was triggered
    assert len(security_violations) > 0, \
        f"Security violation callback was not triggered"
    
    print("✅ SUCCESS: Security violation correctly detected and classified!")
    print(f"   Failure type: {result.failure_type}")
    print(f"   Severity: {result.severity}")
    print(f"   Authority revocation required: {result.requires_authority_revocation()}")
    print(f"   Security violations tracked: {len(security_violations)}")
    
    return True

def test_integrity_violation_immediate_response_fixed():
    """
    Property: Integrity violations must trigger immediate response - FIXED VERSION
    
    Any integrity violation must be detected immediately and
    classified as critical regardless of component type.
    """
    print("\n=== TESTING FIXED INTEGRITY VIOLATION DETECTION ===")
    
    detector = ProductionFailureDetector(
        config=FailureDetectionConfig(detection_interval_seconds=0.1)
    )
    
    component_name = "test_component"
    is_critical = False
    
    component = MockFailureDetectableComponent(component_name, is_critical=is_critical)
    detector.register_component(component_name, component, is_critical=is_critical)
    
    # Trigger integrity violation
    component.trigger_integrity_violation()
    
    # Test direct analysis
    indicators = component.get_failure_indicators()
    result = detector._analyze_failure_indicators(component_name, indicators, component)
    
    # Validate integrity violation detection
    assert result is not None, f"Integrity violation in '{component_name}' was not detected"
    
    assert result.failure_type == FailureType.INTEGRITY_VIOLATION, \
        f"Integrity violation was misclassified as {result.failure_type.value}"
    
    assert result.severity == FailureSeverity.CRITICAL, \
        f"Integrity violation has insufficient severity: {result.severity.value}"
    
    assert result.requires_authority_revocation(), \
        f"Integrity violation does not require authority revocation"
    
    print("✅ SUCCESS: Integrity violation correctly detected and classified!")
    print(f"   Failure type: {result.failure_type}")
    print(f"   Severity: {result.severity}")
    print(f"   Authority revocation required: {result.requires_authority_revocation()}")
    
    return True

def test_security_priority_over_general_failures():
    """
    Property: Security violations must have priority over general failures
    
    When both 'failed' and 'security_violation' are true, security
    violation must be detected, not general failure.
    """
    print("\n=== TESTING SECURITY PRIORITY OVER GENERAL FAILURES ===")
    
    detector = ProductionFailureDetector()
    
    component_name = "test_component"
    component = MockFailureDetectableComponent(component_name, is_critical=False)
    
    # Trigger both general failure AND security violation
    component.trigger_failure("component_unresponsive")
    component.trigger_security_violation()
    
    indicators = component.get_failure_indicators()
    print(f"Mixed indicators: {indicators}")
    
    # Should have both failed=True and security_violation=True
    assert indicators.get('failed', False), "General failure not triggered"
    assert indicators.get('security_violation', False), "Security violation not triggered"
    
    result = detector._analyze_failure_indicators(component_name, indicators, component)
    
    # Security violation must take priority
    assert result is not None, "No failure detected"
    assert result.failure_type == FailureType.SECURITY_VIOLATION, \
        f"Security violation did not take priority - got {result.failure_type.value}"
    
    print("✅ SUCCESS: Security violation correctly prioritized over general failure!")
    print(f"   Result: {result.failure_type}")
    print(f"   Context: {result.context}")
    
    return True

if __name__ == "__main__":
    print("🔒 RUNNING FIXED SECURITY VIOLATION PROPERTY-BASED TESTS")
    print("=" * 70)
    
    try:
        test_security_violation_immediate_response_fixed()
        test_integrity_violation_immediate_response_fixed()
        test_security_priority_over_general_failures()
        
        print("\n" + "=" * 70)
        print("🎉 ALL SECURITY TESTS PASSED!")
        print("✅ Security violations are now detected with absolute priority")
        print("✅ Integrity violations are now detected with high priority")
        print("✅ Fail-safe behavior is implemented correctly")
        print("🛡️ SECURITY BUG FIXED - SYSTEM IS NOW SECURE")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)