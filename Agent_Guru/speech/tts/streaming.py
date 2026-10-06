"""Speak a reply sentence by sentence, synthesising the next while one plays.

The TTS stage used to synthesise the whole reply and only then play it.
Kokoro on the development laptop's CPU is at or slower than real time: in
Windows' "Best power efficiency" mode a 211-character reply took 17.3 s to
synthesise for 12.6 s of audio, and a 348-character one 27.9 s for 22.2 s.
The user heard nothing for the whole synthesis, and replies over about 200
characters overran the stage's 30 s budget and were logged as no audio.

Here the first sentence is synthesised and starts playing while the rest are
synthesised behind it, so the silence before the first word is one sentence's
synthesis whatever the reply's length, and each later sentence is normally
ready before the one in front of it finishes.

Every sentence plays through the caller's play function, which in production
is portaudio_lock.play_and_wait: the process-wide PortAudio lock is held
while a sentence plays and released between sentences, so microphone recovery
can re-initialise PortAudio in a gap but never under a sentence.

If a later sentence fails to synthesise, it is retried once. If it fails
again, speaking stops after the last sentence that was spoken: skipping it
could change what the reply means ("Don't. Unplug it first." without the
first sentence), and the failure is reported with how far speech got.

The reply can also arrive as it is generated, as an async iterable of text
chunks from the LLM. Each sentence is then synthesised as soon as the text
holds it complete, so the first word is heard one sentence into the answer
rather than after the whole of it has been written.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator

logger = logging.getLogger(__name__)

#: A fragment shorter than this is joined to the next one. Kokoro given
#: "Hi." or "Yes!" alone produces clipped prosody and a pause as long as the
#: word, and each sentence costs a separate PortAudio start.
MIN_SENTENCE_CHARS = 24

_SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]*\s+|\n+")


def split_sentences(text: str, min_chars: int = MIN_SENTENCE_CHARS) -> list[str]:
    """Split a reply at sentence ends, joining fragments shorter than min_chars."""
    pieces = [p.strip() for p in _SENTENCE_END.split(text.strip()) if p and p.strip()]
    sentences: list[str] = []
    pending = ""
    for piece in pieces:
        pending = f"{pending} {piece}".strip() if pending else piece
        if len(pending) >= min_chars:
            sentences.append(pending)
            pending = ""
    if pending:
        if sentences and len(pending) < min_chars:
            sentences[-1] = f"{sentences[-1]} {pending}"
        else:
            sentences.append(pending)
    return sentences


async def stream_sentences(
    chunks: AsyncIterable[str],
    *,
    capped: Callable[[], bool] = lambda: False,
    min_chars: int = MIN_SENTENCE_CHARS,
) -> AsyncIterator[str]:
    """Yield the sentences split_sentences would find, each as soon as it is complete.

    A sentence is complete once the whitespace after its end has arrived, so
    the split is the one split_sentences makes of the whole text, with one
    difference: a short last fragment is spoken on its own, because the
    sentence before it has already been spoken.

    capped() is asked once the chunks end: True means the reply was cut off
    by the token limit, and an unfinished last sentence is dropped as
    _drop_unfinished_sentence does for a whole reply (kept whole if the reply
    has no sentence end at all).
    """
    buffer = ""
    pending = ""
    any_sentence = False
    async for chunk in chunks:
        buffer += chunk
        *complete, buffer = _SENTENCE_END.split(buffer)
        for piece in complete:
            piece = piece.strip()
            if not piece:
                continue
            any_sentence = True
            pending = f"{pending} {piece}".strip() if pending else piece
            if len(pending) >= min_chars:
                yield pending
                pending = ""
    tail = buffer.strip()
    if tail and capped():
        cut = max(tail.rfind(mark) for mark in ".!?")
        if cut > 0:
            tail = tail[: cut + 1]
        elif any_sentence or pending:
            tail = ""
    if tail:
        pending = f"{pending} {tail}".strip() if pending else tail
    if pending:
        yield pending


@dataclass
class StreamResult:
    """How far a streamed reply got."""

    sentences: int
    spoken: int = 0
    audio_seconds: float = 0.0
    first_audio_s: float | None = None
    error: str | None = None
    timings: list[tuple[float, float]] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return self.error is None and self.spoken == self.sentences


async def speak_streaming(
    text: str | AsyncIterable[str],
    synthesize: Callable[[str], tuple[Any, int]],
    play: Callable[[Any, int], None],
    *,
    synth_timeout_s: float,
    text_timeout_s: float | None = None,
    capped: Callable[[], bool] = lambda: False,
    gap_s: float = 0.12,
    tail_s: float = 0.30,
) -> StreamResult:
    """Speak text sentence by sentence; synthesise sentence n+1 while n plays.

    text is the whole reply, or an async iterable of chunks as the reply is
    generated (see stream_sentences; capped applies to it).

    synthesize(sentence) returns (float32 samples, sample_rate) and runs in a
    worker thread; play(samples, sample_rate) blocks until the audio has
    played. synth_timeout_s bounds each wait for synthesis, which is the
    silence the user hears, not the length of the reply. text_timeout_s
    bounds each wait for the next sentence of a generated reply, so a stalled
    generator cannot hold the turn open; a stall ends the reply there.

    A synthesis that fails or overruns is retried once; if it fails again,
    speaking stops there and StreamResult.error says why. The first
    sentence failing twice raises, so the caller can fall back as it did
    before streaming existed. A generated reply that fails before its first
    sentence also raises.
    """
    import numpy as np

    if isinstance(text, str):
        sentences = split_sentences(text)
        source_done = True
        source_error: BaseException | None = None
        arrived = asyncio.Event()
        reader = None
    else:
        sentences = []
        source_done = False
        source_error = None
        arrived = asyncio.Event()

        async def read() -> None:
            nonlocal source_done, source_error
            try:
                async for sentence in stream_sentences(text, capped=capped):
                    sentences.append(sentence)
                    arrived.set()
            except Exception as exc:
                source_error = exc
            finally:
                source_done = True
                arrived.set()

        reader = asyncio.ensure_future(read())

    result = StreamResult(sentences=len(sentences))

    async def sentence_at(i: int) -> str | None:
        """Sentence i once it has arrived, or None if the reply ended before it."""
        while len(sentences) <= i and not source_done:
            arrived.clear()
            if len(sentences) > i or source_done:
                break
            await asyncio.wait_for(arrived.wait(), timeout=text_timeout_s)
        return sentences[i] if len(sentences) > i else None

    def is_last(i: int) -> bool:
        return source_done and len(sentences) == i + 1

    def launch(i: int) -> asyncio.Task[tuple[Any, int]]:
        return asyncio.ensure_future(asyncio.to_thread(synthesize, sentences[i]))

    async def ready(i: int, task: asyncio.Task[tuple[Any, int]]) -> tuple[Any, int]:
        for attempt in (1, 2):
            try:
                audio, rate = await asyncio.wait_for(task, timeout=synth_timeout_s)
                if audio is None or len(audio) == 0:
                    msg = "synthesis returned no audio"
                    raise ValueError(msg)
                return audio, rate
            except Exception as exc:
                reason = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
                if attempt == 2:
                    raise RuntimeError(reason) from exc
                logger.warning(
                    "TTS sentence %d/%d failed (%s) - retrying once", i + 1, len(sentences), reason,
                )
                task = launch(i)
        raise AssertionError("unreachable")

    async def next_task(i: int) -> asyncio.Task[tuple[Any, int]] | None:
        """Start synthesising sentence i as soon as it is there; None at the end of the reply."""
        try:
            if await sentence_at(i) is None:
                return None
        except TimeoutError:
            result.error = f"the reply stopped arriving after {i} sentences"
            logger.error("TTS: no further text after %d sentences within %.1fs", i, text_timeout_s or 0)
            return None
        return launch(i)

    started = time.perf_counter()
    try:
        pending = await next_task(0)
        if pending is None:
            if source_error is not None:
                raise RuntimeError(f"reply failed before its first sentence: {source_error}") from source_error
            result.sentences = len(sentences)
            return result
        lookahead: asyncio.Task[asyncio.Task[tuple[Any, int]] | None] | None = None
        i = 0
        while pending is not None:
            t0 = time.perf_counter()
            try:
                audio, rate = await ready(i, pending)
            except RuntimeError as exc:
                if i == 0:
                    raise
                result.error = f"spoke {i} of {len(sentences)} sentences; sentence {i + 1} failed: {exc}"
                logger.error(
                    "TTS stopped after %d of %d sentences: %s. Not skipping ahead, which "
                    "could change the reply's meaning. Unspoken: %r",
                    i, len(sentences), exc, " ".join(sentences[i:]),
                )
                break
            waited = time.perf_counter() - t0
            # Sentence i+1 is synthesised while sentence i plays.
            lookahead = asyncio.ensure_future(next_task(i + 1))
            if not lookahead.done():
                await asyncio.sleep(0)  # let it start, and see the end of a finished reply
            pad = np.zeros(int(rate * (tail_s if is_last(i) else gap_s)), dtype=np.float32)
            samples = np.concatenate([np.asarray(audio, dtype=np.float32), pad])
            if result.first_audio_s is None:
                result.first_audio_s = time.perf_counter() - started
            await asyncio.to_thread(play, samples, rate)
            result.spoken += 1
            result.audio_seconds += len(audio) / rate
            result.timings.append((waited, len(audio) / rate))
            pending = await lookahead
            lookahead = None
            i += 1
        if source_error is not None and result.error is None:
            result.error = f"spoke {result.spoken} sentences; the reply failed after them: {source_error}"
        result.sentences = len(sentences)
        return result
    finally:
        if reader is not None and not reader.done():
            reader.cancel()
