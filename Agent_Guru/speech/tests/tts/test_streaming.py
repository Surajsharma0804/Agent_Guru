"""Streamed TTS: first audio after one sentence, the rest synthesised behind it.

The stage used to synthesise a whole reply before playing any of it. Kokoro on
the development laptop's CPU took 17.3 s for a 211-character reply and 27.9 s
for a 348-character one, so the user waited in silence and long replies
overran the 30 s stage budget.
"""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from Agent_Guru.speech.tts.streaming import split_sentences, speak_streaming

RATE = 1000


class Recorder:
    """Fake synthesize/play pair that records when each call starts and ends."""

    def __init__(self, synth_s: float = 0.05, play_s: float = 0.1, fail: dict[int, int] | None = None,
                 hang: set[int] | None = None) -> None:
        self.synth_s, self.play_s = synth_s, play_s
        self.fail = dict(fail or {})  # sentence index -> failures left
        self.hang = hang or set()
        self.events: list[tuple[str, int, float, float]] = []
        self.played: list[int] = []
        self.index: dict[str, int] = {}
        self.lock = threading.Lock()

    def synthesize(self, sentence: str) -> tuple[np.ndarray, int]:
        i = self.index[sentence]
        start = time.perf_counter()
        if i in self.hang:
            time.sleep(1.0)
        time.sleep(self.synth_s)
        with self.lock:
            if self.fail.get(i, 0) > 0:
                self.fail[i] -= 1
                raise RuntimeError(f"kokoro failed on sentence {i + 1}")
            self.events.append(("synth", i, start, time.perf_counter()))
        return np.ones(int(RATE * self.play_s), dtype=np.float32), RATE

    def play(self, samples: np.ndarray, rate: int) -> None:
        start = time.perf_counter()
        time.sleep(len(samples) / rate)
        i = len(self.played)
        self.played.append(i)
        self.events.append(("play", i, start, time.perf_counter()))


def _reply(n: int) -> str:
    return " ".join(f"This is sentence number {i + 1} of the reply." for i in range(n))


def _recorder_for(text: str, **kw) -> Recorder:
    rec = Recorder(**kw)
    rec.index = {s: i for i, s in enumerate(split_sentences(text))}
    return rec


class TestSplit:
    def test_splits_at_sentence_ends(self) -> None:
        text = "The capital of France is Paris. It is known for the Eiffel Tower! Have you been?"
        assert split_sentences(text) == [
            "The capital of France is Paris.",
            "It is known for the Eiffel Tower! Have you been?",
        ]

    def test_short_fragments_join_the_next_sentence(self) -> None:
        assert split_sentences("Hey! Oh, the capital of France, that's easy, it's Paris.") == [
            "Hey! Oh, the capital of France, that's easy, it's Paris.",
        ]

    def test_newlines_split_and_blank_text_is_empty(self) -> None:
        assert split_sentences("First line of the reply here\nSecond line of the reply here") == [
            "First line of the reply here", "Second line of the reply here",
        ]
        assert split_sentences("   ") == []


class TestStreaming:
    async def test_all_sentences_play_in_order(self) -> None:
        text = _reply(4)
        rec = _recorder_for(text)
        result = await speak_streaming(text, rec.synthesize, rec.play, synth_timeout_s=5)
        assert result.complete and result.spoken == 4
        assert rec.played == [0, 1, 2, 3]

    async def test_next_sentence_is_synthesised_while_one_plays(self) -> None:
        text = _reply(3)
        rec = _recorder_for(text, synth_s=0.05, play_s=0.3)
        await speak_streaming(text, rec.synthesize, rec.play, synth_timeout_s=5)
        play0 = next(e for e in rec.events if e[:2] == ("play", 0))
        synth1 = next(e for e in rec.events if e[:2] == ("synth", 1))
        assert synth1[2] < play0[3], "sentence 2 was not synthesised during sentence 1"

    async def test_first_audio_does_not_grow_with_reply_length(self) -> None:
        firsts = []
        for n in (1, 6):
            text = _reply(n)
            rec = _recorder_for(text, synth_s=0.2, play_s=0.05)
            result = await speak_streaming(text, rec.synthesize, rec.play, synth_timeout_s=5)
            firsts.append(result.first_audio_s)
        assert firsts[1] < firsts[0] + 0.15, firsts

    async def test_a_later_sentence_that_fails_once_is_retried(self) -> None:
        text = _reply(3)
        rec = _recorder_for(text, fail={1: 1})
        result = await speak_streaming(text, rec.synthesize, rec.play, synth_timeout_s=5)
        assert result.complete and rec.played == [0, 1, 2]

    async def test_a_later_sentence_that_keeps_failing_stops_speech_there(self) -> None:
        text = _reply(4)
        rec = _recorder_for(text, fail={2: 2})
        result = await speak_streaming(text, rec.synthesize, rec.play, synth_timeout_s=5)
        assert rec.played == [0, 1], "must not skip ahead past a failed sentence"
        assert not result.complete and result.spoken == 2
        assert "spoke 2 of 4" in result.error and "sentence 3" in result.error

    async def test_a_stuck_sentence_is_bounded_by_the_silence_budget(self) -> None:
        text = _reply(3)
        rec = _recorder_for(text, hang={1})
        start = time.perf_counter()
        result = await speak_streaming(text, rec.synthesize, rec.play, synth_timeout_s=0.3)
        assert rec.played == [0]
        assert "TimeoutError" in result.error
        assert time.perf_counter() - start < 2.0

    async def test_first_sentence_failing_raises_for_the_caller_to_fall_back(self) -> None:
        text = _reply(2)
        rec = _recorder_for(text, fail={0: 2})
        with pytest.raises(RuntimeError, match="sentence 1"):
            await speak_streaming(text, rec.synthesize, rec.play, synth_timeout_s=5)
        assert rec.played == []
