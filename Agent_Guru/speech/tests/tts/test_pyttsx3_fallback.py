"""The pyttsx3 fallback voice speaks every sentence and never hangs the caller.

In-process, pyttsx3 2.99 on Windows SAPI5 returned from the first
save_to_file + runAndWait and blocked for ever in startLoop on the second.
The fallback voice spoke one sentence and froze the speaking thread; on
the Windows CI runners pytest-timeout then ended the whole test run.
"""

from __future__ import annotations

import subprocess
import time

import pytest

from Agent_Guru.speech.models import PersonalityType
from Agent_Guru.speech.tts import tts_engine
from Agent_Guru.speech.tts.tts_engine import _Pyttsx3Engine


def _engine_with_voices() -> _Pyttsx3Engine:
    engine = _Pyttsx3Engine()
    if not engine.initialize():
        pytest.skip("UNVERIFIED on this host: pyttsx3 has no voice here")
    return engine


def test_every_sentence_is_spoken_not_only_the_first():
    engine = _engine_with_voices()
    for i in range(3):
        started = time.perf_counter()
        wav = engine.synthesize(f"Sentence number {i}.", PersonalityType.GURU)
        assert wav[:4] == b"RIFF" and len(wav) > 1000  # nosec B101
        assert time.perf_counter() - started < 10  # nosec B101


def test_a_stalled_synthesis_is_ended_and_gives_silence(monkeypatch):
    engine = _Pyttsx3Engine()
    engine._engine = object()  # initialised; the child process does the work
    monkeypatch.setattr(tts_engine, "_PYTTSX3_SCRIPT", "import time\ntime.sleep(60)\n")
    monkeypatch.setattr(tts_engine, "_PYTTSX3_BASE_TIMEOUT_S", 1.0)
    monkeypatch.setattr(tts_engine, "_PYTTSX3_CHARS_PER_S", 1e9)
    started = time.perf_counter()
    wav = engine.synthesize("Hello there.", PersonalityType.MAYA)
    assert time.perf_counter() - started < 10  # nosec B101
    assert wav == tts_engine._silence_wav("Hello there.")  # nosec B101


def test_the_text_goes_on_stdin_not_on_the_command_line(monkeypatch):
    engine = _Pyttsx3Engine()
    engine._engine = object()
    seen = {}

    def run(args, **kwargs):
        seen["args"], seen["input"] = args, kwargs.get("input")
        return subprocess.CompletedProcess(args, 1, b"", b"stopped by the test")

    monkeypatch.setattr(subprocess, "run", run)
    text = 'say "; rm -rf ~" & other text'
    engine.synthesize(text, PersonalityType.GURU)
    assert text not in " ".join(seen["args"])  # nosec B101
    assert seen["input"] == text.encode("utf-8")  # nosec B101


def test_a_failed_child_gives_silence_not_an_exception(monkeypatch):
    engine = _Pyttsx3Engine()
    engine._engine = object()
    monkeypatch.setattr(tts_engine, "_PYTTSX3_SCRIPT", "import sys\nsys.exit(3)\n")
    assert engine.synthesize("Hi.", PersonalityType.GURU) == tts_engine._silence_wav("Hi.")  # nosec B101
