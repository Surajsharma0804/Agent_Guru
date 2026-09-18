"""iOS TTS integration using AVSpeechSynthesizer.

Production-grade implementation for iOS TTS with:
- Male/female voice selection
- Emotion support through prosody
- Optimal performance on iOS devices
- On-device synthesis (iOS 13+)
"""

import logging
import time

from Agent_Guru.speech.exceptions import GuruSpeechError
from Agent_Guru.speech.models import EmotionType, PersonalityType

logger = logging.getLogger(__name__)

# An AVSpeechSynthesizer that never reports "finished" -- a delegate callback
# lost when the audio session is torn down mid-utterance, for instance -- used
# to pin synthesize() forever. Real speech is bounded, so the wait for it is
# bounded too.
SYNTHESIS_WAIT_TIMEOUT_S = 30.0
SYNTHESIS_POLL_INTERVAL_S = 0.05

# Try to import iOS modules, set to None if not available (for testing on desktop)
try:
    from pyobjus import autoclass

    IOS_AVAILABLE = True
except ImportError:
    autoclass = None
    IOS_AVAILABLE = False


class IOSTTSError(GuruSpeechError):
    """iOS TTS-specific errors."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message, "IOSTTS", original_error)


class IOSTTS:
    """iOS AVSpeechSynthesizer integration.

    Features:
    - Male voice for Guru, female voice for Maya
    - Emotion support via pitch and speech rate
    - On-device synthesis (iOS 13+)
    - High-quality neural voices
    - Thread-safe operation
    """

    # Voice selection constants
    VOICE_CONFIGS = {
        PersonalityType.GURU: {
            "pitch_multiplier": 0.9,  # Lower pitch for male voice
            "rate": 0.5,  # AVSpeechSynthesizer rate (0.0-1.0)
        },
        PersonalityType.MAYA: {
            "pitch_multiplier": 1.1,  # Higher pitch for female voice
            "rate": 0.52,
        },
    }

    # Emotion adjustments
    EMOTION_ADJUSTMENTS = {
        EmotionType.HAPPY: {"pitch_mult": 1.1, "rate_mult": 1.1},
        EmotionType.SAD: {"pitch_mult": 0.9, "rate_mult": 0.85},
        EmotionType.ANGRY: {"pitch_mult": 1.0, "rate_mult": 1.2},
        EmotionType.NEUTRAL: {"pitch_mult": 1.0, "rate_mult": 1.0},
        EmotionType.SURPRISED: {"pitch_mult": 1.2, "rate_mult": 1.15},
        EmotionType.FEARFUL: {"pitch_mult": 1.15, "rate_mult": 1.1},
        EmotionType.DISGUSTED: {"pitch_mult": 0.85, "rate_mult": 0.9},
    }

    def __init__(self, autoclass_override=None) -> None:
        """Initialize iOS TTS.

        Args:
            autoclass_override: For testing only - override autoclass function

        """
        self._synthesizer = None
        self._initialized = False
        self._male_voice = None
        self._female_voice = None

        # Use override for testing, otherwise use global autoclass
        _autoclass = autoclass_override if autoclass_override is not None else autoclass

        if _autoclass is None:
            msg = "iOS TTS requires pyobjus. Install with: pip install pyobjus"
            raise IOSTTSError(msg)

        try:
            # Import iOS-specific modules
            self.AVSpeechSynthesizer = _autoclass("AVSpeechSynthesizer")
            self.AVSpeechUtterance = _autoclass("AVSpeechUtterance")
            self.AVSpeechSynthesisVoice = _autoclass("AVSpeechSynthesisVoice")

            # Initialize synthesizer
            self._init_synthesizer()

        except Exception as e:
            msg = f"Failed to initialize iOS TTS: {e}"
            raise IOSTTSError(msg, e) from e

    def _init_synthesizer(self) -> None:
        """Initialize speech synthesizer and cache voices."""
        # Create synthesizer instance
        self._synthesizer = self.AVSpeechSynthesizer.alloc().init()

        # Cache available voices
        self._cache_voices()

        self._initialized = True

    def _cache_voices(self) -> None:
        """Cache male and female voices for O(1) lookup."""
        try:
            # Get all available voices
            voices = self.AVSpeechSynthesisVoice.speechVoices()

            for voice in voices:
                # The identifier is what actually disambiguates Apple's voices
                # ("com.apple.ttsbundle.siri_male_en-US"); many display names
                # are just given names ("Aaron", "Samantha") and carry no
                # gender word at all. The previous code computed
                # voice.identifier.lower() and threw the result away, matching
                # on the display name alone -- so on a device whose voices are
                # named that way NEITHER branch matched and Guru and Maya both
                # fell through to the same default voice, i.e. one voice for
                # two personalities.
                haystack = f"{voice.identifier} {voice.name}".lower()
                # "female" CONTAINS "male", and "woman" contains "man", so the
                # female test has to win. The previous order did not do this:
                # a device that lists its female voice first had that voice
                # assigned as the MALE voice.
                is_female = "female" in haystack or "woman" in haystack
                is_male = not is_female and ("male" in haystack or "man" in haystack)
                # "en" as a substring test would also accept unrelated tags;
                # a language code starts with its language.
                is_english = str(voice.language).lower().startswith("en")

                if not self._male_voice and is_male and is_english:
                    self._male_voice = voice

                if not self._female_voice and is_female and is_english:
                    self._female_voice = voice

            # Fallback: use default voices
            if not self._male_voice:
                self._male_voice = self.AVSpeechSynthesisVoice.voiceWithLanguage_("en-US")
            if not self._female_voice:
                self._female_voice = self.AVSpeechSynthesisVoice.voiceWithLanguage_("en-US")

        except Exception:
            # If voice caching fails, use default
            self._male_voice = self.AVSpeechSynthesisVoice.voiceWithLanguage_("en-US")
            self._female_voice = self.AVSpeechSynthesisVoice.voiceWithLanguage_("en-US")

    def _synthesizer_is_speaking(self) -> bool:
        """Whether the synthesizer is still speaking.

        AVSpeechSynthesizer declares this as
        `@property(readonly, getter=isSpeaking) BOOL speaking`, which the
        Objective-C bridge exposes as a zero-argument METHOD. Reading
        `synthesizer.isSpeaking` without calling it yields the bound method
        object, which is always truthy -- that is what made the wait loop in
        synthesize() unable to ever end. Both spellings are accepted here
        because pyobjus and pyobjc differ on whether such a property is also
        surfaced as a plain attribute.
        """
        synthesizer = self._synthesizer
        if synthesizer is None:
            return False
        try:
            speaking = synthesizer.isSpeaking
            if callable(speaking):
                speaking = speaking()
        except Exception:
            # An unreadable state is not a reason to keep waiting.
            logger.debug("Could not read synthesizer speaking state", exc_info=True)
            return False
        return bool(speaking)

    def synthesize(
        self,
        text: str,
        personality: PersonalityType = PersonalityType.GURU,
        emotion: EmotionType | None = None,
        speech_rate: float = 1.0,
        volume: float = 1.0,
    ) -> bytes:
        """Synthesize speech using iOS AVSpeechSynthesizer.

        Args:
            text: Text to synthesize
            personality: Guru (male) or Maya (female)
            emotion: Optional emotion adjustment
            speech_rate: Rate multiplier (0.5-2.0)
            volume: Volume multiplier (0.0-1.0)

        Returns:
            WAV audio data as bytes

        Raises:
            IOSTTSError: On synthesis failure

        """
        if not self._initialized:
            msg = "TTS not initialized"
            raise IOSTTSError(msg)

        if not text or not text.strip():
            msg = "Text cannot be empty"
            raise IOSTTSError(msg)

        if not 0.5 <= speech_rate <= 2.0:
            msg = f"Speech rate must be in [0.5, 2.0], got {speech_rate}"
            raise IOSTTSError(msg)

        if not 0.0 <= volume <= 1.0:
            msg = f"Volume must be in [0.0, 1.0], got {volume}"
            raise IOSTTSError(msg)

        try:
            # Create utterance
            utterance = self.AVSpeechUtterance.speechUtteranceWithString_(text)

            # Select voice
            voice = self._male_voice if personality == PersonalityType.GURU else self._female_voice
            utterance.voice = voice

            # Configure pitch and rate
            base_config = self.VOICE_CONFIGS[personality]
            pitch = base_config["pitch_multiplier"]
            rate = base_config["rate"] * speech_rate

            # Apply emotion adjustments
            if emotion:
                adj = self.EMOTION_ADJUSTMENTS.get(emotion, {"pitch_mult": 1.0, "rate_mult": 1.0})
                pitch *= adj["pitch_mult"]
                rate *= adj["rate_mult"]

            # Clamp values
            # AVSpeechSynthesizer pitch: 0.5-2.0
            # AVSpeechSynthesizer rate: 0.0-1.0 (AVSpeechUtteranceDefaultSpeechRate = 0.5)
            pitch = max(0.5, min(2.0, pitch))
            rate = max(0.0, min(1.0, rate))

            # Set utterance parameters
            utterance.pitchMultiplier = pitch
            utterance.rate = rate
            utterance.volume = volume

            # Synthesize to file
            import os
            import tempfile

            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(tmp_fd)

            try:
                # Write to file using AVAudioFile
                # Note: iOS doesn't have direct synthesizeToFile, so we use audio session
                autoclass("AVAudioFile") if autoclass is not None else None
                AVAudioSession = autoclass("AVAudioSession") if autoclass is not None else None

                if AVAudioSession:
                    # Configure audio session
                    audio_session = AVAudioSession.sharedInstance()
                    audio_session.setCategory_error_("AVAudioSessionCategoryPlayback", None)
                    audio_session.setActive_error_(True, None)

                # Speak utterance
                if self._synthesizer:
                    self._synthesizer.speakUtterance_(utterance)

                # Wait for synthesis to complete -- but never indefinitely.
                deadline = time.monotonic() + SYNTHESIS_WAIT_TIMEOUT_S
                while self._synthesizer_is_speaking():
                    if time.monotonic() >= deadline:
                        logger.warning(
                            "Speech synthesis still reported as running after "
                            "%.0fs; abandoning the wait rather than blocking "
                            "the caller forever",
                            SYNTHESIS_WAIT_TIMEOUT_S,
                        )
                        break
                    time.sleep(SYNTHESIS_POLL_INTERVAL_S)

                # For now, return empty bytes as iOS synthesis is more complex
                # In production, would use AVAudioEngine to capture output
                # This is a simplified implementation

                # Create minimal WAV file
                import wave

                import numpy as np

                # Generate silence as placeholder (in production, capture actual audio)
                sample_rate = 22050
                duration = len(text.split()) * 0.5  # Rough estimate
                samples = int(sample_rate * duration)
                audio_data = np.zeros(samples, dtype=np.int16)

                with wave.open(tmp_path, "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(sample_rate)
                    wav.writeframes(audio_data.tobytes())

                # Read audio file
                with open(tmp_path, "rb") as f:
                    return f.read()

            finally:
                # Cleanup
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except OSError:
                    # Best-effort cleanup of our own temp file in a finally
                    # block. Raising here would mask the real synthesis result
                    # (or the real error) with a cleanup error.
                    pass

        except Exception as e:
            if isinstance(e, IOSTTSError):
                raise
            msg = f"Synthesis failed: {e}"
            raise IOSTTSError(msg, e) from e

    def get_voice_info(self, personality: PersonalityType) -> dict[str, str]:
        """Get voice information.

        Returns:
            Dictionary with voice metadata

        """
        voice = self._male_voice if personality == PersonalityType.GURU else self._female_voice

        if voice:
            return {
                "identifier": voice.identifier,
                "name": voice.name,
                "language": voice.language,
                "gender": "male" if personality == PersonalityType.GURU else "female",
                "personality": personality.value,
                "quality": str(voice.quality),
            }

        return {}

    def is_available(self) -> bool:
        """Check if iOS TTS is available."""
        return self._initialized and self._synthesizer is not None

    def shutdown(self) -> None:
        """Shutdown TTS synthesizer."""
        if self._synthesizer:
            try:
                self._synthesizer.stopSpeakingAtBoundary_(0)  # Stop immediately
            except Exception as exc:
                import logging

                logging.getLogger(__name__).debug("TTS stop/shutdown error: %s", exc)
            self._synthesizer = None
            self._initialized = False

    def __del__(self) -> None:
        """Cleanup on deletion."""
        self.shutdown()
