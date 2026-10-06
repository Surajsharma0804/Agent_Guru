"""Regression tests for how long a spoken reply is allowed to be.

The voice path asked the model for up to 400 tokens. Measured on gemma3:4b
with the real system prompt, "tell me about the history of India" ran 228
tokens: about 65 s of speech after 14-27 s of generation on a 4 GB laptop GPU.
The cap now comes from the shared generation policy. A reply that hits it is
cut back to its last full sentence instead of being spoken mid-word. A
clipboard rewrite, which is pasted rather than spoken, keeps its old budget
so the end of the user's text is not lost.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator
from Agent_Guru.platform.features import dictation
from Agent_Guru.reasoning.llm import generation

CAPPED = (
    "The Indus Valley Civilization was one of the first cities. "
    "Then came the Vedic period! After that the Maurya empire united"
)


@pytest.fixture(autouse=True)
def _default_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENT_GURU_SPOKEN_REPLY_TOKENS", raising=False)


async def test_a_spoken_turn_asks_for_the_spoken_reply_cap(run_turn):
    turn = await run_turn("Tell me about the history of India")

    assert [r.max_tokens for r in turn.llm.requests] == [generation.DEFAULT_SPOKEN_REPLY_TOKENS]
    assert generation.DEFAULT_SPOKEN_REPLY_TOKENS < 400


async def test_the_spoken_cap_can_be_overridden(run_turn, monkeypatch):
    monkeypatch.setenv("AGENT_GURU_SPOKEN_REPLY_TOKENS", "60")

    turn = await run_turn("Tell me about the history of India")

    assert [r.max_tokens for r in turn.llm.requests] == [60]


def _orchestrator() -> IntegrationOrchestrator:
    return IntegrationOrchestrator(*([None] * 12))


async def _complete(orch, transcript: str, reply: str, finish_reason: str):
    requests: list = []

    async def complete_fn(request):
        requests.append(request)
        return SimpleNamespace(content=reply, finish_reason=finish_reason)

    text = await orch._llm_complete(complete_fn, transcript, None, "en", None, None)
    return text, requests[0]


async def test_a_capped_reply_ends_on_its_last_full_sentence(user_memory):
    text, _ = await _complete(_orchestrator(), "history of India", CAPPED, "length")

    assert text == (
        "The Indus Valley Civilization was one of the first cities. Then came the Vedic period!"
    )


async def test_a_finished_reply_is_spoken_as_generated(user_memory):
    text, _ = await _complete(_orchestrator(), "history of India", CAPPED, "stop")

    assert text == CAPPED


async def test_a_capped_reply_with_no_sentence_end_is_kept_whole(user_memory):
    text, _ = await _complete(_orchestrator(), "history of India", "well so basically the", "length")

    assert text == "well so basically the"


async def test_a_clipboard_rewrite_keeps_its_budget_and_is_not_trimmed(user_memory, monkeypatch):
    monkeypatch.setattr(dictation, "get_clipboard_text", lambda: "teh quick brown fox jump")
    transcript = "fix the grammar in my clipboard"
    assert dictation.is_clipboard_command(transcript)
    assert dictation.get_clipboard_action(transcript) == "fix"

    text, request = await _complete(_orchestrator(), transcript, CAPPED, "length")

    assert request.max_tokens == IntegrationOrchestrator._CLIPBOARD_REWRITE_MAX_TOKENS
    assert text == CAPPED


async def test_the_voice_adapter_reports_a_capped_reply(monkeypatch):
    """The adapter used to hard-code finish_reason="stop", hiding the cap."""
    from Agent_Guru.llm.models import CompletionRequest, Message, OllamaConfig
    from Agent_Guru.llm.providers.ollama_adapter import OllamaAdapter

    for name, value in (
        ("OLLAMA_KEEP_ALIVE", "-1"),
        ("OLLAMA_FLASH_ATTENTION", "1"),
        ("OLLAMA_NUM_PARALLEL", "1"),
    ):
        monkeypatch.setenv(name, value)

    class FakeClient:
        async def chat(self, **kwargs):
            return {
                "message": {"content": CAPPED},
                "done_reason": "length",
                "prompt_eval_count": 1619,
                "eval_count": 100,
            }

    adapter = OllamaAdapter(OllamaConfig())
    adapter._client = FakeClient()
    response = await adapter.complete(
        CompletionRequest(
            model="gemma3:4b",
            messages=[Message(role="user", content="history of India")],
            max_tokens=100,
        )
    )
    assert response.finish_reason == "length"
