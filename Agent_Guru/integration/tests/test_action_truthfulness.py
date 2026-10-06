"""The reply says what an action did, never "Done." by default.

A turn whose action produced no reply was answered "Done.": an action the
policy refused (with the starting policy, everything but messaging: "open
notepad" was answered "Done." and nothing opened), an action that raised,
a command nothing handled. And most action handlers returned a fixed reply
("Window minimized", "Done" for media keys) whatever the controller's
OperationResult said.

These run whole turns through run_pipeline with a controller whose calls
succeed, fail, raise or return nothing, and check what is spoken and the
turn's action_status.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Agent_Guru.integration.orchestrator import (
    ActionStatus,
    IntegrationOrchestrator,
    WakeWordEvent,
    _call_status,
)

OK = SimpleNamespace(success=True, message="ok", error=None)
FAILED = SimpleNamespace(success=False, message="", error="Access is denied")


class Controller:
    """Every call returns `returns`, or raises it if it is an exception."""

    def __init__(self, returns):
        self.returns, self.calls = returns, []

    def _call(self, name, *args, **kwargs):
        self.calls.append(name)
        if isinstance(self.returns, Exception):
            raise self.returns
        return self.returns

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda *a, **k: self._call(name, *a, **k)


class Policy:
    def __init__(self, allow):
        self.allow = allow

    def evaluate(self, intent):
        return self.allow


async def _turn(said, ctrl=None, allow=True):
    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=None, platform_controller=ctrl,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=Policy(allow),
        avatar=None, deployment=None, gpu_pool=None,
    )
    spoken = []

    async def stt(*a, **k):
        return said, "en"

    async def tts(text, personality):
        spoken.append(text)

    async def silent(*a, **k):
        return None

    orch._stage_stt, orch._stage_tts, orch._play_filler = stt, tts, silent
    result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=np.zeros(16000, np.float32).tobytes()))
    return result, spoken[0] if spoken else None


async def test_a_successful_action_keeps_its_reply():
    result, spoken = await _turn("minimize the window", Controller(OK))
    assert spoken == "Window minimized"  # nosec B101
    assert result.action_status is ActionStatus.SUCCESS  # nosec B101


async def test_a_failed_action_is_not_reported_done():
    # Before: "Window minimized" whatever minimize_window returned.
    result, spoken = await _turn("minimize the window", Controller(FAILED))
    assert spoken == "Sorry, that didn't work."  # nosec B101
    assert result.action_status is ActionStatus.FAILED  # nosec B101


async def test_a_refused_action_is_not_reported_done():
    # Before: "Done.", and nothing was opened.
    ctrl = Controller(OK)
    result, spoken = await _turn("open notepad", ctrl, allow=False)
    assert spoken == "I can't do that - it isn't allowed in my current settings."  # nosec B101
    assert result.action_status is ActionStatus.DENIED and ctrl.calls == []  # nosec B101


async def test_an_action_that_raises_is_not_reported_done():
    result, spoken = await _turn("minimize the window", Controller(OSError("device gone")))
    assert spoken == "Sorry, that didn't work."  # nosec B101
    assert result.action_status is ActionStatus.FAILED  # nosec B101
    assert "device gone" not in spoken  # nosec B101  no raw errors in the reply


async def test_a_call_that_says_nothing_is_unverified():
    # None is not a result. "Next track" used to be said regardless.
    result, spoken = await _turn("next track", Controller(None))
    assert spoken == "I tried, but I couldn't confirm that it worked."  # nosec B101
    assert result.action_status is ActionStatus.UNVERIFIED  # nosec B101


async def test_a_close_without_a_result_is_not_closed():
    # close_application's success defaulted to True, so None said "Closed".
    result, spoken = await _turn("close notepad", Controller(None))
    assert spoken == "Failed to close notepad"  # nosec B101
    assert result.action_status is ActionStatus.FAILED  # nosec B101


async def test_an_open_that_fails_says_so():
    result, spoken = await _turn("open notepad", Controller(FAILED))
    assert "couldn't open notepad" in spoken  # nosec B101
    assert result.action_status is ActionStatus.FAILED  # nosec B101


async def test_an_open_that_works_keeps_its_reply():
    result, spoken = await _turn("open notepad", Controller(OK))
    assert spoken == "Opening notepad for you! What are we doing?"  # nosec B101
    assert result.action_status is ActionStatus.SUCCESS  # nosec B101


async def test_an_error_message_is_not_taken_for_success():
    # A result carrying words, not a success flag of True, is not success.
    said_ok = SimpleNamespace(success=False, message="Done! Window minimized successfully")
    result, spoken = await _turn("minimize the window", Controller(said_ok))
    assert spoken == "Sorry, that didn't work."  # nosec B101
    assert result.action_status is ActionStatus.FAILED  # nosec B101


async def test_a_command_nothing_handles_is_not_reported_done():
    result, spoken = await _turn("minimize the window", ctrl=None)
    assert spoken == "Sorry, I couldn't do that."  # nosec B101
    assert result.action_status is None  # nosec B101


@pytest.mark.parametrize(("value", "status"), [
    (OK, ActionStatus.SUCCESS),
    (FAILED, ActionStatus.FAILED),
    (True, ActionStatus.SUCCESS),
    (False, ActionStatus.FAILED),
    (None, ActionStatus.UNVERIFIED),
    (SimpleNamespace(success="yes"), ActionStatus.UNVERIFIED),  # words are not a success flag
    (b"png bytes", ActionStatus.SUCCESS),
])
def test_what_a_call_returned_decides_its_status(value, status):
    assert _call_status(value) is status  # nosec B101
