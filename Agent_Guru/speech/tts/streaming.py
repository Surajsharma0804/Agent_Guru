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
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

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
    text: str,
    synthesize: Callable[[str], tuple[Any, int]],
    play: Callable[[Any, int], None],
    *,
    synth_timeout_s: float,
    gap_s: float = 0.12,
    tail_s: float = 0.30,
) -> StreamResult:
    """Speak text sentence by sentence; synthesise sentence n+1 while n plays.

    synthesize(sentence) returns (float32 samples, sample_rate) and runs in a
    worker thread; play(samples, sample_rate) blocks until the audio has
    played. synth_timeout_s bounds each wait for synthesis, which is the
    silence the user hears, not the length of the reply.

    A synthesis that fails or overruns is retried once; if it fails again,
    speaking stops there and StreamResult.error says why. The first
    sentence failing twice raises, so the caller can fall back as it did
    before streaming existed.
    """
    import numpy as np

    sentences = split_sentences(text)
    result = StreamResult(sentences=len(sentences))
    if not sentences:
        return result
    started = time.perf_counter()

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

    pending = launch(0)
    for i in range(len(sentences)):
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
        if i + 1 < len(sentences):
            pending = launch(i + 1)
        pad = np.zeros(int(rate * (tail_s if i + 1 == len(sentences) else gap_s)), dtype=np.float32)
        samples = np.concatenate([np.asarray(audio, dtype=np.float32), pad])
        if result.first_audio_s is None:
            result.first_audio_s = time.perf_counter() - started
        await asyncio.to_thread(play, samples, rate)
        result.spoken += 1
        result.audio_seconds += len(audio) / rate
        result.timings.append((waited, len(audio) / rate))
    return result
