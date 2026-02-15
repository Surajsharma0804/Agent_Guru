"""
Audio capture module for microphone and file input.

This module contains:
- AudioCapture base class
- MicrophoneCapture for real-time audio capture
- FileCapture for loading audio files
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
import numpy as np

from .exceptions import AudioCaptureError


class AudioCapture(ABC):
    """Base class for audio capture."""
    
    @abstractmethod
    def capture(self, duration: Optional[float] = None) -> Tuple[np.ndarray, int]:
        """
        Capture audio.
        
        Args:
            duration: Duration in seconds (None for continuous)
            
        Returns:
            Tuple of (audio_data, sample_rate)
            
        Raises:
            AudioCaptureError: If audio capture fails
        """
        pass


class FileCapture(AudioCapture):
    """Loads audio from files using soundfile."""
    
    def __init__(self, file_path: str):
        """
        Initialize FileCapture.
        
        Args:
            file_path: Path to audio file
        """
        self.file_path = file_path
    
    def capture(self, duration: Optional[float] = None) -> Tuple[np.ndarray, int]:
        """
        Load audio from file.
        
        Args:
            duration: Duration in seconds (ignored for file capture)
            
        Returns:
            Tuple of (audio_data, sample_rate)
            
        Raises:
            AudioCaptureError: If file loading fails
        """
        return self.load_file(self.file_path)
    
    def load_file(self, file_path: str) -> Tuple[np.ndarray, int]:
        """
        Load audio from file.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Tuple of (audio_data, sample_rate)
            
        Raises:
            AudioCaptureError: If file loading fails
        """
        try:
            import soundfile as sf
            
            audio_data, sample_rate = sf.read(file_path, dtype='float32')
            
            # Convert stereo to mono if needed
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)
            
            return audio_data, sample_rate
            
        except FileNotFoundError as e:
            raise AudioCaptureError(
                f"Audio file not found: {file_path}",
                original_error=e
            )
        except Exception as e:
            raise AudioCaptureError(
                f"Failed to load audio file: {file_path}",
                original_error=e
            )


class MicrophoneCapture(AudioCapture):
    """Captures audio from system microphone using sounddevice."""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1
    ):
        """
        Initialize microphone capture.
        
        Args:
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
        """
        self.sample_rate = sample_rate
        self.channels = channels
    
    def capture(self, duration: Optional[float] = None) -> Tuple[np.ndarray, int]:
        """
        Capture audio from microphone.
        
        Args:
            duration: Duration in seconds (None for continuous)
            
        Returns:
            Tuple of (audio_data, sample_rate)
            
        Raises:
            AudioCaptureError: If microphone capture fails
        """
        if duration is None:
            raise AudioCaptureError(
                "Duration must be specified for microphone capture"
            )
        
        try:
            import sounddevice as sd
            
            audio_data = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32'
            )
            sd.wait()  # Wait for recording to complete
            
            # Convert to 1D array if mono
            if self.channels == 1:
                audio_data = audio_data.flatten()
            
            return audio_data, self.sample_rate
            
        except Exception as e:
            raise AudioCaptureError(
                f"Failed to capture audio from microphone: {str(e)}",
                original_error=e
            )
