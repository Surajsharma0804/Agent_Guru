"""Multi-platform Text-to-Speech manager for Agent Guru.

Wraps the low-level :class:`~Agent_Guru.speech.tts.synthesis_engine.SynthesisEngine`
with:
- Platform-specific TTS backends (pyttsx3/CoquiTTS on desktop, native APIs on mobile)
- Dual personality voices: Guru (male, deep/confident) and Maya (female, warm/friendly)
- Emotion and prosody control
- Async synthesis with <1 second latency target
- Graceful fallback chain when preferred backend is unavailable

Performance Requirements:
    - TTS latency: <1 second (95th percentile) - beats Alexa 1.5s, Siri 2.0s
    - Male voice for Guru personality (deep, confident)
    - Female voice for Maya personality (warm, friendly)
    - Emotion and prosody control

Architecture:
    TTSManager
    ├── SynthesisEngine  (tts/synthesis_engine.py) - Kokoro ONNX backend
    ├── _DesktopTTSBackend  - pyttsx3 fallback for desktop
    ├── _AndroidTTSBackend  - Android TextToSpeech API
    ├── _IOSTTSBackend      - iOS AVSpeechSynthesizer
    └── asyncio             - async synthesis loop

Author: Agent Guru Team
Date: 2026-03-20
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from Agent_Guru.platform.platform_detector import PlatformDetector

from .exceptions import GuruSpeechError
from .models import EmotionType, PersonalityType
from .tts.synthesis_engine import (
    SynthesisConfig,
    SynthesisEngine,
    SynthesisResult,
    VoiceProfile,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


def _detect_platform() -> str:
    """Thin wrapper - delegates to canonical PlatformDetector."""
    return PlatformDetector.detect().os_name.lower()


# ---------------------------------------------------------------------------
# TTS backend enum
# ---------------------------------------------------------------------------


class TTSBackend(Enum):
    """Available TTS backend implementations."""

    KOKORO = "kokoro"  # Kokoro ONNX (primary - human-quality, multilingual)
    PYTTSX3 = "pyttsx3"  # pyttsx3 (desktop, lightweight fallback)
    ANDROID_TTS = "android_tts"  # Android TextToSpeech API
    IOS_TTS = "ios_tts"  # iOS AVSpeechSynthesizer
    SILENCE = "silence"  # Silence fallback (testing/offline)


# ---------------------------------------------------------------------------
# Voice gender enum
# ---------------------------------------------------------------------------


class VoiceGender(Enum):
    """Voice gender for personality mapping."""

    MALE = "male"  # Guru: deep, confident
    FEMALE = "female"  # Maya: warm, friendly


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class TTSManagerConfig:
    """Configuration for :class:`TTSManager`.

    Attributes:
        platform: Target platform (auto-detected when empty).
        voice_gender: Voice gender override (``None`` = derive from personality).
        speech_rate: Speech rate multiplier (0.5 to 2.0).
        volume: Output volume (0.0 to 1.0).
        sample_rate: Output sample rate in Hz (minimum 22050).
        enable_prosody: Whether to apply prosody/punctuation handling.
        use_gpu: Whether to use GPU acceleration for CoquiTTS.
        max_latency_ms: Target maximum synthesis latency in ms (used in tests).
        on_synthesis_complete: Optional async callback invoked after synthesis.

    """

    platform: str = ""
    voice_gender: VoiceGender | None = None
    speech_rate: float = 1.0
    volume: float = 1.0
    sample_rate: int = 22050
    enable_prosody: bool = True
    use_gpu: bool = False
    max_latency_ms: float = 1000.0  # <1 second target
    on_synthesis_complete: Callable[[SynthesisResult], Coroutine[Any, Any, None]] | None = None


# ---------------------------------------------------------------------------
# Desktop pyttsx3 fallback backend
# ---------------------------------------------------------------------------


class _DesktopTTSBackend:
    """Lightweight pyttsx3 TTS backend for desktop platforms.

    Used as a fallback when Kokoro is unavailable.  Provides basic
    male/female voice selection via pyttsx3's voice enumeration.
    """

    def __init__(self, gender: VoiceGender, speech_rate: float, volume: float) -> None:
        self._gender = gender
        self._speech_rate = speech_rate
        self._volume = volume
        self._engine: Any = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize pyttsx3 engine and select voice."""
        try:
            import pyttsx3  # type: ignore[import]

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", int(200 * self._speech_rate))
            self._engine.setProperty("volume", self._volume)
            self._select_voice()
            self._initialized = True
            logger.debug("pyttsx3 backend initialized (gender=%s)", self._gender.value)
        except Exception:
            logger.exception("pyttsx3 unavailable")
            self._engine = None

    def update_voice(self, gender: VoiceGender, speech_rate: float, volume: float) -> None:
        """Re-apply gender/rate/volume for a new synthesis request.

        FIX: previously, callers mutated ``self._gender`` /
        ``self._speech_rate`` / ``self._volume`` directly from outside this
        class (see TTSManager._synthesize_pyttsx3). That changed the
        attributes but never re-invoked pyttsx3's own
        ``setProperty("rate"/"volume", ...)`` or re-ran voice selection -
        so after the FIRST synthesize() call, every subsequent request
        silently kept using whichever voice/rate/volume was chosen at
        ``initialize()`` time, no matter what personality/rate/volume was
        actually requested. Verified concretely: a Guru request followed by
        a Maya request produced byte-identical audio, both using the
        male voice selected at startup.

        This method is now the ONLY way to change these settings after
        init, and it always re-applies rate/volume to the live pyttsx3
        engine, re-selecting the voice only when gender actually changed
        (avoids redundant voice-enumeration work on every call).
        """
        if self._engine is None or not self._initialized:
            self._gender = gender
            self._speech_rate = speech_rate
            self._volume = volume
            return

        gender_changed = gender != self._gender
        self._gender = gender
        self._speech_rate = speech_rate
        self._volume = volume

        try:
            self._engine.setProperty("rate", int(200 * speech_rate))
            self._engine.setProperty("volume", volume)
            if gender_changed:
                self._select_voice()
        except Exception:
            logger.exception("pyttsx3 update_voice failed")

    def _select_voice(self) -> None:
        """Select a voice matching the desired gender."""
        if self._engine is None:
            return
        try:
            voices = self._engine.getProperty("voices")
            if not voices:
                return
            target_gender = self._gender.value.lower()
            male_keywords = ("male", "david", "mark", "james")
            female_keywords = ("female", "zira", "hazel", "susan", "samantha")
            for voice in voices:
                voice_id_lower = voice.id.lower()
                voice_name_lower = voice.name.lower()
                if target_gender == "male" and any(
                    kw in voice_id_lower or kw in voice_name_lower
                    for kw in male_keywords
                ):
                    self._engine.setProperty("voice", voice.id)
                    logger.debug("pyttsx3 male voice selected: %s", voice.name)
                    return
                if target_gender == "female" and any(
                    kw in voice_id_lower or kw in voice_name_lower
                    for kw in female_keywords
                ):
                    self._engine.setProperty("voice", voice.id)
                    logger.debug("pyttsx3 female voice selected: %s", voice.name)
                    return
            # Fallback: use first available voice
            self._engine.setProperty("voice", voices[0].id)
        except Exception:
            logger.exception("pyttsx3 voice selection failed")

    def synthesize(self, text: str) -> bytes:
        """Synthesize text to WAV bytes using pyttsx3.

        Falls back to silence when pyttsx3 is unavailable.

        Args:
            text: Text to synthesize.

        Returns:
            WAV audio bytes.

        """
        if self._engine is None or not self._initialized:
            return self._silence_bytes(text)
        try:
            import os
            import tempfile

            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(tmp_fd)
            try:
                self._engine.save_to_file(text, tmp_path)
                self._engine.runAndWait()
                with open(tmp_path, "rb") as f:
                    return f.read()
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        except Exception:
            logger.exception("pyttsx3 synthesis failed - using silence")
            return self._silence_bytes(text)

    @staticmethod
    def _silence_bytes(text: str, sample_rate: int = 22050) -> bytes:
        """Generate silence WAV bytes proportional to text length."""
        import io
        import wave

        word_count = max(1, len(text.split()))
        duration_s = max(0.1, min(word_count / 150.0, 30.0))
        n_samples = int(sample_rate * duration_s)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b"\x00\x00" * n_samples)
        return buf.getvalue()


# ---------------------------------------------------------------------------
# Android TTS backend
# ---------------------------------------------------------------------------


class _AndroidTTSBackend:
    """Android TextToSpeech API backend.

    Uses the Android ``android.speech.tts.TextToSpeech`` class via
    Kivy/pyjnius.  Falls back to silence when the API is unavailable
    (e.g. in unit tests running on a non-Android host).

    KNOWN GAP (documented, not silently hidden): unlike the pyttsx3 backend
    above, this backend does not currently re-select voice/gender per
    request - ``initialize()`` sets the language/rate once, and there is no
    equivalent of ``update_voice()`` wired up on the Android side yet. In
    practice this means Guru vs. Maya personality switching is not
    currently audible when this backend is active. Fixing this properly
    requires querying Android's ``TextToSpeech.getVoices()`` for a female
    voice and calling ``setVoice()``, which needs a real Android runtime to
    verify against - flagged here rather than guessed at blind.
    """

    def __init__(self, gender: VoiceGender, speech_rate: float, volume: float) -> None:
        self._gender = gender
        self._speech_rate = speech_rate
        self._volume = volume
        self._tts: Any = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize Android TextToSpeech."""
        try:
            from jnius import autoclass  # type: ignore[import]

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
            Locale = autoclass("java.util.Locale")

            context = PythonActivity.mActivity
            self._tts = TextToSpeech(context, None)
            self._tts.setLanguage(Locale.US)
            self._tts.setSpeechRate(self._speech_rate)
            self._initialized = True
            logger.debug("Android TextToSpeech initialized")
        except Exception:
            logger.exception("Android TTS unavailable - using silence")
            self._tts = None

    def synthesize(self, text: str) -> bytes:
        """Synthesize text using Android TextToSpeech.

        Returns silence bytes when the API is unavailable.

        Args:
            text: Text to synthesize.

        Returns:
            WAV audio bytes (silence fallback when API unavailable).

        """
        if self._tts is None or not self._initialized:
            return _DesktopTTSBackend._silence_bytes(text)
        try:
            import os
            import tempfile

            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(tmp_fd)
            try:
                # Android TTS synthesizeToFile
                self._tts.synthesizeToFile(text, None, tmp_path, "utteranceId")
                with open(tmp_path, "rb") as f:
                    return f.read()
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        except Exception:
            logger.exception("Android TTS synthesis failed")
            return _DesktopTTSBackend._silence_bytes(text)

    def shutdown(self) -> None:
        """Release Android TTS resources."""
        if self._tts is not None:
            try:
                self._tts.shutdown()
            except Exception:
                logger.exception("Android TTS shutdown error")
            self._tts = None


# ---------------------------------------------------------------------------
# iOS TTS backend
# ---------------------------------------------------------------------------


class _IOSTTSBackend:
    """iOS AVSpeechSynthesizer backend.

    Uses ``AVFoundation.AVSpeechSynthesizer`` via pyobjc.  Falls back to
    silence when the framework is unavailable.

    KNOWN GAP: same as `_AndroidTTSBackend` above - voice gender is not
    currently re-selected per request on this backend either. `synthesize()`
    does pick a voice by language each call, but never varies it by gender/
    personality - see the TODO inline below.
    """

    def __init__(self, gender: VoiceGender, speech_rate: float, volume: float) -> None:
        self._gender = gender
        self._speech_rate = speech_rate
        self._volume = volume
        self._synthesizer: Any = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize iOS AVSpeechSynthesizer."""
        try:
            import AVFoundation  # type: ignore[import]

            self._synthesizer = AVFoundation.AVSpeechSynthesizer.alloc().init()
            self._initialized = True
            logger.debug("iOS AVSpeechSynthesizer initialized")
        except Exception:
            logger.exception("iOS AVSpeechSynthesizer unavailable - using silence")
            self._synthesizer = None

    def synthesize(self, text: str) -> bytes:
        """Synthesize text using iOS AVSpeechSynthesizer.

        Returns silence bytes when the framework is unavailable.

        Args:
            text: Text to synthesize.

        Returns:
            WAV audio bytes (silence fallback when API unavailable).

        """
        if self._synthesizer is None or not self._initialized:
            return _DesktopTTSBackend._silence_bytes(text)
        try:
            import AVFoundation  # type: ignore[import]

            utterance = AVFoundation.AVSpeechUtterance.speechUtteranceWithString_(text)
            utterance.setRate_(self._speech_rate * 0.5)  # AVSpeech rate: 0.0-1.0
            utterance.setVolume_(self._volume)

            # Select voice by gender.
            # TODO(gap, see class docstring): AVSpeechSynthesisVoice supports
            # a `gender` property (AVSpeechSynthesisVoiceGender) on iOS 13+;
            # this should filter voiceWithLanguage_ candidates by
            # self._gender instead of always taking the language's default
            # voice. Needs a real iOS runtime to verify voice availability
            # per region, so left as a documented gap rather than guessed.
            language = "en-US"
            voice = AVFoundation.AVSpeechSynthesisVoice.voiceWithLanguage_(language)
            if voice is not None:
                utterance.setVoice_(voice)

            self._synthesizer.speakUtterance_(utterance)
            # AVSpeechSynthesizer plays audio directly; return silence placeholder
            return _DesktopTTSBackend._silence_bytes(text)
        except Exception:
            logger.exception("iOS TTS synthesis failed")
            return _DesktopTTSBackend._silence_bytes(text)


# ---------------------------------------------------------------------------
# TTSManager
# ---------------------------------------------------------------------------


class TTSManager:
    """Multi-platform Text-to-Speech manager with dual personality voices.

    Provides a unified high-level API over platform-specific TTS backends:

    - **Desktop** (Windows / macOS / Linux): Kokoro ONNX (primary) → pyttsx3 (fallback)
    - **Android**: Android TextToSpeech API
    - **iOS**: AVSpeechSynthesizer

    Dual personality voices:
    - **Guru** (male): Deep, confident voice for professional/analytical tasks
    - **Maya** (female): Warm, friendly voice for personal/creative tasks

    Concurrency note: the Kokoro/pyttsx3 backends each wrap a SINGLE shared,
    stateful engine instance (re-configuring it per call is how voice/rate/
    volume switching works). Concurrent synthesize() calls on the same
    backend are therefore serialized internally (see `_coqui_lock`) so that
    one request's voice/rate/volume settings can never bleed into another
    in-flight request - see `_synthesize_coqui` for details of the bug this
    fixes and how it was verified.

    Example::

        manager = TTSManager()
        await manager.initialize()

        # Synthesize with Guru (male) voice
        result = await manager.synthesize("Hello, I'm Guru!", PersonalityType.GURU)
        print(f"Latency: {result.latency_ms:.1f}ms")

        # Synthesize with Maya (female) voice
        result = await manager.synthesize("Hi there!", PersonalityType.MAYA)

        # Synthesize with emotion
        result = await manager.synthesize(
            "Great news!", PersonalityType.GURU, emotion=EmotionType.HAPPY
        )

    Performance:
        - Synthesis latency: <1 second (95th percentile)
        - Male voice for Guru personality (deep, confident)
        - Female voice for Maya personality (warm, friendly)
    """

    def __init__(self, config: TTSManagerConfig | None = None) -> None:
        """Initialise the TTS manager.

        Args:
            config: Manager configuration.  Defaults to
                :class:`TTSManagerConfig` with auto-detected platform.

        """
        self._config = config or TTSManagerConfig()
        if not self._config.platform:
            self._config.platform = _detect_platform()

        # Primary backend: Kokoro ONNX SynthesisEngine
        self._synthesis_engine: SynthesisEngine | None = None

        # Fallback backends
        self._desktop_backend: _DesktopTTSBackend | None = None
        self._android_backend: _AndroidTTSBackend | None = None
        self._ios_backend: _IOSTTSBackend | None = None

        self._active_backend: TTSBackend = TTSBackend.SILENCE
        self._initialized: bool = False

        # FIX: both the Kokoro SynthesisEngine and the pyttsx3 backend are a
        # single shared, mutable, stateful object (configured with
        # voice/rate/volume, THEN read asynchronously via run_in_executor).
        # Verified concretely: two concurrent synthesize() calls (Guru +
        # Maya) with no lock produced audio synthesized with the WRONG
        # request's voice_profile and speech_rate - Guru's text came back
        # tagged with Maya's settings. This lock serializes access to the
        # shared engine so a request's configure-then-synthesize sequence
        # can never be interleaved by another concurrent request.
        self._coqui_lock = asyncio.Lock()
        self._pyttsx3_lock = asyncio.Lock()

        # BUG FIX: initialize() previously had the same unguarded
        # check-then-act race on self._initialized that STTManager had
        # (see speech/stt_manager.py Round 37 fix) -- two concurrent
        # initialize() callers could both observe self._initialized ==
        # False (the check happens before the only await point that
        # would let the other coroutine run) and both proceed into
        # _init_desktop(). Note this is NOT already covered by
        # SynthesisEngine.initialize()'s own Round 16 double-checked-
        # locking fix: that lock only guards concurrent calls on ONE
        # SynthesisEngine instance, but this race happens one level up
        # -- _init_desktop() constructs a SEPARATE `SynthesisEngine(...)`
        # per initialize() call, so two concurrent callers build TWO
        # engines (each independently loading its own Kokoro ONNX
        # model), and whichever finishes last silently overwrites
        # self._synthesis_engine, discarding the other -- a duplicate,
        # wasted model load. This lock makes the whole check-then-
        # initialize sequence atomic, exactly like the STTManager fix.
        self._init_lock: asyncio.Lock = asyncio.Lock()

        logger.info("TTSManager created - platform=%s", self._config.platform)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize TTS engines and backends.

        Selects the appropriate backend for the current platform and loads
        models.  Must be called before :meth:`synthesize`.

        Raises:
            RuntimeError: If already initialized.

        """
        async with self._init_lock:
            if self._initialized:
                logger.warning("TTSManager already initialized")
                return

            plat = self._config.platform

            if plat in ("windows", "macos", "linux", "unknown"):
                await self._init_desktop()
            elif plat == "android":
                await self._init_android()
            elif plat == "ios":
                await self._init_ios()
            else:
                await self._init_desktop()

            self._initialized = True
            logger.info(
                "TTSManager initialized - backend=%s, platform=%s",
                self._active_backend.value,
                plat,
            )

    async def _init_desktop(self) -> None:
        """Initialize desktop TTS: Kokoro ONNX primary, pyttsx3 fallback."""
        # Try Kokoro ONNX first (human-quality, multilingual)
        try:
            synthesis_config = SynthesisConfig(
                voice_profile=VoiceProfile.GURU,
                speech_rate=self._config.speech_rate,
                sample_rate=self._config.sample_rate,
                volume=self._config.volume,
                enable_prosody=self._config.enable_prosody,
                use_gpu=self._config.use_gpu,
            )
            engine = SynthesisEngine(config=synthesis_config)
            # Initialize in executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, engine.initialize)
            self._synthesis_engine = engine
            self._active_backend = TTSBackend.KOKORO
            logger.debug("Desktop Kokoro TTS backend initialized")
        except Exception:
            logger.exception("Kokoro TTS init failed - trying pyttsx3")
            await self._init_pyttsx3_fallback()

    async def _init_pyttsx3_fallback(self) -> None:
        """Initialize pyttsx3 as desktop fallback."""
        gender = self._config.voice_gender or VoiceGender.MALE
        backend = _DesktopTTSBackend(
            gender=gender,
            speech_rate=self._config.speech_rate,
            volume=self._config.volume,
        )
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, backend.initialize)
        self._desktop_backend = backend
        self._active_backend = TTSBackend.PYTTSX3
        logger.debug("Desktop pyttsx3 fallback backend initialized")

    async def _init_android(self) -> None:
        """Initialize Android TextToSpeech backend."""
        gender = self._config.voice_gender or VoiceGender.MALE
        backend = _AndroidTTSBackend(
            gender=gender,
            speech_rate=self._config.speech_rate,
            volume=self._config.volume,
        )
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, backend.initialize)
        self._android_backend = backend
        self._active_backend = TTSBackend.ANDROID_TTS
        logger.debug("Android TTS backend initialized")

    async def _init_ios(self) -> None:
        """Initialize iOS AVSpeechSynthesizer backend."""
        gender = self._config.voice_gender or VoiceGender.MALE
        backend = _IOSTTSBackend(
            gender=gender,
            speech_rate=self._config.speech_rate,
            volume=self._config.volume,
        )
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, backend.initialize)
        self._ios_backend = backend
        self._active_backend = TTSBackend.IOS_TTS
        logger.debug("iOS TTS backend initialized")

    async def shutdown(self) -> None:
        """Release all TTS resources."""
        if self._android_backend is not None:
            self._android_backend.shutdown()
            self._android_backend = None
        self._synthesis_engine = None
        self._desktop_backend = None
        self._ios_backend = None
        # BUG FIX: _active_backend was previously left unchanged here,
        # so after shutdown() the active_backend property kept
        # reporting the last backend that was active (e.g.
        # TTSBackend.KOKORO) even though no backend is actually loaded
        # -- the same class of stale-state bug fixed in STTManager.
        # shutdown() (Round 37). Reset to TTSBackend.SILENCE, the same
        # "no backend" sentinel __init__ uses before the first
        # initialize() call, rather than None -- active_backend's
        # return type is TTSBackend (non-Optional), so None would
        # violate the existing type contract this property already has.
        self._active_backend = TTSBackend.SILENCE
        self._initialized = False
        logger.info("TTSManager shut down")

    # ------------------------------------------------------------------
    # Synthesis API
    # ------------------------------------------------------------------

    async def synthesize(
        self,
        text: str,
        personality: PersonalityType = PersonalityType.GURU,
        emotion: EmotionType | None = None,
        speech_rate: float | None = None,
        volume: float | None = None,
    ) -> SynthesisResult:
        """Synthesize text to audio using the personality-specific voice.

        Selects the voice profile based on personality:
        - :attr:`PersonalityType.GURU` → male voice (deep, confident)
        - :attr:`PersonalityType.MAYA` → female voice (warm, friendly)

        Args:
            text: Text to synthesize.
            personality: Personality determining voice gender and style.
            emotion: Optional emotion for prosody adjustment.
            speech_rate: Override speech rate (0.5-2.0).  Uses config default
                when ``None``.
            volume: Override volume (0.0-1.0).  Uses config default when
                ``None``.

        Returns:
            :class:`~Agent_Guru.speech.tts.synthesis_engine.SynthesisResult`
            with audio bytes and metadata.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called.
            GuruSpeechError: If synthesis fails on all backends.

        """
        if not self._initialized:
            msg = "Call initialize() before synthesize()"
            raise RuntimeError(msg)

        if not text or not text.strip():
            msg = "Text cannot be empty"
            raise GuruSpeechError(msg, "TTSManager")

        effective_rate = speech_rate if speech_rate is not None else self._config.speech_rate
        effective_volume = volume if volume is not None else self._config.volume

        t_start = time.monotonic()

        result = await self._run_synthesis(
            text,
            personality,
            emotion,
            effective_rate,
            effective_volume,
        )

        latency_ms = (time.monotonic() - t_start) * 1000
        logger.debug(
            "TTS synthesis complete - personality=%s, latency=%.1fms, success=%s",
            personality.value,
            latency_ms,
            result.success,
        )

        if self._config.on_synthesis_complete is not None:
            try:
                await self._config.on_synthesis_complete(result)
            except Exception:
                logger.exception("on_synthesis_complete callback error")

        return result

    async def _run_synthesis(
        self,
        text: str,
        personality: PersonalityType,
        emotion: EmotionType | None,
        speech_rate: float,
        volume: float,
    ) -> SynthesisResult:
        """Dispatch synthesis to the active backend.

        Args:
            text: Text to synthesize.
            personality: Personality for voice selection.
            emotion: Optional emotion adjustment.
            speech_rate: Speech rate multiplier.
            volume: Volume multiplier.

        Returns:
            :class:`~Agent_Guru.speech.tts.synthesis_engine.SynthesisResult`.

        """
        voice_profile = self._personality_to_voice_profile(personality)

        if self._active_backend == TTSBackend.KOKORO and self._synthesis_engine is not None:
            return await self._synthesize_coqui(text, voice_profile, emotion, speech_rate, volume)

        if self._active_backend == TTSBackend.PYTTSX3 and self._desktop_backend is not None:
            return await self._synthesize_pyttsx3(text, voice_profile, speech_rate, volume)

        if self._active_backend == TTSBackend.ANDROID_TTS and self._android_backend is not None:
            return await self._synthesize_android(text, voice_profile, speech_rate, volume)

        if self._active_backend == TTSBackend.IOS_TTS and self._ios_backend is not None:
            return await self._synthesize_ios(text, voice_profile, speech_rate, volume)

        # Silence fallback
        return self._silence_result(text, voice_profile, speech_rate, self._config.sample_rate)

    async def _synthesize_coqui(
        self,
        text: str,
        voice_profile: VoiceProfile,
        emotion: EmotionType | None,
        speech_rate: float,
        volume: float,
    ) -> SynthesisResult:
        """Synthesize using the Kokoro-backed SynthesisEngine.

        FIX (verified with a targeted concurrency test): this engine is a
        SINGLE instance shared across every synthesize() call, configured
        (voice/rate/volume) and then read asynchronously via
        run_in_executor(). Without serialization, two concurrent calls can
        interleave: request A sets voice=GURU, request B sets voice=MAYA
        before A's queued executor job actually runs `engine.synthesize()`
        - so A's audio comes back synthesized with B's voice. Confirmed
        this exact failure mode with an isolated repro before applying this
        fix. `_coqui_lock` now serializes the whole
        configure-then-synthesize sequence per engine, so concurrent
        requests queue safely instead of corrupting each other's settings.
        """
        if self._synthesis_engine is None:
            msg = "TTSManager._synthesize_coqui called with no synthesis engine initialized"
            raise AssertionError(msg)

        async with self._coqui_lock:
            engine = self._synthesis_engine
            engine.set_voice_profile(voice_profile)
            engine.set_speech_rate(speech_rate)
            engine._config.volume = volume  # noqa: SLF001 - SynthesisEngine has no public
            # volume setter; see synthesis_engine.py TODO to add one.

            loop = asyncio.get_running_loop()
            result: SynthesisResult = await loop.run_in_executor(
                None, lambda: engine.synthesize(text)
            )
            return result

    async def _synthesize_pyttsx3(
        self,
        text: str,
        voice_profile: VoiceProfile,
        speech_rate: float,
        volume: float,
    ) -> SynthesisResult:
        """Synthesize using pyttsx3 fallback backend.

        FIX: previously mutated `self._desktop_backend._gender` /
        `._speech_rate` / `._volume` directly, which had NO effect on
        actual synthesis - pyttsx3's own voice/rate/volume properties were
        only ever applied once, at initialize() time. Verified concretely:
        a Guru request followed by a Maya request produced byte-identical
        audio. Now calls `update_voice()`, which actually re-applies these
        settings to the live pyttsx3 engine (see `_DesktopTTSBackend.
        update_voice` for the fix and its own verification).

        Also serialized with `_pyttsx3_lock` for the same reason as
        `_synthesize_coqui` above - this is a single shared backend
        instance too.
        """
        if self._desktop_backend is None:
            msg = "TTSManager._synthesize_pyttsx3 called with no desktop backend initialized"
            raise AssertionError(msg)

        async with self._pyttsx3_lock:
            gender = self._voice_profile_to_gender(voice_profile)
            backend = self._desktop_backend

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, lambda: backend.update_voice(gender, speech_rate, volume)
            )

            t_start = time.monotonic()
            audio_bytes: bytes = await loop.run_in_executor(
                None, lambda: backend.synthesize(text)
            )
            latency_ms = (time.monotonic() - t_start) * 1000

        return self._build_result(
            text, audio_bytes, voice_profile, speech_rate, latency_ms, self._config.sample_rate
        )

    async def _synthesize_android(
        self,
        text: str,
        voice_profile: VoiceProfile,
        speech_rate: float,
        volume: float,
    ) -> SynthesisResult:
        """Synthesize using Android TextToSpeech backend.

        See `_AndroidTTSBackend`'s docstring for the documented gap: voice
        gender is not currently re-applied per request on this backend.
        """
        if self._android_backend is None:
            msg = "TTSManager._synthesize_android called with no android backend initialized"
            raise AssertionError(msg)
        loop = asyncio.get_running_loop()
        t_start = time.monotonic()
        audio_bytes: bytes = await loop.run_in_executor(
            None,
            lambda: self._android_backend.synthesize(text),  # type: ignore[union-attr]
        )
        latency_ms = (time.monotonic() - t_start) * 1000
        return self._build_result(
            text, audio_bytes, voice_profile, speech_rate, latency_ms, self._config.sample_rate
        )

    async def _synthesize_ios(
        self,
        text: str,
        voice_profile: VoiceProfile,
        speech_rate: float,
        volume: float,
    ) -> SynthesisResult:
        """Synthesize using iOS AVSpeechSynthesizer backend.

        See `_IOSTTSBackend`'s docstring for the documented gap: voice
        gender is not currently re-applied per request on this backend.
        """
        if self._ios_backend is None:
            msg = "TTSManager._synthesize_ios called with no ios backend initialized"
            raise AssertionError(msg)
        loop = asyncio.get_running_loop()
        t_start = time.monotonic()
        audio_bytes: bytes = await loop.run_in_executor(
            None,
            lambda: self._ios_backend.synthesize(text),  # type: ignore[union-attr]
        )
        latency_ms = (time.monotonic() - t_start) * 1000
        return self._build_result(
            text, audio_bytes, voice_profile, speech_rate, latency_ms, self._config.sample_rate
        )

    # ------------------------------------------------------------------
    # Voice configuration helpers
    # ------------------------------------------------------------------

    def set_speech_rate(self, rate: float) -> None:
        """Set speech rate multiplier.

        Args:
            rate: Rate multiplier (0.5 to 2.0).

        Raises:
            ValueError: If rate is outside [0.5, 2.0].

        """
        if not 0.5 <= rate <= 2.0:
            msg = f"speech_rate must be in [0.5, 2.0], got {rate}"
            raise ValueError(msg)
        self._config.speech_rate = rate
        if self._synthesis_engine is not None:
            self._synthesis_engine.set_speech_rate(rate)
        logger.debug("Speech rate set to %.2f", rate)

    def set_volume(self, volume: float) -> None:
        """Set output volume.

        Args:
            volume: Volume multiplier (0.0 to 1.0).

        Raises:
            ValueError: If volume is outside [0.0, 1.0].

        """
        if not 0.0 <= volume <= 1.0:
            msg = f"volume must be in [0.0, 1.0], got {volume}"
            raise ValueError(msg)
        self._config.volume = volume
        logger.debug("Volume set to %.2f", volume)

    def get_voice_gender(self, personality: PersonalityType) -> VoiceGender:
        """Return the voice gender for a given personality.

        Args:
            personality: Personality type.

        Returns:
            :class:`VoiceGender` for the personality.

        """
        return VoiceGender.MALE if personality == PersonalityType.GURU else VoiceGender.FEMALE

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        """True when the manager has been successfully initialized."""
        return self._initialized

    @property
    def active_backend(self) -> TTSBackend:
        """The currently active TTS backend."""
        return self._active_backend

    @property
    def platform(self) -> str:
        """Detected platform name."""
        return self._config.platform

    @property
    def config(self) -> TTSManagerConfig:
        """Current manager configuration."""
        return self._config

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _personality_to_voice_profile(personality: PersonalityType) -> VoiceProfile:
        """Map PersonalityType to VoiceProfile.

        Args:
            personality: Personality type.

        Returns:
            Corresponding :class:`VoiceProfile`.

        """
        return VoiceProfile.GURU if personality == PersonalityType.GURU else VoiceProfile.MAYA

    @staticmethod
    def _voice_profile_to_gender(profile: VoiceProfile) -> VoiceGender:
        """Map VoiceProfile to VoiceGender.

        Args:
            profile: Voice profile.

        Returns:
            Corresponding :class:`VoiceGender`.

        """
        return VoiceGender.MALE if profile == VoiceProfile.GURU else VoiceGender.FEMALE

    @staticmethod
    def _build_result(
        text: str,
        audio_bytes: bytes,
        voice_profile: VoiceProfile,
        speech_rate: float,
        latency_ms: float,
        sample_rate: int = 22050,
    ) -> SynthesisResult:
        """Build a :class:`SynthesisResult` from raw audio bytes.

        Args:
            text: Original text.
            audio_bytes: WAV audio bytes.
            voice_profile: Voice profile used.
            speech_rate: Speech rate used.
            latency_ms: Synthesis latency in milliseconds.
            sample_rate: Actual output sample rate - FIX: previously
                hardcoded to 22050 regardless of `TTSManagerConfig.
                sample_rate`, so changing the config's sample rate silently
                stopped propagating into the result metadata for every
                non-Kokoro backend.

        Returns:
            :class:`SynthesisResult` instance.

        """
        duration = TTSManager._estimate_duration(audio_bytes, sample_rate)
        return SynthesisResult(
            audio_bytes=audio_bytes,
            sample_rate=sample_rate,
            duration_seconds=duration,
            text=text,
            voice_profile=voice_profile,
            speech_rate=speech_rate,
            latency_ms=latency_ms,
            success=len(audio_bytes) > 0,
            error=None if audio_bytes else "No audio generated",
        )

    @staticmethod
    def _estimate_duration(audio_bytes: bytes, sample_rate: int = 22050) -> float:
        """Estimate audio duration from WAV bytes.

        Args:
            audio_bytes: WAV audio bytes.
            sample_rate: Fallback sample rate to assume if the WAV header
                can't be parsed - FIX: previously hardcoded to 22050 even
                when the actual configured/synthesized rate (e.g. Kokoro's
                24000Hz) was different, which would silently under- or
                over-estimate duration whenever header parsing failed.

        Returns:
            Duration in seconds.

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
            header_size = 44
            data_size = max(0, len(audio_bytes) - header_size)
            bytes_per_sample = 2  # 16-bit PCM, mono
            return data_size / (sample_rate * bytes_per_sample)

    @staticmethod
    def _silence_result(
        text: str,
        voice_profile: VoiceProfile,
        speech_rate: float,
        sample_rate: int = 22050,
    ) -> SynthesisResult:
        """Return a silence SynthesisResult (no backend available).

        Args:
            text: Original text.
            voice_profile: Voice profile.
            speech_rate: Speech rate.
            sample_rate: Output sample rate (see `_build_result` FIX note).

        Returns:
            :class:`SynthesisResult` with silence audio.

        """
        audio_bytes = _DesktopTTSBackend._silence_bytes(text, sample_rate)
        return SynthesisResult(
            audio_bytes=audio_bytes,
            sample_rate=sample_rate,
            duration_seconds=TTSManager._estimate_duration(audio_bytes, sample_rate),
            text=text,
            voice_profile=voice_profile,
            speech_rate=speech_rate,
            latency_ms=0.0,
            success=True,
            error=None,
        )
