"""
Noise reduction module for audio pre-processing.

This module contains:
- NoiseCleaner class for applying noise reduction using noisereduce library
"""

import numpy as np
import noisereduce as nr
import soundfile as sf
from typing import Optional

from .exceptions import GuruSpeechError


class NoiseCleaner:
    """
    Applies noise reduction to audio signals using noisereduce library.
    """
    
    def __init__(
        self,
        stationary: bool = True,
        prop_decrease: float = 1.0
    ):
        """
        Initialize noise cleaner.
        
        Args:
            stationary: Whether to use stationary noise reduction
            prop_decrease: Proportion of noise to reduce (0.0 to 1.0)
        """
        self.stationary = stationary
        self.prop_decrease = prop_decrease
    
    def clean(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> np.ndarray:
        """
        Apply noise reduction to audio.
        
        Args:
            audio_data: Raw audio as numpy array
            sample_rate: Sample rate in Hz
            
        Returns:
            Cleaned audio as numpy array
            
        Raises:
            GuruSpeechError: If noise reduction fails
        """
        try:
            # Apply noise reduction using noisereduce
            cleaned_audio = nr.reduce_noise(
                y=audio_data,
                sr=sample_rate,
                stationary=self.stationary,
                prop_decrease=self.prop_decrease
            )
            
            # Handle NaN/inf values that may occur with certain configurations
            # (e.g., silent audio with non-stationary mode)
            if not np.all(np.isfinite(cleaned_audio)):
                # If output contains NaN/inf, return the original audio
                # This ensures Whisper compatibility
                return audio_data.copy()
            
            return cleaned_audio
        except (ValueError, RuntimeError) as e:
            # Handle cases where noisereduce fails (e.g., audio too short, invalid parameters)
            # Return original audio to maintain Whisper compatibility
            return audio_data.copy()
        except Exception as e:
            raise GuruSpeechError(
                message=f"Failed to apply noise reduction: {str(e)}",
                component="NoiseCleaner",
                original_error=e
            )
    
    def clean_file(
        self,
        input_path: str,
        output_path: str
    ) -> None:
        """
        Clean audio file and save result.
        
        Args:
            input_path: Path to input audio file
            output_path: Path to save cleaned audio
            
        Raises:
            GuruSpeechError: If file processing fails
        """
        try:
            # Load audio file
            audio_data, sample_rate = sf.read(input_path)
            
            # Apply noise reduction
            cleaned_audio = self.clean(audio_data, sample_rate)
            
            # Save cleaned audio
            sf.write(output_path, cleaned_audio, sample_rate)
        except GuruSpeechError:
            # Re-raise GuruSpeechError as-is
            raise
        except Exception as e:
            raise GuruSpeechError(
                message=f"Failed to process audio file '{input_path}': {str(e)}",
                component="NoiseCleaner",
                original_error=e
            )
