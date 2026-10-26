"""The web search runs on the intent engine's verdict, not on punctuation.

It used to run for any turn that ended in "?" or began with a question word,
including turns the intent engine had classified as conversation, in a
product whose README says it runs 100% locally. The query it sent was the
whole enriched prompt, earlier turns included.
"""

import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator

from .conftest import PRIOR_TURNS


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


async def test_only_this_turn_goes_to_the_search_engine(run_turn):
    question = "Who is the Prime Minister of India currently?"

    turn = await run_turn(question)

    assert turn.web_queries == [question]
    earlier = PRIOR_TURNS[0]["user_message"]
    assert not any(earlier in query for query in turn.web_queries)
    # The recalled turns still reach the local model, which is where they belong.
    prompt = "\n".join(message.content for message in turn.llm.requests[0].messages)
    assert earlier in prompt


def test_a_message_with_a_pipe_in_its_text_is_not_searched():
    """The text after "saying" is the owner's message: split on "|", it sent "my bank pin is 4321" to a search engine."""
    message = "communication:send_message:John:whatsapp:my bank pin is 4321|information:news"
    assert IntegrationOrchestrator._intent_needs_web(message, "my bank pin is 4321|information:news") is False
    # Real steps are still looked at one by one.
    assert IntegrationOrchestrator._intent_needs_web("system_control:open_app:edge|information:news", "") is True


@pytest.mark.parametrize("transcript", [
    "keep an eye on the weather in Delhi every hour and tell me if it rains",
    "check the news every morning", "let me know when the price of gold drops", "watch for rain in Pune hourly",
])
def test_a_request_to_watch_or_repeat_is_not_searched_first(transcript):
    # A search first put its results in front of the model, which answered from them that it
    # could not keep watch (3 of 3 live runs), instead of offering the scheduled check.
    assert IntegrationOrchestrator._intent_needs_web(f"information:weather:{transcript}", transcript) is False


@pytest.mark.parametrize("transcript", ["what is the weather in Delhi", "will it rain today", "tell me the news"])
def test_a_one_time_lookup_is_still_searched(transcript):
    assert IntegrationOrchestrator._intent_needs_web(f"information:weather:{transcript}", transcript) is True
