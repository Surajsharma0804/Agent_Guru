"""Exception classes for the speech engine."""


class GuruSpeechError(Exception):
    """Base exception for all speech engine errors."""


class AudioInputError(GuruSpeechError):
    """Error related to audio input."""


class AudioProcessingError(GuruSpeechError):
    """Error during audio processing."""


class WakeWordDetectionError(GuruSpeechError):
    """Error during wake word detection."""


class TranscriptionError(GuruSpeechError):
    """Error during speech-to-text transcription."""


class VoiceBiometricError(GuruSpeechError):
    """Error during voice biometric operations."""


class EmotionDetectionError(GuruSpeechError):
    """Error during emotion detection."""


class TTSError(GuruSpeechError):
    """Error during text-to-speech synthesis."""


class VoiceCloningError(GuruSpeechError):
    """Error during voice cloning operations."""


class CommandParsingError(GuruSpeechError):
    """Error during command parsing."""


class ContextManagementError(GuruSpeechError):
    """Error during conversation context management."""


class StreamingError(GuruSpeechError):
    """Error during audio streaming."""


class ModelLoadError(GuruSpeechError):
    """Error loading speech models."""


class ConfigurationError(GuruSpeechError):
    """Error in speech engine configuration."""
