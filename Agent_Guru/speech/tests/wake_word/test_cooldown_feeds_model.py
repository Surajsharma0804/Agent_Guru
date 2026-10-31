"""openWakeWord keeps hearing the audio during the wake cooldown; only the wake is held back.

The detector used to return before the model saw a cooldown chunk. The model scores a rolling
window of the last second or so, so a phrase that began inside the cooldown reached it with its
start missing, and a phrase just after a cooldown was scored spliced onto audio from before the
gap. Through the assistant's detector that missed 3 of the owner's 16 held-back takes, which
the same model caught when fed every frame. The fake model here fires, like the real one, only
once it has heard most of the phrase in consecutive frames.
"""

from __future__ import annotations

import types

import numpy as np

import Agent_Guru.speech.audio.wake_word as ww
from Agent_Guru.speech.audio.wake_word import WakeWordConfig, WakeWordDetector
from Agent_Guru.speech.models import PersonalityType

SR, CHUNK_S = 16000, 1.5
FRAMES_TO_FIRE = 16  # 1.28 s of the phrase in a row


class PhraseModel:
    """Scores 1.0 once FRAMES_TO_FIRE loud frames have arrived in a row, else 0."""

    def __init__(self, always: float | None = None) -> None:
        self.run, self.calls, self.always = 0, 0, always

    def predict(self, frame: np.ndarray) -> dict[str, float]:
        self.calls += 1
        self.run = self.run + 1 if np.abs(frame).mean() > 8000 else 0
        if self.always is not None:
            return {"hey_guru": self.always}
        return {"hey_guru": 1.0 if self.run >= FRAMES_TO_FIRE else 0.0}

    def reset(self) -> None:
        self.run = 0


def _detector(monkeypatch, clock: list[float], model: PhraseModel) -> WakeWordDetector:
    monkeypatch.setattr(ww, "time", types.SimpleNamespace(time=lambda: clock[0]))
    det = WakeWordDetector(WakeWordConfig(wake_words={"hey guru": PersonalityType.GURU}, cooldown_seconds=3.0))
    det._backend, det._oww_model, det._oww_phrases = "openwakeword", model, {"hey_guru": "hey guru"}
    return det


async def test_a_phrase_that_starts_inside_the_cooldown_still_wakes_it(monkeypatch):
    # Woken at t=0; the next phrase runs from 0.9 s to 2.5 s, so it starts in the first chunk,
    # which is inside the 3 s cooldown, and ends in the second, which is not.
    audio = np.zeros(int(SR * 2 * CHUNK_S), dtype=np.float32)
    audio[int(SR * 0.9):int(SR * 2.5)] = 0.5
    clock = [0.0]
    det = _detector(monkeypatch, clock, PhraseModel())
    det._last_detection_time = 0.0
    found = []
    for i in range(2):
        n = int(SR * CHUNK_S)
        clock[0] = (i + 1) * CHUNK_S
        found.append(await det.detect(audio[i * n:(i + 1) * n]))
    assert found[0] is None  # inside the cooldown
    assert found[1] is not None and found[1].wake_word == "hey guru"


async def test_the_cooldown_still_holds_back_a_second_wake(monkeypatch):
    clock = [1.5]
    model = PhraseModel(always=1.0)
    det = _detector(monkeypatch, clock, model)
    det._last_detection_time = 0.0
    assert await det.detect(np.full(int(SR * CHUNK_S), 0.5, dtype=np.float32)) is None
    assert model.calls == int(SR * CHUNK_S) // 1280  # every whole frame was heard
