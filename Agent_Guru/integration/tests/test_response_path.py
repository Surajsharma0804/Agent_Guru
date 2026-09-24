"""Regression tests for the response path found on the first Windows run.

The user asked for the time and the Prime Minister. The assistant stored the
question as a life goal, spoke an acknowledgement of it instead of the answer,
and sent the question, prefixed with their earlier conversation, to Google.
"""

import datetime

from .conftest import LLM_ANSWER, WINDOWS_TRANSCRIPT


async def test_a_question_is_answered_not_stored_as_a_goal(run_turn):
    turn = await run_turn(WINDOWS_TRANSCRIPT)

    assert "current_goal" not in turn.facts
    assert "I'll remember you're working toward" not in (turn.result.action_result or "")


async def test_a_fact_inside_a_question_does_not_replace_the_answer(run_turn):
    turn = await run_turn("My name is Suraj, who is the Prime Minister of India?")

    assert turn.facts.get("name") == "Suraj"
    assert turn.result.action_result is None
    assert turn.result.llm_response == LLM_ANSWER


async def test_the_time_is_read_from_the_local_clock(run_turn, monkeypatch):
    from Agent_Guru.integration import orchestrator

    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    monkeypatch.setattr(
        orchestrator, "_local_now",
        lambda: datetime.datetime(2026, 9, 24, 15, 7, tzinfo=ist),
        raising=False,
    )

    turn = await run_turn("What's the time right now?")

    assert turn.result.action_result == "It's 3:07 PM on Thursday, 24 September 2026."
    assert turn.llm.requests == []
    assert turn.web_queries == []
    assert turn.controller.browser_searches == []


async def test_small_talk_about_the_day_is_not_answered_with_the_clock(run_turn):
    turn = await run_turn("How was your day?")

    assert turn.result.action_result is None
    assert turn.result.llm_response == LLM_ANSWER
