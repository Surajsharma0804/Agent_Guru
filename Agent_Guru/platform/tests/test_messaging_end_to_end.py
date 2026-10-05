"""A spoken message reaches the messaging app with its recipient and its exact text.

Before, the action stage received only "communication:send_message:<contact>",
so the text was lost: "send a message to John saying hello" opened the
WhatsApp Web home page with no chat and no message. These run the real
pipeline, the real OSController.send_message, the real MessagingController
and the policy the app starts with. The URL it would open and any Enter it
would press are recorded instead, and whether WhatsApp Desktop is installed
or in front is decided by the test, so nothing opens and nothing is sent.
"""

from __future__ import annotations

import numpy as np
import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent
from Agent_Guru.platform.controllers.messaging_controller import MessagingController
from Agent_Guru.platform.os_controller import OSController
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies


class Controller:
    """OSController's real send_message over a real MessagingController; URLs recorded."""

    send_message = OSController.send_message

    def __init__(self, tmp_path, *, whatsapp_desktop=False, whatsapp_in_front=True):
        self.opened: list[str] = []
        self.enter_presses = 0
        m = MessagingController(platform_override="windows", contacts_path_override=tmp_path / "contacts.json")
        m._blocking_open_url = self.opened.append
        m._whatsapp_desktop_installed = lambda: whatsapp_desktop
        m._foreground_is_whatsapp = lambda: whatsapp_in_front
        m._press_enter = self._press
        m._WHATSAPP_FRONT_TIMEOUT_S, m._WHATSAPP_SETTLE_S = 0.5, 0.01
        self._messaging_controller = m

    def _press(self):
        self.enter_presses += 1

    def open_url(self, url):
        self.opened.append(url)


class Transcript:
    def __init__(self, text):
        self.text = text

    async def transcribe(self, audio):
        return type("R", (), {"text": self.text, "language": "en", "language_probability": 0.99})()


def _policy():
    # The policy main.py starts the app with.
    engine = PolicyEngine()
    install_default_policies(engine)
    return engine


@pytest.fixture
def ctrl(tmp_path):
    return Controller(tmp_path)


async def _say(text, ctrl):
    orch = IntegrationOrchestrator(
        speech_engine=Transcript(text), vision_engine=None, llm_runtime=None,
        platform_controller=ctrl, agent_orchestrator=None, memory=None, reasoning=None,
        security=None, policy=_policy(), avatar=None, deployment=None, gpu_pool=None,
    )
    spoken = []

    async def tts(t, personality):
        spoken.append(t)

    async def silent(*a, **k):
        return None

    async def no_browser():
        raise RuntimeError("tests never start a browser")

    orch._stage_tts, orch._play_filler, orch._get_browser_mgr = tts, silent, no_browser
    await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=np.zeros(16000, np.float32).tobytes()))
    return spoken[0] if spoken else None


async def test_message_to_a_number_opens_that_chat_with_the_text(ctrl):
    spoken = await _say("send a message to +919876543210 saying hello", ctrl)
    assert ctrl.opened == ["https://wa.me/919876543210?text=hello"]  # nosec B101
    assert "ready in WhatsApp" in spoken  # nosec B101


async def test_saved_contact_gets_the_exact_text(ctrl):
    await ctrl._messaging_controller.add_contact("John", whatsapp="+15551234567")
    await _say("send a message to John saying I'm late and sorry", ctrl)
    # The apostrophe survives HTML escaping, "and" is not split into a second
    # step, and "sorry" is not removed as a filler word.
    assert ctrl.opened == ["https://wa.me/15551234567?text=I%27m%20late%20and%20sorry"]  # nosec B101


async def test_text_with_a_colon_is_kept_whole(ctrl):
    await _say("text +15551234567: running late, home by 7:30", ctrl)
    assert ctrl.opened == ["https://wa.me/15551234567?text=running%20late%2C%20home%20by%207%3A30"]  # nosec B101


async def test_named_app_is_used(ctrl):
    await _say("send a telegram to alice saying hi", ctrl)
    assert ctrl.opened == ["https://t.me/alice?text=hi"]  # nosec B101


async def test_email_goes_to_the_address(ctrl):
    await _say("send an email to sarah@example.com saying the report is ready", ctrl)
    assert ctrl.opened == ["mailto:sarah@example.com?body=the%20report%20is%20ready"]  # nosec B101


async def test_unknown_name_is_reported_not_sent_to_nobody(ctrl):
    spoken = await _say("send a message to Bob saying hi", ctrl)
    assert ctrl.opened == []  # nosec B101
    assert "Bob" in spoken and "number" in spoken  # nosec B101


async def test_missing_recipient_is_asked_for(ctrl):
    spoken = await _say("send a message saying hello", ctrl)
    assert ctrl.opened == [] and spoken == "Who should I send it to?"  # nosec B101


async def test_without_text_the_app_still_opens_for_the_contact(ctrl):
    # Unchanged behaviour: no text, so nothing to send; WhatsApp is opened.
    spoken = await _say("send a message to John", ctrl)
    assert spoken == "Opening WhatsApp for John"  # nosec B101
    assert ctrl.opened == ["https://web.whatsapp.com"]  # nosec B101


async def test_whatsapp_desktop_sends_the_message_itself(tmp_path):
    ctrl = Controller(tmp_path, whatsapp_desktop=True, whatsapp_in_front=True)
    spoken = await _say("send a message to +919876543210 saying I'm on my way", ctrl)
    assert ctrl.opened == ["whatsapp://send?phone=919876543210&text=I%27m%20on%20my%20way"]  # nosec B101
    assert ctrl.enter_presses == 1  # nosec B101
    assert spoken == "Sent your message to +919876543210 on WhatsApp."  # nosec B101


async def test_enter_is_never_pressed_when_whatsapp_is_not_in_front(tmp_path):
    # An Enter would go to whatever window is in front.
    ctrl = Controller(tmp_path, whatsapp_desktop=True, whatsapp_in_front=False)
    spoken = await _say("send a message to +919876543210 saying hello", ctrl)
    assert ctrl.enter_presses == 0  # nosec B101
    assert "ready in WhatsApp" in spoken and "Press send" in spoken  # nosec B101


@pytest.mark.parametrize(("action", "allowed"), [
    ("communication:send_message:John:whatsapp:hello", True),
    ("communication:reply:Sam:whatsapp:ok", True),
    ("communication:make_call:John", False),
    ("system_control:open_app:notepad", False),
    ("system_control:shutdown", False),
    ("file_ops:delete:C:/x", False),
    ("communication:send_messageX", False),
])
async def test_starting_policy_allows_messaging_and_nothing_else(action, allowed):
    orch = IntegrationOrchestrator.__new__(IntegrationOrchestrator)
    orch.policy = _policy()
    assert await orch._stage_policy(action) is allowed  # nosec B101
