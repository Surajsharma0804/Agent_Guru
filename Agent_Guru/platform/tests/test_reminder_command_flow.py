"""A spoken timer or reminder request schedules something, through the live pipeline.

The recognizer gave reminder intents no parameter, so the action stage
parsed the literal "system_control:reminder::", found no duration, and
"set a timer for 1 minute" was answered "Done." with nothing scheduled.
These run the real IntegrationOrchestrator.run_pipeline with the
microphone, LLM and speaker replaced by fakes; nothing is played.
"""

from __future__ import annotations

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
