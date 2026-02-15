"""
Exception classes for the Guru Speech Engine.

This module contains:
- GuruSpeechError base exception
- AudioCaptureError, ModelLoadError, TranscriptionError, CommandInterpretationError
"""

from typing import Optional


class GuruSpeechError(Exception):
    """Base exception for Guru Speech Engine."""
    
    def __init__(
        self,
        message: str,
        component: str,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize GuruSpeechError.
        
        Args:
            message: Error message
            component: Component where error occurred
            original_error: Original exception that caused this error
        """
        self.message = message
        self.component = component
        self.original_error = original_error
        super().__init__(self.format_message())
    
    def format_message(self) -> str:
        """
        Format error message with context.
        
        Returns:
            Formatted error message with component and original error info
        """
        msg = f"[{self.component}] {self.message}"
        if self.original_error:
            msg += f"\nCaused by: {type(self.original_error).__name__}: {str(self.original_error)}"
        return msg


class AudioCaptureError(GuruSpeechError):
    """Errors during audio capture."""
    
    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize AudioCaptureError.
        
        Args:
            message: Error message
            original_error: Original exception that caused this error
        """
        super().__init__(message, "AudioCapture", original_error)


class ModelLoadError(GuruSpeechError):
    """Errors during model loading."""
    
    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize ModelLoadError.
        
        Args:
            message: Error message
            original_error: Original exception that caused this error
        """
        super().__init__(message, "ModelLoad", original_error)


class TranscriptionError(GuruSpeechError):
    """Errors during transcription."""
    
    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize TranscriptionError.
        
        Args:
            message: Error message
            original_error: Original exception that caused this error
        """
        super().__init__(message, "Transcription", original_error)


class CommandInterpretationError(GuruSpeechError):
    """Errors during command interpretation."""
    
    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize CommandInterpretationError.
        
        Args:
            message: Error message
            original_error: Original exception that caused this error
        """
        super().__init__(message, "CommandInterpretation", original_error)
