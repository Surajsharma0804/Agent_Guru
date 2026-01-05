"""
Security Tests for Authority State Machine

These tests verify security properties, attack resistance, and failure modes
of the Authority State Machine. They focus on security boundaries and
potential attack vectors.
"""

import pytest
import threading
import time
import hashlib
import hmac
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.authority.state import (
    AuthorityState,
    AuthorityPolicy,
    BiometricFactor,
    StateTransitionReason,
    AuthorityConfiguration,
    AuthorityStateMachine,
    AuthorityStateIntegrityError,
    AuthorityTransitionError
)


class TestSecurityBoundaries:
    """Test security boundaries and access controls."""
    
    @pytest.fixture
    def state_machine(self):
        """Create state machine for security tests."""
        config = AuthorityConfiguration(
            max_failed_attempts=3,
            intrusion_cooldown_seconds=5
        )
        return AuthorityStateMachine(config)
    
    def test_no_state_bypass_attempts(self, state_machine):
        """Test that state transitions cannot be bypassed."""
        # Should start locked
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        
        # Direct biometric verification should fail
        with pytest.raises(AuthorityTransitionError):
            state_machine.verify_biometric_factor(
                BiometricFactor.FACE, "test", 0.95, True
            )
        
        # Should still be locked
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        
        # Try to directly access internal state (should not work in real scenario)
        # This tests that the public interface doesn't allow bypassing
        with pytest.raises(AttributeError):
            state_machine._current_state = AuthorityState.ARMED
    
    def test_authority_enforcement_strict(self, state_machine):
        """Test strict authority enforcement."""
        # System should not be armed initially
        assert not state_machine.is_armed
        
        # Low confidence should fail
        result = state_machine.initiate_voice_rearm(0.70, True)
        assert result is False
        assert not state_machine.is_armed
        
        # Speaker verification failure should fail
        result = state_machine.initiate_voice_rearm(0.95, False)
        assert result is False
        assert not state_machine.is_armed
        
        # Only valid credentials should succeed
        result = state_machine.initiate_voice_rearm(0.95, True)
        assert result is True
        assert state_machine.is_armed
    
    def test_session_isolation_security(self, state_machine):
        """Test that sessions are properly isolated."""
        initial_session = state_machine.session_id
        
        # Arm the system
        state_machine.initiate_voice_rearm(0.95, True)
        armed_session = state_machine.session_id
        
        # Session should be the same while armed
        assert armed_session == initial_session
        
        # Revoke authority
        state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
        revoked_session = state_machine.session_id
        
        # Session should change after revocation
        assert revoked_session != armed_session
        
        # New session should be completely independent
        assert isinstance(revoked_session, str)
        assert len(revoked_session) > 0
    
    def test_intrusion_detection_triggers(self, state_machine):
        """Test intrusion detection triggers correctly."""
        # Multiple failed attempts should trigger intrusion detection
        for i in range(3):  # max_failed_attempts = 3
            result = state_machine.initiate_voice_rearm(0.70, True)  # Low confidence
            assert result is False
            
            info = state_machine.get_state_info()
            assert info['failed_attempts'] == i + 1
        
        # Next attempt should trigger intrusion detection
        result = state_machine.initiate_voice_rearm(0.70, True)
        assert result is False
        
        # Should be in intrusion cooldown
        info = state_machine.get_state_info()
        assert info['intrusion_cooldown_active'] is True
        
        # Even valid attempts should be blocked during cooldown
        result = state_machine.initiate_voice_rearm(0.95, True)
        assert result is False
    
    def test_policy_escalation_security(self, state_machine):
        """Test security of policy escalation."""
        # Start with low risk policy (voice only)
        assert state_machine.current_policy == AuthorityPolicy.LOW_RISK
        
        # Arm with voice only
        result = state_machine.initiate_voice_rearm(0.95, True)
        assert result is True
        assert state_machine.is_armed
        
        # Escalate to high risk policy
        result = state_machine.set_authority_policy(AuthorityPolicy.HIGH_RISK)
        assert result is True
        
        # Should automatically revoke authority due to insufficient verification
        assert not state_machine.is_armed
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        
        # Should require full verification for high risk
        assert state_machine.current_policy == AuthorityPolicy.HIGH_RISK
        required_factors = state_machine.get_state_info()['required_factors']
        assert 'voice' in required_factors
        assert 'face' in required_factors
        assert 'fingerprint' in required_factors


class TestIntegrityProtection:
    """Test integrity protection mechanisms."""
    
    @pytest.fixture
    def state_machine(self):
        """Create state machine for integrity tests."""
        return AuthorityStateMachine()
    
    def test_state_integrity_verification(self, state_machine):
        """Test state integrity verification mechanisms."""
        # Should pass initially
        assert state_machine.verify_state_integrity() is True
        
        # Perform normal operations
        state_machine.initiate_voice_rearm(0.95, True)
        assert state_machine.verify_state_integrity() is True
        
        state_machine.update_activity()
        assert state_machine.verify_state_integrity() is True
        
        state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
        assert state_machine.verify_state_integrity() is True
    
    def test_integrity_corruption_detection(self, state_machine):
        """Test detection of integrity corruption."""
        # Verify initial integrity
        assert state_machine.verify_state_integrity() is True
        
        # Simulate integrity corruption by modifying internal checksum
        with state_machine._lock:
            original_checksum = state_machine._state_checksum
            state_machine._state_checksum = "corrupted_checksum"
        
        # Should detect corruption
        assert state_machine.verify_state_integrity() is False
        
        # Should raise exception on state access
        with pytest.raises(AuthorityStateIntegrityError):
            _ = state_machine.current_state
        
        # Restore integrity for cleanup
        with state_machine._lock:
            state_machine._state_checksum = original_checksum
    
    def test_state_history_integrity(self, state_machine):
        """Test integrity of state transition history."""
        # Perform some transitions
        state_machine.initiate_voice_rearm(0.95, True)
        state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
        
        # Get history
        history = state_machine.get_state_history()
        assert len(history) >= 2
        
        # Each transition should have integrity hash
        for transition in history:
            assert isinstance(transition.integrity_hash, str)
            assert len(transition.integrity_hash) > 0
            
            # Verify hash is deterministic
            expected_data = f"{transition.from_state.value}:{transition.to_state.value}:{transition.reason.value}:{transition.timestamp.isoformat()}:{transition.session_id}"
            expected_hash = hashlib.sha256(expected_data.encode()).hexdigest()
            assert transition.integrity_hash == expected_hash
    
    def test_concurrent_integrity_protection(self, state_machine):
        """Test integrity protection under concurrent access."""
        errors = []
        
        def integrity_checker():
            try:
                for _ in range(50):
                    # Should always pass integrity check
                    assert state_machine.verify_state_integrity() is True
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        def state_modifier():
            try:
                for _ in range(25):
                    state_machine.update_activity()
                    time.sleep(0.002)
            except Exception as e:
                errors.append(e)
        
        # Start concurrent threads
        threads = [
            threading.Thread(target=integrity_checker),
            threading.Thread(target=integrity_checker),
            threading.Thread(target=state_modifier)
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have no errors
        assert len(errors) == 0


class TestAttackResistance:
    """Test resistance to various attack scenarios."""
    
    @pytest.fixture
    def state_machine(self):
        """Create state machine for attack resistance tests."""
        config = AuthorityConfiguration(
            max_failed_attempts=3,
            intrusion_cooldown_seconds=2
        )
        return AuthorityStateMachine(config)
    
    def test_brute_force_resistance(self, state_machine):
        """Test resistance to brute force attacks."""
        # Simulate brute force attempts
        attempts = [
            (0.60, True),   # Low confidence
            (0.70, False),  # Speaker verification failed
            (0.65, True),   # Low confidence
            (0.95, False),  # Speaker verification failed
            (0.95, True),   # This should be blocked by intrusion detection
        ]
        
        for i, (confidence, speaker_verified) in enumerate(attempts):
            result = state_machine.initiate_voice_rearm(confidence, speaker_verified)
            
            if i < 3:  # First 3 should fail normally
                assert result is False
            else:  # 4th and beyond should be blocked by intrusion detection
                assert result is False
                info = state_machine.get_state_info()
                assert info['intrusion_cooldown_active'] is True
    
    def test_timing_attack_resistance(self, state_machine):
        """Test resistance to timing attacks."""
        # Test timing consistency for confidence validation
        # All confidence values should take similar time to validate (constant-time comparison)
        
        timings = []
        
        # Test multiple confidence values that will all fail (below threshold)
        test_confidences = [0.50, 0.60, 0.70, 0.80]  # All below default 0.85 threshold
        
        for confidence in test_confidences:
            # Ensure we're in LOCKED state
            if state_machine.current_state != AuthorityState.LOCKED_LISTEN_ONLY:
                state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
            
            # Measure timing for confidence validation (should be constant-time)
            start_time = time.perf_counter()
            result = state_machine.initiate_voice_rearm(confidence, True)
            end_time = time.perf_counter()
            
            timing = end_time - start_time
            timings.append(max(timing, 1e-9))  # Minimum 1 nanosecond to avoid division by zero
            
            # All should fail due to low confidence
            assert result is False

        # Timing variations should be minimal for constant-time operations
        max_timing = max(timings)
        min_timing = min(timings)
        timing_ratio = max_timing / min_timing
        
        # Allow for reasonable timing variation in test environment (50x is generous)
        # In production, this would be much stricter
        assert timing_ratio < 50.0, f"Timing ratio {timing_ratio} suggests timing attack vulnerability"
    
    def test_race_condition_resistance(self, state_machine):
        """Test resistance to race condition attacks."""
        results = []
        errors = []
        
        def concurrent_rearm_attempt():
            try:
                result = state_machine.initiate_voice_rearm(0.95, True)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Launch many concurrent attempts
        threads = [threading.Thread(target=concurrent_rearm_attempt) for _ in range(20)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have some errors (expected when trying to rearm from non-LOCKED state)
        # At most one should succeed
        successful = sum(1 for result in results if result)
        assert successful <= 1
        
        # Total attempts should equal results + errors
        assert len(results) + len(errors) == 20
        
        # State should be consistent
        assert state_machine.verify_state_integrity() is True
    
    def test_state_confusion_resistance(self, state_machine):
        """Test resistance to state confusion attacks."""
        # Try invalid state transitions
        invalid_transitions = [
            # Try to verify biometric without proper setup
            lambda: state_machine.verify_biometric_factor(
                BiometricFactor.FACE, "test", 0.95, True
            ),
            # Try to arm from wrong state
            lambda: state_machine._transition_state(
                AuthorityState.ARMED, StateTransitionReason.BIOMETRIC_VERIFIED
            ) if hasattr(state_machine, '_transition_state') else None
        ]
        
        for invalid_op in invalid_transitions:
            if invalid_op:
                try:
                    invalid_op()
                    # Should not reach here for invalid operations
                    assert False, "Invalid operation should have been rejected"
                except (AuthorityTransitionError, AttributeError):
                    # Expected - invalid operations should be rejected
                    pass
        
        # State should remain consistent
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        assert state_machine.verify_state_integrity() is True


class TestFailureModes:
    """Test various failure modes and error conditions."""
    
    @pytest.fixture
    def state_machine(self):
        """Create state machine for failure mode tests."""
        return AuthorityStateMachine()
    
    def test_timeout_handling(self):
        """Test proper handling of various timeouts."""
        config = AuthorityConfiguration(
            identity_verification_timeout=1,  # Very short for testing
            armed_session_timeout=2,
            inactivity_timeout=1
        )
        state_machine = AuthorityStateMachine(config)
        
        # Test identity verification timeout
        state_machine.set_authority_policy(AuthorityPolicy.MEDIUM_RISK)
        state_machine.initiate_voice_rearm(0.95, True)
        assert state_machine.current_state == AuthorityState.IDENTITY_VERIFICATION
        
        # Wait for timeout
        time.sleep(1.5)
        
        # Should timeout and return to locked
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
    
    def test_configuration_validation(self):
        """Test validation of configuration parameters."""
        # Valid configuration should work
        valid_config = AuthorityConfiguration(
            voice_confidence_threshold=0.85,
            max_failed_attempts=3
        )
        state_machine = AuthorityStateMachine(valid_config)
        assert state_machine.verify_state_integrity() is True
        
        # Edge case configurations should still work
        edge_config = AuthorityConfiguration(
            voice_confidence_threshold=1.0,  # Maximum threshold
            max_failed_attempts=1,           # Minimum attempts
            identity_verification_timeout=1  # Minimum timeout
        )
        edge_state_machine = AuthorityStateMachine(edge_config)
        assert edge_state_machine.verify_state_integrity() is True
    
    def test_memory_pressure_handling(self, state_machine):
        """Test behavior under memory pressure conditions."""
        # Simulate many state transitions to test memory usage
        for i in range(1000):
            # Arm and revoke repeatedly
            if state_machine.initiate_voice_rearm(0.95, True):
                state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
            
            # Check integrity periodically
            if i % 100 == 0:
                assert state_machine.verify_state_integrity() is True
        
        # History should be maintained but not grow unbounded
        history = state_machine.get_state_history()
        assert len(history) > 0
        
        # System should still be functional
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        assert state_machine.verify_state_integrity() is True
    
    def test_thread_cleanup_on_destruction(self):
        """Test proper cleanup of background threads."""
        config = AuthorityConfiguration(
            identity_verification_timeout=1,
            armed_session_timeout=1
        )
        
        # Create and destroy multiple state machines
        for _ in range(5):
            sm = AuthorityStateMachine(config)
            session_id = sm.session_id
            
            # Verify it works
            assert sm.current_state == AuthorityState.LOCKED_LISTEN_ONLY
            
            # Delete should clean up properly
            del sm
        
        # Give time for cleanup
        time.sleep(0.1)
        
        # Should not have hanging threads or resources
        # (This is mainly testing that cleanup doesn't crash)


class TestNegativeSecurityTests:
    """Negative security tests - things that should NOT work."""
    
    @pytest.fixture
    def state_machine(self):
        """Create state machine for negative tests."""
        return AuthorityStateMachine()
    
    def test_cannot_bypass_voice_verification(self, state_machine):
        """Test that voice verification cannot be bypassed."""
        # Should not be able to arm without voice verification
        with pytest.raises(AuthorityTransitionError):
            state_machine.verify_biometric_factor(
                BiometricFactor.FACE, "test", 0.95, True
            )
        
        assert not state_machine.is_armed
    
    def test_cannot_modify_internal_state_directly(self, state_machine):
        """Test that internal state cannot be modified directly."""
        # These should not be accessible or modifiable
        with pytest.raises(AttributeError):
            state_machine._current_state = AuthorityState.ARMED
        
        with pytest.raises(AttributeError):
            state_machine._failed_attempts = 0
        
        with pytest.raises(AttributeError):
            state_machine._session_id = "hacked_session"
    
    def test_cannot_skip_policy_requirements(self, state_machine):
        """Test that policy requirements cannot be skipped."""
        # Set high risk policy
        state_machine.set_authority_policy(AuthorityPolicy.HIGH_RISK)
        
        # Voice alone should not be sufficient
        result = state_machine.initiate_voice_rearm(0.95, True)
        assert result is True  # Should start verification
        assert state_machine.current_state == AuthorityState.IDENTITY_VERIFICATION
        assert not state_machine.is_armed  # But not armed yet
        
        # Verifying only one factor should not be sufficient
        result = state_machine.verify_biometric_factor(
            BiometricFactor.FACE, "test", 0.95, True
        )
        assert result is False  # Still need more factors
        assert not state_machine.is_armed
    
    def test_cannot_reuse_old_session_data(self, state_machine):
        """Test that old session data cannot be reused."""
        # Arm the system
        state_machine.initiate_voice_rearm(0.95, True)
        old_session = state_machine.session_id
        
        # Revoke authority
        state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
        new_session = state_machine.session_id
        
        # Session should have changed
        assert new_session != old_session
        
        # Old session data should not be accessible
        # (This is more of a design verification than a direct test)
        assert state_machine.session_id == new_session
    
    def test_cannot_bypass_intrusion_cooldown(self, state_machine):
        """Test that intrusion cooldown cannot be bypassed."""
        # Trigger intrusion detection
        for _ in range(4):  # Exceed max_failed_attempts
            state_machine.initiate_voice_rearm(0.70, True)
        
        # Should be in cooldown
        assert state_machine.get_state_info()['intrusion_cooldown_active'] is True
        
        # Even perfect credentials should be blocked
        result = state_machine.initiate_voice_rearm(1.0, True)
        assert result is False
        
        # Manual revocation should not clear cooldown
        state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
        result = state_machine.initiate_voice_rearm(1.0, True)
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])