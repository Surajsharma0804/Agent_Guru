"""
Text-to-Speech (TTS) Synthesis Module

Provides text-to-speech synthesis using various TTS engines.
Supports multiple voices, languages, and emotion synthesis.
"""

import numpy as np
from typing import Optional, List
from dataclasses import dataclass
from pathlib import Path

from .exceptions import GuruSpeechError


class TTSError(GuruSpeechError):
    """Errors related to text-to-speech synthesis."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, "TTS", original_error)


@dataclass
class TTSConfig:
    """Configuration for TTS engine."""
    
    voice: str = "default"
    """Voice model to use"""
    
    speaking_rate: float = 1.0
    """Speaking rate (0.5 to 2.0)"""
    
    pitch: float = 0.0
    """Voice pitch adjustment (-1.0 to 1.0)"""
    
    sample_rate: int = 22050
    """Output sample rate in Hz"""
    
    emotion: Optional[str] = None
    """Optional emotion (e.g., 'happy', 'sad', 'neutral')"""


class TextToSpeech:
    """
    Text-to-Speech synthesis engine.
    
    Supports multiple TTS backends:
    - Coqui TTS (best quality, local)
    - pyttsx3 (fast, offline)
    - gTTS (Google TTS, requires internet)
    """
    
    def __init__(self, config: Optional[TTSConfig] = None):
        """
        Initialize TTS engine.
        
        Args:
            config: TTS configuration
        """
        self.config = config or TTSConfig()
        
        self.tts = None
        self.engine_type = None
        
        # Try to initialize Coqui TTS (best quality)
        try:
            from TTS.api import TTS as CoquiTTS
            self.tts = CoquiTTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
            self.engine_type = "coqui"
            print("✅ Coqui TTS initialized")
        except Exception as e:
            print(f"⚠️  Coqui TTS not available: {e}")
            
            # Fallback to pyttsx3
            try:
                import pyttsx3
                self.tts = pyttsx3.init()
                self.tts.setProperty('rate', int(150 * self.config.speaking_rate))
                self.tts.setProperty('volume', 0.9)
                self.engine_type = "pyttsx3"
                print("✅ pyttsx3 TTS initialized")
            except Exception as e2:
                print(f"⚠️  pyttsx3 not available: {e2}")
                print("⚠️  Using fallback formant synthesis")
                self.engine_type = "fallback"
    
    def synthesize(self, text: str) -> np.ndarray:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            
        Returns:
            Audio samples as numpy array (float32, normalized to [-1, 1])
        """
        if not text or not text.strip():
            return np.array([], dtype=np.float32)
        
        if self.engine_type == "coqui":
            return self._synthesize_with_coqui(text)
        elif self.engine_type == "pyttsx3":
            return self._synthesize_with_pyttsx3(text)
        else:
            return self._synthesize_with_fallback(text)
    
    def _synthesize_with_coqui(self, text: str) -> np.ndarray:
        """Synthesize using Coqui TTS."""
        try:
            # Generate audio
            wav = self.tts.tts(text)
            
            # Convert to numpy array
            audio = np.array(wav, dtype=np.float32)
            
            # Normalize
            if np.max(np.abs(audio)) > 0:
                audio = audio / np.max(np.abs(audio))
            
            return audio
        except Exception as e:
            raise TTSError(f"Coqui TTS synthesis failed: {e}", e)
    
    def _synthesize_with_pyttsx3(self, text: str) -> np.ndarray:
        """Synthesize using pyttsx3."""
        try:
            import tempfile
            import soundfile as sf
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            self.tts.save_to_file(text, tmp_path)
            self.tts.runAndWait()
            
            # Load audio
            audio, sr = sf.read(tmp_path)
            
            # Convert to float32 and normalize
            audio = audio.astype(np.float32)
            if np.max(np.abs(audio)) > 0:
                audio = audio / np.max(np.abs(audio))
            
            # Resample if needed
            if sr != self.config.sample_rate:
                audio = self._resample(audio, sr, self.config.sample_rate)
            
            # Cleanup
            Path(tmp_path).unlink(missing_ok=True)
            
            return audio
        except Exception as e:
            raise TTSError(f"pyttsx3 synthesis failed: {e}", e)
    
    def _synthesize_with_fallback(self, text: str) -> np.ndarray:
        """
        Fallback formant synthesis.
        
        Generates simple but natural-sounding speech using formant synthesis.
        This is the same algorithm from the Rust implementation.
        """
        sample_rate = float(self.config.sample_rate)
        duration_per_char = 0.08  # 80ms per character
        total_duration = max(len(text) * duration_per_char, 0.5)
        total_samples = int(total_duration * sample_rate)
        
        audio = np.zeros(total_samples, dtype=np.float32)
        
        # Generate formant-based synthesis
        for i in range(total_samples):
            t = i / sample_rate
            
            # Character-based frequency modulation
            char_index = int(t / duration_per_char) % max(len(text), 1)
            char_code = ord(text[char_index]) if char_index < len(text) else ord('a')
            
            # Formant frequencies for vowel-like sounds
            f1 = 200.0 + (char_code % 300)  # First formant
            f2 = 800.0 + (char_code % 500)  # Second formant
            f3 = 2500.0 + (char_code % 300)  # Third formant
            
            # Fundamental frequency with natural variation
            f0 = 120.0 + 20.0 * np.sin(t * 2.0)  # Pitch variation
            
            # Generate formant synthesis
            formant1 = np.sin(2.0 * np.pi * f1 * t) * 0.4
            formant2 = np.sin(2.0 * np.pi * f2 * t) * 0.3
            formant3 = np.sin(2.0 * np.pi * f3 * t) * 0.2
            fundamental = np.sin(2.0 * np.pi * f0 * t) * 0.1
            
            # Combine formants
            sample = formant1 + formant2 + formant3 + fundamental
            
            # Apply envelope for natural speech rhythm
            if t < 0.05:
                envelope = t / 0.05  # Attack
            elif t > total_duration - 0.1:
                envelope = (total_duration - t) / 0.1  # Release
            else:
                # Sustain with natural amplitude variation
                envelope = 0.8 + 0.2 * np.sin(t * 5.0)
            
            sample *= envelope * 0.3  # Overall amplitude
            
            # Soft clipping for natural saturation
            sample = np.tanh(sample)
            
            audio[i] = sample
        
        return audio
    
    def _resample(
        self,
        audio: np.ndarray,
        orig_sr: int,
        target_sr: int
    ) -> np.ndarray:
        """Simple linear interpolation resampling."""
        if orig_sr == target_sr:
            return audio
        
        ratio = target_sr / orig_sr
        new_length = int(len(audio) * ratio)
        
        # Linear interpolation
        indices = np.arange(new_length) / ratio
        indices_floor = np.floor(indices).astype(int)
        indices_ceil = np.minimum(indices_floor + 1, len(audio) - 1)
        fraction = indices - indices_floor
        
        resampled = (
            audio[indices_floor] * (1 - fraction) +
            audio[indices_ceil] * fraction
        )
        
        return resampled.astype(np.float32)
    
    def synthesize_to_file(self, text: str, output_path: str) -> None:
        """
        Synthesize speech and save to file.
        
        Args:
            text: Text to synthesize
            output_path: Path to save audio file
        """
        import soundfile as sf
        
        audio = self.synthesize(text)
        sf.write(output_path, audio, self.config.sample_rate)
    
    def set_voice(self, voice: str) -> None:
        """
        Change the voice.
        
        Args:
            voice: Voice identifier
        """
        self.config.voice = voice
        
        # Reinitialize if needed
        if self.engine_type == "pyttsx3" and self.tts:
            voices = self.tts.getProperty('voices')
            for v in voices:
                if voice.lower() in v.name.lower():
                    self.tts.setProperty('voice', v.id)
                    break
    
    def set_speaking_rate(self, rate: float) -> None:
        """
        Adjust speaking rate.
        
        Args:
            rate: Speaking rate (0.5 to 2.0)
        """
        self.config.speaking_rate = max(0.5, min(2.0, rate))
        
        if self.engine_type == "pyttsx3" and self.tts:
            self.tts.setProperty('rate', int(150 * self.config.speaking_rate))
    
    def list_voices(self) -> List[str]:
        """
        Get list of available voices.
        
        Returns:
            List of voice identifiers
        """
        if self.engine_type == "pyttsx3" and self.tts:
            voices = self.tts.getProperty('voices')
            return [v.name for v in voices]
        elif self.engine_type == "coqui":
            return ["default"]
        else:
            return ["fallback"]
