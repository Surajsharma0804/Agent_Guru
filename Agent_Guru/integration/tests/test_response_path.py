"""Regression tests for the response path found on the first Windows run.

The user asked for the time and the Prime Minister. The assistant stored the
question as a life goal, spoke an acknowledgement of it instead of the answer,
and sent the question, prefixed with their earlier conversation, to Google.
"""

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
