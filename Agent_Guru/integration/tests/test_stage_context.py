"""What a pipeline stage records in a context variable reaches the rest of the turn, on every Python.

The STT and answer stages ran under asyncio.wait_for. On Python 3.11 wait_for runs its coroutine as a
separate task with a copy of the context, so values a stage set were lost when it returned: the STT
confidence the quiet rule reads, and the model the router chose, which the turn record and the
router's learning read. From Python 3.12 wait_for runs in the caller's task, so these pass there with
either code; they are the regression tests for 3.11, where CI runs them.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

import Agent_Guru.integration.orchestrator as orchestrator_module
from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent
from Agent_Guru.speech.models import TranscriptionResult


class Heard:
    def transcribe(self, audio, sample_rate=16000):
        return TranscriptionResult(text="Hey Guru, what is the capital of France?", language="en", confidence=-0.2)


@pytest.fixture
def orch(tmp_path):
    o = IntegrationOrchestrator(
        speech_engine=Heard(), vision_engine=None, llm_runtime=None, platform_controller=None,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=None, avatar=None,
        deployment=None, gpu_pool=None, reminder_store=tmp_path / "r.json",
    )

    async def silent(*a, **k):
        return None

    o._fetch_web_context = silent
    o._play_filler = silent
    o._stage_tts = silent
    o._streamable_tts_fn = lambda: None  # no streamed reply, so the answer goes through _stage_llm
    yield o
    o.close_scheduler()


async def test_the_model_the_answer_stage_routed_to_reaches_the_turn_record(orch):
    async def answered_by_a_routed_model(*a, **k):
        # What _build_llm_request does when the turn router picks another model.
        orchestrator_module._ROUTED_MODEL.set("routed-model:7b")
        return "Paris."

    orch._stage_llm = answered_by_a_routed_model
    audio = np.full(16000, 0.05, dtype=np.float32).tobytes()
    result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=audio))
    assert result.llm_response == "Paris."  # nosec B101
    assert result.routed_model == "routed-model:7b"  # nosec B101


async def test_the_stt_confidence_reaches_the_quiet_rule(orch):
    seen = []
    real = orch._unsure

    def unsure(transcript):
        seen.append(orchestrator_module._STT_CONFIDENCE.get())
        return real(transcript)

    orch._unsure = unsure

    async def answer(*a, **k):
        return "Paris."

    orch._stage_llm = answer
    audio = np.full(16000, 0.05, dtype=np.float32).tobytes()
    await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=audio, quiet_if_unsure=True))
    assert seen == [-0.2]  # nosec B101
