"""A turn that comes while the memory embedding model is still loading waits its budget, then answers.

Startup preloads the model in the background. A turn that comes before the load finishes waits on
that same load inside its memory stage, up to MEMORY_TIMEOUT_S, and then answers without recalled
memory and says so in the log. Over 10 cold starts on 2026-11-02, a question asked as soon as the
app listened waited a median of 5.007 s there and recalled the stored fact in only 4 of 10.

The load is stood in for by an embedding that waits on an event, so whether the load has finished
is decided by the test, not by a clock. The budgets are shortened to keep the test quick; the 30 s
guard only stops a hang, it measures nothing.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from Agent_Guru.integration import orchestrator as orchestrator_module
from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent
from Agent_Guru.memory import memory_manager
from Agent_Guru.memory.memory_manager import MemoryManager
from Agent_Guru.platform.features import user_memory as user_memory_module

TOPICS = ["sister", "name", "priya", "pune", "capital", "france"]
GUARD_S = 30


def _embed(text: str) -> list[float]:
    words = set(re.findall(r"[a-z]+", text.lower()))
    v = [1.0 if t in words else 0.0 for t in TOPICS] + [0.05]
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v]


class _LLM:
    def __init__(self) -> None:
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        return SimpleNamespace(content="Okay.", finish_reason="stop")


class _Allow:
    def evaluate(self, intent):
        return True


@pytest.fixture
def session(tmp_path, monkeypatch):
    loaded = asyncio.Event()
    loaded.set()

    async def embed(text: str) -> list[float]:
        await loaded.wait()
        return _embed(text)

    monkeypatch.setattr(memory_manager, "_embed_text_async", embed)
    monkeypatch.setattr(orchestrator_module, "MEMORY_TIMEOUT_S", 0.2)
    # Storing the finished turn needs an embedding too, under its own 10 s budget; shortened for
    # the same reason, so a turn during the load does not hold each test for 10 s.
    monkeypatch.setattr(orchestrator_module, "MEMORY_WRITE_TIMEOUT_S", 0.2)
    monkeypatch.setattr(
        user_memory_module, "_user_memory", user_memory_module.UserMemory(path=tmp_path / "user_memory.json"),
    )
    memory = MemoryManager(platform_override="test-platform")
    llm = _LLM()
    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=llm, platform_controller=object(),
        agent_orchestrator=None, memory=memory, reasoning=None, security=None, policy=_Allow(),
        avatar=None, deployment=None, gpu_pool=None,
    )
    orch._stage_tts = AsyncMock(return_value=None)
    orch._play_filler = AsyncMock(return_value=None)
    orch._fetch_web_context = AsyncMock(return_value="")

    async def turn(transcript: str):
        orch._stage_stt = AsyncMock(return_value=(transcript, "en"))
        return await asyncio.wait_for(orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru")), GUARD_S)

    return SimpleNamespace(memory=memory, llm=llm, turn=turn, loaded=loaded)


async def _remember(session) -> None:
    await session.memory.store_interaction("GURU", "My sister's name is Priya and she lives in Pune.", "Noted.")


async def test_a_turn_during_the_load_answers_without_memory_after_its_budget(session, caplog):
    await _remember(session)
    session.loaded.clear()
    with caplog.at_level(logging.WARNING, logger=orchestrator_module.logger.name):
        result = await session.turn("What is my sister's name?")
    assert not result.memory_context  # nosec B101
    assert len(session.llm.requests) == 1  # nosec B101
    said = [r.getMessage() for r in caplog.records if "Memory stage exceeded" in r.getMessage()]
    assert said == ["Memory stage exceeded 0.2s - answering without recalled context"]  # nosec B101


async def test_a_turn_after_the_load_gets_the_memory(session):
    await _remember(session)
    result = await session.turn("What is my sister's name?")
    assert [m["user_message"] for m in result.memory_context] == [  # nosec B101
        "My sister's name is Priya and she lives in Pune.",
    ]


async def test_the_turn_after_a_slow_load_recalls_once_the_load_is_done(session):
    await _remember(session)
    session.loaded.clear()
    first = await session.turn("What is my sister's name?")
    session.loaded.set()
    second = await session.turn("What is my sister's name?")
    assert not first.memory_context  # nosec B101
    assert [m["user_message"] for m in second.memory_context] == [  # nosec B101
        "My sister's name is Priya and she lives in Pune.",
    ]
