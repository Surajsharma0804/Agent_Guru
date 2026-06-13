"""Wake word manager for Agent Guru - multi-platform continuous detection.

Wraps the low-level :class:`~Agent_Guru.speech.audio.wake_word.WakeWordDetector`
with:
- Continuous listening loop (``start_listening`` / ``stop_listening``)
- Platform-specific audio capture (Desktop PyAudio/sounddevice, Android, iOS)
- Low-power idle mode between detections
- Personality selection based on detected wake word ("Hey Guru" → GURU,
  "Hey Maya" → MAYA)

Performance Requirements:
    - Detection latency: <200ms (95th percentile) — beats Alexa 250ms, Siri 300ms
    - Accuracy: >95% in noisy environments
    - Sleep mode CPU: <5% (low-power idle)
    - Wake mode CPU: <15%

Architecture:
    WakeWordManager
    ├── WakeWordDetector  (audio/wake_word.py) — backend detection
    ├── _AudioCapture     — platform-specific audio I/O
    └── asyncio loop      — continuous non-blocking detection

Author: Agent Guru Team
Date: 2026-03-20
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import numpy as np

from .audio.wake_word import WakeWordConfig, WakeWordDetector
from .models import PersonalityType, WakeWordDetection
from Agent_Guru.platform.platform_detector import PlatformDetector

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

def _detect_platform() -> str:
    """Thin wrapper — delegates to canonical PlatformDetector."""
    return PlatformDetector.detect().os_name.lower()


# ---------------------------------------------------------------------------
# Power mode
# ---------------------------------------------------------------------------

class PowerMode(Enum):
    """Operating power mode for the wake word manager."""
    SLEEP = "sleep"   # Low-power idle — minimal CPU, waiting for wake word
    ACTIVE = "active"  # Full processing — command listening after wake word


# ---------------------------------------------------------------------------
# Manager configuration
# ---------------------------------------------------------------------------

@dataclass
class WakeWordManagerConfig:
    """Configuration for :class:`WakeWordManager`.

    Attributes:
        wake_word_config: Low-level detector configuration.
        platform: Target platform (auto-detected when empty).
        sleep_poll_interval: Seconds to sleep between audio captures in
            low-power mode.  Lower values reduce latency; higher values
            reduce CPU usage.
        active_poll_interval: Seconds between captures in active mode.
        audio_capture_duration: Duration of each audio capture in seconds.
        on_detection_callback: Optional async callback invoked on detection.
        max_detection_latency_ms: Target maximum detection latency in ms.
            Used for performance assertions in tests.
    """

    wake_word_config: WakeWordConfig = field(default_factory=WakeWordConfig)
    platform: str = ""
    sleep_poll_interval: float = 0.05   # 50 ms — low-power idle
    active_poll_interval: float = 0.01  # 10 ms — active listening
    audio_capture_duration: float = 0.5  # 500 ms of audio per capture
    on_detection_callback: Optional[
        Callable[[WakeWordDetection], Coroutine[Any, Any, None]]
    ] = None
    max_detection_latency_ms: float = 200.0


# ---------------------------------------------------------------------------
# Platform-specific audio capture helpers
# ---------------------------------------------------------------------------

class _AudioCapture:
    """Thin wrapper around platform-specific audio capture.

    Provides a single :meth:`capture` method that returns a float32 NumPy
    array regardless of the underlying platform API.
    """

    def __init__(self, sample_rate: int, duration: float, platform_name: str) -> None:
        self._sample_rate = sample_rate
        self._duration = duration
        self._platform = platform_name
        self._stream: Any = None
        self._pyaudio_instance: Any = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open the audio capture stream."""
        if self._platform in ("windows", "macos", "linux"):
            self._open_desktop()
        elif self._platform == "android":
            self._open_android()
        elif self._platform == "ios":
            self._open_ios()
        else:
            # Unknown platform — try sounddevice as best-effort
            self._open_sounddevice()

    def capture(self) -> np.ndarray:
        """Capture one audio chunk.

        Returns:
            Float32 array of shape ``(n_samples,)`` normalised to [-1, 1].
        """
        if self._platform in ("windows", "macos", "linux"):
            return self._capture_desktop()
        if self._platform == "android":
            return self._capture_android()
        if self._platform == "ios":
            return self._capture_ios()
        return self._capture_sounddevice()

    def close(self) -> None:
        """Release audio resources."""
        try:
            if self._stream is not None:
                if hasattr(self._stream, "stop_stream"):
                    self._stream.stop_stream()
                    self._stream.close()
                elif hasattr(self._stream, "stop"):
                    self._stream.stop()
                self._stream = None
            if self._pyaudio_instance is not None:
                self._pyaudio_instance.terminate()
                self._pyaudio_instance = None
        except Exception as exc:  # pragma: no cover
            logger.warning("Error closing audio stream: %s", exc)

    # ------------------------------------------------------------------
    # Desktop (PyAudio primary, sounddevice fallback)
    # ------------------------------------------------------------------

    def _open_desktop(self) -> None:
        """Open desktop audio stream (PyAudio → sounddevice fallback)."""
        try:
            import pyaudio  # type: ignore[import]
            pa = pyaudio.PyAudio()
            self._pyaudio_instance = pa
            self._stream = pa.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=self._sample_rate,
                input=True,
                frames_per_buffer=int(self._sample_rate * self._duration),
            )
            logger.debug("Desktop audio opened via PyAudio")
        except Exception as exc:
            logger.debug("PyAudio unavailable (%s), trying sounddevice", exc)
            self._open_sounddevice()

    def _capture_desktop(self) -> np.ndarray:
        """Capture audio on desktop."""
        if self._stream is not None and self._pyaudio_instance is not None:
            return self._capture_pyaudio()
        return self._capture_sounddevice()

    def _capture_pyaudio(self) -> np.ndarray:
        """Read one frame from a PyAudio stream, auto-reopening on stream-closed errors."""
        n_samples = int(self._sample_rate * self._duration)
        try:
            raw = self._stream.read(n_samples, exception_on_overflow=False)
            audio = np.frombuffer(raw, dtype=np.float32).copy()
            # Normalise to [-1, 1] if needed
            if audio.max() > 1.0 or audio.min() < -1.0:
                audio = audio / 32768.0
            return audio
        except Exception as exc:
            # -9988 = paStreamIsStopped / stream closed — reopen transparently
            if "-9988" in str(exc) or "Stream closed" in str(exc) or "Stream is stopped" in str(exc):
                logger.info("PyAudio stream closed — reopening...")
                try:
                    self.close()
                except Exception:
                    pass
                try:
                    self._open_desktop()
                    if self._stream is not None and self._pyaudio_instance is not None:
                        raw = self._stream.read(n_samples, exception_on_overflow=False)
                        audio = np.frombuffer(raw, dtype=np.float32).copy()
                        if audio.max() > 1.0 or audio.min() < -1.0:
                            audio = audio / 32768.0
                        logger.info("PyAudio stream reopened successfully")
                        return audio
                except Exception as reopen_exc:
                    logger.warning("PyAudio reopen failed (%s) — trying sounddevice", reopen_exc)
                    self._open_sounddevice()
            else:
                logger.warning("PyAudio read error: %s", exc)
            return np.zeros(n_samples, dtype=np.float32)

    def _open_sounddevice(self) -> None:
        """Open sounddevice stream (fallback)."""
        try:
            import sounddevice as sd  # type: ignore[import]
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype="float32",
                blocksize=int(self._sample_rate * self._duration),
            )
            self._stream.start()
            logger.debug("Desktop audio opened via sounddevice")
        except Exception as exc:
            logger.warning("sounddevice unavailable: %s — using silence", exc)
            self._stream = None

    def _capture_sounddevice(self) -> np.ndarray:
        """Read one frame from a sounddevice stream."""
        n_samples = int(self._sample_rate * self._duration)
        if self._stream is None:
            return np.zeros(n_samples, dtype=np.float32)
        try:
            data, _ = self._stream.read(n_samples)
            return data[:, 0].astype(np.float32)
        except Exception as exc:
            logger.warning("sounddevice read error: %s", exc)
            return np.zeros(n_samples, dtype=np.float32)

    # ------------------------------------------------------------------
    # Android (AudioRecord via Kivy/pyjnius)
    # ------------------------------------------------------------------

    def _open_android(self) -> None:
        """Open Android AudioRecord stream via Kivy/pyjnius."""
        try:
            from jnius import autoclass  # type: ignore[import]
            AudioRecord = autoclass("android.media.AudioRecord")
            AudioFormat = autoclass("android.media.AudioFormat")
            MediaRecorder = autoclass("android.media.MediaRecorder$AudioSource")

            buffer_size = AudioRecord.getMinBufferSize(
                self._sample_rate,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
            )
            self._stream = AudioRecord(
                MediaRecorder.MIC,
                self._sample_rate,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                buffer_size,
            )
            self._stream.startRecording()
            logger.debug("Android AudioRecord opened")
        except Exception as exc:
            logger.warning("Android AudioRecord unavailable: %s — using silence", exc)
            self._stream = None

    def _capture_android(self) -> np.ndarray:
        """Read audio from Android AudioRecord."""
        n_samples = int(self._sample_rate * self._duration)
        if self._stream is None:
            return np.zeros(n_samples, dtype=np.float32)
        try:
            buffer = bytearray(n_samples * 2)  # 16-bit PCM
            self._stream.read(buffer, len(buffer))
            audio = np.frombuffer(bytes(buffer), dtype=np.int16).astype(np.float32)
            return audio / 32768.0
        except Exception as exc:
            logger.warning("Android capture error: %s", exc)
            return np.zeros(n_samples, dtype=np.float32)

    # ------------------------------------------------------------------
    # iOS (AVAudioEngine via pyobjc)
    # ------------------------------------------------------------------

    def _open_ios(self) -> None:
        """Open iOS AVAudioEngine stream via pyobjc."""
        try:
            import AVFoundation  # type: ignore[import]
            engine = AVFoundation.AVAudioEngine.alloc().init()
            input_node = engine.inputNode()
            format_ = input_node.outputFormatForBus_(0)
            self._stream = {"engine": engine, "input_node": input_node, "format": format_}
            engine.prepare()
            engine.startAndReturnError_(None)
            logger.debug("iOS AVAudioEngine opened")
        except Exception as exc:
            logger.warning("iOS AVAudioEngine unavailable: %s — using silence", exc)
            self._stream = None

    def _capture_ios(self) -> np.ndarray:
        """Read audio from iOS AVAudioEngine."""
        n_samples = int(self._sample_rate * self._duration)
        if self._stream is None:
            return np.zeros(n_samples, dtype=np.float32)
        # AVAudioEngine tap-based capture — simplified synchronous read
        try:
            import AVFoundation  # type: ignore[import]
            AVFoundation.AVAudioPCMBuffer.alloc().initWithPCMFormat_frameCapacity_(
                self._stream["format"], n_samples
            )
            self._stream["input_node"].installTapOnBus_bufferSize_format_block_(
                0, n_samples, self._stream["format"],
                lambda b, t: np.frombuffer(b.floatChannelData()[0], dtype=np.float32)
            )
            return np.zeros(n_samples, dtype=np.float32)  # placeholder
        except Exception as exc:
            logger.warning("iOS capture error: %s", exc)
            return np.zeros(n_samples, dtype=np.float32)


# ---------------------------------------------------------------------------
# WakeWordManager
# ---------------------------------------------------------------------------

class WakeWordManager:
    """Multi-platform wake word manager with continuous detection.

    Provides a high-level API over :class:`WakeWordDetector` with:
    - Continuous async listening loop
    - Platform-specific audio capture
    - Low-power idle mode (``PowerMode.SLEEP``)
    - Personality selection from detected wake word

    Example::

        manager = WakeWordManager()
        await manager.initialize()
        await manager.start_listening()

        # In your main loop:
        detection = await manager.detect()
        if detection:
            print(detection.personality)  # GURU or MAYA

        await manager.stop_listening()

    Performance:
        - Detection latency: <200ms (95th percentile)
        - Sleep mode CPU: <5%
        - Wake mode CPU: <15%
    """

    def __init__(self, config: WakeWordManagerConfig | None = None) -> None:
        """Initialise the manager.

        Args:
            config: Manager configuration.  Defaults to
                :class:`WakeWordManagerConfig` with auto-detected platform.
        """
        self._config = config or WakeWordManagerConfig()
        if not self._config.platform:
            self._config.platform = _detect_platform()

        self._detector: WakeWordDetector | None = None
        self._audio_capture: _AudioCapture | None = None
        self._power_mode: PowerMode = PowerMode.SLEEP
        self._is_listening: bool = False
        self._listen_task: asyncio.Task[None] | None = None
        self._last_detection: WakeWordDetection | None = None
        self._initialized: bool = False

        logger.info(
            "WakeWordManager created — platform=%s", self._config.platform
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the detector and audio capture.

        Must be called before :meth:`start_listening` or :meth:`detect`.

        Raises:
            RuntimeError: If already initialized.
        """
        if self._initialized:
            logger.warning("WakeWordManager already initialized")
            return

        self._detector = WakeWordDetector(self._config.wake_word_config)

        sample_rate = self._config.wake_word_config.sample_rate
        self._audio_capture = _AudioCapture(
            sample_rate=sample_rate,
            duration=self._config.audio_capture_duration,
            platform_name=self._config.platform,
        )
        self._audio_capture.open()
        self._initialized = True
        logger.info(
            "WakeWordManager initialized — backend=%s, platform=%s",
            self._detector._backend,
            self._config.platform,
        )

    async def start_listening(self) -> None:
        """Start the continuous background listening loop.

        The loop runs in low-power (SLEEP) mode, polling audio at
        ``config.sleep_poll_interval`` intervals.  On detection it invokes
        the optional ``on_detection_callback`` and switches to ACTIVE mode.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called.
        """
        if not self._initialized:
            raise RuntimeError("Call initialize() before start_listening()")
        if self._is_listening:
            logger.warning("Already listening")
            return

        self._is_listening = True
        self._power_mode = PowerMode.SLEEP
        self._listen_task = asyncio.create_task(self._listen_loop())
        logger.info("WakeWordManager started listening")

    async def stop_listening(self) -> None:
        """Stop the continuous listening loop and release audio resources."""
        self._is_listening = False
        if self._listen_task is not None:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        if self._audio_capture is not None:
            self._audio_capture.close()
            self._audio_capture = None

        # BUG-026: do NOT reset _initialized here. Stopping the listening loop
        # is a separate concern from the initialization state — resetting it
        # would force callers to call initialize() again before start_listening().
        logger.info("WakeWordManager stopped")

    # ------------------------------------------------------------------
    # Detection API
    # ------------------------------------------------------------------

    async def detect(self, audio: np.ndarray | None = None) -> WakeWordDetection | None:
        """Detect a wake word in *audio* (or capture from microphone).

        When *audio* is ``None`` the manager captures a chunk from the
        platform microphone.  This is the primary API for single-shot
        detection without the background loop.

        Args:
            audio: Optional pre-captured float32 audio at
                ``config.wake_word_config.sample_rate`` Hz.

        Returns:
            :class:`~Agent_Guru.speech.models.WakeWordDetection` with
            ``personality`` set to :attr:`PersonalityType.GURU` or
            :attr:`PersonalityType.MAYA`, or ``None`` if no wake word found.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called.
        """
        if not self._initialized or self._detector is None:
            raise RuntimeError("Call initialize() before detect()")

        if audio is None:
            if self._audio_capture is None:
                raise RuntimeError("Audio capture not available")
            audio = self._audio_capture.capture()

        t_start = time.perf_counter()
        detection = await self._detector.detect(audio)
        latency_ms = (time.perf_counter() - t_start) * 1000

        if detection is not None:
            detection = self._resolve_personality(detection)
            self._last_detection = detection
            logger.info(
                "Wake word detected: %s → %s (latency=%.1fms)",
                detection.wake_word,
                detection.personality.value,
                latency_ms,
            )

        return detection

    def get_last_detection(self) -> WakeWordDetection | None:
        """Return the most recent detection result (or ``None``)."""
        return self._last_detection

    async def capture_command_audio(self, chunks: int = 2) -> bytes:
        """Capture command audio after a wake word is detected.

        Reads *chunks* consecutive audio frames from the platform microphone
        and returns them concatenated as raw float32 bytes.

        Args:
            chunks: Number of audio frames to capture.  Each frame is
                ``config.audio_capture_duration`` seconds long, so the
                default of 2 captures ~1 second of command audio
                (2 × 0.5s default ``audio_capture_duration``).
                (BUG-034: old docstring incorrectly said ~3 seconds)

        Returns:
            Raw float32 bytes of the captured audio, or ``b""`` if the
            audio capture device is not available.
        """
        if self._audio_capture is None:
            return b""

        loop = asyncio.get_running_loop()
        captured: list[np.ndarray] = []
        for _ in range(chunks):
            chunk = await loop.run_in_executor(None, self._audio_capture.capture)
            captured.append(chunk)

        combined = np.concatenate(captured).astype(np.float32)
        return combined.tobytes()

    @property
    def power_mode(self) -> PowerMode:
        """Current power mode."""
        return self._power_mode

    @property
    def is_listening(self) -> bool:
        """True when the background listening loop is active."""
        return self._is_listening

    @property
    def platform(self) -> str:
        """Detected platform name."""
        return self._config.platform

    # ------------------------------------------------------------------
    # Wake word management
    # ------------------------------------------------------------------

    def get_wake_words(self) -> list[str]:
        """Return registered wake word phrases."""
        if self._detector is None:
            return list(self._config.wake_word_config.wake_words.keys())
        return self._detector.get_wake_words()

    async def add_wake_word(self, phrase: str, personality: PersonalityType) -> None:
        """Register a new wake word phrase.

        Args:
            phrase: Phrase to detect (case-insensitive).
            personality: Personality to activate on detection.
        """
        self._config.wake_word_config.wake_words[phrase.strip().lower()] = personality
        if self._detector is not None:
            await self._detector.add_wake_word(phrase, personality)

    async def remove_wake_word(self, phrase: str) -> None:
        """Unregister a wake word phrase."""
        key = phrase.strip().lower()
        self._config.wake_word_config.wake_words.pop(key, None)
        if self._detector is not None:
            await self._detector.remove_wake_word(phrase)

    def set_sensitivity(self, sensitivity: float) -> None:
        """Set detection sensitivity in [0.0, 1.0].

        Args:
            sensitivity: Higher values increase recall at the cost of more
                false positives.

        Raises:
            ValueError: If *sensitivity* is outside [0.0, 1.0].
        """
        if not 0.0 <= sensitivity <= 1.0:
            raise ValueError(f"Sensitivity must be in [0.0, 1.0], got {sensitivity}")
        self._config.wake_word_config.sensitivity = sensitivity
        if self._detector is not None:
            self._detector.set_sensitivity(sensitivity)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _listen_loop(self) -> None:
        """Continuous background listening loop.

        Runs in SLEEP (low-power) mode, capturing audio at
        ``sleep_poll_interval`` intervals.  Switches to ACTIVE mode on
        detection and back to SLEEP after the callback completes.
        """
        while self._is_listening:
            try:
                poll_interval = (
                    self._config.sleep_poll_interval
                    if self._power_mode == PowerMode.SLEEP
                    else self._config.active_poll_interval
                )

                if self._audio_capture is not None:
                    # BUG-018: capture() is a blocking synchronous call (sleeps
                    # for audio_capture_duration seconds). Running it on the
                    # event loop directly blocks ALL async tasks. Offload to a
                    # thread so only this coroutine is suspended, not the loop.
                    loop = asyncio.get_running_loop()
                    audio = await loop.run_in_executor(
                        None, self._audio_capture.capture
                    )
                    detection = await self.detect(audio)

                    if detection is not None:
                        self._power_mode = PowerMode.ACTIVE
                        if self._config.on_detection_callback is not None:
                            try:
                                await self._config.on_detection_callback(detection)
                            except Exception as exc:
                                logger.error("Detection callback error: %s", exc)
                        # Return to sleep after callback
                        self._power_mode = PowerMode.SLEEP

                await asyncio.sleep(poll_interval)

            except asyncio.CancelledError as e:
                break
            except Exception as exc:
                logger.error("Listen loop error: %s", exc)
                await asyncio.sleep(0.1)

    @staticmethod
    def _resolve_personality(detection: WakeWordDetection) -> WakeWordDetection:
        """Ensure personality is correctly set from the wake word phrase.

        Overrides the detector's personality assignment with the canonical
        mapping: "hey guru" / "guru" → GURU, "hey maya" / "maya" → MAYA.

        Args:
            detection: Raw detection from the underlying detector.

        Returns:
            Detection with corrected personality.
        """
        phrase = detection.wake_word.lower().strip()
        if "maya" in phrase:
            personality = PersonalityType.MAYA
        else:
            personality = PersonalityType.GURU

        # Return a new instance only if personality changed
        if detection.personality == personality:
            return detection

        return WakeWordDetection(
            wake_word=detection.wake_word,
            personality=personality,
            confidence=detection.confidence,
            timestamp=detection.timestamp,
            audio_chunk=detection.audio_chunk,
        )
