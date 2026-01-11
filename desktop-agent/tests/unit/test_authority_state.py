"""
Unit Tests for Authority State Machine

These tests verify the core functionality of the AuthorityStateMachine,
including state transitions, thread safety, and security invariants.
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
    AuthorityTransitionError,
    create_authority_state_machine,
    get_default_authority_config
)


class TestAuthorityState:
    """Test AuthorityState enum values."""
    
    def test_authority_state_values(self):
        """Test that all required authority states are defined."""
        assert AuthorityState.LOCKED_LISTEN_ONLY.value == "LOCKED_LISTEN_ONLY"
        assert AuthorityState.IDENTITY_VERIFICATION.value == "IDENTITY_VERIFICATION"
        assert AuthorityState.ARMED.value == "ARMED"
        assert AuthorityState.INTRUSION_DETECTED.value == "INTRUSION_DETECTED"
    
    def test_authority_state_count(self):
        """Test that we have exactly the expected number of states."""
        assert len(AuthorityState) == 4


class TestAuthorityConfiguration:
    """Test AuthorityConfiguration class."""
    
    def test_default_configuration(self):
        """Test default configuration values."""
        config = AuthorityConfiguration()
        
        # Timeout configurations
        assert config.identity_verification_timeout == 30
        assert config.armed_session_timeout == 300
        assert config.inactivity_timeout == 60
        
        # Biometric thresholds
        assert config.voice_confidence_threshold == 0.85
        assert config.face_confidence_threshold == 0.90
        assert config.fingerprint_confidence_threshold == 0.95
        
        # Security policies
        assert config.max_failed_attempts == 3
        assert config.intrusion_cooldown_seconds == 300
        assert config.require_biometric_for_rearm is True
    
    def test_policy_requirements(self):
        """Test policy requirements mapping."""
        config = AuthorityConfiguration()
        
        assert config.policy_requirements[AuthorityPolicy.LOW_RISK] == {BiometricFactor.VOICE}
        assert config.policy_requirements[AuthorityPolicy.MEDIUM_RISK] == {BiometricFactor.VOICE, BiometricFactor.FACE}
        assert config.policy_requirements[AuthorityPolicy.HIGH_RISK] == {BiometricFactor.VOICE, BiometricFactor.FACE, BiometricFactor.FINGERPRINT}
        assert config.policy_requirements[AuthorityPolicy.ADMIN] == {BiometricFactor.VOICE, BiometricFactor.FACE, BiometricFactor.FINGERPRINT}


class TestAuthorityStateMachine:
    """Test AuthorityStateMachine core functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration with shorter timeouts."""
        return AuthorityConfiguration(
            identity_verification_timeout=5,
            armed_session_timeout=10,
            inactivity_timeout=3,
            intrusion_cooldown_seconds=5
        )
    
    @pytest.fixture
    def state_machine(self, config):
        """Create test state machine."""
        return AuthorityStateMachine(config)
    
    def test_initial_state(self, state_machine):
        """Test initial state is LOCKED_LISTEN_ONLY."""
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        assert state_machine.is_locked is True
        assert state_machine.is_armed is False
        assert state_machine.current_policy == AuthorityPolicy.LOW_RISK
    
    def test_session_id_generation(self, state_machine):
        """Test session ID is generated and accessible."""
        session_id = state_machine.session_id
        assert isinstance(session_id, str)
        assert len(session_id) > 0
        
        # Session ID should be consistent
        assert state_machine.session_id == session_id
    
    def test_state_info(self, state_machine):
        """Test comprehensive state information."""
        info = state_machine.get_state_info()
        
        assert info['state'] == AuthorityState.LOCKED_LISTEN_ONLY.value
        assert info['policy'] == AuthorityPolicy.LOW_RISK.value
        assert info['is_armed'] is False
        assert info['is_locked'] is True
        assert info['failed_attempts'] == 0
        assert info['required_factors'] == ['voice']
        assert info['verification_in_progress'] is False
        assert info['intrusion_cooldown_active'] is False
    
    def test_voice_rearm_success_low_risk(self, state_machine):
        """Test successful voice re-arming with low risk policy."""
        # Should succeed with voice-only for low risk
        result = state_machine.initiate_voice_rearm(
            voice_confidence=0.90,
            speaker_verified=True
        )
        
        assert result is True
        assert state_machine.current_state == AuthorityState.ARMED
        assert state_machine.is_armed is True
    
    def test_voice_rearm_insufficient_confidence(self, state_machine):
        """Test voice re-arming failure due to low confidence."""
        result = state_machine.initiate_voice_rearm(
            voice_confidence=0.70,  # Below threshold
            speaker_verified=True
        )
        
        assert result is False
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        assert state_machine.is_armed is False
    
    def test_voice_rearm_speaker_not_verified(self, state_machine):
        """Test voice re-arming failure due to speaker verification failure."""
        result = state_machine.initiate_voice_rearm(
            voice_confidence=0.90,
            speaker_verified=False
        )
        
        assert result is False
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        assert state_machine.is_armed is False
    
    def test_voice_rearm_medium_risk_policy(self, state_machine):
        """Test voice re-arming with medium risk policy requires additional verification."""
        # Set medium risk policy
        state_machine.set_authority_policy(AuthorityPolicy.MEDIUM_RISK)
        
        result = state_machine.initiate_voice_rearm(
            voice_confidence=0.90,
            speaker_verified=True
        )
        
        # Should transition to identity verification, not directly armed
        assert result is True
        assert state_machine.current_state == AuthorityState.IDENTITY_VERIFICATION
        assert state_machine.is_armed is False
    
    def test_biometric_verification_success(self, state_machine):
        """Test successful biometric verification during identity verification."""
        # Set medium risk and initiate voice rearm
        state_machine.set_authority_policy(AuthorityPolicy.MEDIUM_RISK)
        state_machine.initiate_voice_rearm(0.90, True)
        
        # Verify face biometric
        result = state_machine.enforce_biometric_factor_verification_boundary(
            factor=BiometricFactor.FACE,
            provider="windows_hello",
            confidence=0.95,
            success=True
        )
        
        assert result is True
        assert state_machine.current_state == AuthorityState.ARMED
        assert state_machine.is_armed is True
    
    def test_biometric_verification_failure(self, state_machine):
        """Test biometric verification failure."""
        # Set medium risk and initiate voice rearm
        state_machine.set_authority_policy(AuthorityPolicy.MEDIUM_RISK)
        state_machine.initiate_voice_rearm(0.90, True)
        
        # Fail face biometric
        result = state_machine.enforce_biometric_factor_verification_boundary(
            factor=BiometricFactor.FACE,
            provider="windows_hello",
            confidence=0.50,
            success=False,
            failure_reason="low_confidence"
        )
        
        assert result is False
        assert state_machine.current_state == AuthorityState.IDENTITY_VERIFICATION
        assert state_machine.is_armed is False
    
    def test_authority_revocation(self, state_machine):
        """Test manual authority revocation."""
        # First arm the system
        state_machine.initiate_voice_rearm(0.90, True)
        assert state_machine.is_armed is True
        
        # Revoke authority
        result = state_machine.revoke_authority(
            reason=StateTransitionReason.MANUAL_REVOKE,
            metadata={"user_requested": "true"}
        )
        
        assert result is True
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        assert state_machine.is_armed is False
    
    def test_activity_update(self, state_machine):
        """Test activity timestamp update."""
        # Arm the system
        state_machine.initiate_voice_rearm(0.90, True)
        
        initial_info = state_machine.get_state_info()
        time.sleep(0.1)  # Small delay
        
        # Update activity
        state_machine.update_activity()
        
        updated_info = state_machine.get_state_info()
        assert updated_info['time_since_activity'] < initial_info['time_since_activity']
    
    def test_policy_change_requires_reauth(self, state_machine):
        """Test that policy changes requiring more factors revoke authority."""
        # Arm with low risk policy
        state_machine.initiate_voice_rearm(0.90, True)
        assert state_machine.is_armed is True
        
        # Change to high risk policy
        result = state_machine.set_authority_policy(AuthorityPolicy.HIGH_RISK)
        
        assert result is True
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        assert state_machine.is_armed is False
    
    def test_state_history_tracking(self, state_machine):
        """Test state transition history tracking."""
        initial_history = state_machine.get_state_history()
        assert len(initial_history) == 1  # Initial startup transition
        
        # Perform some transitions
        state_machine.initiate_voice_rearm(0.90, True)
        state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
        
        final_history = state_machine.get_state_history()
        assert len(final_history) == 3  # startup + arm + revoke
        
        # Check most recent transition
        latest = final_history[0]
        assert latest.to_state == AuthorityState.LOCKED_LISTEN_ONLY
        assert latest.reason == StateTransitionReason.MANUAL_REVOKE
    
    def test_integrity_verification(self, state_machine):
        """Test state integrity verification."""
        # Should pass initially
        assert state_machine.verify_state_integrity() is True
        
        # Simulate integrity corruption by directly modifying internal state
        # DANGEROUS: Enable test corruption mode for this test only
        with state_machine._lock:
            state_machine._test_corruption_mode = True
            state_machine._state_checksum = "corrupted_checksum"
            delattr(state_machine, "_test_corruption_mode")
        
        # Should detect corruption
        assert state_machine.verify_state_integrity() is False
        
        # Should raise exception on access
        with pytest.raises(AuthorityStateIntegrityError):
            _ = state_machine.current_state
    
    def test_invalid_state_transitions(self, state_machine):
        """Test that invalid state transitions are rejected."""
        # Try to verify biometric without being in identity verification
        with pytest.raises(AuthorityTransitionError):
            state_machine.enforce_biometric_factor_verification_boundary(
                factor=BiometricFactor.FACE,
                provider="test",
                confidence=0.95,
                success=True
            )
    
    def test_intrusion_detection_trigger(self, state_machine):
        """Test intrusion detection after multiple failed attempts."""
        # Fail authentication multiple times
        for _ in range(3):  # max_failed_attempts = 3
            state_machine.initiate_voice_rearm(0.70, True)  # Low confidence
        
        # Next failure should trigger intrusion detection
        state_machine.initiate_voice_rearm(0.70, True)
        
        info = state_machine.get_state_info()
        assert info['intrusion_cooldown_active'] is True
    
    def test_intrusion_cooldown_blocks_rearm(self, state_machine):
        """Test that intrusion cooldown blocks re-arming attempts."""
        # Trigger intrusion detection
        for _ in range(4):
            state_machine.initiate_voice_rearm(0.70, True)
        
        # Should be in cooldown
        assert state_machine.get_state_info()['intrusion_cooldown_active'] is True
        
        # Valid attempt should be blocked
        result = state_machine.initiate_voice_rearm(0.95, True)
        assert result is False


class TestThreadSafety:
    """Test thread safety of AuthorityStateMachine."""
    
    @pytest.fixture
    def state_machine(self):
        """Create state machine for thread safety tests."""
        config = AuthorityConfiguration(
            identity_verification_timeout=10,
            armed_session_timeout=30,
            inactivity_timeout=10
        )
        return AuthorityStateMachine(config)
    
    def test_concurrent_state_access(self, state_machine):
        """Test concurrent access to state properties."""
        results = []
        errors = []
        
        def access_state():
            try:
                for _ in range(100):
                    state = state_machine.current_state
                    is_armed = state_machine.is_armed
                    info = state_machine.get_state_info()
                    results.append((state, is_armed, info['state']))
                    time.sleep(0.001)  # Small delay
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = [threading.Thread(target=access_state) for _ in range(5)]
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should have no errors and consistent results
        assert len(errors) == 0
        assert len(results) == 500  # 5 threads * 100 iterations
        
        # All results should be consistent (same state)
        states = set(result[0] for result in results)
        assert len(states) == 1  # Only one state should be observed
    
    def test_concurrent_voice_rearm(self, state_machine):
        """Test concurrent voice re-arming attempts."""
        results = []
        errors = []
        
        def attempt_rearm():
            try:
                result = state_machine.initiate_voice_rearm(0.90, True)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Start multiple concurrent re-arm attempts
        threads = [threading.Thread(target=attempt_rearm) for _ in range(10)]
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have some errors (expected when trying to rearm from non-LOCKED state)
        # Only one should succeed (first one), others should get exceptions
        successful = sum(1 for result in results if result)
        assert successful <= 1
        
        # Total attempts should equal results + errors
        assert len(results) + len(errors) == 10
        
        # If any succeeded, system should be armed
        if successful > 0:
            assert state_machine.is_armed is True
    
    def test_concurrent_activity_updates(self, state_machine):
        """Test concurrent activity updates."""
        # Arm the system first
        state_machine.initiate_voice_rearm(0.90, True)
        
        errors = []
        
        def update_activity():
            try:
                for _ in range(50):
                    state_machine.update_activity()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads updating activity
        threads = [threading.Thread(target=update_activity) for _ in range(5)]
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have no errors
        assert len(errors) == 0
        
        # System should still be armed
        assert state_machine.is_armed is True


class TestTimeoutHandling:
    """Test timeout handling and monitoring."""
    
    @pytest.fixture
    def fast_config(self):
        """Create configuration with very short timeouts for testing."""
        return AuthorityConfiguration(
            identity_verification_timeout=1,
            armed_session_timeout=2,
            inactivity_timeout=1
        )
    
    def test_identity_verification_timeout(self, fast_config):
        """Test identity verification timeout."""
        state_machine = AuthorityStateMachine(fast_config)
        
        # Set medium risk policy and start verification
        state_machine.set_authority_policy(AuthorityPolicy.MEDIUM_RISK)
        state_machine.initiate_voice_rearm(0.90, True)
        
        assert state_machine.current_state == AuthorityState.IDENTITY_VERIFICATION
        
        # Wait for timeout
        time.sleep(1.5)
        
        # Should timeout and return to locked state
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
    
    def test_armed_session_timeout(self, fast_config):
        """Test armed session timeout."""
        state_machine = AuthorityStateMachine(fast_config)
        
        # Arm the system
        state_machine.initiate_voice_rearm(0.90, True)
        assert state_machine.is_armed is True
        
        # Wait for session timeout
        time.sleep(2.5)
        
        # Should timeout and return to locked state
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
    
    def test_inactivity_timeout(self, fast_config):
        """Test inactivity timeout."""
        state_machine = AuthorityStateMachine(fast_config)
        
        # Arm the system
        state_machine.initiate_voice_rearm(0.90, True)
        assert state_machine.is_armed is True
        
        # Wait for inactivity timeout (no activity updates)
        time.sleep(1.5)
        
        # Should timeout due to inactivity
        assert state_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY


class TestFactoryFunctions:
    """Test factory functions and utilities."""
    
    def test_create_authority_state_machine(self):
        """Test factory function for creating state machine."""
        # With default config
        sm1 = create_authority_state_machine()
        assert isinstance(sm1, AuthorityStateMachine)
        assert sm1.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        
        # With custom config
        config = AuthorityConfiguration(voice_confidence_threshold=0.95)
        sm2 = create_authority_state_machine(config)
        assert isinstance(sm2, AuthorityStateMachine)
        assert sm2.current_state == AuthorityState.LOCKED_LISTEN_ONLY
    
    def test_get_default_authority_config(self):
        """Test default configuration factory."""
        config = get_default_authority_config()
        assert isinstance(config, AuthorityConfiguration)
        assert config.voice_confidence_threshold == 0.85
        assert config.max_failed_attempts == 3


class TestSecurityInvariants:
    """Test security invariants and edge cases."""
    
    @pytest.fixture
    def state_machine(self):
        """Create state machine for security tests."""
        return AuthorityStateMachine()
    
    def test_no_bypass_locked_state(self, state_machine):
        """Test that locked state cannot be bypassed."""
        # Should start locked
        assert state_machine.is_locked is True
        
        # Direct biometric verification should fail
        with pytest.raises(AuthorityTransitionError):
            state_machine.enforce_biometric_factor_verification_boundary(
                BiometricFactor.FACE, "test", 0.95, True
            )
        
        # Should still be locked
        assert state_machine.is_locked is True
    
    def test_authority_revocation_always_works(self, state_machine):
        """Test that authority can always be revoked."""
        # Arm the system
        state_machine.initiate_voice_rearm(0.90, True)
        assert state_machine.is_armed is True
        
        # Revocation should always work
        result = state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
        assert result is True
        assert state_machine.is_locked is True
        
        # Multiple revocations should be safe
        result = state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
        assert result is True
        assert state_machine.is_locked is True
    
    def test_session_isolation(self, state_machine):
        """Test that sessions are properly isolated."""
        initial_session = state_machine.session_id
        
        # Arm and revoke to trigger session change
        state_machine.initiate_voice_rearm(0.90, True)
        state_machine.revoke_authority(StateTransitionReason.MANUAL_REVOKE)
        
        # Session ID should change
        new_session = state_machine.session_id
        assert new_session != initial_session
    
    def test_state_machine_cleanup(self):
        """Test proper cleanup of state machine resources."""
        config = AuthorityConfiguration(
            identity_verification_timeout=1,
            armed_session_timeout=1
        )
        
        # Create and destroy state machine
        sm = AuthorityStateMachine(config)
        session_id = sm.session_id
        
        # Verify it's working
        assert sm.current_state == AuthorityState.LOCKED_LISTEN_ONLY
        
        # Delete should clean up monitoring thread
        del sm
        
        # Give time for cleanup
        time.sleep(0.1)
        
        # Should not crash or leave hanging threads
        # (This is mainly testing that __del__ works properly)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])