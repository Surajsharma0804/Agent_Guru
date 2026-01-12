"""
Property-Based Tests for Failure Safety

Property 10: Failure Safety
Validates: Requirements 21.1, 21.2, 21.4

This module implements comprehensive property-based testing for the failure
handling system to ensure that all failure scenarios result in safe system
behavior with no degraded security states.

Security Principles Tested:
- Fail-safe, never fail-open
- Immediate authority revocation on critical failures
- No silent degradation of security boundaries
- Comprehensive audit trail of all failure events
- Component isolation prevents cascade failures
"""

import pytest
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set
from unittest.mock import Mock, MagicMock
from hypothesis import given, strategies as st, settings, assume, note
from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule, initialize, invariant

from src.failure import (
    FailureDetector,
    ComponentFailure,
    FailureType,
    FailureSeverity,
    FailureDetectionConfig,
    ComponentHealthMonitor,
    HealthStatus,
    SafeDegradationManager,
    DegradationLevel,
    RecoveryOrchestrator,
    DependencyMapper
)
from src.failure.exceptions import (
    ComponentFailureError,
    CriticalSystemFailureError,
    SecurityViolationError,
    IntegrityViolationError
)


# Test data generation strategies
component_names = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
failure_types = st.sampled_from(list(FailureType))
failure_severities = st.sampled_from(list(FailureSeverity))
error_messages = st.text(min_size=1, max_size=100)
failure_contexts = st.dictionaries(
    st.text(min_size=1, max_size=10), 
    st.one_of(st.text(), st.integers(), st.floats(allow_nan=False, allow_infinity=False), st.booleans()),
    max_size=5
)


class MockFailureDetectableComponent:
    """Mock component for property-based testing."""
    
    def __init__(self, name: str, is_critical: bool = False, should_fail: bool = False):
        self.name = name
        self._is_critical = is_critical
        self._should_fail = should_fail
        self._failure_indicators = {"failed": should_fail}
        self._security_violation = False
        self._integrity_violation = False
        
    def get_failure_indicators(self) -> Dict[str, Any]:
        """Get failure indicators."""
        indicators = self._failure_indicators.copy()
        if self._security_violation:
            indicators["security_violation"] = True
            indicators["security_message"] = "Test security violation"
        if self._integrity_violation:
            indicators["integrity_violation"] = True
            indicators["integrity_message"] = "Test integrity violation"
        return indicators
    
    def is_critical_component(self) -> bool:
        """Check if component is critical."""
        return self._is_critical
    
    def trigger_failure(self, failure_type: str = "component_unresponsive"):
        """Trigger a failure for testing."""
        self._should_fail = True
        self._failure_indicators = {
            "failed": True,
            "failure_type": failure_type,
            "error_message": f"Test {failure_type} failure"
        }
    
    def trigger_security_violation(self):
        """Trigger a security violation."""
        self._security_violation = True
        self._failure_indicators["failed"] = True
    
    def trigger_integrity_violation(self):
        """Trigger an integrity violation."""
        self._integrity_violation = True
        self._failure_indicators["failed"] = True
    
    def recover(self):
        """Recover the component."""
        self._should_fail = False
        self._security_violation = False
        self._integrity_violation = False
        self._failure_indicators = {"failed": False}


class FailureSafetyStateMachine(RuleBasedStateMachine):
    """
    Stateful property-based testing for failure safety.
    
    This state machine tests that the failure handling system maintains
    safety invariants under all possible sequences of failures and recoveries.
    """
    
    components = Bundle('components')
    failures = Bundle('failures')
    
    def __init__(self):
        super().__init__()
        self.failure_detector = FailureDetector(
            config=FailureDetectionConfig(
                detection_interval_seconds=0.1,
                max_consecutive_failures=3,
                cascade_detection_timeout_seconds=2.0
            )
        )
        self.degradation_manager = SafeDegradationManager()
        self.recovery_orchestrator = RecoveryOrchestrator()
        
        # Track system state for invariant checking
        self.registered_components: Dict[str, MockFailureDetectableComponent] = {}
        self.critical_components: Set[str] = set()
        self.detected_failures: List[ComponentFailure] = []
        self.critical_failures: List[ComponentFailure] = []
        self.security_violations: List[ComponentFailure] = []
        self.integrity_violations: List[ComponentFailure] = []
        self.emergency_halts: List[ComponentFailure] = []
        
        # Set up callbacks to track system behavior
        self.failure_detector.add_failure_callback(self._on_failure_detected)
        self.failure_detector.add_critical_failure_callback(self._on_critical_failure)
        
        # Start detection
        self.failure_detector.start_detection()
        
    def teardown(self):
        """Clean up after testing."""
        self.failure_detector.stop_detection()
    
    def _on_failure_detected(self, failure: ComponentFailure):
        """Track detected failures."""
        self.detected_failures.append(failure)
        
        if failure.failure_type == FailureType.SECURITY_VIOLATION:
            self.security_violations.append(failure)
        elif failure.failure_type == FailureType.INTEGRITY_VIOLATION:
            self.integrity_violations.append(failure)
    
    def _on_critical_failure(self, failure: ComponentFailure):
        """Track critical failures."""
        self.critical_failures.append(failure)
        
        if failure.failure_type in [FailureType.SECURITY_VIOLATION, FailureType.INTEGRITY_VIOLATION]:
            self.emergency_halts.append(failure)
    
    @initialize()
    def setup_initial_state(self):
        """Set up initial system state."""
        note("Initializing failure safety test state machine")
    
    @rule(target=components, name=component_names, is_critical=st.booleans())
    def register_component(self, name, is_critical):
        """Register a component for monitoring."""
        assume(name not in self.registered_components)
        assume(len(name.strip()) > 0)
        
        component = MockFailureDetectableComponent(name, is_critical=is_critical)
        self.registered_components[name] = component
        
        if is_critical:
            self.critical_components.add(name)
        
        self.failure_detector.register_component(name, component, is_critical=is_critical)
        
        note(f"Registered component '{name}' (critical: {is_critical})")
        return name
    
    @rule(component=components, failure_type=failure_types)
    def trigger_component_failure(self, component, failure_type):
        """Trigger a failure in a component."""
        if component in self.registered_components:
            mock_component = self.registered_components[component]
            
            if failure_type == FailureType.SECURITY_VIOLATION:
                mock_component.trigger_security_violation()
                note(f"Triggered security violation in '{component}'")
            elif failure_type == FailureType.INTEGRITY_VIOLATION:
                mock_component.trigger_integrity_violation()
                note(f"Triggered integrity violation in '{component}'")
            else:
                mock_component.trigger_failure(failure_type.value)
                note(f"Triggered {failure_type.value} failure in '{component}'")
            
            # Give the detector time to detect the failure
            time.sleep(0.2)
    
    @rule(component=components)
    def recover_component(self, component):
        """Recover a failed component."""
        if component in self.registered_components:
            mock_component = self.registered_components[component]
            mock_component.recover()
            
            # Clear failure tracking for this component
            self.failure_detector.clear_component_failures(component)
            
            note(f"Recovered component '{component}'")
            time.sleep(0.1)
    
    @rule(components_list=st.lists(components, min_size=2, max_size=5))
    def trigger_cascade_failure(self, components_list):
        """Trigger cascade failures across multiple components."""
        valid_components = [c for c in components_list if c in self.registered_components]
        assume(len(valid_components) >= 2)
        
        # Trigger failures in quick succession to simulate cascade
        for component in valid_components:
            mock_component = self.registered_components[component]
            mock_component.trigger_failure("cascade_failure")
            time.sleep(0.05)  # Small delay to simulate cascade timing
        
        note(f"Triggered cascade failure across {len(valid_components)} components")
        time.sleep(0.3)  # Give time for cascade detection
    
    @invariant()
    def no_silent_security_degradation(self):
        """
        CRITICAL INVARIANT: Security violations must never be silent.
        
        Every security violation must be detected, logged, and result in
        immediate system response. No security violation can be ignored.
        """
        for violation in self.security_violations:
            # Security violations must be detected as failures
            assert any(f.component_name == violation.component_name and 
                      f.failure_type == FailureType.SECURITY_VIOLATION 
                      for f in self.detected_failures), \
                f"Security violation in '{violation.component_name}' was not detected as failure"
            
            # Security violations must be classified as critical
            assert any(f.component_name == violation.component_name and 
                      f.failure_type == FailureType.SECURITY_VIOLATION 
                      for f in self.critical_failures), \
                f"Security violation in '{violation.component_name}' was not classified as critical"
    
    @invariant()
    def no_silent_integrity_degradation(self):
        """
        CRITICAL INVARIANT: Integrity violations must never be silent.
        
        Every integrity violation must be detected, logged, and result in
        immediate system response. No integrity violation can be ignored.
        """
        for violation in self.integrity_violations:
            # Integrity violations must be detected as failures
            assert any(f.component_name == violation.component_name and 
                      f.failure_type == FailureType.INTEGRITY_VIOLATION 
                      for f in self.detected_failures), \
                f"Integrity violation in '{violation.component_name}' was not detected as failure"
            
            # Integrity violations must be classified as critical
            assert any(f.component_name == violation.component_name and 
                      f.failure_type == FailureType.INTEGRITY_VIOLATION 
                      for f in self.critical_failures), \
                f"Integrity violation in '{violation.component_name}' was not classified as critical"
    
    @invariant()
    def critical_components_get_priority(self):
        """
        CRITICAL INVARIANT: Critical component failures must be prioritized.
        
        Failures in critical components must be detected and classified
        with appropriate severity levels.
        """
        for component_name in self.critical_components:
            component_failures = [f for f in self.detected_failures if f.component_name == component_name]
            
            for failure in component_failures:
                # Critical components should have higher severity for equivalent failure types
                if failure.failure_type not in [FailureType.SECURITY_VIOLATION, FailureType.INTEGRITY_VIOLATION]:
                    assert failure.severity in [FailureSeverity.HIGH, FailureSeverity.CRITICAL, FailureSeverity.FATAL], \
                        f"Critical component '{component_name}' failure has insufficient severity: {failure.severity}"
    
    @invariant()
    def failure_detection_completeness(self):
        """
        CRITICAL INVARIANT: All component failures must be detected.
        
        No component failure can go undetected. The failure detection
        system must have complete coverage.
        """
        for component_name, component in self.registered_components.items():
            if component._should_fail or component._security_violation or component._integrity_violation:
                # Component is in failed state, must have detected failure
                assert any(f.component_name == component_name for f in self.detected_failures), \
                    f"Failed component '{component_name}' was not detected by failure detector"
    
    @invariant()
    def no_degraded_security_operation(self):
        """
        CRITICAL INVARIANT: System must not operate in degraded security state.
        
        When security violations occur, the system must not continue
        operating with degraded security. It must halt or recover completely.
        """
        # If we have security violations, system should be in safe state
        if self.security_violations:
            # Check that degradation manager would not allow degraded operation
            for violation in self.security_violations:
                plan = self.degradation_manager.assess_degradation_need([violation.component_name])
                if plan:
                    # Security violations should result in safe halt, not degraded operation
                    assert plan.degradation_level == DegradationLevel.SAFE_HALT, \
                        f"Security violation in '{violation.component_name}' resulted in degraded operation instead of safe halt"
    
    @invariant()
    def audit_trail_completeness(self):
        """
        CRITICAL INVARIANT: All failures must have complete audit trail.
        
        Every detected failure must be properly logged and tracked
        for security audit purposes.
        """
        # All detected failures must have proper timestamps and context
        for failure in self.detected_failures:
            assert failure.timestamp is not None, f"Failure in '{failure.component_name}' missing timestamp"
            assert failure.error_message, f"Failure in '{failure.component_name}' missing error message"
            assert failure.failure_type is not None, f"Failure in '{failure.component_name}' missing failure type"
            assert failure.severity is not None, f"Failure in '{failure.component_name}' missing severity"
    
    @invariant()
    def recovery_safety(self):
        """
        CRITICAL INVARIANT: Recovery operations must be safe.
        
        Recovery operations must not introduce new security vulnerabilities
        or leave the system in an inconsistent state.
        """
        # Check that recovery plans exist for detected failures
        for failure in self.detected_failures:
            if failure.severity in [FailureSeverity.HIGH, FailureSeverity.CRITICAL, FailureSeverity.FATAL]:
                # High severity failures should have recovery plans
                plan = self.recovery_orchestrator.create_recovery_plan(failure)
                if plan:
                    # Recovery plan must have rollback capability
                    assert plan.rollback_plan is not None, \
                        f"Recovery plan for '{failure.component_name}' missing rollback plan"
                    
                    # Recovery plan must have success criteria
                    assert len(plan.success_criteria) > 0, \
                        f"Recovery plan for '{failure.component_name}' missing success criteria"


# Property-based test functions

@given(
    component_name=component_names,
    failure_type=failure_types,
    severity=failure_severities,
    error_message=error_messages,
    context=failure_contexts
)
@settings(max_examples=100, deadline=5000)
def test_failure_immutability(component_name, failure_type, severity, error_message, context):
    """
    Property: ComponentFailure objects must be immutable.
    
    Once created, failure records cannot be modified to ensure
    audit trail integrity and prevent tampering.
    """
    assume(len(component_name.strip()) > 0)
    assume(len(error_message.strip()) > 0)
    
    failure = ComponentFailure(
        component_name=component_name,
        failure_type=failure_type,
        severity=severity,
        timestamp=datetime.now(),
        error_message=error_message,
        context=context
    )
    
    # Failure objects should be frozen (immutable)
    with pytest.raises(AttributeError):
        failure.component_name = "modified"
    
    with pytest.raises(AttributeError):
        failure.severity = FailureSeverity.LOW
    
    with pytest.raises(AttributeError):
        failure.error_message = "modified message"


@given(
    failure_type=failure_types,
    severity=failure_severities
)
@settings(max_examples=50, deadline=3000)
def test_critical_failure_classification(failure_type, severity):
    """
    Property: Critical failure classification must be consistent.
    
    The same failure type and severity combination must always
    result in the same criticality classification.
    """
    failure = ComponentFailure(
        component_name="test_component",
        failure_type=failure_type,
        severity=severity,
        timestamp=datetime.now(),
        error_message="Test failure"
    )
    
    # Critical classification must be deterministic
    is_critical_1 = failure.is_critical()
    is_critical_2 = failure.is_critical()
    assert is_critical_1 == is_critical_2, "Critical classification must be deterministic"
    
    # Authority revocation requirement must be deterministic
    requires_revocation_1 = failure.requires_authority_revocation()
    requires_revocation_2 = failure.requires_authority_revocation()
    assert requires_revocation_1 == requires_revocation_2, "Authority revocation requirement must be deterministic"
    
    # Security and integrity violations must always require authority revocation
    if failure_type in [FailureType.SECURITY_VIOLATION, FailureType.INTEGRITY_VIOLATION]:
        assert failure.requires_authority_revocation(), \
            f"{failure_type.value} must always require authority revocation"


@given(
    components=st.lists(
        st.tuples(component_names, st.booleans()),  # (name, is_critical)
        min_size=1,
        max_size=10,
        unique_by=lambda x: x[0]  # Unique by component name
    )
)
@settings(max_examples=50, deadline=10000)
def test_failure_detector_isolation(components):
    """
    Property: Failure detector must isolate component failures.
    
    Failures in one component must not affect the detection
    of failures in other components.
    """
    assume(all(len(name.strip()) > 0 for name, _ in components))
    
    detector = FailureDetector(
        config=FailureDetectionConfig(detection_interval_seconds=0.1)
    )
    
    try:
        # Register all components
        mock_components = {}
        for name, is_critical in components:
            component = MockFailureDetectableComponent(name, is_critical=is_critical)
            mock_components[name] = component
            detector.register_component(name, component, is_critical=is_critical)
        
        detector.start_detection()
        
        # Trigger failure in first component only
        first_component_name = components[0][0]
        mock_components[first_component_name].trigger_failure()
        
        # Wait for detection
        time.sleep(0.3)
        
        active_failures = detector.get_active_failures()
        
        # Only the first component should have active failure
        assert first_component_name in active_failures, \
            f"Failure in '{first_component_name}' was not detected"
        
        # Other components should not have failures
        for name, _ in components[1:]:
            assert name not in active_failures or not active_failures[name], \
                f"Component '{name}' incorrectly shows failure due to isolation breach"
    
    finally:
        detector.stop_detection()


@given(
    component_name=component_names,
    is_critical=st.booleans()
)
@settings(max_examples=50, deadline=5000)
def test_security_violation_immediate_response(component_name, is_critical):
    """
    Property: Security violations must trigger immediate response.
    
    Any security violation must be detected immediately and
    classified as critical regardless of component type.
    """
    assume(len(component_name.strip()) > 0)
    
    detector = FailureDetector(
        config=FailureDetectionConfig(detection_interval_seconds=0.1)
    )
    
    critical_failures = []
    
    def on_critical_failure(failure):
        critical_failures.append(failure)
    
    detector.add_critical_failure_callback(on_critical_failure)
    
    try:
        component = MockFailureDetectableComponent(component_name, is_critical=is_critical)
        detector.register_component(component_name, component, is_critical=is_critical)
        detector.start_detection()
        
        # Trigger security violation
        component.trigger_security_violation()
        
        # Wait for detection
        time.sleep(0.3)
        
        # Security violation must be detected as critical failure
        assert len(critical_failures) > 0, \
            f"Security violation in '{component_name}' was not detected as critical failure"
        
        security_failure = critical_failures[0]
        assert security_failure.failure_type == FailureType.SECURITY_VIOLATION, \
            f"Security violation was misclassified as {security_failure.failure_type.value}"
        
        assert security_failure.severity == FailureSeverity.CRITICAL, \
            f"Security violation has insufficient severity: {security_failure.severity.value}"
    
    finally:
        detector.stop_detection()


@given(
    component_name=component_names,
    is_critical=st.booleans()
)
@settings(max_examples=50, deadline=5000)
def test_integrity_violation_immediate_response(component_name, is_critical):
    """
    Property: Integrity violations must trigger immediate response.
    
    Any integrity violation must be detected immediately and
    classified as critical regardless of component type.
    """
    assume(len(component_name.strip()) > 0)
    
    detector = FailureDetector(
        config=FailureDetectionConfig(detection_interval_seconds=0.1)
    )
    
    critical_failures = []
    
    def on_critical_failure(failure):
        critical_failures.append(failure)
    
    detector.add_critical_failure_callback(on_critical_failure)
    
    try:
        component = MockFailureDetectableComponent(component_name, is_critical=is_critical)
        detector.register_component(component_name, component, is_critical=is_critical)
        detector.start_detection()
        
        # Trigger integrity violation
        component.trigger_integrity_violation()
        
        # Wait for detection
        time.sleep(0.3)
        
        # Integrity violation must be detected as critical failure
        assert len(critical_failures) > 0, \
            f"Integrity violation in '{component_name}' was not detected as critical failure"
        
        integrity_failure = critical_failures[0]
        assert integrity_failure.failure_type == FailureType.INTEGRITY_VIOLATION, \
            f"Integrity violation was misclassified as {integrity_failure.failure_type.value}"
        
        assert integrity_failure.severity == FailureSeverity.CRITICAL, \
            f"Integrity violation has insufficient severity: {integrity_failure.severity.value}"
    
    finally:
        detector.stop_detection()


@given(
    critical_components=st.lists(component_names, min_size=1, max_size=5, unique=True)
)
@settings(max_examples=30, deadline=8000)
def test_critical_component_safe_halt(critical_components):
    """
    Property: Critical component failures must result in safe halt.
    
    When critical components fail, the system must not attempt
    degraded operation but must halt safely.
    """
    assume(all(len(name.strip()) > 0 for name in critical_components))
    
    degradation_manager = SafeDegradationManager()
    
    for component_name in critical_components:
        # Critical components should result in safe halt
        plan = degradation_manager.assess_degradation_need([component_name])
        
        assert plan is not None, f"No degradation plan for critical component '{component_name}'"
        assert plan.degradation_level == DegradationLevel.SAFE_HALT, \
            f"Critical component '{component_name}' resulted in {plan.degradation_level.value} instead of safe halt"


# Stateful testing
TestFailureSafety = FailureSafetyStateMachine.TestCase


# Integration property tests

def test_failure_safety_state_machine():
    """
    Property: Complete failure safety validation through state machine.
    
    This test runs the stateful property-based testing to validate
    all failure safety invariants under complex scenarios.
    """
    # The state machine test is automatically run by pytest
    # This function serves as documentation and can be extended
    # with additional setup or teardown logic if needed
    pass


if __name__ == "__main__":
    # Run property-based tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])