"""A tool is selected only if it can run: its required arguments exist and it serves the intent.

Tier 2 used to rank every tool on vocabulary and never check required
parameters, so a set_timer intent with an entity named "recipient" and no
duration selected messaging.send with no message. Hypothesis found it in
test_selector_property.py only when it happened to generate that intent;
these pin the rule down for the cases around it.
"""

from __future__ import annotations

import pytest

from Agent_Guru.reasoning.models.intent import Entity, Intent
from Agent_Guru.reasoning.tools.selector import ToolSelector
from Agent_Guru.reasoning.tools.tests.test_selector_property import create_registry


def _entity(value, entity_type="text"):
    return Entity(entity_type=entity_type, value=value, raw_text=str(value))


def _intent(intent_type, text, **entities):
    return Intent(intent_type=intent_type, original_input=text, entities=entities, confidence=0.9)


async def _select(intent):
    return await ToolSelector(await create_registry()).select_tool(intent)


def _runnable(result):
    required = {p.name for p in result.tool.metadata.parameters if p.required}
    return required.issubset({k for k, v in result.parameters.items() if v not in (None, "")})


async def test_timer_with_an_entity_named_recipient_does_not_send_a_message():
    # The counterexample Hypothesis found, as it was generated.
    result = await _select(_intent("set_timer", "000 A", recipient=_entity(1, "duration")))
    assert result is None  # nosec B101  was messaging.send with {'recipient': 1}


async def test_timer_with_only_an_unrelated_entity_selects_nothing():
    result = await _select(_intent("set_timer", "set a timer", colour=_entity("red")))
    assert result is None  # nosec B101  no duration: the caller has to ask for one


async def test_timer_with_a_duration_still_selects_the_timer():
    result = await _select(_intent(
        "set_timer", "set a timer for ten minutes",
        duration_seconds=_entity(600, "duration"), colour=_entity("red"),
    ))
    assert result.tool.metadata.tool_id == "timer.set"  # nosec B101
    assert result.parameters == {"duration_seconds": 600}  # nosec B101


async def test_message_with_recipient_and_text_is_sent():
    result = await _select(_intent(
        "send_message", "tell John hello", recipient=_entity("John", "person"), message=_entity("hello"),
    ))
    assert result.tool.metadata.tool_id == "messaging.send"  # nosec B101
    assert result.parameters == {"recipient": "John", "message": "hello"}  # nosec B101


async def test_message_without_text_is_not_sent():
    result = await _select(_intent("send_message", "message John", recipient=_entity("John", "person")))
    assert result is None  # nosec B101


async def test_ambiguous_wording_selects_the_only_runnable_tool():
    # Message vocabulary, but only a duration was extracted: the timer is the
    # one tool that can run.
    result = await _select(_intent(
        "unknown", "send me a message when the timer is done", duration_seconds=_entity(300, "duration"),
    ))
    assert result is not None and result.tool.metadata.tool_id == "timer.set"  # nosec B101


async def test_classified_timer_never_becomes_a_message_even_with_message_entities():
    # Every argument messaging.send needs is present, but the request was a
    # timer: another intent's tool must not replace it.
    result = await _select(_intent(
        "set_timer", "remind John with a message", recipient=_entity("John", "person"), message=_entity("hi"),
    ))
    assert result is None  # nosec B101


@pytest.mark.parametrize("intent_type", ["set_timer", "cancel_timer", "query_weather", "send_message", "unknown"])
@pytest.mark.parametrize("entities", [
    {},
    {"recipient": "John"},
    {"message": "hi"},
    {"recipient": "John", "duration": 5},
    {"location": "Paris", "message": "hi"},
    {"timer": "abc"},
])
async def test_no_selection_ever_misses_a_required_argument(intent_type, entities):
    # Wording that overlaps every tool's vocabulary, so Tier 2 has candidates.
    text = "send a message about the timer and the weather location to my contacts"
    result = await _select(_intent(intent_type, text, **{k: _entity(v) for k, v in entities.items()}))
    assert result is None or _runnable(result)  # nosec B101


async def test_between_runnable_candidates_the_better_match_wins():
    result = await _select(_intent(
        "unknown", "send a message to John saying hello",
        recipient=_entity("John", "person"), message=_entity("hello"), duration_seconds=_entity(60, "duration"),
    ))
    assert result.tool.metadata.tool_id == "messaging.send"  # nosec B101
    assert _runnable(result)  # nosec B101


async def test_repeated_selection_is_identical():
    intent = _intent("unknown", "send a message to John saying hello",
                     recipient=_entity("John", "person"), message=_entity("hello"))
    fresh = {(await _select(intent)).tool.metadata.tool_id for _ in range(10)}
    selector = ToolSelector(await create_registry())
    reused = {(await selector.select_tool(intent)).tool.metadata.tool_id for _ in range(10)}
    assert fresh == reused == {"messaging.send"}  # nosec B101


@pytest.mark.parametrize("value", [None, "", "   "])
async def test_empty_extracted_argument_does_not_count(value):
    result = await _select(_intent(
        "send_message", "message John", recipient=_entity("John", "person"), message=_entity(value),
    ))
    assert result is None  # nosec B101  would have sent an empty message
