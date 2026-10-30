"""Scheduled checks and actions run when they should, at most once, only as approved, and say what happened.

The reminder manager only spoke reminders. It now also runs checks (a
read-only tool, repeatedly) and actions (a tool that changes things, on the
owner's approval of exactly it), kept in the same store. A fake tool runner
stands in for MCPToolbox.call here; test_scheduled_tasks_in_turns covers the
real one.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import time
from types import SimpleNamespace

import pytest

from Agent_Guru.platform.features import reminders
from Agent_Guru.platform.features.reminders import (
    ACTION_GRACE_S,
    MIN_CHECK_INTERVAL_S,
    ReminderManager,
    action_fingerprint,
)

ARGS = {"city": "Delhi"}


class Runner:
    """Answers tool calls from a script, counting them."""

    def __init__(self, *outputs, status="success", delay=0.0):
        self.outputs, self.status, self.delay, self.calls = list(outputs), status, delay, []

    async def __call__(self, server, tool, arguments):
        self.calls.append((server, tool, arguments))
        await asyncio.sleep(self.delay)
        output = self.outputs.pop(0) if self.outputs else "same"
        return SimpleNamespace(status=SimpleNamespace(value=self.status), output=output, error="")


@pytest.fixture
def store(tmp_path):
    return tmp_path / "reminders.json"


def _manager(store, runner=None):
    said, audited = [], []
    manager = ReminderManager(speak_callback=said.append, store_path=store)
    manager.set_tool_runner(runner or Runner())
    manager.set_audit(lambda task_id, status, details: audited.append((task_id, status, details)))
    manager.said, manager.audited = said, audited
    return manager


def _kept(store):
    return {t["reminder_id"]: t for t in json.loads(store.read_text(encoding="utf-8"))}


async def _action(manager, *, fire_in=0.05, expires_in=3600.0, arguments=None, every_s=None):
    return await manager.add_action(
        "water the plants", server="home", tool="valve", arguments=arguments or {"zone": 1},
        fire_at=time.time() + fire_in, approved_by="owner", approval_expires_at=time.time() + expires_in,
        every_s=every_s,
    )


# ---- the time a reminder is set for ----


def test_a_time_of_day_is_the_owners_local_time():
    # "11:59 pm" said at 22:32 in India was set for 05:29 the next morning:
    # the time was read as UTC.
    target = (datetime.datetime.now() + datetime.timedelta(hours=1)).replace(second=0, microsecond=0)
    delay = ReminderManager._parse_time_to_delay(target.strftime("%H:%M"))
    assert abs(delay - (target - datetime.datetime.now()).total_seconds()) < 5  # nosec B101


# ---- checks ----


async def test_a_check_says_what_it_found_and_runs_again(store, monkeypatch):
    monkeypatch.setattr(reminders, "MIN_CHECK_INTERVAL_S", 0.1)
    runner = Runner("31 C, haze", "32 C, haze")
    manager = _manager(store, runner)
    await manager.add_check("Delhi weather", server="w", tool="get_weather", arguments=ARGS, every_s=0.2)
    # Until the second run is recorded, then close at once. A fixed 0.35 s
    # sleep left 0.05 s before the third run was due, and a slow CI runner
    # (Python 3.12) overslept it: 3 runs. A third run needs another 0.2 s,
    # so closing right after the second is recorded keeps the count exact.
    def recorded() -> int:
        kept = _kept(store) if store.exists() else {}
        return len(next(iter(kept.values()), {}).get("runs") or [])

    deadline = asyncio.get_running_loop().time() + 5
    while recorded() < 2 and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.01)
    manager.close()
    assert len(runner.calls) == 2 and manager.said[0] == "Your check, Delhi weather: 31 C, haze"  # nosec B101
    assert [r["status"] for r in _kept(store)[next(iter(_kept(store)))]["runs"]] == ["success", "success"]  # nosec B101


async def test_a_check_set_to_changes_only_speaks_when_the_result_changes(store, monkeypatch):
    monkeypatch.setattr(reminders, "MIN_CHECK_INTERVAL_S", 0.1)
    runner = Runner("A", "A", "B")
    manager = _manager(store, runner)
    task = await manager.add_check("watch", server="w", tool="t", arguments={}, every_s=10, notify_when="changed")
    for _ in range(3):
        await manager._run(task)
    manager.close()
    assert manager.said == ["Your check, watch: A", "Your check, watch: B"]  # nosec B101


async def test_a_check_that_fails_says_so(store):
    manager = _manager(store, Runner(status="failed"))
    task = await manager.add_check("watch", server="w", tool="t", arguments={}, every_s=MIN_CHECK_INTERVAL_S,
                                   first_in_s=3600)
    assert await manager._run(task) == "failed"  # nosec B101
    assert manager.said == ["Your check, watch, didn't work this time."]  # nosec B101
    manager.close()


async def test_checks_are_bounded_in_frequency_and_number(store, monkeypatch):
    manager = _manager(store)
    with pytest.raises(ValueError, match="at most every 5 minutes"):
        await manager.add_check("too often", server="w", tool="t", arguments={}, every_s=60)
    monkeypatch.setattr(reminders, "MAX_TASKS", 1)
    await manager.add_check("one", server="w", tool="t", arguments={}, every_s=MIN_CHECK_INTERVAL_S, first_in_s=3600)
    with pytest.raises(ValueError, match="at most 1"):
        await manager.add_check("two", server="w", tool="t", arguments={}, every_s=MIN_CHECK_INTERVAL_S)
    manager.close()


# ---- actions and their approval ----


async def test_an_approved_action_runs_once_at_its_time(store):
    runner = Runner("done")
    manager = _manager(store, runner)
    task = await _action(manager)
    await asyncio.sleep(0.25)
    assert runner.calls == [("home", "valve", {"zone": 1})]  # nosec B101
    assert manager.said == ["Your scheduled task, water the plants, is done."]  # nosec B101
    assert task.reminder_id not in _kept(store)  # nosec B101  a one-off action is done with
    assert manager.audited[-1][1] == "success"  # nosec B101
    manager.close()


async def test_only_the_owner_can_approve(store):
    manager = _manager(store)
    with pytest.raises(ValueError, match="only the owner"):
        await manager.add_action("x", server="s", tool="t", arguments={}, fire_at=time.time() + 60,
                                 approved_by="model", approval_expires_at=time.time() + 600)
    manager.close()


async def test_an_action_changed_after_approval_does_not_run(store):
    runner = Runner()
    manager = _manager(store, runner)
    task = await _action(manager, fire_in=3600)
    task.arguments["zone"] = 9  # someone edits the stored task
    assert await manager._run(task) == "denied" and runner.calls == []  # nosec B101
    assert "changed after you approved it" in manager.said[0]  # nosec B101
    manager.close()


async def test_an_action_whose_approval_expired_does_not_run(store):
    runner = Runner()
    manager = _manager(store, runner)
    task = await _action(manager, fire_in=3600, expires_in=-1)
    assert await manager._run(task) == "denied" and runner.calls == []  # nosec B101
    assert "approval has expired" in manager.said[0]  # nosec B101
    manager.close()


async def test_the_policy_is_asked_again_when_an_action_runs(store):
    # The tool runner is MCPToolbox.call, which asks the policy at call
    # time; a refusal there is reported, not ignored.
    manager = _manager(store, Runner(status="denied"))
    task = await _action(manager, fire_in=3600)
    assert await manager._run(task) == "denied"  # nosec B101
    assert manager.said == ["I wasn't allowed to run your scheduled task, water the plants."]  # nosec B101
    manager.close()


async def test_an_unverified_action_is_reported_as_such_and_not_retried(store):
    runner = Runner(status="unverified")
    manager = _manager(store, runner)
    await _action(manager)
    await asyncio.sleep(0.3)
    assert len(runner.calls) == 1  # nosec B101
    assert manager.said == ["Your scheduled task, water the plants, ran, but I couldn't confirm it worked."]  # nosec B101
    manager.close()


async def test_a_run_that_times_out_is_unverified_for_an_action_and_failed_for_a_check(store, monkeypatch):
    monkeypatch.setattr(reminders, "RUN_TIMEOUT_S", 0.1)
    runner = Runner(delay=1.0)
    manager = _manager(store, runner)
    action = await _action(manager, fire_in=3600)
    check = await manager.add_check("w", server="w", tool="t", arguments={}, every_s=MIN_CHECK_INTERVAL_S, first_in_s=3600)
    assert await manager._run(action) == "unverified" and await manager._run(check) == "failed"  # nosec B101
    manager.close()


async def test_a_task_never_runs_twice_at_once(store):
    runner = Runner(delay=0.2)
    manager = _manager(store, runner)
    task = await _action(manager, fire_in=3600)
    statuses = await asyncio.gather(manager._run(task), manager._run(task))
    assert sorted(statuses) == ["skipped", "success"] and len(runner.calls) == 1  # nosec B101
    manager.close()


# ---- cancelling and switching off ----


async def test_a_cancelled_or_switched_off_task_does_not_run(store, monkeypatch):
    monkeypatch.setattr(reminders, "MIN_CHECK_INTERVAL_S", 0.1)
    runner = Runner()
    manager = _manager(store, runner)
    check = await manager.add_check("w", server="w", tool="t", arguments={}, every_s=0.1)
    action = await _action(manager, fire_in=0.1)
    assert manager.set_enabled(check.reminder_id, False) and manager.cancel_reminder(action.reminder_id)  # nosec B101
    await asyncio.sleep(0.3)
    assert runner.calls == [] and action.reminder_id not in _kept(store)  # nosec B101
    assert _kept(store)[check.reminder_id]["enabled"] is False  # nosec B101
    manager.close()


# ---- after a restart ----


def _write(store, **task):
    base = {"reminder_id": "action_1", "message": "water the plants", "fire_at": time.time() + 3600,
            "created_at": time.time(), "kind": "action", "server": "home", "tool": "valve",
            "arguments": {"zone": 1}, "every_s": None}
    base.update(task)
    base.setdefault("approval", {"fingerprint": action_fingerprint(base["server"], base["tool"], base["arguments"]),
                                 "by": "owner", "approved_at": time.time(), "expires_at": time.time() + 86400})
    store.write_text(json.dumps([base]), encoding="utf-8")


async def test_an_action_interrupted_by_a_restart_is_unverified_and_not_run_again(store):
    _write(store, fire_at=time.time() - 30, running={"run_id": "r1", "started": time.time() - 30})
    runner = Runner()
    manager = _manager(store, runner)
    said = await manager.restore()
    await asyncio.sleep(0.2)
    assert runner.calls == []  # nosec B101
    assert said == ["Your scheduled task, water the plants, was running when I stopped; I can't tell if it finished."]  # nosec B101
    assert manager.audited[0][1] == "unverified"  # nosec B101
    manager.close()


async def test_an_interrupted_check_runs_again_and_records_the_interruption(store):
    _write(store, reminder_id="check_1", kind="check", every_s=600, fire_at=time.time() - 10, approval=None,
           running={"run_id": "r1", "started": time.time() - 10})
    runner = Runner("ok")
    manager = _manager(store, runner)
    await manager.restore()
    await asyncio.sleep(0.2)
    runs = _kept(store)["check_1"]["runs"]
    assert [r["status"] for r in runs] == ["interrupted", "success"] and len(runner.calls) == 1  # nosec B101
    manager.close()


async def test_a_long_missed_action_is_not_run_late(store):
    _write(store, fire_at=time.time() - ACTION_GRACE_S - 3600)
    runner = Runner()
    manager = _manager(store, runner)
    said = await manager.restore()
    await asyncio.sleep(0.2)
    assert runner.calls == [] and said == ["Your scheduled task, water the plants, was due 1 hour 10 minutes ago; I didn't run it late."]  # nosec B101
    manager.close()


async def test_an_action_missed_by_a_little_runs_once(store):
    _write(store, fire_at=time.time() - 30)
    runner = Runner()
    manager = _manager(store, runner)
    await manager.restore()
    await asyncio.sleep(0.2)
    assert len(runner.calls) == 1  # nosec B101
    manager.close()


async def test_many_missed_checks_run_once_not_in_a_burst(store):
    _write(store, reminder_id="check_1", kind="check", every_s=300, fire_at=time.time() - 300 * 50, approval=None)
    runner = Runner()
    manager = _manager(store, runner)
    await manager.restore()
    await asyncio.sleep(0.3)
    assert len(runner.calls) == 1  # nosec B101
    assert _kept(store)["check_1"]["fire_at"] > time.time()  # nosec B101  next run is in the future
    manager.close()


async def test_a_second_copy_of_the_assistant_runs_none_of_the_tasks(store):
    _write(store, fire_at=time.time() - 10)
    # The lock is held by another live process (this test's parent).
    store.with_suffix(".lock").write_text(str(os.getppid()), encoding="utf-8")
    runner = Runner()
    manager = _manager(store, runner)
    assert await manager.restore() == [] and manager.standby  # nosec B101
    await asyncio.sleep(0.2)
    assert runner.calls == []  # nosec B101


async def test_a_lock_left_by_a_stopped_copy_is_taken_over(store):
    _write(store)
    store.with_suffix(".lock").write_text("999999", encoding="utf-8")  # no such process
    manager = _manager(store)
    await manager.restore()
    assert not manager.standby  # nosec B101
    manager.close()
    assert not store.with_suffix(".lock").exists()  # nosec B101


async def test_old_reminder_files_still_load(store):
    store.write_text(json.dumps([{"reminder_id": "r1", "message": "call John", "fire_at": time.time() + 3600,
                                  "created_at": time.time(), "fired": False}]), encoding="utf-8")
    manager = _manager(store)
    await manager.restore()
    assert [r.message for r in manager.list_reminders()] == ["call John"]  # nosec B101
    manager.close()


# A watch for a condition (rain, a temperature) used to be a "contains" match on
# the whole report, which said "chance of rain" every day, and it spoke the first
# 240 characters of the report, source formatting included.

MET_OUTPUT = ("Condition met: It is raining in Delhi, National Capital Territory of Delhi, India now "
              "(light rain, 23.5°C).\n\n[S1] Open-Meteo forecast for Delhi <https://api.open-meteo.com/...>")
NOT_MET_OUTPUT = ("Condition not met: No rain in Delhi, National Capital Territory of Delhi, India now "
                  "(partly cloudy, 23.5°C).\n\n[S1] Open-Meteo forecast ... chance of precipitation 100%")


async def test_a_watch_speaks_only_the_sentence_and_only_when_the_condition_holds(store):
    manager = _manager(store, Runner(NOT_MET_OUTPUT, MET_OUTPUT, NOT_MET_OUTPUT))
    task = await manager.add_check("the Delhi rain watch", server="guru", tool="weather",
                                   arguments={"place": "Delhi", "condition": "rain"},
                                   every_s=MIN_CHECK_INTERVAL_S, first_in_s=3600, notify_when="met")
    for _ in range(3):
        await manager._run(task)
    assert manager.said == ["Your check, the Delhi rain watch: It is raining in Delhi, National Capital Territory "  # nosec B101
                            "of Delhi, India now (light rain, 23.5°C)."]


async def test_a_watch_whose_tool_failed_still_says_so(store):
    manager = _manager(store, Runner(status="failed"))
    task = await manager.add_check("the Delhi rain watch", server="guru", tool="weather", arguments={},
                                   every_s=MIN_CHECK_INTERVAL_S, first_in_s=3600, notify_when="met")
    assert await manager._run(task) == "failed"  # nosec B101
    assert manager.said == ["Your check, the Delhi rain watch, didn't work this time."]  # nosec B101
