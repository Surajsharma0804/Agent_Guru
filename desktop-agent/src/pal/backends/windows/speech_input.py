"""
Windows Speech Input Implementation.

Implements SpeechInput interface using Whisper.cpp for local speech recognition
on Windows 10/11.

IMPLEMENTATION NOTE:
This is a stub implementation. Full implementation will be completed in Task 1.2.

Validates: Requirements 37.4, 37.7
"""

from typing import Dict
from ...interfaces import SpeechInput, Transcription


class WindowsSpeechInput(SpeechInput):
    """
    Windows implementation of SpeechInput.
    
    Uses:
        - Whisper.cpp for local speech recognition
        - Background thread for continuous listening
        - Microphone calibration for noise
    
    Capabilities:
        - Local processing (no cloud)
        - Wake word detection
        - Continuous listening
    """
    
    def __init__(self):
        """Initialize Windows speech input."""
        # TODO: Initialize Whisper.cpp and audio capture
        pass
    
    def start_listening(self) -> None:
        """Start listening thread."""
        # TODO: Implement in Task 1.2
        raise NotImplementedError("WindowsSpeechInput.start_listening will be implemented in Task 1.2")
    
    def stop_listening(self) -> None:
        """Stop listening and cleanup."""
        # TODO: Implement in Task 1.2
        raise NotImplementedError("WindowsSpeechInput.stop_listening will be implemented in Task 1.2")
    
    def transcribe(self, audio_data: bytes) -> Transcription:
        """Transcribe audio using Whisper.cpp."""
        # TODO: Implement in Task 1.2
        raise NotImplementedError("WindowsSpeechInput.transcribe will be implemented in Task 1.2")
    
    def calibrate_microphone(self) -> float:
        """Calibrate for ambient noise."""
        # TODO: Implement in Task 1.2
        raise NotImplementedError("WindowsSpeechInput.calibrate_microphone will be implemented in Task 1.2")
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Return Windows speech input capabilities."""
        return {
            'has_local_processing': True,
            'requires_cloud': False,
            'supports_wake_word': True,
            'supports_continuous': True,
        }
