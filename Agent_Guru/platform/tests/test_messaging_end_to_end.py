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

from urllib.parse import unquote

import numpy as np
import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent
from Agent_Guru.platform.controllers.messaging_controller import MessagingController
from Agent_Guru.platform.controllers.whatsapp_view import Message, View
from Agent_Guru.platform.os_controller import OSController
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies


class WhatsApp:
    """WhatsApp Desktop as measured: a link adds its text to the box, Enter sends the box.

    statuses: what the sent message's status button shows on each look after
    Enter ("pending", "sent", ...; None for no button). sends=False: Enter
    does nothing. readable=False: the window cannot be read.
    """

    def __init__(self, *, draft="", earlier=(), statuses=("sent",), sends=True, readable=True):
        self.box = draft
        self.messages = [(f"earlier-{i}", text, "read") for i, text in enumerate(earlier)]
        self.statuses, self.sends, self.readable = list(statuses), sends, readable
        self.sent_text = None

    def open(self, url):
        if url.startswith("whatsapp://send"):
            self.box += unquote(url.split("&text=", 1)[1])

    def enter(self):
        if self.sends and self.box:
            self.sent_text, self.box = self.box, ""

    def view(self, text):
        if not self.readable:
            return None
        msgs = [Message(k, s) for k, t, s in self.messages if t == text]
        if self.sent_text == text:
            status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            msgs.append(Message("new", status))
        return View(self.box, msgs)


class Controller:
    """OSController's real send_message over a real MessagingController; URLs recorded."""

    send_message = OSController.send_message

    def __init__(self, tmp_path, *, whatsapp_desktop=False, whatsapp_in_front=True, whatsapp=None):
        self.opened: list[str] = []
        self.enter_presses = 0
        self.whatsapp = whatsapp or WhatsApp()
        m = MessagingController(platform_override="windows", contacts_path_override=tmp_path / "contacts.json")
        m._blocking_open_url = self._open
        m._whatsapp_desktop_installed = lambda: whatsapp_desktop
        m._foreground_is_whatsapp = lambda: whatsapp_in_front
        m._press_enter = self._press
        m._whatsapp_view = self.whatsapp.view
        m._WHATSAPP_FRONT_TIMEOUT_S, m._WHATSAPP_SETTLE_S = 0.5, 0.01
        m._WHATSAPP_VERIFY_TIMEOUT_S, m._WHATSAPP_VERIFY_POLL_S = 0.2, 0.01
        self._messaging_controller = m

    def _open(self, url):
        self.opened.append(url)
        self.whatsapp.open(url)

    def _press(self):
        self.enter_presses += 1
        self.whatsapp.enter()

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


class Session:
    """One orchestrator spoken to turn after turn, as the running app is."""

    def __init__(self, ctrl):
        self.transcript = Transcript("")
        self.orch = IntegrationOrchestrator(
            speech_engine=self.transcript, vision_engine=None, llm_runtime=None,
            platform_controller=ctrl, agent_orchestrator=None, memory=None, reasoning=None,
            security=None, policy=_policy(), avatar=None, deployment=None, gpu_pool=None,
        )
        self.spoken: list[str] = []
        self.last = None

        async def tts(t, personality):
            self.spoken.append(t)

        async def silent(*a, **k):
            return None

        async def no_browser():
            raise RuntimeError("tests never start a browser")

        self.orch._stage_tts, self.orch._play_filler, self.orch._get_browser_mgr = tts, silent, no_browser

    async def say(self, text):
        self.transcript.text = text
        before = len(self.spoken)
        self.last = await self.orch.run_pipeline(
            WakeWordEvent(wake_word="Hey Guru", audio=np.zeros(16000, np.float32).tobytes()),
        )
        return self.spoken[before] if len(self.spoken) > before else None


async def _say(text, ctrl):
    return await Session(ctrl).say(text)


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


async def test_without_text_the_recipient_is_asked_what_to_send(ctrl):
    # Before: "Opening WhatsApp for John", an empty app and no message.
    session = Session(ctrl)
    assert await session.say("send a message to John") == "What would you like me to send John?"  # nosec B101
    assert session.last.awaiting_reply  # nosec B101
    assert ctrl.opened == []  # nosec B101


async def test_the_answer_is_read_back_and_sent_on_yes(tmp_path):
    ctrl = Controller(tmp_path, whatsapp_desktop=True, whatsapp_in_front=True)
    await ctrl._messaging_controller.add_contact("John", whatsapp="+15551234567")
    session = Session(ctrl)
    await session.say("Send John a message.")
    read_back = await session.say("I'll reach in 10 minutes")
    assert read_back == "Your message to John says: I'll reach in 10 minutes. Send it?"  # nosec B101
    assert ctrl.opened == [] and session.last.awaiting_reply  # nosec B101  nothing sent yet
    assert await session.say("yes") == "Sent your message to John on WhatsApp."  # nosec B101
    assert ctrl.opened == ["whatsapp://send?phone=15551234567&text=I%27ll%20reach%20in%2010%20minutes"]  # nosec B101
    assert ctrl.enter_presses == 1 and not session.last.awaiting_reply  # nosec B101


@pytest.mark.parametrize("answer", ["no", "hello there", "wait", "send it to Mary instead"])
async def test_anything_but_yes_to_the_read_back_sends_nothing(ctrl, answer):
    await ctrl._messaging_controller.add_contact("John", whatsapp="+15551234567")
    session = Session(ctrl)
    await session.say("send a message to John")
    await session.say("running late")
    assert await session.say(answer) == "Okay, I didn't send it."  # nosec B101
    assert ctrl.opened == []  # nosec B101
    # And the draft is gone: the next "yes" is an ordinary turn.
    await session.say("yes")
    assert ctrl.opened == []  # nosec B101


@pytest.mark.parametrize("answer", ["never mind", "Cancel.", "nahi"])
async def test_the_text_question_can_be_cancelled(ctrl, answer):
    session = Session(ctrl)
    await session.say("send a message to John")
    assert await session.say(answer) == "Okay, I won't send anything."  # nosec B101
    assert ctrl.opened == [] and not session.last.awaiting_reply  # nosec B101


async def test_a_message_with_no_in_it_is_not_taken_as_cancel(ctrl):
    session = Session(ctrl)
    await session.say("send a message to John")
    reply = await session.say("No rush, stop by whenever you can")
    assert reply == "Your message to John says: No rush, stop by whenever you can. Send it?"  # nosec B101


async def test_a_missing_recipient_is_asked_for_and_kept(ctrl):
    await ctrl._messaging_controller.add_contact("John", whatsapp="+15551234567")
    session = Session(ctrl)
    assert await session.say("send a message saying hello") == "Who should I send it to?"  # nosec B101
    assert await session.say("to John") == "Your message to John says: hello. Send it?"  # nosec B101
    await session.say("yes, send it")
    assert ctrl.opened == ["https://wa.me/15551234567?text=hello"]  # nosec B101


async def test_an_unclear_recipient_answer_is_asked_again(ctrl):
    session = Session(ctrl)
    await session.say("send a message saying hello")
    reply = await session.say("John and Mary")
    assert reply == "Sorry, who should I send it to? Say one name or number."  # nosec B101
    assert session.last.awaiting_reply and ctrl.opened == []  # nosec B101


async def test_an_unanswered_question_expires(ctrl, monkeypatch):
    from Agent_Guru.integration import orchestrator

    session = Session(ctrl)
    await session.say("send a message to John")
    real = orchestrator.time.monotonic
    monkeypatch.setattr(orchestrator.time, "monotonic", lambda: real() + orchestrator.MESSAGE_DRAFT_TTL_S + 1)
    # Long after the question, a sentence is a new turn, not John's message.
    await session.say("what time is it")
    assert session.orch._message_draft is None  # nosec B101
    assert ctrl.opened == []  # nosec B101


async def test_a_taught_reply_does_not_answer_the_read_back(tmp_path, monkeypatch):
    from Agent_Guru.platform.features import reaction_rules

    class Rules:
        def match(self, text):
            return "Taught reply" if text.strip().lower() == "yes" else None

    monkeypatch.setattr(reaction_rules, "get_reaction_rules", Rules)
    ctrl = Controller(tmp_path, whatsapp_desktop=True)
    await ctrl._messaging_controller.add_contact("John", whatsapp="+15551234567")
    session = Session(ctrl)
    await session.say("send a message to John")
    await session.say("hello")
    assert await session.say("yes") == "Sent your message to John on WhatsApp."  # nosec B101


async def test_the_policy_is_asked_again_before_sending(ctrl):
    class DenyAll:
        def evaluate(self, intent):
            return False

    await ctrl._messaging_controller.add_contact("John", whatsapp="+15551234567")
    session = Session(ctrl)
    await session.say("send a message to John")
    await session.say("hello")
    session.orch.policy = DenyAll()
    assert await session.say("yes") == "Sorry, I'm not allowed to send that message."  # nosec B101
    assert ctrl.opened == []  # nosec B101


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


# What "sent" means through WhatsApp Desktop: the chat shows the new message
# as sent, delivered or read. Before, it meant only that Enter was pressed.

SAY = "send a message to +919876543210 saying I'm on my way"


async def _desktop(tmp_path, **whatsapp):
    ctrl = Controller(tmp_path, whatsapp_desktop=True, whatsapp=WhatsApp(**whatsapp))
    return ctrl, await _say(SAY, ctrl)


async def test_a_message_shown_as_sent_is_reported_sent(tmp_path):
    ctrl, spoken = await _desktop(tmp_path, statuses=("pending", "pending", "sent"))
    assert spoken == "Sent your message to +919876543210 on WhatsApp."  # nosec B101
    assert ctrl.enter_presses == 1  # nosec B101


async def test_an_unsent_draft_in_the_box_is_not_sent_with_it(tmp_path):
    # The link adds its text after the draft; Enter would have sent both.
    ctrl, spoken = await _desktop(tmp_path, draft="half-written reply ")
    assert ctrl.enter_presses == 0 and ctrl.whatsapp.sent_text is None  # nosec B101
    assert "already had unsent text" in spoken and "didn't send anything" in spoken  # nosec B101


async def test_enter_that_does_not_send_is_reported_and_not_repeated(tmp_path):
    ctrl, spoken = await _desktop(tmp_path, sends=False)
    assert ctrl.enter_presses == 1  # nosec B101  never pressed again
    assert "still in WhatsApp's message box" in spoken and "didn't go" in spoken  # nosec B101


async def test_a_message_still_pending_is_not_reported_sent(tmp_path):
    ctrl, spoken = await _desktop(tmp_path, statuses=("pending",))
    assert ctrl.enter_presses == 1  # nosec B101
    assert spoken == "I sent your message to +919876543210, but WhatsApp hasn't confirmed it has gone yet."  # nosec B101


async def test_an_unreadable_window_is_not_sent_to_blind(tmp_path):
    ctrl, spoken = await _desktop(tmp_path, readable=False)
    assert ctrl.enter_presses == 0  # nosec B101
    assert "ready in WhatsApp" in spoken and "Press send" in spoken  # nosec B101


async def test_an_older_identical_message_is_not_taken_for_the_new_one(tmp_path):
    # The same words were sent before; Enter does nothing this time. The old
    # message must not count as this one having been sent.
    ctrl, spoken = await _desktop(tmp_path, earlier=["I'm on my way"], sends=False)
    assert "didn't go" in spoken  # nosec B101


async def test_a_window_unreadable_after_enter_is_unverified(tmp_path):
    whatsapp = WhatsApp()
    ctrl = Controller(tmp_path, whatsapp_desktop=True, whatsapp=whatsapp)
    real_enter = whatsapp.enter

    def enter_then_unreadable():
        real_enter()
        whatsapp.readable = False

    whatsapp.enter = enter_then_unreadable
    spoken = await _say(SAY, ctrl)
    assert ctrl.enter_presses == 1  # nosec B101
    assert spoken == (  # nosec B101
        "I pressed send, but I couldn't check that it went. Please look at your chat with +919876543210."
    )


@pytest.mark.parametrize(("action", "allowed"), [
    ("communication:send_message:John:whatsapp:hello", True),
    ("communication:reply:Sam:whatsapp:ok", True),
    ("communication:make_call:John", False),
    # Reversible device actions are allowed (policy/defaults.py DEVICE_ACTIONS); keystrokes, settings and power are not.
    ("system_control:open_app:notepad", True),
    ("system_control:type_text:hello", False),
    ("system_control:settings:wifi off", False),
    ("system_control:open_app:notepad|system_control:type_text:hello", False),
    ("system_control:shutdown", False),
    ("file_ops:delete:C:/x", False),
    ("communication:send_messageX", False),
])
async def test_starting_policy_allows_messaging_and_reversible_device_actions_only(action, allowed):
    orch = IntegrationOrchestrator.__new__(IntegrationOrchestrator)
    orch.policy = _policy()
    assert await orch._stage_policy(action) is allowed  # nosec B101
