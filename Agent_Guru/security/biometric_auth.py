"""Central biometric authenticator for Agent Guru.

This module is the SINGLE source of truth for all biometric authentication.
Feature extraction is delegated to specialised components:
  - FaceFeatureExtractor  (Agent_Guru.vision)
  - SpeechEngine          (Agent_Guru.speech) via SpeechSecurityIntegration

Authentication decisions (template comparison, liveness enforcement, fusion)
are made exclusively here.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np

from Agent_Guru.security.embedding_auth import BIOMETRIC_THRESHOLD, verify_embedding
from Agent_Guru.security.models import AuthenticationResult
from Agent_Guru.security.voice_auth import VoiceAuthenticationError, VoiceAuthenticator
from Agent_Guru.vision.face_features import FaceFeatureExtractor

if TYPE_CHECKING:
    from Agent_Guru.vision.models import FaceFeatures

logger = logging.getLogger(__name__)

# Fusion weights (face is generally more reliable than voice)
_FACE_WEIGHT: float = 0.6
_VOICE_WEIGHT: float = 0.4


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity in [-1.0, 1.0] (raw, not normalised to [0,1])."""
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class BiometricAuthenticator:
    """Central multi-modal biometric authenticator.

    Wraps FaceFeatureExtractor and VoiceAuthenticator to provide a unified
    authentication interface.  All authentication decisions are made here;
    feature extractors only return raw feature vectors.

    Args:
        face_extractor: FaceFeatureExtractor instance (created if None).
        voice_authenticator: VoiceAuthenticator instance (created if None).
        face_threshold: Minimum cosine similarity for face auth. Default 0.75.
        voice_threshold: Minimum cosine similarity for voice auth. Default 0.85.
        liveness_threshold: Minimum liveness score for face auth. Default 0.5.

    """

    def __init__(
        self,
        face_extractor: FaceFeatureExtractor | None = None,
        voice_authenticator: VoiceAuthenticator | None = None,
        face_threshold: float = 0.75,
        voice_threshold: float = 0.85,
        liveness_threshold: float = 0.5,
    ) -> None:
        if not 0.0 <= face_threshold <= 1.0:
            msg = "face_threshold must be in [0.0, 1.0]"
            raise ValueError(msg)
        if not 0.0 <= voice_threshold <= 1.0:
            msg = "voice_threshold must be in [0.0, 1.0]"
            raise ValueError(msg)
        if not 0.0 <= liveness_threshold <= 1.0:
            msg = "liveness_threshold must be in [0.0, 1.0]"
            raise ValueError(msg)

        self.face_extractor = face_extractor or FaceFeatureExtractor(
            liveness_threshold=liveness_threshold,
        )
        self.voice_authenticator = voice_authenticator or VoiceAuthenticator(
            similarity_threshold=voice_threshold,
        )
        self.face_threshold = face_threshold
        self.voice_threshold = voice_threshold

        # In-memory face template store: {profile_id: embedding (512,)}
        self._face_templates: dict[str, np.ndarray] = {}
        # Cached SpeechEngine - initialized lazily, reused across calls
        self._speech_engine: Any = None

    # ------------------------------------------------------------------
    # Face authentication
    # ------------------------------------------------------------------

    def enroll_face(self, profile_id: str, image_data: bytes) -> None:
        """Enroll a face template for *profile_id*.

        Extracts a 512-dim embedding from *image_data* and stores it.

        Raises:
            ValueError: If liveness check fails (anti-spoofing).
            RuntimeError: If face extraction fails.

        """
        features: FaceFeatures = self.face_extractor.extract_face_embedding(image_data)
        if not features.is_live:
            logger.warning(
                "SECURITY: Face enrollment rejected for %s - liveness failed (score=%.3f)",
                profile_id,
                features.liveness_score,
            )
            msg = (
                f"Face enrollment rejected: liveness check failed "
                f"(score={features.liveness_score:.3f})"
            )
            raise ValueError(
                msg,
            )
        self._face_templates[profile_id] = features.embedding
        logger.info("Enrolled face template for %s", profile_id)

    def authenticate_face(self, profile_id: str, image_data: bytes) -> AuthenticationResult:
        """Authenticate *profile_id* using a face image.

        Steps:
          1. Extract embedding via FaceFeatureExtractor.
          2. Reject if liveness check fails.
          3. Compare embedding to stored template (cosine similarity).
          4. Return AuthenticationResult.

        Returns:
            AuthenticationResult(authenticated=False, ...) when *profile_id*
            has no enrolled face template. (Docstring fixed, Round 24: this
            used to document "Raises: KeyError" here, but the implementation
            has always returned a failed AuthenticationResult instead of
            raising -- the safer of the two behaviors, but the docstring was
            simply wrong about what callers actually get back.)

        """
        if profile_id not in self._face_templates:
            return AuthenticationResult(
                authenticated=False,
                confidence=0.0,
                modality="face",
                user_id=profile_id,
                failure_reason=f"No face template enrolled for '{profile_id}'",
            )

        features: FaceFeatures = self.face_extractor.extract_face_embedding(image_data)

        # Liveness gate
        if not features.is_live:
            logger.warning(
                "SECURITY: Face auth rejected for %s - liveness failed (score=%.3f)",
                profile_id,
                features.liveness_score,
            )
            return AuthenticationResult(
                authenticated=False,
                confidence=features.liveness_score,
                modality="face",
                user_id=profile_id,
                failure_reason=(f"Liveness check failed (score={features.liveness_score:.3f})"),
                liveness_failed=True,
            )

        template = self._face_templates[profile_id]
        # BUG FIX (Round 15): this used to enforce the FIXED
        # BIOMETRIC_THRESHOLD (0.97) unconditionally and then report
        # `self.face_threshold` (default 0.75, whatever the caller
        # configured) in the failure message -- a number that was never
        # actually the gate being applied. self.face_threshold was pure
        # dead configuration: setting it to anything had zero effect on
        # whether authentication succeeded, and the error message actively
        # misreported what threshold caused the rejection. Fixed the same
        # way as VoiceAuthenticator.effective_similarity_threshold: take
        # the max of the configured threshold and the security floor, so
        # a caller can only ever demand something STRICTER than
        # BIOMETRIC_THRESHOLD, never weaker (which would silently lower
        # the audited FAR<0.1% guarantee) -- default behavior (0.75 < 0.97)
        # is unchanged.
        effective_threshold = max(self.face_threshold, BIOMETRIC_THRESHOLD)
        # Also compute raw similarity for the confidence field.
        similarity = float(max(0.0, min(1.0, _cosine_similarity(features.embedding, template))))
        authenticated = verify_embedding(features.embedding, template, effective_threshold)

        logger.info(
            "Face auth for %s: %s (similarity=%.3f)",
            profile_id,
            "SUCCESS" if authenticated else "FAILED",
            similarity,
        )

        return AuthenticationResult(
            authenticated=authenticated,
            confidence=similarity,
            modality="face",
            user_id=profile_id,
            failure_reason=(
                None
                if authenticated
                else f"Similarity {similarity:.3f} below threshold {effective_threshold}"
            ),
        )

    # ------------------------------------------------------------------
    # Voice authentication
    # ------------------------------------------------------------------

    def enroll_voice(self, profile_id: str, audio_data: np.ndarray) -> None:
        """Enroll a voice template for *profile_id*.

        Delegates to VoiceAuthenticator.enroll_user() via the speech engine.
        The speech engine must be wired into VoiceAuthenticator externally
        (or use SpeechSecurityIntegration directly).

        For direct use without a SpeechEngine, callers should use
        SpeechSecurityIntegration.enroll_user_from_audio() instead.

        Raises:
            VoiceAuthenticationError: If enrollment fails.

        """
        # Local import to break circular dependency:
        # security -> speech -> security
        from Agent_Guru.speech.engine import SpeechEngine

        # Reuse a cached engine instance to avoid re-initializing on every call
        if not hasattr(self, "_speech_engine") or self._speech_engine is None:
            self._speech_engine = SpeechEngine()
            self._speech_engine.initialize()
        voice_features = self._speech_engine.extract_voice_features(audio_data)
        self.voice_authenticator.enroll_user(profile_id, voice_features)
        logger.info("Enrolled voice template for %s", profile_id)

    def authenticate_voice(self, profile_id: str, audio_data: np.ndarray) -> AuthenticationResult:
        """Authenticate *profile_id* using a voice sample.

        Delegates feature extraction to SpeechEngine and authentication to
        VoiceAuthenticator (which enforces liveness).

        Returns:
            AuthenticationResult with modality="voice".

        """
        # Local import to break circular dependency:
        # security -> speech -> security
        from Agent_Guru.speech.engine import SpeechEngine

        # Reuse a cached engine instance to avoid re-initializing on every call
        if not hasattr(self, "_speech_engine") or self._speech_engine is None:
            self._speech_engine = SpeechEngine()
            self._speech_engine.initialize()
        voice_features = self._speech_engine.extract_voice_features(audio_data)

        try:
            authenticated, _matched_id, similarity = self.voice_authenticator.authenticate(
                voice_features,
                user_id=profile_id,
            )
        except VoiceAuthenticationError as exc:
            return AuthenticationResult(
                authenticated=False,
                confidence=0.0,
                modality="voice",
                user_id=profile_id,
                failure_reason=str(exc),
            )

        # Liveness rejection is already handled inside VoiceAuthenticator.authenticate()
        # (returns False, None, 0.0 when is_live is False).
        liveness_failed = not authenticated and not voice_features.is_live
        if liveness_failed:
            failure_reason = f"Liveness check failed (score={voice_features.liveness_score:.3f})"
        elif not authenticated:
            # BUG FIX (Round 15): previously reported self.voice_threshold
            # (the raw, possibly-lower constructor argument) here, but the
            # actual gate applied inside VoiceAuthenticator.authenticate()
            # is effective_similarity_threshold (max of that argument and
            # the BIOMETRIC_THRESHOLD security floor) -- see that
            # property's docstring. Reporting the unused argument here
            # actively misreported the real cause of the rejection.
            effective_threshold = self.voice_authenticator.effective_similarity_threshold
            failure_reason = f"Similarity {similarity:.3f} below threshold {effective_threshold}"
        else:
            failure_reason = None

        # Clamp similarity to [0.0, 1.0] to guard against floating-point
        # precision issues (cosine similarity can be marginally above 1.0).
        clamped_similarity = float(max(0.0, min(1.0, similarity)))

        return AuthenticationResult(
            authenticated=authenticated,
            confidence=clamped_similarity,
            modality="voice",
            user_id=profile_id,
            failure_reason=failure_reason,
            liveness_failed=liveness_failed,
        )

    # ------------------------------------------------------------------
    # Multi-modal fusion
    # ------------------------------------------------------------------

    def authenticate_multi_factor(
        self,
        profile_id: str,
        face_image: bytes | None = None,
        voice_audio: np.ndarray | None = None,
    ) -> AuthenticationResult:
        """Authenticate using multiple biometric modalities.

        Runs all provided modalities and fuses scores with weighted average:
          - face weight: 0.6
          - voice weight: 0.4

        If any modality fails liveness detection the entire attempt is rejected
        immediately (Req 6.5).

        Args:
            profile_id: Identity to verify.
            face_image: Raw image bytes for face authentication (optional).
            voice_audio: Audio array for voice authentication (optional).

        Returns:
            AuthenticationResult with modality="multi" and fused confidence.

        Raises:
            ValueError: If no modality is provided.

        """
        if face_image is None and voice_audio is None:
            msg = "At least one modality (face_image or voice_audio) must be provided"
            raise ValueError(msg)

        results: list[AuthenticationResult] = []
        weights: list[float] = []

        if face_image is not None:
            face_result = self.authenticate_face(profile_id, face_image)
            # Liveness failure → immediate rejection.
            # BUG FIX (Round 24): this used to detect a liveness rejection by
            # substring-matching "liveness" inside failure_reason.lower() --
            # fragile, since it silently stops working the moment that
            # message's wording changes anywhere it's set, with nothing to
            # catch the drift. AuthenticationResult.liveness_failed (added
            # this round) is a real, structured flag set directly by
            # authenticate_face()/authenticate_voice() at the point they
            # know the true cause, so this check can no longer desync from
            # what actually happened.
            if not face_result.authenticated and face_result.liveness_failed:
                logger.warning(
                    "SECURITY: Multi-factor auth rejected for %s - face liveness failed",
                    profile_id,
                )
                return AuthenticationResult(
                    authenticated=False,
                    confidence=face_result.confidence,
                    modality="multi",
                    user_id=profile_id,
                    failure_reason=f"Face liveness failed: {face_result.failure_reason}",
                )
            results.append(face_result)
            weights.append(_FACE_WEIGHT)

        if voice_audio is not None:
            voice_result = self.authenticate_voice(profile_id, voice_audio)
            # Liveness failure → immediate rejection (see the face-modality
            # comment above for why this now checks the structured flag).
            if not voice_result.authenticated and voice_result.liveness_failed:
                logger.warning(
                    "SECURITY: Multi-factor auth rejected for %s - voice liveness failed",
                    profile_id,
                )
                return AuthenticationResult(
                    authenticated=False,
                    confidence=voice_result.confidence,
                    modality="multi",
                    user_id=profile_id,
                    failure_reason=f"Voice liveness failed: {voice_result.failure_reason}",
                )
            results.append(voice_result)
            weights.append(_VOICE_WEIGHT)

        # Normalise weights to sum to 1.0
        total_weight = sum(weights)
        norm_weights = [w / total_weight for w in weights]

        # Weighted average confidence
        fused_confidence = sum(
            r.confidence * w for r, w in zip(results, norm_weights, strict=False)
        )
        # Clamp to [0, 1] for safety
        fused_confidence = float(max(0.0, min(1.0, fused_confidence)))

        # All modalities must pass for multi-factor to succeed
        all_authenticated = all(r.authenticated for r in results)

        failure_reasons = [
            r.failure_reason for r in results if not r.authenticated and r.failure_reason
        ]
        failure_reason = "; ".join(failure_reasons) if failure_reasons else None

        logger.info(
            "Multi-factor auth for %s: %s (fused_confidence=%.3f)",
            profile_id,
            "SUCCESS" if all_authenticated else "FAILED",
            fused_confidence,
        )

        return AuthenticationResult(
            authenticated=all_authenticated,
            confidence=fused_confidence,
            modality="multi",
            user_id=profile_id,
            failure_reason=failure_reason,
        )
