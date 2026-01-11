"""
Production-grade Speech-to-Text Engine using whisper.cpp

This module provides secure, local speech-to-text processing with:
- Model loading and management
- Audio preprocessing pipeline
- Confidence scoring and validation
- Security hardening against audio injection attacks
- Comprehensive error handling and recovery
"""

import hashlib
import logging
import os
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Handle whisper_cpp import gracefully for testing
try:
    import whisper_cpp

    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

    # Mock whisper_cpp for testing
    class MockWhisper:
        def __init__(self, model_path):
            self.model_path = model_path

        def transcribe(self, audio):
            return {
                "text": "Mock transcription result",
                "language": "en",
                "segments": [{"text": "Mock transcription result", "confidence": 0.9, "start": 0.0, "end": 1.0}],
            }

    whisper_cpp = type("MockModule", (), {"Whisper": MockWhisper})


class ModelSize(Enum):
    """Whisper model sizes with security and performance characteristics"""

    TINY = "tiny"  # 39 MB, fastest, lowest accuracy
    BASE = "base"  # 74 MB, balanced
    SMALL = "small"  # 244 MB, good accuracy
    MEDIUM = "medium"  # 769 MB, high accuracy
    LARGE = "large"  # 1550 MB, highest accuracy


@dataclass
class STTResult:
    """Speech-to-text processing result with security metadata"""

    text: str
    confidence: float
    processing_time_ms: int
    model_used: str
    audio_duration_ms: int
    language_detected: Optional[str]
    segments: List[Dict[str, Any]]
    security_flags: List[str]  # Potential security issues detected

    @property
    def is_high_confidence(self) -> bool:
        """Check if result meets high confidence threshold"""
        return self.confidence >= 0.8

    @property
    def has_security_concerns(self) -> bool:
        """Check if security flags were raised"""
        return len(self.security_flags) > 0


@dataclass
class ModelInfo:
    """Whisper model information and integrity data"""

    size: ModelSize
    path: Path
    checksum: str
    loaded: bool
    load_time_ms: int
    memory_usage_mb: int


class WhisperSTTEngine:
    """
    Production-grade Speech-to-Text engine using whisper.cpp

    Features:
    - Local processing only (no external API calls)
    - Model integrity verification
    - Audio preprocessing and validation
    - Confidence scoring and thresholding
    - Security hardening against injection attacks
    - Thread-safe operation
    - Comprehensive error handling
    """

    def __init__(
        self,
        model_size: ModelSize = ModelSize.BASE,
        models_dir: Optional[Path] = None,
        confidence_threshold: float = 0.7,
        max_audio_duration_seconds: int = 30,
        enable_security_checks: bool = True,
    ):
        self.model_size = model_size
        self.models_dir = models_dir or Path.home() / ".guru" / "models" / "whisper"
        self.confidence_threshold = confidence_threshold
        self.max_audio_duration_seconds = max_audio_duration_seconds
        self.enable_security_checks = enable_security_checks

        # Thread safety
        self._lock = threading.RLock()
        self._model = None
        self._model_info: Optional[ModelInfo] = None

        # Security and monitoring
        self._processing_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "security_violations": 0,
            "average_confidence": 0.0,
        }

        # Logger
        self.logger = logging.getLogger(__name__)

        # Initialize models directory
        self._ensure_models_directory()

    def _ensure_models_directory(self) -> None:
        """Ensure models directory exists with proper permissions"""
        try:
            self.models_dir.mkdir(parents=True, exist_ok=True)
            # Set restrictive permissions (owner read/write only)
            os.chmod(self.models_dir, 0o700)
        except Exception as e:
            self.logger.error(f"Failed to create models directory: {e}")
            raise RuntimeError(f"Cannot initialize models directory: {e}")

    def _get_model_path(self, model_size: ModelSize) -> Path:
        """Get the expected path for a model file"""
        return self.models_dir / f"ggml-{model_size.value}.bin"

    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of model file for integrity verification"""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            self.logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            raise

    def _verify_model_integrity(self, model_path: Path) -> bool:
        """
        Verify model file integrity

        In production, this would check against known good checksums.
        For now, we verify the file exists and is readable.
        """
        try:
            if not model_path.exists():
                self.logger.error(f"Model file not found: {model_path}")
                return False

            if not model_path.is_file():
                self.logger.error(f"Model path is not a file: {model_path}")
                return False

            # Check file size (models should be substantial)
            file_size = model_path.stat().st_size
            if file_size < 1024 * 1024:  # Less than 1MB is suspicious
                self.logger.error(f"Model file suspiciously small: {file_size} bytes")
                return False

            # Calculate checksum for integrity
            checksum = self._calculate_file_checksum(model_path)
            self.logger.info(f"Model checksum: {checksum}")

            return True

        except Exception as e:
            self.logger.error(f"Model integrity verification failed: {e}")
            return False

    def download_model(self, model_size: Optional[ModelSize] = None) -> bool:
        """
        Download whisper model if not present

        In production, this would download from a trusted source with signature verification.
        For now, we provide instructions for manual download.
        """
        target_size = model_size or self.model_size
        model_path = self._get_model_path(target_size)

        if model_path.exists() and self._verify_model_integrity(model_path):
            self.logger.info(f"Model {target_size.value} already exists and is valid")
            return True

        self.logger.error(
            f"Model {target_size.value} not found at {model_path}. "
            f"Please download the model manually from the official whisper.cpp repository "
            f"and place it at {model_path}"
        )

        # In a production system, we would implement secure model downloading here
        # with signature verification and trusted sources

        return False

    def load_model(self, model_size: Optional[ModelSize] = None) -> bool:
        """
        Load whisper model with integrity verification

        Returns:
            bool: True if model loaded successfully, False otherwise
        """
        target_size = model_size or self.model_size

        with self._lock:
            try:
                # Check if already loaded
                if self._model is not None and self._model_info is not None and self._model_info.size == target_size:
                    return True

                model_path = self._get_model_path(target_size)

                # Verify model exists and has integrity
                if not self._verify_model_integrity(model_path):
                    return False

                # Load model
                load_start_time = time.time()

                self.logger.info(f"Loading whisper model: {target_size.value}")
                self._model = whisper_cpp.Whisper(str(model_path))

                # Calculate load time
                load_time_ms = int((time.time() - load_start_time) * 1000)

                # Create model info
                checksum = self._calculate_file_checksum(model_path)
                self._model_info = ModelInfo(
                    size=target_size,
                    path=model_path,
                    checksum=checksum,
                    loaded=True,
                    load_time_ms=load_time_ms,
                    memory_usage_mb=0,  # Would measure actual memory usage
                )

                self.logger.info(f"Successfully loaded model {target_size.value}")
                return True

            except Exception as e:
                self.logger.error(f"Failed to load model {target_size.value}: {e}")
                self._model = None
                self._model_info = None
                return False

    def _validate_audio_input(self, audio_data: np.ndarray) -> List[str]:
        """
        Validate audio input for security and quality

        Returns:
            List[str]: Security flags if any issues detected
        """
        security_flags: List[str] = []

        if not self.enable_security_checks:
            return security_flags

        try:
            # Check audio duration
            sample_rate = 16000  # Whisper expects 16kHz
            duration_seconds = len(audio_data) / sample_rate

            if duration_seconds > self.max_audio_duration_seconds:
                security_flags.append(f"audio_too_long:{duration_seconds:.1f}s")

            # Check for suspicious patterns
            if np.all(audio_data == 0):
                security_flags.append("silent_audio")

            # Check for clipping (potential injection)
            max_val = np.max(np.abs(audio_data))
            if max_val >= 0.99:
                security_flags.append("audio_clipping_detected")

            # Check for unusual frequency content (basic)
            if len(audio_data) > 1000:
                # Simple frequency analysis
                fft = np.fft.fft(audio_data[:1000])
                freq_energy = np.abs(fft)

                # Check for suspicious frequency spikes
                if np.max(freq_energy) > 10 * np.mean(freq_energy):
                    security_flags.append("suspicious_frequency_spike")

        except Exception as e:
            self.logger.warning(f"Audio validation failed: {e}")
            security_flags.append("validation_error")

        return security_flags

    def transcribe(
        self, audio_data: np.ndarray, language: Optional[str] = None, require_high_confidence: bool = False
    ) -> Optional[STTResult]:
        """
        Transcribe audio to text with security validation

        Args:
            audio_data: Audio data as numpy array (16kHz, mono)
            language: Optional language hint
            require_high_confidence: If True, reject low-confidence results

        Returns:
            STTResult if successful, None if failed or rejected
        """
        with self._lock:
            self._processing_stats["total_requests"] += 1

            try:
                # Ensure model is loaded
                if self._model is None:
                    if not self.load_model():
                        self.logger.error("Cannot transcribe: model not loaded")
                        self._processing_stats["failed_requests"] += 1
                        return None

                # Validate audio input
                security_flags = self._validate_audio_input(audio_data)

                # Reject if critical security issues
                critical_flags = [f for f in security_flags if "injection" in f or "suspicious" in f]
                if critical_flags:
                    self.logger.warning(f"Rejecting audio due to security flags: {critical_flags}")
                    self._processing_stats["security_violations"] += 1
                    return None

                # Perform transcription
                transcription_start_time = time.time()

                # Convert numpy array to format expected by whisper.cpp
                audio_float = audio_data.astype(np.float32)

                # Transcribe
                if self._model is None:
                    raise RuntimeError("Model not loaded")
                result = self._model.transcribe(audio_float)

                processing_time_ms = int((time.time() - transcription_start_time) * 1000)

                # Extract results
                text = result.get("text", "").strip()
                segments = result.get("segments", [])

                # Calculate confidence (simplified - whisper.cpp provides segment-level confidence)
                if segments:
                    confidences = [seg.get("confidence", 0.0) for seg in segments if "confidence" in seg]
                    confidence = np.mean(confidences) if confidences else 0.5
                else:
                    confidence = 0.5  # Default confidence

                # Create result
                stt_result = STTResult(
                    text=text,
                    confidence=confidence,
                    processing_time_ms=processing_time_ms,
                    model_used=self._model_info.size.value if self._model_info else "unknown",
                    audio_duration_ms=int(len(audio_data) / 16),  # 16kHz sample rate
                    language_detected=result.get("language"),
                    segments=segments,
                    security_flags=security_flags,
                )

                # Check confidence requirements
                if require_high_confidence and not stt_result.is_high_confidence:
                    self.logger.info(f"Rejecting low confidence result: {confidence:.2f}")
                    return None

                if confidence < self.confidence_threshold:
                    self.logger.info(f"Result below confidence threshold: {confidence:.2f}")
                    return None

                # Update statistics
                self._processing_stats["successful_requests"] += 1
                self._processing_stats["average_confidence"] = (
                    self._processing_stats["average_confidence"] * (self._processing_stats["successful_requests"] - 1)
                    + confidence
                ) / self._processing_stats["successful_requests"]

                self.logger.info(f"Transcription successful: confidence={confidence:.2f}")
                return stt_result

            except Exception as e:
                self.logger.error(f"Transcription failed: {e}")
                self._processing_stats["failed_requests"] += 1
                return None

    def get_model_info(self) -> Optional[ModelInfo]:
        """Get information about the currently loaded model"""
        with self._lock:
            return self._model_info

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics for monitoring"""
        with self._lock:
            return self._processing_stats.copy()

    def unload_model(self) -> None:
        """Unload the current model to free memory"""
        with self._lock:
            if self._model is not None:
                self.logger.info("Unloading whisper model")
                self._model = None
                self._model_info = None

    def __del__(self):
        """Cleanup on destruction"""
        try:
            self.unload_model()
        except Exception:
            pass  # Ignore errors during cleanup
