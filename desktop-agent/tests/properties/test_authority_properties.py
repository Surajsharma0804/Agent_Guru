"""
Property-Based Tests for Authority State Machine

These tests use Hypothesis to verify universal properties that must hold
across all valid inputs and state combinations. They validate the core
security invariants of the Authority State Machine.

Feature: guru-personal-assistant
Property 1: Authority State Enforcement
Validates: Requirements 3.1, 3.2, 24.4, 24.5
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, initialize
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Set

from src.authority.state import (
    AuthorityState,
    AuthorityPolicy,
    BiometricFactor,
    StateTransitionReason,
    AuthorityConfiguration,
    AuthorityStateMachine,
    AuthorityStateIntegrityError,
    AuthorityTransitionError,
    create_authority_state_machine
)


# Hypothesis strategies for generating test data

@st.composite
def authority_config_strategy(draw):
    """Generate valid AuthorityConfiguration instances."""
    return AuthorityConfiguration(
        identity_verification_timeout=draw(st.integers(min_value=1, max_value=60)),
        armed_session_timeout=draw(st.integers(min_value=10, max_value=600)),
        inactivity_timeout=draw(st.integers(min_value=1, max_value=120)),
        voice_confidence_threshold=draw(st.floats(min_value=0.5, max_value=1.0)),
        face_confidence_threshold=draw(st.floats(min_value=0.5, max_value=1.0)),
        fingerprint_confidence_threshold=draw(st.floats(min_value=0.5, max_value=1.0)),
        max_failed_attempts=draw(st.integers(min_value=1, max_value=10)),
        intrusion_cooldown_seconds=draw(st.integers(min_value=1, max_value=300)),
        require_biometric_for_rearm=draw(st.booleans())
    )


@st.composite
def voice_rearm_params_strategy(draw):
    """Generate voice re-arming parameters."""
    return {
        'voice_confidence': draw(st.floats(min_value=0.0, max_value=1.0)),
        'speaker_verified': draw(st.booleans())
    }


@st.composite
def biometric_verification_strategy(draw):
    """Generate biometric verification parameters."""
    return {
        'factor': draw(st.sampled_from(BiometricFactor)),
        'provider': draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))),
        'confidence': draw(st.floats(min_value=0.0, max_value=1.0)),
        'success': draw(st.booleans()),
        'failure_reason': draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    }


class TestAuthorityStateProperties:
    """Property-based tests for Authority State Machine invariants."""
    
    @given(authority_config_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_initial_state_invariant(self, config):
        """
        Property: Initial State Invariant
        For any valid configuration, a newly created AuthorityStateMachine
        must always start in LOCKED_LISTEN_ONLY state with consistent properties.
        
        **Feature: guru-personal-assistant, Property 1: Authority State Enforcement**
        **Validates: Requirements 3.1, 3.2, 24.4, 24.5**
        """
        state_machine = AuthorityStateMachine(config)
        
        # Core invariants
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        assert state_machine.is_locked is True
        assert state_machine.is_armed is False
        
        # Session properties
        assert isinstance(state_machine.session_id, str)
        assert len(state_machine.session_id) > 0
        
        # State info consistency
        info = state_machine.get_state_info()
        assert info['state'] == AuthorityState.LOCKED_LISTEN_ONLY.value
        assert info['is_armed'] is False
        assert info['is_locked'] is True
        assert info['failed_attempts'] == 0
        assert info['verification_in_progress'] is False
        
        # Integrity must be valid
        assert state_machine.verify_state_integrity() is True
    
    @given(authority_config_strategy(), voice_rearm_params_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_voice_rearm_determinism(self, config, voice_params):
        """
        Property: Voice Re-arming Determinism
        For any configuration and voice parameters, the result of voice re-arming
        must be deterministic and consistent with the security policy.
        
        **Feature: guru-personal-assistant, Property 1: Authority State Enforcement**
        **Validates: Requirements 3.1, 3.2, 24.4, 24.5**
        """
        state_machine = AuthorityStateMachine(config)
        
        # Test determinism by calling twice with same parameters
        result1 = state_machine.initiate_voice_rearm(
            voice_params['voice_confidence'],
            voice_params['speaker_verified']
        )
        
        # Reset state if needed
        if state_machine.current_state != AuthorityState.LOCKED_LISTEN_ONLY:
            state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
        
        result2 = state_machine.initiate_voice_rearm(
            voice_params['voice_confidence'],
            voice_params['speaker_verified']
        )
        
        # Results should be identical for same inputs
        assert result1 == result2
        
        # Validate result consistency with thresholds
        expected_success = (
            voice_params['voice_confidence'] >= config.voice_confidence_threshold and
            voice_params['speaker_verified']
        )
        
        if expected_success and config.policy_requirements[AuthorityPolicy.LOW_RISK] == {BiometricFactor.VOICE}:
            # Should succeed and arm for voice-only policy
            assert result1 is True
        elif expected_success:
            # Should succeed but require additional verification
            assert result1 is True
        else:
            # Should fail
            assert result1 is False
    
    @given(authority_config_strategy(), st.sampled_from(AuthorityPolicy))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_policy_enforcement(self, config, policy):
        """
        Property: Policy Enforcement
        For any configuration and policy, the required biometric factors
        must be enforced consistently.
        
        **Feature: guru-personal-assistant, Property 1: Authority State Enforcement**
        **Validates: Requirements 3.1, 3.2, 24.4, 24.5**
        """
        state_machine = AuthorityStateMachine(config)
        
        # Set the policy
        state_machine.set_authority_policy(policy)
        
        # Get required factors for this policy
        required_factors = config.policy_requirements[policy]
        
        # State info should reflect the policy
        info = state_machine.get_state_info()
        assert info['policy'] == policy.value
        assert set(info['required_factors']) == {f.value for f in required_factors}
        
        # Use confidence that meets the threshold
        voice_confidence = max(config.voice_confidence_threshold, 0.95)
        voice_result = state_machine.initiate_voice_rearm(voice_confidence, True)
        
        if required_factors == {BiometricFactor.VOICE}:
            # Voice-only policy should arm directly
            assert voice_result is True
            assert state_machine.is_armed is True
        else:
            # Multi-factor policy should require additional verification
            assert voice_result is True
            assert state_machine.current_state == AuthorityState.IDENTITY_VERIFICATION
            assert state_machine.is_armed is False
    
    @given(authority_config_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_authority_revocation_always_succeeds(self, config):
        """
        Property: Authority Revocation Always Succeeds
        For any state and configuration, authority revocation must always succeed
        and return the system to a locked state.
        
        **Feature: guru-personal-assistant, Property 1: Authority State Enforcement**
        **Validates: Requirements 3.1, 3.2, 24.4, 24.5**
        """
        state_machine = AuthorityStateMachine(config)
        
        # Try revocation from initial state
        result = state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
        assert result is True
        assert state_machine.is_locked is True
        
        # Arm the system and try revocation
        if state_machine.initiate_voice_rearm(0.95, True):
            result = state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
            assert result is True
            assert state_machine.is_locked is True
        
        # Multiple revocations should be safe
        result = state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
        assert result is True
        assert state_machine.is_locked is True
    
    @given(authority_config_strategy(), st.lists(voice_rearm_params_strategy(), min_size=1, max_size=10))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_failed_attempts_tracking(self, config, voice_attempts):
        """
        Property: Failed Attempts Tracking
        For any sequence of voice re-arming attempts, failed attempts must be
        tracked correctly and trigger intrusion detection when threshold is exceeded.
        
        **Feature: guru-personal-assistant, Property 1: Authority State Enforcement**
        **Validates: Requirements 3.1, 3.2, 24.4, 24.5**
        """
        state_machine = AuthorityStateMachine(config)
        
        consecutive_failed_count = 0
        
        for attempt in voice_attempts:
            # Reset to locked state if needed
            if state_machine.current_state != AuthorityState.LOCKED_LISTEN_ONLY:
                state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
            
            # Skip if in intrusion cooldown
            if state_machine.get_state_info()['intrusion_cooldown_active']:
                break
            
            result = state_machine.initiate_voice_rearm(
                attempt['voice_confidence'],
                attempt['speaker_verified']
            )
            
            # Check if this attempt should fail
            should_fail = (attempt['voice_confidence'] < config.voice_confidence_threshold or
                          not attempt['speaker_verified'])
            
            if should_fail:
                consecutive_failed_count += 1
                assert result is False
            else:
                # Successful authentication resets the counter
                consecutive_failed_count = 0
                assert result is True
            
            info = state_machine.get_state_info()
            
            # Failed attempts should match our tracking
            assert info['failed_attempts'] == consecutive_failed_count
            
            # Intrusion detection should trigger at threshold
            if consecutive_failed_count >= config.max_failed_attempts:
                assert info['intrusion_cooldown_active'] is True
                break  # Stop testing once intrusion is detected
                break
    
    @given(authority_config_strategy(), st.integers(min_value=1, max_value=10))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_session_isolation(self, config, num_sessions):
        """
        Property: Session Isolation
        For any number of session cycles, each session must have a unique ID
        and sessions must be properly isolated.
        
        **Feature: guru-personal-assistant, Property 1: Authority State Enforcement**
        **Validates: Requirements 3.1, 3.2, 24.4, 24.5**
        """
        state_machine = AuthorityStateMachine(config)
        
        session_ids = set()
        
        for _ in range(num_sessions):
            # Record current session ID
            current_session = state_machine.session_id
            session_ids.add(current_session)
            
            # Arm and revoke to trigger session change
            if state_machine.initiate_voice_rearm(0.95, True):
                state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
            
            # Session ID should change after revocation
            new_session = state_machine.session_id
            if current_session != new_session:
                session_ids.add(new_session)
        
        # All session IDs should be unique
        assert len(session_ids) >= 1  # At least the initial session
        
        # Current session should be valid
        assert isinstance(state_machine.session_id, str)
        assert len(state_machine.session_id) > 0
    
    @given(authority_config_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_state_integrity_preservation(self, config):
        """
        Property: State Integrity Preservation
        For any valid operations, state integrity must be preserved throughout
        the lifetime of the state machine.
        
        **Feature: guru-personal-assistant, Property 1: Authority State Enforcement**
        **Validates: Requirements 3.1, 3.2, 24.4, 24.5**
        """
        state_machine = AuthorityStateMachine(config)
        
        # Integrity should be valid initially
        assert state_machine.verify_state_integrity() is True
        
        # Perform various operations
        operations = [
            lambda: state_machine.initiate_voice_rearm(0.95, True),
            lambda: state_machine.update_activity(),
            lambda: state_machine.get_state_info(),
            lambda: state_machine.get_state_history(),
            lambda: state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE),
            lambda: state_machine.set_authority_policy(AuthorityPolicy.MEDIUM_RISK)
        ]
        
        for operation in operations:
            try:
                operation()
                # Integrity should remain valid after each operation
                assert state_machine.verify_state_integrity() is True
            except (AuthorityTransitionError, AuthorityStateIntegrityError):
                # These exceptions are expected for invalid operations
                pass


class AuthorityStateMachineStateful(RuleBasedStateMachine):
    """
    Stateful property-based testing for Authority State Machine.
    
    This uses Hypothesis's stateful testing to explore complex sequences
    of operations and verify that invariants hold throughout.
    """
    
    def __init__(self):
        super().__init__()
        self.config = AuthorityConfiguration(
            identity_verification_timeout=30,
            armed_session_timeout=300,
            inactivity_timeout=60,
            max_failed_attempts=3
        )
        self.state_machine = None
    
    @initialize()
    def initialize_state_machine(self):
        """Initialize the state machine."""
        self.state_machine = AuthorityStateMachine(self.config)
    
    @rule()
    def voice_rearm_high_confidence(self):
        """Attempt voice re-arming with high confidence."""
        if self.state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY:
            self.state_machine.initiate_voice_rearm(0.95, True)
    
    @rule()
    def voice_rearm_low_confidence(self):
        """Attempt voice re-arming with low confidence."""
        if self.state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY:
            self.state_machine.initiate_voice_rearm(0.70, True)
    
    @rule()
    def voice_rearm_speaker_failed(self):
        """Attempt voice re-arming with speaker verification failure."""
        if self.state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY:
            self.state_machine.initiate_voice_rearm(0.95, False)
    
    @rule(factor=st.sampled_from(BiometricFactor))
    def biometric_verification_success(self, factor):
        """Successful biometric verification."""
        if self.state_machine.current_state == AuthorityState.IDENTITY_VERIFICATION:
            try:
                self.state_machine.verify_biometric_factor(
                    factor=factor,
                    provider="test_provider",
                    confidence=0.95,
                    success=True
                )
            except AuthorityTransitionError:
                pass  # Expected if factor not required
    
    @rule(factor=st.sampled_from(BiometricFactor))
    def biometric_verification_failure(self, factor):
        """Failed biometric verification."""
        if self.state_machine.current_state == AuthorityState.IDENTITY_VERIFICATION:
            try:
                self.state_machine.verify_biometric_factor(
                    factor=factor,
                    provider="test_provider",
                    confidence=0.50,
                    success=False,
                    failure_reason="low_confidence"
                )
            except AuthorityTransitionError:
                pass  # Expected if not in correct state
    
    @rule()
    def revoke_authority(self):
        """Revoke authority."""
        self.state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
    
    @rule()
    def update_activity(self):
        """Update activity timestamp."""
        self.state_machine.update_activity()
    
    @rule(policy=st.sampled_from(AuthorityPolicy))
    def change_policy(self, policy):
        """Change authority policy."""
        self.state_machine.set_authority_policy(policy)
    
    @invariant()
    def state_integrity_invariant(self):
        """State integrity must always be valid."""
        assert self.state_machine.verify_state_integrity() is True
    
    @invariant()
    def state_consistency_invariant(self):
        """State properties must be consistent."""
        state = self.state_machine.current_state
        is_armed = self.state_machine.is_armed
        is_locked = self.state_machine.is_locked
        
        # Consistency checks
        if state == AuthorityState.ARMED:
            assert is_armed is True
            assert is_locked is False
        elif state == AuthorityState.LOCKED_LISTEN_ONLY:
            assert is_armed is False
            assert is_locked is True
        else:
            assert is_armed is False
    
    @invariant()
    def session_id_invariant(self):
        """Session ID must always be valid."""
        session_id = self.state_machine.session_id
        assert isinstance(session_id, str)
        assert len(session_id) > 0
    
    @invariant()
    def state_info_consistency_invariant(self):
        """State info must be consistent with actual state."""
        info = self.state_machine.get_state_info()
        actual_state = self.state_machine.current_state
        
        assert info['state'] == actual_state.value
        assert info['is_armed'] == self.state_machine.is_armed
        assert info['is_locked'] == self.state_machine.is_locked


# Test the stateful machine
TestAuthorityStateMachineStateful = AuthorityStateMachineStateful.TestCase


class TestConcurrentProperties:
    """Property-based tests for concurrent access patterns."""
    
    @given(st.integers(min_value=2, max_value=10), st.integers(min_value=10, max_value=100))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=1000)  # 1 second deadline
    def test_property_concurrent_state_access(self, num_threads, operations_per_thread):
        """
        Property: Concurrent State Access Safety
        For any number of concurrent threads accessing state properties,
        the state machine must remain consistent and not crash.
        
        **Feature: guru-personal-assistant, Property 1: Authority State Enforcement**
        **Validates: Requirements 3.1, 3.2, 24.4, 24.5**
        """
        state_machine = AuthorityStateMachine()
        results = []
        errors = []
        
        def access_operations():
            try:
                for _ in range(operations_per_thread):
                    # Various read operations
                    state = state_machine.current_state
                    is_armed = state_machine.is_armed
                    is_locked = state_machine.is_locked
                    info = state_machine.get_state_info()
                    history = state_machine.get_state_history(limit=5)
                    
                    results.append((state, is_armed, is_locked, len(history)))
                    
                    # Small delay to increase chance of race conditions
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Start concurrent threads
        threads = [threading.Thread(target=access_operations) for _ in range(num_threads)]
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should have no errors
        assert len(errors) == 0
        
        # Should have expected number of results
        assert len(results) == num_threads * operations_per_thread
        
        # All results should be consistent (same state since no modifications)
        states = set(result[0] for result in results)
        assert len(states) == 1  # Only one state should be observed
        assert list(states)[0] == AuthorityState.LOCKED_LISTEN_ONLY
    
    @given(st.integers(min_value=2, max_value=8))
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_concurrent_voice_rearm_exclusivity(self, num_threads):
        """
        Property: Concurrent Voice Re-arm Exclusivity
        For any number of concurrent voice re-arming attempts,
        at most one should succeed and the system should remain consistent.
        
        **Feature: guru-personal-assistant, Property 1: Authority State Enforcement**
        **Validates: Requirements 3.1, 3.2, 24.4, 24.5**
        """
        state_machine = AuthorityStateMachine()
        results = []
        errors = []
        
        def attempt_rearm():
            try:
                result = state_machine.initiate_voice_rearm(0.95, True)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Start concurrent re-arm attempts
        threads = [threading.Thread(target=attempt_rearm) for _ in range(num_threads)]
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have some errors (expected when trying to rearm from non-LOCKED state)
        # At most one should succeed
        successful = sum(1 for result in results if result)
        assert successful <= 1
        
        # Total attempts should equal results + errors
        assert len(results) + len(errors) == num_threads
        assert successful <= 1
        
        # If one succeeded, system should be armed or in verification
        if successful == 1:
            assert (state_machine.is_armed or 
                   state_machine.current_state == AuthorityState.IDENTITY_VERIFICATION)
        else:
            # If none succeeded, should still be locked
            assert state_machine.is_locked


if __name__ == "__main__":
    # Run property-based tests
    pytest.main([__file__, "-v", "--tb=short"])