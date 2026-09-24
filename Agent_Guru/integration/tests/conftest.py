"""Drive the real IntegrationOrchestrator.run_pipeline with only I/O stubbed.

STT, TTS, the filler clip, the LLM and the web are replaced; intent
recognition, the response path, user memory and the web-search gate run for
real. The defects these tests pin were all in how those real pieces were
wired together, so stubbing any of them would test nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent
from Agent_Guru.platform.features import user_memory as user_memory_module
from Agent_Guru.platform.features import web_search as web_search_module

#: The transcript from the first Windows run, verbatim.
WINDOWS_TRANSCRIPT = (
    "Hey Guru, what's the time right now? And I want to know the timing, "
    "current time of India, and also I want to know who is the Prime Minister "
    "of India currently"
)

LLM_ANSWER = "Narendra Modi is the Prime Minister of India."

#: An earlier turn, as MemoryManager.retrieve() hands it back.
PRIOR_TURNS = [
    {
        "personality": "GURU",
        "user_message": "my doctor says my blood pressure is too high",
        "ai_message": "Let's keep an eye on that together.",
    },
]


class _RecordingLLM:
    def __init__(self) -> None:
        self.requests: list = []

    async def complete(self, request):
        self.requests.append(request)
        return SimpleNamespace(content=LLM_ANSWER)


class _Memory:
    async def retrieve(self, transcript):
        return PRIOR_TURNS


class _AllowAll:
    def evaluate(self, intent):
        return True


class _Controller:
    def __init__(self) -> None:
        self.browser_searches: list[str] = []

    def web_search(self, query, engine):
        self.browser_searches.append(query)


@dataclass
class Turn:
    result: object
    llm: _RecordingLLM
    web_queries: list[str]
    controller: _Controller
    facts: dict = field(default_factory=dict)


@pytest.fixture
def user_memory(tmp_path, monkeypatch):
    memory = user_memory_module.UserMemory(path=tmp_path / "user_memory.json")
    monkeypatch.setattr(user_memory_module, "_user_memory", memory)
    return memory


@pytest.fixture
def run_turn(user_memory, monkeypatch):
    """Return an async function that runs one spoken turn end to end."""

    async def _run(transcript: str) -> Turn:
        web_queries: list[str] = []

        async def _fake_search_web(query, *args, **kwargs):
            web_queries.append(query)
            return "search result"

        monkeypatch.setattr(web_search_module, "search_web", _fake_search_web)

        llm, controller = _RecordingLLM(), _Controller()
        orch = IntegrationOrchestrator(
            speech_engine=None, vision_engine=None, llm_runtime=llm,
            platform_controller=controller, agent_orchestrator=None,
            memory=_Memory(), reasoning=None, security=None, policy=_AllowAll(),
            avatar=None, deployment=None, gpu_pool=None,
        )
        orch._stage_stt = AsyncMock(return_value=(transcript, "en"))
        orch._stage_tts = AsyncMock(return_value=None)
        orch._play_filler = AsyncMock(return_value=None)

        result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru"))
        return Turn(result, llm, web_queries, controller, user_memory.get_all())

    return _run
