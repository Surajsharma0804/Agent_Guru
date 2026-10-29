"""Every action gets its target as said: &, <, >, quotes and Devanagari are not HTML-escaped.

The action stage HTML-escaped the whole intent before reading the target out of it, so a controller
was asked to close "AT&amp;T", a web search looked for "AT&amp;T", and replies built from the target
were escaped a second time ("AT&amp;amp;T") and spoken as "amp". The controller here records calls.
"""

from __future__ import annotations

import tempfile
import urllib.parse
from pathlib import Path

import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator

NAME = 'AT&T "R&D" नमस्ते'  # three words, so the open gate takes it as a name
TEXT = "5 < 6 & \"yes\" it's नमस्ते"


class Controller:
    def __init__(self, running):
        self.calls, self.running = [], running

    def app_instances(self, name):
        return {1: True} if self.running else {}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        async def sent(*args, **kwargs):
            self.calls.append((name, args))
            return "sent"

        def call(*args, **kwargs):
            self.calls.append((name, args))
            return {"success": True}

        return sent if name == "send_message" else call


@pytest.fixture
def act():
    made = []

    async def run(intent, running=True):
        ctrl = Controller(running)
        orch = IntegrationOrchestrator(
            speech_engine=None, vision_engine=None, llm_runtime=None, platform_controller=ctrl,
            agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=None, avatar=None,
            deployment=None, gpu_pool=None, reminder_store=Path(tempfile.mkdtemp()) / "r.json",
        )
        orch._APP_OPEN_VERIFY_S = 0.0

        async def no_browser():
            raise RuntimeError("no browser in tests")

        orch._get_browser_mgr = no_browser
        made.append(orch)
        outcome = await orch._execute_single_action(intent, "full", "")
        return ctrl.calls, outcome.text or ""

    yield run
    for orch in made:
        orch.close_scheduler()


@pytest.mark.parametrize("action, running", [
    ("open_app", False), ("open_file", False), ("close_app", True), ("switch_app", True),
])
async def test_an_app_name_reaches_the_controller_as_said(act, action, running):
    calls, reply = await act(f"system_control:{action}:{NAME}", running=running)
    names = [args[0] for called, args in calls if args]
    assert NAME in names and not any("&amp;" in n or "&lt;" in n or "&quot;" in n for n in names)  # nosec B101
    assert "&amp;" not in reply and "&quot;" not in reply  # nosec B101


async def test_a_web_search_looks_for_what_was_said(act):
    calls, reply = await act(f"system_control:web_search:{TEXT}:google")
    (url,) = [args[0] for called, args in calls if called == "open_url"]
    assert urllib.parse.quote_plus(TEXT) in url  # nosec B101
    assert reply == f"Searching for {TEXT} on google"  # nosec B101


async def test_a_message_and_its_contact_are_sent_as_said(act):
    calls, reply = await act(f"communication:send_message:Tom O'Brien & Co:whatsapp:{TEXT}")
    assert ("send_message", ("whatsapp", "Tom O'Brien & Co", TEXT)) in calls  # nosec B101
    assert "Tom O'Brien & Co" in reply  # nosec B101


async def test_typed_text_is_typed_as_said(act):
    calls, reply = await act(f"system_control:type_text:{TEXT}")
    assert any(TEXT in args for called, args in calls)  # nosec B101
    assert "&lt;" not in reply and "&amp;" not in reply  # nosec B101


async def test_a_spoken_search_reply_is_not_escaped(act):
    calls, reply = await act(f"information:search:{TEXT}")
    assert reply == f"Searching for {TEXT}" or TEXT in reply  # nosec B101
    assert "&amp;" not in reply and "&#x27;" not in reply  # nosec B101
