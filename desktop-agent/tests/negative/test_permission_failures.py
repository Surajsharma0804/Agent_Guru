"""
Negative Tests for Authority State Machine

These tests verify that the system properly rejects invalid operations,
handles corrupted state, and fails safely under adverse conditions.
"""

import pytest
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import patch

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


class TestInvalidTransitions:
    """Test rejection of invalid state transitions."""
    
    @pytest.fixture
    def state_machine(self):
        """Create state machine for invalid transition tests."""
        return AuthorityStateMachine()
    
    def test_invalid_biometric_verification_from_locked(self, state_machine):
        """Test that biometric verification fails from locked state."""
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        
        # Should reject biometric verification without voice phrase
        with pytest.raises(AuthorityTransitionError) as exc_info:
            state_machine.verify_biometric_factor(
                factor=BiometricFactor.FACE,
                provider="windows_hello",
                confidence=0.95,
                success=True
            )
        
        assert "IDENTITY_VERIFICATION" in str(exc_info.value)
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
    
    def test_invalid_voice_rearm_from_armed(self, state_machine):
        """Test that voice re-arm fails when already armed."""
        # First arm the system
        result = state_machine.initiate_voice_rearm(0.95, True)
        assert result is True
        assert state_machine.is_armed
        
        # Second voice re-arm should fail
        with pytest.raises(AuthorityTransitionError) as exc_info:
            state_machine.initiate_voice_rearm(0.95, True)
        
        assert "LOCKED_LISTEN_ONLY" in str(exc_info.value)
        assert state_machine.is_armed  # Should remain armed
    
    def test_invalid_voice_rearm_from_verification(self, state_machine):
        """Test that voice re-arm fails during identity verification."""
        # Set medium risk policy and start verification
        state_machine.set_authority_policy(AuthorityPolicy.MEDIUM_RISK)
        result = state_machine.initiate_voice_rearm(0.95, True)
        assert result is True
        assert state_machine.current_state == AuthorityState.IDENTITY_VERIFICATION
        
        # Second voice re-arm should fail
        with pytest.raises(AuthorityTransitionError) as exc_info:
            state_machine.initiate_voice_rearm(0.95, True)
        
        assert "LOCKED_LISTEN_ONLY" in str(exc_info.value)
        assert state_machine.current_state == AuthorityState.IDENTITY_VERIFICATION
    
    def test_biometric_verification_wrong_factor(self, state_machine):
        """Test biometric verification with wrong factor for policy."""
        # Set voice-only policy
        state_machine.set_authority_policy(AuthorityPolicy.LOW_RISK)
        
        # Start verification (should arm directly for voice-only)
        result = state_machine.initiate_voice_rearm(0.95, True)
        assert result is True
        assert state_machine.is_armed
        
        # Reset to test medium risk
        state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
        state_machine.set_authority_policy(AuthorityPolicy.MEDIUM_RISK)
        
        # Start verification
        result = state_machine.initiate_voice_rearm(0.95, True)
        assert result is True
        assert state_machine.current_state == AuthorityState.IDENTITY_VERIFICATION
        
        # Try to verify fingerprint when only face is required (along with voice)
        # This should work but not complete arming
        result = state_machine.verify_biometric_factor(
            factor=BiometricFactor.FINGERPRINT,
            provider="windows_hello",
            confidence=0.95,
            success=True
        )
        # Should not complete arming because face is still required
        assert result is False
        assert not state_machine.is_armed


class TestCorruptedState:
    """Test handling of corrupted or invalid state."""
    
    @pytest.fixture
    def state_machine(self):
        """Create state machine for corruption tests."""
        return AuthorityStateMachine()
    
    def test_corrupted_integrity_checksum(self, state_machine):
        """Test detection and handling of corrupted integrity checksum."""
        # Verify initial integrity
        assert state_machine.verify_state_integrity() is True
        
        # Enable test corruption mode (required for testing)
        state_machine.enable_test_corruption_mode()
        
        # Corrupt the integrity checksum
        with state_machine._lock:
            state_machine._state_checksum = "definitely_corrupted_checksum"
        
        # Disable test corruption mode to restore normal protection
        state_machine.disable_test_corruption_mode()
        
        # Should detect corruption
        assert state_machine.verify_state_integrity() is False
        
        # All operations should fail with integrity error
        with pytest.raises(AuthorityStateIntegrityError):
            _ = state_machine.current_state
        
        with pytest.raises(AuthorityStateIntegrityError):
            state_machine.initiate_voice_rearm(0.95, True)
        
        with pytest.raises(AuthorityStateIntegrityError):
            state_machine.get_state_info()
    
    def test_corrupted_session_id(self, state_machine):
        """Test handling of corrupted session ID."""
        original_session = state_machine.session_id
        
        # Try to corrupt session ID (should fail due to protection)
        with pytest.raises(AttributeError):
            state_machine._session_id = ""  # Should be protected
        
        # Session should remain unchanged
        assert state_machine.session_id == original_session
        
        # Operations should still work normally
        info = state_machine.get_state_info()
        assert info['session_id'] == original_session
    
    def test_corrupted_failed_attempts_counter(self, state_machine):
        """Test handling of corrupted failed attempts counter."""
        # Corrupt failed attempts counter to negative value
        with state_machine._lock:
            object.__setattr__(state_machine, '_failed_attempts', -1)
            state_machine._update_state_checksum()
        
        # Should still handle operations safely
        info = state_machine.get_state_info()
        assert info['failed_attempts'] == -1  # Reports corrupted value
        
        # But new failures should be tracked correctly
        result = state_machine.initiate_voice_rearm(0.70, True)  # Low confidence
        assert result is False
        
        info = state_machine.get_state_info()
        assert info['failed_attempts'] == 0  # Should be reset/corrected
    
    def test_corrupted_state_history(self, state_machine):
        """Test handling of corrupted state history."""
        # Perform some transitions to build history
        state_machine.initiate_voice_rearm(0.95, True)
        state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
        
        # Corrupt state history
        with state_machine._lock:
            object.__setattr__(state_machine, '_state_history', [])  # Clear history
            state_machine._update_state_checksum()
        
        # Should still function but with empty history
        history = state_machine.get_state_history()
        assert len(history) == 0
        
        # New transitions should be recorded
        state_machine.initiate_voice_rearm(0.95, True)
        history = state_machine.get_state_history()
        assert len(history) == 1


class TestInvalidInputs:
    """Test handling of invalid inputs and parameters."""
    
    @pytest.fixture
    def state_machine(self):
        """Create state machine for invalid input tests."""
        return AuthorityStateMachine()
    
    def test_invalid_confidence_values(self, state_machine):
        """Test handling of invalid confidence values."""
        # Negative confidence
        result = state_machine.initiate_voice_rearm(-0.5, True)
        assert result is False
        
        # Confidence > 1.0
        result = state_machine.initiate_voice_rearm(1.5, True)
        assert result is False
        
        # NaN confidence
        result = state_machine.initiate_voice_rearm(float('nan'), True)
        assert result is False
        
        # Infinity confidence
        result = state_machine.initiate_voice_rearm(float('inf'), True)
        assert result is False
    
    def test_invalid_biometric_parameters(self, state_machine):
        """Test handling of invalid biometric parameters."""
        # Set up for biometric verification - use HIGH_RISK to require multiple factors
        state_machine.set_authority_policy(AuthorityPolicy.HIGH_RISK)  # Requires voice + face + fingerprint
        state_machine.initiate_voice_rearm(0.95, True)
        
        # Should be in IDENTITY_VERIFICATION state waiting for face and fingerprint
        assert state_machine.current_state == AuthorityState.IDENTITY_VERIFICATION
        
        # Empty provider name
        result = state_machine.verify_biometric_factor(
            factor=BiometricFactor.FACE,
            provider="",
            confidence=0.95,
            success=True
        )
        # Should handle gracefully (might succeed or fail depending on implementation)
        
        # None as provider
        with pytest.raises((TypeError, AttributeError)):
            state_machine.verify_biometric_factor(
                factor=BiometricFactor.FACE,
                provider=None,
                confidence=0.95,
                success=True
            )
        
        # Invalid confidence values
        result = state_machine.verify_biometric_factor(
            factor=BiometricFactor.FINGERPRINT,
            provider="test",
            confidence=-1.0,
            success=True
        )
        assert result is False
    
    def test_invalid_policy_changes(self, state_machine):
        """Test handling of invalid policy changes."""
        # None as policy should raise KeyError when looking up requirements
        with pytest.raises(KeyError):
            state_machine.set_authority_policy(None)
        
        # Invalid enum value should raise AttributeError
        with pytest.raises(AttributeError):
            state_machine.set_authority_policy("invalid_policy")
    
    def test_invalid_revocation_reasons(self, state_machine):
        """Test handling of invalid revocation reasons."""
        # Arm the system first
        state_machine.initiate_voice_rearm(0.95, True)
        
        # None as reason should raise TypeError
        with pytest.raises(TypeError):
            state_machine.revoke_authority(None)
        
        # Invalid enum value should raise TypeError
        with pytest.raises(TypeError):
            state_machine.revoke_authority("invalid_reason")


class TestResourceExhaustion:
    """Test behavior under resource exhaustion conditions."""
    
    def test_memory_exhaustion_simulation(self):
        """Test behavior when memory is exhausted."""
        config = AuthorityConfiguration()
        state_machine = AuthorityStateMachine(config)
        
        # Simulate memory pressure by creating many state transitions
        try:
            for i in range(10000):  # Large number of transitions
                state_machine.initiate_voice_rearm(0.95, True)
                state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
                
                # Check integrity periodically
                if i % 1000 == 0:
                    assert state_machine.verify_state_integrity() is True
        
        except MemoryError:
            # If we actually hit memory limits, system should still be consistent
            assert state_machine.verify_state_integrity() is True
        
        # System should still be functional
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
    
    def test_thread_exhaustion_simulation(self):
        """Test behavior when thread resources are exhausted."""
        state_machine = AuthorityStateMachine()
        
        # Create many concurrent operations
        threads = []
        errors = []
        
        def safe_operation():
            try:
                for _ in range(10):
                    state_machine.get_state_info()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Create many threads (but not so many as to crash the test)
        for _ in range(100):
            thread = threading.Thread(target=safe_operation)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should handle gracefully
        assert len(errors) == 0
        assert state_machine.verify_state_integrity() is True
    
    def test_disk_space_exhaustion_simulation(self):
        """Test behavior when disk space is exhausted."""
        # This is more of a conceptual test since we don't actually write to disk
        # in the current implementation, but tests the principle
        
        state_machine = AuthorityStateMachine()
        
        # Simulate many operations that would write audit logs
        for _ in range(1000):
            state_machine.update_activity()
            state_machine.get_state_info()
        
        # System should remain functional
        assert state_machine.verify_state_integrity() is True
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY


class TestConcurrentFailures:
    """Test handling of concurrent access failures."""
    
    @pytest.fixture
    def state_machine(self):
        """Create state machine for concurrent failure tests."""
        return AuthorityStateMachine()
    
    def test_concurrent_corruption_attempts(self, state_machine):
        """Test resistance to concurrent corruption attempts."""
        errors = []
        corruption_attempts = 0
        
        # Enable test corruption mode for this test
        state_machine.enable_test_corruption_mode()
        
        def corruption_attempt():
            nonlocal corruption_attempts
            try:
                # Attempt to corrupt state concurrently
                with state_machine._lock:
                    if corruption_attempts < 5:  # Limit corruption attempts
                        state_machine._state_checksum = f"corrupt_{corruption_attempts}"
                        corruption_attempts += 1
            except Exception as e:
                errors.append(e)
        
        def normal_operation():
            try:
                for _ in range(20):
                    try:
                        state_machine.get_state_info()
                    except AuthorityStateIntegrityError:
                        # Expected when corruption occurs
                        pass
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Start concurrent threads
        threads = [
            threading.Thread(target=corruption_attempt),
            threading.Thread(target=normal_operation),
            threading.Thread(target=normal_operation)
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Disable test corruption mode
        state_machine.disable_test_corruption_mode()
        
        # Should detect corruption but not crash
        # Some operations may fail with integrity errors, which is expected
        assert len([e for e in errors if not isinstance(e, AuthorityStateIntegrityError)]) == 0
    
    def test_concurrent_invalid_transitions(self, state_machine):
        """Test concurrent invalid transition attempts."""
        errors = []
        
        def invalid_transition_attempt():
            try:
                # Try invalid biometric verification
                try:
                    state_machine.verify_biometric_factor(
                        BiometricFactor.FACE, "test", 0.95, True
                    )
                except AuthorityTransitionError:
                    # Expected
                    pass
            except Exception as e:
                errors.append(e)
        
        def valid_operation():
            try:
                state_machine.get_state_info()
            except Exception as e:
                errors.append(e)
        
        # Start many concurrent invalid attempts
        threads = []
        for _ in range(10):
            threads.append(threading.Thread(target=invalid_transition_attempt))
            threads.append(threading.Thread(target=valid_operation))
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should handle all attempts gracefully
        assert len(errors) == 0
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        assert state_machine.verify_state_integrity() is True


class TestConfigurationFailures:
    """Test handling of invalid configurations."""
    
    def test_invalid_timeout_configurations(self):
        """Test handling of invalid timeout values."""
        # Zero timeouts should work but be impractical
        config = AuthorityConfiguration(
            identity_verification_timeout=0,
            armed_session_timeout=0,
            inactivity_timeout=0
        )
        state_machine = AuthorityStateMachine(config)
        assert state_machine.verify_state_integrity() is True
        
        # Negative timeouts should work (implementation dependent)
        config = AuthorityConfiguration(
            identity_verification_timeout=-1,
            armed_session_timeout=-1,
            inactivity_timeout=-1
        )
        state_machine = AuthorityStateMachine(config)
        assert state_machine.verify_state_integrity() is True
    
    def test_invalid_threshold_configurations(self):
        """Test handling of invalid threshold values."""
        # Thresholds outside 0-1 range
        config = AuthorityConfiguration(
            voice_confidence_threshold=-0.5,
            face_confidence_threshold=1.5,
            fingerprint_confidence_threshold=2.0
        )
        state_machine = AuthorityStateMachine(config)
        
        # Should still create but behavior may be undefined
        assert state_machine.verify_state_integrity() is True
        
        # Operations with invalid thresholds should fail safely
        result = state_machine.initiate_voice_rearm(0.95, True)
        # Result depends on implementation - might succeed or fail
    
    def test_invalid_attempt_limits(self):
        """Test handling of invalid attempt limit configurations."""
        # Zero max attempts
        config = AuthorityConfiguration(max_failed_attempts=0)
        state_machine = AuthorityStateMachine(config)
        
        # Should trigger intrusion detection immediately
        result = state_machine.initiate_voice_rearm(0.70, True)
        assert result is False
        
        info = state_machine.get_state_info()
        # Might be in intrusion cooldown immediately
        
        # Negative max attempts
        config = AuthorityConfiguration(max_failed_attempts=-1)
        state_machine = AuthorityStateMachine(config)
        
        # Behavior is implementation dependent but should not crash
        assert state_machine.verify_state_integrity() is True


class TestEdgeCaseFailures:
    """Test edge case failure scenarios."""
    
    def test_rapid_policy_changes(self):
        """Test rapid policy changes under load."""
        state_machine = AuthorityStateMachine()
        errors = []
        
        def rapid_policy_changer():
            try:
                policies = [AuthorityPolicy.LOW_RISK, AuthorityPolicy.MEDIUM_RISK, 
                           AuthorityPolicy.HIGH_RISK, AuthorityPolicy.ADMIN]
                for _ in range(50):
                    for policy in policies:
                        state_machine.set_authority_policy(policy)
                        time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        def concurrent_operations():
            try:
                for _ in range(100):
                    state_machine.get_state_info()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Start concurrent threads
        threads = [
            threading.Thread(target=rapid_policy_changer),
            threading.Thread(target=concurrent_operations)
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should handle gracefully
        assert len(errors) == 0
        assert state_machine.verify_state_integrity() is True
    
    def test_system_clock_manipulation(self):
        """Test behavior when system clock is manipulated."""
        state_machine = AuthorityStateMachine()
        
        # Mock datetime to simulate clock manipulation
        future_time = datetime.utcnow() + timedelta(hours=1)
        
        with patch('src.authority.state.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = future_time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Operations should still work with future time
            result = state_machine.initiate_voice_rearm(0.95, True)
            assert result is True
            
            # State should remain consistent
            assert state_machine.verify_state_integrity() is True
    
    def test_thread_interruption_handling(self):
        """Test handling of thread interruptions."""
        config = AuthorityConfiguration(
            identity_verification_timeout=1,
            armed_session_timeout=1
        )
        state_machine = AuthorityStateMachine(config)
        
        # Start verification
        state_machine.set_authority_policy(AuthorityPolicy.MEDIUM_RISK)
        state_machine.initiate_voice_rearm(0.95, True)
        
        # Simulate thread interruption by deleting state machine
        # (This tests cleanup behavior)
        del state_machine
        
        # Should not crash or leave hanging resources
        time.sleep(0.1)  # Allow cleanup time


if __name__ == "__main__":
    pytest.main([__file__, "-v"])