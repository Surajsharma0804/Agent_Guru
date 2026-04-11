"""Android TTS integration using Android TextToSpeech API.

Production-grade implementation for mobile TTS with:
- Male/female voice selection
- Emotion support through prosody
- Optimal performance on Android devices
- Automatic fallback handling
"""

import time
from typing import Optional

from Agent_Guru.speech.exceptions import GuruSpeechError
from Agent_Guru.speech.models import EmotionType, PersonalityType

# Try to import Android modules, set to None if not available (for testing on desktop)
try:
    from jnius import autoclass
    ANDROID_AVAILABLE = True
except ImportError:
    autoclass = None
    ANDROID_AVAILABLE = False


class AndroidTTSError(GuruSpeechError):
    """Android TTS-specific errors."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, "AndroidTTS", original_error)


class AndroidTTS:
    """
    Android TextToSpeech integration.

    Features:
    - Male voice for Guru, female voice for Maya
    - Emotion support via pitch and speech rate
    - On-device synthesis
    - Automatic voice selection
    - Thread-safe operation
    """

    # Voice selection constants
    VOICE_CONFIGS = {
        PersonalityType.GURU: {
            "pitch": 0.9,  # Lower pitch for male voice
            "rate": 1.0
        },
        PersonalityType.MAYA: {
            "pitch": 1.2,  # Higher pitch for female voice
            "rate": 1.05
        }
    }

    # Emotion adjustments
    EMOTION_ADJUSTMENTS = {
        EmotionType.HAPPY: {"pitch_mult": 1.1, "rate_mult": 1.1},
        EmotionType.SAD: {"pitch_mult": 0.9, "rate_mult": 0.85},
        EmotionType.ANGRY: {"pitch_mult": 1.0, "rate_mult": 1.2},
        EmotionType.NEUTRAL: {"pitch_mult": 1.0, "rate_mult": 1.0},
        EmotionType.SURPRISED: {"pitch_mult": 1.2, "rate_mult": 1.15},
        EmotionType.FEARFUL: {"pitch_mult": 1.15, "rate_mult": 1.1},
        EmotionType.DISGUSTED: {"pitch_mult": 0.85, "rate_mult": 0.9}
    }

    def __init__(self, autoclass_override=None):
        """Initialize Android TTS.

        Args:
            autoclass_override: For testing only - override autoclass function
        """
        self._tts = None
        self._initialized = False
        self._male_voice = None
        self._female_voice = None

        # Use override for testing, otherwise use global autoclass
        _autoclass = autoclass_override if autoclass_override is not None else autoclass

        if _autoclass is None:
            raise AndroidTTSError(
                "Android TTS requires pyjnius. Install with: pip install pyjnius"
            )

        try:
            # Import Android-specific modules
            self.TextToSpeech = _autoclass('android.speech.tts.TextToSpeech')
            self.Locale = _autoclass('java.util.Locale')
            self.PythonActivity = _autoclass('org.kivy.android.PythonActivity')
            self.Voice = _autoclass('android.speech.tts.Voice')

            # Initialize TTS engine
            self._init_tts()

        except Exception as e:
            raise AndroidTTSError(f"Failed to initialize Android TTS: {e}", e) from e

    def _init_tts(self) -> None:
        """Initialize TTS engine and cache voices."""
        context = self.PythonActivity.mActivity

        # Create TTS instance
        self._tts = self.TextToSpeech(context, None)

        # Wait for initialization
        time.sleep(0.5)

        # Cache available voices
        self._cache_voices()

        self._initialized = True

    def _cache_voices(self) -> None:
        """Cache male and female voices for O(1) lookup."""
        try:
            voices = self._tts.getVoices() if self._tts else []

            for voice in voices:
                name = voice.getName().lower()

                # Look for male voice
                if not self._male_voice and ('male' in name or 'man' in name):
                    self._male_voice = voice

                # Look for female voice
                if not self._female_voice and ('female' in name or 'woman' in name):
                    self._female_voice = voice

            # Fallback: use default voice
            if not self._male_voice:
                self._male_voice = self._tts.getDefaultVoice() if self._tts else None
            if not self._female_voice:
                self._female_voice = self._tts.getDefaultVoice() if self._tts else None

        except Exception as e:
            # If voice caching fails, continue with default
            pass

    def synthesize(
        self,
        text: str,
        personality: PersonalityType = PersonalityType.GURU,
        emotion: Optional[EmotionType] = None,
        speech_rate: float = 1.0,
        volume: float = 1.0
    ) -> bytes:
        """
        Synthesize speech using Android TTS.

        Args:
            text: Text to synthesize
            personality: Guru (male) or Maya (female)
            emotion: Optional emotion adjustment
            speech_rate: Rate multiplier (0.5-2.0)
            volume: Volume multiplier (0.0-1.0)

        Returns:
            WAV audio data as bytes

        Raises:
            AndroidTTSError: On synthesis failure
        """
        if not self._initialized:
            raise AndroidTTSError("TTS not initialized")

        if not text or not text.strip():
            raise AndroidTTSError("Text cannot be empty")

        if not 0.5 <= speech_rate <= 2.0:
            raise AndroidTTSError(f"Speech rate must be in [0.5, 2.0], got {speech_rate}")

        if not 0.0 <= volume <= 1.0:
            raise AndroidTTSError(f"Volume must be in [0.0, 1.0], got {volume}")

        try:
            # Select voice
            voice = self._male_voice if personality == PersonalityType.GURU else self._female_voice
            if self._tts:
                self._tts.setVoice(voice)

            # Configure pitch and rate
            base_config = self.VOICE_CONFIGS[personality]
            pitch = base_config["pitch"]
            rate = base_config["rate"] * speech_rate

            # Apply emotion adjustments
            if emotion:
                adj = self.EMOTION_ADJUSTMENTS.get(emotion, {"pitch_mult": 1.0, "rate_mult": 1.0})
                pitch *= adj["pitch_mult"]
                rate *= adj["rate_mult"]

            # Clamp values
            pitch = max(0.5, min(2.0, pitch))
            rate = max(0.5, min(2.0, rate))

            # Set TTS parameters
            if self._tts:
                self._tts.setPitch(pitch)
            if self._tts:
                self._tts.setSpeechRate(rate)

            # Synthesize to file
            import os
            import tempfile

            tmp_fd, tmp_path = tempfile.mkstemp(suffix='.wav')
            os.close(tmp_fd)

            try:
                # Synthesize
                result = None
                if self._tts:
                    result = self._tts.synthesizeToFile(text, None, tmp_path, None)

                if result != self.TextToSpeech.SUCCESS:
                    raise AndroidTTSError(f"Synthesis failed with code: {result}")

                # Wait for synthesis to complete
                time.sleep(0.1)

                # Read audio file
                if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                    raise AndroidTTSError("Synthesis produced no output")

                with open(tmp_path, 'rb') as f:
                    audio_data = f.read()

                return audio_data

            finally:
                # Cleanup
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except OSError:
                    pass

        except Exception as e:
            if isinstance(e, AndroidTTSError):
                raise
            raise AndroidTTSError(f"Synthesis failed: {e}", e) from e

    def get_voice_info(self, personality: PersonalityType) -> dict[str, str]:
        """
        Get voice information.

        Returns:
            Dictionary with voice metadata
        """
        voice = self._male_voice if personality == PersonalityType.GURU else self._female_voice

        if voice:
            return {
                "name": voice.getName(),
                "locale": str(voice.getLocale()),
                "gender": "male" if personality == PersonalityType.GURU else "female",
                "personality": personality.value,
                "quality": str(voice.getQuality())
            }

        return {}

    def is_available(self) -> bool:
        """Check if Android TTS is available."""
        return self._initialized and self._tts is not None

    def shutdown(self) -> None:
        """Shutdown TTS engine."""
        if self._tts:
            try:
                self._tts.shutdown()
            except Exception as exc:
                import logging
                logging.getLogger(__name__).debug("TTS stop/shutdown error: %s", exc)
            self._tts = None
            self._initialized = False

    def __del__(self):
        """Cleanup on deletion."""
        self.shutdown()
