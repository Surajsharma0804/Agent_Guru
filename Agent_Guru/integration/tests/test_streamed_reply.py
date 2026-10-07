"""A spoken answer starts while the LLM is still writing it.

The pipeline used to wait for LLMRuntime.complete() to return the whole
answer before the TTS stage spoke any of it. With gemma4 on the development
laptop the pipeline's own request had its first sentence after 0.12 to
0.14 s and the whole answer after 1.9 to 4.6 s, and the user heard nothing
for all of that. These use the real PortAudio lock and play_and_wait, with
sounddevice replaced so nothing plays.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
import types

import numpy as np
import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent
from Agent_Guru.llm.models import StreamChunk

SENTENCES = [
    "The capital of France is Paris. ",
    "It sits on the river Seine in the north. ",
    "About two million people live in the city itself.",
]
ANSWER = "".join(SENTENCES)
SENTENCE_S = 0.3  # how long the fake model takes to write each sentence
SR = 16000


class _Allow:
    def evaluate(self, intent):
        return True


class _Speech:
    def __init__(self):
        self.synthesised: list[str] = []

    async def transcribe(self, audio):
        return type("R", (), {"text": "tell me about Paris", "language": "en", "language_probability": 0.99})()

    def synthesize_to_array(self, sentence, personality):
        self.synthesised.append(sentence)
        return np.zeros(int(0.05 * SR), np.float32), SR


class _Runtime:
    """complete() and stream() as LLMRuntime has them, writing at a fixed pace."""

    def __init__(self, chunks=None, fail_stream=False):
        self.chunks = chunks if chunks is not None else [StreamChunk(content=s) for s in SENTENCES] + [
            StreamChunk(content="", finish_reason="stop"),
        ]
        self.fail_stream = fail_stream
        self.complete_calls = 0
        self.stream_started_at: float | None = None
        self.stream_ended_at: float | None = None

    async def complete(self, request):
        # The same answer stream() writes, in one piece once it is all written.
        self.complete_calls += 1
        written = [c for c in self.chunks if c.content]
        await asyncio.sleep(SENTENCE_S * len(written))
        return types.SimpleNamespace(
            content="".join(c.content for c in written), finish_reason=self.chunks[-1].finish_reason,
        )

    async def stream(self, request):
        if self.fail_stream:
            msg = "ollama went away"
            raise ConnectionError(msg)
        self.stream_started_at = time.perf_counter()
        for chunk in self.chunks:
            if chunk.content:
                await asyncio.sleep(SENTENCE_S)
            yield chunk
        self.stream_ended_at = time.perf_counter()


@pytest.fixture
def plays(monkeypatch):
    """Real play_and_wait over a fake sounddevice that records when each clip starts."""
    log: list[float] = []
    current = threading.local()

    def play(samples, samplerate=None):
        current.duration = len(samples) / samplerate
        log.append(time.perf_counter())

    def wait():
        time.sleep(current.duration)

    monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(play=play, wait=wait))
    return log


def _orchestrator(monkeypatch, runtime):
    class Cache:
        _initialized = True

        async def play_filler_async(self, **kwargs):
            return None

    monkeypatch.setattr("Agent_Guru.speech.filler_response.get_filler_cache", Cache)
    speech = _Speech()
    orch = IntegrationOrchestrator(
        speech_engine=speech, vision_engine=None, llm_runtime=runtime,
        platform_controller=object(), agent_orchestrator=None, memory=None, reasoning=None,
        security=None, policy=_Allow(), avatar=None, deployment=None, gpu_pool=None,
    )

    async def no_web(transcript, intent):
        return ""

    orch._fetch_web_context = no_web
    return orch, speech


async def _turn(orch):
    start = time.perf_counter()
    result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=np.zeros(16000, np.float32).tobytes()))
    return result, start


async def test_the_answer_is_heard_before_it_is_written(plays, monkeypatch):
    runtime = _Runtime()
    orch, speech = _orchestrator(monkeypatch, runtime)
    result, _ = await _turn(orch)
    # Before: complete() wrote the whole answer (0.9 s here) and only then
    # did the first sentence play. Now it plays one sentence (0.3 s) in.
    assert runtime.stream_started_at is not None  # nosec B101
    assert plays  # nosec B101
    assert plays[0] < runtime.stream_ended_at  # nosec B101
    assert plays[0] - runtime.stream_started_at < 2 * SENTENCE_S  # nosec B101
    assert runtime.complete_calls == 0  # nosec B101  the answer was asked for once
    assert result.llm_response == ANSWER  # nosec B101
    assert result.tts_response.spoken == 3  # nosec B101
    assert result.error is None  # nosec B101
    assert speech.synthesised == [s.strip() for s in SENTENCES]  # nosec B101
    assert orch._chat_history[-1] == {"role": "assistant", "content": ANSWER}  # nosec B101


async def test_a_stream_that_fails_before_any_text_answers_the_usual_way(plays, monkeypatch):
    runtime = _Runtime(fail_stream=True)
    orch, speech = _orchestrator(monkeypatch, runtime)
    result, _ = await _turn(orch)
    assert runtime.complete_calls == 1  # nosec B101  complete(), with its retries, answered
    assert result.llm_response == ANSWER  # nosec B101
    assert speech.synthesised == [s.strip() for s in SENTENCES]  # nosec B101
    assert len(plays) == 3  # nosec B101


async def test_a_capped_answer_is_not_spoken_mid_sentence(plays, monkeypatch):
    runtime = _Runtime(chunks=[
        StreamChunk(content=SENTENCES[0]),
        StreamChunk(content="It sits on the river Seine in the"),
        StreamChunk(content="", finish_reason="length"),
    ])
    orch, speech = _orchestrator(monkeypatch, runtime)
    result, _ = await _turn(orch)
    assert speech.synthesised == [SENTENCES[0].strip()]  # nosec B101
    assert result.llm_response == SENTENCES[0].strip()  # nosec B101
    assert orch._chat_history[-1]["content"] == SENTENCES[0].strip()  # nosec B101


async def test_a_spoken_answer_records_tokens_timings_and_first_text(plays, monkeypatch, tmp_path):
    # A streamed answer used to leave no token counts, model timings or
    # time-to-first-text anywhere, though every question is answered this way.
    from Agent_Guru.integration.turn_trace import TurnTraceStore
    from Agent_Guru.llm.models import TokenUsage

    runtime = _Runtime(chunks=[StreamChunk(content=s) for s in SENTENCES] + [
        StreamChunk(content="", finish_reason="stop", usage=TokenUsage(120, 40, 160, 0.0),
                    timings={"prompt_s": 0.05, "decode_s": 0.8}),
    ])
    orch, _ = _orchestrator(monkeypatch, runtime)
    orch.trace_store = TurnTraceStore(tmp_path / "turns.db")
    result, _ = await _turn(orch)
    stats = result.llm_stats
    assert SENTENCE_S <= stats["first_text_s"] < 2 * SENTENCE_S  # nosec B101  the first sentence took 0.3 s to write
    assert (stats["prompt_tokens"], stats["output_tokens"]) == (120, 40)  # nosec B101
    assert stats["prompt_s"] == 0.05 and stats["tokens_per_s"] == pytest.approx(50.0)  # nosec B101
    [turn] = orch.trace_store.recent()
    answer = next(s for s in turn.stages if s.name == "answer_spoken")
    assert answer.detail == stats  # nosec B101


async def test_an_answer_without_model_counts_records_only_what_was_measured(plays, monkeypatch):
    orch, _ = _orchestrator(monkeypatch, _Runtime())
    result, _ = await _turn(orch)
    assert set(result.llm_stats) == {"first_text_s"}  # nosec B101  no invented zeros
