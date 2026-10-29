"""A wake backend is chosen only when it can hear the configured wake words, and the log says why.

openWakeWord was chosen whenever the package was installed, with the stock
hey_jarvis model standing in for "hey guru"; it caught 0 of 28 recorded wake
phrases, so installing it made the assistant deaf and the log said only
"backend=openwakeword". Porcupine likewise fell back to "computer". The fake
openWakeWord here records what it was asked to load and scores what it is told.
"""

from __future__ import annotations

import logging
import types
from pathlib import Path

import numpy as np
import pytest

import Agent_Guru.speech.audio.wake_word as ww
from Agent_Guru.speech.audio.wake_word import WakeWordConfig, WakeWordDetector
from Agent_Guru.speech.models import PersonalityType


class FakeOWW:
    loaded: list[list[str]] = []
    scores: dict[str, float] = {}
    fail: Exception | None = None

    def __init__(self, wakeword_models=None, inference_framework="onnx") -> None:
        if FakeOWW.fail is not None:
            raise FakeOWW.fail
        FakeOWW.loaded.append(list(wakeword_models or []))
        self.names = [Path(m).stem for m in wakeword_models or ["hey_jarvis_v0.1"]]

    def predict(self, chunk):
        return {name: FakeOWW.scores.get(name, 0.0) for name in self.names}


@pytest.fixture
def oww(monkeypatch):
    FakeOWW.loaded, FakeOWW.scores, FakeOWW.fail = [], {}, None
    monkeypatch.setattr(ww, "_HAS_OWW", True)
    monkeypatch.setattr(ww, "OWWModel", FakeOWW, raising=False)
    monkeypatch.setattr(ww, "_HAS_PORCUPINE", False)
    monkeypatch.setattr(ww, "_HAS_VOSK", False)
    return FakeOWW


def _detector(folder: Path, caplog) -> WakeWordDetector:
    with caplog.at_level(logging.INFO, logger=ww.__name__):
        return WakeWordDetector(WakeWordConfig(oww_model_dir=str(folder), cooldown_seconds=0.0))


def _startup_line(caplog) -> str:
    (line,) = [r.getMessage() for r in caplog.records if "WakeWordDetector initialised" in r.getMessage()]
    return line


def test_installed_without_a_model_for_the_wake_words_is_not_chosen(oww, tmp_path, caplog):
    (tmp_path / "hey_jarvis.onnx").write_bytes(b"stock")  # not one of the wake words
    det = _detector(tmp_path, caplog)
    assert det._backend == "mfcc"
    assert oww.loaded == []
    line = _startup_line(caplog)
    assert "hey_guru.onnx" in line and "hey_maya.onnx" in line and str(tmp_path) in line
    assert "wakes on any loud sound" in line


def test_a_model_named_after_a_wake_word_is_chosen_and_said(oww, tmp_path, caplog):
    (tmp_path / "hey_guru.onnx").write_bytes(b"model")
    det = _detector(tmp_path, caplog)
    assert det._backend == "openwakeword"
    assert oww.loaded == [[str(tmp_path / "hey_guru.onnx")]]
    line = _startup_line(caplog)
    assert "backend=openwakeword" in line and "hey guru" in line
    assert "none for" in line and "hey maya" in line


async def test_the_model_that_fires_names_the_wake_word(oww, tmp_path, caplog, monkeypatch):
    for name in ("hey_guru", "hey_maya"):
        (tmp_path / f"{name}.onnx").write_bytes(b"model")
    det = _detector(tmp_path, caplog)
    monkeypatch.setattr(det, "_transcribe_wake_word", lambda audio: pytest.fail("Whisper is not needed"))
    oww.scores = {"hey_maya": 0.9, "hey_guru": 0.2}
    found = await det.detect(np.zeros(1280 * 3, np.float32))
    assert found is not None
    assert (found.wake_word, found.personality) == ("hey maya", PersonalityType.MAYA)


async def test_a_low_score_wakes_nothing(oww, tmp_path, caplog):
    (tmp_path / "hey_guru.onnx").write_bytes(b"model")
    det = _detector(tmp_path, caplog)
    oww.scores = {"hey_guru": 0.1}
    assert await det.detect(np.zeros(1280 * 3, np.float32)) is None


def test_a_model_that_does_not_load_falls_back_and_says_why(oww, tmp_path, caplog):
    (tmp_path / "hey_guru.onnx").write_bytes(b"damaged")
    oww.fail = RuntimeError("INVALID_PROTOBUF")
    det = _detector(tmp_path, caplog)
    assert det._backend == "mfcc"
    assert "could not load hey_guru.onnx: INVALID_PROTOBUF" in _startup_line(caplog)


def test_not_installed_says_so(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(ww, "_HAS_OWW", False)
    monkeypatch.setattr(ww, "_HAS_PORCUPINE", False)
    monkeypatch.setattr(ww, "_HAS_VOSK", False)
    (tmp_path / "hey_guru.onnx").write_bytes(b"model")
    det = _detector(tmp_path, caplog)
    assert det._backend == "mfcc"
    assert "openwakeword not installed" in _startup_line(caplog)


def test_porcupine_without_a_keyword_for_the_wake_words_is_not_chosen(oww, tmp_path, caplog, monkeypatch):
    monkeypatch.setattr(ww, "_HAS_PORCUPINE", True)
    monkeypatch.setattr(ww, "pvporcupine", types.SimpleNamespace(KEYWORDS={"computer", "jarvis"}), raising=False)
    with caplog.at_level(logging.INFO, logger=ww.__name__):
        det = WakeWordDetector(WakeWordConfig(oww_model_dir=str(tmp_path), porcupine_access_key="test-key"))
    assert det._backend == "mfcc"
    assert "porcupine has no built-in keyword" in _startup_line(caplog)
