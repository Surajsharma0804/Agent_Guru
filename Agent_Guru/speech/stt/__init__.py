"""Speech-to-text components."""

from .language_detector import Language, LanguageDetectionResult, LanguageDetector


# Lazy import to avoid torch dependency issues
def get_whisper_transcriber():
    from .whisper_stt import WhisperTranscriber

    return WhisperTranscriber


__all__ = ["Language", "LanguageDetectionResult", "LanguageDetector", "get_whisper_transcriber"]
