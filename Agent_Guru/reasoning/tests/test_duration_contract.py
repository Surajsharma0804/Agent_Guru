"""Durations are whole seconds everywhere, from any producer, and compound phrases are summed.

The fast router produced {'value': 5, 'unit': 'minutes'}, the NER extractor
and the LLM fallback produced seconds, and every one of them kept only one
part of "1 hour 30 minutes". SetTimerTool takes duration_seconds and
compared the dict with 0.
"""

from __future__ import annotations

import asyncio

import pytest

from Agent_Guru.reasoning.intent.engine import IntentDetectionEngine
from Agent_Guru.reasoning.intent.fast_router import FastIntentRouter
from Agent_Guru.reasoning.intent.ner_extractor import NEREntityExtractor
from Agent_Guru.reasoning.models.intent import Entity, Intent
from Agent_Guru.reasoning.tools.examples.timer_tool import SetTimerTool
from Agent_Guru.reasoning.tools.selector import ToolSelector
from Agent_Guru.reasoning.tools.tests.test_selector_property import create_registry
from Agent_Guru.utils.duration import describe_duration, parse_duration, to_seconds

SPOKEN = [
    ("5 seconds", 5), ("1 minute", 60), ("5 minutes", 300), ("1 hour", 3600), ("2 hours", 7200),
    ("90 seconds", 90), ("1 hour 30 minutes", 5400), ("1 minute 30 seconds", 90),
    ("2 hours, 15 minutes and 10 seconds", 8110), ("half an hour", 1800), ("an hour and a half", 5400),
    ("1.5 minutes", 90), ("10 mins", 600), ("3 hrs", 10800),
]


@pytest.mark.parametrize(("text", "seconds"), SPOKEN)
def test_spoken_duration_is_exact_seconds(text, seconds):
    assert parse_duration(f"set a timer for {text}") == seconds  # nosec B101


@pytest.mark.parametrize("text", ["remind me at 3pm", "set a timer", "in 5 hello", "", "soon"])
def test_text_without_a_duration_has_none(text):
    assert parse_duration(text) is None  # nosec B101


@pytest.mark.parametrize(("value", "seconds"), [
    (300, 300), (90.4, 90), ("5 minutes", 300), ({"value": 5, "unit": "minutes"}, 300),
    ({"value": 2, "unit": "hours"}, 7200), ({"minutes": 2, "seconds": 30, "total_seconds": 150}, 150),
])
def test_every_producer_representation_converts_to_seconds(value, seconds):
    assert to_seconds(value) == seconds  # nosec B101


@pytest.mark.parametrize("value", [{"value": 5, "unit": "fortnights"}, {"value": "5"}, None, True, [5], "soon"])
def test_unreadable_duration_is_none_not_a_guess(value):
    assert to_seconds(value) is None  # nosec B101


@pytest.mark.parametrize(("value", "raw", "seconds"), [
    ({"value": 30, "unit": "minutes"}, "1 hour 30 minutes", 5400),  # the fast router kept only "30 minutes"
    ({"value": 5, "unit": "minutes"}, "5 minutes", 300),
    (300, "5 minutes", 300),
    ({"minutes": 2, "seconds": 30, "total_seconds": 150}, "2:30", 150),
    ("half an hour", "half an hour", 1800),
    ("whenever", "whenever", None),
])
def test_duration_entity_value_is_always_seconds(value, raw, seconds):
    entity = Entity(entity_type="duration", value=value, raw_text=raw)
    assert entity.value == seconds and entity.normalized_value == seconds  # nosec B101


def test_other_entity_types_are_untouched():
    entity = Entity(entity_type="person", value={"value": 5, "unit": "minutes"}, raw_text="5 minutes")
    assert entity.value == {"value": 5, "unit": "minutes"}  # nosec B101


@pytest.fixture(scope="module")
def router():
    r = FastIntentRouter()
    r.load_patterns(IntentDetectionEngine().config.patterns_file)
    return r


@pytest.mark.parametrize(("text", "seconds"), [
    ("set timer for 5 minutes", 300), ("set timer for 1 hour 30 minutes", 5400),
    ("set timer for 1 minute 30 seconds", 90), ("set timer for 2 hours", 7200),
])
def test_fast_router_duration_reaches_the_intent_as_seconds(router, text, seconds):
    match = router.match(text)
    assert match is not None  # nosec B101
    assert match.entities["duration"].value == seconds  # nosec B101


@pytest.mark.parametrize(("text", "seconds"), [("2 hours 30 minutes", 9000), ("90 seconds", 90), ("1 hour", 3600)])
def test_ner_normalises_with_the_same_parser(text, seconds):
    assert NEREntityExtractor.__new__(NEREntityExtractor)._normalize_duration(text) == seconds  # nosec B101


def test_timer_tool_receives_canonical_seconds_and_runs(router):
    match = router.match("set timer for 1 hour 30 minutes")
    intent = Intent(intent_type="set_timer", entities=match.entities, confidence=0.95,
                    original_input="set timer for 1 hour 30 minutes")

    async def select_and_run():
        selected = await ToolSelector(await create_registry()).select_tool(intent)
        return selected, await SetTimerTool().execute(**selected.parameters)

    selected, result = asyncio.run(select_and_run())
    assert selected.parameters == {"duration_seconds": 5400}  # nosec B101  was a dict
    assert result["success"] is True  # nosec B101


@pytest.mark.parametrize(("seconds", "words"), [(60, "1 minute"), (5400, "1 hour 30 minutes"), (90, "1 minute 30 seconds"), (7200, "2 hours")])
def test_durations_are_described_exactly(seconds, words):
    assert describe_duration(seconds) == words  # nosec B101
