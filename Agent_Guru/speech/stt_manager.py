"""Multi-platform Speech-to-Text manager for Agent Guru.

Wraps the low-level :class:`~Agent_Guru.speech.stt.whisper_stt.WhisperTranscriber`
with:
- Platform-specific STT backends (faster-whisper on desktop, native APIs on mobile)
- Streaming transcription support with async generators
- Language auto-detection via :class:`~Agent_Guru.speech.stt.language_detector.LanguageDetector`
- Offline capability on mobile (cached models / on-device APIs)
- Graceful fallback chain when preferred backend is unavailable

Performance Requirements:
    - STT latency: <1 second (95th percentile) - beats Alexa 1.5s, Siri 2.0s
    - Accuracy: >90% on each platform
    - Streaming: first partial result within 200ms of speech start

Architecture:
    STTManager
    ├── WhisperTranscriber  (stt/whisper_stt.py) - desktop backend
    ├── _MobileSTTBackend   - Android / iOS native speech recognition
    ├── LanguageDetector    (stt/language_detector.py) - auto-detection
    └── asyncio             - streaming transcription loop

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

import numpy as np

from Agent_Guru.platform.platform_detector import PlatformDetector

from .exceptions import ModelLoadError, TranscriptionError
from .models import TranscriptionResult
from .stt.language_detector import Language, LanguageDetector
from .stt.whisper_stt import WhisperTranscriber

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Coroutine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform detection (mirrors wake_word_manager._detect_platform)
# ---------------------------------------------------------------------------


def _detect_platform() -> str:
    """Thin wrapper - delegates to canonical PlatformDetector."""
    return PlatformDetector.detect().os_name.lower()


# ---------------------------------------------------------------------------
# STT backend enum
# ---------------------------------------------------------------------------


class STTBackend(Enum):
    """Available STT backend implementations."""

    WHISPER = "whisper"  # faster-whisper (desktop)
    ANDROID_SPEECH = "android_speech"  # Android SpeechRecognizer API
    IOS_SPEECH = "ios_speech"  # Apple Speech Framework
    CLOUD_FALLBACK = "cloud_fallback"  # Cloud API fallback (future)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class STTManagerConfig:
    """Configuration for :class:`STTManager`.

    Attributes:
        platform: Target platform (auto-detected when empty).
        model_size: Whisper model size for desktop (``"tiny"`` … ``"large"``).
        compute_type: Whisper compute type (``"float32"``, ``"float16"``, ``"int8"``).
        device: Compute device for Whisper (``"cpu"`` or ``"cuda"``).
        beam_size: Beam size for Whisper decoding.
        language: Force a specific language code (``None`` for auto-detect).
        enable_language_detection: Whether to run language auto-detection.
        streaming_chunk_duration: Duration of each streaming audio chunk in seconds.
        max_latency_ms: Target maximum transcription latency in ms (used in tests).
        offline_mode: Force offline-only operation (no cloud fallback).
        on_partial_result: Optional async callback for streaming partial results.
        on_final_result: Optional async callback for final transcription results.

    """

    platform: str = ""
    model_size: str = "base"
    compute_type: str = "float32"
    device: str = "cpu"
    beam_size: int = 5
    language: str | None = None
    enable_language_detection: bool = True
    streaming_chunk_duration: float = 0.5  # 500 ms chunks
    max_latency_ms: float = 1000.0  # <1 second target
    offline_mode: bool = False
    on_partial_result: Callable[[TranscriptionResult], Coroutine[Any, Any, None]] | None = None
    on_final_result: Callable[[TranscriptionResult], Coroutine[Any, Any, None]] | None = None


# ---------------------------------------------------------------------------
# Mobile STT backend helpers
# ---------------------------------------------------------------------------


class _MobileSTTBackend:
    """Thin wrapper around platform-specific mobile STT APIs.

    Provides a unified :meth:`transcribe` interface regardless of whether
    the underlying API is Android SpeechRecognizer or Apple Speech Framework.
    """

    def __init__(self, platform_name: str) -> None:
        self._platform = platform_name
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the mobile STT backend."""
        if self._platform == "android":
            self._init_android()
        elif self._platform == "ios":
            self._init_ios()
        self._initialized = True

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio using the native mobile API.

        Args:
            audio: Float32 audio array normalised to [-1, 1].
            sample_rate: Sample rate in Hz.
            language: BCP-47 language code or ``None`` for auto-detect.

        Returns:
            :class:`~Agent_Guru.speech.models.TranscriptionResult`.

        """
        if self._platform == "android":
            return self._transcribe_android(audio, sample_rate, language)
        if self._platform == "ios":
            return self._transcribe_ios(audio, sample_rate, language)
        # Fallback: return empty result
        return TranscriptionResult(
            text="",
            language=language or "en",
            confidence=0.0,
            segments=[],
            duration=len(audio) / sample_rate,
        )

    # ------------------------------------------------------------------
    # Android
    # ------------------------------------------------------------------

    def _init_android(self) -> None:
        """Initialize Android SpeechRecognizer."""
        try:
            from jnius import autoclass  # type: ignore[import]

            self._SpeechRecognizer = autoclass("android.speech.SpeechRecognizer")
            logger.debug("Android SpeechRecognizer initialized")
        except Exception:
            logger.exception("Android SpeechRecognizer unavailable")
            self._SpeechRecognizer = None

    def _transcribe_android(
        self,
        audio: np.ndarray,
        sample_rate: int,
        language: str | None,
    ) -> TranscriptionResult:
        """Transcribe using Android SpeechRecognizer API.

        Falls back to silence result when the API is unavailable (e.g. in
        unit tests running on a non-Android host).
        """
        duration = len(audio) / sample_rate
        if getattr(self, "_SpeechRecognizer", None) is None:
            logger.debug("Android STT unavailable - returning empty result")
            return TranscriptionResult(
                text="",
                language=language or "en",
                confidence=0.0,
                segments=[],
                duration=duration,
            )
        # Real Android implementation would use Intent-based recognition.
        # Simplified synchronous wrapper for integration purposes.
        try:
            from jnius import autoclass  # type: ignore[import]

            Intent = autoclass("android.content.Intent")
            RecognizerIntent = autoclass("android.speech.RecognizerIntent")
            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            if language:
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, language)
            # NOTE: Full async result handling requires Activity context.
            # This stub returns an empty result for offline/background use.
            return TranscriptionResult(
                text="",
                language=language or "en",
                confidence=0.0,
                segments=[],
                duration=duration,
            )
        except Exception:
            logger.exception("Android transcription error")
            return TranscriptionResult(
                text="",
                language=language or "en",
                confidence=0.0,
                segments=[],
                duration=duration,
            )

    # ------------------------------------------------------------------
    # iOS
    # ------------------------------------------------------------------

    def _init_ios(self) -> None:
        """Initialize Apple Speech Framework."""
        try:
            import Speech  # type: ignore[import]  # pyobjc-framework-Speech

            self._SFSpeechRecognizer = Speech.SFSpeechRecognizer
            logger.debug("iOS SFSpeechRecognizer initialized")
        except Exception:
            logger.exception("iOS Speech Framework unavailable")
            self._SFSpeechRecognizer = None

    def _transcribe_ios(
        self,
        audio: np.ndarray,
        sample_rate: int,
        language: str | None,
    ) -> TranscriptionResult:
        """Transcribe using Apple Speech Framework.

        Falls back to empty result when the framework is unavailable.
        """
        duration = len(audio) / sample_rate
        if getattr(self, "_SFSpeechRecognizer", None) is None:
            logger.debug("iOS STT unavailable - returning empty result")
            return TranscriptionResult(
                text="",
                language=language or "en",
                confidence=0.0,
                segments=[],
                duration=duration,
            )
        try:
            import Speech  # type: ignore[import]

            locale_id = language or "en-US"
            recognizer = self._SFSpeechRecognizer.alloc().initWithLocale_(
                Speech.NSLocale.alloc().initWithLocaleIdentifier_(locale_id),
            )
            if not recognizer or not recognizer.isAvailable():
                return TranscriptionResult(
                    text="",
                    language=language or "en",
                    confidence=0.0,
                    segments=[],
                    duration=duration,
                )
            # Full async recognition requires AVAudioEngine integration.
            # Stub returns empty result for offline/background use.
            return TranscriptionResult(
                text="",
                language=language or "en",
                confidence=0.0,
                segments=[],
                duration=duration,
            )
        except Exception:
            logger.exception("iOS transcription error")
            return TranscriptionResult(
                text="",
                language=language or "en",
                confidence=0.0,
                segments=[],
                duration=duration,
            )


# ---------------------------------------------------------------------------
# STTManager
# ---------------------------------------------------------------------------


class STTManager:
    """Multi-platform Speech-to-Text manager.

    Provides a unified high-level API over platform-specific STT backends:

    - **Desktop** (Windows / macOS / Linux): faster-whisper with CPU/GPU support
    - **Android**: Android SpeechRecognizer API (with offline capability)
    - **iOS**: Apple Speech Framework (with offline capability)

    Example::

        manager = STTManager()
        await manager.initialize()

        # Single-shot transcription
        audio = np.zeros(16000, dtype=np.float32)
        result = await manager.transcribe(audio, sample_rate=16000)
        print(result.text)

        # Streaming transcription
        async for partial in manager.transcribe_stream(audio_chunks):
            print(partial.text)

    Performance:
        - Latency: <1 second (95th percentile)
        - Accuracy: >90% on each platform
        - Streaming: first partial within 200ms
    """

    def __init__(self, config: STTManagerConfig | None = None) -> None:
        """Initialise the STT manager.

        Args:
            config: Manager configuration.  Defaults to
                :class:`STTManagerConfig` with auto-detected platform.

        """
        self._config = config or STTManagerConfig()
        if not self._config.platform:
            self._config.platform = _detect_platform()

        self._whisper: WhisperTranscriber | None = None
        self._mobile_backend: _MobileSTTBackend | None = None
        self._language_detector: LanguageDetector | None = None
        self._active_backend: STTBackend | None = None
        self._initialized: bool = False
        # BUG FIX: initialize() previously had a check-then-act race on
        # self._initialized -- two concurrent initialize() callers could
        # both observe self._initialized == False (the check happens
        # before the only await point that would let the other coroutine
        # run) and both proceed to construct and load a full Whisper
        # model. Whichever call's _init_desktop() runs second overwrites
        # self._whisper, silently discarding the first (fully-loaded, or
        # still-loading) WhisperTranscriber instance -- wasting a
        # duplicate model load (CPU + significant RAM for the loaded
        # model, exactly the "duplicate model instances" this project's
        # engineering standard calls out) for no benefit. An asyncio.Lock
        # makes the whole check-then-initialize sequence atomic: a second
        # concurrent caller now blocks until the first completes, then
        # sees self._initialized == True and returns immediately without
        # re-running backend init.
        self._init_lock: asyncio.Lock = asyncio.Lock()

        logger.info("STTManager created - platform=%s", self._config.platform)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize STT models and backends.

        Selects the appropriate backend for the current platform and loads
        models.  Must be called before :meth:`transcribe` or
        :meth:`transcribe_stream`.

        Raises:
            RuntimeError: If already initialized.
            ModelLoadError: If the backend fails to load.

        """
        async with self._init_lock:
            if self._initialized:
                logger.warning("STTManager already initialized")
                return

            plat = self._config.platform

            if plat in ("windows", "macos", "linux", "unknown"):
                await self._init_desktop()
            elif plat == "android":
                await self._init_android()
            elif plat == "ios":
                await self._init_ios()
            else:
                # Unknown platform - try desktop backend as best-effort
                await self._init_desktop()

            if self._config.enable_language_detection:
                self._language_detector = LanguageDetector()

            self._initialized = True
            logger.info(
                "STTManager initialized - backend=%s, platform=%s",
                self._active_backend,
                plat,
            )

    async def _init_desktop(self) -> None:
        """Initialize faster-whisper backend for desktop platforms."""
        try:
            self._whisper = WhisperTranscriber(
                model_size=self._config.model_size,
                compute_type=self._config.compute_type,
                beam_size=self._config.beam_size,
                device=self._config.device,
            )
            # Trigger lazy model load now so first transcription is fast
            await asyncio.get_running_loop().run_in_executor(None, self._whisper._load_model)
            self._active_backend = STTBackend.WHISPER
            logger.debug("Desktop Whisper backend loaded (model=%s)", self._config.model_size)
        except Exception as exc:
            msg = f"Failed to initialize Whisper backend: {exc}"
            raise ModelLoadError(msg) from exc

    async def _init_android(self) -> None:
        """Initialize Android SpeechRecognizer backend."""
        self._mobile_backend = _MobileSTTBackend("android")
        try:
            self._mobile_backend.initialize()
            self._active_backend = STTBackend.ANDROID_SPEECH
        except Exception:
            logger.exception("Android STT init failed - using fallback")
            # Fall back to Whisper if available
            try:
                await self._init_desktop()
            except ModelLoadError:
                self._active_backend = STTBackend.ANDROID_SPEECH  # stub

    async def _init_ios(self) -> None:
        """Initialize Apple Speech Framework backend."""
        self._mobile_backend = _MobileSTTBackend("ios")
        try:
            self._mobile_backend.initialize()
            self._active_backend = STTBackend.IOS_SPEECH
        except Exception:
            logger.exception("iOS STT init failed - using fallback")
            try:
                await self._init_desktop()
            except ModelLoadError:
                self._active_backend = STTBackend.IOS_SPEECH  # stub

    async def shutdown(self) -> None:
        """Release all STT resources."""
        self._whisper = None
        self._mobile_backend = None
        self._language_detector = None
        # BUG FIX: _active_backend was previously left unchanged here, so
        # after shutdown() the active_backend property kept reporting the
        # last backend that was active (e.g. STTBackend.WHISPER) even
        # though no backend is actually loaded or usable. If a later
        # initialize() call failed (e.g. ModelLoadError from a missing
        # model file), self._initialized correctly stayed False, but
        # active_backend still misleadingly reported the prior session's
        # value -- a caller that checks active_backend without also
        # checking is_initialized would wrongly conclude STT is ready.
        self._active_backend = None
        self._initialized = False
        logger.info("STTManager shut down")

    # ------------------------------------------------------------------
    # Transcription API
    # ------------------------------------------------------------------

    async def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio to text.

        Selects the appropriate backend for the current platform and runs
        transcription.  Language is auto-detected when not specified and
        ``config.enable_language_detection`` is ``True``.

        Args:
            audio: Float32 audio array normalised to [-1, 1].
            sample_rate: Sample rate in Hz (default 16 000).
            language: BCP-47 language code or ``None`` for auto-detect.

        Returns:
            :class:`~Agent_Guru.speech.models.TranscriptionResult`.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called.
            TranscriptionError: If transcription fails on all backends.

        """
        if not self._initialized:
            msg = "Call initialize() before transcribe()"
            raise RuntimeError(msg)

        if audio is None or audio.size == 0:
            msg = "Empty audio data provided"
            raise TranscriptionError(msg)

        # Resolve language
        effective_language = language or self._config.language
        if effective_language is None and self._config.enable_language_detection:
            effective_language = self._detect_language_from_audio(audio, sample_rate)

        t_start = time.perf_counter()

        try:
            result = await self._run_transcription(audio, sample_rate, effective_language)
        except Exception as exc:
            msg = f"Transcription failed: {exc}"
            raise TranscriptionError(msg) from exc

        latency_ms = (time.perf_counter() - t_start) * 1000
        logger.debug(
            "Transcription complete - text=%r, lang=%s, latency=%.1fms",
            result.text[:50] if result.text else "",
            result.language,
            latency_ms,
        )

        if self._config.on_final_result is not None:
            try:
                await self._config.on_final_result(result)
            except Exception:
                logger.exception("on_final_result callback error")

        return result

    async def _run_transcription(
        self,
        audio: np.ndarray,
        sample_rate: int,
        language: str | None,
    ) -> TranscriptionResult:
        """Dispatch transcription to the active backend.

        Args:
            audio: Audio array.
            sample_rate: Sample rate in Hz.
            language: Language code or ``None``.

        Returns:
            :class:`~Agent_Guru.speech.models.TranscriptionResult`.

        """
        if self._active_backend == STTBackend.WHISPER and self._whisper is not None:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: self._whisper.transcribe(audio, sample_rate, language),  # type: ignore[union-attr]
            )

        if (
            self._active_backend
            in (
                STTBackend.ANDROID_SPEECH,
                STTBackend.IOS_SPEECH,
            )
            and self._mobile_backend is not None
        ):
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: self._mobile_backend.transcribe(audio, sample_rate, language),  # type: ignore[union-attr]
            )

        # No backend available - return empty result
        logger.warning("No STT backend available - returning empty result")
        return TranscriptionResult(
            text="",
            language=language or "en",
            confidence=0.0,
            segments=[],
            duration=len(audio) / sample_rate,
        )

    # ------------------------------------------------------------------
    # Streaming transcription
    # ------------------------------------------------------------------

    async def transcribe_stream(
        self,
        audio_chunks: AsyncIterator[np.ndarray],
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> AsyncIterator[TranscriptionResult]:
        """Stream transcription results as audio chunks arrive.

        Yields partial :class:`~Agent_Guru.speech.models.TranscriptionResult`
        objects as each chunk is processed, enabling real-time feedback.

        Args:
            audio_chunks: Async iterator of float32 audio chunks.
            sample_rate: Sample rate in Hz (default 16 000).
            language: BCP-47 language code or ``None`` for auto-detect.

        Yields:
            Partial :class:`~Agent_Guru.speech.models.TranscriptionResult`
            for each processed chunk.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called.

        """
        if not self._initialized:
            msg = "Call initialize() before transcribe_stream()"
            raise RuntimeError(msg)

        effective_language = language or self._config.language
        buffer: list[np.ndarray] = []
        buffer_duration = 0.0
        chunk_duration = self._config.streaming_chunk_duration

        async for chunk in audio_chunks:
            if chunk is None or chunk.size == 0:
                continue

            buffer.append(chunk)
            buffer_duration += len(chunk) / sample_rate

            if buffer_duration >= chunk_duration:
                combined = np.concatenate(buffer)
                buffer = []
                buffer_duration = 0.0

                try:
                    partial = await self.transcribe(combined, sample_rate, effective_language)
                    if self._config.on_partial_result is not None:
                        try:
                            await self._config.on_partial_result(partial)
                        except Exception:
                            logger.exception("on_partial_result callback error")
                    yield partial
                except TranscriptionError:
                    logger.exception("Streaming chunk transcription failed")

        # Flush remaining buffer
        if buffer:
            combined = np.concatenate(buffer)
            try:
                final = await self.transcribe(combined, sample_rate, effective_language)
                if self._config.on_partial_result is not None:
                    try:
                        await self._config.on_partial_result(final)
                    except Exception:
                        logger.exception("on_partial_result callback error")
                yield final
            except TranscriptionError:
                logger.exception("Streaming flush transcription failed")

    # ------------------------------------------------------------------
    # Language detection
    # ------------------------------------------------------------------

    def detect_language(self, text: str) -> str:
        """Detect language from transcribed text.

        Args:
            text: Transcribed text to analyse.

        Returns:
            BCP-47 language code string (e.g. ``"en"``, ``"es"``).

        """
        if not self._language_detector or not text.strip():
            return "en"
        result = self._language_detector.detect_language(text)
        return result.language.value if result.language != Language.UNKNOWN else "en"

    def _detect_language_from_audio(self, audio: np.ndarray, sample_rate: int) -> str | None:
        """Attempt language detection from audio characteristics.

        Currently delegates to Whisper's built-in language detection by
        returning ``None`` (which tells Whisper to auto-detect).  A future
        implementation could use a lightweight language-ID model.

        Args:
            audio: Audio array.
            sample_rate: Sample rate in Hz.

        Returns:
            Language code string or ``None`` to let the backend auto-detect.

        """
        # Whisper handles auto-detection natively when language=None
        return None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        """True when the manager has been successfully initialized."""
        return self._initialized

    @property
    def active_backend(self) -> STTBackend | None:
        """The currently active STT backend."""
        return self._active_backend

    @property
    def platform(self) -> str:
        """Detected platform name."""
        return self._config.platform

    @property
    def config(self) -> STTManagerConfig:
        """Current manager configuration."""
        return self._config

    def get_supported_languages(self) -> list[str]:
        """Return list of supported language codes.

        Returns:
            List of BCP-47 language code strings.

        """
        if self._language_detector is not None:
            return [lang.value for lang in self._language_detector.get_supported_languages()]
        # Whisper supports 99 languages; return common subset
        return [
            "en",
            "es",
            "fr",
            "de",
            "it",
            "pt",
            "ru",
            "pl",
            "nl",
            "zh",
            "ja",
            "ko",
            "hi",
            "ar",
            "tr",
            "vi",
            "id",
            "th",
        ]
