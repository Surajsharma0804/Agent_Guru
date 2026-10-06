"""Streamed TTS: first audio after one sentence, the rest synthesised behind it.

The stage used to synthesise a whole reply before playing any of it. Kokoro on
the development laptop's CPU took 17.3 s for a 211-character reply and 27.9 s
for a 348-character one, so the user waited in silence and long replies
overran the 30 s stage budget.
"""

from __future__ import annotations

import asyncio
import threading
import time

import numpy as np
import pytest

from Agent_Guru.speech.tts.streaming import split_sentences, speak_streaming, stream_sentences

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


async def _chunks(text: str, *, size: int = 7, delay_s: float = 0.0, then: BaseException | None = None,
                  hang_after: int | None = None):
    """The reply as an LLM streams it: a few characters at a time."""
    for n, at in enumerate(range(0, len(text), size)):
        if hang_after is not None and n == hang_after:
            await asyncio.sleep(3600)
        if delay_s:
            await asyncio.sleep(delay_s)
        yield text[at:at + size]
    if then is not None:
        raise then


async def _collect(source, **kw) -> list[str]:
    return [s async for s in stream_sentences(source, **kw)]


class TestGeneratedReply:
    """The reply spoken while the LLM is still writing it.

    It used to be spoken only once the model had finished: for the voice
    pipeline's own request the first sentence existed after 0.12 to 0.14 s
    and the whole answer after 1.9 to 4.6 s, all of it silence.
    """

    async def test_split_matches_the_whole_text_split(self) -> None:
        text = _reply(4)
        assert await _collect(_chunks(text)) == split_sentences(text)

    async def test_a_sentence_is_yielded_before_the_reply_ends(self) -> None:
        released = asyncio.Event()

        async def source():
            yield "The capital of France is Paris. "
            await released.wait()
            yield "It is known for the Eiffel Tower."

        sentences = stream_sentences(source())
        first = await asyncio.wait_for(anext(sentences), timeout=1.0)
        assert first == "The capital of France is Paris."
        released.set()
        assert [s async for s in sentences] == ["It is known for the Eiffel Tower."]

    async def test_a_capped_reply_drops_its_unfinished_sentence(self) -> None:
        text = "The capital of France is Paris. It is known for the Eiffel"
        assert await _collect(_chunks(text), capped=lambda: True) == ["The capital of France is Paris."]
        assert await _collect(_chunks(text)) == ["The capital of France is Paris.", "It is known for the Eiffel"]

    async def test_a_capped_reply_with_no_sentence_end_is_kept(self) -> None:
        text = "Paris is the capital and largest city of"
        assert await _collect(_chunks(text), capped=lambda: True) == [text]

    async def test_first_audio_comes_before_the_reply_is_written(self) -> None:
        text = _reply(4)
        rec = _recorder_for(text, synth_s=0.02, play_s=0.05)
        start = time.perf_counter()
        result = await speak_streaming(
            _chunks(text, delay_s=0.05), rec.synthesize, rec.play, synth_timeout_s=5, text_timeout_s=5,
        )
        written_s = 0.05 * -(-len(text) // 7)
        assert result.complete and rec.played == [0, 1, 2, 3]
        assert result.first_audio_s < written_s / 2, (result.first_audio_s, written_s)
        assert time.perf_counter() - start >= written_s

    async def test_a_stalled_reply_ends_after_what_was_spoken(self) -> None:
        text = _reply(3)
        rec = _recorder_for(text)
        start = time.perf_counter()
        result = await speak_streaming(
            _chunks(text, size=len(text) // 3 + 1, hang_after=1), rec.synthesize, rec.play,
            synth_timeout_s=5, text_timeout_s=0.3,
        )
        assert rec.played == [0]
        assert "stopped arriving after 1" in result.error
        assert time.perf_counter() - start < 2.0

    async def test_a_reply_that_fails_before_its_first_sentence_raises(self) -> None:
        rec = Recorder()
        with pytest.raises(RuntimeError, match="before its first sentence"):
            await speak_streaming(
                _chunks("The capital", then=ConnectionError("ollama went away")),
                rec.synthesize, rec.play, synth_timeout_s=5, text_timeout_s=5,
            )
        assert rec.played == []

    async def test_a_reply_that_fails_later_reports_how_far_it_got(self) -> None:
        text = _reply(2) + " "
        rec = _recorder_for(text)
        result = await speak_streaming(
            _chunks(text, then=ConnectionError("ollama went away")),
            rec.synthesize, rec.play, synth_timeout_s=5, text_timeout_s=5,
        )
        assert rec.played == [0, 1]
        assert "ollama went away" in result.error

    async def test_cancelling_the_reply_stops_the_generation(self) -> None:
        # At shutdown the turn is cancelled; the model must not go on
        # writing an answer nobody will hear.
        closed = asyncio.Event()

        async def source():
            try:
                yield "The capital of France is Paris. "
                await asyncio.sleep(3600)
                yield "It is known for the Eiffel Tower."
            finally:
                closed.set()

        rec = Recorder()
        rec.index = {"The capital of France is Paris.": 0}
        task = asyncio.ensure_future(
            speak_streaming(source(), rec.synthesize, rec.play, synth_timeout_s=5, text_timeout_s=60),
        )
        while not rec.played:
            await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(closed.wait(), timeout=1.0)
