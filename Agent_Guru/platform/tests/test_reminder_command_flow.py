"""A spoken timer or reminder request schedules something, through the live pipeline.

The recognizer gave reminder intents no parameter, so the action stage
parsed the literal "system_control:reminder::", found no duration, and
"set a timer for 1 minute" was answered "Done." with nothing scheduled.
These run the real IntegrationOrchestrator.run_pipeline with the
microphone, LLM and speaker replaced by fakes; nothing is played.
"""

from __future__ import annotations

import asyncio
import time

import numpy as np
import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent


class FakeSpeech:
    def __init__(self, transcript):
        self.transcript = transcript

    async def transcribe(self, audio):
        return type("R", (), {"text": self.transcript, "language": "en", "language_probability": 0.99})()


class FakeLLM:
    async def infer(self, *args, **kwargs):
        return "unused"

    generate = infer


class AllowPolicy:
    def evaluate(self, intent):
        return True


async def _speak(transcript):
    orch = IntegrationOrchestrator(
        speech_engine=FakeSpeech(transcript), vision_engine=None, llm_runtime=FakeLLM(),
        platform_controller=object(), agent_orchestrator=None, memory=None, reasoning=None,
        security=None, policy=AllowPolicy(), avatar=None, deployment=None, gpu_pool=None,
    )
    spoken = []

    async def capture_tts(text, personality):
        spoken.append(text)

    async def no_filler(*args, **kwargs):
        return None

    orch._stage_tts = capture_tts
    orch._play_filler = no_filler
    await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=np.zeros(16000, np.float32).tobytes()))
    pending = orch._reminder_mgr.list_reminders() if orch._reminder_mgr else []
    for r in pending:
        r.delay = r.fire_at - time.time()
        orch._reminder_mgr.cancel_reminder(r.reminder_id)
    return (spoken[0] if spoken else None), pending


@pytest.mark.parametrize(("transcript", "reply", "message"), [
    ("set a timer for 1 minute", "I'll remind you in 1 minute.", "Your 1-minute timer is done."),
    ("set a timer for 5 minutes", "I'll remind you in 5 minutes.", "Your 5-minute timer is done."),
    ("remind me in 2 minutes to call mom", "I'll remind you in 2 minutes.", "call mom"),
])
async def test_timer_request_schedules_a_reminder(transcript, reply, message):
    spoken, pending = await _speak(transcript)
    assert spoken == reply  # nosec B101  was "Done."
    assert [r.message for r in pending] == [message]  # nosec B101


@pytest.mark.parametrize(("transcript", "reply", "seconds"), [
    # Hours and compound durations were not understood: "1 hour" was not
    # scheduled at all and "1 minute 30 seconds" was scheduled for 1 minute.
    ("set a timer for 5 seconds", "I'll remind you in 5 seconds.", 5),
    ("set a timer for 90 seconds", "I'll remind you in 1 minute 30 seconds.", 90),
    ("set a timer for 1 hour", "I'll remind you in 1 hour.", 3600),
    ("set a timer for 2 hours", "I'll remind you in 2 hours.", 7200),
    ("set a timer for 1 hour 30 minutes", "I'll remind you in 1 hour 30 minutes.", 5400),
    ("set a timer for 1 minute 30 seconds", "I'll remind you in 1 minute 30 seconds.", 90),
    ("remind me to stretch in half an hour", "I'll remind you in 30 minutes.", 1800),
])
async def test_scheduler_gets_the_exact_delay(transcript, reply, seconds):
    spoken, pending = await _speak(transcript)
    assert spoken == reply  # nosec B101
    assert len(pending) == 1 and abs(pending[0].delay - seconds) < 2  # nosec B101


async def test_short_timer_fires_on_time():
    from Agent_Guru.platform.features.reminders import ReminderManager, parse_reminder_from_transcript

    fired = []
    manager = ReminderManager()
    manager.set_speak_callback(lambda text: fired.append((time.perf_counter(), text)))
    params = parse_reminder_from_transcript("set a timer for 2 seconds")
    started = time.perf_counter()
    await manager.set_reminder(params["message"], seconds=params["seconds"])
    await asyncio.sleep(3)
    assert [text for _, text in fired] == ["Your 2-second timer is done."]  # nosec B101
    assert 1.9 <= fired[0][0] - started <= 2.9  # nosec B101
