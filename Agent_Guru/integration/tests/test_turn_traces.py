"""Every voice turn leaves a trace: what was heard, what was done, how long each stage took.

Before, main.py logged a turn's PipelineResult and dropped it. No stage was
timed except wake-to-first-speech on two shortcut paths, and the per-turn
audit event went to an in-memory database, so "which stage was slow" or
"what did it say when that failed" had no stored answer.

These run whole turns through run_pipeline with a TurnTraceStore in a temporary folder.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import numpy as np
import pytest

from Agent_Guru.integration import orchestrator as orch_module
from Agent_Guru.integration.orchestrator import ActionStatus, IntegrationOrchestrator, WakeWordEvent
from Agent_Guru.integration.turn_trace import TurnTraceStore

OK = SimpleNamespace(success=True, message="ok", error=None)
FAILED = SimpleNamespace(success=False, message="", error="Access is denied")


class Controller:
    def __init__(self, returns):
        self.returns = returns

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda *a, **k: self.returns


class Policy:
    def __init__(self, allow):
        self.allow = allow

    def evaluate(self, intent):
        return self.allow


def _orchestrator(ctrl, allow=True, trace_store=None):
    return IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=None, platform_controller=ctrl,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=Policy(allow),
        avatar=None, deployment=None, gpu_pool=None, trace_store=trace_store,
    )


async def _turn(orch, said, stt_seconds=0.0):
    spoken = []

    async def stt(*a, **k):
        await asyncio.sleep(stt_seconds)
        return said, "en"

    async def tts(text, personality):
        spoken.append(text)

    async def silent(*a, **k):
        return None

    orch._stage_stt, orch._stage_tts, orch._play_filler = stt, tts, silent
    result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=np.zeros(16000, np.float32).tobytes()))
    return result, spoken[0] if spoken else None


@pytest.fixture
def store(tmp_path):
    return TurnTraceStore(tmp_path / "turns.db")


async def test_a_turn_is_recorded_with_what_was_heard_done_and_said(store):
    result, spoken = await _turn(_orchestrator(Controller(OK), trace_store=store), "minimize the window")
    [turn] = store.recent()
    assert turn.heard == "minimize the window" and turn.said == spoken == "Window minimized"  # nosec B101
    assert turn.personality == "guru" and turn.outcome == "success"  # nosec B101
    assert turn.action_status == "success" and turn.intent == result.intent  # nosec B101
    stages = [s.name for s in turn.stages]
    for stage in ("stt", "memory", "intent", "policy", "action", "tts"):
        assert stage in stages  # nosec B101
    assert stages.index("stt") < stages.index("intent") < stages.index("policy") < stages.index("action")  # nosec B101
    assert next(s for s in turn.stages if s.name == "action").detail == {"status": "success"}  # nosec B101


async def test_a_stage_is_recorded_as_long_as_it_took(store):
    await _turn(_orchestrator(Controller(OK), trace_store=store), "minimize the window", stt_seconds=0.2)
    [turn] = store.recent()
    stt = next(s for s in turn.stages if s.name == "stt")
    assert 0.2 <= stt.seconds < 1.0  # nosec B101
    assert turn.seconds >= 0.2  # nosec B101


async def test_a_failed_action_is_a_failure(store):
    await _turn(_orchestrator(Controller(FAILED), trace_store=store), "minimize the window")
    [turn] = store.recent()
    assert turn.outcome == "failure" and turn.action_status == "failed"  # nosec B101


async def test_a_refused_action_is_not_a_success_and_has_no_action_stage(store):
    await _turn(_orchestrator(Controller(OK), allow=False, trace_store=store), "minimize the window")
    [turn] = store.recent()
    assert turn.outcome is None and turn.action_status == "denied"  # nosec B101
    assert "action" not in [s.name for s in turn.stages]  # nosec B101
    assert next(s for s in turn.stages if s.name == "policy").detail == {"allowed": False}  # nosec B101


async def test_an_unconfirmed_action_is_not_a_success(store):
    await _turn(_orchestrator(Controller(None), trace_store=store), "next track")
    [turn] = store.recent()
    assert turn.outcome is None and turn.action_status == "unverified"  # nosec B101


async def test_without_a_store_nothing_is_recorded_and_the_turn_is_unchanged():
    # The default. Tests and embedders never write into the user's own turns.db.
    orch = _orchestrator(Controller(OK))
    assert orch.trace_store is None  # nosec B101
    result, spoken = await _turn(orch, "minimize the window")
    assert spoken == "Window minimized" and result.action_status is ActionStatus.SUCCESS  # nosec B101


async def test_a_store_that_fails_costs_the_record_not_the_turn():
    class Broken:
        def record(self, turn):
            raise OSError("disk full")

    result, spoken = await _turn(_orchestrator(Controller(OK), trace_store=Broken()), "minimize the window")
    assert spoken == "Window minimized" and result.action_status is ActionStatus.SUCCESS and result.error is None  # nosec B101


async def test_a_store_that_hangs_holds_the_turn_only_until_the_write_timeout(monkeypatch):
    class Slow:
        def record(self, turn):
            time.sleep(1.5)

    monkeypatch.setattr(orch_module, "TRACE_WRITE_TIMEOUT_S", 0.2)
    started = time.perf_counter()
    result, spoken = await _turn(_orchestrator(Controller(OK), trace_store=Slow()), "minimize the window")
    assert time.perf_counter() - started < 1.0  # nosec B101  not the 1.5 s the save took
    assert spoken == "Window minimized"  # nosec B101


async def test_nothing_heard_is_still_recorded(store):
    await _turn(_orchestrator(Controller(OK), trace_store=store), "")
    [turn] = store.recent()
    assert turn.heard == "" and [s.name for s in turn.stages] == ["stt"]  # nosec B101


# ---- rating the last answer by voice ----

async def test_saying_that_was_wrong_marks_the_last_answer(store):
    orch = _orchestrator(Controller(OK), trace_store=store)
    await _turn(orch, "minimize the window")
    [answered] = store.recent()
    result, spoken = await _turn(orch, "that was wrong")
    assert spoken == "Sorry about that. I've marked that answer as wrong."  # nosec B101
    assert result.action_status is ActionStatus.SUCCESS and result.intent == "feedback:rating"  # nosec B101
    assert store.get(answered.turn_id).rating == 0.0  # nosec B101


async def test_hinglish_praise_marks_it_right(store):
    orch = _orchestrator(Controller(OK), trace_store=store)
    await _turn(orch, "minimize the window")
    [answered] = store.recent()
    _, spoken = await _turn(orch, "bilkul sahi")
    assert spoken == "Thanks, I've marked that answer as right." and store.get(answered.turn_id).rating == 1.0  # nosec B101


async def test_a_rating_never_becomes_the_answer_the_next_rating_marks(store):
    orch = _orchestrator(Controller(OK), trace_store=store)
    await _turn(orch, "minimize the window")
    [answered] = store.recent()
    await _turn(orch, "that was right")
    await _turn(orch, "that was wrong")
    assert store.get(answered.turn_id).rating == 0.0  # nosec B101
    ratings = [t.rating for t in store.recent() if t.intent == "feedback:rating"]
    assert ratings == [None, None]  # nosec B101  the rating turns themselves are not rated


async def test_with_nothing_to_mark_it_says_so(store):
    result, spoken = await _turn(_orchestrator(Controller(OK), trace_store=store), "that was wrong")
    assert spoken == "There's no earlier answer I can mark." and result.action_status is ActionStatus.FAILED  # nosec B101
    result, spoken = await _turn(_orchestrator(Controller(OK)), "that was wrong")
    assert spoken == "There's no earlier answer I can mark."  # nosec B101  no store, no record to mark


async def test_a_correction_is_not_taken_for_a_rating(store):
    orch = _orchestrator(Controller(OK), trace_store=store)
    await _turn(orch, "minimize the window")
    result, _ = await _turn(orch, "that's wrong, the capital is Delhi")
    assert result.intent != "feedback:rating"  # nosec B101
    assert all(t.rating is None for t in store.recent())  # nosec B101


async def test_an_unverified_speaker_cannot_rate(store):
    orch = _orchestrator(Controller(OK), trace_store=store)
    await _turn(orch, "minimize the window")
    orch._verify_speaker = lambda *a, **k: "restricted"
    result, _ = await _turn(orch, "that was wrong")
    assert result.intent != "feedback:rating"  # nosec B101
    assert all(t.rating is None for t in store.recent())  # nosec B101
