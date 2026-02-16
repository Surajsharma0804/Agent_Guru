"""Exception classes for the speech engine."""


class GuruSpeechError(Exception):
    """Base exception for all speech engine errors."""
    pass


class AudioInputError(GuruSpeechError):
    """Error related to audio input."""
    pass


class AudioProcessingError(GuruSpeechError):
    """Error during audio processing."""
    pass


class WakeWordDetectionError(GuruSpeechError):
    """Error during wake word detection."""
    pass


class TranscriptionError(GuruSpeechError):
    """Error during speech-to-text transcription."""
    pass


class VoiceBiometricError(GuruSpeechError):
    """Error during voice biometric operations."""
    pass


class EmotionDetectionError(GuruSpeechError):
    """Error during emotion detection."""
    pass


class TTSError(GuruSpeechError):
    """Error during text-to-speech synthesis."""
    pass


class VoiceCloningError(GuruSpeechError):
    """Error during voice cloning operations."""
    pass


class CommandParsingError(GuruSpeechError):
    """Error during command parsing."""
    pass


class ContextManagementError(GuruSpeechError):
    """Error during conversation context management."""
    pass


class StreamingError(GuruSpeechError):
    """Error during audio streaming."""
    pass


class ModelLoadError(GuruSpeechError):
    """Error loading speech models."""
    pass


class ConfigurationError(GuruSpeechError):
    """Error in speech engine configuration."""
    pass
