"""
GURU Voice Processing Module

This module provides production-grade voice processing capabilities including:
- Local speech-to-text using whisper.cpp
- Voice fingerprinting and speaker identification
- Audio preprocessing and noise reduction
- Confidence scoring and validation
- Security-hardened audio processing pipeline

All audio processing occurs locally without external dependencies.
"""

from .audio_preprocessing import AudioPreprocessor
from .speaker_verification import SpeakerVerificationEngine
from .speech_to_text import WhisperSTTEngine
from .voice_pipeline import VoiceProcessingPipeline

__all__ = ["WhisperSTTEngine", "SpeakerVerificationEngine", "AudioPreprocessor", "VoiceProcessingPipeline"]
