"""A message command's recipient and text are separated, and an unclear recipient is asked about.

The recipient was "up to 30 letters and spaces after 'to'": "send a message
to John saying hello" went to a contact named "John saying hello", "send
John a message saying hello" had no recipient at all, the text was never
extracted, and 'send "hello" to John' was answered as a greeting.
"""

from __future__ import annotations

import numpy as np
import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent
from Agent_Guru.platform.intent_recognizer import IntentRecognizer

_RULES = IntentRecognizer(llm_manager=None)._rule_engine


def _parse(text):
    result = _RULES.recognize(text, "windows")
    return result.intent_type, result.parameters


@pytest.mark.parametrize(("text", "contact", "message"), [
    ("send a message to John saying hello", "John", "hello"),
    ("send John a message saying hello", "John", "hello"),
    ("message John saying hello", "John", "hello"),
    ("send a message to John that says hello", "John", "hello"),
    ('send "hello" to John', "John", "hello"),
    ("send a message to John: hello", "John", "hello"),
    ("send a message to Mary Ann Smith saying see you at 6", "Mary Ann Smith", "see you at 6"),
    ("text mom: running late, home by 7", "mom", "running late, home by 7"),
    ("send an email to Sarah saying the report is ready", "Sarah", "the report is ready"),
    # The first boundary splits; later words belong to the message.
    ("send a message to John saying tell Mary I said hi", "John", "tell Mary I said hi"),
    ("send a message to John saying hello, how are you?", "John", "hello, how are you?"),
])
def test_recipient_and_message_are_separated(text, contact, message):
    intent_type, params = _parse(text)
    assert intent_type == "communication" and params["action"] == "send_message"  # nosec B101
    assert (params["contact"], params["message"]) == (contact, message)  # nosec B101
    assert "clarification" not in params  # nosec B101


@pytest.mark.parametrize(("text", "action", "contact"), [
    ("reply to John saying sounds good", "reply", "John"),
    ("respond to Sam: on my way", "reply", "Sam"),
])
def test_replies_are_separated_too(text, action, contact):
    _, params = _parse(text)
    assert (params["action"], params["contact"]) == (action, contact) and params["message"]  # nosec B101


def test_missing_recipient_is_empty_not_invented():
    _, params = _parse("send a message saying hello")
    assert (params["contact"], params["message"]) == ("", "hello")  # nosec B101


def test_missing_message_is_empty_not_invented():
    _, params = _parse("send a message to John")
    assert (params["contact"], params["message"]) == ("John", "")  # nosec B101


@pytest.mark.parametrize("text", [
    "send a message to John and Mary saying hi",   # two recipients
    "send a message to John, Mary saying hi",
    "message John hello there",                    # no boundary: name and text cannot be told apart
])
def test_unclear_recipient_asks_instead_of_guessing(text):
    _, params = _parse(text)
    assert params["contact"] == "" and params["clarification"]  # nosec B101


def test_calls_still_extract_the_contact():
    assert _parse("call John")[1]["contact"] == "John"  # nosec B101


class RecordingController:
    def __init__(self):
        self.opened = []

    def open_url(self, url):
        self.opened.append(url)


class FakeSpeech:
    def __init__(self, transcript):
        self.transcript = transcript

    async def transcribe(self, audio):
        return type("R", (), {"text": self.transcript, "language": "en", "language_probability": 0.99})()


class AllowPolicy:
    def evaluate(self, intent):
        return True


async def test_live_pipeline_addresses_the_recipient_only():
    ctrl = RecordingController()
    orch = IntegrationOrchestrator(
        speech_engine=FakeSpeech("send a message to John saying hello"), vision_engine=None, llm_runtime=None,
        platform_controller=ctrl, agent_orchestrator=None, memory=None, reasoning=None,
        security=None, policy=AllowPolicy(), avatar=None, deployment=None, gpu_pool=None,
    )
    spoken = []

    async def capture(text, personality):
        spoken.append(text)

    async def silent(*a, **k):
        return None

    orch._stage_tts = capture
    orch._play_filler = silent
    await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=np.zeros(16000, np.float32).tobytes()))
    assert spoken == ["Opening WhatsApp for John"]  # nosec B101  was "... for John saying hello"
    assert ctrl.opened == ["https://web.whatsapp.com"]  # nosec B101  recorded, never opened
