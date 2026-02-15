"""
Wake Word Detection Module

Provides real-time wake word detection using Porcupine or Vosk.
Supports custom wake words with configurable sensitivity.
"""

import numpy as np
from typing import Optional, List, Callable
from dataclasses import dataclass
from datetime import datetime
import threading
import queue

from .exceptions import GuruSpeechError


class WakeWordError(GuruSpeechError):
    """Errors related to wake word detection."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, "WakeWord", original_error)


@dataclass
class WakeWordEvent:
    """Event triggered when a wake word is detected."""
    
    wake_word: str
    """The detected wake word"""
    
    confidence: float
    """Confidence score (0.0 to 1.0)"""
    
    timestamp: datetime
    """When the wake word was detected"""
    
    audio_segment: Optional[np.ndarray] = None
    """Optional audio segment containing the wake word"""


class WakeWordDetector:
    """
    Wake word detection engine.
    
    Supports multiple wake words with configurable sensitivity.
    Uses Porcupine (if available) or falls back to energy-based detection.
    """
    
    def __init__(
        self,
        wake_words: List[str] = None,
        sensitivity: float = 0.7,
        sample_rate: int = 16000
    ):
        """
        Initialize wake word detector.
        
        Args:
            wake_words: List of wake words to detect (e.g., ["guru", "maya"])
            sensitivity: Detection sensitivity (0.0 to 1.0)
            sample_rate: Audio sample rate in Hz
        """
        self.wake_words = wake_words or ["guru", "maya"]
        self.sensitivity = max(0.0, min(1.0, sensitivity))
        self.sample_rate = sample_rate
        
        self.porcupine = None
        self.use_porcupine = False
        
        # Try to initialize Porcupine
        try:
            import pvporcupine
            self.porcupine = pvporcupine.create(
                keywords=self.wake_words,
                sensitivities=[self.sensitivity] * len(self.wake_words)
            )
            self.use_porcupine = True
            print(f"✅ Porcupine wake word detection initialized for: {self.wake_words}")
        except (ImportError, Exception) as e:
            print(f"⚠️  Porcupine not available, using fallback detection: {e}")
            self.use_porcupine = False
        
        # Fallback: energy-based detection
        self.energy_threshold = 0.01
        self.detection_callback: Optional[Callable[[WakeWordEvent], None]] = None
    
    def set_sensitivity(self, sensitivity: float) -> None:
        """
        Adjust detection sensitivity.
        
        Args:
            sensitivity: New sensitivity value (0.0 to 1.0)
        """
        self.sensitivity = max(0.0, min(1.0, sensitivity))
        
        if self.use_porcupine and self.porcupine:
            # Recreate Porcupine with new sensitivity
            try:
                self.porcupine.delete()
                import pvporcupine
                self.porcupine = pvporcupine.create(
                    keywords=self.wake_words,
                    sensitivities=[self.sensitivity] * len(self.wake_words)
                )
            except Exception as e:
                raise WakeWordError(f"Failed to update sensitivity: {e}", e)
    
    def process_audio(self, audio_data: np.ndarray) -> Optional[WakeWordEvent]:
        """
        Process audio chunk for wake word detection.
        
        Args:
            audio_data: Audio samples as numpy array
            
        Returns:
            WakeWordEvent if wake word detected, None otherwise
        """
        if self.use_porcupine and self.porcupine:
            return self._process_with_porcupine(audio_data)
        else:
            return self._process_with_fallback(audio_data)
    
    def _process_with_porcupine(self, audio_data: np.ndarray) -> Optional[WakeWordEvent]:
        """Process audio using Porcupine."""
        try:
            # Convert to int16 for Porcupine
            audio_int16 = (audio_data * 32767).astype(np.int16)
            
            # Process frame
            keyword_index = self.porcupine.process(audio_int16)
            
            if keyword_index >= 0:
                return WakeWordEvent(
                    wake_word=self.wake_words[keyword_index],
                    confidence=self.sensitivity,
                    timestamp=datetime.now(),
                    audio_segment=audio_data
                )
            
            return None
        except Exception as e:
            raise WakeWordError(f"Porcupine processing failed: {e}", e)
    
    def _process_with_fallback(self, audio_data: np.ndarray) -> Optional[WakeWordEvent]:
        """
        Fallback energy-based detection.
        
        This is a simple energy threshold detector that triggers on loud sounds.
        In production, you'd want to use Porcupine or train a custom model.
        """
        # Calculate RMS energy
        energy = np.sqrt(np.mean(audio_data ** 2))
        
        if energy > self.energy_threshold:
            # Simple detection - in production, use proper wake word model
            return WakeWordEvent(
                wake_word=self.wake_words[0],
                confidence=min(energy / self.energy_threshold, 1.0),
                timestamp=datetime.now(),
                audio_segment=audio_data
            )
        
        return None
    
    def start_listening(
        self,
        callback: Callable[[WakeWordEvent], None],
        duration: Optional[float] = None
    ) -> None:
        """
        Start continuous wake word detection.
        
        Args:
            callback: Function to call when wake word is detected
            duration: Optional duration in seconds (None for continuous)
        """
        self.detection_callback = callback
        
        # This would integrate with audio capture in production
        # For now, it's a placeholder for the API
        raise NotImplementedError(
            "Continuous listening requires integration with audio capture. "
            "Use process_audio() in a loop instead."
        )
    
    def stop_listening(self) -> None:
        """Stop continuous wake word detection."""
        self.detection_callback = None
    
    def __del__(self):
        """Cleanup resources."""
        if self.porcupine:
            try:
                self.porcupine.delete()
            except:
                pass
