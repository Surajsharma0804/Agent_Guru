"""The time_date action must mean "read me the clock", nothing broader.

time_date is answered from the system clock without the LLM, so anything it
matches gets the time as its whole reply. It used to match any mention of
time, date, day or today.
"""

import pytest

from Agent_Guru.platform.intent_recognizer import IntentRecognizer


@pytest.fixture(scope="module")
def recognize():
    engine = IntentRecognizer(llm_manager=None)._rule_engine
    return lambda text: engine.recognize(text, "windows")


@pytest.mark.parametrize(
    "utterance",
    [
        "what's the time right now?",
        "What time is it?",
        "what is the date today",
        "what day is it",
        "what's today's date",
        "Can you tell me the time please",
        "bhai kitne baje hain",
        "time kya hua",
        "Hey Guru, what's the time right now? And I want to know the timing, "
        "current time of India, and also I want to know who is the Prime "
        "Minister of India currently",
    ],
)
def test_clock_questions_are_time_date(recognize, utterance):
    result = recognize(utterance)
    assert (result.intent_type, result.parameters.get("action")) == ("information", "time_date")


@pytest.mark.parametrize(
    "utterance",
    [
        "How was your day?",
        "I had a long day",
        "today I feel great",
        "what is the time complexity of quicksort?",
        "what's the date of Diwali this year?",
        "what time is it in London?",
        "what's the time in Tokyo",
    ],
)
def test_other_mentions_of_time_are_not_time_date(recognize, utterance):
    assert recognize(utterance).parameters.get("action") != "time_date"
