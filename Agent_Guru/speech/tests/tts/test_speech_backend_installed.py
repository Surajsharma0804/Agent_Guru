"""The assistant's voice must be installed, not quietly replaced.

kokoro-onnx was missing from pyproject.toml, so a fresh install had no TTS
package. Speech fell back to the pyttsx3 voice with a warning, or to silence
where pyttsx3 is missing, and nothing in the suite noticed, because every TTS
test degrades to that fallback or skips. These tests fail instead.
"""

from __future__ import annotations

import sys

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
