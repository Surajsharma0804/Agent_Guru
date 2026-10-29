"""The wake cooldown starts again when a turn ends, not only when the wake word was heard.

It counted from detection alone. Every turn outlasts the 3 s cooldown, so the
first chunk read after a turn could wake the assistant straight away, and that
chunk is often audio the stream held during the turn, the end of the spoken
reply among it. This runs the real listen loop and the real MFCC detector on a
clock that the turn moves on by 30 s.
"""

from __future__ import annotations

import asyncio
import types

import numpy as np

import Agent_Guru.speech.audio.wake_word as ww
from Agent_Guru.speech import wake_word_manager as wwm
from Agent_Guru.speech.audio.wake_word import WakeWordConfig
from Agent_Guru.speech.models import PersonalityType

SR = 16000
TURN_S = 30.0


def _loud(seconds: float) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    return (0.2 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)


class Capture:
    """Loud audio in 1.5 s chunks; each read moves the clock on by its length."""

    failing_since = None
    reopen_attempts = 0

    def __init__(self, clock: list[float], reads: int, manager: wwm.WakeWordManager) -> None:
        self.clock, self.left, self.manager = clock, reads, manager

    def capture(self, seconds: float | None = None) -> np.ndarray:
        self.left -= 1
        if self.left <= 0:
            self.manager._is_listening = False
        self.clock[0] += seconds or 1.5
        return _loud(seconds or 1.5)

    def close(self) -> None:
        pass


async def _wakes(monkeypatch, reads: int) -> list[float]:
    clock = [1000.0]
    monkeypatch.setattr(ww, "time", types.SimpleNamespace(time=lambda: clock[0]))
    woke: list[float] = []

    async def on_wake(detection) -> None:
        woke.append(clock[0])
        clock[0] += TURN_S

    manager = wwm.WakeWordManager(
        wwm.WakeWordManagerConfig(
            wake_word_config=WakeWordConfig(cooldown_seconds=3.0),
            platform="windows",
            sleep_poll_interval=0.0,
            on_detection_callback=on_wake,
        ),
    )
    manager._detector = ww.WakeWordDetector(manager._config.wake_word_config)
    manager._detector._backend = "mfcc"
    monkeypatch.setattr(
        manager._detector, "_match_phrase_by_spectrum", lambda audio: ("hey guru", PersonalityType.GURU),
    )
    manager._audio_capture = Capture(clock, reads, manager)
    manager._initialized = manager._is_listening = True
    await asyncio.wait_for(manager._listen_loop(), timeout=30)
    return woke


async def test_the_chunk_read_right_after_a_turn_does_not_wake_it(monkeypatch):
    woke = await _wakes(monkeypatch, reads=2)
    assert len(woke) == 1, woke


async def test_it_wakes_again_once_the_cooldown_after_the_turn_has_passed(monkeypatch):
    # Read 2 ends 1.5 s after the turn, inside the 3 s cooldown; read 3 ends
    # 3.0 s after, when it has run out.
    woke = await _wakes(monkeypatch, reads=3)
    assert len(woke) == 2, woke
    assert woke[1] - (woke[0] + TURN_S) >= 3.0
