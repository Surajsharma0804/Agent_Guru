"""Timer responses say the duration in words, whatever form it was spoken in.

Duration entities carry whole seconds (utils.duration). The spoken template
and the timer card used to print the entity value as it was, so once every
producer gave seconds they said "Timer set for 300".
"""

from __future__ import annotations

import pytest

from Agent_Guru.reasoning.models.intent import Entity, Intent
from Agent_Guru.reasoning.models.result import ExecutionResult, ResponseModality
from Agent_Guru.reasoning.response.rich_content_generator import ClientCapability, RichContentGenerator
from Agent_Guru.reasoning.response.template_generator import TemplateGenerator

CASES = [("5 minutes", "5 minutes"), ("1 hour 30 minutes", "1 hour 30 minutes"),
         ("90 seconds", "1 minute 30 seconds"), ("2 hours", "2 hours")]


def _timer(spoken):
    intent = Intent(intent_type="set_timer", confidence=0.9, original_input=f"set a timer for {spoken}",
                    entities={"duration": Entity(entity_type="duration", value=None, raw_text=spoken)})
    result = ExecutionResult(success=True, action_id="timer.set", tool_id="timer.set",
                             result_data={"duration_seconds": intent.entities["duration"].value}, execution_time=0.01)
    return intent, result


@pytest.mark.parametrize(("spoken", "words"), CASES)
def test_spoken_reply_says_the_duration_in_words(spoken, words):
    intent, result = _timer(spoken)
    text = TemplateGenerator().generate(result=result, intent=intent, modality=ResponseModality.VOICE).text
    assert text == f"Timer set for {words}"  # nosec B101  was "Timer set for 300"


@pytest.mark.parametrize(("spoken", "words"), CASES)
def test_timer_card_says_the_duration_in_words(spoken, words):
    intent, result = _timer(spoken)
    card = RichContentGenerator().generate(result, intent, {ClientCapability.CARDS, ClientCapability.BUTTONS})
    assert card["body"] == f"Timer for {words} is now active"  # nosec B101
