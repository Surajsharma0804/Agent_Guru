"""
Production-grade Audio Preprocessing Pipeline

This module provides comprehensive audio preprocessing for voice processing:
- Noise reduction and filtering
- Audio normalization and enhancement
- Format conversion and validation
- Security hardening against audio injection
- Real-time processing capabilities
"""

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import scipy.signal
from scipy.io import wavfile


class AudioFormat(Enum):
    """Supported audio formats"""

    WAV = "wav"
    PCM = "pcm"
    FLOAT32 = "float32"


class NoiseReductionLevel(Enum):
    """Noise reduction intensity levels"""

    NONE = "none"
    LIGHT = "light"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass
class AudioMetrics:
    """Audio quality and security metrics"""

    sample_rate: int
    duration_seconds: float
    channels: int
    bit_depth: int
    rms_level: float
    peak_level: float
    snr_estimate: float
    clipping_detected: bool
    silence_ratio: float
    frequency_range_hz: Tuple[float, float]
    security_flags: List[str]

    @property
    def is_good_quality(self) -> bool:
        """Check if audio meets quality standards"""
        return (
            self.snr_estimate > 10.0  # Good signal-to-noise ratio
            and not self.clipping_detected
            and self.silence_ratio < 0.8  # Not mostly silent
            and self.rms_level > 0.01  # Has actual content
        )


@dataclass
class PreprocessingConfig:
    """Audio preprocessing configuration"""

    target_sample_rate: int = 16000  # Whisper expects 16kHz
    target_channels: int = 1  # Mono
    normalize_audio: bool = True
    noise_reduction: NoiseReductionLevel = NoiseReductionLevel.MODERATE
    high_pass_cutoff: float = 80.0  # Remove low-frequency noise
    low_pass_cutoff: float = 7000.0  # Remove high-frequency noise (below Nyquist)
    max_duration_seconds: float = 30.0
    enable_security_checks: bool = True

    # Advanced settings
    frame_size: int = 1024
    hop_length: int = 512
    spectral_subtraction_alpha: float = 2.0
    wiener_filter_enabled: bool = True


class VoiceSignalSecurityValidator:
    """
    Production-grade audio preprocessing pipeline

    Features:
    - Multi-stage noise reduction
    - Format conversion and normalization
    - Security validation and injection detection
    - Real-time processing capabilities
    - Comprehensive quality metrics
    - Thread-safe operation
    """

    def __init__(self, config: Optional[PreprocessingConfig] = None):
        self.config = config or PreprocessingConfig()
        self._lock = threading.RLock()
        self.logger = logging.getLogger(__name__)

        # Processing statistics
        self._stats = {
            "total_processed": 0,
            "successful_processed": 0,
            "rejected_security": 0,
            "rejected_quality": 0,
            "average_snr": 0.0,
            "average_processing_time_ms": 0.0,
        }

        # Initialize filters
        self._initialize_filters()

    def _initialize_filters(self) -> None:
        """Initialize audio filters and processing components"""
        try:
            # Design high-pass filter (remove low-frequency noise)
            nyquist = self.config.target_sample_rate / 2
            high_cutoff = self.config.high_pass_cutoff / nyquist
            self._high_pass_filter = scipy.signal.butter(4, high_cutoff, btype="high", output="sos")

            # Design low-pass filter (remove high-frequency noise)
            low_cutoff = self.config.low_pass_cutoff / nyquist
            self._low_pass_filter = scipy.signal.butter(4, low_cutoff, btype="low", output="sos")

            self.logger.info("Audio filters initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize audio filters: {e}")
            raise RuntimeError(f"Audio preprocessing initialization failed: {e}")

    def _convert_sample_rate(self, audio: np.ndarray, original_rate: int) -> np.ndarray:
        """Convert audio to target sample rate using high-quality resampling"""
        if original_rate == self.config.target_sample_rate:
            return audio

        try:
            # Use scipy's high-quality resampling
            target_length = int(len(audio) * self.config.target_sample_rate / original_rate)
            resampled = scipy.signal.resample(audio, target_length)

            self.logger.debug(f"Resampled audio from {original_rate}Hz to {self.config.target_sample_rate}Hz")
            return resampled.astype(np.float32)

        except Exception as e:
            self.logger.error(f"Sample rate conversion failed: {e}")
            raise

    def _convert_to_mono(self, audio: np.ndarray) -> np.ndarray:
        """Convert stereo/multi-channel audio to mono"""
        if len(audio.shape) == 1:
            return audio  # Already mono

        if len(audio.shape) == 2:
            # Convert stereo to mono by averaging channels
            return np.mean(audio, axis=1).astype(np.float32)
        else:
            raise ValueError(f"Unsupported audio shape: {audio.shape}")

    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio amplitude to prevent clipping and improve consistency"""
        if not self.config.normalize_audio:
            return audio

        try:
            # Calculate RMS level
            rms = np.sqrt(np.mean(audio**2))

            if rms < 1e-6:
                # Essentially silent
                return audio

            # Target RMS level (prevents clipping while maintaining dynamics)
            target_rms = 0.2

            # Calculate normalization factor
            normalization_factor = target_rms / rms

            # Apply normalization with peak limiting
            normalized = audio * normalization_factor

            # Soft limiting to prevent clipping
            peak = np.max(np.abs(normalized))
            if peak > 0.95:
                normalized = normalized * (0.95 / peak)

            return normalized.astype(np.float32)

        except Exception as e:
            self.logger.error(f"Audio normalization failed: {e}")
            return audio

    def _apply_noise_reduction(self, audio: np.ndarray) -> np.ndarray:
        """Apply noise reduction based on configuration"""
        if self.config.noise_reduction == NoiseReductionLevel.NONE:
            return audio

        try:
            # Apply high-pass filter to remove low-frequency noise
            filtered = scipy.signal.sosfilt(self._high_pass_filter, audio)

            # Apply low-pass filter to remove high-frequency noise
            filtered = scipy.signal.sosfilt(self._low_pass_filter, filtered)

            # Additional noise reduction based on level
            if self.config.noise_reduction in [NoiseReductionLevel.MODERATE, NoiseReductionLevel.AGGRESSIVE]:
                # Simple spectral subtraction (production would use more sophisticated methods)
                filtered = self._spectral_subtraction(filtered)

            return filtered.astype(np.float32)

        except Exception as e:
            self.logger.error(f"Noise reduction failed: {e}")
            return audio

    def _spectral_subtraction(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply spectral subtraction for noise reduction

        This is a simplified implementation. Production systems would use
        more sophisticated algorithms like Wiener filtering or deep learning.
        """
        try:
            # Estimate noise from first 0.5 seconds (assuming initial silence)
            noise_samples = min(int(0.5 * self.config.target_sample_rate), len(audio) // 4)

            if noise_samples < 100:
                return audio  # Not enough data for noise estimation

            noise_estimate = np.var(audio[:noise_samples])

            # Simple noise gate
            threshold = noise_estimate * 2.0

            # Apply soft noise gate
            mask = np.abs(audio) > threshold
            gated = audio * mask + audio * (1 - mask) * 0.1

            return gated.astype(np.float32)

        except Exception as e:
            self.logger.warning(f"Spectral subtraction failed: {e}")
            return audio

    def _calculate_audio_metrics(
        self, audio: np.ndarray, sample_rate: int, enable_security_checks: bool = True
    ) -> AudioMetrics:
        """Calculate comprehensive audio quality and security metrics"""
        try:
            duration = len(audio) / sample_rate

            # Basic metrics
            rms_level = np.sqrt(np.mean(audio**2))
            peak_level = np.max(np.abs(audio))

            # Clipping detection (more precise threshold)
            clipping_detected = peak_level >= 1.0

            # Silence detection (improved logic)
            if rms_level == 0.0:
                # Completely silent audio
                silence_ratio = 1.0
            else:
                silence_threshold = max(rms_level * 0.1, 1e-6)  # Minimum threshold for numerical stability
                silence_samples = np.sum(np.abs(audio) < silence_threshold)
                silence_ratio = silence_samples / len(audio)

            # SNR estimation (production-grade voice audio analysis)
            signal_power = rms_level**2

            if len(audio) > 512 and signal_power > 0:
                # Advanced spectral analysis for voice audio SNR estimation
                window_size = min(2048, len(audio))
                windowed_audio = audio[:window_size] * np.hanning(window_size)

                # Compute power spectral density
                fft_data = np.fft.fft(windowed_audio)
                power_spectrum = np.abs(fft_data) ** 2

                # For voice audio, separate signal and noise in frequency domain
                # Voice energy is typically concentrated in 85Hz-4kHz range
                freqs = np.fft.fftfreq(window_size, 1 / sample_rate)
                voice_band_mask = (np.abs(freqs) >= 85) & (np.abs(freqs) <= 4000)
                noise_band_mask = (np.abs(freqs) > 4000) & (np.abs(freqs) <= sample_rate / 2)

                if np.any(voice_band_mask) and np.any(noise_band_mask):
                    # Calculate signal power in voice band
                    voice_power = np.mean(power_spectrum[voice_band_mask])
                    # Calculate noise power in high-frequency band
                    noise_power = np.mean(power_spectrum[noise_band_mask])

                    if noise_power > 0:
                        snr_estimate = 10 * np.log10(voice_power / noise_power)
                        # Ensure reasonable bounds for voice audio
                        snr_estimate = max(0.0, min(60.0, snr_estimate))
                    else:
                        # Very clean signal
                        snr_estimate = 40.0
                else:
                    # Fallback: use time-domain analysis
                    # For clean synthetic audio, estimate based on dynamic range
                    if peak_level > 0 and rms_level > 0:
                        # Dynamic range-based SNR estimation
                        dynamic_range_db = 20 * np.log10(peak_level / (rms_level + 1e-10))
                        # For sine waves, theoretical SNR is related to bit depth and dynamic range
                        snr_estimate = max(15.0, min(dynamic_range_db + 10.0, 50.0))
                    else:
                        snr_estimate = 20.0
            else:
                # Short audio or no signal
                if peak_level > 0 and rms_level > 0:
                    # Simple heuristic for short audio
                    snr_estimate = 20 * np.log10(peak_level / (rms_level * 0.1 + 1e-10))
                    snr_estimate = max(0.0, min(snr_estimate, 40.0))
                else:
                    snr_estimate = 0.0  # Silent or invalid audio

            # Frequency analysis
            if len(audio) > 1024:
                fft = np.fft.fft(audio[:1024])
                freqs = np.fft.fftfreq(1024, 1 / sample_rate)
                magnitude = np.abs(fft)

                # Find frequency range with significant energy
                energy_threshold = np.max(magnitude) * 0.1
                significant_freqs = freqs[magnitude > energy_threshold]

                if len(significant_freqs) > 0:
                    freq_range = (float(np.min(np.abs(significant_freqs))), float(np.max(np.abs(significant_freqs))))
                else:
                    freq_range = (0.0, float(sample_rate / 2))
            else:
                freq_range = (0.0, float(sample_rate / 2))

            # Security flags (comprehensive threat detection)
            security_flags: List[str] = []

            if enable_security_checks and self.config.enable_security_checks:
                # Critical security violations (always reject)
                if duration > self.config.max_duration_seconds:
                    security_flags.append(f"duration_exceeded:{duration:.1f}s")

                # Severe audio anomalies indicating potential attacks
                if rms_level == 0.0 and peak_level == 0.0:
                    security_flags.append("no_signal")

                if silence_ratio > 0.98:
                    # Nearly complete silence (more lenient)
                    security_flags.append("mostly_silent")

                # Clipping detection (informational, not always critical)
                if clipping_detected:
                    security_flags.append("clipping_detected")

                # Frequency analysis for injection attacks
                if len(audio) > 512:
                    # Only for sufficient data
                    # Check for ultrasonic injection (above human hearing)
                    if freq_range[1] > sample_rate * 0.45:
                        # Above Nyquist safety margin
                        security_flags.append("suspicious_high_freq")

                    # Check for subsonic injection (below human hearing)
                    if freq_range[0] > 0 and freq_range[0] < 20:
                        # Below human hearing threshold
                        security_flags.append("suspicious_low_freq")

                # Statistical anomaly detection for synthetic audio
                if len(audio) > 1000:
                    # Check for unnatural amplitude distribution
                    amplitude_variance = np.var(audio)
                    if amplitude_variance > 1e-10:
                        # Avoid division by very small numbers
                        try:
                            audio_mean = np.mean(audio)
                            # Use numpy's built-in functions with proper error handling
                            with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
                                amplitude_kurtosis = np.mean((audio - audio_mean) ** 4) / (amplitude_variance**2)

                            # Check for valid result
                            if np.isfinite(amplitude_kurtosis) and amplitude_kurtosis > 10.0:
                                security_flags.append("unnatural_distribution")
                        except (FloatingPointError, RuntimeWarning):
                            # Skip kurtosis analysis if numerical issues occur
                            pass

                # Temporal pattern analysis for replay attacks (refined detection)
                if len(audio) > 4096:
                    # Require more data for reliable pattern detection
                    # Check for exact repetitive patterns indicating looped audio
                    chunk_size = min(len(audio) // 8, 2048)  # Smaller chunks for better detection
                    if chunk_size > 512:
                        # Minimum chunk size for meaningful analysis
                        chunks: List[np.ndarray] = []
                        for i in range(0, len(audio) - chunk_size, chunk_size):
                            if len(chunks) >= 4:
                                # Limit to 4 chunks for efficiency
                                break
                            chunks.append(audio[i : i + chunk_size])

                        if len(chunks) >= 3:
                            # Need at least 3 chunks for pattern detection
                            # Check for near-identical repetition (not just correlation)
                            correlations = []
                            for i in range(len(chunks) - 1):
                                try:
                                    with np.errstate(divide="ignore", invalid="ignore"):
                                        corr = np.corrcoef(chunks[i], chunks[i + 1])[0, 1]
                                    if np.isfinite(corr) and not np.isnan(corr):
                                        correlations.append(corr)
                                except (ValueError, RuntimeWarning):
                                    # Skip correlation if chunks are invalid (e.g., constant values)
                                    pass

                            # Only flag if ALL consecutive chunks are nearly identical
                            if correlations and all(corr > 0.98 for corr in correlations):
                                # Additional check: ensure it's not just a pure tone (legitimate)
                                chunk_variance = np.var(chunks[0])
                                if chunk_variance > 1e-6:
                                    # Has sufficient variation but still repetitive
                                    security_flags.append("repetitive_pattern")

            return AudioMetrics(
                sample_rate=sample_rate,
                duration_seconds=duration,
                channels=1,  # We convert to mono
                bit_depth=32,  # Float32
                rms_level=float(rms_level),
                peak_level=float(peak_level),
                snr_estimate=float(snr_estimate),
                clipping_detected=clipping_detected,
                silence_ratio=float(silence_ratio),
                frequency_range_hz=freq_range,
                security_flags=security_flags,
            )

        except Exception as e:
            self.logger.error(f"Audio metrics calculation failed: {e}")
            # Return minimal metrics on error
            return AudioMetrics(
                sample_rate=sample_rate,
                duration_seconds=len(audio) / sample_rate,
                channels=1,
                bit_depth=32,
                rms_level=0.0,
                peak_level=0.0,
                snr_estimate=0.0,
                clipping_detected=True,
                silence_ratio=1.0,
                frequency_range_hz=(0.0, float(sample_rate / 2)),
                security_flags=["metrics_calculation_failed"],
            )

    def process_audio(
        self, audio_data: np.ndarray, sample_rate: int, validate_security: bool = True
    ) -> Tuple[Optional[np.ndarray], AudioMetrics]:
        """
        Process audio through the complete preprocessing pipeline

        Alias for enforce_voice_signal_security_boundary for backward compatibility.

        Args:
            audio_data: Input audio as numpy array
            sample_rate: Sample rate of input audio
            validate_security: Whether to perform security validation

        Returns:
            Tuple of (processed_audio, metrics). processed_audio is None if rejected.
        """
        return self.enforce_voice_signal_security_boundary(audio_data, sample_rate, validate_security)

    def process_audio_file(self, file_path: str) -> Tuple[Optional[np.ndarray], AudioMetrics]:
        """
        Process audio from file

        Alias for enforce_voice_signal_security_boundary_from_file for backward compatibility.

        Args:
            file_path:  Path to audio file

        Returns:
            Tuple of (processed_audio, metrics)
        """
        return self.enforce_voice_signal_security_boundary_from_file(file_path)

    def enforce_voice_signal_security_boundary(
        self, audio_data: np.ndarray, sample_rate: int, validate_security: bool = True
    ) -> Tuple[Optional[np.ndarray], AudioMetrics]:
        """
        Process audio through the complete preprocessing pipeline

        Args:
            audio_data: Input audio as numpy array
            sample_rate: Sample rate of input audio
            validate_security: Whether to perform security validation

        Returns:
            Tuple of (processed_audio, metrics). processed_audio is None if rejected.
        """
        with self._lock:
            self._stats["total_processed"] += 1
            processing_start_time = time.time()

            try:
                # Convert to float32 if needed
                if audio_data.dtype != np.float32:
                    audio_data = audio_data.astype(np.float32)

                # Normalize to [-1, 1] range if needed
                if audio_data.dtype == np.int16:
                    audio_data = audio_data / 32768.0
                elif audio_data.dtype == np.int32:
                    audio_data = audio_data / 2147483648.0

                # Convert to mono
                audio_mono = self._convert_to_mono(audio_data)

                # Convert sample rate
                audio_resampled = self._convert_sample_rate(audio_mono, sample_rate)

                # Calculate initial metrics
                metrics = self._calculate_audio_metrics(
                    audio_resampled, self.config.target_sample_rate, validate_security
                )

                # Intelligent security validation (threat-based filtering)
                if validate_security and self.config.enable_security_checks:
                    # Critical threats that always require rejection
                    critical_threats = [
                        f
                        for f in metrics.security_flags
                        if any(
                            threat in f
                            for threat in [
                                "duration_exceeded",  # Resource exhaustion attack
                                "unnatural_distribution",  # Synthetic audio injection
                                "repetitive_pattern",  # Replay attack detection
                            ]
                        )
                    ]

                    # Informational flags that don't require rejection for normal use
                    informational_flags = [
                        f
                        for f in metrics.security_flags
                        if any(
                            info in f
                            for info in [
                                "clipping_detected",  # Common in real audio
                                "suspicious_high_freq",  # May be legitimate
                                "suspicious_low_freq",  # May be environmental
                            ]
                        )
                    ]

                    # Special handling for silence (context-dependent)
                    silence_flags = [
                        f
                        for f in metrics.security_flags
                        if any(silence in f for silence in ["no_signal", "mostly_silent"])
                    ]

                    # Reject only for critical threats or complete silence
                    should_reject = bool(critical_threats) or (
                        "no_signal" in metrics.security_flags and metrics.rms_level == 0.0 and metrics.peak_level == 0.0
                    )

                    if should_reject:
                        rejection_reason = critical_threats + (
                            ["complete_silence"] if "no_signal" in metrics.security_flags else []
                        )
                        self.logger.warning(f"Audio rejected due to security threats: {rejection_reason}")
                        self._stats["rejected_security"] += 1
                        return None, metrics

                    # Log informational flags without rejection
                    if informational_flags or silence_flags:
                        self.logger.info(f"Audio security flags (informational): {informational_flags + silence_flags}")

                # Quality validation
                if not metrics.is_good_quality:
                    self.logger.info(f"Audio rejected due to poor quality: SNR={metrics.snr_estimate:.1f}")
                    self._stats["rejected_quality"] += 1
                    return None, metrics

                # Apply preprocessing pipeline
                processed_audio = audio_resampled

                # Noise reduction
                processed_audio = self._apply_noise_reduction(processed_audio)

                # Normalization
                processed_audio = self._normalize_audio(processed_audio)

                # Final validation
                final_metrics = self._calculate_audio_metrics(
                    processed_audio, self.config.target_sample_rate, validate_security
                )

                # Update statistics
                self._stats["successful_processed"] += 1
                self._stats["average_snr"] = (
                    self._stats["average_snr"] * (self._stats["successful_processed"] - 1) + final_metrics.snr_estimate
                ) / self._stats["successful_processed"]

                processing_time_ms = int((time.time() - processing_start_time) * 1000)
                self._stats["average_processing_time_ms"] = (
                    self._stats["average_processing_time_ms"] * (self._stats["successful_processed"] - 1)
                    + processing_time_ms
                ) / self._stats["successful_processed"]

                self.logger.debug(f"Audio preprocessing successful: SNR={final_metrics.snr_estimate:.1f}dB")
                return processed_audio, final_metrics

            except Exception as e:
                self.logger.error(f"Audio preprocessing failed: {e}")
                # Return error metrics
                error_metrics = AudioMetrics(
                    sample_rate=sample_rate,
                    duration_seconds=len(audio_data) / sample_rate if len(audio_data) > 0 else 0.0,
                    channels=1,
                    bit_depth=32,
                    rms_level=0.0,
                    peak_level=0.0,
                    snr_estimate=0.0,
                    clipping_detected=True,
                    silence_ratio=1.0,
                    frequency_range_hz=(0.0, float(sample_rate / 2)),
                    security_flags=["preprocessing_failed"],
                )
                return None, error_metrics

    def enforce_voice_signal_security_boundary_from_file(
        self, file_path: str
    ) -> Tuple[Optional[np.ndarray], AudioMetrics]:
        """
        Process audio from file

        Args:
            file_path:  Path to audio file

        Returns:
            Tuple of (processed_audio, metrics)
        """
        try:
            # Read audio file
            sample_rate, audio_data = wavfile.read(file_path)

            # Process the audio
            return self.process_audio(audio_data, sample_rate)

        except Exception as e:
            self.logger.error(f"Failed to process audio file {file_path}: {e}")
            error_metrics = AudioMetrics(
                sample_rate=16000,
                duration_seconds=0.0,
                channels=1,
                bit_depth=32,
                rms_level=0.0,
                peak_level=0.0,
                snr_estimate=0.0,
                clipping_detected=True,
                silence_ratio=1.0,
                frequency_range_hz=(0.0, 8000.0),
                security_flags=["file_read_failed"],
            )
            return None, error_metrics

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get preprocessing statistics for monitoring"""
        with self._lock:
            return self._stats.copy()

    def reset_stats(self) -> None:
        """Reset processing statistics"""
        with self._lock:
            self._stats = {
                "total_processed": 0,
                "successful_processed": 0,
                "rejected_security": 0,
                "rejected_quality": 0,
                "average_snr": 0.0,
                "average_processing_time_ms": 0.0,
            }


# Alias for backward compatibility
AudioPreprocessor = VoiceSignalSecurityValidator

# Export public interface
__all__ = [
    "AudioFormat",
    "NoiseReductionLevel",
    "AudioMetrics",
    "PreprocessingConfig",
    "VoiceSignalSecurityValidator",
    "AudioPreprocessor",  # Alias
]
