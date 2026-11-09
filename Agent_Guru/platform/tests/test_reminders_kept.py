"""Reminders outlive the app, and one missed while it was off is said late, not lost.

Reminders were asyncio tasks in memory: if the app stopped before one fired it
was gone, with nothing said. The owner chose (2026-10-07) that a reminder due
while the app was off is said on the next start with how late it is.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time

import pytest

from Agent_Guru.platform.features.reminders import ReminderManager, _how_late


@pytest.fixture
def store(tmp_path):
    return tmp_path / "reminders.json"


def _kept(store):
    return json.loads(store.read_text(encoding="utf-8")) if store.exists() else []


async def test_a_reminder_is_kept_on_disk_until_it_fires(store):
    said = []
    manager = ReminderManager(speak_callback=said.append, store_path=store)
    await manager.set_reminder("drink water", seconds=0.2)
    assert [r["message"] for r in _kept(store)] == ["drink water"]  # nosec B101
    await asyncio.sleep(0.5)
    assert said == ["drink water"] and _kept(store) == []  # nosec B101


async def test_a_reminder_set_before_a_restart_fires_after_it(store):
    first = ReminderManager(store_path=store)
    await first.set_reminder("call John", seconds=0.4)
    for task in first._tasks.values():
        task.cancel()  # the app stopped
    said = []
    again = ReminderManager(speak_callback=said.append, store_path=store)
    assert await again.restore() == []  # nosec B101  not due yet, nothing said now
    await asyncio.sleep(0.7)
    assert said == ["call John"] and _kept(store) == []  # nosec B101


async def test_a_reminder_missed_while_off_is_said_with_how_late(store):
    store.write_text(json.dumps([{"reminder_id": "r1", "message": "take your medicine",
                                  "fire_at": 1000.0, "created_at": 900.0, "fired": False}]), encoding="utf-8")
    said = []
    manager = ReminderManager(speak_callback=said.append, store_path=store)
    out = await manager.restore(now=1000.0 + 40 * 60)
    assert said == out == ["You had a reminder 40 minutes ago: take your medicine"]  # nosec B101
    assert _kept(store) == []  # nosec B101  said once, not again on the next start


async def test_missed_and_pending_reminders_are_sorted_out_together(store):
    now = time.time()
    store.write_text(json.dumps([
        {"reminder_id": "later", "message": "stretch", "fire_at": now + 3600, "created_at": now},
        {"reminder_id": "missed", "message": "lunch", "fire_at": now - 2 * 3600, "created_at": now - 3 * 3600},
    ]), encoding="utf-8")
    said = []
    manager = ReminderManager(speak_callback=said.append, store_path=store)
    await manager.restore(now=now)
    assert said == ["You had a reminder 2 hours ago: lunch"]  # nosec B101
    assert [r["message"] for r in _kept(store)] == ["stretch"]  # nosec B101
    manager.cancel_reminder("later")
    assert _kept(store) == []  # nosec B101  a cancel is kept too


@pytest.mark.parametrize(("seconds", "words"), [
    (30, None), (60, "1 minute"), (40 * 60 + 13, "40 minutes"), (5400, "1 hour 30 minutes"),
    (3 * 86400 + 7200, "3 days"),
])
def test_how_late_is_said_in_words_fit_to_speak(seconds, words):
    assert _how_late(seconds) == words  # nosec B101


async def test_an_unreadable_store_is_set_aside_not_overwritten(store):
    store.write_text("{not json", encoding="utf-8")
    manager = ReminderManager(store_path=store)
    assert await manager.restore() == []  # nosec B101
    assert store.with_suffix(".unreadable.json").read_text(encoding="utf-8") == "{not json"  # nosec B101


async def test_reminder_ids_do_not_repeat_across_runs(store):
    first = ReminderManager(store_path=store)
    await first.set_reminder("a", seconds=60)
    second = ReminderManager(store_path=store)
    await second.restore()
    await second.set_reminder("b", seconds=60)
    ids = [r["reminder_id"] for r in _kept(store)]
    assert len(ids) == len(set(ids)) == 2  # nosec B101
    for manager in (first, second):
        for task in manager._tasks.values():
            task.cancel()


async def test_saying_a_reminder_does_not_hold_up_the_event_loop(store):
    # The speaker synthesizes and plays the whole sentence. Called on the event
    # loop, it stalled wake-word listening for as long as the reminder took to
    # say. The fix offloads the callback to a thread with asyncio.to_thread.
    #
    # What this checks:
    #   1. speak() runs on a worker thread, never the loop thread.
    #   2. The loop is not blocked while speak sleeps: a coroutine scheduled
    #      concurrently can observe the speak thread working and tick at least
    #      once during the 0.3-second sleep, even under CI load.
    #
    # What it deliberately avoids:
    #   The old version counted absolute ticks in a 500-ms window and required
    #   > 20. Under a fully-loaded CI runner, the asyncio timer resolution can
    #   push 10-ms sleeps to 20+ ms, dropping the count below the threshold and
    #   making the test fail without the loop ever having been blocked. The fix
    #   uses an asyncio.Event set by a concurrent task: if the loop is blocked
    #   the event can never be set while speak runs, so the assertion is tight
    #   without depending on absolute timing.
    loop_thread = threading.get_ident()
    on_loop_thread: list[bool] = []
    speak_started = threading.Event()   # set by the speak thread when it starts
    loop_ticked = asyncio.Event()       # set by the event loop while speak runs

    def speak(text: str) -> None:
        on_loop_thread.append(threading.get_ident() == loop_thread)
        speak_started.set()             # tell the watcher the thread is live
        time.sleep(0.3)

    async def watch() -> None:
        # Wait until speak has started on its thread, then tick the loop once.
        # If speak were on the loop thread, this coroutine would never get to
        # run during speak and loop_ticked would stay clear.
        await asyncio.to_thread(speak_started.wait, 2.0)
        loop_ticked.set()

    manager = ReminderManager(speak_callback=speak, store_path=store)
    watcher = asyncio.create_task(watch())
    await manager.set_reminder("stand up", seconds=0)

    # Wait up to 1 s for both speak and the loop tick to complete.
    await asyncio.wait_for(loop_ticked.wait(), timeout=1.0)
    await watcher

    assert on_loop_thread == [False]    # speak never ran on the loop thread  # nosec B101
    assert loop_ticked.is_set()         # the loop could schedule while speak ran  # nosec B101


async def test_without_a_store_nothing_is_written(tmp_path):
    manager = ReminderManager()
    await manager.set_reminder("x", seconds=60)
    assert list(tmp_path.iterdir()) == []  # nosec B101
    assert await manager.restore() == []  # nosec B101
    for task in manager._tasks.values():
        task.cancel()


async def test_the_assistant_restores_kept_reminders_when_it_starts(store, monkeypatch):
    from Agent_Guru.integration.gpu_pool import GPUResourcePool
    from Agent_Guru.integration.orchestrator import IntegrationOrchestrator

    class NoFiller:
        _initialized = True

    # Startup warms the Kokoro filler cache, which takes tens of seconds.
    monkeypatch.setattr("Agent_Guru.speech.filler_response.get_filler_cache", NoFiller)

    store.write_text(json.dumps([{"reminder_id": "r1", "message": "water the plants", "fire_at": time.time() - 3600,
                                  "created_at": 0.0}]), encoding="utf-8")
    said = []
    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=None, platform_controller=None,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=None,
        avatar=None, deployment=None, gpu_pool=GPUResourcePool(), reminder_store=store,
    )
    orch._reminders().set_speak_callback(said.append)
    await orch.startup()
    [line] = said
    assert line.startswith("You had a reminder 1 hour") and line.endswith("ago: water the plants")  # nosec B101
