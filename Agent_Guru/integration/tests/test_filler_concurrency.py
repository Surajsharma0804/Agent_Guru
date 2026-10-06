"""The filler clip plays while the turn is worked on, and the reply still follows it.

run_pipeline awaited the filler before STT, so every turn waited for the
whole clip (0.58 to 0.84 s measured with the real cache) before
transcription started, although the command had already been recorded.
Playback goes through the process-wide PortAudio lock, which is what keeps
the reply from starting before the filler ends; these use that real lock,
with sounddevice replaced so nothing plays.
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
from Agent_Guru.speech.audio.portaudio_lock import play_and_wait

FILLER_S = 0.5
STT_S = 0.3
SR = 16000


class _Allow:
    def evaluate(self, intent):
        return True


class _Speech:
    def __init__(self, events, transcript="what is the capital of France"):
        self.events, self.transcript = events, transcript

    async def transcribe(self, audio):
        self.events.append(("stt_start", time.perf_counter()))
        await asyncio.sleep(STT_S)
        return type("R", (), {"text": self.transcript, "language": "en", "language_probability": 0.99})()


class _LLM:
    async def infer(self, *a, **k):
        return "Paris."

    generate = infer


@pytest.fixture
def events(monkeypatch):
    """Real play_and_wait over a fake sounddevice that records when each clip plays."""
    log: list[tuple[str, float]] = []
    current = threading.local()

    def play(samples, samplerate=None):
        current.duration = len(samples) / samplerate
        log.append((f"play_start:{len(samples)}", time.perf_counter()))

    def wait():
        time.sleep(current.duration)
        log.append(("play_end", time.perf_counter()))

    monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(play=play, wait=wait))
    return log


def _filler_cache(initialized=True):
    filler = np.zeros(int(FILLER_S * SR), np.float32)

    class Cache:
        _initialized = initialized
        initialized_calls = 0

        def initialize(self):
            Cache.initialized_calls += 1

        async def play_filler_async(self, **kwargs):
            await asyncio.to_thread(play_and_wait, filler, SR)

    return Cache()


def _orchestrator(events, monkeypatch, cache, transcript="what is the capital of France"):
    monkeypatch.setattr("Agent_Guru.speech.filler_response.get_filler_cache", lambda: cache)
    orch = IntegrationOrchestrator(
        speech_engine=_Speech(events, transcript), vision_engine=None, llm_runtime=_LLM(),
        platform_controller=object(), agent_orchestrator=None, memory=None, reasoning=None,
        security=None, policy=_Allow(), avatar=None, deployment=None, gpu_pool=None,
    )
    reply = np.zeros(int(0.1 * SR), np.float32)

    async def tts(text, personality):
        # A quick reply: it is ready long before the filler ends.
        await asyncio.to_thread(play_and_wait, reply, SR)
        return text

    orch._stage_tts = tts
    return orch


async def _turn(orch):
    start = time.perf_counter()
    result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=np.zeros(16000, np.float32).tobytes()))
    return result, start, time.perf_counter()


def _plays(events):
    starts = [t for name, t in events if name.startswith("play_start")]
    ends = [t for name, t in events if name == "play_end"]
    return starts, ends


async def test_transcription_starts_while_the_filler_plays(events, monkeypatch):
    orch = _orchestrator(events, monkeypatch, _filler_cache())
    await _turn(orch)
    stt_start = next(t for name, t in events if name == "stt_start")
    starts, ends = _plays(events)
    assert stt_start < ends[0]  # nosec B101  was after the filler ended


async def test_the_turn_is_not_filler_plus_work(events, monkeypatch):
    orch = _orchestrator(events, monkeypatch, _filler_cache())
    _, start, end = await _turn(orch)
    # Before: filler (0.5 s) + STT (0.3 s) + reply (0.1 s) back to back, 0.9 s.
    assert end - start < FILLER_S + STT_S  # nosec B101


async def test_the_reply_never_plays_over_the_filler(events, monkeypatch):
    orch = _orchestrator(events, monkeypatch, _filler_cache())
    result, _, end = await _turn(orch)
    starts, ends = _plays(events)
    assert len(starts) == 2 and starts[1] >= ends[0]  # nosec B101  reply after the filler
    assert result.tts_response == "Paris."  # nosec B101


async def test_the_filler_has_finished_when_the_turn_returns(events, monkeypatch):
    # Also when nothing was said and the turn ends straight after STT.
    orch = _orchestrator(events, monkeypatch, _filler_cache(), transcript="")
    _, _, end = await _turn(orch)
    _, ends = _plays(events)
    assert ends and ends[0] <= end  # nosec B101


async def test_cold_cache_skips_the_filler_rather_than_playing_it_late(events, monkeypatch):
    cache = _filler_cache(initialized=False)
    orch = _orchestrator(events, monkeypatch, cache)
    await _turn(orch)
    await orch._filler_warmup
    starts, _ = _plays(events)
    assert len(starts) == 1  # nosec B101  only the reply played
    assert type(cache).initialized_calls == 1  # nosec B101  built for the next turn
