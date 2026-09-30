"""GPUResourcePool must say why it runs on the CPU, not claim there is no GPU.

It logged "no CUDA device - CPU-only mode" whenever torch could not see CUDA.
A clean install gets PyPI's CPU-only torch, so on an RTX 2050 laptop that
Ollama and CTranslate2 were both using, the log said there was no GPU.
"""

from __future__ import annotations

import sys
import types

import pytest

from Agent_Guru.integration import gpu_pool


def _torch(cuda: str | None) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        __version__="2.14.0+cpu" if cuda is None else "2.14.0+cu128",
        version=types.SimpleNamespace(cuda=cuda),
    )


@pytest.fixture
def cuda_devices(monkeypatch: pytest.MonkeyPatch):
    def set_count(n: int) -> None:
        fake = types.SimpleNamespace(get_cuda_device_count=lambda: n)
        monkeypatch.setitem(sys.modules, "ctranslate2", fake)

    return set_count


def test_cpu_build_on_a_gpu_machine_says_so(cuda_devices) -> None:
    cuda_devices(1)
    message = gpu_pool._cpu_mode_reason(_torch(None))
    assert "CPU-only build" in message
    assert "1 CUDA device(s) are present" in message
    assert "no CUDA device" not in message


def test_cpu_build_without_a_gpu_says_no_device(cuda_devices) -> None:
    cuda_devices(0)
    message = gpu_pool._cpu_mode_reason(_torch(None))
    assert "CPU-only build" in message
    assert "no CUDA device was found" in message


def test_cuda_build_that_sees_no_device_names_the_build(cuda_devices) -> None:
    """A CUDA torch that still finds nothing is a driver or hardware problem."""
    cuda_devices(1)
    message = gpu_pool._cpu_mode_reason(_torch("12.8"))
    assert "torch has CUDA 12.8" in message
    assert "CPU-only build" not in message


def test_pool_log_does_not_deny_a_present_gpu(
    cuda_devices, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The line an operator actually reads at startup, from the pool itself."""
    import logging

    cuda_devices(1)
    torch = _torch(None)
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    monkeypatch.setitem(sys.modules, "torch", torch)
    with caplog.at_level(logging.INFO, logger=gpu_pool.logger.name):
        pool = gpu_pool.GPUResourcePool()
    assert pool.device == "cpu"
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "no CUDA device - CPU-only mode" not in text
    assert "CUDA device(s) are present" in text


def test_startup_banner_does_not_deny_a_gpu() -> None:
    """main.py printed "CPU-only (no CUDA GPU detected)" from the torch pool.

    With PyPI's CPU-only torch that line sat directly under the pool's own line
    saying a CUDA device was present.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parents[3] / "main.py").read_text(encoding="utf-8")
    code = [line for line in source.splitlines() if not line.lstrip().startswith("#")]
    assert not [line for line in code if "no CUDA GPU detected" in line]
