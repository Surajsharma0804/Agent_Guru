"""The turn evaluation set is well formed and its checks say what they mean.

The set itself runs against a real model (scripts/turn_eval.py); these only
make sure a case cannot silently never match or always match.
"""

from __future__ import annotations

import re

import pytest

from Agent_Guru.integration.turn_eval_set import CASES, NEEDY_PHRASES, SMALL_TALK_OPENING, TurnCase

REQUIRED = {"first_question", "factual", "follow_up", "conversation", "emotional", "memory_session",
            "memory_long_term", "command", "feedback", "failure"}


def test_every_kind_of_turn_is_covered():
    assert {c.category for c in CASES} >= REQUIRED  # nosec B101


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c.category}:{c.said[-1]}")
def test_each_case_is_well_formed(case):
    assert case.said and all(case.said)  # nosec B101
    for pattern in (case.correct, case.wrong, case.intent):
        if pattern:
            re.compile(pattern)
    assert case.correct or case.intent or case.status  # nosec B101  something is judged
    assert not case.answer_first or case.correct  # nosec B101  "answer first" needs to know the answer


def test_the_reply_check_needs_the_answer_and_rejects_the_wrong_one():
    case = TurnCase("factual", ("what is two plus two",), correct=r"\b(?:four|4)\b", wrong=r"\bfive\b")
    assert case.reply_ok("Two plus two is four.") is True  # nosec B101
    assert case.reply_ok("It's five.") is False  # nosec B101
    assert case.reply_ok("Four, or maybe five.") is False  # nosec B101
    assert TurnCase("command", ("open notepad",), intent="x").reply_ok("anything") is None  # nosec B101


@pytest.mark.parametrize("reply", [
    # Openings measured on gemma4 before the first-turn fix.
    "Hey! What's up, man? Haven't talked to ya in a while, how's everything going? Two plus two is four.",
    "Yo! What's up, dude? Haven't chatted with you in a bit, how's everything going with you?",
])
def test_small_talk_openings_are_caught(reply):
    assert SMALL_TALK_OPENING.match(reply)  # nosec B101


@pytest.mark.parametrize("reply", [
    "Oh that's easy - Paris! Have you ever been to France?",
    "Dude, there are seven days in a week, easy.",
    "Hey, the capital of France is Paris.",
])
def test_answers_are_not_taken_for_small_talk(reply):
    assert not SMALL_TALK_OPENING.match(reply)  # nosec B101


def test_needy_phrases_are_caught():
    assert NEEDY_PHRASES.search("Honestly, I missed you so much!")  # nosec B101
    assert not NEEDY_PHRASES.search("I'm glad you're back to studying.")  # nosec B101
