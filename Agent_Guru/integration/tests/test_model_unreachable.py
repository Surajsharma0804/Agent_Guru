"""With the model server down, the owner is told so, not that a setting forbids it.

In the round 12 soak Ollama had stopped, and "Tell me a short fact about the
moon." was answered "I can't do that - it isn't allowed in my current
settings." The answer stage swallowed the refused connection and returned no
answer; the reply then fell back to the turn's status, and a question's
status is DENIED because the production policy allows no action for it.

These turns go through the real LLMRuntime and Ollama adapter, pointed at a
local port nothing listens on, so the refusal is a real refused connection.
"""

from __future__ import annotations

import socket
from types import SimpleNamespace

import pytest

from Agent_Guru.integration.orchestrator import (
    ActionStatus,
    IntegrationOrchestrator,
    WakeWordEvent,
)
from Agent_Guru.llm.llm_runtime import LLMRuntime
from Agent_Guru.llm.models import OllamaConfig, RuntimeConfig
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies

REFUSAL = "isn't allowed in my current settings"
#: The words the owner is told, pinned here rather than imported so the
#: test fails on the behaviour, not on a missing name.
MODEL_DOWN_REPLY = "My language model is not running. Start Ollama and try again."


def _closed_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def orch(tmp_path):
    runtime = LLMRuntime.from_config(
        RuntimeConfig(ollama_config=OllamaConfig(host=f"http://127.0.0.1:{_closed_port()}")),
    )
    engine = PolicyEngine()
    install_default_policies(engine)
    made = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=runtime, platform_controller=None,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine,
        avatar=None, deployment=None, gpu_pool=None, reminder_store=tmp_path / "r.json",
    )

    async def no_web(*a, **k):
        return ""

    made._fetch_web_context = no_web
    yield made
    made.close_scheduler()


@pytest.mark.parametrize("said", ["Tell me a short fact about the moon.", "What is the capital of Japan?"])
async def test_a_typed_question_says_the_model_is_not_running(orch, said):
    result = await orch.run_text_turn(said)
    assert result.llm_response == MODEL_DOWN_REPLY, result  # nosec B101
    assert result.action_status is ActionStatus.FAILED  # nosec B101
    assert result.error == "llm_unreachable"  # nosec B101


async def test_a_spoken_question_says_the_model_is_not_running(orch):
    said: list[str] = []

    async def speak(fn, text, personality, **kw):
        # A streamed reply's chunks come from the model; iterating them
        # meets the refused connection, as the real speaker would.
        chunks = [c async for c in text] if not isinstance(text, str) else [text]
        said.append("".join(chunks))
        return SimpleNamespace(spoken=1, error=None)

    orch._streamable_tts_fn = lambda: (lambda text, pt: (b"", 22050))
    orch._speak_streaming = speak

    async def no_filler(*a, **k):
        return None

    orch._play_filler = no_filler

    async def stt(*a, **k):
        return "tell me a short fact about the moon", "en"

    orch._stage_stt = stt
    result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=b"\x00" * 3200))
    assert said == [MODEL_DOWN_REPLY]  # nosec B101
    assert REFUSAL not in " ".join(said)  # nosec B101
    assert result.action_status is ActionStatus.FAILED  # nosec B101


async def test_a_refused_action_still_says_it_is_not_allowed(orch):
    # The plain-words reply is for the model being down; a command the policy
    # refuses keeps the refusal, model or no model.
    result = await orch.run_text_turn("shut down the computer")
    assert result.action_status is ActionStatus.DENIED  # nosec B101
    from Agent_Guru.integration.orchestrator import _STATUS_REPLIES

    reply = result.llm_response or result.action_result or _STATUS_REPLIES[result.action_status]
    assert REFUSAL in reply and "language model" not in reply, reply  # nosec B101
