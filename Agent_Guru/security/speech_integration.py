"""Integration between speech engine and security system."""

import logging
from typing import Optional

import numpy as np

from Agent_Guru.security.voice_auth import VoiceAuthenticator, VoiceProfile
from Agent_Guru.speech.engine import SpeechEngine

logger = logging.getLogger(__name__)


class SpeechSecurityIntegration:
    """
    Integration layer between speech engine and security system.

    Provides seamless voice biometric authentication using the speech engine.
    """

    def __init__(
        self,
        speech_engine: SpeechEngine,
        voice_authenticator: Optional[VoiceAuthenticator] = None
    ):
        """
        Initialize speech-security integration.

        Args:
            speech_engine: Speech engine instance
            voice_authenticator: Voice authenticator (creates new if None)
        """
        self.speech_engine = speech_engine
        self.voice_authenticator = voice_authenticator or VoiceAuthenticator()
        self.logger = logging.getLogger(__name__)

    def enroll_user_from_audio(
        self,
        user_id: str,
        audio: np.ndarray
    ) -> VoiceProfile:
        """
        Enroll user using audio sample.

        Args:
            user_id: Unique user identifier
            audio: Audio data for enrollment

        Returns:
            VoiceProfile for enrolled user

        Raises:
            VoiceAuthenticationError: If enrollment fails
        """
        self.logger.info("Enrolling user %s from audio", user_id)

        # Extract voice features using speech engine
        voice_features = self.speech_engine.extract_voice_features(audio)

        # Enroll with voice authenticator
        profile = self.voice_authenticator.enroll_user(user_id, voice_features)

        self.logger.info(
            f"Successfully enrolled {user_id} "
            f"(quality: {profile.quality_score:.2f})"
        )

        return profile

    def authenticate_from_audio(
        self,
        audio: np.ndarray,
        user_id: Optional[str] = None
    ) -> tuple[bool, Optional[str], float]:
        """
        Authenticate user from audio sample.

        Args:
            audio: Audio data for authentication
            user_id: Optional user ID for verification (None for identification)

        Returns:
            Tuple of (authenticated, user_id, similarity_score)

        Raises:
            VoiceAuthenticationError: If authentication fails
        """
        mode = "verification" if user_id else "identification"
        self.logger.info("Authenticating user from audio (%s mode)", mode)

        # Extract voice features using speech engine
        voice_features = self.speech_engine.extract_voice_features(audio)

        # Authenticate with voice authenticator
        authenticated, matched_user, similarity = self.voice_authenticator.authenticate(
            voice_features,
            user_id
        )

        self.logger.info(
            f"Authentication result: "
            f"{'SUCCESS' if authenticated else 'FAILED'} "
            f"(user: {matched_user}, similarity: {similarity:.3f})"
        )

        return authenticated, matched_user, similarity

    def update_profile_from_audio(
        self,
        user_id: str,
        audio: np.ndarray
    ) -> VoiceProfile:
        """
        Update user profile with new audio sample.

        Args:
            user_id: User identifier
            audio: New audio sample

        Returns:
            Updated VoiceProfile

        Raises:
            VoiceAuthenticationError: If update fails
        """
        self.logger.info("Updating profile for %s from audio", user_id)

        # Extract voice features using speech engine
        voice_features = self.speech_engine.extract_voice_features(audio)

        # Update profile
        profile = self.voice_authenticator.update_profile(user_id, voice_features)

        self.logger.info(
            f"Successfully updated {user_id} "
            f"(samples: {profile.sample_count}, quality: {profile.quality_score:.2f})"
        )

        return profile

    def delete_user(self, user_id: str) -> None:
        """
        Delete user's voice profile.

        Args:
            user_id: User identifier

        Raises:
            VoiceAuthenticationError: If user not found
        """
        self.voice_authenticator.delete_profile(user_id)
        self.logger.info("Deleted user %s", user_id)

    def get_user_profile(self, user_id: str) -> Optional[VoiceProfile]:
        """
        Get user's voice profile.

        Args:
            user_id: User identifier

        Returns:
            VoiceProfile or None if not found
        """
        return self.voice_authenticator.get_profile(user_id)

    def list_enrolled_users(self) -> list[str]:
        """
        List all enrolled users.

        Returns:
            List of user IDs
        """
        return self.voice_authenticator.list_users()
