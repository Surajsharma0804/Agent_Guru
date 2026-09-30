"""_init_subsystem must not hide a dropped GPU allocation or a crash.

It called initialize(device_cfg=...) and, on any TypeError, called
initialize() again with nothing. Two things went silent that way:

- SpeechEngine.initialize() takes no device_cfg, so Whisper's GPU allocation
  was dropped with no log line and every command ran on the CPU (1.8 s
  against 0.2 s for a 2.5 s command on an RTX 2050).
- A TypeError raised inside an initialize() that does take device_cfg, a real
  bug, was swallowed, and the subsystem was initialised a second time without
  its config as if nothing had happened.
"""

from __future__ import annotations

import logging

import pytest

from Agent_Guru.integration.gpu_pool import DeviceConfig
from Agent_Guru.integration.orchestrator import IntegrationOrchestrator

GPU = DeviceConfig(device="cuda", memory_limit=1 << 30)
CPU = DeviceConfig(device="cpu", memory_limit=0)


def _orchestrator() -> IntegrationOrchestrator:
    # _init_subsystem uses no instance state, so skip wiring every subsystem.
    return IntegrationOrchestrator.__new__(IntegrationOrchestrator)


class TakesConfig:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def initialize(self, device_cfg: DeviceConfig | None = None) -> None:
        self.calls.append(device_cfg)


class IgnoresConfig:
    def __init__(self) -> None:
        self.calls = 0

    def initialize(self) -> None:
        self.calls += 1


class BrokenWithConfig:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def initialize(self, device_cfg: DeviceConfig | None = None) -> None:
        self.calls.append(device_cfg)
        raise TypeError("unsupported operand type(s) for +: 'int' and 'str'")


class AsyncTakesConfig:
    def __init__(self) -> None:
        self.calls: list[object] = []

    async def initialize(self, device_cfg: DeviceConfig | None = None) -> None:
        self.calls.append(device_cfg)


async def test_config_reaches_a_subsystem_that_takes_it() -> None:
    sync, coro = TakesConfig(), AsyncTakesConfig()
    await _orchestrator()._init_subsystem("sync", sync, GPU)
    await _orchestrator()._init_subsystem("async", coro, GPU)
    assert sync.calls == [GPU]
    assert coro.calls == [GPU]


async def test_dropped_gpu_allocation_is_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    sub = IgnoresConfig()
    with caplog.at_level(logging.INFO):
        await _orchestrator()._init_subsystem("speech_engine", sub, GPU)
    assert sub.calls == 1
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("speech_engine" in m and "cuda" in m for m in warnings), warnings


async def test_dropped_cpu_allocation_is_stated_not_warned(caplog: pytest.LogCaptureFixture) -> None:
    sub = IgnoresConfig()
    with caplog.at_level(logging.INFO):
        await _orchestrator()._init_subsystem("speech_engine", sub, CPU)
    assert sub.calls == 1
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("speech_engine" in r.getMessage() for r in caplog.records)


async def test_typeerror_inside_initialize_is_an_error_not_a_retry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sub = BrokenWithConfig()
    with caplog.at_level(logging.INFO):
        await _orchestrator()._init_subsystem("vision_engine", sub, GPU)
    # Called once, with its config: not re-run bare after the crash.
    assert sub.calls == [GPU]
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors and "vision_engine" in errors[0].getMessage()
    assert errors[0].exc_info is not None
