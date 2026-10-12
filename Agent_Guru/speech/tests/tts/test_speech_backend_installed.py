"""The assistant's voice must be installed, not quietly replaced.

kokoro-onnx was missing from pyproject.toml, so a fresh install had no TTS
package. Speech fell back to the pyttsx3 voice with a warning, or to silence
where pyttsx3 is missing, and nothing in the suite noticed, because every TTS
test degrades to that fallback or skips. These tests fail instead.
"""

from __future__ import annotations

import os
import subprocess  # nosec B404 - runs this interpreter on a fixed script
import sys

import pytest

from Agent_Guru.speech.tts import tts_engine


def test_kokoro_onnx_is_installed():
    """A plain import, not importorskip: a missing voice is a failure."""
    import kokoro_onnx  # noqa: F401


def test_espeak_loads_and_turns_text_into_phonemes():
    """kokoro-onnx needs the espeak-ng native library, which a bare import does not load."""
    from kokoro_onnx.tokenizer import Tokenizer

    phonemes = Tokenizer().phonemize("hello there", "en-us")

    assert phonemes.strip()


def test_backend_is_not_reported_as_kokoro_when_the_package_is_missing(monkeypatch, tmp_path):
    """active_backend used to look at the model files only.

    With the model on disk and kokoro-onnx not installed it said "kokoro"
    while every call fell back to pyttsx3 or silence.
    """
    model, voices = tmp_path / "kokoro-v1.0.onnx", tmp_path / "voices-v1.0.bin"
    model.write_bytes(b"x")
    voices.write_bytes(b"x")
    monkeypatch.setattr(tts_engine, "_MODEL_PATH", model)
    monkeypatch.setattr(tts_engine, "_VOICES_PATH", voices)
    monkeypatch.setitem(sys.modules, "kokoro_onnx", None)

    assert tts_engine.TTSEngine().active_backend != "kokoro"


def test_backend_is_kokoro_when_package_and_model_are_present(monkeypatch, tmp_path):
    model, voices = tmp_path / "kokoro-v1.0.onnx", tmp_path / "voices-v1.0.bin"
    model.write_bytes(b"x")
    voices.write_bytes(b"x")
    monkeypatch.setattr(tts_engine, "_MODEL_PATH", model)
    monkeypatch.setattr(tts_engine, "_VOICES_PATH", voices)

    assert tts_engine.TTSEngine().active_backend == "kokoro"


def test_espeak_data_is_pointed_at_when_the_loader_library_is_loaded(monkeypatch):
    import espeakng_loader

    monkeypatch.delenv("ESPEAK_DATA_PATH", raising=False)
    maps = "7f00-7f10 r-xp 0 08:01 1 " + os.path.realpath(espeakng_loader.get_library_path())
    assert tts_engine._espeak_data_for_loaded_library("linux", maps) == espeakng_loader.get_data_path()  # nosec B101


def test_espeak_data_is_left_alone_otherwise(monkeypatch):
    """A system eSpeak NG keeps its own data; other platforms do not use eSpeak through pyttsx3."""
    import espeakng_loader

    loaded = os.path.realpath(espeakng_loader.get_library_path())
    monkeypatch.delenv("ESPEAK_DATA_PATH", raising=False)
    assert tts_engine._espeak_data_for_loaded_library("linux", "/usr/lib/libespeak-ng.so.1") is None  # nosec B101
    assert tts_engine._espeak_data_for_loaded_library("win32", loaded) is None  # nosec B101
    monkeypatch.setenv("ESPEAK_DATA_PATH", "/usr/share/espeak-ng-data")
    assert tts_engine._espeak_data_for_loaded_library("linux", loaded) is None  # nosec B101


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="pyttsx3 uses eSpeak NG only on Linux")
def test_pyttsx3_fallback_after_kokoro_does_not_end_the_process():
    """eSpeak NG calls exit(1) when it cannot find its data, and pyttsx3 does not stop it.

    Before the fix every CI run (Python 3.11, 3.12, 3.13) died here with
    exit code 1 and no report. Run in a child so a regression fails this
    test instead of ending the suite.
    """
    child = "\n".join([
        "import ctypes, espeakng_loader",
        # What Kokoro's phonemizer does before any fallback can happen.
        "ctypes.CDLL(espeakng_loader.get_library_path(), mode=ctypes.RTLD_GLOBAL)",
        "from Agent_Guru.speech.tts.tts_engine import _Pyttsx3Engine",
        "print('initialized', _Pyttsx3Engine().initialize())",
    ])
    env = {k: v for k, v in os.environ.items() if k != "ESPEAK_DATA_PATH"}
    done = subprocess.run([sys.executable, "-c", child], env=env, capture_output=True, text=True, timeout=25)  # nosec B603
    assert done.returncode == 0, done.stderr[-500:]  # nosec B101
    assert "initialized" in done.stdout  # nosec B101
