"""Regression tests for losing the microphone mid-session.

A PortAudio read error used to be logged and answered with silence, and the
stream was never reopened. PortAudio never recovers a failed stream (every
later read raises the same error), so one error, such as a USB mic
replugged, a Bluetooth headset dropping or Windows moving the default device
(PaErrorCode -9999), left the assistant deaf until restart. It kept reporting
that it was listening and logged a traceback about 64 times a second. Driven
through the real listen loop, 8 s after the error it had read the dead
stream 510 times, opened no new stream, and woken 0 times.
"""

from __future__ import annotations

import asyncio
import sys
import types
from typing import TYPE_CHECKING

import numpy as np

from Agent_Guru.speech import wake_word_manager as wwm
from Agent_Guru.speech.audio.wake_word import WakeWordConfig
from Agent_Guru.speech.models import PersonalityType

if TYPE_CHECKING:
    import pytest

SR = 16_000


class PortAudioError(Exception):
    pass


def _speech_like(n: int) -> np.ndarray:
    """Voiced harmonics alternating with fricative noise: passes the MFCC gates."""
    t = np.arange(n) / SR
    voiced = sum(np.sin(2 * np.pi * 150 * k * t) / k for k in range(1, 8))
    voiced = voiced * (0.5 + 0.5 * np.sin(2 * np.pi * 4 * t))
    noise = np.random.default_rng(0).normal(0, 1, n) * 0.5
    return (0.06 * np.where(np.sin(2 * np.pi * 3 * t) > 0.6, noise, voiced)).astype(np.float32)


class FakeSounddevice(types.ModuleType):
    """Stands in for the sounddevice module.

    ``plan`` decides what each successive InputStream() call does: "dies"
    opens a stream that fails after ``die_after`` reads, "fails" raises on
    open, "ok" opens a stream that delivers speech-like audio.
    """

    PortAudioError = PortAudioError

    def __init__(self, plan: list[str], die_after: int = 1) -> None:
        super().__init__("sounddevice")
        self.plan = plan
        self.die_after = die_after
        self.streams: list[FakeStream] = []
        self.open_calls = 0
        self.reinits = 0
        self.default = types.SimpleNamespace(device=[0, 0])

    def query_devices(self, *_: object) -> dict:
        return {"name": "fake mic", "default_samplerate": SR, "max_input_channels": 1}

    def _terminate(self) -> None:
        self.reinits += 1

    def _initialize(self) -> None:
        pass

    def InputStream(self, **_: object) -> FakeStream:  # noqa: N802 - mirrors sounddevice
        kind = self.plan[min(self.open_calls, len(self.plan) - 1)]
        self.open_calls += 1
        if kind == "fails":
            msg = "Error querying device -1"
            raise PortAudioError(msg)
        stream = FakeStream(self, dies=kind == "dies")
        self.streams.append(stream)
        return stream


class FakeStream:
    def __init__(self, sd: FakeSounddevice, *, dies: bool) -> None:
        self.sd = sd
        self.dies = dies
        self.reads = 0
        self.closed = False

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    def read(self, n: int):
        self.reads += 1
        if self.dies and self.reads > self.sd.die_after:
            msg = "Unanticipated host error [PaErrorCode -9999]"
            raise PortAudioError(msg)
        audio = np.zeros(n, np.float32) if self.dies else _speech_like(n)
        return audio.reshape(-1, 1), False


class FakeClock:
    """Replaces the module's ``time`` so backoff waits cost nothing."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def perf_counter(self) -> float:
        return self.now


def _install(monkeypatch: pytest.MonkeyPatch, sd: FakeSounddevice) -> FakeClock:
    clock = FakeClock()
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    monkeypatch.setattr(wwm, "time", clock)
    return clock


def _capture_until_audio(capture: wwm._AudioCapture, limit: int = 200) -> bool:
    """Capture until real audio arrives. Bounded, so broken code fails, not hangs."""
    return any(capture.capture().any() for _ in range(limit))


def _capture(duration: float = 0.5) -> wwm._AudioCapture:
    capture = wwm._AudioCapture(SR, duration, "windows")
    capture.open()
    return capture


class TestReopen:
    def test_a_failed_read_reopens_the_stream_and_audio_returns(self, monkeypatch):
        sd = FakeSounddevice(["dies", "ok"])
        _install(monkeypatch, sd)
        capture = _capture()

        capture.capture()  # live
        assert not capture.capture().any()  # the read that fails
        assert capture.failing_since is not None

        audio = capture.capture()

        assert audio.any()
        assert len(sd.streams) == 2
        assert capture.failing_since is None

    def test_the_failed_stream_is_closed_and_never_read_again(self, monkeypatch):
        sd = FakeSounddevice(["dies", "ok"])
        _install(monkeypatch, sd)
        capture = _capture()
        for _ in range(5):
            capture.capture()

        dead = sd.streams[0]
        assert dead.closed
        assert dead.reads == 2  # one good read, one that raised

    def test_the_first_reopen_does_not_reinitialise_portaudio(self, monkeypatch):
        """Re-initialising invalidates every other stream, TTS playback included."""
        sd = FakeSounddevice(["dies", "ok"])
        _install(monkeypatch, sd)
        capture = _capture()
        capture.capture()
        capture.capture()
        capture.capture()

        assert sd.reinits == 0

    def test_later_attempts_reinitialise_so_a_new_device_can_be_found(self, monkeypatch):
        sd = FakeSounddevice(["dies", "fails", "ok"])
        _install(monkeypatch, sd)
        capture = _capture()
        capture.capture()
        capture.capture()  # fails
        capture.capture()  # attempt 1 fails, backoff scheduled
        recovered = _capture_until_audio(capture)

        assert recovered
        assert sd.reinits == 1
        assert capture.failing_since is None

    def test_attempts_back_off_instead_of_spinning(self, monkeypatch):
        sd = FakeSounddevice(["dies", "fails"])
        clock = _install(monkeypatch, sd)
        capture = _capture()
        capture.capture()
        capture.capture()  # fails

        start = clock.now
        attempt_times = []
        for _ in range(200):
            if capture.reopen_attempts >= 6:
                break
            before = capture.reopen_attempts
            capture.capture()
            if capture.reopen_attempts != before:
                attempt_times.append(clock.now - start)

        assert len(attempt_times) == 6
        gaps = np.diff(attempt_times).round(3).tolist()
        assert attempt_times[0] == 0.0
        assert gaps == [1.0, 2.0, 5.0, 10.0, 10.0]

    def test_waiting_for_a_retry_is_paced_like_real_audio(self, monkeypatch):
        sd = FakeSounddevice(["dies", "fails"])
        clock = _install(monkeypatch, sd)
        capture = _capture(duration=0.5)
        capture.capture()
        capture.capture()
        capture.capture()  # attempt 1 fails, next in 1 s
        clock.slept.clear()

        capture.capture()

        assert clock.slept == [0.5]

    def test_a_mic_missing_at_startup_is_retried(self, monkeypatch):
        """No input device at startup used to mean silence for the whole session."""
        sd = FakeSounddevice(["fails", "ok"])
        _install(monkeypatch, sd)
        monkeypatch.setitem(sys.modules, "pyaudio", None)  # no fallback either
        capture = _capture()
        assert capture.failing_since is not None

        audio = capture.capture()

        assert audio.any()


class TestTellingTheUser:
    async def _manager(self, monkeypatch, sd, lost, restored):
        _install(monkeypatch, sd)

        async def on_lost(message: str) -> None:
            lost.append(message)

        async def on_restored(message: str) -> None:
            restored.append(message)

        manager = wwm.WakeWordManager(
            wwm.WakeWordManagerConfig(
                platform="windows",
                audio_capture_duration=0.5,
                on_microphone_lost=on_lost,
                on_microphone_restored=on_restored,
            ),
        )
        await manager.initialize()
        return manager

    async def test_a_mic_that_stays_lost_is_reported_once(self, monkeypatch):
        lost: list[str] = []
        restored: list[str] = []
        sd = FakeSounddevice(["dies", "fails"])
        manager = await self._manager(monkeypatch, sd, lost, restored)
        capture = manager._audio_capture

        for _ in range(40):
            capture.capture()
            await manager._report_microphone_health()

        assert capture.reopen_attempts >= wwm.MIC_LOST_REPORT_AFTER_ATTEMPTS
        assert len(lost) == 1
        assert "microphone" in lost[0].lower()
        assert not manager.microphone_available
        assert restored == []

    async def test_a_brief_drop_is_not_reported(self, monkeypatch):
        """A mic that comes back on the first reopen must not alarm the user."""
        lost: list[str] = []
        restored: list[str] = []
        sd = FakeSounddevice(["dies", "ok"])
        manager = await self._manager(monkeypatch, sd, lost, restored)
        for _ in range(5):
            manager._audio_capture.capture()
            await manager._report_microphone_health()

        assert lost == []
        assert restored == []
        assert manager.microphone_available

    async def test_recovery_after_a_report_is_announced(self, monkeypatch):
        lost: list[str] = []
        restored: list[str] = []
        attempts = wwm.MIC_LOST_REPORT_AFTER_ATTEMPTS
        sd = FakeSounddevice(["dies"] + ["fails"] * attempts + ["ok"])
        manager = await self._manager(monkeypatch, sd, lost, restored)
        capture = manager._audio_capture

        for _ in range(200):
            if lost and manager.microphone_available:
                break
            capture.capture()
            await manager._report_microphone_health()
        await manager._report_microphone_health()

        assert len(lost) == 1
        assert len(restored) == 1

    async def test_a_failing_callback_does_not_stop_listening(self, monkeypatch):
        sd = FakeSounddevice(["dies", "fails"])
        _install(monkeypatch, sd)

        async def broken(_: str) -> None:
            msg = "TTS unavailable"
            raise RuntimeError(msg)

        manager = wwm.WakeWordManager(
            wwm.WakeWordManagerConfig(platform="windows", on_microphone_lost=broken),
        )
        await manager.initialize()
        for _ in range(40):
            manager._audio_capture.capture()
            await manager._report_microphone_health()

        assert manager._mic_loss_reported


async def test_the_listen_loop_wakes_again_after_the_stream_dies(monkeypatch):
    """End to end: the case that used to leave the assistant deaf until restart."""
    sd = FakeSounddevice(["dies", "ok"], die_after=2)
    _install(monkeypatch, sd)
    # The loop's own pacing uses asyncio.sleep, which the fake clock does not
    # touch, so the loop runs in real time here.
    wakes = []

    async def on_wake(detection) -> None:
        wakes.append(detection)

    manager = wwm.WakeWordManager(
        wwm.WakeWordManagerConfig(
            wake_word_config=WakeWordConfig(cooldown_seconds=0.0),
            platform="windows",
            audio_capture_duration=0.5,
            sleep_poll_interval=0.01,
            on_detection_callback=on_wake,
        ),
    )
    await manager.initialize()
    manager._detector._backend = "mfcc"
    # Personality matching can load a Whisper model; not what this tests.
    monkeypatch.setattr(
        manager._detector,
        "_match_phrase_by_spectrum",
        lambda audio: ("hey guru", PersonalityType.GURU),
    )
    await manager.start_listening()
    try:
        for _ in range(200):
            if wakes:
                break
            await asyncio.sleep(0.01)
    finally:
        await manager.stop_listening()

    assert wakes, "never woke after the input stream failed"
    assert manager.is_listening is False
    assert sd.streams[0].reads == 3
