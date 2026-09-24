"""The web search runs on the intent engine's verdict, not on punctuation.

It used to run for any turn that ended in "?" or began with a question word,
including turns the intent engine had classified as conversation, in a
product whose README says it runs 100% locally.
"""

import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator


@pytest.mark.parametrize(
    "utterance",
    [
        "Tell me a joke?",
        "I feel a bit lonely, can you talk with me?",
        "Thanks, that helped?",
        "What is the capital of France?",
    ],
)
async def test_turns_the_model_can_answer_are_not_searched(run_turn, utterance):
    turn = await run_turn(utterance)

    assert turn.web_queries == []
    assert turn.llm.requests, "the local model still answers"


@pytest.mark.parametrize(
    "utterance",
    [
        "Who is the Prime Minister of India currently?",
        "what's the weather in Delhi",
    ],
)
async def test_questions_about_live_facts_are_searched(run_turn, utterance):
    turn = await run_turn(utterance)

    assert len(turn.web_queries) == 1


@pytest.mark.parametrize(
    ("intent", "needs_web"),
    [
        (None, False),
        ("", False),
        ("conversation:joke", False),
        ("system_control:open_app:notepad", False),
        ("information:time_date:what's the time", False),
        ("information:calculation:what is 12 times 7", False),
        ("information:definition:define entropy", False),
        ("information:question:what is the capital of France", False),
        ("information:question:who is the prime minister now", True),
        ("information:weather:weather in Delhi", True),
        ("information:news:latest news", True),
        ("information:search:search for pasta recipes", True),
        ("system_control:open_app:edge|information:weather:weather in Delhi", True),
    ],
)
def test_the_gate_reads_the_intent(intent, needs_web):
    transcript = intent.rsplit(":", 1)[-1] if intent else ""
    assert IntegrationOrchestrator._intent_needs_web(intent, transcript) is needs_web
