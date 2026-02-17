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
        """Create speech-security integration."""
        return SpeechSecurityIntegration(speech_engine)
    
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
