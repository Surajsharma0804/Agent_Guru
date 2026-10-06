"""Opening or closing an application is reported from what is then running.

The reply used to follow open_application() and close_application(), which
report only that the request was made. Measured on Windows 11: "open paint"
returned success and no Paint process ever appeared; "close notepad"
returned success and the Notepad window stayed open. Now the turn looks at
the application's instances (OSController.app_instances) before and after.

These run whole turns through run_pipeline against a fake set of running
applications; ApplicationController's identity rules are tested in
platform/controllers/tests/test_app_identity.py.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest

from Agent_Guru.integration.orchestrator import ActionStatus, IntegrationOrchestrator, WakeWordEvent

OK = SimpleNamespace(success=True, error=None)
FAILED = SimpleNamespace(success=False, error="not found")


class Apps:
    """Running applications, {name: {pid: shows a window}}, and a controller over them.

    appear_after: looks after a launch before the app shows up (None: never).
    close_removes: "all", "one", "window" (the windowed process only) or "none".
    """

    def __init__(self, running=None, *, open_result=OK, close_result=OK, appear_after=1,
                 close_removes="all", readable=True):
        self.running = {k: dict(v) for k, v in (running or {}).items()}
        self.open_result, self.close_result = open_result, close_result
        self.appear_after, self.close_removes, self.readable = appear_after, close_removes, readable
        self.launched, self.closed, self.looks, self.pending = [], [], 0, None

    def app_instances(self, name):
        self.looks += 1
        if self.readable is False or (self.readable == "before" and (self.launched or self.closed)):
            return None
        if self.pending is not None:
            self.pending[1] -= 1
            if self.pending[1] <= 0:
                self.running.setdefault(self.pending[0], {})[900] = True
                self.pending = None
        return dict(self.running.get(name, {}))

    def open_application(self, name):
        self.launched.append(name)
        if isinstance(self.open_result, Exception):
            raise self.open_result
        if getattr(self.open_result, "success", False) and self.appear_after is not None:
            self.pending = [name, self.appear_after]
        return self.open_result

    def close_application(self, name):
        self.closed.append(name)
        if isinstance(self.close_result, Exception):
            raise self.close_result
        inst = self.running.get(name, {})
        if getattr(self.close_result, "success", False):
            if self.close_removes == "all":
                inst.clear()
            elif self.close_removes == "one" and inst:
                inst.pop(next(pid for pid, w in inst.items() if w))
            elif self.close_removes == "window":
                for pid in [p for p, w in inst.items() if w]:
                    inst.pop(pid)
        return self.close_result


class Policy:
    def __init__(self, allow):
        self.allow = allow

    def evaluate(self, intent):
        return self.allow


def _orchestrator(apps, allow=True):
    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=None, platform_controller=apps,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=Policy(allow),
        avatar=None, deployment=None, gpu_pool=None,
    )
    orch._APP_OPEN_VERIFY_S, orch._APP_CLOSE_VERIFY_S, orch._APP_POLL_S = 0.5, 0.5, 0.01
    return orch


async def _turn(said, apps, allow=True, orch=None):
    orch = orch or _orchestrator(apps, allow)
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


# ---- open ----

async def test_an_open_that_shows_up_is_done():
    apps = Apps(appear_after=3)
    result, spoken = await _turn("open notepad", apps)
    assert spoken == "Opening notepad for you! What are we doing?"  # nosec B101
    assert result.action_status is ActionStatus.SUCCESS and apps.launched == ["notepad"]  # nosec B101


async def test_an_open_that_never_shows_up_is_unconfirmed():
    # Measured: "open paint" reported success; no Paint process appeared.
    result, spoken = await _turn("open paint", Apps(appear_after=None))
    assert spoken == "I started paint, but I couldn't confirm that it opened."  # nosec B101
    assert result.action_status is ActionStatus.UNVERIFIED  # nosec B101


async def test_a_launch_that_fails_is_failed():
    result, spoken = await _turn("open notepad", Apps(open_result=FAILED))
    assert "couldn't open notepad" in spoken and result.action_status is ActionStatus.FAILED  # nosec B101


async def test_a_launch_that_raises_is_failed():
    result, spoken = await _turn("open notepad", Apps(open_result=OSError("boom")))
    assert spoken == "Sorry, that didn't work." and result.action_status is ActionStatus.FAILED  # nosec B101


async def test_an_app_already_running_is_not_launched_again():
    apps = Apps({"notepad": {10: True}})
    result, spoken = await _turn("open notepad", apps)
    assert spoken == "notepad is already open."  # nosec B101
    assert result.action_status is ActionStatus.SUCCESS and apps.launched == []  # nosec B101


async def test_a_refused_open_is_denied_and_nothing_runs():
    apps = Apps()
    result, spoken = await _turn("open notepad", apps, allow=False)
    assert result.action_status is ActionStatus.DENIED and apps.launched == [] and apps.looks == 0  # nosec B101


async def test_an_open_that_cannot_be_watched_is_unconfirmed():
    result, spoken = await _turn("open notepad", Apps(readable=False))
    assert spoken == "I started notepad, but I couldn't confirm that it opened."  # nosec B101
    assert result.action_status is ActionStatus.UNVERIFIED  # nosec B101


async def test_cancelling_stops_the_looking():
    apps = Apps(appear_after=None)
    orch = _orchestrator(apps)
    orch._APP_OPEN_VERIFY_S = 30.0
    task = asyncio.ensure_future(_turn("open notepad", apps, orch=orch))
    while not apps.launched:
        await asyncio.sleep(0.01)
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    looks = apps.looks
    await asyncio.sleep(0.1)
    assert apps.looks == looks  # nosec B101  no look after the cancel


# ---- close ----

async def test_a_close_that_removes_the_app_is_done():
    apps = Apps({"notepad": {10: True}})
    result, spoken = await _turn("close notepad", apps)
    assert spoken == "Closed notepad" and result.action_status is ActionStatus.SUCCESS  # nosec B101


async def test_a_close_that_leaves_the_window_is_not_done():
    # Measured: Windows 11 Notepad; one process ended, the window stayed.
    apps = Apps({"notepad": {10: False, 11: True}}, close_removes="none")
    result, spoken = await _turn("close notepad", apps)
    assert spoken == "I tried to close notepad, but it's still open."  # nosec B101
    assert result.action_status is ActionStatus.FAILED  # nosec B101


async def test_a_background_helper_left_running_is_still_closed():
    apps = Apps({"notepad": {10: False, 11: True}}, close_removes="window")
    result, spoken = await _turn("close notepad", apps)
    assert spoken == "Closed notepad" and result.action_status is ActionStatus.SUCCESS  # nosec B101


async def test_a_close_that_fails_is_failed():
    result, spoken = await _turn("close notepad", Apps({"notepad": {10: True}}, close_result=FAILED))
    assert spoken == "Failed to close notepad" and result.action_status is ActionStatus.FAILED  # nosec B101


async def test_a_close_that_raises_is_failed():
    result, spoken = await _turn("close notepad", Apps({"notepad": {10: True}}, close_result=OSError("x")))
    assert spoken == "Sorry, that didn't work." and result.action_status is ActionStatus.FAILED  # nosec B101


async def test_closing_an_app_that_is_not_open_closes_nothing():
    apps = Apps()
    result, spoken = await _turn("close notepad", apps)
    assert spoken == "notepad isn't open."  # nosec B101
    assert result.action_status is ActionStatus.SUCCESS and apps.closed == []  # nosec B101


async def test_a_refused_close_is_denied():
    apps = Apps({"notepad": {10: True}})
    result, _ = await _turn("close notepad", apps, allow=False)
    assert result.action_status is ActionStatus.DENIED and apps.closed == []  # nosec B101


async def test_a_close_that_cannot_be_watched_afterwards_is_unconfirmed():
    apps = Apps({"notepad": {10: True}}, readable="before")
    result, spoken = await _turn("close notepad", apps)
    assert spoken == "I asked notepad to close, but I couldn't confirm that it closed."  # nosec B101
    assert result.action_status is ActionStatus.UNVERIFIED  # nosec B101


async def test_closing_one_of_several_instances_says_so():
    apps = Apps({"notepad": {10: True, 11: True}}, close_removes="one")
    result, spoken = await _turn("close notepad", apps)
    assert spoken == "Closed one notepad window; 1 more still open."  # nosec B101
    assert result.action_status is ActionStatus.SUCCESS  # nosec B101


async def test_an_unrelated_app_does_not_count():
    # The close is judged by notepad's own instances only.
    apps = Apps({"notepad": {10: True}, "paint": {20: True}})
    _, spoken = await _turn("close notepad", apps)
    assert spoken == "Closed notepad" and apps.running["paint"] == {20: True}  # nosec B101
