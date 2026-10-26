"""The time question is answered, and a typed turn always gets words back.

Found in the first live run (2026-10-26): "what time is it" through the running app came back empty
over the local API, and the same question by voice was answered "I can't do that - it isn't allowed
in my current settings.", because the starting policies allowed messaging and device actions only.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from Agent_Guru.integration.orchestrator import ActionStatus, IntegrationOrchestrator
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies


def _orchestrator():
    engine = PolicyEngine()
    install_default_policies(engine)
    return IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=None, platform_controller=None,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine, avatar=None,
        deployment=None, gpu_pool=None, reminder_store=Path(tempfile.mkdtemp()) / "r.json",
    )


@pytest.mark.parametrize("said", ["what time is it", "what's the date today", "what day is it"])
async def test_the_clock_question_is_answered_from_the_clock(said):
    orch = _orchestrator()
    try:
        result = await orch.run_text_turn(said)
        assert result.policy_allowed and result.action_status is ActionStatus.SUCCESS  # nosec B101
        assert orch._finalize_tts_text(result).startswith("It's ")  # nosec B101
    finally:
        orch.close_scheduler()


async def test_the_clock_allow_does_not_carry_another_step():
    orch = _orchestrator()
    try:
        assert not await orch._stage_policy("information:time_date|system_control:shutdown")  # nosec B101
        assert not await orch._stage_policy("information:time_dates")  # nosec B101  a whole match
    finally:
        orch.close_scheduler()


def test_a_refused_typed_turn_says_so():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from Agent_Guru.integration import local_api

    import secrets

    key = secrets.token_urlsafe(24)  # made per run: a literal key here is what the secret scan refuses

    class Orchestrator:
        events = SimpleNamespace(publish=lambda event, **d: None)

        async def run_text_turn(self, text):
            return SimpleNamespace(llm_response=None, action_result=None, action_status=ActionStatus.DENIED,
                                   awaiting_reply=False, sources=[], error=None)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(local_api, "owner_key", lambda **k: key)
    try:
        http = TestClient(local_api.create_app(Orchestrator()))
        answer = http.post("/v1/turn", json={"text": "type hello"}, headers={"X-API-Key": key}).json()
    finally:
        monkey.undo()
    assert answer["status"] == "denied" and answer["reply"] == "I can't do that - it isn't allowed in my current settings."  # nosec B101
