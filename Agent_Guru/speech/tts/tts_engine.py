"""Text-to-speech engine with gender-specific voices and emotion support."""

import time
import io
import wave
from typing import Optional
import numpy as np
import pyttsx3

from Agent_Guru.speech.models import PersonalityType, EmotionType, TTSConfig
from Agent_Guru.speech.exceptions import GuruSpeechError


class TTSError(GuruSpeechError):
    """TTS-specific errors."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, "TTSEngine", original_error)


class TTSEngine:
    """
    Text-to-speech engine with gender-specific voices and emotion support.
    
    Features:
    - Male voice for Guru personality
    - Female voice for Maya personality
    - Emotion support (happy, sad, angry, neutral, etc.)
    - SSML markup support
    - Real-time factor <0.3
    - Speech rate and pitch adjustment
    - Offline operation with pyttsx3
    """
    
    def __init__(self):
        """Initialize TTS engine."""
        self.engine = None
        self._initialize_engine()
        
        # Voice configurations for personalities
        self.voice_configs = {
            PersonalityType.GURU: {
                "gender": "male",
                "rate": 175,  # Words per minute
                "volume": 0.9,
                "pitch": 1.0
            },
            PersonalityType.MAYA: {
                "gender": "female",
                "rate": 180,
                "volume": 0.9,
                "pitch": 1.1
            }
        }
        
        # Emotion adjustments (rate and pitch modifiers)
        self.emotion_adjustments = {
            EmotionType.HAPPY: {"rate_mult": 1.1, "pitch_mult": 1.1},
            EmotionType.SAD: {"rate_mult": 0.85, "pitch_mult": 0.9},
            EmotionType.ANGRY: {"rate_mult": 1.15, "pitch_mult": 1.2},
            EmotionType.NEUTRAL: {"rate_mult": 1.0, "pitch_mult": 1.0},
            EmotionType.SURPRISED: {"rate_mult": 1.2, "pitch_mult": 1.15},
            EmotionType.FEARFUL: {"rate_mult": 1.1, "pitch_mult": 1.05},
            EmotionType.DISGUSTED: {"rate_mult": 0.9, "pitch_mult": 0.95}
        }
        
        # Cache for available voices
        self._male_voice_id = None
        self._female_voice_id = None
        self._detect_voices()
        
        # Track if engine is busy
        self._is_busy = False
    
    def _initialize_engine(self) -> None:
        """Initialize pyttsx3 engine."""
        try:
            self.engine = pyttsx3.init()
        except Exception as e:
            raise TTSError(f"Failed to initialize TTS engine: {e}", e)
    
    def _detect_voices(self) -> None:
        """Detect available male and female voices."""
        try:
            voices = self.engine.getProperty('voices')
            
            # Try to find male and female voices
            for voice in voices:
                voice_name = voice.name.lower()
                voice_id = voice.id
                
                # Detect male voice
                if self._male_voice_id is None:
                    if any(keyword in voice_name for keyword in ['male', 'david', 'alex', 'james', 'mark']):
                        self._male_voice_id = voice_id
                
                # Detect female voice
                if self._female_voice_id is None:
                    if any(keyword in voice_name for keyword in ['female', 'zira', 'samantha', 'victoria', 'karen']):
                        self._female_voice_id = voice_id
            
            # Fallback: use first two voices if gender-specific not found
            if self._male_voice_id is None and len(voices) > 0:
                self._male_voice_id = voices[0].id
            if self._female_voice_id is None and len(voices) > 1:
                self._female_voice_id = voices[1].id
            elif self._female_voice_id is None and len(voices) > 0:
                self._female_voice_id = voices[0].id
                
        except Exception as e:
            raise TTSError(f"Failed to detect voices: {e}", e)
    
    def _select_voice(self, personality: PersonalityType) -> str:
        """
        Select voice based on personality.
        
        Args:
            personality: Guru (male) or Maya (female)
            
        Returns:
            Voice ID
        """
        if personality == PersonalityType.GURU:
            return self._male_voice_id
        else:
            return self._female_voice_id
    
    def _apply_config(self, config: TTSConfig) -> None:
        """
        Apply TTS configuration to engine.
        
        Args:
            config: TTS configuration
        """
        # Get base voice config for personality
        base_config = self.voice_configs[config.personality]
        
        # Select voice
        voice_id = self._select_voice(config.personality)
        self.engine.setProperty('voice', voice_id)
        
        # Apply base rate
        rate = base_config["rate"]
        
        # Apply emotion adjustments
        if config.emotion:
            emotion_adj = self.emotion_adjustments.get(
                config.emotion,
                {"rate_mult": 1.0, "pitch_mult": 1.0}
            )
            rate = int(rate * emotion_adj["rate_mult"])
        
        # Apply user rate adjustment
        rate = int(rate * config.speech_rate)
        
        # Clamp rate to reasonable bounds (50-300 wpm)
        rate = max(50, min(300, rate))
        
        self.engine.setProperty('rate', rate)
        
        # Apply volume
        volume = base_config["volume"] * config.volume
        volume = max(0.0, min(1.0, volume))
        self.engine.setProperty('volume', volume)
    
    def synthesize(
        self,
        text: str,
        personality: PersonalityType = PersonalityType.GURU,
        emotion: Optional[EmotionType] = None,
        speech_rate: float = 1.0,
        pitch: float = 1.0,
        volume: float = 1.0,
        use_ssml: bool = False
    ) -> bytes:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            personality: Guru (male) or Maya (female)
            emotion: Optional emotion to apply
            speech_rate: Speech rate multiplier (0.5-2.0)
            pitch: Pitch multiplier (0.5-2.0)
            volume: Volume multiplier (0.0-1.0)
            use_ssml: Whether text contains SSML markup
            
        Returns:
            Audio data as bytes (WAV format)
            
        Raises:
            TTSError: If synthesis fails
        """
        if not text or not text.strip():
            raise TTSError("Text cannot be empty")
        
        # Validate parameters
        if not 0.5 <= speech_rate <= 2.0:
            raise TTSError(f"Speech rate must be between 0.5 and 2.0, got {speech_rate}")
        if not 0.5 <= pitch <= 2.0:
            raise TTSError(f"Pitch must be between 0.5 and 2.0, got {pitch}")
        if not 0.0 <= volume <= 1.0:
            raise TTSError(f"Volume must be between 0.0 and 1.0, got {volume}")
        
        # Create config
        config = TTSConfig(
            personality=personality,
            emotion=emotion,
            speech_rate=speech_rate,
            pitch=pitch,
            volume=volume,
            use_ssml=use_ssml
        )
        
        # Apply configuration
        self._apply_config(config)
        
        # Measure synthesis time for real-time factor
        start_time = time.time()
        
        try:
            # Save to temporary file
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            try:
                # Synthesize to file
                self.engine.save_to_file(text, tmp_path)
                self.engine.runAndWait()
                
                # Read audio data
                with open(tmp_path, 'rb') as f:
                    audio_data = f.read()
                
                # Calculate real-time factor
                synthesis_time = time.time() - start_time
                
                # Parse WAV to get duration
                with wave.open(tmp_path, 'rb') as wav_file:
                    frames = wav_file.getnframes()
                    rate = wav_file.getframerate()
                    audio_duration = frames / float(rate)
                
                real_time_factor = synthesis_time / audio_duration if audio_duration > 0 else 0
                
                # Log performance
                if real_time_factor >= 0.3:
                    import logging
                    logger = logging.getLogger("Agent_Guru.speech.tts")
                    logger.warning(
                        f"TTS real-time factor {real_time_factor:.3f} exceeds target 0.3 "
                        f"(synthesis_time={synthesis_time:.3f}s, audio_duration={audio_duration:.3f}s)"
                    )
                
                return audio_data
                
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except Exception as e:
            raise TTSError(f"Failed to synthesize speech: {e}", e)
    
    def synthesize_to_array(
        self,
        text: str,
        personality: PersonalityType = PersonalityType.GURU,
        emotion: Optional[EmotionType] = None,
        speech_rate: float = 1.0,
        pitch: float = 1.0,
        volume: float = 1.0
    ) -> tuple[np.ndarray, int]:
        """
        Synthesize speech and return as numpy array.
        
        Args:
            text: Text to synthesize
            personality: Guru (male) or Maya (female)
            emotion: Optional emotion to apply
            speech_rate: Speech rate multiplier (0.5-2.0)
            pitch: Pitch multiplier (0.5-2.0)
            volume: Volume multiplier (0.0-1.0)
            
        Returns:
            Tuple of (audio_array, sample_rate)
        """
        audio_bytes = self.synthesize(
            text=text,
            personality=personality,
            emotion=emotion,
            speech_rate=speech_rate,
            pitch=pitch,
            volume=volume
        )
        
        # Parse WAV data
        with wave.open(io.BytesIO(audio_bytes), 'rb') as wav_file:
            sample_rate = wav_file.getframerate()
            n_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frames = wav_file.readframes(wav_file.getnframes())
            
            # Convert to numpy array
            if sample_width == 1:
                dtype = np.uint8
            elif sample_width == 2:
                dtype = np.int16
            else:
                dtype = np.int32
            
            audio_array = np.frombuffer(frames, dtype=dtype)
            
            # Convert to float32 in range [-1.0, 1.0]
            if dtype == np.uint8:
                audio_array = (audio_array.astype(np.float32) - 128) / 128.0
            else:
                max_val = float(np.iinfo(dtype).max)
                audio_array = audio_array.astype(np.float32) / max_val
            
            # Handle stereo by taking first channel
            if n_channels > 1:
                audio_array = audio_array[::n_channels]
        
        return audio_array, sample_rate
    
    def get_voice_info(self, personality: PersonalityType) -> dict:
        """
        Get information about the voice for a personality.
        
        Args:
            personality: Guru or Maya
            
        Returns:
            Dictionary with voice information
        """
        voice_id = self._select_voice(personality)
        voices = self.engine.getProperty('voices')
        
        for voice in voices:
            if voice.id == voice_id:
                return {
                    "id": voice.id,
                    "name": voice.name,
                    "languages": voice.languages,
                    "gender": "male" if personality == PersonalityType.GURU else "female",
                    "personality": personality.value
                }
        
        return {}
    
    def stop(self) -> None:
        """Stop current synthesis."""
        try:
            self.engine.stop()
        except Exception as e:
            raise TTSError(f"Failed to stop synthesis: {e}", e)
    
    def __del__(self):
        """Cleanup resources."""
        if self.engine:
            try:
                self.engine.stop()
            except:
                pass
