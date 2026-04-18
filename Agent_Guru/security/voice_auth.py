"""Voice biometric authentication system."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from Agent_Guru.security.embedding_auth import BIOMETRIC_THRESHOLD, verify_embedding
from Agent_Guru.speech.models import VoiceFeatures

logger = logging.getLogger(__name__)


@dataclass
class VoiceProfile:
    """Voice biometric profile."""
    user_id: str
    feature_vector: np.ndarray
    enrollment_date: datetime
    last_updated: datetime
    quality_score: float
    sample_count: int


class VoiceAuthenticationError(Exception):
    """Voice authentication error."""


class VoiceAuthenticator:
    """
    Voice biometric authentication system.

    Integrates with speech engine for secure voice-based authentication.
    """

    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize voice authenticator.

        Args:
            similarity_threshold: Minimum similarity score for authentication (0.0-1.0)
        """
        self.similarity_threshold = similarity_threshold
        self.quality_threshold = 0.5  # Minimum quality score for enrollment
        self._profiles: dict[str, VoiceProfile] = {}
        self.logger = logging.getLogger(__name__)

    def enroll_user(
        self,
        user_id: str,
        voice_features: VoiceFeatures
    ) -> VoiceProfile:
        """
        Enroll a new user with voice biometrics.

        Args:
            user_id: Unique user identifier
            voice_features: Voice biometric features from speech engine

        Returns:
            VoiceProfile for the enrolled user

        Raises:
            VoiceAuthenticationError: If enrollment fails
        """
        if user_id in self._profiles:
            raise VoiceAuthenticationError(f"User {user_id} already enrolled")

        if voice_features.quality_score < self.quality_threshold:
            raise VoiceAuthenticationError(
                f"Voice quality too low: {voice_features.quality_score:.2f} < {self.quality_threshold}"
            )

        profile = VoiceProfile(
            user_id=user_id,
            feature_vector=voice_features.feature_vector,
            enrollment_date=datetime.now(tz=timezone.utc),
            last_updated=datetime.now(tz=timezone.utc),
            quality_score=voice_features.quality_score,
            sample_count=1
        )

        self._profiles[user_id] = profile
        self.logger.info("Enrolled user: %s (quality: %.2f)", user_id, voice_features.quality_score)

        return profile

    def authenticate(
        self,
        voice_features: VoiceFeatures,
        user_id: Optional[str] = None
    ) -> tuple[bool, Optional[str], float]:
        """
        Authenticate user by voice.

        Args:
            voice_features: Voice biometric features to authenticate
            user_id: Optional user ID to verify against (None for identification)

        Returns:
            Tuple of (authenticated, user_id, similarity_score)

        Raises:
            VoiceAuthenticationError: If authentication fails
        """
        # Liveness check: reject non-live audio immediately
        if not voice_features.is_live:
            self.logger.warning(
                "SECURITY: Liveness check failed for %s (liveness_score: %.3f) — authentication rejected",
                ("user " + user_id) if user_id else "identification",
                voice_features.liveness_score,
            )
            return False, None, 0.0

        if user_id:
            # Verification mode: check against specific user
            if user_id not in self._profiles:
                raise VoiceAuthenticationError(f"User {user_id} not enrolled")

            profile = self._profiles[user_id]
            similarity = self._compute_similarity(
                voice_features.feature_vector,
                profile.feature_vector
            )

            authenticated = verify_embedding(
                voice_features.feature_vector,
                profile.feature_vector,
                BIOMETRIC_THRESHOLD,
            )
            self.logger.info(
                "Verification for %s: %s (similarity: %.3f)",
                user_id,
                "SUCCESS" if authenticated else "FAILED",
                similarity,
            )

            return authenticated, user_id if authenticated else None, similarity

        else:
            # Identification mode: find matching user
            if not self._profiles:
                raise VoiceAuthenticationError("No enrolled users")

            best_match = None
            best_similarity = 0.0

            for uid, profile in self._profiles.items():
                similarity = self._compute_similarity(
                    voice_features.feature_vector,
                    profile.feature_vector
                )

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = uid

            authenticated = (
                best_match is not None
                and verify_embedding(
                    voice_features.feature_vector,
                    self._profiles[best_match].feature_vector,
                    BIOMETRIC_THRESHOLD,
                )
            )
            self.logger.info(
                "Identification: %s (user: %s, similarity: %.3f)",
                "SUCCESS" if authenticated else "FAILED",
                best_match,
                best_similarity,
            )

            return authenticated, best_match if authenticated else None, best_similarity

    def update_profile(
        self,
        user_id: str,
        voice_features: VoiceFeatures
    ) -> VoiceProfile:
        """
        Update user's voice profile with new sample.

        Args:
            user_id: User identifier
            voice_features: New voice features

        Returns:
            Updated VoiceProfile

        Raises:
            VoiceAuthenticationError: If update fails
        """
        if user_id not in self._profiles:
            raise VoiceAuthenticationError(f"User {user_id} not enrolled")

        profile = self._profiles[user_id]

        # Incremental update: blend old and new features
        alpha = 0.3  # Weight for new sample
        profile.feature_vector = (
            (1 - alpha) * profile.feature_vector +
            alpha * voice_features.feature_vector
        )

        profile.last_updated = datetime.now(tz=timezone.utc)
        profile.sample_count += 1
        profile.quality_score = (
            (profile.quality_score * (profile.sample_count - 1) +
             voice_features.quality_score) / profile.sample_count
        )

        self.logger.info(
            "Updated profile for %s (samples: %d, quality: %.2f)",
            user_id,
            profile.sample_count,
            profile.quality_score,
        )

        return profile

    def delete_profile(self, user_id: str) -> None:
        """
        Delete user's voice profile.

        Args:
            user_id: User identifier

        Raises:
            VoiceAuthenticationError: If user not found
        """
        if user_id not in self._profiles:
            raise VoiceAuthenticationError(f"User {user_id} not enrolled")

        del self._profiles[user_id]
        self.logger.info("Deleted profile for %s", user_id)

    def get_profile(self, user_id: str) -> Optional[VoiceProfile]:
        """
        Get user's voice profile.

        Args:
            user_id: User identifier

        Returns:
            VoiceProfile or None if not found
        """
        return self._profiles.get(user_id)

    def list_users(self) -> list[str]:
        """
        List all enrolled users.

        Returns:
            List of user IDs
        """
        return list(self._profiles.keys())

    def _compute_similarity(
        self,
        features1: np.ndarray,
        features2: np.ndarray
    ) -> float:
        """
        Compute similarity between two feature vectors.

        Uses cosine similarity.

        Args:
            features1: First feature vector
            features2: Second feature vector

        Returns:
            Similarity score (0.0-1.0)
        """
        # Cosine similarity
        dot_product = np.dot(features1, features2)
        norm1 = np.linalg.norm(features1)
        norm2 = np.linalg.norm(features2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        # Normalize to 0-1 range (cosine similarity is -1 to 1)
        result: float = float((similarity + 1) / 2)
        return result
