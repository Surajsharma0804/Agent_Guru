"""KokoroTTSEngine's use_gpu flag must decide where synthesis runs.

It used to be stored and never read. Kokoro(model, voices) ran on the CPU
unless onnxruntime-gpu was installed, and then took every provider on offer,
so use_gpu=True did nothing and use_gpu=False did not guarantee the CPU.

These tests replace onnxruntime and kokoro_onnx with fakes that record what
the engine asks for, so they run the same on machines with and without a GPU.
"""

from __future__ import annotations

import logging
import sys
import types
from typing import TYPE_CHECKING

from Agent_Guru.speech.tts import tts_engine

if TYPE_CHECKING:
    import pytest


class FakeSession:
    def __init__(self, path: str, providers: list[str], available: list[str]) -> None:
        self.requested = providers
        self._granted = [p for p in providers if p in available]

    def get_providers(self) -> list[str]:
        return self._granted


def _install(monkeypatch: pytest.MonkeyPatch, tmp_path, available: list[str]) -> dict:
    seen: dict = {"preloaded": 0, "session": None, "constructed_directly": False}
    ort = types.ModuleType("onnxruntime")
    ort.get_available_providers = lambda: list(available)

    def inference_session(path, providers):
        seen["session"] = FakeSession(path, providers, available)
        return seen["session"]

    ort.InferenceSession = inference_session

    def preload_dlls():
        seen["preloaded"] += 1

    ort.preload_dlls = preload_dlls

    kokoro = types.ModuleType("kokoro_onnx")

    class Kokoro:
        def __init__(self, *args, **kwargs) -> None:
            seen["constructed_directly"] = True

        @classmethod
        def from_session(cls, session, voices_path):
            return cls.__new__(cls)

    kokoro.Kokoro = Kokoro
    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    monkeypatch.setitem(sys.modules, "kokoro_onnx", kokoro)

    model, voices = tmp_path / "kokoro-v1.0.onnx", tmp_path / "voices-v1.0.bin"
    model.write_bytes(b"model")
    voices.write_bytes(b"voices")
    monkeypatch.setattr(tts_engine, "_MODEL_PATH", model)
    monkeypatch.setattr(tts_engine, "_VOICES_PATH", voices)
    # The engine loads only pinned files; these stand-ins are pinned here,
    # since this test is about providers, not integrity (test_kokoro_pins.py).
    import hashlib

    from Agent_Guru.utils.verified_files import PinnedFile

    pins = tuple(PinnedFile(f.name, f.stat().st_size, hashlib.sha256(f.read_bytes()).hexdigest()) for f in (model, voices))
    monkeypatch.setattr(tts_engine, "KOKORO_PINS", pins)
    monkeypatch.setattr(tts_engine, "_PINS_BY_NAME", {p.name: p for p in pins})
    return seen


CUDA = ["CUDAExecutionProvider", "CPUExecutionProvider"]
CPU_ONLY = ["CPUExecutionProvider"]


def _load(use_gpu: bool) -> tts_engine.KokoroTTSEngine:
    engine = tts_engine.KokoroTTSEngine(use_gpu=use_gpu)
    engine._ensure_loaded()
    return engine


def test_gpu_requested_and_available_runs_on_cuda(monkeypatch, tmp_path):
    seen = _install(monkeypatch, tmp_path, CUDA)

    engine = _load(use_gpu=True)

    assert seen["session"].requested[0] == "CUDAExecutionProvider"
    assert seen["preloaded"] == 1
    assert engine.device == "cuda"


def test_gpu_requested_on_a_cpu_only_build_says_so_and_uses_the_cpu(monkeypatch, tmp_path, caplog):
    seen = _install(monkeypatch, tmp_path, CPU_ONLY)

    with caplog.at_level(logging.WARNING):
        engine = _load(use_gpu=True)

    assert seen["session"].requested == ["CPUExecutionProvider"]
    assert engine.device == "cpu"
    assert "CPU-only" in caplog.text


def test_gpu_not_requested_stays_on_the_cpu_even_with_a_gpu_build(monkeypatch, tmp_path):
    """Kokoro(model, voices) would have taken the GPU here regardless of use_gpu."""
    seen = _install(monkeypatch, tmp_path, CUDA)

    engine = _load(use_gpu=False)

    assert seen["session"].requested == ["CPUExecutionProvider"]
    assert seen["preloaded"] == 0
    assert engine.device == "cpu"


def test_the_model_is_not_loaded_through_the_provider_guessing_constructor(monkeypatch, tmp_path):
    seen = _install(monkeypatch, tmp_path, CUDA)

    _load(use_gpu=True)

    assert not seen["constructed_directly"]
