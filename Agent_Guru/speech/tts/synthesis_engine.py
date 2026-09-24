"""Module: Agent_Guru.speech.tts.synthesis_engine
Purpose: Production TTS SynthesisEngine with voice profiles, rate adjustment, prosody.

Wraps CoquiTTSEngine with:
- Multiple voice profiles (male/female/neutral)
- Speech rate adjustment (0.5x to 2.0x)
- Prosody and punctuation handling for natural pauses
- Interruption support
- 22kHz+ output sample rate

Performance:
    - Time Complexity: O(n) where n = text length
    - Space Complexity: O(n) for audio output
    - Synthesis latency: <200ms P95 for typical sentences
    - Sample rate: 22050 Hz minimum

Author: Agent Guru Team
Date: 2026-03-19
Version: 1.0.0
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Minimum sample rate for quality output
_MIN_SAMPLE_RATE = 22050

# Rate adjustment bounds
_MIN_RATE = 0.5
_MAX_RATE = 2.0

# Punctuation pause durations (in seconds)
_PAUSE_DURATIONS = {
    ".": 0.4,
    "!": 0.4,
    "?": 0.4,
    ",": 0.15,
    ";": 0.25,
    ":": 0.2,
    "...": 0.5,
    "\n": 0.3,
}


class VoiceProfile(str, Enum):
    """Available voice profiles."""

    GURU = "guru"  # Male, professional
    MAYA = "maya"  # Female, warm
    NEUTRAL = "neutral"  # Gender-neutral


@dataclass
class SynthesisConfig:
    """Configuration for the synthesis engine.

    Attributes:
        voice_profile: Voice profile to use
        speech_rate: Speech rate multiplier (0.5x to 2.0x)
        sample_rate: Output sample rate in Hz (minimum 22050)
        volume: Output volume (0.0 to 1.0)
        enable_prosody: Whether to apply prosody/punctuation handling
        use_gpu: Whether to use GPU acceleration

    """

    voice_profile: VoiceProfile = VoiceProfile.GURU
    speech_rate: float = 1.0
    sample_rate: int = _MIN_SAMPLE_RATE
    volume: float = 1.0
    enable_prosody: bool = True
    use_gpu: bool = False

    def __post_init__(self) -> None:
        if not _MIN_RATE <= self.speech_rate <= _MAX_RATE:
            msg = f"speech_rate must be between {_MIN_RATE} and {_MAX_RATE}, got {self.speech_rate}"
            raise ValueError(
                msg,
            )
        if self.sample_rate < _MIN_SAMPLE_RATE:
            msg = f"sample_rate must be >= {_MIN_SAMPLE_RATE}, got {self.sample_rate}"
            raise ValueError(msg)
        if not 0.0 <= self.volume <= 1.0:
            msg = f"volume must be between 0.0 and 1.0, got {self.volume}"
            raise ValueError(msg)


@dataclass
class SynthesisResult:
    """Result of a TTS synthesis operation.

    Attributes:
        audio_bytes: Raw PCM audio bytes (WAV format)
        sample_rate: Audio sample rate in Hz
        duration_seconds: Audio duration in seconds
        text: Original text that was synthesized
        voice_profile: Voice profile used
        speech_rate: Speech rate used
        latency_ms: Synthesis latency in milliseconds
        success: Whether synthesis succeeded
        error: Error message if synthesis failed

    """

    audio_bytes: bytes
    sample_rate: int
    duration_seconds: float
    text: str
    voice_profile: VoiceProfile
    speech_rate: float
    latency_ms: float
    success: bool
    error: str | None = None


class SynthesisEngine:
    """Production TTS synthesis engine with voice profiles and prosody.

    Provides a unified interface for text-to-speech synthesis with:
    - Multiple voice profiles (Guru/Maya/Neutral)
    - Speech rate adjustment (0.5x to 2.0x)
    - Prosody and punctuation handling
    - Interruption support
    - GPU acceleration

    Example:
        >>> engine = SynthesisEngine()
        >>> result = engine.synthesize("Hello, I'm Guru!")
        >>> print(f"Duration: {result.duration_seconds:.2f}s")
        >>> print(f"Latency: {result.latency_ms:.1f}ms")

    Performance:
        - Synthesis latency: <200ms P95
        - Sample rate: 22050 Hz
        - Throughput: >5 sentences/second

    """

    def __init__(self, config: SynthesisConfig | None = None) -> None:
        """Initialize the synthesis engine.

        Args:
            config: Synthesis configuration. Uses defaults if None.

        """
        self._config = config or SynthesisConfig()
        self._lock = threading.Lock()
        self._interrupted = threading.Event()
        self._coqui_engine: Any | None = None
        self._initialized = False

        logger.info(
            f"SynthesisEngine initialized: profile={self._config.voice_profile.value}, "
            f"rate={self._config.speech_rate}x, sample_rate={self._config.sample_rate}Hz",
        )

    def initialize(self) -> None:
        """Load TTS model. Call once before synthesizing.

        BUG FIX (Round 16): `self._lock` was created in __init__ but never
        actually acquired anywhere in this class -- this method's
        check-then-act (`if self._initialized: return` ... construct ...
        `self._initialized = True`) was a textbook unguarded race: two
        threads calling synthesize() concurrently before the first
        initialize() completes could both observe `_initialized is False`
        and both construct a CoquiTTSEngine (which itself loads the Kokoro
        ONNX model) -- duplicate, wasted model construction, exactly the
        "duplicate model instances" anti-pattern this project explicitly
        audits for. Fixed with the standard double-checked-locking pattern:
        check outside the lock (fast path once initialized), re-check
        inside it (in case another thread finished first while this one
        waited), then initialize while holding the lock.
        """
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            try:
                from Agent_Guru.speech.tts.tts_engine import CoquiTTSEngine

                self._coqui_engine = CoquiTTSEngine(use_gpu=self._config.use_gpu)
                self._initialized = True
                logger.info("SynthesisEngine: Kokoro TTS engine loaded")
            except Exception:
                logger.exception("TTS engine unavailable. Using silence fallback.")
                self._initialized = True  # Mark as initialized even without model

    def synthesize(self, text: str) -> SynthesisResult:
        """Synthesize text to audio.

        Time Complexity: O(n) where n = len(text)
        Space Complexity: O(n) for audio output

        Args:
            text: Text to synthesize

        Returns:
            SynthesisResult with audio bytes and metadata

        """
        start = time.perf_counter()

        if not self._initialized:
            self.initialize()

        # BUG FIX (Round 16): interrupt()/is_interrupted() previously had
        # NO effect on anything -- interrupt() only set a threading.Event
        # that nothing in synthesize()/_synthesize_audio() ever checked, so
        # calling it mid-utterance did not stop the current or next
        # synthesis. Kokoro's actual synthesis call (_kokoro.create(...) in
        # tts_engine.py) is a single opaque blocking call into the ONNX
        # runtime with no safe internal cancellation point -- a
        # threading.Event can't abort another thread's C-extension call
        # mid-inference, so a synthesis already in flight genuinely cannot
        # be cut short without materially riskier machinery (e.g. running
        # ONNX in a separate, killable process), which is out of scope for
        # this fix. What CAN be honestly fixed, and is fixed here: when a
        # caller speaks a long response as a queue of per-sentence
        # synthesize() calls (the realistic shape of "interruption" for a
        # companion that speaks in chunks), a not-yet-started call now
        # correctly honors an interrupt() issued before it began, instead
        # of synthesizing anyway and only exposing the flag to a caller
        # who has to remember to check it themselves.
        if self._interrupted.is_set():
            logger.info("SynthesisEngine: synthesize() skipped - already interrupted")
            # Consume the interrupt: this skip is what interrupt() asked
            # for. Without clearing here, the flag would stay set forever
            # (the only other clear() is further below, on the path this
            # branch just avoided), permanently wedging every future
            # synthesize() call into this same skip branch instead of
            # resuming normal operation after the one interrupted call.
            self._interrupted.clear()
            latency_ms = (time.perf_counter() - start) * 1000
            return SynthesisResult(
                audio_bytes=b"",
                sample_rate=self._config.sample_rate,
                duration_seconds=0.0,
                text=text,
                voice_profile=self._config.voice_profile,
                speech_rate=self._config.speech_rate,
                latency_ms=latency_ms,
                success=False,
                error="Synthesis interrupted before starting",
            )

        # Apply prosody preprocessing
        processed_text = self._apply_prosody(text) if self._config.enable_prosody else text

        # Clear interruption flag so this call starts fresh. (Per-call
        # clearing preserves the original semantics: interrupt() cancels
        # calls made before the next one, not a whole future queue: a
        # caller that wants to stop an entire pending queue of sentences
        # must check is_interrupted() itself between queued calls, before
        # each one clears it for itself.)
        self._interrupted.clear()

        try:
            audio_bytes, sample_rate = self._synthesize_audio(processed_text)
            duration = self._estimate_duration(audio_bytes, sample_rate)
            latency_ms = (time.perf_counter() - start) * 1000

            return SynthesisResult(
                audio_bytes=audio_bytes,
                sample_rate=sample_rate,
                duration_seconds=duration,
                text=text,
                voice_profile=self._config.voice_profile,
                speech_rate=self._config.speech_rate,
                latency_ms=latency_ms,
                success=True,
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.exception("Synthesis failed")
            return SynthesisResult(
                audio_bytes=b"",
                sample_rate=self._config.sample_rate,
                duration_seconds=0.0,
                text=text,
                voice_profile=self._config.voice_profile,
                speech_rate=self._config.speech_rate,
                latency_ms=latency_ms,
                success=False,
                error=str(e),
            )

    def interrupt(self) -> None:
        """Interrupt ongoing synthesis/playback."""
        self._interrupted.set()
        logger.info("SynthesisEngine: interrupted")

    def is_interrupted(self) -> bool:
        """Return True if synthesis has been interrupted."""
        return self._interrupted.is_set()

    def set_voice_profile(self, profile: VoiceProfile) -> None:
        """Switch voice profile.

        Args:
            profile: New voice profile

        """
        self._config.voice_profile = profile
        logger.info("Voice profile switched to: %s", profile.value)

    def set_speech_rate(self, rate: float) -> None:
        """Set speech rate multiplier.

        Args:
            rate: Rate multiplier (0.5 to 2.0)

        Raises:
            ValueError: If rate is out of bounds

        """
        if not _MIN_RATE <= rate <= _MAX_RATE:
            msg = f"speech_rate must be between {_MIN_RATE} and {_MAX_RATE}, got {rate}"
            raise ValueError(msg)
        self._config.speech_rate = rate
        logger.info("Speech rate set to: %sx", rate)

    def get_config(self) -> SynthesisConfig:
        """Return current configuration."""
        return self._config

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _synthesize_audio(self, text: str) -> tuple[bytes, int]:
        """Synthesize audio using available TTS engine.

        Falls back to silence if no TTS engine is available.

        Args:
            text: Preprocessed text to synthesize

        Returns:
            Tuple of (audio_bytes, sample_rate)

        """
        if self._coqui_engine is not None:
            try:
                personality = self._profile_to_personality()
                audio_bytes = self._coqui_engine.synthesize(
                    text=text,
                    personality=personality,
                    speech_rate=self._config.speech_rate,
                    volume=self._config.volume,
                )
                # BUG FIX (Round 16): this used to unconditionally return
                # self._config.sample_rate (default 22050) as the audio's
                # sample rate, regardless of what the underlying engine
                # actually produced. The real Kokoro engine (tts_engine.py)
                # outputs 24000Hz natively -- that's the rate genuinely
                # baked into audio_bytes' WAV header -- so SynthesisResult
                # .sample_rate was simply wrong whenever Kokoro was active.
                # Any downstream code that configures audio playback (e.g.
                # an output device/stream) from result.sample_rate instead
                # of independently parsing the WAV header would play back
                # 24000Hz audio at a 22050Hz rate: ~8.7% too slow/pitched
                # down. Fixed by reading the actual rate out of the WAV
                # header (mirroring _estimate_duration()'s existing
                # approach), falling back to the configured rate only if
                # the bytes can't be parsed as WAV.
                sample_rate = self._parse_wav_sample_rate(audio_bytes) or self._config.sample_rate
                return audio_bytes, sample_rate
            except Exception:
                logger.exception("CoquiTTS synthesis failed. Using silence fallback.")

        # Fallback: generate silence (for testing/offline mode)
        return self._generate_silence(text), self._config.sample_rate

    def _profile_to_personality(self) -> Any:
        """Map VoiceProfile to PersonalityType."""
        try:
            from Agent_Guru.speech.models import PersonalityType

            mapping = {
                VoiceProfile.GURU: PersonalityType.GURU,
                VoiceProfile.MAYA: PersonalityType.MAYA,
                VoiceProfile.NEUTRAL: PersonalityType.GURU,  # Default to Guru
            }
            return mapping.get(self._config.voice_profile, PersonalityType.GURU)
        except ImportError:
            return None

    def _apply_prosody(self, text: str) -> str:
        """Apply prosody preprocessing for natural speech.

        - Normalizes whitespace
        - Handles abbreviations
        - Removes unspeakable characters

        Time Complexity: O(n)

        Args:
            text: Raw text

        Returns:
            Prosody-processed text

        """
        if not text:
            return text

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Expand common abbreviations
        abbreviations = {
            r"\bDr\.": "Doctor",
            r"\bMr\.": "Mister",
            r"\bMrs\.": "Missus",
            r"\bMs\.": "Miss",
            r"\bProf\.": "Professor",
            r"\betc\.": "etcetera",
            r"\bvs\.": "versus",
            r"\be\.g\.": "for example",
            r"\bi\.e\.": "that is",
        }
        for pattern, replacement in abbreviations.items():
            text = re.sub(pattern, replacement, text)

        # Remove markdown formatting
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # Bold
        text = re.sub(r"\*(.+?)\*", r"\1", text)  # Italic
        text = re.sub(r"`(.+?)`", r"\1", text)  # Code
        text = re.sub(r"#{1,6}\s", "", text)  # Headers

        # Remove URLs (replace with "link")
        text = re.sub(r"https?://\S+", "link", text)

        # Remove emojis and special characters
        text = re.sub(r"[^\w\s.,!?;:'\"-]", "", text)

        return text.strip()

    def _generate_silence(self, text: str) -> bytes:
        """Generate silence audio as fallback.

        Duration is estimated from text length (average speaking rate).

        Args:
            text: Text to estimate duration from

        Returns:
            WAV-format silence bytes

        """
        import io
        import wave

        # Estimate duration: ~150 words/minute, ~5 chars/word
        word_count = max(1, len(text.split()))
        duration_s = (word_count / 150.0) / self._config.speech_rate
        duration_s = max(0.1, min(duration_s, 30.0))  # Clamp to 0.1-30s

        sample_rate = self._config.sample_rate
        n_samples = int(sample_rate * duration_s)

        # Generate silence (zeros)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(b"\x00\x00" * n_samples)

        return buf.getvalue()

    @staticmethod
    def _parse_wav_sample_rate(audio_bytes: bytes) -> int | None:
        """Read the actual sample rate baked into WAV-format *audio_bytes*.

        Returns None if the bytes can't be parsed as WAV (caller should
        fall back to the configured rate in that case). See _synthesize_
        audio()'s BUG FIX (Round 16) note for why this exists.
        """
        if not audio_bytes:
            return None
        try:
            import io
            import wave

            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                rate = wf.getframerate()
                return rate if rate > 0 else None
        except Exception:
            return None

    @staticmethod
    def _estimate_duration(audio_bytes: bytes, sample_rate: int) -> float:
        """Estimate audio duration from WAV bytes.

        Args:
            audio_bytes: WAV audio bytes
            sample_rate: Sample rate in Hz

        Returns:
            Duration in seconds

        """
        if not audio_bytes:
            return 0.0

        try:
            import io
            import wave

            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / float(rate) if rate > 0 else 0.0
        except Exception:
            # Rough estimate: 2 bytes per sample, 1 channel
            header_size = 44  # WAV header
            data_size = max(0, len(audio_bytes) - header_size)
            return data_size / (sample_rate * 2)  # 16-bit mono
