"""
TTS Service Compatibility Module

This module provides backward compatibility for imports expecting 'tts_service'.
All functionality is implemented in 'text_to_speech_service.py'.
"""

# Re-export all public symbols from the actual implementation
from .text_to_speech_service import (
    TTSPriority,
    SpeechRequest,
    TTSService,
    get_tts_service,
    speak,
)

__all__ = [
    "TTSPriority",
    "SpeechRequest", 
    "TTSService",
    "get_tts_service",
    "speak",
]