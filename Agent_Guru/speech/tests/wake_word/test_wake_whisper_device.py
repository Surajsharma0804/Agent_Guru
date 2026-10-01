"""The wake detector's own Whisper tiny must go through the CUDA guard.

It chose CUDA with torch.cuda.is_available() and trusted the load. With a
CUDA torch build but no CUDA 12 libraries (the README's cu118 install), and
any earlier failed CUDA attempt in the process, its first transcription hung
inside CTranslate2's encode(); measured, the watchdog had to kill it. It only
escaped in production because main.py injects a pre-loaded model.
"""

from __future__ import annotations

import sys
import types

import numpy as np
import pytest

from Agent_Guru.speech.audio.wake_word import WakeWordConfig, WakeWordDetector

CUBLAS_MISSING = "Library cublas64_12.dll is not found or cannot be loaded"


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch):
    """Fake WhisperModel, a GPU present, torch claiming CUDA as a cu118 build does."""
    import faster_whisper

    from Agent_Guru.speech.stt import whisper_stt

    state = {"cuda_runs": True}
    built: list[str] = []

    class FakeModel:
        def __init__(self, model_id, device, compute_type, **kwargs):
            self.device = device
            built.append(device)

        def transcribe(self, audio, **kwargs):
            if self.device == "cuda" and not state["cuda_runs"]:
                raise RuntimeError(CUBLAS_MISSING)
            return iter([types.SimpleNamespace(text="hey guru")]), None

    monkeypatch.setattr(faster_whisper, "WhisperModel", FakeModel)
    monkeypatch.setattr(whisper_stt, "_cuda_device_count", lambda: 1)
    monkeypatch.setattr(whisper_stt, "_add_nvidia_runtime_to_path", lambda: [])
    monkeypatch.setattr(whisper_stt, "_cuda_failure", None)
    fake_torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: True))
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    return state, built


def _transcribe() -> tuple[WakeWordDetector, str]:
    det = WakeWordDetector(WakeWordConfig())
    return det, det._transcribe_wake_word(np.zeros(16000, dtype=np.float32))


def test_no_cuda_attempt_after_an_earlier_failure(env) -> None:
    """The retry that hung: CUDA had already failed once in this process."""
    from Agent_Guru.speech.stt import whisper_stt

    _, built = env
    whisper_stt._cuda_failure = f"RuntimeError: {CUBLAS_MISSING}"
    _, text = _transcribe()
    assert built == ["cpu"]
    assert text == "hey guru"


def test_cuda_that_cannot_run_falls_back_and_is_recorded(env) -> None:
    from Agent_Guru.speech.stt import whisper_stt

    state, built = env
    state["cuda_runs"] = False
    det, text = _transcribe()
    assert built == ["cuda", "cpu"]
    assert det._whisper_tiny.device == "cpu"
    assert text == "hey guru"
    assert "cublas64_12.dll" in (whisper_stt.cuda_failure() or "")


def test_working_cuda_is_used(env) -> None:
    _, built = env
    det, text = _transcribe()
    assert built == ["cuda"]
    assert det._whisper_tiny.device == "cuda"
    assert text == "hey guru"
