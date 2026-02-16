"""Wake word detection for dual personality system."""

import numpy as np
import librosa
from typing import Optional, List, Dict
from dataclasses import dataclass
import time

from ..models import WakeWordDetection, PersonalityType
from ..exceptions import GuruSpeechError


class WakeWordError(GuruSpeechError):
    """Wake word detection error."""
    pass


@dataclass
class WakeWordConfig:
    """Configuration for wake word detection."""
    wake_words: Dict[str, PersonalityType]
    sensitivity: float = 0.5  # 0.0-1.0
    sample_rate: int = 16000
    n_mfcc: int = 13
    hop_length: int = 512
    n_fft: int = 2048


class WakeWordDetector:
    """
    Detect wake words for dual personality system.
    
    Supports "Hey Guru" and "Hey Maya" detection with configurable sensitivity.
    Uses MFCC-based feature extraction for pattern matching.
    """
    
    def __init__(self, config: Optional[WakeWordConfig] = None):
        """
        Initialize wake word detector.
        
        Args:
            config: Wake word configuration (uses defaults if None)
        """
        if config is None:
            config = WakeWordConfig(
                wake_words={
                    "hey guru": PersonalityType.GURU,
                    "guru": PersonalityType.GURU,
                    "hey maya": PersonalityType.MAYA,
                    "maya": PersonalityType.MAYA,
                }
            )
        
        self.config = config
        self._wake_word_templates: Dict[str, np.ndarray] = {}
        self._initialize_templates()
    
    def _initialize_templates(self) -> None:
        """Initialize wake word templates with synthetic patterns."""
        # In a production system, these would be trained models
        # For now, we create synthetic templates based on expected patterns
        for wake_word in self.config.wake_words.keys():
            # Create a synthetic MFCC template
            # Each wake word gets a unique pattern
            template_length = len(wake_word.split()) * 10  # ~10 frames per word
            template = np.random.randn(self.config.n_mfcc, template_length)
            
            # Add some structure to make patterns distinguishable
            if "guru" in wake_word:
                # Lower frequency emphasis for male voice
                template[:5, :] *= 1.5
            elif "maya" in wake_word:
                # Higher frequency emphasis for female voice
                template[5:, :] *= 1.5
            
            self._wake_word_templates[wake_word] = template
    
    def _extract_mfcc(self, audio: np.ndarray) -> np.ndarray:
        """
        Extract MFCC features from audio.
        
        Args:
            audio: Audio data as numpy array
            
        Returns:
            MFCC features (n_mfcc x time_frames)
        """
        # Ensure audio is float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        # Normalize audio
        if np.max(np.abs(audio)) > 0:
            audio = audio / np.max(np.abs(audio))
        
        # Extract MFCC features
        mfcc = librosa.feature.mfcc(
            y=audio,
            sr=self.config.sample_rate,
            n_mfcc=self.config.n_mfcc,
            hop_length=self.config.hop_length,
            n_fft=self.config.n_fft
        )
        
        return mfcc
    
    def _compute_similarity(
        self,
        features: np.ndarray,
        template: np.ndarray
    ) -> float:
        """
        Compute similarity between features and template.
        
        Uses dynamic time warping (DTW) distance converted to similarity score.
        
        Args:
            features: MFCC features from audio
            template: Wake word template
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Check for zero variance (silence or constant signal)
        if np.std(features) < 0.01:
            return 0.0
        
        # Use DTW to compare sequences of different lengths
        # For simplicity, we'll use correlation-based matching
        
        # Pad or truncate features to match template length
        if features.shape[1] < template.shape[1]:
            # Pad with zeros
            pad_width = template.shape[1] - features.shape[1]
            features = np.pad(features, ((0, 0), (0, pad_width)), mode='constant')
        elif features.shape[1] > template.shape[1]:
            # Use sliding window to find best match
            best_corr = -np.inf
            for i in range(features.shape[1] - template.shape[1] + 1):
                window = features[:, i:i + template.shape[1]]
                # Normalize both window and template
                window_norm = (window - np.mean(window)) / (np.std(window) + 1e-8)
                template_norm = (template - np.mean(template)) / (np.std(template) + 1e-8)
                corr = np.corrcoef(window_norm.flatten(), template_norm.flatten())[0, 1]
                if not np.isnan(corr):
                    best_corr = max(best_corr, corr)
            
            # Convert correlation to similarity (0 to 1)
            # Apply stricter threshold by scaling down
            similarity = (best_corr + 1) / 2 * 0.8  # Scale down to reduce false positives
            return max(0.0, min(1.0, similarity))
        
        # Normalize features and template
        features_norm = (features - np.mean(features)) / (np.std(features) + 1e-8)
        template_norm = (template - np.mean(template)) / (np.std(template) + 1e-8)
        
        # Compute correlation
        corr = np.corrcoef(features_norm.flatten(), template_norm.flatten())[0, 1]
        
        # Handle NaN (can occur with constant signals)
        if np.isnan(corr):
            return 0.0
        
        # Convert correlation (-1 to 1) to similarity (0 to 1)
        # Apply stricter threshold by scaling down
        similarity = (corr + 1) / 2 * 0.8  # Scale down to reduce false positives
        
        return max(0.0, min(1.0, similarity))
    
    async def detect(self, audio: np.ndarray) -> Optional[WakeWordDetection]:
        """
        Detect wake word in audio chunk.
        
        Args:
            audio: Audio data as numpy array
            
        Returns:
            WakeWordDetection if detected, None otherwise
        """
        if len(audio) == 0:
            return None
        
        # Extract MFCC features
        try:
            features = self._extract_mfcc(audio)
        except Exception as e:
            raise WakeWordError(f"Failed to extract MFCC features: {e}")
        
        # Check each wake word
        best_match = None
        best_confidence = 0.0
        
        for wake_word, personality in self.config.wake_words.items():
            template = self._wake_word_templates[wake_word]
            similarity = self._compute_similarity(features, template)
            
            # Adjust confidence based on sensitivity
            # Higher sensitivity = lower threshold
            # Base threshold is 0.6 (more conservative)
            threshold = 0.6 - (self.config.sensitivity - 0.5) * 0.4
            
            if similarity > threshold and similarity > best_confidence:
                best_confidence = similarity
                best_match = (wake_word, personality)
        
        # Return detection if confidence exceeds threshold
        if best_match is not None:
            wake_word, personality = best_match
            return WakeWordDetection(
                wake_word=wake_word,
                personality=personality,
                confidence=best_confidence,
                timestamp=time.time(),
                audio_chunk=audio
            )
        
        return None
    
    def detect_sync(self, audio: np.ndarray) -> Optional[WakeWordDetection]:
        """
        Synchronous version of detect() for non-async contexts.
        
        Args:
            audio: Audio data as numpy array
            
        Returns:
            WakeWordDetection if detected, None otherwise
        """
        import asyncio
        return asyncio.run(self.detect(audio))
    
    async def add_wake_word(
        self,
        wake_word: str,
        personality: PersonalityType,
        template: Optional[np.ndarray] = None
    ) -> None:
        """
        Register a new wake word.
        
        Args:
            wake_word: Wake word phrase (lowercase)
            personality: Associated personality
            template: Optional MFCC template (generated if None)
        """
        wake_word = wake_word.lower()
        self.config.wake_words[wake_word] = personality
        
        if template is not None:
            self._wake_word_templates[wake_word] = template
        else:
            # Generate synthetic template
            template_length = len(wake_word.split()) * 10
            template = np.random.randn(self.config.n_mfcc, template_length)
            
            if personality == PersonalityType.GURU:
                template[:5, :] *= 1.5
            else:
                template[5:, :] *= 1.5
            
            self._wake_word_templates[wake_word] = template
    
    async def remove_wake_word(self, wake_word: str) -> None:
        """
        Unregister a wake word.
        
        Args:
            wake_word: Wake word phrase to remove
        """
        wake_word = wake_word.lower()
        if wake_word in self.config.wake_words:
            del self.config.wake_words[wake_word]
            del self._wake_word_templates[wake_word]
    
    def get_wake_words(self) -> List[str]:
        """
        Get list of registered wake words.
        
        Returns:
            List of wake word phrases
        """
        return list(self.config.wake_words.keys())
    
    def set_sensitivity(self, sensitivity: float) -> None:
        """
        Set detection sensitivity.
        
        Args:
            sensitivity: Sensitivity value (0.0 to 1.0)
                        Higher = more sensitive (more detections, more false positives)
                        Lower = less sensitive (fewer detections, fewer false positives)
        """
        if not 0.0 <= sensitivity <= 1.0:
            raise ValueError("Sensitivity must be between 0.0 and 1.0")
        
        self.config.sensitivity = sensitivity
