"""The briefing speaks the local time, today's reminders, and the owner's calendar and tasks where connected."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from Agent_Guru.platform.features import briefing

IST = timezone(timedelta(hours=5, minutes=30))
EVENING = datetime(2026, 10, 17, 20, 13, tzinfo=IST)
MORNING = datetime(2026, 10, 17, 8, 5, tzinfo=IST)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    async def none(*a, **k):
        return []

    async def no_weather(*a, **k):
        return None

    monkeypatch.setattr(briefing, "_get_news_headlines", none)
    monkeypatch.setattr(briefing, "_get_weather", no_weather)


class Accounts:
    def __init__(self, calendar=None, tasks=None, slow=False):
        self.answers = {"calendar_events": calendar, "tasks_list": tasks}
        self.slow = slow

    def tool_list(self):
        return [{"name": n} for n, v in self.answers.items() if v is not None]

    async def call(self, name, arguments):
        if self.slow:
            await asyncio.sleep(60)
        return self.answers[name], False


def _say(**kw):
    return asyncio.run(briefing.get_morning_briefing(location="Delhi", **kw))


def test_the_local_time_and_a_fitting_greeting_are_said():
    said = _say(now=EVENING)
    assert said.startswith("Good evening. Today is Saturday, October 17. The time is 8:13 PM.")  # nosec B101
    assert _say(now=MORNING).startswith("Good morning.")  # nosec B101


def test_by_default_it_uses_the_local_clock_not_utc():
    """It used datetime.now(tz=UTC): in India it said 02:43 PM at 08:13 PM."""
    local = datetime.now().astimezone()
    said = asyncio.run(briefing.get_morning_briefing(location="Delhi"))
    spoken = {(local + timedelta(minutes=m)).strftime("%I:%M %p").lstrip("0") for m in (-1, 0, 1)}
    assert any(f"The time is {s}." in said for s in spoken), said  # nosec B101


def test_only_todays_reminders_are_said_in_order():
    def reminder(message, at, kind="say"):
        return SimpleNamespace(message=message, fire_at=at.timestamp(), kind=kind, fired=False)

    said = _say(now=MORNING, reminders=[
        reminder("call mom", MORNING.replace(hour=18, minute=0)), reminder("pay rent", MORNING.replace(hour=10, minute=30)),
        reminder("dentist", MORNING + timedelta(days=1)), reminder("check the weather", MORNING.replace(hour=9), "check"),
        reminder("yesterday's", MORNING - timedelta(hours=1)),
    ])
    assert "Reminders today: pay rent at 10:30 AM and call mom at 6 PM." in said  # nosec B101
    assert "dentist" not in said and "weather" not in said and "yesterday" not in said  # nosec B101


def test_todays_calendar_and_tasks_are_read_from_the_accounts():
    calendar = ("2026-10-17T10:00:00+05:30 | Standup | Zoom\n2026-10-17T07:30:00Z | Lunch with Rahul | \n"
                "2026-10-17 | Diwali shopping | \n2026-10-18T09:00:00+05:30 | Tomorrow's meeting | ")
    said = _say(now=MORNING, connectors=Accounts(calendar=calendar, tasks="Send invoice (due 2026-10-17)\nBuy milk"))
    assert "You have 3 events today: Standup at 10 AM, Lunch with Rahul at 1 PM and Diwali shopping all day." in said  # nosec B101
    assert "Tomorrow" not in said  # nosec B101
    assert "You have 2 open tasks: Send invoice (due 2026-10-17) and Buy milk." in said  # nosec B101


def test_an_account_that_is_not_connected_is_left_out():
    said = _say(now=MORNING, connectors=Accounts())
    assert "calendar" not in said and "task" not in said  # nosec B101


def test_a_slow_account_is_left_out_not_waited_for(monkeypatch):
    monkeypatch.setattr(briefing, "_SOURCE_TIMEOUT_S", 0.2)
    started = datetime.now()
    said = _say(now=MORNING, connectors=Accounts(calendar="x", slow=True))
    assert (datetime.now() - started).total_seconds() < 5 and "Have a great day." in said  # nosec B101


async def test_a_spoken_good_morning_includes_todays_reminder(tmp_path):
    """Through the real pipeline: the briefing promised reminders and said none."""
    import time

    import numpy as np

    from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent

    if (datetime.now() + timedelta(minutes=31)).date() != datetime.now().date():
        pytest.skip("too close to midnight for a reminder later today")

    class Speech:
        async def transcribe(self, audio):
            return SimpleNamespace(text="good morning", language="en", language_probability=0.99)

    class Allow:
        def evaluate(self, intent):
            return True

    orch = IntegrationOrchestrator(
        speech_engine=Speech(), vision_engine=None, llm_runtime=None, platform_controller=object(),
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=Allow(), avatar=None,
        deployment=None, gpu_pool=None, reminder_store=tmp_path / "reminders.json",
    )
    spoken = []

    async def capture(text, personality):
        spoken.append(text)

    async def no_filler(*args, **kwargs):
        return None

    orch._stage_tts = capture
    orch._play_filler = no_filler
    try:
        await orch._reminders().set_reminder("call the bank", minutes=30)
        await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=np.zeros(16000, np.float32).tobytes()))
        assert spoken and "Reminders today: call the bank at" in spoken[0], spoken  # nosec B101
    finally:
        for r in orch._reminders().list_reminders():
            orch._reminders().cancel_reminder(r.reminder_id)
        orch.close_scheduler()
        assert time.time()  # nosec B101
