"""Writing something for the owner is a conversation; typing needs an explicit instruction.

"Help me write a message to my landlord" was labelled type_text: the typing
rule matched "write" anywhere in the sentence. The production policy refuses
typing, so the owner was told "it isn't allowed in my current settings" and got
no draft. Narrowing that rule alone moved the request to send_message. Now a
request to compose is answered by the model, a request that gives the words to
send stays a message, and "type hello" is still typing, still refused by the
policy.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from Agent_Guru.integration.orchestrator import ActionStatus, IntegrationOrchestrator
from Agent_Guru.platform.intent_recognizer import _RuleEngine
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies

COMPOSE = [
    "Help me write a message to my landlord",
    "help me draft an email",
    "write a note to my teacher",
    "compose a message for my boss",
    "draft a reply to my landlord about the rent",
    "write an email to my manager asking for leave",
    "can you write a birthday message for my mom",
    "help me write a cover letter",
    "compose an email to the school",
    "draft a message to my team",
]
TYPING = ["type hello", "type hello world", "type this: meeting at 5", "write hello in notepad"]
SENDING = [
    "send a message to John saying hi",
    "write a message to John saying I am late",
    "write a text to my friend saying sorry",
    "compose a whatsapp to Ravi: running late",
]


@pytest.mark.parametrize("said", COMPOSE)
def test_a_request_to_write_something_is_a_conversation(said):
    result = _RuleEngine().recognize(said, "windows")
    assert result.intent_type == "conversation", (said, result)  # nosec B101


@pytest.mark.parametrize("said", TYPING)
def test_an_explicit_typing_instruction_is_still_typing(said):
    result = _RuleEngine().recognize(said, "windows")
    assert result.parameters.get("action") == "type_text", (said, result)  # nosec B101


@pytest.mark.parametrize("said", SENDING)
def test_a_message_with_its_words_is_still_a_message(said):
    result = _RuleEngine().recognize(said, "windows")
    assert (result.intent_type, result.parameters.get("action")) == ("communication", "send_message"), result  # nosec B101


class _Model:
    def __init__(self) -> None:
        self.asked: list[str] = []

    async def complete(self, request):
        self.asked.append(request.messages[-1].content)
        return SimpleNamespace(content="Dear landlord, the kitchen tap has been leaking since Monday.",
                               finish_reason="stop", tool_calls=[])


class _Controller:
    """Records any call the action stage makes; typing would show up here."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append(name)
            return True
        return record


async def _turn(said, tmp_path):
    engine = PolicyEngine()
    install_default_policies(engine)
    model, controller = _Model(), _Controller()
    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=model, platform_controller=controller,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine,
        avatar=None, deployment=None, gpu_pool=None, reminder_store=tmp_path / "r.json",
    )

    async def no_web(*a, **k):
        return ""

    orch._fetch_web_context = no_web
    try:
        return await orch.run_text_turn(said), model, controller
    finally:
        orch.close_scheduler()


async def test_the_landlord_message_is_drafted_not_typed_or_refused(tmp_path):
    result, model, controller = await _turn("Help me write a message to my landlord", tmp_path)
    # A conversation turn's status reads DENIED (no action is allowed for one);
    # what the owner gets is the reply, which must be the model's draft.
    assert result.intent.startswith("conversation"), result.intent  # nosec B101
    assert "landlord" in (result.llm_response or ""), result  # nosec B101
    assert "allowed" not in (result.llm_response or "")  # nosec B101
    assert model.asked, "the model was not asked"  # nosec B101
    assert "type_text" not in controller.calls  # nosec B101


async def test_typing_is_still_refused_by_the_policy(tmp_path):
    result, _, controller = await _turn("type hello", tmp_path)
    assert result.action_status is ActionStatus.DENIED, result  # nosec B101
    assert "type_text" not in controller.calls  # nosec B101
