"""What the owner says about themselves is remembered, whatever the action policy allows.

Facts ("I live in Pune", "my name is Ravi", "remember that my exam is on
Monday") were extracted inside the action stage, from the intent string. Such
sentences are recognized as plain "conversation", which carries no text, so
the extractor read the word "conversation" and stored nothing; and the action
stage runs only when the policy allows the action, which the production policy
(messaging only) never does for a conversation. Found by scripts/turn_eval.py:
told "I live in Pune" in one session, the assistant answered "where do I live"
in the next with "I seriously have no clue where you live".
"""

from __future__ import annotations

import numpy as np
import pytest

from Agent_Guru.integration.orchestrator import ActionStatus, IntegrationOrchestrator, Personality, WakeWordEvent
from Agent_Guru.platform.features import user_memory as user_memory_module


class Policy:
    def __init__(self, allow):
        self.allow = allow
        self.asked = []

    def evaluate(self, intent):
        self.asked.append(intent)
        return self.allow


@pytest.fixture
def facts(tmp_path, monkeypatch):
    store = user_memory_module.UserMemory(tmp_path / "user_memory.json")
    monkeypatch.setattr(user_memory_module, "_user_memory", store)
    return store


def _orchestrator(allow=False):
    return IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=None, platform_controller=None,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=Policy(allow),
        avatar=None, deployment=None, gpu_pool=None,
    )


async def _turn(orch, said):
    spoken = []

    async def stt(*a, **k):
        return said, "en"

    async def tts(text, personality):
        spoken.append(text)

    async def silent(*a, **k):
        return None

    orch._stage_stt, orch._stage_tts, orch._play_filler = stt, tts, silent
    result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=np.zeros(16000, np.float32).tobytes()))
    return result, spoken[0] if spoken else None


async def test_where_the_owner_lives_is_remembered_under_the_production_policy(facts):
    result, spoken = await _turn(_orchestrator(allow=False), "I live in Pune")
    assert facts.get("location") == "Pune"  # nosec B101
    assert spoken == "Pune - cool, I'll keep that in mind."  # nosec B101
    assert result.action_status is ActionStatus.SUCCESS  # nosec B101


async def test_a_name_is_remembered_when_actions_are_allowed_too(facts):
    await _turn(_orchestrator(allow=True), "my name is Ravi")
    assert facts.get("name") == "Ravi"  # nosec B101


async def test_remember_and_forget_work(facts):
    orch = _orchestrator()
    _, spoken = await _turn(orch, "remember that my exam is on Monday")
    assert "my exam is on Monday" in facts.get_all().values()  # nosec B101
    assert spoken == "done, yaad rakh liya - my exam is on Monday"  # nosec B101
    _, spoken = await _turn(orch, "forget that my exam is on Monday")
    assert "my exam is on Monday" not in facts.get_all().values()  # nosec B101
    assert spoken == "done, bhool gaya!"  # nosec B101


async def test_a_question_carrying_a_fact_keeps_the_fact_and_is_still_answered(facts):
    # "My name is Suraj, what's the weather?" must not be answered with
    # "Nice to meet you, Suraj!" and nothing else.
    result, _ = await _turn(_orchestrator(allow=True), "my name is Suraj, what's the weather")
    assert facts.get("name") == "Suraj"  # nosec B101
    assert result.action_result != "Nice to meet you, Suraj! I'll remember that."  # nosec B101


async def test_an_unverified_speaker_cannot_change_what_is_remembered(facts):
    orch = _orchestrator()
    orch._verify_speaker = lambda *a, **k: "restricted"
    await _turn(orch, "my name is Mallory")
    assert facts.get_all() == {}  # nosec B101


async def test_a_remembered_fact_reaches_the_next_session(facts):
    await _turn(_orchestrator(), "I live in Pune")
    later = _orchestrator()

    async def no_web(transcript, intent):
        return ""

    later._fetch_web_context = no_web
    request, _ = await later._build_llm_request("where do I live", None, "en", Personality.GURU, "information:question")
    assert "Pune" in request.messages[0].content  # nosec B101


async def test_a_dictated_message_is_sent_not_taken_as_a_fact_about_the_owner(facts):
    sent = []

    class Messaging:
        def send_message(self, *args, **kwargs):
            sent.append(args)
            return type("R", (), {"success": True, "message": "ok", "error": None, "data": {"status": "sent"}})()

    orch = _orchestrator(allow=True)
    orch.platform_controller = Messaging()
    result, _ = await _turn(orch, "send a message to John saying my name is Ravi")
    assert result.intent.startswith("communication:send_message:John")  # nosec B101
    assert facts.get("name") is None  # nosec B101
