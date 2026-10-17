"""Regression tests for re-initialising PortAudio while it is in use.

The microphone recovery path called sd._terminate() and sd._initialize()
on the listen thread from its second reopen attempt, while answers, the
filler clip and the beep played on other threads through the same
PortAudio instance, with no lock. Measured on Windows: speech cut off
mid-sentence with sd.wait() reporting success (8 of 8), the process killed
by an access violation when playback overlapped repeated re-initialises
(5 of 5), and heap corruption with a writing OutputStream (3 of 3).

These tests use a fake sounddevice module. Real audio would reproduce the
crash, and a crash takes the whole pytest run down with it, so the broken
code would stop the suite instead of failing a test. The fake records, at
every PortAudio call, whether another thread could have re-initialised
PortAudio at that moment.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import types
from typing import TYPE_CHECKING, Any

import numpy as np

from Agent_Guru.speech.audio import portaudio_lock

if TYPE_CHECKING:
    import pytest


def _another_thread_could_reinitialise() -> bool:
    """True if the PortAudio lock is free to a thread other than this one."""
    result: list[bool] = []

    def probe() -> None:
        got = portaudio_lock._PORTAUDIO_LOCK.acquire(blocking=False)
        if got:
            portaudio_lock._PORTAUDIO_LOCK.release()
        result.append(got)

    thread = threading.Thread(target=probe)
    thread.start()
    thread.join()
    return result[0]


class FakeSounddevice(types.ModuleType):
    """Records every PortAudio call and whether it was exposed to a teardown."""

    class PortAudioError(Exception):
        pass

    def __init__(self) -> None:
        super().__init__("sounddevice")
        self.calls: list[tuple[str, bool]] = []
        self.terminated = 0
        self.default = types.SimpleNamespace(device=[0, 1])
        self.playing = threading.Event()
        self.release_playback = threading.Event()
        self.release_playback.set()

    def _record(self, name: str) -> None:
        self.calls.append((name, _another_thread_could_reinitialise()))

    def exposed_calls(self) -> list[str]:
        return [name for name, exposed in self.calls if exposed]

    def play(self, data: Any, samplerate: int) -> None:
        self._record("play")
        self.playing.set()

    def wait(self) -> None:
        self._record("wait")
        self.release_playback.wait(5)
        self.playing.clear()

    def rec(self, frames: int, **_: Any) -> np.ndarray:
        self._record("rec")
        return np.zeros((frames, 1), np.float32)

    def get_stream(self) -> Any:
        # MicrophoneCapture polls the recording stream against a deadline
        # instead of trusting sd.wait(), which never returned on a device
        # that sent no frames. The fake recording is already finished.
        self._record("get_stream")
        return types.SimpleNamespace(active=False)

    def stop(self) -> None:
        self._record("stop")

    def query_devices(self, *_: Any, **__: Any) -> Any:
        self._record("query_devices")
        device = {"name": "fake mic", "max_input_channels": 1, "max_output_channels": 2,
                  "default_samplerate": 16000.0, "hostapi": 0}
        return device if _ else [device]

    def query_hostapis(self, *_: Any) -> dict:
        return {"name": "MME"}

    def _terminate(self) -> None:
        self.terminated += 1

    def _initialize(self) -> None:
        pass

    def InputStream(self, **_: Any) -> Any:  # noqa: N802 - mirrors sounddevice
        return types.SimpleNamespace(start=lambda: None, stop=lambda: None, close=lambda: None)


def _install(monkeypatch: pytest.MonkeyPatch) -> FakeSounddevice:
    sd = FakeSounddevice()
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    return sd


def _start_blocked_playback(sd: FakeSounddevice) -> threading.Thread:
    """Start a playback that stays in sd.wait() until released."""
    sd.release_playback.clear()
    thread = threading.Thread(target=portaudio_lock.play_and_wait, args=(np.zeros(10), 22050))
    thread.start()
    assert sd.playing.wait(5)
    return thread


class TestReinitialiseIfIdle:
    def test_reinitialises_when_nothing_is_playing(self, monkeypatch):
        sd = _install(monkeypatch)

        assert portaudio_lock.reinitialise_if_idle() is True
        assert sd.terminated == 1

    def test_never_tears_down_playback_in_progress(self, monkeypatch):
        sd = _install(monkeypatch)
        playback = _start_blocked_playback(sd)
        try:
            assert portaudio_lock.reinitialise_if_idle() is False
            assert sd.terminated == 0
        finally:
            sd.release_playback.set()
            playback.join(5)

    def test_does_not_wait_for_playback_to_finish(self, monkeypatch):
        """Recovery must not stall behind a long answer."""
        sd = _install(monkeypatch)
        playback = _start_blocked_playback(sd)
        try:
            done = threading.Event()
            threading.Thread(target=lambda: (portaudio_lock.reinitialise_if_idle(), done.set())).start()
            assert done.wait(1.0)
        finally:
            sd.release_playback.set()
            playback.join(5)


class TestMicrophoneRecoveryPath:
    def test_reopen_during_playback_does_not_tear_it_down(self, monkeypatch):
        """The path that re-initialised on every attempt from the second on."""
        from Agent_Guru.speech.wake_word_manager import _AudioCapture

        sd = _install(monkeypatch)
        playback = _start_blocked_playback(sd)
        try:
            capture = _AudioCapture(16_000, 0.5, "windows")
            capture.failing_since = 1.0
            capture.reopen_attempts = 1  # the next attempt is one that re-initialises

            assert capture._try_reopen_sounddevice() is True
            assert sd.terminated == 0
            assert sd.playing.is_set()
        finally:
            sd.release_playback.set()
            playback.join(5)

    def test_reopen_when_idle_still_re_enumerates_devices(self, monkeypatch):
        """A reconnected mic is only found after a re-initialise."""
        from Agent_Guru.speech.wake_word_manager import _AudioCapture

        sd = _install(monkeypatch)
        capture = _AudioCapture(16_000, 0.5, "windows")
        capture.failing_since = 1.0
        capture.reopen_attempts = 1

        assert capture._try_reopen_sounddevice() is True
        assert sd.terminated == 1


class TestEveryPortAudioUserHoldsTheLock:
    """Each production site, driven through its real code."""

    def test_filler_clip(self, monkeypatch):
        from Agent_Guru.speech import filler_response

        sd = _install(monkeypatch)
        cache = filler_response.FillerResponseCache()
        cache._cache = {filler_response._DEFAULT_LANG: [(np.zeros(100, np.float32), 22050)]}
        cache._initialized = True

        cache.play_filler("guru")

        assert [name for name, _ in sd.calls] == ["play", "wait"]
        assert sd.exposed_calls() == []

    def test_spoken_answer(self, monkeypatch):
        from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, Personality

        sd = _install(monkeypatch)
        orch = IntegrationOrchestrator(*([None] * 12))
        orch._tts_fn = lambda text, personality: (np.zeros(2205, np.float32), 22050)
        orch._tts_fn_type = "array"

        asyncio.run(orch._stage_tts("Paris is the capital of France.", Personality.GURU))

        assert [name for name, _ in sd.calls] == ["play", "wait"]
        assert sd.exposed_calls() == []

    def test_streamed_multi_sentence_answer(self, monkeypatch):
        """Streaming plays each sentence separately; every one must hold the lock."""
        from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, Personality

        sd = _install(monkeypatch)
        orch = IntegrationOrchestrator(*([None] * 12))
        orch._tts_fn = lambda text, personality: (np.zeros(2205, np.float32), 22050)
        orch._tts_fn_type = "array"
        reply = (
            "The capital of France is Paris, on the Seine. "
            "It has been the capital for over a thousand years. "
            "Would you like some tips for a short visit?"
        )

        result = asyncio.run(orch._stage_tts(reply, Personality.GURU))

        assert result.complete and result.spoken == 3
        assert [name for name, _ in sd.calls] == ["play", "wait"] * 3
        assert sd.exposed_calls() == []

    def test_microphone_capture_recording_and_listing(self, monkeypatch):
        from Agent_Guru.speech.audio.capture import MicrophoneCapture

        sd = _install(monkeypatch)
        mic = MicrophoneCapture(sample_rate=16_000, device=0)
        mic.capture(0.1)
        MicrophoneCapture.list_devices()

        assert [name for name, _ in sd.calls] == [
            "query_devices", "rec", "get_stream", "wait", "query_devices"]
        assert sd.exposed_calls() == []

    def test_audio_pipeline_device_query(self, monkeypatch):
        from Agent_Guru.speech.audio.pipeline import AudioPipeline

        sd = _install(monkeypatch)
        AudioPipeline._query_devices(AudioPipeline.__new__(AudioPipeline))

        assert [name for name, _ in sd.calls] == ["query_devices"]
        assert sd.exposed_calls() == []

    def test_platform_integration_device_list(self, monkeypatch):
        from Agent_Guru.speech.platform_integration import PlatformIntegration

        sd = _install(monkeypatch)
        PlatformIntegration().list_audio_devices()

        assert [name for name, _ in sd.calls] == ["query_devices"]
        assert sd.exposed_calls() == []
