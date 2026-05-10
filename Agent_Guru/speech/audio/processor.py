"""Audio processing with VAD, noise reduction, and AGC."""

import logging
from typing import Any

import numpy as np

from Agent_Guru.speech.config import AudioProcessingConfig
from Agent_Guru.speech.exceptions import AudioProcessingError

logger = logging.getLogger(__name__)

# Lazy import to avoid loading torch unnecessarily
_noisereduce: Any | None = None


def _get_noisereduce() -> Any | None:  # noqa: ANN401
    """Lazy import of noisereduce to avoid torch loading issues."""
    global _noisereduce
    if _noisereduce is None:
        try:
            import noisereduce as nr

            _noisereduce = nr
        except Exception:
            logger.exception("Failed to import noisereduce")
            # Set to False to indicate failed import (not None which means not tried yet)
            _noisereduce = False
    return _noisereduce if _noisereduce is not False else None


class AudioProcessor:
    """Audio processor with Voice Activity Detection, noise reduction, and AGC.

    Provides real-time audio enhancement for speech recognition.
    """

    def __init__(self, config: AudioProcessingConfig, sample_rate: int = 16000) -> None:
        """Initialize audio processor.

        Args:
            config: Audio processing configuration
            sample_rate: Sample rate in Hz

        """
        self.config = config
        self.sample_rate = sample_rate
        self._noise_profile: np.ndarray | None = None

        logger.info(
            f"AudioProcessor initialized: VAD={config.enable_vad}, "
            f"NoiseReduction={config.enable_noise_reduction}, "
            f"AGC={config.enable_agc}",
        )

    async def process_chunk(self, audio: np.ndarray) -> np.ndarray:
        """Process a single audio chunk with all enabled enhancements.

        Applies noise reduction, AGC, and other processing in optimal order.

        Args:
            audio: Audio chunk as numpy array

        Returns:
            Processed audio chunk

        Raises:
            AudioProcessingError: If processing fails

        """
        try:
            processed = audio.copy()

            # Apply noise reduction first
            if self.config.enable_noise_reduction:
                processed = await self.reduce_noise(processed)

            # Apply AGC to normalize levels
            if self.config.enable_agc:
                processed = await self.apply_agc(processed)

            return processed

        except Exception as e:
            msg = f"Failed to process audio chunk: {e}"
            raise AudioProcessingError(msg) from e

    async def detect_voice_activity(self, audio: np.ndarray) -> bool:
        """Detect if voice is present in audio chunk.

        Uses energy-based VAD with configurable aggressiveness.

        Args:
            audio: Audio chunk as numpy array

        Returns:
            True if voice activity detected, False otherwise

        """
        if not self.config.enable_vad:
            return True

        try:
            # Calculate energy
            energy = float(np.sum(audio**2) / len(audio))

            # Calculate zero crossing rate
            zero_crossings = float(np.sum(np.abs(np.diff(np.sign(audio)))) / (2 * len(audio)))

            # Thresholds based on aggressiveness (0-3)
            # Higher aggressiveness = higher thresholds = more selective
            energy_thresholds = [0.001, 0.005, 0.01, 0.02]
            zcr_thresholds = [0.05, 0.08, 0.1, 0.15]

            aggressiveness = min(3, max(0, self.config.vad_aggressiveness))
            energy_threshold = energy_thresholds[aggressiveness]
            zcr_threshold = zcr_thresholds[aggressiveness]

            # Voice typically has moderate energy and zero crossing rate
            return bool(energy > energy_threshold and zero_crossings > zcr_threshold)

        except Exception:
            logger.exception("VAD failed: %s, assuming voice present")
            return True

    async def reduce_noise(self, audio: np.ndarray) -> np.ndarray:
        """Apply noise reduction to audio.

        Uses spectral subtraction via noisereduce library.

        Args:
            audio: Audio chunk as numpy array

        Returns:
            Noise-reduced audio

        """
        try:
            nr = _get_noisereduce()
            if nr is None:
                logger.warning("noisereduce not available, returning original audio")
                return audio

            # Ensure audio is float32 for noisereduce
            audio_float = audio.astype(np.float32)

            # Apply noise reduction with configured strength
            # prop_decrease controls how much noise to reduce (0.0-1.0)
            reduced: np.ndarray = nr.reduce_noise(
                y=audio_float,
                sr=self.sample_rate,
                prop_decrease=self.config.noise_reduction_strength,
                stationary=True,
            )

            return reduced

        except Exception:
            logger.exception("Noise reduction failed: %s, returning original audio")
            return audio

    async def cancel_echo(self, audio: np.ndarray, reference: np.ndarray) -> np.ndarray:
        """Cancel echo using reference signal.

        Simple echo cancellation using adaptive filtering.

        Args:
            audio: Audio with echo
            reference: Reference signal (playback audio)

        Returns:
            Echo-cancelled audio

        """
        if not self.config.enable_echo_cancellation:
            return audio

        try:
            # Ensure same length
            min_len = min(len(audio), len(reference))
            audio = audio[:min_len]
            reference = reference[:min_len]

            # Simple echo cancellation: subtract scaled reference
            # In production, use adaptive filter (LMS, NLMS, etc.)
            echo_estimate = reference * 0.3  # Simple scaling
            cancelled: np.ndarray = audio - echo_estimate

            return cancelled

        except Exception:
            logger.exception("Echo cancellation failed: %s, returning original audio")
            return audio

    async def apply_agc(self, audio: np.ndarray) -> np.ndarray:
        """Apply automatic gain control to normalize audio levels.

        Normalizes audio to target RMS level while preventing clipping.

        Args:
            audio: Audio chunk as numpy array

        Returns:
            Gain-controlled audio

        """
        try:
            # Calculate current RMS
            rms = np.sqrt(np.mean(audio**2))

            if rms < 1e-6:  # Silence  # noqa: PLR2004 (Epsilon value)

                return audio

            # Target RMS (normalized to -20dB)
            target_rms = 0.1

            # Calculate gain
            gain = target_rms / rms

            # Limit gain to prevent excessive amplification
            max_gain = 10.0
            gain = min(gain, max_gain)

            # Apply gain
            normalized = audio * gain

            # Prevent clipping
            max_val = np.max(np.abs(normalized))
            if max_val > 1.0:
                normalized = normalized / max_val * 0.95

            result: np.ndarray = normalized
            return result

        except Exception:
            logger.exception("AGC failed: %s, returning original audio")
            return audio

    def convert_format(self, audio: np.ndarray, target_rate: int) -> np.ndarray:
        """Convert audio sample rate.

        Uses simple linear interpolation for resampling.
        For production, consider using scipy.signal.resample or librosa.

        Args:
            audio: Audio data
            target_rate: Target sample rate in Hz

        Returns:
            Resampled audio

        """
        if self.sample_rate == target_rate:
            return audio

        try:
            # Calculate resampling ratio
            ratio = target_rate / self.sample_rate

            # Calculate new length
            new_length = int(len(audio) * ratio)

            # Simple linear interpolation
            indices = np.linspace(0, len(audio) - 1, new_length)
            return np.interp(indices, np.arange(len(audio)), audio)

        except Exception as e:
            msg = f"Format conversion failed: {e}"
            raise AudioProcessingError(msg) from e

    def set_noise_profile(self, noise_sample: np.ndarray) -> None:
        """Set noise profile for adaptive noise reduction.

        Args:
            noise_sample: Sample of background noise

        """
        self._noise_profile = noise_sample
        logger.info("Noise profile updated")

    def reset(self) -> None:
        """Reset processor state."""
        self._noise_profile = None
        logger.debug("AudioProcessor reset")
