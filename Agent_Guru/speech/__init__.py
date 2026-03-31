"""
Agent Guru - Speech Engine

Provides dual-personality AI voice processing with:
- Wake word detection (Hey Guru / Hey Maya)
- Speech-to-text transcription (Whisper)
- Text-to-speech synthesis (Coqui TTS, personality-specific voices)
- Voice emotion detection
- Voice biometric authentication
- Command parsing
- Always-on background service (Windows / macOS / Linux / Android / iOS)

Quick start::

    from Agent_Guru.speech import SpeechEngine
    from Agent_Guru.speech.models import PersonalityType

    engine = SpeechEngine()
    engine.initialize()
    result = engine.transcribe(audio_array)
    print(result.text, result.language)
    engine.shutdown()
"""

__version__ = "0.1.0"
__status__ = "IMPLEMENTED"

from Agent_Guru.speech.engine import SpeechEngine
from Agent_Guru.speech.models import (
    CommandResult,
    EmotionResult,
    EmotionType,
    PersonalityType,
    TranscriptionResult,
    VoiceFeatures,
)

__all__ = [
    # Main facade
    "SpeechEngine",
    # Data models
    "TranscriptionResult",
    "EmotionResult",
    "EmotionType",
    "CommandResult",
    "VoiceFeatures",
    "PersonalityType",
]
