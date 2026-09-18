"""Emotion detection from voice patterns."""

import logging
import time
from collections.abc import AsyncIterator

import librosa
import numpy as np

from Agent_Guru.speech.exceptions import EmotionDetectionError
from Agent_Guru.speech.models import EmotionHistory, EmotionResult, EmotionType

logger = logging.getLogger(__name__)


class EmotionDetector:
    """Detect emotional state from voice patterns.

    Uses acoustic features (pitch, energy, tempo, MFCC, spectral features)
    to classify emotional state into 7 categories:
    - HAPPY: High pitch, high energy, fast tempo
    - SAD: Low pitch, low energy, slow tempo
    - ANGRY: High pitch variance, high energy, fast tempo
    - NEUTRAL: Moderate pitch, moderate energy, moderate tempo
    - SURPRISED: High pitch, high energy, fast tempo with sudden changes
    - FEARFUL: High pitch, moderate energy, fast tempo with tremor
    - DISGUSTED: Low pitch, moderate energy, slow tempo

    Completes analysis within 200ms as per requirements.
    """

    def __init__(self, model_path: str | None = None) -> None:
        """Initialize emotion detector.

        Args:
            model_path: Path to emotion detection model (optional, uses rule-based if None)

        """
        self.model_path = model_path
        self._use_ml_model = model_path is not None

        # Emotion feature thresholds (rule-based approach)
        # These are empirically derived values for acoustic features
        self._emotion_profiles = {
            EmotionType.HAPPY: {
                "pitch_mean": (200, 300),  # Hz
                "pitch_std": (20, 60),
                "energy_mean": (0.05, 0.3),
                "tempo": (120, 180),  # BPM
                "zcr_mean": (0.1, 0.3),
            },
            EmotionType.SAD: {
                "pitch_mean": (100, 180),
                "pitch_std": (10, 30),
                "energy_mean": (0.01, 0.08),
                "tempo": (60, 100),
                "zcr_mean": (0.05, 0.15),
            },
            EmotionType.ANGRY: {
                "pitch_mean": (180, 280),
                "pitch_std": (40, 100),
                "energy_mean": (0.1, 0.4),
                "tempo": (130, 200),
                "zcr_mean": (0.15, 0.35),
            },
            EmotionType.NEUTRAL: {
                "pitch_mean": (120, 220),
                "pitch_std": (15, 40),
                "energy_mean": (0.03, 0.15),
                "tempo": (90, 130),
                "zcr_mean": (0.08, 0.2),
            },
            EmotionType.SURPRISED: {
                "pitch_mean": (220, 320),
                "pitch_std": (30, 80),
                "energy_mean": (0.08, 0.35),
                "tempo": (140, 200),
                "zcr_mean": (0.12, 0.3),
            },
            EmotionType.FEARFUL: {
                "pitch_mean": (200, 300),
                "pitch_std": (35, 90),
                "energy_mean": (0.04, 0.2),
                "tempo": (110, 160),
                "zcr_mean": (0.1, 0.28),
            },
            EmotionType.DISGUSTED: {
                "pitch_mean": (100, 190),
                "pitch_std": (15, 45),
                "energy_mean": (0.03, 0.12),
                "tempo": (70, 110),
                "zcr_mean": (0.06, 0.18),
            },
        }

        logger.info("EmotionDetector initialized (ML model: %s)", self._use_ml_model)

    def detect_emotion(self, audio: np.ndarray, sample_rate: int) -> EmotionResult:
        """Detect emotion from audio.

        Completes analysis within 200ms as per requirements.

        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate in Hz

        Returns:
            EmotionResult with primary emotion and confidence scores

        Raises:
            EmotionDetectionError: If detection fails

        """
        start_time = time.time()

        try:
            # Extract acoustic features
            features = self.extract_acoustic_features(audio, sample_rate)

            # Compute audio quality score
            audio_quality = self._compute_audio_quality(audio, features, sample_rate)

            # Classify emotion based on features
            emotion_scores = self._classify_emotion(features, audio_quality)

            # Get primary emotion (highest score)
            primary_emotion = max(emotion_scores.items(), key=lambda x: x[1])[0]
            confidence = emotion_scores[primary_emotion]

            # Check processing time (should be < 200ms)
            processing_time = (time.time() - start_time) * 1000
            if processing_time > 200:
                logger.warning("Emotion detection took %.1fms (target: <200ms)", processing_time)

            result = EmotionResult(
                primary_emotion=primary_emotion,
                emotion_scores=emotion_scores,
                confidence=confidence,
                timestamp=time.time(),
                audio_quality=audio_quality,
            )

            logger.debug(
                f"Detected emotion: {primary_emotion.value} "
                f"(confidence: {confidence:.2f}, quality: {audio_quality:.2f}, "
                f"time: {processing_time:.1f}ms)",
            )

            return result

        except Exception as e:
            msg = f"Failed to detect emotion: {e}"
            raise EmotionDetectionError(msg) from e

    async def detect_emotion_streaming(
        self,
        audio_stream: AsyncIterator[np.ndarray],
        sample_rate: int,
    ) -> AsyncIterator[EmotionResult]:
        """Detect emotion from streaming audio.

        Yields emotion results as audio is processed in real-time.

        Args:
            audio_stream: Async iterator of audio chunks
            sample_rate: Sample rate in Hz

        Yields:
            EmotionResult for each audio chunk

        """
        try:
            async for audio_chunk in audio_stream:
                # Skip very short chunks
                if len(audio_chunk) < sample_rate * 0.5:  # At least 0.5 seconds
                    continue

                # Detect emotion for this chunk (synchronous call)
                result = self.detect_emotion(audio_chunk, sample_rate)
                yield result

        except Exception as e:
            logger.exception("Streaming emotion detection failed")
            msg = f"Streaming detection failed: {e}"
            raise EmotionDetectionError(msg) from e

    def track_emotion_history(
        self,
        emotions: list[EmotionResult],
        window_seconds: float = 60.0,
    ) -> EmotionHistory:
        """Track emotion changes over time.

        Analyzes emotion transitions and identifies dominant emotion
        within the specified time window.

        Args:
            emotions: List of emotion results
            window_seconds: Time window for analysis (default: 60 seconds)

        Returns:
            EmotionHistory with transitions and dominant emotion

        """
        try:
            if not emotions:
                # Return neutral if no emotions
                return EmotionHistory(
                    emotions=[],
                    dominant_emotion=EmotionType.NEUTRAL,
                    emotion_transitions=[],
                )

            # Filter emotions within time window
            current_time = time.time()
            cutoff_time = current_time - window_seconds
            recent_emotions = [e for e in emotions if e.timestamp >= cutoff_time]

            if not recent_emotions:
                recent_emotions = emotions[-10:]  # Use last 10 if none in window

            # Detect emotion transitions
            transitions = []
            for i in range(1, len(recent_emotions)):
                prev_emotion = recent_emotions[i - 1].primary_emotion
                curr_emotion = recent_emotions[i].primary_emotion

                # Only record actual transitions (emotion changes)
                if prev_emotion != curr_emotion:
                    transitions.append((prev_emotion, curr_emotion, recent_emotions[i].timestamp))

            # Calculate dominant emotion (weighted by confidence)
            emotion_weights: dict[EmotionType, float] = {}
            for emotion_result in recent_emotions:
                emotion = emotion_result.primary_emotion
                weight = emotion_result.confidence * emotion_result.audio_quality
                emotion_weights[emotion] = emotion_weights.get(emotion, 0.0) + weight

            # Get dominant emotion
            if emotion_weights:
                dominant_emotion = max(emotion_weights.items(), key=lambda x: x[1])[0]
            else:
                dominant_emotion = EmotionType.NEUTRAL

            history = EmotionHistory(
                emotions=recent_emotions,
                dominant_emotion=dominant_emotion,
                emotion_transitions=transitions,
            )

            logger.debug(
                f"Emotion history: {len(recent_emotions)} emotions, "
                f"{len(transitions)} transitions, dominant: {dominant_emotion.value}",
            )

            return history

        except Exception as e:
            msg = f"Failed to track emotion history: {e}"
            raise EmotionDetectionError(msg) from e

    def extract_acoustic_features(self, audio: np.ndarray, sample_rate: int) -> dict[str, float]:
        """Extract acoustic features for emotion detection.

        Features include:
        - Pitch (F0): Mean and standard deviation
        - Energy: RMS energy
        - Tempo: Estimated speaking rate
        - MFCC: Mel-frequency cepstral coefficients
        - Zero Crossing Rate: Voice quality indicator
        - Spectral features: Centroid, rolloff, bandwidth

        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate in Hz

        Returns:
            Dictionary of acoustic features

        """
        try:
            # Ensure audio is float32
            audio = audio.astype(np.float32)

            # Normalize audio
            if np.max(np.abs(audio)) > 0:
                audio = audio / np.max(np.abs(audio))

            features = {}

            # 1. Pitch (F0) features
            try:
                # Adjust n_fft for short audio to prevent warnings
                audio_length = len(audio)
                n_fft_pitch = min(2048, audio_length)
                if n_fft_pitch < 2:
                    n_fft_pitch = 2
                else:
                    # Round down to nearest power of 2
                    n_fft_pitch = 2 ** int(np.log2(n_fft_pitch))

                hop_length_pitch = min(512, n_fft_pitch // 4)
                hop_length_pitch = max(hop_length_pitch, 1)

                # Suppress librosa warnings for short audio
                import warnings

                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message="n_fft=.*is too large")
                    warnings.filterwarnings("ignore", category=UserWarning, module="librosa")

                    # Use librosa's piptrack for pitch detection
                    pitches, magnitudes = librosa.piptrack(
                        y=audio,
                        sr=sample_rate,
                        fmin=50,
                        fmax=400,
                        n_fft=n_fft_pitch,
                        hop_length=hop_length_pitch,
                    )

                # Extract pitch values where magnitude is highest
                pitch_values = []
                for t in range(pitches.shape[1]):
                    index = magnitudes[:, t].argmax()
                    pitch = pitches[index, t]
                    if pitch > 0:
                        pitch_values.append(pitch)

                if pitch_values:
                    features["pitch_mean"] = float(np.mean(pitch_values))
                    features["pitch_std"] = float(np.std(pitch_values))
                    features["pitch_min"] = float(np.min(pitch_values))
                    features["pitch_max"] = float(np.max(pitch_values))
                else:
                    features["pitch_mean"] = 150.0
                    features["pitch_std"] = 20.0
                    features["pitch_min"] = 100.0
                    features["pitch_max"] = 200.0
            except Exception:
                logger.exception("Pitch extraction failed")
                features["pitch_mean"] = 150.0
                features["pitch_std"] = 20.0
                features["pitch_min"] = 100.0
                features["pitch_max"] = 200.0

            # 2. Energy features
            rms = librosa.feature.rms(y=audio)[0]
            features["energy_mean"] = float(np.mean(rms))
            features["energy_std"] = float(np.std(rms))
            features["energy_max"] = float(np.max(rms))

            # 3. Tempo (speaking rate)
            try:
                # Adjust hop_length for short audio
                audio_length = len(audio)
                hop_length_tempo = min(512, audio_length // 4)
                hop_length_tempo = max(hop_length_tempo, 1)

                # Suppress warnings
                import warnings

                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message="n_fft=.*is too large")
                    warnings.filterwarnings("ignore", category=UserWarning, module="librosa")

                    tempo, _ = librosa.beat.beat_track(
                        y=audio,
                        sr=sample_rate,
                        hop_length=hop_length_tempo,
                    )
                # Ensure tempo is a scalar
                if isinstance(tempo, np.ndarray):
                    tempo = float(tempo.item()) if tempo.size == 1 else float(tempo[0])
                else:
                    tempo = float(tempo)
                # Ensure reasonable tempo range
                if tempo <= 0 or tempo > 300:
                    tempo = 100.0
                features["tempo"] = tempo
            except Exception:
                logger.exception("Tempo extraction failed")
                features["tempo"] = 100.0

            # 4. MFCC features (first 13 coefficients)
            # Adjust n_fft for short audio
            audio_length = len(audio)
            n_fft_mfcc = min(2048, audio_length)
            n_fft_mfcc = 2 if n_fft_mfcc < 2 else 2 ** int(np.log2(n_fft_mfcc))

            hop_length_mfcc = min(512, n_fft_mfcc // 4)
            hop_length_mfcc = max(hop_length_mfcc, 1)

            # Suppress warnings
            import warnings

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="n_fft=.*is too large")
                warnings.filterwarnings("ignore", category=UserWarning, module="librosa")

                mfccs = librosa.feature.mfcc(
                    y=audio,
                    sr=sample_rate,
                    n_mfcc=13,
                    n_fft=n_fft_mfcc,
                    hop_length=hop_length_mfcc,
                )
            for i in range(min(13, mfccs.shape[0])):
                features[f"mfcc_{i}_mean"] = float(np.mean(mfccs[i]))
                features[f"mfcc_{i}_std"] = float(np.std(mfccs[i]))

            # 5. Zero Crossing Rate
            # Adjust frame_length for short audio
            frame_length_zcr = min(2048, len(audio))
            frame_length_zcr = max(frame_length_zcr, 2)

            hop_length_zcr = min(512, frame_length_zcr // 4)
            hop_length_zcr = max(hop_length_zcr, 1)

            import warnings

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning, module="librosa")

                zcr = librosa.feature.zero_crossing_rate(
                    audio,
                    frame_length=frame_length_zcr,
                    hop_length=hop_length_zcr,
                )[0]
            features["zcr_mean"] = float(np.mean(zcr))
            features["zcr_std"] = float(np.std(zcr))

            # 6. Spectral features
            # Adjust n_fft for short audio
            audio_length = len(audio)
            n_fft_spectral = min(2048, audio_length)
            n_fft_spectral = 2 if n_fft_spectral < 2 else 2 ** int(np.log2(n_fft_spectral))

            hop_length_spectral = min(512, n_fft_spectral // 4)
            hop_length_spectral = max(hop_length_spectral, 1)

            import warnings

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="n_fft=.*is too large")
                warnings.filterwarnings("ignore", category=UserWarning, module="librosa")

                spectral_centroids = librosa.feature.spectral_centroid(
                    y=audio,
                    sr=sample_rate,
                    n_fft=n_fft_spectral,
                    hop_length=hop_length_spectral,
                )[0]
                features["spectral_centroid_mean"] = float(np.mean(spectral_centroids))
                features["spectral_centroid_std"] = float(np.std(spectral_centroids))

                spectral_rolloff = librosa.feature.spectral_rolloff(
                    y=audio,
                    sr=sample_rate,
                    n_fft=n_fft_spectral,
                    hop_length=hop_length_spectral,
                )[0]
                features["spectral_rolloff_mean"] = float(np.mean(spectral_rolloff))

                spectral_bandwidth = librosa.feature.spectral_bandwidth(
                    y=audio,
                    sr=sample_rate,
                    n_fft=n_fft_spectral,
                    hop_length=hop_length_spectral,
                )[0]
                features["spectral_bandwidth_mean"] = float(np.mean(spectral_bandwidth))

            return features

        except Exception:
            logger.exception("Feature extraction failed")
            # Return default features
            return {
                "pitch_mean": 150.0,
                "pitch_std": 20.0,
                "energy_mean": 0.1,
                "tempo": 100.0,
                "zcr_mean": 0.1,
            }

    def _classify_emotion(
        self,
        features: dict[str, float],
        audio_quality: float,
    ) -> dict[EmotionType, float]:
        """Classify emotion based on acoustic features.

        Uses rule-based classification with feature matching.
        Returns confidence scores for all emotion types.

        Args:
            features: Extracted acoustic features
            audio_quality: Audio quality score (0.0-1.0)

        Returns:
            Dictionary mapping EmotionType to confidence scores

        """
        emotion_scores = {}

        # If audio quality is poor, we have no reliable signal to classify
        # on. BUG FIX (Round 17): this used to return an IDENTICAL score
        # (0.3) for every EmotionType. Since detect_emotion() picks the
        # primary emotion via max(emotion_scores.items(), key=...), a tie
        # across all 7 emotions is broken by dict/enum iteration order --
        # meaning every low-quality utterance was silently classified as
        # whichever EmotionType happens to be declared first, which is not
        # necessarily (and should not be assumed to be) NEUTRAL. Give
        # NEUTRAL a strictly higher score so poor-quality audio
        # deterministically and correctly reports "we don't know" rather
        # than an arbitrary, possibly-wrong specific emotion.
        if audio_quality < 0.3:
            low_confidence_scores = dict.fromkeys(EmotionType, 0.1)
            low_confidence_scores[EmotionType.NEUTRAL] = 0.3
            return low_confidence_scores

        # Calculate match score for each emotion
        for emotion, profile in self._emotion_profiles.items():
            score = 0.0
            matches = 0

            # Check each feature against emotion profile
            for feature_name, (min_val, max_val) in profile.items():
                if feature_name in features:
                    feature_val = features[feature_name]

                    # Calculate how well feature matches profile
                    if min_val <= feature_val <= max_val:
                        # Perfect match
                        score += 1.0
                    else:
                        # Partial match based on distance
                        range_size = max_val - min_val
                        if feature_val < min_val:
                            distance = min_val - feature_val
                        else:
                            distance = feature_val - max_val

                        # Exponential decay for distance
                        match_score = np.exp(-distance / range_size)
                        score += match_score

                    matches += 1

            # Normalize score by number of features
            normalized_score = score / matches if matches > 0 else 0.5

            # Apply audio quality weighting
            final_score = normalized_score * (0.5 + 0.5 * audio_quality)

            # Ensure score is in valid range
            emotion_scores[emotion] = float(np.clip(final_score, 0.0, 1.0))

        # Normalize scores to sum to 1.0
        total_score = sum(emotion_scores.values())
        if total_score > 0:
            emotion_scores = {
                emotion: score / total_score for emotion, score in emotion_scores.items()
            }
        else:
            # Default to neutral if all scores are zero
            emotion_scores = {emotion: 1.0 / len(EmotionType) for emotion in EmotionType}

        return emotion_scores

    def _compute_audio_quality(
        self,
        audio: np.ndarray,
        features: dict[str, float],
        sample_rate: int,
    ) -> float:
        """Compute audio quality score for emotion detection.

        Considers:
        - Signal-to-noise ratio (SNR)
        - Audio duration
        - Voice activity
        - Feature reliability

        Args:
            audio: Audio data
            features: Extracted features
            sample_rate: Sample rate in Hz of `audio`

        Returns:
            Quality score between 0.0 and 1.0

        """
        quality_factors = []

        # 1. Check audio duration (prefer 1-5 seconds)
        # BUG FIX (Round 17): this used to hardcode `len(audio) / 16000.0`
        # regardless of the actual sample rate, even though detect_emotion()
        # receives (and extract_acoustic_features() correctly uses) the real
        # `sample_rate`. Any caller passing non-16kHz audio (e.g. 44.1kHz
        # capture, or 8kHz telephony) got a silently wrong duration, which
        # corrupted duration_score and therefore the overall audio_quality
        # score feeding directly into emotion classification confidence.
        duration = len(audio) / float(sample_rate) if sample_rate > 0 else len(audio) / 16000.0
        if 1.0 <= duration <= 5.0:
            duration_score = 1.0
        elif duration < 1.0:
            duration_score = duration  # Linear penalty for short audio
        else:
            duration_score = max(0.5, 1.0 - (duration - 5.0) / 10.0)
        quality_factors.append(duration_score)

        # 2. Check energy level (not too quiet or too loud)
        energy = features.get("energy_mean", 0.1)
        if 0.05 <= energy <= 0.3:
            energy_score = 1.0
        elif energy < 0.05:
            # Very quiet audio - strong penalty
            energy_score = max(0.1, energy / 0.05)
        else:
            energy_score = max(0.3, 1.0 - (energy - 0.3) / 0.7)
        quality_factors.append(energy_score)

        # 3. Check pitch reliability (should have reasonable variance)
        pitch_std = features.get("pitch_std", 20.0)
        if 10.0 <= pitch_std <= 100.0:
            pitch_score = 1.0
        elif pitch_std < 10.0:
            # Very low variance - likely noise or silence
            pitch_score = max(0.1, pitch_std / 10.0)
        else:
            pitch_score = max(0.3, 1.0 - (pitch_std - 100.0) / 100.0)
        quality_factors.append(pitch_score)

        # 4. Check zero crossing rate (voice quality indicator)
        zcr = features.get("zcr_mean", 0.1)
        zcr_score = 1.0 if 0.05 <= zcr <= 0.35 else 0.5

        quality_factors.append(zcr_score)

        # 5. Check signal strength (RMS)
        rms = np.sqrt(np.mean(audio**2))
        if rms > 0.02:  # Reasonable signal strength
            signal_score = 1.0
        elif rms > 0.005:  # Weak signal
            signal_score = 0.5
        else:
            # Very weak signal - likely silence or noise
            signal_score = 0.1
        quality_factors.append(signal_score)

        # Compute overall quality as weighted average
        quality = float(np.mean(quality_factors))

        result: float = float(np.clip(quality, 0.0, 1.0))
        return result
