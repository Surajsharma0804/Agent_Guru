"""Regression tests for over-capture in user_memory._FACT_PATTERNS.

Every fact these patterns extract is written to a pinned key that is never
evicted and is repeated back to the user in the companion prompt, so a
question mistaken for a fact is a lasting error, not a one-turn glitch. The
first Windows run stored "I want to know who is the Prime Minister of India"
as the user's current goal.
"""

import pytest

from Agent_Guru.platform.features.user_memory import extract_user_fact

WINDOWS_TRANSCRIPT = (
    "Hey Guru, what's the time right now? And I want to know the timing, "
    "current time of India, and also I want to know who is the Prime Minister "
    "of India currently"
)


@pytest.mark.parametrize(
    "utterance",
    [
        WINDOWS_TRANSCRIPT,
        "I want to know what time it is",
        "I'm trying to find out who won the match",
        "I want to talk to you about my day",
        "Can I speak to Rahul?",
        "Do you think I like her?",
        "Hi like the new song?",
        "I am 25 minutes late",
        "I love you",
        "I'm working on it",
        "call me back in ten minutes",
        "Can you call me a cab?",
        "I'm a bit tired",
        "my wife is angry with me",
        "my friend is sick",
        "I speak to my mom every day",
    ],
)
def test_questions_and_requests_are_not_stored_as_facts(utterance):
    assert extract_user_fact(utterance) is None


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("I want to learn Spanish", ("current_goal", "learn Spanish")),
        ("I'm trying to lose weight and get fit", ("current_goal", "lose weight and get fit")),
        # A request verb in one clause must not hide a real goal in the next.
        ("I want to know the time and I want to learn Spanish", ("current_goal", "learn Spanish")),
        ("my goal is to run a marathon", ("current_goal", "run a marathon")),
        ("my name is Suraj", ("name", "Suraj")),
        ("I am Suraj and I love cricket", ("name", "Suraj")),
        ("call me Chotu", ("nickname", "Chotu")),
        ("I live in Delhi", ("location", "Delhi")),
        ("I am 22 years old", ("age", "22")),
        ("I'm 30.", ("age", "30")),
        ("I love hiking, photography and cooking", ("hobbies", "hiking, photography and cooking")),
        ("I am a teacher", ("occupation", "teacher")),
        ("I work as a nurse", ("occupation", "nurse")),
        ("I'm working on a chess engine", ("current_project", "a chess engine")),
        ("I speak Hindi", ("preferred_language", "Hindi")),
        ("my wife is Priya", ("family", "Priya")),
        ("my mom is named Sunita", ("family", "Sunita")),
        ("my best friend is Rahul", ("friends", "Rahul")),
        # A preference command phrased as a question is still a command.
        ("Can you talk to me in Hindi?", ("code_mixing", "hinglish")),
        ("talk to me in English only", ("code_mixing", "english")),
    ],
)
def test_real_facts_are_still_extracted(utterance, expected):
    assert extract_user_fact(utterance) == expected


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("I want to learn Spanish. What is the weather today?", ("current_goal", "learn Spanish")),
        ("I live in Mumbai, what is the weather there?", ("location", "Mumbai")),
        ("I'm a teacher, what's the time?", ("occupation", "teacher")),
    ],
)
def test_a_fact_value_stops_where_its_clause_ends(utterance, expected):
    assert extract_user_fact(utterance) == expected
