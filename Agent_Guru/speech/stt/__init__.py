"""Speech-to-text components."""

from .language_detector import LanguageDetector, Language, LanguageDetectionResult

# Lazy import to avoid torch dependency issues
def get_whisper_transcriber():
    from .whisper_stt import WhisperTranscriber
    return WhisperTranscriber

__all__ = ["LanguageDetector", "Language", "LanguageDetectionResult", "get_whisper_transcriber"]
