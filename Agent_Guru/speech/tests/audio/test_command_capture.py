"""Command capture stops soon after the speaker stops, and not before.

The capture used to run on for a median 2.06 s after the end of speech
(1.2 s target) because it judged whole 1.5 s chunks, and it had no tests.
These run the real capture loop on synthetic audio with a scorer whose
answer is known for every frame, so where it stops can be checked exactly.
"""

from __future__ import annotations

import numpy as np
import pytest

from Agent_Guru.speech.audio.command_capture import (
    FRAME_SAMPLES,
    SAMPLE_RATE,
    CaptureSettings,
    capture_after_wake,
    capture_command,
)

SPEECH, SOFT, QUIET = 0.2, 0.05, 0.0005


def signal(*parts: tuple[float, float]) -> np.ndarray:
    """Concatenate (seconds, amplitude) segments of a 300 Hz tone."""
    out = []
    for seconds, amp in parts:
        n = int(seconds * SAMPLE_RATE)
        t = np.arange(n) / SAMPLE_RATE
        out.append((amp * np.sin(2 * np.pi * 300 * t)).astype(np.float32))
    return np.concatenate(out)


class AmplitudeScorer:
    """Speech probability from loudness: 1.0 loud, 0.4 soft (the hysteresis zone), 0.0 quiet."""

    def __init__(self) -> None:
        self.resets = 0
        self.frames = 0

    def reset(self) -> None:
        self.resets += 1

    def __call__(self, frame: np.ndarray) -> float:
        assert len(frame) == FRAME_SAMPLES
        self.frames += 1
        level = float(np.abs(frame).max())
        return 1.0 if level > 0.1 else 0.4 if level > 0.01 else 0.0


class Mic:
    def __init__(self, audio: np.ndarray) -> None:
        self.audio = audio
        self.pos = 0
        self.reads: list[float | None] = []

    async def capture_command_audio(self, chunks: int = 1, seconds: float | None = None) -> bytes:
        self.reads.append(seconds)
        n = int((seconds or 1.5) * SAMPLE_RATE)
        out = self.audio[self.pos:self.pos + n]
        self.pos += n
        if len(out) < n:
            out = np.concatenate([out, np.full(n - len(out), QUIET, dtype=np.float32)])
        return out.astype(np.float32).tobytes()

    @property
    def seconds_read(self) -> float:
        return self.pos / SAMPLE_RATE


@pytest.mark.parametrize("lead", [0.0, 0.1, 0.37, 0.6])
async def test_stops_one_read_after_the_silence_target(lead: float) -> None:
    speech_end = lead + 2.0
    mic = Mic(signal((lead, QUIET), (2.0, SPEECH), (6.0, QUIET)))
    out = await capture_command(mic, vad=AmplitudeScorer())

    waited = mic.seconds_read - speech_end
    # 1.2 s of silence, plus at most one 0.25 s read and one 32 ms frame.
    # The old chunked capture waited up to 1.2 + 1.5 s.
    assert 1.2 - 1e-6 <= waited <= 1.2 + 0.25 + FRAME_SAMPLES / SAMPLE_RATE
    assert len(out) // 4 >= int(speech_end * SAMPLE_RATE)


async def test_reads_short_pieces() -> None:
    mic = Mic(signal((1.0, SPEECH), (3.0, QUIET)))
    await capture_command(mic, vad=AmplitudeScorer())
    assert set(mic.reads) == {0.25}


async def test_soft_frames_do_not_end_the_turn() -> None:
    # 2 s of hysteresis-zone audio inside the utterance is neither speech nor
    # silence, so capture must not stop in it.
    mic = Mic(signal((1.0, SPEECH), (2.0, SOFT), (0.5, SPEECH), (4.0, QUIET)))
    out = await capture_command(mic, vad=AmplitudeScorer())
    assert len(out) // 4 >= int(3.5 * SAMPLE_RATE)


async def test_a_click_is_not_a_command() -> None:
    # 0.1 s of loud audio is below min_speech_seconds: no end-of-speech 1.2 s
    # later; capture gives up at no_speech_seconds instead.
    mic = Mic(signal((0.1, SPEECH), (12.0, QUIET)))
    await capture_command(mic, vad=AmplitudeScorer())
    assert mic.seconds_read == pytest.approx(CaptureSettings().no_speech_seconds, abs=0.26)


async def test_never_longer_than_max_seconds() -> None:
    mic = Mic(signal((20.0, SPEECH)))
    await capture_command(mic, vad=AmplitudeScorer())
    assert mic.seconds_read == pytest.approx(CaptureSettings().max_seconds, abs=0.26)


async def test_near_silence_is_not_sent_to_stt() -> None:
    mic = Mic(signal((9.0, QUIET)))
    assert await capture_command(mic, vad=AmplitudeScorer()) == b""


async def test_scorer_is_reset_per_turn() -> None:
    scorer = AmplitudeScorer()
    await capture_command(Mic(signal((1.0, SPEECH), (3.0, QUIET))), vad=scorer)
    await capture_command(Mic(signal((1.0, SPEECH), (3.0, QUIET))), vad=scorer)
    assert scorer.resets == 2


async def test_scorer_failure_falls_back_to_energy() -> None:
    class Broken(AmplitudeScorer):
        def __call__(self, frame: np.ndarray) -> float:
            raise RuntimeError("model gone")

    speech_end = 2.0
    mic = Mic(signal((2.0, SPEECH), (6.0, QUIET)))
    out = await capture_command(mic, vad=Broken())
    assert out
    assert mic.seconds_read - speech_end <= 1.2 + 0.25 + FRAME_SAMPLES / SAMPLE_RATE


async def test_read_failure_keeps_what_was_heard() -> None:
    class Failing(Mic):
        async def capture_command_audio(self, chunks: int = 1, seconds: float | None = None) -> bytes:
            if self.pos >= SAMPLE_RATE:
                raise OSError("device unplugged")
            return await super().capture_command_audio(chunks, seconds)

    out = await capture_command(Failing(signal((3.0, SPEECH))), vad=AmplitudeScorer())
    assert len(out) // 4 == SAMPLE_RATE


async def test_no_microphone_returns_nothing() -> None:
    class NoMic:
        calls = 0

        async def capture_command_audio(self, chunks: int = 1, seconds: float | None = None) -> bytes:
            NoMic.calls += 1
            return b""

    assert await capture_command(NoMic(), vad=AmplitudeScorer()) == b""
    assert NoMic.calls <= CaptureSettings().no_speech_seconds / 0.25 + 1


# After a wake word. main.py put the wake chunk in front of whatever capture
# returned, an empty recording included, so a cough or a door that woke the
# loudness-gate detector ran a turn on itself. AFTER_WAKE has the measurement.

WAKE = signal((1.5, SPEECH))


async def test_a_wake_no_speech_follows_starts_nothing() -> None:
    mic = Mic(signal((10.0, QUIET)))
    assert await capture_after_wake(mic, WAKE, vad=AmplitudeScorer()) == b""
    # Gives up at the 3 s window, not the 8 s a command may take to start.
    assert mic.seconds_read <= 3.0 + 0.25


async def test_noise_that_is_not_speech_is_not_a_command() -> None:
    # Loud enough to pass the near-silence check, scored as no speech: the
    # case that used to reach STT with the waking sound in front of it.
    mic = Mic(signal((10.0, SOFT)))
    assert await capture_after_wake(mic, WAKE, vad=AmplitudeScorer()) == b""


@pytest.mark.parametrize("pause", [0.0, 0.5, 2.5])
async def test_a_command_said_after_the_wake_keeps_both(pause: float) -> None:
    mic = Mic(signal((pause, QUIET), (1.5, SPEECH), (4.0, QUIET)))
    out = await capture_after_wake(mic, WAKE, vad=AmplitudeScorer())
    assert out[:len(WAKE) * 4] == WAKE.tobytes()
    assert len(out) // 4 - len(WAKE) >= int((pause + 1.5) * SAMPLE_RATE)


async def test_a_command_that_starts_too_late_is_not_taken() -> None:
    mic = Mic(signal((3.5, QUIET), (1.5, SPEECH), (4.0, QUIET)))
    assert await capture_after_wake(mic, WAKE, vad=AmplitudeScorer()) == b""


async def test_without_a_wake_chunk_the_command_alone_is_returned() -> None:
    mic = Mic(signal((1.5, SPEECH), (4.0, QUIET)))
    out = await capture_after_wake(mic, None, vad=AmplitudeScorer())
    assert len(out) // 4 >= int(1.5 * SAMPLE_RATE)


async def test_other_captures_still_keep_audio_without_speech() -> None:
    # Follow-up answers and the default settings are unchanged: a recording
    # above near-silence still goes to STT.
    assert await capture_command(Mic(signal((9.0, SOFT))), vad=AmplitudeScorer())
