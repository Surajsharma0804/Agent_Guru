"""
GURU Voice Processing Module

Production-grade voice processing with whisper.cpp integration:
- Local speech-to-text using whisper.cpp subprocess
- Voice fingerprinting and speaker identification
- Audio preprocessing and noise reduction
- Confidence scoring and validation
- Security-hardened audio processing pipeline

whisper.cpp Integration:
- 100% local processing (no external APIs)
- Deterministic output (same audio → same text)
- No Python dependencies (pure C++ subprocess)
- Security boundaries enforced
- Process isolation

All audio processing occurs locally without external dependencies.
"""

# whisper.cpp integration (production-grade)
from .whisper_cpp_engine import (
    WhisperCppEngine,
    WhisperConfig,
    WhisperModel,
    TranscriptionResult,
    get_whisper_engine,
    initialize_whisper_engine
)

# Legacy components (backward compatibility)
from .audio_preprocessing import AudioPreprocessor
from .speaker_verification import SpeakerVerificationEngine
from .speech_to_text import WhisperSTTEngine
from .voice_pipeline import VoiceProcessingPipeline

__all__ = [
    # whisper.cpp (production)
    "WhisperCppEngine",
    "WhisperConfig",
    "WhisperModel",
    "TranscriptionResult",
    "get_whisper_engine",
    "initialize_whisper_engine",
    
    # Legacy components
    "WhisperSTTEngine",
    "SpeakerVerificationEngine",
    "AudioPreprocessor",
    "VoiceProcessingPipeline",
]

__version__ = "2.0.0"  # Updated for whisper.cpp integration
