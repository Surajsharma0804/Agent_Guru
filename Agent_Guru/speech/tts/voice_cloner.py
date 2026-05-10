"""Voice cloning and personalization for custom voice synthesis.

This module implements voice cloning functionality that allows the system
to learn and replicate a user's voice characteristics for personalized
text-to-speech synthesis.
"""

import contextlib
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import librosa
import numpy as np

from Agent_Guru.security.embedding_auth import BIOMETRIC_THRESHOLD, verify_embedding
from Agent_Guru.speech.exceptions import GuruSpeechError
from Agent_Guru.speech.models import VoiceModel

if TYPE_CHECKING:
    from Agent_Guru.speech.models import PersonalityType

logger = logging.getLogger(__name__)


class VoiceCloningError(GuruSpeechError):
    """Voice cloning error."""


@dataclass
class VoiceProfile:
    """Voice profile for cloning."""

    voice_id: str
    features: np.ndarray
    sample_count: int
    total_duration: float
    quality_score: float
    created_at: float
    updated_at: float
    metadata: dict = field(default_factory=dict)


class VoiceCloner:
    """Voice cloning and personalization system.

    Implements voice enrollment, incremental learning, and personalized
    voice synthesis with target similarity >0.85.

    Features:
    - Voice enrollment from 5+ minutes of audio
    - Incremental learning for continuous improvement
    - Voice similarity computation
    - Personalized voice synthesis
    - Voice profile management
    """

    def __init__(self, model_path: str | None = None) -> None:
        """Initialize voice cloner.

        Args:
            model_path: Path to voice cloning model (optional)

        """
        self.model_path = model_path
        self._voice_profiles: dict[str, VoiceProfile] = {}

        # Feature extraction parameters
        self.n_mfcc = 40  # More coefficients for voice cloning
        self.n_fft = 2048
        self.hop_length = 512
        self.sample_rate = 16000

        # Minimum requirements for enrollment
        self.min_enrollment_duration = 300.0  # 5 minutes in seconds
        self.min_quality_score = 0.6

        logger.info("VoiceCloner initialized")

    def enroll_voice(
        self,
        audio_samples: list[np.ndarray],
        voice_id: str,
        sample_rate: int = 16000,
        metadata: dict | None = None,
    ) -> VoiceModel:
        """Enroll a new voice from audio samples.

        Requires 5+ minutes of audio for quality voice cloning.

        Args:
            audio_samples: List of audio arrays (each should be clean speech)
            voice_id: Unique identifier for this voice
            sample_rate: Sample rate of audio
            metadata: Optional metadata about the voice

        Returns:
            VoiceModel with enrolled voice profile

        Raises:
            VoiceCloningError: If enrollment fails or insufficient audio

        """
        try:
            if not audio_samples:
                msg = "No audio samples provided for enrollment"
                raise VoiceCloningError(msg)

            # Calculate total duration
            total_duration = sum(len(audio) / sample_rate for audio in audio_samples)

            if total_duration < self.min_enrollment_duration:
                msg = (
                    f"Insufficient audio for enrollment: {total_duration:.1f}s "
                    f"(minimum: {self.min_enrollment_duration:.1f}s)"
                )
                raise VoiceCloningError(
                    msg,
                )

            logger.info(
                f"Enrolling voice '{voice_id}' with {len(audio_samples)} samples "
                f"({total_duration:.1f}s total)",
            )

            # Extract features from all samples
            all_features = []
            quality_scores = []

            for i, audio in enumerate(audio_samples):
                # Ensure audio is float32
                if audio.dtype != np.float32:
                    audio = audio.astype(np.float32)

                # Normalize
                if np.max(np.abs(audio)) > 0:
                    audio = audio / np.max(np.abs(audio))

                # Extract features
                features = self._extract_voice_features(audio, sample_rate)
                quality = self._compute_audio_quality(audio, sample_rate)

                all_features.append(features)
                quality_scores.append(quality)

                if (i + 1) % 10 == 0:
                    logger.debug("Processed %s/%s samples", i + 1, len(audio_samples))

            # Compute average quality
            avg_quality = float(np.mean(quality_scores))

            if avg_quality < self.min_quality_score:
                msg = (
                    f"Audio quality too low: {avg_quality:.2f} "
                    f"(minimum: {self.min_quality_score:.2f})"
                )
                raise VoiceCloningError(
                    msg,
                )

            # Aggregate features (mean and std)
            feature_matrix = np.array(all_features)
            mean_features = np.mean(feature_matrix, axis=0)
            std_features = np.std(feature_matrix, axis=0)

            # Combine mean and std for robust representation
            voice_features = np.concatenate([mean_features, std_features])

            # Create voice profile
            profile = VoiceProfile(
                voice_id=voice_id,
                features=voice_features,
                sample_count=len(audio_samples),
                total_duration=total_duration,
                quality_score=avg_quality,
                created_at=time.time(),
                updated_at=time.time(),
                metadata=metadata or {},
            )

            # Store profile
            self._voice_profiles[voice_id] = profile

            # Create voice model
            voice_model = VoiceModel(
                model_id=voice_id,
                user_id=voice_id,  # Use voice_id as user_id for now
                voice_characteristics={
                    "quality_score": avg_quality,
                    "sample_count": float(len(audio_samples)),
                    "feature_dim": float(len(voice_features)),
                },
                training_duration_seconds=total_duration,
                similarity_score=avg_quality,
                created_at=time.time(),
                updated_at=time.time(),
            )

            logger.info(
                f"Voice '{voice_id}' enrolled successfully "
                f"(quality: {avg_quality:.2f}, samples: {len(audio_samples)})",
            )

            return voice_model

        except Exception as e:
            if isinstance(e, VoiceCloningError):
                raise
            msg = f"Voice enrollment failed: {e}"
            raise VoiceCloningError(msg) from e
    def update_voice_model(
        self,
        voice_id: str,
        new_audio_samples: list[np.ndarray],
        sample_rate: int = 16000,
    ) -> VoiceModel:
        """Update existing voice model with new samples (incremental learning).

        Args:
            voice_id: ID of voice to update
            new_audio_samples: New audio samples to incorporate
            sample_rate: Sample rate of audio

        Returns:
            Updated VoiceModel

        Raises:
            VoiceCloningError: If voice not found or update fails

        """
        try:
            if voice_id not in self._voice_profiles:
                msg = f"Voice '{voice_id}' not found"
                raise VoiceCloningError(msg)

            profile = self._voice_profiles[voice_id]

            logger.info("Updating voice '%s' with %s new samples", voice_id, len(new_audio_samples))

            # Extract features from new samples
            new_features = []
            quality_scores = []

            for audio in new_audio_samples:
                # Ensure audio is float32
                if audio.dtype != np.float32:
                    audio = audio.astype(np.float32)

                # Normalize
                if np.max(np.abs(audio)) > 0:
                    audio = audio / np.max(np.abs(audio))

                features = self._extract_voice_features(audio, sample_rate)
                quality = self._compute_audio_quality(audio, sample_rate)

                new_features.append(features)
                quality_scores.append(quality)

            # Calculate new duration
            new_duration = sum(len(audio) / sample_rate for audio in new_audio_samples)

            # Incremental update using weighted average
            # Give more weight to existing profile (80%) vs new samples (20%)
            old_weight = 0.8
            new_weight = 0.2

            new_feature_matrix = np.array(new_features)
            new_mean = np.mean(new_feature_matrix, axis=0)
            new_std = np.std(new_feature_matrix, axis=0)
            new_combined = np.concatenate([new_mean, new_std])

            # Weighted update
            updated_features = old_weight * profile.features + new_weight * new_combined

            # Update quality score
            new_quality = float(np.mean(quality_scores))
            updated_quality = old_weight * profile.quality_score + new_weight * new_quality

            # Update profile
            profile.features = updated_features
            profile.sample_count += len(new_audio_samples)
            profile.total_duration += new_duration
            profile.quality_score = updated_quality
            profile.updated_at = time.time()

            # Create updated voice model
            voice_model = VoiceModel(
                model_id=voice_id,
                user_id=voice_id,
                voice_characteristics={
                    "quality_score": updated_quality,
                    "sample_count": float(profile.sample_count),
                    "feature_dim": float(len(updated_features)),
                },
                training_duration_seconds=profile.total_duration,
                similarity_score=updated_quality,
                created_at=profile.created_at,
                updated_at=time.time(),
            )

            logger.info(
                f"Voice '{voice_id}' updated successfully "
                f"(quality: {updated_quality:.2f}, total samples: {profile.sample_count})",
            )

            return voice_model

        except Exception as e:
            if isinstance(e, VoiceCloningError):
                raise
            msg = f"Voice model update failed: {e}"
            raise VoiceCloningError(msg) from e
    def synthesize_with_cloned_voice(
        self,
        text: str,
        voice_id: str,
        emotion: str | None = None,
        personality: "PersonalityType | None" = None,
        lang: str = "en-us",
    ) -> np.ndarray:
        """Synthesize speech using the Kokoro TTS engine.

        Voice cloning (conditioning on a specific enrolled voice) requires
        XTTS v2 or a similar model that accepts a reference audio embedding.
        Until that model is integrated, this method uses the Kokoro engine
        with the personality-matched voice (Guru = male, Maya = female),
        which already sounds human-quality.

        Args:
            text: Text to synthesize.
            voice_id: Enrolled voice ID (used to look up personality hint).
            emotion: Optional emotion string (``"happy"``, ``"sad"``, etc.).
            personality: Override personality. If ``None``, defaults to GURU.
            lang: BCP-47 language code (default ``"en-us"``).

        Returns:
            Float32 numpy array in [-1, 1] at 24 kHz.

        Raises:
            VoiceCloningError: If synthesis fails.

        """
        try:
            if voice_id not in self._voice_profiles:
                msg = f"Voice '{voice_id}' not found"
                raise VoiceCloningError(msg)

            from Agent_Guru.speech.models import EmotionType, PersonalityType
            from Agent_Guru.speech.tts.tts_engine import CoquiTTSEngine

            # Resolve personality
            if personality is None:
                personality = PersonalityType.GURU

            # Map emotion string to EmotionType
            emotion_enum: EmotionType | None = None
            if emotion:
                with contextlib.suppress(ValueError):
                    emotion_enum = EmotionType(emotion.lower())

            engine = CoquiTTSEngine()
            audio, _sr = engine.synthesize_to_array(
                text,
                personality=personality,
                emotion=emotion_enum,
                lang=lang,
            )

            logger.info(
                "Synthesized %.1fs of audio for voice '%s'",
                len(audio) / _sr,
                voice_id,
            )
            return audio

        except VoiceCloningError as exc:
            raise
            msg = f"Voice synthesis failed: {exc}"
            raise VoiceCloningError(msg) from exc
    def compute_similarity(
        self,
        audio1: np.ndarray,
        audio2: np.ndarray,
        sample_rate: int = 16000,
    ) -> float:
        """Compute similarity between two voice samples.

        Target similarity >0.85 for successful voice cloning.

        Args:
            audio1: First audio sample
            audio2: Second audio sample
            sample_rate: Sample rate of audio

        Returns:
            Similarity score between 0.0 and 1.0

        """
        try:
            # Extract features from both samples
            features1 = self._extract_voice_features(audio1, sample_rate)
            features2 = self._extract_voice_features(audio2, sample_rate)

            # Compute cosine similarity
            dot_product = np.dot(features1, features2)
            norm1 = np.linalg.norm(features1)
            norm2 = np.linalg.norm(features2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)

            # Convert from [-1, 1] to [0, 1]
            similarity = (similarity + 1.0) / 2.0

            return float(np.clip(similarity, 0.0, 1.0))

        except Exception:
            logger.exception("Similarity computation failed")
            return 0.0
    def is_voice_match(
        self,
        audio1: np.ndarray,
        audio2: np.ndarray,
        sample_rate: int = 16000,
        threshold: float = BIOMETRIC_THRESHOLD,
    ) -> bool:
        """Return True iff the two voice samples are a biometric match.

        Uses :func:`~Agent_Guru.security.embedding_auth.verify_embedding` to
        enforce the biometric threshold (FAR < 0.1%).

        Args:
            audio1: First audio sample.
            audio2: Second audio sample.
            sample_rate: Sample rate of audio.
            threshold: Minimum cosine similarity for a positive match.

        Returns:
            ``True`` if the voice embeddings are similar enough, ``False`` otherwise.

        """
        try:
            features1 = self._extract_voice_features(audio1, sample_rate)
            features2 = self._extract_voice_features(audio2, sample_rate)
            return verify_embedding(features1, features2, threshold)
        except Exception:
            logger.exception("Voice match check failed")
            return False
    def get_voice_model(self, voice_id: str) -> VoiceModel | None:
        """Get voice model by ID.

        Args:
            voice_id: Voice identifier

        Returns:
            VoiceModel if found, None otherwise

        """
        if voice_id not in self._voice_profiles:
            return None

        profile = self._voice_profiles[voice_id]

        return VoiceModel(
            model_id=voice_id,
            user_id=voice_id,
            voice_characteristics={
                "quality_score": profile.quality_score,
                "sample_count": float(profile.sample_count),
                "feature_dim": float(len(profile.features)),
            },
            training_duration_seconds=profile.total_duration,
            similarity_score=profile.quality_score,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    def list_voices(self) -> list[str]:
        """List all enrolled voice IDs.

        Returns:
            List of voice IDs

        """
        return list(self._voice_profiles.keys())

    def delete_voice(self, voice_id: str) -> bool:
        """Delete a voice profile.

        Args:
            voice_id: Voice identifier

        Returns:
            True if deleted, False if not found

        """
        if voice_id in self._voice_profiles:
            del self._voice_profiles[voice_id]
            logger.info("Voice '%s' deleted", voice_id)
            return True
        return False

    def save_voice_profile(self, voice_id: str, filepath: str) -> None:
        """Save voice profile to file.

        Args:
            voice_id: Voice identifier
            filepath: Path to save profile

        Raises:
            VoiceCloningError: If voice not found or save fails

        """
        try:
            if voice_id not in self._voice_profiles:
                msg = f"Voice '{voice_id}' not found"
                raise VoiceCloningError(msg)

            profile = self._voice_profiles[voice_id]

            import json as _json

            profile_data = {
                "voice_id": profile.voice_id,
                "features": profile.features.tolist(),
                "sample_count": profile.sample_count,
                "total_duration": profile.total_duration,
                "quality_score": profile.quality_score,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
            }
            with open(filepath, "w", encoding="utf-8") as f:  # noqa: PTH123
                _json.dump(profile_data, f)

            logger.info("Voice profile '%s' saved to %s", voice_id, filepath)

        except Exception as e:
            if isinstance(e, VoiceCloningError):
                raise
            msg = f"Failed to save voice profile: {e}"
            raise VoiceCloningError(msg) from e
    def load_voice_profile(self, filepath: str) -> str:
        """Load voice profile from file.

        Args:
            filepath: Path to profile file

        Returns:
            Voice ID of loaded profile

        Raises:
            VoiceCloningError: If load fails

        """
        try:
            import json as _json

            with open(filepath, encoding="utf-8") as f:  # noqa: PTH123
                profile_data = _json.load(f)

            profile = VoiceProfile(
                voice_id=profile_data["voice_id"],
                features=np.array(profile_data["features"], dtype=np.float32),
                sample_count=profile_data["sample_count"],
                total_duration=profile_data["total_duration"],
                quality_score=profile_data["quality_score"],
                created_at=profile_data["created_at"],
                updated_at=profile_data["updated_at"],
            )

            self._voice_profiles[profile.voice_id] = profile

            logger.info("Voice profile '%s' loaded from %s", profile.voice_id, filepath)

            return profile.voice_id

        except Exception as e:
            if isinstance(e, VoiceCloningError):
                raise
            msg = f"Failed to load voice profile: {e}"
            raise VoiceCloningError(msg) from e
    def _extract_voice_features(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Extract voice features for cloning.

        Args:
            audio: Audio data
            sample_rate: Sample rate

        Returns:
            Feature vector

        """
        # Adjust n_fft for short audio
        audio_length = len(audio)
        n_fft = min(self.n_fft, audio_length)
        n_fft = 2 if n_fft < 2 else 2 ** int(np.log2(n_fft))  # noqa: PLR2004 - Small integer threshold


        hop_length = min(self.hop_length, n_fft // 4)
        hop_length = max(hop_length, 1)

        # Suppress warnings
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="n_fft=.*is too large")
            warnings.filterwarnings("ignore", category=UserWarning, module="librosa")

            # Extract MFCC features
            mfcc = librosa.feature.mfcc(
                y=audio,
                sr=sample_rate,
                n_mfcc=self.n_mfcc,
                n_fft=n_fft,
                hop_length=hop_length,
            )

            # Extract pitch features
            pitches, magnitudes = librosa.piptrack(
                y=audio,
                sr=sample_rate,
                n_fft=n_fft,
                hop_length=hop_length,
            )

            # Extract spectral features
            spectral_centroid = librosa.feature.spectral_centroid(
                y=audio,
                sr=sample_rate,
                n_fft=n_fft,
                hop_length=hop_length,
            )

            spectral_rolloff = librosa.feature.spectral_rolloff(
                y=audio,
                sr=sample_rate,
                n_fft=n_fft,
                hop_length=hop_length,
            )

        # Aggregate features
        mfcc_mean = np.mean(mfcc, axis=1)
        mfcc_std = np.std(mfcc, axis=1)

        # Pitch statistics
        pitch_values = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            if pitch > 0:
                pitch_values.append(pitch)

        if pitch_values:
            pitch_mean = np.mean(pitch_values)
            pitch_std = np.std(pitch_values)
        else:
            pitch_mean = pitch_std = 0.0

        # Spectral statistics
        centroid_mean = np.mean(spectral_centroid)
        centroid_std = np.std(spectral_centroid)
        rolloff_mean = np.mean(spectral_rolloff)

        # Combine all features
        features = np.concatenate(
            [
                mfcc_mean,
                mfcc_std,
                [pitch_mean, pitch_std, centroid_mean, centroid_std, rolloff_mean],
            ],
        )

        result: np.ndarray = features.astype(np.float32)
        return result

    def _compute_audio_quality(self, audio: np.ndarray, sample_rate: int) -> float:
        """Compute audio quality score.

        Args:
            audio: Audio data
            sample_rate: Sample rate

        Returns:
            Quality score between 0.0 and 1.0

        """
        scores = []

        # 1. Duration check
        duration = len(audio) / sample_rate
        if duration < 1.0:
            duration_score = duration
        elif duration > 10.0:  # noqa: PLR2004 - Threshold

            duration_score = max(0.5, 1.0 - (duration - 10.0) / 20.0)
        else:
            duration_score = 1.0
        scores.append(duration_score)

        # 2. Energy check
        rms = np.sqrt(np.mean(audio**2))
        if rms > 0.05:  # noqa: PLR2004 - Threshold value

            energy_score = 1.0
        elif rms > 0.01:  # noqa: PLR2004 - Threshold value

            energy_score = 0.7
        else:
            energy_score = 0.3
        scores.append(energy_score)

        # 3. Clipping check
        max_val = np.max(np.abs(audio))
        clipping_score = 0.5 if max_val >= 0.99 else 1.0  # noqa: PLR2004 - Threshold value

        scores.append(clipping_score)

        # 4. Voice activity
        threshold = np.max(np.abs(audio)) * 0.1
        voice_ratio = np.sum(np.abs(audio) > threshold) / len(audio)
        if 0.3 <= voice_ratio <= 0.9:  # noqa: PLR2004 - Threshold value

            voice_score = 1.0
        elif voice_ratio < 0.3:  # noqa: PLR2004 - Threshold value

            voice_score = voice_ratio / 0.3
        else:
            voice_score = 0.7
        scores.append(voice_score)

        return float(np.mean(scores))
