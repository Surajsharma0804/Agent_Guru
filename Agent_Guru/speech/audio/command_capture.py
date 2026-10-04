"""Record the spoken command after a wake word, stopping when the speaker stops.

This lived in main.py as _capture_command_with_vad. It read the microphone in
the wake detector's 1.5 s chunks and ran Silero's whole-chunk segmentation on
each one, so a chunk holding the end of a sentence counted as speech however
much silence followed, and capture always waited for one more full chunk.
Measured on 40 real utterances of 1 to 5 s fed through it: recording ran on
for a median 2.06 s (p90 2.49 s) after the speaker stopped, against a 1.2 s
end-of-speech target, on every voice turn. main.py also could not be imported
by a test (it rewraps stdout and rewrites CUDA variables at import), so none
of this had a test.

Now the microphone is read in 0.25 s pieces and each 32 ms frame is scored
once by Silero as it arrives, so the end of speech is known to the frame.
On the live MME stream the pieces still arrive in bursts every half chunk
(0.75 s), because the stream keeps one full chunk per block to avoid losing
audio (see _AudioCapture._open_desktop); the decision lands on the first burst
after the silence is long enough.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
# Silero VAD scores 512-sample windows at 16 kHz.
FRAME_SAMPLES = 512
FRAME_SECONDS = FRAME_SAMPLES / SAMPLE_RATE


@dataclass(frozen=True)
class CaptureSettings:
    """When command capture stops.

    speech_threshold and silence_threshold are Silero's own streaming
    hysteresis (VADIterator uses threshold and threshold - 0.15): a frame
    between them neither adds speech nor counts as silence, so a soft
    syllable does not end the turn.
    """

    max_seconds: float = 12.0
    end_silence_seconds: float = 1.2
    read_seconds: float = 0.25
    no_speech_seconds: float = 8.0
    # As min_speech_duration_ms=250 did before: a click or a cough is not a
    # command, so capture does not end 1.2 s after one.
    min_speech_seconds: float = 0.25
    speech_threshold: float = 0.5
    silence_threshold: float = 0.35
    # Used when Silero is unavailable: RMS of a frame that counts as speech.
    energy_threshold: float = 0.008
    # Below this RMS over the whole recording nothing is sent to STT.
    near_silence_rms: float = 0.005


class SpeechProbability(Protocol):
    """Scores one frame of FRAME_SAMPLES float32 samples; stateful across a turn."""

    def reset(self) -> None: ...

    def __call__(self, frame: np.ndarray) -> float: ...


class _SileroProbability:
    def __init__(self, model: Any) -> None:
        self._model = model

    def reset(self) -> None:
        self._model.reset_states()

    def __call__(self, frame: np.ndarray) -> float:
        import torch

        with torch.no_grad():
            return float(self._model(torch.from_numpy(frame), SAMPLE_RATE).item())


_silero_lock = threading.Lock()
_silero: _SileroProbability | None = None
_silero_failed = False


def load_silero() -> SpeechProbability | None:
    """Silero VAD, loaded once per process; None if it cannot be loaded."""
    global _silero, _silero_failed
    with _silero_lock:
        if _silero is None and not _silero_failed:
            try:
                from silero_vad import load_silero_vad  # type: ignore[import]

                _silero = _SileroProbability(load_silero_vad())
                logger.info("Silero VAD loaded for end-of-speech detection")
            except Exception as exc:
                # Recorded so every later turn does not retry a load that
                # failed and log the same warning again.
                _silero_failed = True
                logger.warning("Silero VAD unavailable (%s) - using an energy threshold", exc)
        return _silero


class _Turn:
    """Speech and silence bookkeeping for one command, frame by frame."""

    def __init__(self, settings: CaptureSettings, vad: SpeechProbability | None) -> None:
        self.s = settings
        self.vad = vad
        self.speech_seconds = 0.0
        self.silence_seconds = 0.0

    @property
    def speech_found(self) -> bool:
        return self.speech_seconds >= self.s.min_speech_seconds

    def frame(self, frame: np.ndarray) -> None:
        if self.vad is not None:
            try:
                p = self.vad(frame)
            except Exception as exc:
                logger.warning("Silero VAD failed mid-command (%s) - using an energy threshold", exc)
                self.vad = None
            else:
                if p >= self.s.speech_threshold:
                    self._speech()
                elif p < self.s.silence_threshold:
                    self._silence()
                return
        if float(np.sqrt(np.mean(frame**2))) >= self.s.energy_threshold:
            self._speech()
        else:
            self._silence()

    def _speech(self) -> None:
        self.speech_seconds += FRAME_SECONDS
        self.silence_seconds = 0.0

    def _silence(self) -> None:
        if self.speech_seconds > 0:
            self.silence_seconds += FRAME_SECONDS

    @property
    def ended(self) -> bool:
        return self.speech_found and self.silence_seconds >= self.s.end_silence_seconds


async def capture_command(
    mic: Any,
    settings: CaptureSettings | None = None,
    vad: SpeechProbability | None = None,
) -> bytes:
    """Record until the speaker stops; return float32 mono 16 kHz bytes, or b"".

    Args:
        mic: Anything with ``async capture_command_audio(chunks, seconds)``
            returning float32 bytes (WakeWordManager).
        settings: Stop rules; CaptureSettings() if None.
        vad: Frame scorer; Silero if None and loadable, else an energy
            threshold.

    Returns:
        The recording, or b"" when it holds no speech worth transcribing:
        near-silence, or music with no speech in it.

    """
    s = settings or CaptureSettings()
    if vad is None:
        vad = load_silero()
    if vad is not None:
        vad.reset()
    turn = _Turn(s, vad)

    pieces: list[np.ndarray] = []
    pending = np.zeros(0, dtype=np.float32)
    elapsed = 0.0
    while elapsed < s.max_seconds:
        try:
            raw = await mic.capture_command_audio(chunks=1, seconds=s.read_seconds)
        except Exception as exc:
            logger.warning("Command capture read failed after %.2f s: %s", elapsed, exc)
            break
        elapsed += s.read_seconds
        if not raw:
            # No microphone: time passes as silence, as it did before.
            turn.silence_seconds += s.read_seconds if turn.speech_seconds > 0 else 0.0
        else:
            piece = np.frombuffer(raw, dtype=np.float32).copy()
            pieces.append(piece)
            pending = np.concatenate([pending, piece])
            whole = len(pending) - len(pending) % FRAME_SAMPLES
            for i in range(0, whole, FRAME_SAMPLES):
                turn.frame(pending[i:i + FRAME_SAMPLES])
            pending = pending[whole:]
        if turn.ended:
            logger.info(
                "VAD: end of speech after %.2f s (%.2f s of speech, %.2f s of silence)",
                elapsed, turn.speech_seconds, turn.silence_seconds,
            )
            break
        if not turn.speech_found and elapsed >= s.no_speech_seconds:
            logger.info("VAD: no speech in %.1f s - stopping", elapsed)
            break

    if not pieces:
        return b""
    audio = np.concatenate(pieces).astype(np.float32)
    rms = float(np.sqrt(np.mean(audio**2)))
    if rms < s.near_silence_rms:
        logger.info("VAD: audio is near-silence (rms=%.4f) - discarding", rms)
        return b""
    if not turn.speech_found:
        try:
            from Agent_Guru.speech.audio.wake_word import WakeWordDetector

            if WakeWordDetector._looks_like_music(audio):
                logger.info("VAD: no speech + music detected - discarding")
                return b""
        except Exception:
            # The old code swallowed this silently; a broken music check
            # should at least leave a trace while the audio goes on to STT.
            logger.debug("Music check failed", exc_info=True)
    logger.info("VAD: captured %.1f s of audio (rms=%.4f)", len(audio) / SAMPLE_RATE, rms)
    return audio.tobytes()
