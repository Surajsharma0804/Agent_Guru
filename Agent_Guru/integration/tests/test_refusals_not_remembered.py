"""A refused turn is not stored as a memory; everything else still is.

Every refused turn used to be stored ("I can't do that - it isn't allowed in my current settings.")
and recalled into later prompts, so after the policy changed, the owner's memory still held
refusals for requests it now allows (rows 160 and 162 of the owner's memory.db, deleted 2026-10-26).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from Agent_Guru.integration.orchestrator import ActionStatus, IntegrationOrchestrator
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies


class Memory:
    def __init__(self):
        self.stored = []

    async def store_interaction(self, personality, user_message, ai_message):
        self.stored.append((user_message, ai_message))
        return True

    async def search(self, *args, **kwargs):
        return []


class Controller:
    def app_instances(self, name):
        return {}

    def open_application(self, name):
        return {"success": True}


class Model:
    async def supports_tool_calling(self, model):
        return False

    async def complete(self, request):
        return SimpleNamespace(content="17 times 23 is 391.", tool_calls=[], finish_reason="stop")


@pytest.fixture
async def assistant(tmp_path):
    engine = PolicyEngine()
    install_default_policies(engine)
    memory = Memory()
    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=Model(), platform_controller=Controller(),
        agent_orchestrator=None, memory=memory, reasoning=None, security=None, policy=engine, avatar=None,
        deployment=None, gpu_pool=None, reminder_store=tmp_path / "r.json",
    )
    orch._APP_OPEN_VERIFY_S = 0.0
    yield orch, memory
    orch.close_scheduler()


@pytest.mark.parametrize("said", ["type hello world", "read my clipboard"])
async def test_a_refused_turn_is_not_remembered(assistant, said):
    orch, memory = assistant
    result = await orch.run_text_turn(said)
    assert result.action_status is ActionStatus.DENIED and not result.llm_response  # nosec B101  refused
    assert memory.stored == []  # nosec B101


async def test_a_turn_that_did_something_is_still_remembered(assistant):
    orch, memory = assistant
    await orch.run_text_turn("open notepad")
    assert [u for u, _ in memory.stored] == ["open notepad"]  # nosec B101


async def test_a_question_the_model_answered_is_still_remembered(assistant):
    orch, memory = assistant
    await orch.run_text_turn("what is 17 times 23")
    assert memory.stored and "391" in memory.stored[0][1]  # nosec B101


class SaysItCannot(Model):
    async def complete(self, request):
        return SimpleNamespace(content="Dude, I can\u2019t actually set up a recurring alert for the weather like that.",
                               tool_calls=[], finish_reason="stop")


async def test_a_reply_saying_it_cannot_is_not_remembered(tmp_path):
    # Recalled into the next prompt for the same request, the model repeated it nearly word for word
    # (live run, 2026-10-26), though schedule_check was on offer, and the repeat was stored as well.
    engine = PolicyEngine()
    install_default_policies(engine)
    memory = Memory()
    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=SaysItCannot(), platform_controller=Controller(),
        agent_orchestrator=None, memory=memory, reasoning=None, security=None, policy=engine, avatar=None,
        deployment=None, gpu_pool=None, reminder_store=tmp_path / "r.json",
    )
    try:
        result = await orch.run_text_turn("keep an eye on the weather in Delhi every hour")
        assert "can\u2019t" in (result.llm_response or "") and memory.stored == []  # nosec B101
    finally:
        orch.close_scheduler()
