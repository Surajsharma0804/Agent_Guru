"""While muted the microphone is closed: nothing is read, woken on, captured or recorded.

There was no way to stop the assistant listening short of quitting it, and the loudness-gate wake
detector started turns on room talk and the TV (5 in 5.2 minutes in the live run). The real listen
loop and MFCC detector run here; the input stream is a fake that counts opens, reads and closes,
and its audio is loud enough to wake the detector every time.
"""

from __future__ import annotations

import asyncio

import numpy as np

from Agent_Guru.speech import wake_word_manager as wwm
from Agent_Guru.speech.audio.wake_word import WakeWordConfig, WakeWordDetector
from Agent_Guru.speech.models import PersonalityType

SR = 16000


class Stream:
    """One opened input stream. Every read returns 0.5 s of a loud tone (the MFCC gate needs 0.3 s)."""

    made: list[Stream] = []
    on_read = None

    def __init__(self, sample_rate, duration, platform_name) -> None:
        self.opened = self.closed = False
        self.reads = 0
        self.failing_since = None
        self.reopen_attempts = 0
        Stream.made.append(self)

    def open(self) -> None:
        self.opened = True

    def capture(self, seconds=None) -> np.ndarray:
        assert self.opened and not self.closed, "read from a stream that is not open"
        self.reads += 1
        if Stream.on_read is not None:
            Stream.on_read()
        t = np.arange(int(SR * 0.5)) / SR
        return (0.2 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)

    def close(self) -> None:
        self.closed = True


async def _manager(monkeypatch, wakes: list):
    Stream.made, Stream.on_read = [], None
    monkeypatch.setattr(wwm, "_AudioCapture", Stream)

    async def on_wake(detection) -> None:
        wakes.append(detection)

    manager = wwm.WakeWordManager(wwm.WakeWordManagerConfig(
        wake_word_config=WakeWordConfig(cooldown_seconds=0.0), platform="windows",
        audio_capture_duration=0.25, sleep_poll_interval=0.0, on_detection_callback=on_wake,
    ))
    manager._detector = WakeWordDetector(manager._config.wake_word_config)
    manager._detector._backend = "mfcc"
    monkeypatch.setattr(manager._detector, "_match_phrase_by_spectrum", lambda a: ("hey guru", PersonalityType.GURU))
    manager._initialized = True
    return manager


async def _listen_for(manager, seconds: float) -> None:
    manager._is_listening = True
    task = asyncio.create_task(manager._listen_loop())
    await asyncio.sleep(seconds)
    manager._is_listening = False
    await asyncio.wait_for(task, timeout=5)


async def test_a_new_session_starts_listening():
    assert wwm.WakeWordManager(wwm.WakeWordManagerConfig(platform="windows")).muted is False


async def test_muted_the_stream_is_never_opened_or_read_and_nothing_wakes(monkeypatch):
    wakes: list = []
    manager = await _manager(monkeypatch, wakes)
    manager.set_muted(True)
    await _listen_for(manager, 0.3)
    assert wakes == []
    assert all(s.reads == 0 for s in Stream.made)
    assert manager._audio_capture is None


async def test_muting_while_listening_closes_the_stream_and_unmuting_opens_a_new_one(monkeypatch):
    wakes: list = []
    manager = await _manager(monkeypatch, wakes)
    await _listen_for(manager, 0.2)
    assert wakes, "the fake audio should wake it while unmuted"
    first = Stream.made[-1]

    manager.set_muted(True)
    woke_before = len(wakes)
    await _listen_for(manager, 0.3)
    assert first.closed and manager._audio_capture is None
    reads_while_muted = first.reads
    await _listen_for(manager, 0.2)
    assert first.reads == reads_while_muted and len(wakes) == woke_before

    manager.set_muted(False)
    await _listen_for(manager, 0.2)
    assert Stream.made[-1] is not first and Stream.made[-1].opened and len(wakes) > woke_before


async def test_audio_read_as_the_mute_arrives_is_not_heard(monkeypatch):
    wakes: list = []
    manager = await _manager(monkeypatch, wakes)
    Stream.on_read = lambda: manager.set_muted(True)  # muted during the very first read
    await _listen_for(manager, 0.3)
    assert wakes == []
    assert Stream.made[0].reads == 1 and Stream.made[0].closed


async def test_muted_no_command_is_captured_and_detect_hears_nothing(monkeypatch):
    wakes: list = []
    manager = await _manager(monkeypatch, wakes)
    manager._audio_capture = Stream(SR, 0.25, "windows")
    manager._audio_capture.open()
    manager.set_muted(True)
    assert await manager.capture_command_audio(chunks=2, seconds=0.25) == b""
    assert await manager.detect() is None
    assert manager._audio_capture.reads == 0


def _api(monkeypatch, microphone):
    import secrets
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from Agent_Guru.integration import local_api

    key = secrets.token_urlsafe(24)  # made per run: the secret scan refuses a literal key
    monkeypatch.setattr(local_api, "owner_key", lambda **k: key)
    orch = SimpleNamespace(events=SimpleNamespace(publish=lambda *a, **k: None), microphone=microphone)
    return TestClient(local_api.create_app(orch)), {"X-API-Key": key}


def test_the_owner_mutes_and_unmutes_through_the_local_api(monkeypatch):
    manager = wwm.WakeWordManager(wwm.WakeWordManagerConfig(platform="windows"))
    http, auth = _api(monkeypatch, manager)
    assert http.post("/v1/mic", json={"muted": True}, headers=auth).json() == {"microphone": "muted"}
    assert manager.muted and http.get("/v1/status", headers=auth).json()["microphone"] == "muted"
    assert http.post("/v1/mic", json={"muted": False}, headers=auth).json() == {"microphone": "listening"}
    assert not manager.muted


def test_muting_needs_the_owners_key(monkeypatch):
    manager = wwm.WakeWordManager(wwm.WakeWordManagerConfig(platform="windows"))
    http, _ = _api(monkeypatch, manager)
    assert http.post("/v1/mic", json={"muted": True}).status_code in (401, 403)
    assert not manager.muted


def test_with_nothing_listening_the_api_says_so(monkeypatch):
    http, auth = _api(monkeypatch, None)
    answer = http.post("/v1/mic", json={"muted": True}, headers=auth)
    assert answer.status_code == 409 and answer.json()["microphone"] == "none"
