"""`agent-guru doctor` reports what it actually found, and the health manager runs it one check at a time.

The doctor is run against the real machine by hand; these replace each piece
it talks to so every verdict path is pinned: a missing model is a failure, a
Whisper that falls back to the CPU is a warning with the reason, a speech round
trip that comes back wrong is a failure, a muted microphone is not "working".
"""

from __future__ import annotations

import asyncio
import sys
import types

import numpy as np
import pytest

from Agent_Guru.platform.error_handling import doctor
from Agent_Guru.platform.error_handling.health_check import (
    ComponentHealth,
    HealthCheckManager,
    HealthStatus,
)

# Real icacls output on Windows 11, for a file restricted to its owner and
# for one that inherited its folder's permissions.
OWNER_ONLY = (
    "C:\\Users\\suraj\\AppData\\Local\\agent_guru\\turns.db SURAJ_SHARMA\\suraj:(F)\n\n"
    "Successfully processed 1 files; Failed processing 0 files\n"
)
INHERITED = (
    "C:\\Users\\suraj\\AppData\\Local\\agent_guru\\memory.db NT AUTHORITY\\SYSTEM:(I)(F)\n"
    "                                                  BUILTIN\\Administrators:(I)(F)\n"
    "                                                  SURAJ_SHARMA\\suraj:(I)(F)\n\n"
    "Successfully processed 1 files; Failed processing 0 files\n"
)


def test_acl_principals_reads_account_names_not_the_drive_letter():
    # The first line starts with "C:", which a split on the first colon took
    # for an account: every file looked shared.
    assert doctor.acl_principals(OWNER_ONLY, "C:\\Users\\suraj\\AppData\\Local\\agent_guru\\turns.db") == [  # nosec B101
        "SURAJ_SHARMA\\suraj",
    ]
    assert doctor.acl_principals(INHERITED, "C:\\Users\\suraj\\AppData\\Local\\agent_guru\\memory.db") == [  # nosec B101
        "NT AUTHORITY\\SYSTEM", "BUILTIN\\Administrators", "SURAJ_SHARMA\\suraj",
    ]


async def test_an_unreachable_ollama_fails_with_what_to_do(monkeypatch):
    def refuse(url, payload=None, timeout=5.0):
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr(doctor, "_get_json", refuse)
    result = await doctor.check_ollama()
    assert result.status is HealthStatus.UNHEALTHY and "Start Ollama" in result.message  # nosec B101


async def test_a_model_that_is_not_installed_fails_with_the_pull_command(monkeypatch):
    monkeypatch.setattr(doctor, "_get_json", lambda url, payload=None, timeout=5.0: {"models": [{"name": "llama3:8b"}]})
    monkeypatch.setattr("Agent_Guru.reasoning.llm.generation.ollama_model", lambda: "gemma4")
    result = await doctor.check_model()
    assert result.status is HealthStatus.UNHEALTHY and "ollama pull gemma4" in result.message  # nosec B101


async def test_an_installed_model_must_also_answer(monkeypatch):
    def server(url, payload=None, timeout=5.0):
        if url.endswith("/api/tags"):
            return {"models": [{"name": "gemma4:latest"}]}
        assert payload["options"]["num_predict"] == 1  # nosec B101  one token, not a whole answer
        return {"response": "OK", "load_duration": 2_000_000_000}

    monkeypatch.setattr(doctor, "_get_json", server)
    monkeypatch.setattr("Agent_Guru.reasoning.llm.generation.ollama_model", lambda: "gemma4")
    result = await doctor.check_model()
    assert result.status is HealthStatus.HEALTHY and "2.0 s of it loading" in result.message  # nosec B101


def _fake_speech(monkeypatch, heard, device="cuda", fail_cuda=None):
    class Transcriber:
        pass

    class Engine:
        def __init__(self):
            self.stt_transcriber = Transcriber()

        def initialize(self):
            self.stt_transcriber.device = device

        def synthesize_to_array(self, text, personality):
            return np.zeros(24000, np.float32), 24000

        def transcribe(self, audio):
            return types.SimpleNamespace(text=heard)

    monkeypatch.setattr("Agent_Guru.speech.engine.SpeechEngine", Engine)
    monkeypatch.setattr("Agent_Guru.speech.stt.whisper_stt.cuda_failure", lambda: fail_cuda)


async def test_speech_that_comes_back_right_on_the_gpu_is_ok(monkeypatch):
    _fake_speech(monkeypatch, "The quick brown fox jumps over the lazy dog.")
    assert (await doctor.check_speech()).status is HealthStatus.HEALTHY  # nosec B101


async def test_speech_on_the_cpu_warns_and_says_why(monkeypatch):
    _fake_speech(monkeypatch, "The quick brown fox jumps over the lazy dog.", device="cpu",
                 fail_cuda="RuntimeError: Library cublas64_12.dll is not found or cannot be loaded")
    result = await doctor.check_speech()
    assert result.status is HealthStatus.DEGRADED and "cublas64_12.dll" in result.message  # nosec B101


async def test_speech_heard_wrong_fails(monkeypatch):
    _fake_speech(monkeypatch, "Testing")
    result = await doctor.check_speech()
    assert result.status is HealthStatus.UNHEALTHY and "heard 'testing'" in result.message  # nosec B101


async def test_one_misheard_word_is_not_a_failure(monkeypatch):
    _fake_speech(monkeypatch, "The quick brown box jumps over the lazy dog")
    assert (await doctor.check_speech()).status is HealthStatus.HEALTHY  # nosec B101


def _fake_microphone(monkeypatch, samples=None, error=None):
    def rec(frames, samplerate, channels, dtype, blocking):
        if error:
            raise error
        return samples

    sd = types.SimpleNamespace(query_devices=lambda kind: {"name": "Test Mic"}, rec=rec)
    monkeypatch.setitem(sys.modules, "sounddevice", sd)


async def test_a_microphone_that_records_is_ok(monkeypatch):
    _fake_microphone(monkeypatch, samples=np.full((8000, 1), 0.01, np.float32))
    assert (await doctor.check_microphone()).status is HealthStatus.HEALTHY  # nosec B101


async def test_a_microphone_sending_pure_silence_is_not_called_working(monkeypatch):
    _fake_microphone(monkeypatch, samples=np.zeros((8000, 1), np.float32))
    result = await doctor.check_microphone()
    assert result.status is HealthStatus.DEGRADED and "silence" in result.message  # nosec B101


async def test_a_microphone_that_cannot_open_fails(monkeypatch):
    _fake_microphone(monkeypatch, error=OSError("Invalid device"))
    assert (await doctor.check_microphone()).status is HealthStatus.UNHEALTHY  # nosec B101


async def test_the_speaker_is_not_played_unless_asked(monkeypatch):
    played = []
    monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(query_devices=lambda kind: {"name": "Out"}))
    monkeypatch.setattr("Agent_Guru.speech.audio.portaudio_lock.play_and_wait", lambda *a: played.append(a))
    assert "not played" in (await doctor.check_speaker()).message and played == []  # nosec B101
    await doctor.check_speaker(play=True)
    assert len(played) == 1  # nosec B101


# ---- the health manager the doctor runs on ----

def _health(name):
    return ComponentHealth(name=name, status=HealthStatus.HEALTHY, message="ok", last_check=None,
                           response_time_ms=0.0)


async def test_a_check_gets_its_own_time_limit():
    async def slow():
        await asyncio.sleep(0.3)
        return _health("slow")

    manager = HealthCheckManager(check_timeout=0.05)
    manager.register_check("slow", slow, timeout=1.0)
    manager.register_check("slow_default", slow)
    results = {c.name: c for c in (await manager.check_health(use_cache=False)).components}
    assert results["slow"].status is HealthStatus.HEALTHY  # nosec B101
    assert results["slow_default"].status is HealthStatus.UNHEALTHY  # nosec B101
    assert "0.05s" in results["slow_default"].message  # nosec B101


async def test_sequential_checks_run_one_at_a_time_in_order():
    running, log = [], []

    def make(name):
        async def check():
            running.append(name)
            log.append((name, len(running)))
            await asyncio.sleep(0.02)
            running.remove(name)
            return _health(name)

        return check

    manager = HealthCheckManager()
    for name in ("a", "b", "c"):
        manager.register_check(name, make(name))
    health = await manager.check_health(use_cache=False, sequential=True)
    assert [c.name for c in health.components] == ["a", "b", "c"]  # nosec B101
    assert all(at_once == 1 for _, at_once in log)  # nosec B101


def test_doctor_exits_non_zero_when_something_fails(monkeypatch, capsys):
    async def broken():
        return doctor._fail("thing", "broken")

    async def fine():
        return doctor._ok("other", "fine")

    def manager(**kwargs):
        m = HealthCheckManager()
        m.register_check("thing", broken)
        m.register_check("other", fine)
        return m

    monkeypatch.setattr(doctor, "build_manager", manager)
    assert doctor.run([]) == 1  # nosec B101
    out = capsys.readouterr().out
    assert "[FAIL] thing" in out and "[ok  ] other" in out and "1 ok, 0 warnings, 1 failed" in out  # nosec B101


def test_agent_guru_doctor_runs_the_doctor_not_the_assistant(monkeypatch):
    from Agent_Guru import __main__ as entry

    called = []
    monkeypatch.setattr(doctor, "run", lambda argv: called.append(argv) or 0)
    monkeypatch.setattr(sys, "argv", ["agent-guru", "doctor", "--quick"])
    with pytest.raises(SystemExit) as exit_info:
        entry._run()
    assert exit_info.value.code == 0 and called == [["--quick"]]  # nosec B101


def test_the_quick_doctor_skips_only_the_model_loading_checks():
    full = set(doctor.build_manager().get_registered_components())
    quick = set(doctor.build_manager(quick=True).get_registered_components())
    assert full - quick == {"model", "speech"}  # nosec B101
