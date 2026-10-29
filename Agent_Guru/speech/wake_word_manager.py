"""Wake word manager for Agent Guru - multi-platform continuous detection.

Wraps the low-level :class:`~Agent_Guru.speech.audio.wake_word.WakeWordDetector`
with:
- Continuous listening loop (``start_listening`` / ``stop_listening``)
- Platform-specific audio capture (Desktop PyAudio/sounddevice, Android, iOS)
- Low-power idle mode between detections
- Personality selection based on detected wake word ("Hey Guru" → GURU,
  "Hey Maya" → MAYA)

Performance Requirements:
    - Detection latency: <200ms (95th percentile) - beats Alexa 250ms, Siri 300ms
    - Accuracy: >95% in noisy environments
    - Sleep mode CPU: <5% (low-power idle)
    - Wake mode CPU: <15%

Architecture:
    WakeWordManager
    ├── WakeWordDetector  (audio/wake_word.py) - backend detection
    ├── _AudioCapture     - platform-specific audio I/O
    └── asyncio loop      - continuous non-blocking detection

Author: Agent Guru Team
Date: 2026-03-20
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import numpy as np

from Agent_Guru.platform.platform_detector import PlatformDetector

from .audio.portaudio_lock import reinitialise_if_idle
from .audio.wake_word import WakeWordConfig, WakeWordDetector
from .models import PersonalityType, WakeWordDetection

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
# Power mode
# ---------------------------------------------------------------------------


class PowerMode(Enum):
    """Operating power mode for the wake word manager."""

    SLEEP = "sleep"  # Low-power idle - minimal CPU, waiting for wake word
    ACTIVE = "active"  # Full processing - command listening after wake word


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
        on_microphone_lost: Optional async callback, given a sentence for
            the user, invoked once when the microphone has failed and
            several reopen attempts have not brought it back.
        on_microphone_restored: Optional async callback, given a sentence
            for the user, invoked when a reported lost microphone works
            again.

    """

    wake_word_config: WakeWordConfig = field(default_factory=WakeWordConfig)
    platform: str = ""
    sleep_poll_interval: float = 0.05  # 50 ms - low-power idle
    active_poll_interval: float = 0.01  # 10 ms - active listening
    audio_capture_duration: float = 0.5  # 500 ms of audio per capture
    on_detection_callback: Callable[[WakeWordDetection], Coroutine[Any, Any, None]] | None = None
    max_detection_latency_ms: float = 200.0
    on_microphone_lost: Callable[[str], Coroutine[Any, Any, None]] | None = None
    on_microphone_restored: Callable[[str], Coroutine[Any, Any, None]] | None = None


#: Failed reopen attempts before a lost microphone is reported to the user.
#: With the backoff in _AudioCapture (0, 1, 2, 5 s) the fourth failure lands
#: about 8 s after the stream died: long enough that a mic reconnecting or a
#: Bluetooth headset re-pairing does not produce a false alarm, short enough
#: that the user hears about it before giving up on the assistant.
MIC_LOST_REPORT_AFTER_ATTEMPTS = 4


#: A wake word must be at least this many times louder (RMS) than the room's
#: measured noise floor: 6 dB, so steady noise sitting just under the
#: threshold cannot cross it on a louder moment, while speech in a moderately
#: noisy room still can.
#:
#: What this can and cannot do, measured on a laptop with an Intel Smart
#: Sound array: its driver already removes steady noise (fan-like brown
#: noise from the speaker never reached the app), and intermittent,
#: TV-like sound keeps a low median floor because the driver gates the gaps,
#: so it woke the fixed and the calibrated threshold equally (5 of 8 chunks).
#: On that machine calibration never moved the threshold. It matters where
#: steady noise does reach the app: a USB or desktop mic next to a fan,
#: which could not be tested here.
NOISE_FLOOR_MARGIN = 2.0

#: Highest wake threshold (RMS, after sensitivity scaling) calibration may set.
#:
#: Calibration used to have a lower bound only, and ran once at startup. On
#: the development laptop 5 of 11 starts in one morning measured a "noise
#: floor" of 0.078 to 0.231 and pinned the threshold at 0.156 to 0.462 for the
#: whole session. Room recordings labelled by Silero VAD showed that level is
#: people talking, not noise, and nobody could wake the assistant after.
#:
#: The cap comes from real speech on that mic: 120 s of room audio cut into
#: the detector's 1.5 s chunks, 75 of which carried speech. The highest
#: threshold each speech chunk still passes (both the RMS and the peak gate)
#: had a median of 0.0163. The shipped 0.0112 lets 61% of those chunks wake
#: it, 0.015 lets 52%, 0.03 lets 28%, and the 0.156 set that morning let 4%.
#: So calibration may never push the threshold past the point where half of
#: measured speech still gets through.
MAX_CALIBRATED_THRESHOLD = 0.015

#: The room is re-measured this often, from the audio the listen loop already
#: reads, so a threshold set in a loud moment comes back down when the room
#: quietens instead of holding for the rest of the session.
RECALIBRATE_EVERY_S = 30.0

#: How much recent audio a re-measurement looks at. The floor is the median
#: 0.5 s window over this span, so talking for less than half of it does not
#: count as noise.
_RECALIBRATION_HISTORY_S = 60.0

#: Length of the windows the noise floor is measured over. Their median RMS
#: is the floor: a word spoken during calibration raises a window or two but
#: not the median, so it cannot deafen the assistant for the whole session.
_NOISE_WINDOW_S = 0.5


@dataclass
class NoiseCalibration:
    """What :meth:`WakeWordManager.calibrate_noise_floor` measured and set."""

    seconds: float
    noise_rms: float
    peak: float
    threshold_before: float
    threshold_after: float
    digital_silence: bool
    #: True when the measured level was too loud to be a noise floor (speech
    #: or music during calibration) and the default threshold was kept.
    rejected: bool = False


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
        # Lost-stream state, read by WakeWordManager to tell the user. See
        # _mark_stream_failed(). failing_since is None while the mic works.
        self.failing_since: float | None = None
        self.reopen_attempts: int = 0
        self.last_error: str = ""
        self._next_reopen_at: float = 0.0

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
            # Unknown platform - try sounddevice as best-effort
            self._open_sounddevice()

    def capture(self, seconds: float | None = None) -> np.ndarray:
        """Capture one audio chunk.

        Args:
            seconds: Length to read; the configured chunk duration if None.
                Command capture reads shorter pieces so it can notice the
                end of speech sooner. The stream itself keeps its blocksize
                of one full chunk (see _open_desktop).

        Returns:
            Float32 array of shape ``(n_samples,)`` normalised to [-1, 1].

        """
        n_samples = int(self._sample_rate * (seconds if seconds else self._duration))
        if self._platform in ("windows", "macos", "linux"):
            return self._capture_desktop(n_samples)
        if self._platform == "android":
            return self._capture_android(n_samples)
        if self._platform == "ios":
            return self._capture_ios(n_samples)
        return self._capture_sounddevice(n_samples)

    def close(self) -> None:
        """Release audio resources."""
        try:
            if self._stream is not None:
                if hasattr(self._stream, "stop_stream"):
                    self._stream.stop_stream()
                    self._stream.close()
                elif hasattr(self._stream, "stop"):
                    # BUG FIX: sounddevice's InputStream separates stop()
                    # (halts the audio callback) from close() (actually
                    # releases the underlying PortAudio stream/OS audio
                    # device handle) -- calling only stop() here left the
                    # device handle held open indefinitely. This module
                    # explicitly targets 24+ hour continuous operation
                    # (see class/module docstrings), and _capture_pyaudio's
                    # own error-recovery path calls close() + reopens on
                    # every transient stream error it sees -- each such
                    # cycle, over a long session, leaked one more
                    # unreleased sounddevice stream, eventually risking
                    # "device busy"/"too many open streams" failures.
                    self._stream.stop()
                    if hasattr(self._stream, "close"):
                        self._stream.close()
                self._stream = None
            if self._pyaudio_instance is not None:
                self._pyaudio_instance.terminate()
                self._pyaudio_instance = None
        except Exception:  # pragma: no cover
            logger.exception("Error closing audio stream")

    # ------------------------------------------------------------------
    # Desktop (PyAudio primary, sounddevice fallback)
    # ------------------------------------------------------------------

    def _open_desktop(self) -> None:
        """Open desktop audio stream (sounddevice preferred → PyAudio fallback).

        sounddevice is preferred because PyAudio's built-in resampling
        produces near-silent output when the default device's native
        sample rate / channel count differs significantly from the
        requested 16 kHz mono (common with Intel Smart Sound mic arrays).
        """
        # --- Try sounddevice first (handles resampling correctly) ---
        try:
            import sounddevice as sd  # type: ignore[import]

            # Use the system default input device - don't try to pick a
            # specific device by sample rate, because devices that advertise
            # 16 kHz natively (e.g. "Microphone Array 3 ()") are often
            # virtual WAS endpoints that can't be opened for mono capture.
            # The default device is the one the user actually configured in
            # Windows Sound settings and PortAudio resamples correctly.
            try:
                default_dev_idx = sd.default.device[0]
                dev_info = sd.query_devices(default_dev_idx)
                # This used to say "native_rate", but the figure is whatever
                # the host API reports. Through MME the Intel array reported
                # 44100 Hz x4 while its real format (per WASAPI) is
                # 48000 Hz x2, which misleads anyone debugging the mic.
                logger.info(
                    "Opening mic via sounddevice: [%d] %s (%s, reported %d Hz x%d) -> %d Hz mono",
                    default_dev_idx, dev_info["name"],
                    sd.query_hostapis(dev_info["hostapi"])["name"],
                    int(dev_info["default_samplerate"]),
                    dev_info["max_input_channels"],
                    self._sample_rate,
                )
            except Exception:
                logger.info("Using system default input device")

            # No device= and no host API is chosen here, so on Windows
            # PortAudio opens the default device through MME. That was
            # measured against WASAPI shared mode on an Intel Smart Sound
            # array (the WASAPI stream at the device's 48000 Hz, resampled
            # with soxr) and MME was kept:
            # - MME opens at 16000 Hz and Windows converts the rate. WASAPI
            #   shared mode refuses anything but the device's own rate
            #   (-9997 "Invalid sample rate"), so switching means rate
            #   negotiation, channel handling and a resampler of our own.
            # - Reported latency 26 ms (MME) vs 22 ms (WASAPI), next to
            #   chunks of 500-1500 ms. No overflows on either over 20 s,
            #   process CPU 0.5% vs 0.2%.
            # - Audio quality (MME's resampler against soxr) is NOT settled.
            #   Test tones played through the laptop speaker barely reach its
            #   own mic, because the driver's echo cancellation removes them
            #   (3 s of speech-band noise at 0.6 recorded at rms 0.00005), so
            #   that comparison measured echo-cancelled residue, not the
            #   resampler. It needs an external speaker or a second machine.
            # - Device indices are not stable (the WASAPI default moved from
            #   15 to 9 between two runs as Bluetooth devices came and went),
            #   so pinning one would break for users.
            # Not measured: how each API reports a device being unplugged,
            # and drivers other than this one. Revisit if a user's mic
            # opens but delivers audio that is silent or distorted.
            # blocksize stays one full chunk even though command capture
            # reads shorter pieces. Measured on this MME stream: with
            # PortAudio's default small blocks, audio that arrived while the
            # listen loop was busy (Whisper on a wake candidate) was dropped,
            # 0 s of a 2 s gap kept and no overflow flag raised; with one
            # chunk per block, 2 to 2.5 s of it was still waiting to be read.
            # Shorter reads then return in bursts every half chunk.
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype="float32",
                blocksize=int(self._sample_rate * self._duration),
            )
            self._stream.start()
            self._pyaudio_instance = None  # mark: using sounddevice path
            logger.info("Desktop audio opened via sounddevice (rate=%d)", self._sample_rate)
            return
        except Exception as exc:
            logger.warning("sounddevice failed: %s - trying PyAudio", exc)

        # --- Fallback: PyAudio ---
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
            logger.info("Desktop audio opened via PyAudio")
        except Exception as exc:
            logger.warning("PyAudio also unavailable (%s) - no audio capture", exc)
            self._stream = None
            # A mic that could not be opened at startup (unplugged, held by
            # another app) used to mean silence for the whole session, even
            # after it became available. It now gets the same reopen attempts
            # as a stream that failed mid-session.
            self._pyaudio_instance = None
            self._mark_stream_failed(f"could not open an input device: {exc}")

    def _capture_desktop(self, n_samples: int) -> np.ndarray:
        """Capture audio on desktop (sounddevice or PyAudio)."""
        if self._stream is None:
            # Silence, or a reopen attempt if the stream was lost.
            return self._capture_sounddevice(n_samples)
        # sounddevice path - _pyaudio_instance is None when using sounddevice
        if self._pyaudio_instance is None:
            return self._capture_sounddevice(n_samples)
        # PyAudio path
        return self._capture_pyaudio(n_samples)

    def _capture_pyaudio(self, n_samples: int) -> np.ndarray:
        """Read one frame from a PyAudio stream, auto-reopening on stream-closed errors."""
        try:
            raw = self._stream.read(n_samples, exception_on_overflow=False)
            audio = np.frombuffer(raw, dtype=np.float32).copy()
            # Normalise to [-1, 1] if needed
            if audio.max() > 1.0 or audio.min() < -1.0:
                audio = audio / 32768.0
            return audio
        except Exception as exc:
            # -9988 = paStreamIsStopped / stream closed - reopen transparently
            if "-9988" in str(exc) or "Stream closed" in str(exc) or "Stream is stopped" in str(exc):
                logger.info("PyAudio stream closed - reopening...")
                try:
                    self.close()
                except Exception:
                    logger.debug("Stream close during reopen failed", exc_info=True)
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
                    logger.warning("PyAudio reopen failed (%s) - trying sounddevice", reopen_exc)
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
        except Exception:
            logger.exception("sounddevice unavailable - using silence")
            self._stream = None

    # ------------------------------------------------------------------
    # Recovering a lost input stream
    # ------------------------------------------------------------------
    #
    # A read error used to be logged and answered with silence, and the
    # stream was never touched again. PortAudio never recovers a stream
    # that has failed: measured on Windows, every later read on it raises
    # the same error (-9988 "Invalid stream pointer" once the handle is
    # gone, -9983 "Stream is stopped" after an abort). So one error (a
    # USB mic replugged, a Bluetooth headset dropping, Windows moving the
    # default device, PaErrorCode -9999) left the assistant deaf until it
    # was restarted, while it went on reporting that it was listening and
    # logged a traceback about 64 times a second.
    #
    # What recovers, measured on the same machine:
    # - Reopening the stream recovers as long as the device still exists
    #   (about 150 ms to open, first audio after about 650 ms through MME).
    # - A device that disappeared and came back, or a new default device,
    #   is invisible to PortAudio until it is re-initialised: it enumerates
    #   devices once, so the old default index keeps pointing at the stale
    #   device. Re-initialising takes about 80 ms.
    # - Re-initialising is process-wide and destroys every stream. This
    #   used to call it directly on every attempt from the second on, on
    #   this thread, while answers played on others. Measured: speech cut
    #   off mid-sentence with sd.wait() reporting success (8 of 8), and
    #   the process killed by an access violation when playback overlapped
    #   the repeated re-initialises of a mic that stays unplugged (5 of 5).
    #   Making it the second step only delayed that by a second. It now
    #   goes through portaudio_lock.reinitialise_if_idle(), which skips
    #   the re-initialise while anything is playing; that attempt is then
    #   a plain reopen, and the next attempt tries again.
    # - Re-initialising only once per outage was rejected: it still tears
    #   down whatever plays at that moment, and a mic plugged back in
    #   after it would stay invisible for the rest of the outage, which is
    #   the deaf-until-restart bug again.
    # - A machine with no working input device at all does not recover.
    #   That is why the failure is reported to the user after a few
    #   attempts, instead of retrying silently.
    #
    # Not measured here: a physical unplug and a Windows default-device
    # change. Both can only be produced by hand. The PortAudio
    # re-enumeration step above exists for exactly those cases.

    #: Seconds to wait before each reopen attempt. The first attempt is
    #: immediate, because the device is usually still there. After that the
    #: wait grows to cover a device reconnecting, then holds at 10 s: an
    #: attempt costs about 230 ms, so 10 s is cheap and means a mic that
    #: comes back is heard again within 10 s.
    _REOPEN_BACKOFF_S: tuple[float, ...] = (0.0, 1.0, 2.0, 5.0, 10.0)

    def _mark_stream_failed(self, error: str) -> None:
        """Drop a failed stream and schedule the first reopen attempt."""
        if self._stream is not None:
            try:
                self._stream.close()
            except Exception:
                logger.debug("Closing the failed input stream raised", exc_info=True)
            self._stream = None
        if self.failing_since is None:
            self.failing_since = time.monotonic()
            self.reopen_attempts = 0
            self._next_reopen_at = self.failing_since
            logger.warning("Microphone stream failed (%s) - reopening", error)
        self.last_error = error

    def _try_reopen_sounddevice(self) -> bool:
        """Make one reopen attempt. Returns True when the stream is back."""
        attempt = self.reopen_attempts + 1
        try:
            import sounddevice as sd  # type: ignore[import]

            if attempt > 1 and not reinitialise_if_idle():
                # Something is playing; tearing PortAudio down now would cut
                # it off or crash the process. Reopen without re-enumerating
                # this time. See the notes above.
                logger.debug("PortAudio busy - reopen attempt %d without re-initialising", attempt)
            stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype="float32",
                blocksize=int(self._sample_rate * self._duration),
            )
            stream.start()
        except Exception as exc:
            self.reopen_attempts = attempt
            self.last_error = str(exc)
            delay = self._REOPEN_BACKOFF_S[min(attempt, len(self._REOPEN_BACKOFF_S) - 1)]
            self._next_reopen_at = time.monotonic() + delay
            logger.warning(
                "Microphone reopen attempt %d failed (%s) - next attempt in %.0fs",
                attempt, exc, delay,
            )
            return False
        self._stream = stream
        self._pyaudio_instance = None
        logger.warning(
            "Microphone stream reopened after %.1fs (%d attempt(s))",
            time.monotonic() - (self.failing_since or time.monotonic()), attempt,
        )
        self.failing_since = None
        self.reopen_attempts = 0
        self.last_error = ""
        return True

    def _capture_sounddevice(self, n_samples: int) -> np.ndarray:
        """Read one frame from a sounddevice stream, reopening it if it failed."""
        if self._stream is None:
            if self.failing_since is None:
                return np.zeros(n_samples, dtype=np.float32)
            wait = self._next_reopen_at - time.monotonic()
            if wait > 0:
                # Pace the listen loop like real audio would instead of
                # spinning on silence while waiting for the next attempt.
                time.sleep(min(wait, n_samples / self._sample_rate))
                return np.zeros(n_samples, dtype=np.float32)
            if not self._try_reopen_sounddevice():
                return np.zeros(n_samples, dtype=np.float32)
        try:
            data, _ = self._stream.read(n_samples)
            return data[:, 0].astype(np.float32)
        except Exception as exc:
            self._mark_stream_failed(str(exc))
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
        except Exception:
            logger.exception("Android AudioRecord unavailable - using silence")
            self._stream = None

    def _capture_android(self, n_samples: int) -> np.ndarray:
        """Read audio from Android AudioRecord."""
        if self._stream is None:
            return np.zeros(n_samples, dtype=np.float32)
        try:
            buffer = bytearray(n_samples * 2)  # 16-bit PCM
            self._stream.read(buffer, len(buffer))
            audio = np.frombuffer(bytes(buffer), dtype=np.int16).astype(np.float32)
            return audio / 32768.0
        except Exception:
            logger.exception("Android capture error")
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
        except Exception:
            logger.exception("iOS AVAudioEngine unavailable - using silence")
            self._stream = None

    def _capture_ios(self, n_samples: int) -> np.ndarray:
        """Read audio from iOS AVAudioEngine."""
        if self._stream is None:
            return np.zeros(n_samples, dtype=np.float32)
        # AVAudioEngine tap-based capture - simplified synchronous read
        try:
            import AVFoundation  # type: ignore[import]

            AVFoundation.AVAudioPCMBuffer.alloc().initWithPCMFormat_frameCapacity_(
                self._stream["format"],
                n_samples,
            )
            self._stream["input_node"].installTapOnBus_bufferSize_format_block_(
                0,
                n_samples,
                self._stream["format"],
                lambda b, t: np.frombuffer(b.floatChannelData()[0], dtype=np.float32),
            )
            return np.zeros(n_samples, dtype=np.float32)  # placeholder
        except Exception:
            logger.exception("iOS capture error")
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
        self._mic_loss_reported: bool = False
        # The configured threshold, before any calibration. Every calibration
        # is measured against it, and a rejected one returns to it exactly.
        self._base_energy_threshold: float = self._config.wake_word_config.energy_threshold
        self._recent_window_rms: deque[float] = deque(
            maxlen=int(_RECALIBRATION_HISTORY_S / _NOISE_WINDOW_S),
        )
        self._last_recalibration: float = time.monotonic()
        self._room_too_loud: bool = False

        logger.info("WakeWordManager created - platform=%s", self._config.platform)

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
        # EVENT-LOOP FIX: opening the audio device is a blocking call into the
        # host audio stack and routinely takes tens to hundreds of milliseconds
        # (device enumeration, stream setup). Running it directly in this
        # `async def` froze the whole event loop for that entire time -- and
        # this is the wake-word path, so the freeze lands squarely on audio.
        await asyncio.to_thread(self._audio_capture.open)
        self._initialized = True
        logger.info(
            "WakeWordManager initialized - backend=%s, platform=%s",
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
            msg = "Call initialize() before start_listening()"
            raise RuntimeError(msg)
        if self._is_listening:
            logger.warning("Already listening")
            return

        # BUG FIX: stop_listening() closes and drops _audio_capture by
        # design (see close(), fixed above -- resources should genuinely
        # be released on stop), and the BUG-026 note below deliberately
        # does NOT reset _initialized so a caller can start_listening()
        # again without re-initialize()-ing. But nothing previously
        # recreated _audio_capture here: after a stop/start cycle,
        # _listen_loop()'s `if self._audio_capture is not None` guard
        # silently skipped capturing on every single iteration forever,
        # while is_listening still reported True the whole time -- a
        # permanently dead, silently non-functional listening loop with
        # no error, warning, or log to reveal it (detect() called
        # directly raises RuntimeError in this same situation, so the
        # background loop's silent failure was also inconsistent with
        # the class's own explicit API). Recreating _audio_capture here
        # when missing makes the stop/start cycle BUG-026 was written to
        # support actually work as documented.
        if self._audio_capture is None:
            sample_rate = self._config.wake_word_config.sample_rate
            self._audio_capture = _AudioCapture(
                sample_rate=sample_rate,
                duration=self._config.audio_capture_duration,
                platform_name=self._config.platform,
            )
            # Same blocking device open as in initialize(); this one runs on
            # every stop/start cycle, i.e. repeatedly during normal use.
            await asyncio.to_thread(self._audio_capture.open)

        self._is_listening = True
        self._power_mode = PowerMode.SLEEP
        self._listen_task = asyncio.create_task(self._listen_loop())
        logger.info("WakeWordManager started listening")

    async def stop_listening(self) -> None:
        """Stop the continuous listening loop and release audio resources."""
        self._is_listening = False
        if self._listen_task is not None:
            self._listen_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listen_task
            self._listen_task = None

        if self._audio_capture is not None:
            self._audio_capture.close()
            self._audio_capture = None

        # BUG-026: do NOT reset _initialized here. Stopping the listening loop
        # is a separate concern from the initialization state - resetting it
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
            msg = "Call initialize() before detect()"
            raise RuntimeError(msg)

        if audio is None:
            if self._audio_capture is None:
                msg = "Audio capture not available"
                raise RuntimeError(msg)
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

    async def calibrate_noise_floor(self, seconds: float = 3.0) -> NoiseCalibration | None:
        """Measure the room through the microphone and set the wake threshold from it.

        main.py used to log "Calibrating microphone (3s)" and then only sleep:
        nothing read the mic, and the threshold stayed at the shipped 0.015
        (0.0112 after sensitivity scaling) on every machine, in a silent room
        or next to a running fan. On the energy-based fallback detector that
        threshold is the only thing separating a wake word from room noise.

        The threshold is only ever raised above the configured one, never
        lowered, so a quiet room behaves exactly as before. It rises when the
        room's steady noise floor would otherwise sit within 6 dB of it. It
        cannot tell intermittent sound such as a TV from a wake word; see
        NOISE_FLOOR_MARGIN for what was measured.

        Returns:
            What was measured and set, or ``None`` if there is no working
            microphone to measure.

        """
        if not self._initialized or self._detector is None or self._audio_capture is None:
            return None
        capture = self._audio_capture
        chunks = max(1, math.ceil(seconds / self._config.audio_capture_duration))
        loop = asyncio.get_running_loop()
        audio = np.concatenate(
            [await loop.run_in_executor(None, capture.capture) for _ in range(chunks)],
        )
        if capture.failing_since is not None:
            logger.warning("Microphone calibration skipped: the microphone is not delivering audio")
            return None

        sample_rate = self._config.wake_word_config.sample_rate
        window_rms = self._window_rms(audio)
        noise_rms = float(np.median(window_rms))
        before, after, rejected = self._apply_noise_floor(noise_rms)
        self._recent_window_rms.extend(window_rms)
        self._last_recalibration = time.monotonic()

        result = NoiseCalibration(
            seconds=len(audio) / sample_rate,
            noise_rms=noise_rms,
            peak=float(np.max(np.abs(audio))) if len(audio) else 0.0,
            threshold_before=before,
            threshold_after=after,
            # Only the whole window being exact zeros counts: this hardware
            # returns plenty of exact zeros while sound is present, because the
            # driver's noise suppression gates the gaps.
            digital_silence=bool(len(audio)) and not np.any(audio),
            rejected=rejected,
        )
        self._report_room_level(noise_rms, rejected)
        if result.digital_silence:
            logger.warning(
                "Microphone delivered %.1fs of digital silence (every sample exactly 0). "
                "If wake words are not heard, check the microphone is not muted or "
                "blocked by a privacy switch.",
                result.seconds,
            )
        return result

    def _window_rms(self, audio: np.ndarray) -> list[float]:
        """RMS of each 0.5 s window of *audio*."""
        window = max(1, int(self._config.wake_word_config.sample_rate * _NOISE_WINDOW_S))
        return [
            float(np.sqrt(np.mean(audio[i : i + window] ** 2)))
            for i in range(0, max(1, len(audio) - window + 1), window)
        ]

    def _apply_noise_floor(self, noise_rms: float) -> tuple[float, float, bool]:
        """Set the wake threshold from a measured noise floor.

        Returns ``(threshold_before, threshold_after, rejected)``, both after
        sensitivity scaling. A floor whose margin would put the threshold
        above MAX_CALIBRATED_THRESHOLD is as loud as the speech the assistant
        has to hear, so it was talking or music, not noise. It is rejected and
        the configured default restored, rather than trusted and left in
        place for the session.
        """
        if self._detector is None:
            return 0.0, 0.0, False
        config = self._detector.config
        scale = 1.0 - config.sensitivity * 0.5
        before = config.energy_threshold * scale
        default = self._base_energy_threshold * scale
        proposed = NOISE_FLOOR_MARGIN * noise_rms
        rejected = proposed > MAX_CALIBRATED_THRESHOLD
        after = default if rejected else max(default, proposed)
        if after != before:
            # The default is written back as configured, not divided back out
            # of the scale: that division does not round-trip exactly (0.05
            # came back as 0.05000000000000001).
            config.energy_threshold = (
                self._base_energy_threshold if after == default else after / scale
            )
        return before, after, rejected

    def _report_room_level(self, noise_rms: float, rejected: bool) -> None:
        """Say, once per change, that the room was too loud to calibrate against."""
        if rejected and not self._room_too_loud:
            logger.warning(
                "The room was too loud to measure the microphone's background noise "
                "(level %.3f, as loud as talking or music), so wake sensitivity was left "
                "at its normal setting. If 'Hey Guru' is not heard, turn music or the TV "
                "down, or speak closer to the microphone. The room is measured again "
                "every %.0f seconds.",
                noise_rms, RECALIBRATE_EVERY_S,
            )
        elif not rejected and self._room_too_loud:
            logger.info("The room is quiet enough to measure again (level %.5f)", noise_rms)
        self._room_too_loud = rejected

    def _recalibrate_from(self, audio: np.ndarray) -> None:
        """Re-measure the room from audio the listen loop has already read.

        Startup calibration used to be the only one, so a threshold raised by
        a loud moment at startup could never come back down. Lowering it after
        a long stretch with no wake was rejected: no wake cannot tell a noisy
        room from a user who is not talking, so it would walk the threshold
        down into the noise in exactly the rooms that raised it. Re-measuring
        looks at the cause instead. Every chunk that did not wake the
        assistant goes into a rolling minute of history, and the same rule as
        startup is re-applied every RECALIBRATE_EVERY_S, with no extra
        microphone reads.
        """
        capture = self._audio_capture
        if self._detector is None or len(audio) == 0:
            return
        if capture is not None and capture.failing_since is not None:
            return  # silence from a lost microphone is not the room
        self._recent_window_rms.extend(self._window_rms(audio))
        now = time.monotonic()
        if now - self._last_recalibration < RECALIBRATE_EVERY_S:
            return
        if len(self._recent_window_rms) < (self._recent_window_rms.maxlen or 0) // 3:
            return
        self._last_recalibration = now
        noise_rms = float(np.median(self._recent_window_rms))
        before, after, rejected = self._apply_noise_floor(noise_rms)
        if after != before:
            logger.info(
                "Room re-measured: noise floor %.5f, wake threshold %.4f -> %.4f",
                noise_rms, before, after,
            )
        self._report_room_level(noise_rms, rejected)

    def get_last_detection(self) -> WakeWordDetection | None:
        """Return the most recent detection result (or ``None``)."""
        return self._last_detection

    async def capture_command_audio(self, chunks: int = 2, seconds: float | None = None) -> bytes:
        """Capture command audio after a wake word is detected.

        Reads *chunks* consecutive audio frames from the platform microphone
        and returns them concatenated as raw float32 bytes.

        Args:
            chunks: Number of audio frames to capture.  Each frame is
                ``config.audio_capture_duration`` seconds long, so the
                default of 2 captures ~1 second of command audio
                (2 × 0.5s default ``audio_capture_duration``).
                (BUG-034: old docstring incorrectly said ~3 seconds)
            seconds: Length of each frame instead of the configured chunk
                duration. Command capture reads 0.25 s pieces to notice the
                end of speech sooner.

        Returns:
            Raw float32 bytes of the captured audio, or ``b""`` if the
            audio capture device is not available.

        """
        if self._audio_capture is None:
            return b""

        loop = asyncio.get_running_loop()
        captured: list[np.ndarray] = []
        for _ in range(chunks):
            chunk = await loop.run_in_executor(None, self._audio_capture.capture, seconds)
            captured.append(chunk)

        combined = np.concatenate(captured).astype(np.float32)
        return combined.tobytes()

    @property
    def power_mode(self) -> PowerMode:
        """Current power mode."""
        return self._power_mode

    @property
    def is_listening(self) -> bool:
        """True when the background listening loop is active.

        The loop keeps running while the microphone is lost, so it can
        reopen it. Whether audio is actually arriving is
        :attr:`microphone_available`.
        """
        return self._is_listening

    @property
    def microphone_available(self) -> bool:
        """False while the input stream is lost and being reopened."""
        return self._audio_capture is not None and self._audio_capture.failing_since is None

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
            msg = f"Sensitivity must be in [0.0, 1.0], got {sensitivity}"
            raise ValueError(msg)
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
                    audio = await loop.run_in_executor(None, self._audio_capture.capture)
                    await self._report_microphone_health()
                    detection = await self.detect(audio)
                    if detection is None:
                        # Only audio that did not wake it describes the room;
                        # a wake word counted as noise would raise the bar
                        # against the next one.
                        self._recalibrate_from(audio)

                    if detection is not None:
                        self._power_mode = PowerMode.ACTIVE
                        if self._config.on_detection_callback is not None:
                            try:
                                await self._config.on_detection_callback(detection)
                            except Exception:
                                logger.exception("Detection callback error")
                        if self._detector is not None:
                            self._detector.start_cooldown()
                        # Return to sleep after callback
                        self._power_mode = PowerMode.SLEEP

                await asyncio.sleep(poll_interval)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Listen loop error")
                await asyncio.sleep(0.1)

    async def _report_microphone_health(self) -> None:
        """Tell the user once when the mic stays lost, and again when it is back.

        Before this, a lost microphone was visible only as a log line, and the
        assistant kept announcing that it was listening. A voice user never
        sees the log, so they had no way to know it could not hear them.
        """
        capture = self._audio_capture
        if capture is None:
            return
        if capture.failing_since is not None:
            if self._mic_loss_reported or capture.reopen_attempts < MIC_LOST_REPORT_AFTER_ATTEMPTS:
                return
            self._mic_loss_reported = True
            logger.error(
                "Microphone lost for %.0fs and %d reopen attempts failed (%s). "
                "Wake words cannot be heard. Still retrying every %.0fs.",
                time.monotonic() - capture.failing_since,
                capture.reopen_attempts,
                capture.last_error,
                _AudioCapture._REOPEN_BACKOFF_S[-1],
            )
            await self._notify(
                self._config.on_microphone_lost,
                "I can't hear you. I've lost the microphone. Check that it's "
                "connected. I'll keep trying to reconnect.",
            )
        elif self._mic_loss_reported:
            self._mic_loss_reported = False
            logger.warning("Microphone is working again - listening for wake words.")
            await self._notify(
                self._config.on_microphone_restored,
                "The microphone is working again. I can hear you.",
            )

    @staticmethod
    async def _notify(
        callback: Callable[[str], Coroutine[Any, Any, None]] | None, message: str,
    ) -> None:
        if callback is None:
            return
        try:
            await callback(message)
        except Exception:
            logger.exception("Microphone status callback failed")

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
        personality = PersonalityType.MAYA if "maya" in phrase else PersonalityType.GURU

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
