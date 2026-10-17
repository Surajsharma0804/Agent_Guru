"""Features whose intent is only a label are decided on the owner's words.

"Good morning" reached the action stage as "system_control:briefing" and
"what's my battery level" as "system_control:system_status": no feature
check matches those strings, so both fell through to platform control
and the owner heard "Sorry, I couldn't do that."
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent


async def _reply(transcript, tmp_path):
    class Speech:
        async def transcribe(self, audio):
            return SimpleNamespace(text=transcript, language="en", language_probability=0.99)

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
        await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=np.zeros(16000, np.float32).tobytes()))
    finally:
        orch.close_scheduler()
    return spoken[0] if spoken else ""


async def test_system_status_is_answered_from_the_question(tmp_path):
    said = await _reply("how much ram am I using", tmp_path)
    assert "couldn't" not in said and ("RAM" in said or "memory" in said.lower()), said  # nosec B101


async def test_good_morning_gets_the_briefing(tmp_path, monkeypatch):
    from Agent_Guru.platform.features import briefing

    async def nothing(*a, **k):
        return None

    monkeypatch.setattr(briefing, "_get_weather", nothing)

    async def no_news(*a, **k):
        return []

    monkeypatch.setattr(briefing, "_get_news_headlines", no_news)
    said = await _reply("good morning", tmp_path)
    assert "Today is" in said and "Have a great day." in said, said  # nosec B101
