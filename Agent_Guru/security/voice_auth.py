"""Voice biometric authentication system."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

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
    """Voice biometric authentication system.

    Integrates with speech engine for secure voice-based authentication.
    """

    def __init__(self, similarity_threshold: float = 0.85) -> None:
        """Initialize voice authenticator.

        Args:
            similarity_threshold: Minimum similarity score for authentication
                (0.0-1.0). See `effective_similarity_threshold` -- this can
                only ever make matching STRICTER than the biometric security
                floor (BIOMETRIC_THRESHOLD), never weaker.

        """
        if not 0.0 <= similarity_threshold <= 1.0:
            msg = f"similarity_threshold must be in [0.0, 1.0], got {similarity_threshold!r}"
            raise ValueError(msg)
        self.similarity_threshold = similarity_threshold
        self.quality_threshold = 0.5  # Minimum quality score for enrollment
        self._profiles: dict[str, VoiceProfile] = {}
        self.logger = logging.getLogger(__name__)

    @property
    def effective_similarity_threshold(self) -> float:
        """The cosine-similarity threshold actually enforced by authenticate().

        BUG FIX (Round 15): `similarity_threshold` (the constructor
        parameter above, default 0.85) used to be accepted, stored, and
        then never read again anywhere -- authenticate() called
        verify_embedding() with the hardcoded BIOMETRIC_THRESHOLD (0.97,
        the NIST-FRVT-derived FAR<0.1% security floor from
        embedding_auth.py) no matter what similarity_threshold was set to.
        That made the constructor parameter completely dead, and every
        failure-reason message that quoted it (here and in
        BiometricAuthenticator, which threads its own voice_threshold
        straight into this constructor) reported a number that was never
        actually enforced -- actively misleading, not just unused.

        Fixed by taking the max of the two: a caller can demand a
        STRICTER match than the security floor (a real, honored setting),
        but can never configure a WEAKER one, which would silently lower
        the audited FAR<0.1% guarantee below what it was reviewed for.
        With the default of 0.85 (< 0.97) this is exactly the threshold
        that was already being enforced, so default behavior is unchanged
        by this fix -- only the dead parameter and the misleading messages
        are.
        """
        return max(self.similarity_threshold, BIOMETRIC_THRESHOLD)

    def enroll_user(self, user_id: str, voice_features: VoiceFeatures) -> VoiceProfile:
        """Enroll a new user with voice biometrics.

        Args:
            user_id: Unique user identifier
            voice_features: Voice biometric features from speech engine

        Returns:
            VoiceProfile for the enrolled user

        Raises:
            VoiceAuthenticationError: If enrollment fails

        """
        if user_id in self._profiles:
            msg = f"User {user_id} already enrolled"
            raise VoiceAuthenticationError(msg)

        if voice_features.quality_score < self.quality_threshold:
            msg = f"Voice quality too low: {voice_features.quality_score:.2f} < {self.quality_threshold}"
            raise VoiceAuthenticationError(
                msg,
            )

        # BUG FIX (Round 24): enrollment used to store voice_features.feature_vector
        # as a trusted biometric template with no liveness check at all, even though
        # VoiceFeatures.is_live's own docstring says "The BiometricAuthenticator MUST
        # reject authentication when this field is False", and authenticate() below
        # already enforces exactly that. BiometricAuthenticator.enroll_face() (the
        # face-modality equivalent) already rejects enrollment when features.is_live
        # is False -- this was the one asymmetric gap between the two modalities: an
        # attacker who could reach this method (directly, or via
        # BiometricAuthenticator.enroll_voice() / SpeechSecurityIntegration.
        # enroll_user_from_audio(), both of which call straight through here) could
        # plant a synthetic/replayed voice sample as somebody's permanent reference
        # template, since nothing here ever checked is_live at enrollment time --
        # undermining the anti-spoofing guarantee at its foundation rather than just
        # at the point of use. Checked after the quality gate (not before) so this
        # doesn't change the failure reason reported for a low-quality-but-live
        # sample (test_enroll_low_quality_voice's fixture omits is_live, which
        # defaults to False -- placing this check first would have changed that
        # test's failure from "quality too low" to a liveness rejection).
        if not voice_features.is_live:
            self.logger.warning(
                "SECURITY: Voice enrollment rejected for %s - liveness check failed (score=%.3f)",
                user_id,
                voice_features.liveness_score,
            )
            msg = (
                f"Voice enrollment rejected: liveness check failed "
                f"(score={voice_features.liveness_score:.3f})"
            )
            raise VoiceAuthenticationError(msg)

        profile = VoiceProfile(
            user_id=user_id,
            feature_vector=voice_features.feature_vector,
            enrollment_date=datetime.now(tz=UTC),
            last_updated=datetime.now(tz=UTC),
            quality_score=voice_features.quality_score,
            sample_count=1,
        )

        self._profiles[user_id] = profile
        self.logger.info("Enrolled user: %s (quality: %.2f)", user_id, voice_features.quality_score)

        return profile

    def authenticate(
        self,
        voice_features: VoiceFeatures,
        user_id: str | None = None,
    ) -> tuple[bool, str | None, float]:
        """Authenticate user by voice.

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
                "SECURITY: Liveness check failed for %s (liveness_score: %.3f) - authentication rejected",
                ("user " + user_id) if user_id else "identification",
                voice_features.liveness_score,
            )
            return False, None, 0.0

        if user_id:
            # Verification mode: check against specific user
            if user_id not in self._profiles:
                msg = f"User {user_id} not enrolled"
                raise VoiceAuthenticationError(msg)

            profile = self._profiles[user_id]
            similarity = self._compute_similarity(
                voice_features.feature_vector,
                profile.feature_vector,
            )

            authenticated = verify_embedding(
                voice_features.feature_vector,
                profile.feature_vector,
                self.effective_similarity_threshold,
            )
            self.logger.info(
                "Verification for %s: %s (similarity: %.3f)",
                user_id,
                "SUCCESS" if authenticated else "FAILED",
                similarity,
            )

            return authenticated, user_id if authenticated else None, similarity

        # Identification mode: find matching user
        if not self._profiles:
            msg = "No enrolled users"
            raise VoiceAuthenticationError(msg)

        best_match = None
        best_similarity = 0.0

        for uid, profile in self._profiles.items():
            similarity = self._compute_similarity(
                voice_features.feature_vector,
                profile.feature_vector,
            )

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = uid

        authenticated = best_match is not None and verify_embedding(
            voice_features.feature_vector,
            self._profiles[best_match].feature_vector,
            self.effective_similarity_threshold,
        )
        self.logger.info(
            "Identification: %s (user: %s, similarity: %.3f)",
            "SUCCESS" if authenticated else "FAILED",
            best_match,
            best_similarity,
        )

        return authenticated, best_match if authenticated else None, best_similarity

    def update_profile(self, user_id: str, voice_features: VoiceFeatures) -> VoiceProfile:
        """Update user's voice profile with new sample.

        Args:
            user_id: User identifier
            voice_features: New voice features

        Returns:
            Updated VoiceProfile

        Raises:
            VoiceAuthenticationError: If update fails

        """
        if user_id not in self._profiles:
            msg = f"User {user_id} not enrolled"
            raise VoiceAuthenticationError(msg)

        # BUG FIX (Round 24): same liveness gap as enroll_user() above, and just
        # as consequential here -- without this, an attacker who could reach this
        # method could gradually replace a user's trusted template with a
        # synthetic/replayed sample via the alpha=0.3 blend below, one call at a
        # time, without ever needing to pass the enrollment-time liveness check.
        if not voice_features.is_live:
            self.logger.warning(
                "SECURITY: Voice profile update rejected for %s - liveness check failed (score=%.3f)",
                user_id,
                voice_features.liveness_score,
            )
            msg = (
                f"Voice profile update rejected: liveness check failed "
                f"(score={voice_features.liveness_score:.3f})"
            )
            raise VoiceAuthenticationError(msg)

        profile = self._profiles[user_id]

        # Incremental update: blend old and new features
        alpha = 0.3  # Weight for new sample
        profile.feature_vector = (
            1 - alpha
        ) * profile.feature_vector + alpha * voice_features.feature_vector

        profile.last_updated = datetime.now(tz=UTC)
        profile.sample_count += 1
        profile.quality_score = (
            profile.quality_score * (profile.sample_count - 1) + voice_features.quality_score
        ) / profile.sample_count

        self.logger.info(
            "Updated profile for %s (samples: %d, quality: %.2f)",
            user_id,
            profile.sample_count,
            profile.quality_score,
        )

        return profile

    def delete_profile(self, user_id: str) -> None:
        """Delete user's voice profile.

        Args:
            user_id: User identifier

        Raises:
            VoiceAuthenticationError: If user not found

        """
        if user_id not in self._profiles:
            msg = f"User {user_id} not enrolled"
            raise VoiceAuthenticationError(msg)

        del self._profiles[user_id]
        self.logger.info("Deleted profile for %s", user_id)

    def get_profile(self, user_id: str) -> VoiceProfile | None:
        """Get user's voice profile.

        Args:
            user_id: User identifier

        Returns:
            VoiceProfile or None if not found

        """
        return self._profiles.get(user_id)

    def list_users(self) -> list[str]:
        """List all enrolled users.

        Returns:
            List of user IDs

        """
        return list(self._profiles.keys())

    def _compute_similarity(self, features1: np.ndarray, features2: np.ndarray) -> float:
        """Compute similarity between two feature vectors.

        Uses raw cosine similarity, in [-1.0, 1.0].

        BUG FIX (Round 15): this used to remap raw cosine similarity into
        [0, 1] via `(similarity + 1) / 2` before returning it. That value
        is what `authenticate()` returns to callers as its reported
        `similarity`/`confidence` number, and what gets logged -- but the
        actual pass/fail decision (`verify_embedding()`, both here and in
        BiometricAuthenticator) compares RAW cosine similarity against
        BIOMETRIC_THRESHOLD (0.97). So the number shown in logs and
        returned as "confidence" was on a different scale than the number
        actually being thresholded (e.g. a raw cosine of 0.5 -- clearly
        failing a 0.97 bar -- displayed as 0.75, which reads as "pretty
        close"). Worse, BiometricAuthenticator.authenticate_multi_factor()
        averages this value together with the FACE modality's confidence,
        which BiometricAuthenticator computes as raw cosine (clamped to
        [0,1], no remapping) -- so the two modalities' "confidence" scores
        were never comparable, silently skewing the fused score toward
        voice. Returning raw cosine here (matching
        BiometricAuthenticator._cosine_similarity() and
        embedding_auth.verify_embedding()'s scale) fixes both: logs/
        confidence now reflect the actual quantity being thresholded, and
        multi-factor fusion averages like-scaled numbers. The `best_match`
        selection in identification mode is unaffected -- remapping via
        `(x+1)/2` is monotonic, so it never changed which candidate had
        the highest similarity, only the number's parade.

        Args:
            features1: First feature vector
            features2: Second feature vector

        Returns:
            Cosine similarity score (-1.0 to 1.0). Callers that need a
            [0, 1] confidence value should clamp (as
            BiometricAuthenticator.authenticate_voice() already does).

        """
        dot_product = np.dot(features1, features2)
        norm1 = np.linalg.norm(features1)
        norm2 = np.linalg.norm(features2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))
