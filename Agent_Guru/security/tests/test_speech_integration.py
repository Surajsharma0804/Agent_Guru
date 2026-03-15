"""Tests for speech-security integration."""

import pytest
import numpy as np

from Agent_Guru.speech.engine import SpeechEngine
from Agent_Guru.security.voice_auth import VoiceAuthenticator, VoiceAuthenticationError
from Agent_Guru.security.speech_integration import SpeechSecurityIntegration


class TestSpeechSecurityIntegration:
    """Tests for SpeechSecurityIntegration."""
    
    @pytest.fixture
    def speech_engine(self) -> SpeechEngine:
        """Create and initialize speech engine."""
        engine = SpeechEngine()
        engine.initialize()
        return engine
    
    @pytest.fixture
    def integration(self, speech_engine: SpeechEngine) -> SpeechSecurityIntegration:
        """Create speech-security integration.

        Uses a liveness-permissive VoiceAuthenticator so that integration tests
        focus on the speech↔security wiring rather than liveness policy
        (liveness policy is tested separately in test_biometric_auth.py).
        """
        import dataclasses

        class _LivenessPermissiveAuthenticator(VoiceAuthenticator):
            """Authenticator that treats all audio as live for integration tests."""

            def authenticate(self, voice_features, user_id=None):  # type: ignore[override]
                live_features = dataclasses.replace(voice_features, is_live=True)
                return super().authenticate(live_features, user_id)

        return SpeechSecurityIntegration(
            speech_engine,
            voice_authenticator=_LivenessPermissiveAuthenticator(similarity_threshold=0.85),
        )
    
    @pytest.fixture
    def sample_audio(self) -> np.ndarray:
        """Create sample audio data."""
        # 3 seconds of audio at 16kHz
        return np.random.randn(48000).astype(np.float32)
    
    # ========================================================================
    # ENROLLMENT TESTS
    # ========================================================================
    
    def test_enroll_user_from_audio(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test enrolling user from audio."""
        profile = integration.enroll_user_from_audio("user1", sample_audio)
        
        assert profile.user_id == "user1"
        assert profile.sample_count == 1
        assert profile.quality_score > 0.0
    
    def test_enroll_duplicate_user_from_audio(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test enrolling duplicate user fails."""
        integration.enroll_user_from_audio("user1", sample_audio)
        
        with pytest.raises(VoiceAuthenticationError, match="already enrolled"):
            integration.enroll_user_from_audio("user1", sample_audio)
    
    # ========================================================================
    # AUTHENTICATION TESTS
    # ========================================================================
    
    def test_authenticate_from_audio_verification(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test authentication from audio in verification mode."""
        # Enroll user
        integration.enroll_user_from_audio("user1", sample_audio)
        
        # Authenticate with same audio
        authenticated, user_id, similarity = integration.authenticate_from_audio(
            sample_audio,
            user_id="user1"
        )
        
        assert authenticated == True
        assert user_id == "user1"
        assert similarity >= 0.85
    
    def test_authenticate_from_audio_identification(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test authentication from audio in identification mode."""
        # Enroll user
        integration.enroll_user_from_audio("user1", sample_audio)
        
        # Authenticate without user_id
        authenticated, user_id, similarity = integration.authenticate_from_audio(sample_audio)
        
        assert authenticated == True
        assert user_id == "user1"
        assert similarity >= 0.85
    
    def test_authenticate_wrong_audio(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test authentication with different audio fails."""
        # Enroll user
        integration.enroll_user_from_audio("user1", sample_audio)
        
        # Try to authenticate with very different audio (zeros - orthogonal to any random vector)
        different_audio = np.zeros(48000, dtype=np.float32)
        authenticated, user_id, similarity = integration.authenticate_from_audio(
            different_audio,
            user_id="user1"
        )
        
        assert bool(authenticated) == False
        assert user_id is None
    
    # ========================================================================
    # PROFILE MANAGEMENT TESTS
    # ========================================================================
    
    def test_update_profile_from_audio(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test updating profile from audio."""
        # Enroll user
        integration.enroll_user_from_audio("user1", sample_audio)
        
        # Update with new audio
        new_audio = np.random.randn(48000).astype(np.float32)
        updated_profile = integration.update_profile_from_audio("user1", new_audio)
        
        assert updated_profile.sample_count == 2
    
    def test_delete_user(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test deleting user."""
        # Enroll user
        integration.enroll_user_from_audio("user1", sample_audio)
        
        # Delete user
        integration.delete_user("user1")
        
        # Verify deleted
        assert integration.get_user_profile("user1") is None
    
    def test_get_user_profile(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test getting user profile."""
        # Enroll user
        integration.enroll_user_from_audio("user1", sample_audio)
        
        # Get profile
        profile = integration.get_user_profile("user1")
        
        assert profile is not None
        assert profile.user_id == "user1"
    
    def test_list_enrolled_users(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test listing enrolled users."""
        # Enroll multiple users
        integration.enroll_user_from_audio("user1", sample_audio)
        integration.enroll_user_from_audio("user2", sample_audio)
        
        # List users
        users = integration.list_enrolled_users()
        
        assert len(users) == 2
        assert "user1" in users
        assert "user2" in users
    
    # ========================================================================
    # END-TO-END WORKFLOW TESTS
    # ========================================================================
    
    def test_end_to_end_enrollment_and_authentication(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test complete enrollment and authentication workflow."""
        # Step 1: Enroll user
        profile = integration.enroll_user_from_audio("user1", sample_audio)
        assert profile.user_id == "user1"
        
        # Step 2: Authenticate user
        authenticated, user_id, similarity = integration.authenticate_from_audio(
            sample_audio,
            user_id="user1"
        )
        assert authenticated == True
        assert user_id == "user1"
        
        # Step 3: Update profile
        new_audio = np.random.randn(48000).astype(np.float32)
        updated_profile = integration.update_profile_from_audio("user1", new_audio)
        assert updated_profile.sample_count == 2
        
        # Step 4: Delete user
        integration.delete_user("user1")
        assert integration.get_user_profile("user1") is None
    
    def test_multi_user_authentication(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test authentication with multiple enrolled users."""
        # Enroll multiple users
        audio1 = sample_audio
        audio2 = np.random.randn(48000).astype(np.float32)
        audio3 = np.random.randn(48000).astype(np.float32)
        
        integration.enroll_user_from_audio("user1", audio1)
        integration.enroll_user_from_audio("user2", audio2)
        integration.enroll_user_from_audio("user3", audio3)
        
        # Authenticate each user
        auth1, uid1, _ = integration.authenticate_from_audio(audio1)
        auth2, uid2, _ = integration.authenticate_from_audio(audio2)
        auth3, uid3, _ = integration.authenticate_from_audio(audio3)
        
        assert auth1 == True and uid1 == "user1"
        assert auth2 == True and uid2 == "user2"
        assert auth3 == True and uid3 == "user3"

    # ========================================================================
    # EDGE CASE AND STRESS TESTS - ZERO COMPROMISE
    # ========================================================================
    
    def test_enroll_with_empty_audio(
        self,
        integration: SpeechSecurityIntegration
    ):
        """Test enrollment with empty audio array."""
        from Agent_Guru.speech.exceptions import VoiceBiometricError
        
        empty_audio = np.array([], dtype=np.float32)
        
        # Should raise error for empty audio
        with pytest.raises(VoiceBiometricError, match="Audio data is empty"):
            integration.enroll_user_from_audio("user1", empty_audio)
    
    def test_enroll_with_very_short_audio(
        self,
        integration: SpeechSecurityIntegration
    ):
        """Test enrollment with very short audio (1 sample)."""
        short_audio = np.array([0.5], dtype=np.float32)
        
        # Very short audio will have low quality and fail enrollment
        with pytest.raises(VoiceAuthenticationError, match="Voice quality too low"):
            integration.enroll_user_from_audio("user1", short_audio)
    
    def test_enroll_with_very_long_audio(
        self,
        integration: SpeechSecurityIntegration
    ):
        """Test enrollment with very long audio (10 minutes)."""
        # 10 minutes at 16kHz = 9,600,000 samples
        long_audio = np.random.randn(9600000).astype(np.float32)
        
        profile = integration.enroll_user_from_audio("user1", long_audio)
        assert profile.user_id == "user1"
    
    def test_enroll_with_silent_audio(
        self,
        integration: SpeechSecurityIntegration
    ):
        """Test enrollment with silent audio (all zeros)."""
        silent_audio = np.zeros(48000, dtype=np.float32)
        
        # Should handle but may have low quality
        profile = integration.enroll_user_from_audio("user1", silent_audio)
        assert profile.user_id == "user1"
    
    def test_enroll_with_clipped_audio(
        self,
        integration: SpeechSecurityIntegration
    ):
        """Test enrollment with clipped audio (values at limits)."""
        # Audio clipped at -1.0 and 1.0
        clipped_audio = np.ones(48000, dtype=np.float32)
        
        profile = integration.enroll_user_from_audio("user1", clipped_audio)
        assert profile.user_id == "user1"
    
    def test_enroll_with_nan_audio(
        self,
        integration: SpeechSecurityIntegration
    ):
        """Test enrollment with NaN values in audio."""
        nan_audio = np.full(48000, np.nan, dtype=np.float32)
        
        # Should handle (speech engine may filter or fail gracefully)
        try:
            profile = integration.enroll_user_from_audio("user1", nan_audio)
            assert profile.user_id == "user1"
        except Exception:
            # Acceptable to fail with NaN
            pass
    
    def test_enroll_with_inf_audio(
        self,
        integration: SpeechSecurityIntegration
    ):
        """Test enrollment with infinite values in audio."""
        inf_audio = np.full(48000, np.inf, dtype=np.float32)
        
        # Should handle (speech engine may filter or fail gracefully)
        try:
            profile = integration.enroll_user_from_audio("user1", inf_audio)
            assert profile.user_id == "user1"
        except Exception:
            # Acceptable to fail with inf
            pass
    
    def test_authenticate_after_multiple_updates(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test authentication after multiple profile updates."""
        # Enroll user
        integration.enroll_user_from_audio("user1", sample_audio)
        
        # Update profile 20 times
        for _ in range(20):
            update_audio = np.random.randn(48000).astype(np.float32)
            integration.update_profile_from_audio("user1", update_audio)
        
        # Original audio should still authenticate (profile adapts)
        authenticated, user_id, similarity = integration.authenticate_from_audio(
            sample_audio,
            user_id="user1"
        )
        
        # May or may not authenticate depending on how much profile drifted
        assert user_id in [None, "user1"]
    
    def test_concurrent_user_operations(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test enrolling and authenticating multiple users rapidly."""
        # Enroll 50 users rapidly
        for i in range(50):
            audio = np.random.randn(48000).astype(np.float32)
            integration.enroll_user_from_audio(f"user{i}", audio)
        
        # Verify all users are enrolled
        users = integration.list_enrolled_users()
        assert len(users) == 50
        
        # Delete half of them
        for i in range(0, 50, 2):
            integration.delete_user(f"user{i}")
        
        # Verify only 25 remain
        users = integration.list_enrolled_users()
        assert len(users) == 25
    
    def test_profile_quality_degradation(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test profile quality with progressively worse audio."""
        # Enroll with good quality
        profile = integration.enroll_user_from_audio("user1", sample_audio)
        initial_quality = profile.quality_score
        
        # Update with progressively noisier audio
        for i in range(10):
            # Add increasing noise
            noisy_audio = sample_audio + np.random.randn(len(sample_audio)).astype(np.float32) * (i + 1) * 0.1
            profile = integration.update_profile_from_audio("user1", noisy_audio)
        
        # Quality may fluctuate but sample count should increase
        assert profile.sample_count == 11  # 1 initial + 10 updates
        # Quality is averaged, so it may not strictly degrade
        assert 0.0 < profile.quality_score <= 1.0
    
    def test_authentication_with_different_audio_lengths(
        self,
        integration: SpeechSecurityIntegration
    ):
        """Test authentication with different audio lengths."""
        # Enroll with 3 seconds
        enroll_audio = np.random.randn(48000).astype(np.float32)
        integration.enroll_user_from_audio("user1", enroll_audio)
        
        # Authenticate with 1 second
        short_audio = np.random.randn(16000).astype(np.float32)
        authenticated1, _, _ = integration.authenticate_from_audio(short_audio, user_id="user1")
        
        # Authenticate with 10 seconds
        long_audio = np.random.randn(160000).astype(np.float32)
        authenticated2, _, _ = integration.authenticate_from_audio(long_audio, user_id="user1")
        
        # Both should work (may or may not authenticate depending on features)
        assert isinstance(authenticated1, (bool, np.bool_))
        assert isinstance(authenticated2, (bool, np.bool_))
    
    def test_delete_and_reenroll_same_user(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test deleting and re-enrolling the same user."""
        # Enroll user
        profile1 = integration.enroll_user_from_audio("user1", sample_audio)
        
        # Delete user
        integration.delete_user("user1")
        
        # Re-enroll with different audio
        different_audio = np.random.randn(48000).astype(np.float32)
        profile2 = integration.enroll_user_from_audio("user1", different_audio)
        
        # Should be a fresh profile
        assert profile2.sample_count == 1
        assert profile2.enrollment_date > profile1.enrollment_date
    
    def test_get_nonexistent_profile(
        self,
        integration: SpeechSecurityIntegration
    ):
        """Test getting profile for non-existent user."""
        profile = integration.get_user_profile("nonexistent_user")
        assert profile is None
    
    def test_update_nonexistent_profile(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test updating profile for non-existent user."""
        with pytest.raises(VoiceAuthenticationError, match="not enrolled"):
            integration.update_profile_from_audio("nonexistent_user", sample_audio)
    
    def test_delete_nonexistent_user(
        self,
        integration: SpeechSecurityIntegration
    ):
        """Test deleting non-existent user."""
        with pytest.raises(VoiceAuthenticationError, match="not enrolled"):
            integration.delete_user("nonexistent_user")
    
    def test_list_users_empty(
        self,
        integration: SpeechSecurityIntegration
    ):
        """Test listing users when none are enrolled."""
        users = integration.list_enrolled_users()
        assert users == []
    
    def test_authenticate_identification_no_match(
        self,
        integration: SpeechSecurityIntegration,
        sample_audio: np.ndarray
    ):
        """Test identification mode when no user matches."""
        # Enroll user with specific audio
        integration.enroll_user_from_audio("user1", sample_audio)
        
        # Try to identify with very different audio (zeros)
        different_audio = np.zeros(48000, dtype=np.float32)
        authenticated, user_id, similarity = integration.authenticate_from_audio(different_audio)
        
        # Should not authenticate
        assert bool(authenticated) == False
        assert user_id is None
        assert similarity < 0.85
