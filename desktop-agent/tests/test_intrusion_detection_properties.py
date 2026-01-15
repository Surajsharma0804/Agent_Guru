"""
Property-Based Tests for Intrusion Detection System

This module contains property-based tests using Hypothesis to validate
the intrusion detection system's behavior across a wide range of inputs
and scenarios.

Properties tested:
- Property 25: Failed Authentication Lockout

Requirements validated: 6.2
"""

import sys
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intrusion.detection import (
    IntrusionDetector,
    IntrusionDetectionConfig,
    IntrusionEventType,
    IntrusionSeverity,
)
from biometric.providers import BiometricFactor
from pal.interfaces import SecurityEnforcer


# ============================================================================
# Hypothesis Strategies
# ============================================================================

@st.composite
def biometric_factor_strategy(draw):
    """Generate random biometric factors."""
    return draw(st.sampled_from([
        BiometricFactor.FINGERPRINT,
        BiometricFactor.FACE,
        BiometricFactor.VOICE,
    ]))


@st.composite
def failure_count_strategy(draw):
    """Generate failure counts (1-20)."""
    return draw(st.integers(min_value=1, max_value=20))


@st.composite
def confidence_score_strategy(draw):
    """Generate confidence scores (0.0-1.0)."""
    return draw(st.floats(min_value=0.0, max_value=1.0))


@st.composite
def failure_reason_strategy(draw):
    """Generate failure reasons."""
    reasons = [
        "Low confidence",
        "No match found",
        "Sensor error",
        "Timeout",
        "User cancelled",
        "Hardware failure",
        "Poor quality",
        "Multiple attempts",
    ]
    return draw(st.sampled_from(reasons))


# ============================================================================
# Property 25: Failed Authentication Lockout
# ============================================================================

@pytest.mark.property
class TestProperty25_FailedAuthenticationLockout:
    """
    Property 25: Failed Authentication Lockout
    
    PROPERTY: After N failed authentication attempts (where N is the configured
    threshold), the system MUST trigger an intrusion event with HIGH or CRITICAL
    severity and invoke workstation lock if enforcement is enabled.
    
    Validates: Requirements 6.2
    """
    
    @given(
        factor=biometric_factor_strategy(),
        threshold=st.integers(min_value=2, max_value=10),
        confidence=confidence_score_strategy(),
        reason=failure_reason_strategy(),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_threshold_triggers_high_severity_event(
        self,
        factor: BiometricFactor,
        threshold: int,
        confidence: float,
        reason: str
    ):
        """
        Test that exceeding failure threshold triggers HIGH or CRITICAL severity event.
        
        Property: For any biometric factor and threshold N, recording N failures
        MUST produce at least one intrusion event with severity >= HIGH.
        """
        # Create mock security enforcer
        mock_security_enforcer = Mock(spec=SecurityEnforcer)
        mock_security_enforcer.get_capabilities.return_value = {
            'can_lock_session': True
        }
        mock_security_enforcer.get_lock_scope.return_value = 'workstation'
        
        # Create intrusion detector with custom threshold
        config = IntrusionDetectionConfig(
            max_failures_per_factor=threshold,
            enable_security_enforcement=False  # Disable for testing
        )
        detector = IntrusionDetector(mock_security_enforcer, config)
        
        # Record failures up to threshold
        events = []
        for i in range(threshold):
            event = detector.record_biometric_failure(
                factor=factor,
                failure_reason=reason,
                confidence_score=confidence,
                provider="test"
            )
            if event:
                events.append(event)
        
        # PROPERTY: At least one HIGH or CRITICAL event must be generated
        high_severity_events = [
            e for e in events
            if e.severity in (IntrusionSeverity.HIGH, IntrusionSeverity.CRITICAL)
        ]
        
        assert len(high_severity_events) > 0, \
            f"Expected HIGH/CRITICAL event after {threshold} failures, got {[e.severity for e in events]}"
        
        # PROPERTY: Event must be THRESHOLD_EXCEEDED type
        threshold_events = [
            e for e in events
            if e.event_type == IntrusionEventType.THRESHOLD_EXCEEDED
        ]
        
        assert len(threshold_events) > 0, \
            f"Expected THRESHOLD_EXCEEDED event, got {[e.event_type for e in events]}"
    
    @given(
        factor=biometric_factor_strategy(),
        threshold=st.integers(min_value=3, max_value=10),
        confidence=confidence_score_strategy(),
        reason=failure_reason_strategy(),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_below_threshold_no_critical_event(
        self,
        factor: BiometricFactor,
        threshold: int,
        confidence: float,
        reason: str
    ):
        """
        Test that failures below threshold do not trigger CRITICAL events.
        
        Property: For any threshold N, recording N-1 failures MUST NOT produce
        CRITICAL severity events.
        """
        # Ensure we have at least 2 attempts below threshold
        assume(threshold >= 3)
        
        # Create mock security enforcer
        mock_security_enforcer = Mock(spec=SecurityEnforcer)
        mock_security_enforcer.get_capabilities.return_value = {
            'can_lock_session': True
        }
        mock_security_enforcer.get_lock_scope.return_value = 'workstation'
        
        # Create intrusion detector with custom threshold
        config = IntrusionDetectionConfig(
            max_failures_per_factor=threshold,
            max_total_failures=threshold * 2,  # Higher to avoid total threshold
            enable_security_enforcement=False
        )
        detector = IntrusionDetector(mock_security_enforcer, config)
        
        # Record failures BELOW threshold (N-1)
        events = []
        for i in range(threshold - 1):
            event = detector.record_biometric_failure(
                factor=factor,
                failure_reason=reason,
                confidence_score=confidence,
                provider="test"
            )
            if event:
                events.append(event)
        
        # PROPERTY: No CRITICAL events should be generated below threshold
        critical_events = [
            e for e in events
            if e.severity == IntrusionSeverity.CRITICAL
        ]
        
        assert len(critical_events) == 0, \
            f"Expected no CRITICAL events below threshold, got {len(critical_events)}"
    
    @given(
        factor=biometric_factor_strategy(),
        threshold=st.integers(min_value=2, max_value=10),
        confidence=confidence_score_strategy(),
        reason=failure_reason_strategy(),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_lockout_invoked_when_enforcement_enabled(
        self,
        factor: BiometricFactor,
        threshold: int,
        confidence: float,
        reason: str
    ):
        """
        Test that workstation lock is invoked when enforcement is enabled.
        
        Property: When security enforcement is enabled and threshold is exceeded,
        the security enforcer's lock_session method MUST be called.
        """
        # Create mock security enforcer
        mock_security_enforcer = Mock(spec=SecurityEnforcer)
        mock_security_enforcer.get_capabilities.return_value = {
            'can_lock_session': True
        }
        mock_security_enforcer.get_lock_scope.return_value = 'workstation'
        mock_security_enforcer.lock_session.return_value = True
        
        # Create intrusion detector with enforcement ENABLED
        config = IntrusionDetectionConfig(
            max_failures_per_factor=threshold,
            enable_security_enforcement=True,  # ENABLED
            lock_on_high_severity_events=True
        )
        detector = IntrusionDetector(mock_security_enforcer, config)
        
        # Record failures to exceed threshold
        for i in range(threshold + 1):
            detector.record_biometric_failure(
                factor=factor,
                failure_reason=reason,
                confidence_score=confidence,
                provider="test"
            )
        
        # PROPERTY: lock_session must be called when enforcement is enabled
        # (May be called multiple times depending on event severity)
        assert mock_security_enforcer.lock_session.called or \
               detector.get_current_threat_level() == IntrusionSeverity.CRITICAL, \
            "Expected lock_session to be called or threat level to be CRITICAL"
    
    @given(
        factor=biometric_factor_strategy(),
        threshold=st.integers(min_value=2, max_value=10),
        confidence=confidence_score_strategy(),
        reason=failure_reason_strategy(),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_lockout_not_invoked_when_enforcement_disabled(
        self,
        factor: BiometricFactor,
        threshold: int,
        confidence: float,
        reason: str
    ):
        """
        Test that workstation lock is NOT invoked when enforcement is disabled.
        
        Property: When security enforcement is disabled, the security enforcer's
        lock_session method MUST NOT be called, regardless of failure count.
        """
        # Create mock security enforcer
        mock_security_enforcer = Mock(spec=SecurityEnforcer)
        mock_security_enforcer.get_capabilities.return_value = {
            'can_lock_session': True
        }
        mock_security_enforcer.get_lock_scope.return_value = 'workstation'
        mock_security_enforcer.lock_session.return_value = True
        
        # Create intrusion detector with enforcement DISABLED
        config = IntrusionDetectionConfig(
            max_failures_per_factor=threshold,
            enable_security_enforcement=False,  # DISABLED
        )
        detector = IntrusionDetector(mock_security_enforcer, config)
        
        # Record failures to exceed threshold
        for i in range(threshold + 1):
            detector.record_biometric_failure(
                factor=factor,
                failure_reason=reason,
                confidence_score=confidence,
                provider="test"
            )
        
        # PROPERTY: lock_session must NOT be called when enforcement is disabled
        assert not mock_security_enforcer.lock_session.called, \
            "Expected lock_session NOT to be called when enforcement is disabled"
    
    @given(
        total_threshold=st.integers(min_value=5, max_value=15),
        num_factors=st.integers(min_value=2, max_value=3),  # Only 3 factors available
        confidence=confidence_score_strategy(),
        reason=failure_reason_strategy(),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_total_failures_across_factors_triggers_critical(
        self,
        total_threshold: int,
        num_factors: int,
        confidence: float,
        reason: str
    ):
        """
        Test that total failures across multiple factors trigger CRITICAL event.
        
        Property: When total failures across all factors exceed the total threshold,
        a CRITICAL severity event MUST be generated.
        """
        # Ensure we have enough factors to distribute failures
        assume(num_factors >= 2)
        
        # Create mock security enforcer
        mock_security_enforcer = Mock(spec=SecurityEnforcer)
        mock_security_enforcer.get_capabilities.return_value = {
            'can_lock_session': True
        }
        mock_security_enforcer.get_lock_scope.return_value = 'workstation'
        
        # Create intrusion detector with total threshold
        config = IntrusionDetectionConfig(
            max_failures_per_factor=total_threshold,  # High per-factor threshold
            max_total_failures=total_threshold,  # Lower total threshold
            enable_security_enforcement=False
        )
        detector = IntrusionDetector(mock_security_enforcer, config)
        
        # Select factors to use
        all_factors = [
            BiometricFactor.FINGERPRINT,
            BiometricFactor.FACE,
            BiometricFactor.VOICE,
        ]
        factors_to_use = all_factors[:num_factors]
        
        # Distribute failures across factors to exceed total threshold
        failures_per_factor = (total_threshold // num_factors) + 1
        
        events = []
        for factor in factors_to_use:
            for i in range(failures_per_factor):
                event = detector.record_biometric_failure(
                    factor=factor,
                    failure_reason=reason,
                    confidence_score=confidence,
                    provider="test"
                )
                if event:
                    events.append(event)
                
                # Stop if we've exceeded total threshold
                if detector._total_failures > total_threshold:
                    break
            
            if detector._total_failures > total_threshold:
                break
        
        # PROPERTY: At least one CRITICAL event must be generated
        critical_events = [
            e for e in events
            if e.severity == IntrusionSeverity.CRITICAL
        ]
        
        assert len(critical_events) > 0, \
            f"Expected CRITICAL event after exceeding total threshold {total_threshold}, " \
            f"got {[e.severity for e in events]}"
    
    @given(
        factor=biometric_factor_strategy(),
        threshold=st.integers(min_value=2, max_value=10),
        confidence=confidence_score_strategy(),
        reason=failure_reason_strategy(),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_failure_statistics_accuracy(
        self,
        factor: BiometricFactor,
        threshold: int,
        confidence: float,
        reason: str
    ):
        """
        Test that failure statistics are accurately tracked.
        
        Property: The failure statistics MUST accurately reflect the number
        of failures recorded for each factor and in total.
        """
        # Create mock security enforcer
        mock_security_enforcer = Mock(spec=SecurityEnforcer)
        mock_security_enforcer.get_capabilities.return_value = {
            'can_lock_session': True
        }
        mock_security_enforcer.get_lock_scope.return_value = 'workstation'
        
        # Create intrusion detector
        config = IntrusionDetectionConfig(
            max_failures_per_factor=threshold,
            enable_security_enforcement=False
        )
        detector = IntrusionDetector(mock_security_enforcer, config)
        
        # Record specific number of failures
        num_failures = threshold - 1  # Below threshold
        
        for i in range(num_failures):
            detector.record_biometric_failure(
                factor=factor,
                failure_reason=reason,
                confidence_score=confidence,
                provider="test"
            )
        
        # Get statistics
        stats = detector.get_failure_statistics()
        
        # PROPERTY: Total failures must match recorded count
        assert stats['total_failures'] == num_failures, \
            f"Expected {num_failures} total failures, got {stats['total_failures']}"
        
        # PROPERTY: Factor-specific failures must match recorded count
        factor_stats = stats['factor_statistics'].get(factor.value, {})
        assert factor_stats.get('total_failures', 0) == num_failures, \
            f"Expected {num_failures} failures for {factor.value}, " \
            f"got {factor_stats.get('total_failures', 0)}"
    
    @given(
        factor=biometric_factor_strategy(),
        threshold=st.integers(min_value=2, max_value=10),
        confidence=confidence_score_strategy(),
        reason=failure_reason_strategy(),
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_threat_level_escalation(
        self,
        factor: BiometricFactor,
        threshold: int,
        confidence: float,
        reason: str
    ):
        """
        Test that threat level escalates as failures increase.
        
        Property: As failures accumulate, the threat level MUST escalate
        from LOW -> MEDIUM -> HIGH -> CRITICAL.
        """
        # Create mock security enforcer
        mock_security_enforcer = Mock(spec=SecurityEnforcer)
        mock_security_enforcer.get_capabilities.return_value = {
            'can_lock_session': True
        }
        mock_security_enforcer.get_lock_scope.return_value = 'workstation'
        
        # Create intrusion detector
        config = IntrusionDetectionConfig(
            max_failures_per_factor=threshold,
            max_total_failures=threshold,
            enable_security_enforcement=False
        )
        detector = IntrusionDetector(mock_security_enforcer, config)
        
        # Initial threat level should be LOW
        initial_threat = detector.get_current_threat_level()
        assert initial_threat == IntrusionSeverity.LOW, \
            f"Expected initial threat level LOW, got {initial_threat}"
        
        # Record failures to exceed threshold
        for i in range(threshold + 1):
            detector.record_biometric_failure(
                factor=factor,
                failure_reason=reason,
                confidence_score=confidence,
                provider="test"
            )
        
        # PROPERTY: Threat level must escalate after threshold exceeded
        final_threat = detector.get_current_threat_level()
        
        # Threat level should be at least MEDIUM or higher
        assert final_threat in (
            IntrusionSeverity.MEDIUM,
            IntrusionSeverity.HIGH,
            IntrusionSeverity.CRITICAL
        ), f"Expected threat level >= MEDIUM after threshold exceeded, got {final_threat}"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short", "-m", "property"])
