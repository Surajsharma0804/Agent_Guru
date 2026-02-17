"""Tests for voice authentication system."""

import pytest
import numpy as np
from datetime import datetime

from Agent_Guru.security.voice_auth import (
    VoiceAuthenticator,
    VoiceProfile,
    VoiceAuthenticationError
)
from Agent_Guru.speech.models import VoiceFeatures


class TestVoiceAuthenticator:
    """Tests for VoiceAuthenticator."""
    
    @pytest.fixture
    def authenticator(self) -> VoiceAuthenticator:
        """Create voice authenticator."""
        return VoiceAuthenticator(similarity_threshold=0.85)
    
    @pytest.fixture
    def voice_features(self) -> VoiceFeatures:
        """Create sample voice features."""
        return VoiceFeatures(
            feature_vector=np.random.randn(128).astype(np.float32),
            sample_rate=16000,
            duration=3.0,
            quality_score=0.9
        )
    
    # ========================================================================
    # ENROLLMENT TESTS
    # ========================================================================
    
    def test_enroll_user(self, authenticator: VoiceAuthenticator, voice_features: VoiceFeatures):
        """Test user enrollment."""
        profile = authenticator.enroll_user("user1", voice_features)
        
        assert profile.user_id == "user1"
        assert np.array_equal(profile.feature_vector, voice_features.feature_vector)
        assert profile.quality_score == voice_features.quality_score
        assert profile.sample_count == 1
        assert isinstance(profile.enrollment_date, datetime)
    
    def test_enroll_duplicate_user(self, authenticator: VoiceAuthenticator, voice_features: VoiceFeatures):
        """Test enrolling duplicate user fails."""
        authenticator.enroll_user("user1", voice_features)
        
        with pytest.raises(VoiceAuthenticationError, match="already enrolled"):
            authenticator.enroll_user("user1", voice_features)
    
    def test_enroll_low_quality_voice(self, authenticator: VoiceAuthenticator):
        """Test enrolling low quality voice fails."""
        low_quality_features = VoiceFeatures(
            feature_vector=np.random.randn(128).astype(np.float32),
            sample_rate=16000,
            duration=1.0,
            quality_score=0.4  # Below threshold (0.5)
        )
        
        with pytest.raises(VoiceAuthenticationError, match="Voice quality too low"):
            authenticator.enroll_user("user1", low_quality_features)
    
    # ========================================================================
    # AUTHENTICATION TESTS
    # ========================================================================
    
    def test_authenticate_verification_mode(
        self,
        authenticator: VoiceAuthenticator,
        voice_features: VoiceFeatures
    ):
        """Test authentication in verification mode."""
        # Enroll user
        authenticator.enroll_user("user1", voice_features)
        
        # Authenticate with same features (should succeed)
        authenticated, user_id, similarity = authenticator.authenticate(
            voice_features,
            user_id="user1"
        )
        
        assert authenticated == True
        assert user_id == "user1"
        assert similarity >= 0.85
    
    def test_authenticate_identification_mode(
        self,
        authenticator: VoiceAuthenticator,
        voice_features: VoiceFeatures
    ):
        """Test authentication in identification mode."""
        # Enroll user
        authenticator.enroll_user("user1", voice_features)
        
        # Authenticate without user_id (should identify user1)
        authenticated, user_id, similarity = authenticator.authenticate(voice_features)
        
        assert authenticated == True
        assert user_id == "user1"
        assert similarity >= 0.85
    
    def test_authenticate_wrong_user(
        self,
        authenticator: VoiceAuthenticator,
        voice_features: VoiceFeatures
    ):
        """Test authentication with wrong user fails."""
        # Enroll user1
        authenticator.enroll_user("user1", voice_features)
        
        # Try to authenticate as user2 (different features)
        different_features = VoiceFeatures(
            feature_vector=np.random.randn(128).astype(np.float32),
            sample_rate=16000,
            duration=3.0,
            quality_score=0.9
        )
        
        authenticated, user_id, similarity = authenticator.authenticate(
            different_features,
            user_id="user1"
        )
        
        assert authenticated == False
        assert user_id is None
        assert similarity < 0.85
    
    def test_authenticate_no_enrolled_users(
        self,
        authenticator: VoiceAuthenticator,
        voice_features: VoiceFeatures
    ):
        """Test authentication with no enrolled users fails."""
        with pytest.raises(VoiceAuthenticationError, match="No enrolled users"):
            authenticator.authenticate(voice_features)
    
    def test_authenticate_user_not_enrolled(
        self,
        authenticator: VoiceAuthenticator,
        voice_features: VoiceFeatures
    ):
        """Test authentication for non-enrolled user fails."""
        with pytest.raises(VoiceAuthenticationError, match="User user1 not enrolled"):
            authenticator.authenticate(voice_features, user_id="user1")
    
    # ========================================================================
    # PROFILE MANAGEMENT TESTS
    # ========================================================================
    
    def test_update_profile(
        self,
        authenticator: VoiceAuthenticator,
        voice_features: VoiceFeatures
    ):
        """Test profile update."""
        # Enroll user
        authenticator.enroll_user("user1", voice_features)
        
        # Update with new features
        new_features = VoiceFeatures(
            feature_vector=np.random.randn(128).astype(np.float32),
            sample_rate=16000,
            duration=3.0,
            quality_score=0.95
        )
        
        updated_profile = authenticator.update_profile("user1", new_features)
        
        assert updated_profile.sample_count == 2
        assert updated_profile.quality_score > voice_features.quality_score
    
    def test_update_profile_not_enrolled(
        self,
        authenticator: VoiceAuthenticator,
        voice_features: VoiceFeatures
    ):
        """Test updating non-enrolled user fails."""
        with pytest.raises(VoiceAuthenticationError, match="not enrolled"):
            authenticator.update_profile("user1", voice_features)
    
    def test_delete_profile(
        self,
        authenticator: VoiceAuthenticator,
        voice_features: VoiceFeatures
    ):
        """Test profile deletion."""
        # Enroll user
        authenticator.enroll_user("user1", voice_features)
        
        # Delete profile
        authenticator.delete_profile("user1")
        
        # Verify deleted
        assert authenticator.get_profile("user1") is None
    
    def test_delete_profile_not_enrolled(self, authenticator: VoiceAuthenticator):
        """Test deleting non-enrolled user fails."""
        with pytest.raises(VoiceAuthenticationError, match="not enrolled"):
            authenticator.delete_profile("user1")
    
    def test_get_profile(
        self,
        authenticator: VoiceAuthenticator,
        voice_features: VoiceFeatures
    ):
        """Test getting user profile."""
        # Enroll user
        authenticator.enroll_user("user1", voice_features)
        
        # Get profile
        profile = authenticator.get_profile("user1")
        
        assert profile is not None
        assert profile.user_id == "user1"
    
    def test_get_profile_not_enrolled(self, authenticator: VoiceAuthenticator):
        """Test getting non-enrolled user returns None."""
        profile = authenticator.get_profile("user1")
        assert profile is None
    
    def test_list_users(
        self,
        authenticator: VoiceAuthenticator,
        voice_features: VoiceFeatures
    ):
        """Test listing enrolled users."""
        # Enroll multiple users
        authenticator.enroll_user("user1", voice_features)
        
        features2 = VoiceFeatures(
            feature_vector=np.random.randn(128).astype(np.float32),
            sample_rate=16000,
            duration=3.0,
            quality_score=0.9
        )
        authenticator.enroll_user("user2", features2)
        
        # List users
        users = authenticator.list_users()
        
        assert len(users) == 2
        assert "user1" in users
        assert "user2" in users
    
    # ========================================================================
    # SIMILARITY COMPUTATION TESTS
    # ========================================================================
    
    def test_similarity_identical_features(self, authenticator: VoiceAuthenticator):
        """Test similarity of identical features is 1.0."""
        features = np.random.randn(128).astype(np.float32)
        similarity = authenticator._compute_similarity(features, features)
        
        assert similarity == pytest.approx(1.0, abs=0.01)
    
    def test_similarity_different_features(self, authenticator: VoiceAuthenticator):
        """Test similarity of different features is < 1.0."""
        features1 = np.random.randn(128).astype(np.float32)
        features2 = np.random.randn(128).astype(np.float32)
        
        similarity = authenticator._compute_similarity(features1, features2)
        
        assert 0.0 <= similarity <= 1.0
        assert similarity < 1.0
    
    def test_similarity_zero_vectors(self, authenticator: VoiceAuthenticator):
        """Test similarity with zero vectors."""
        features1 = np.zeros(128, dtype=np.float32)
        features2 = np.random.randn(128).astype(np.float32)
        
        similarity = authenticator._compute_similarity(features1, features2)
        
        assert similarity == 0.0
