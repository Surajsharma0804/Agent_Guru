"""Natural Conversation: Barge-In, Multi-Party, Prosody."""

from __future__ import annotations

import asyncio
import heapq
import logging
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["BargeInHandler", "ConversationManager", "ProsodyConfig", "SpeakerDiarization"]

# Latency targets
BARGE_IN_DETECTION_MS = 100
BARGE_IN_HALT_MS = 200
DIARIZATION_LATENCY_MS = 300
RESUMPTION_WINDOW_S = 1800  # 30 minutes

#: Turns retained per speaker.
#:
#: MEMORY: ConversationContext.turns was an unbounded list appended to by
#: add_turn(). In a companion that is meant to run for weeks, a single
#: speaker's history grew without limit and nothing ever trimmed it.
MAX_TURNS_PER_SPEAKER = 500

#: Speakers whose context is kept in memory.
#:
#: MEMORY: SpeakerDiarization._contexts was an unbounded dict keyed by
#: speaker_id, created on demand by get_or_create_context() and never removed.
#: Diarization invents an id per distinct voice, so the key space is bounded
#: only by how many people ever speak near the device.
MAX_TRACKED_SPEAKERS = 64

VALID_EMPHASIS = frozenset({"none", "moderate", "strong"})


@dataclass(frozen=True)
class ProsodyConfig:
    """Prosody settings for different utterance types.

    CRASH FIX: this class was previously unconstructible. ``PRESETS`` was
    declared as a dataclass *instance* field and ``__post_init__`` filled it by
    constructing four more ``ProsodyConfig`` objects - each of which ran the
    same ``__post_init__``, constructing four more, without end. Every single
    ``ProsodyConfig(...)`` call, including the no-argument one, terminated in
    ``RecursionError``, which took ``ConversationManager.get_prosody()`` down
    with it. The presets are shared, immutable data that belongs to the module,
    not per-instance state rebuilt inside each instance's own constructor, so
    they now live in PROSODY_PRESETS below and are exposed here as a read-only
    class attribute.

    The class is frozen because the presets are shared: a caller that received
    a preset and mutated it would have silently changed the prosody of every
    later utterance of that type. ``object.__setattr__`` in the old
    ``__post_init__`` shows immutability was the intent all along.
    """

    rate: float = 1.0  # speech rate multiplier
    pitch: float = 1.0  # pitch multiplier
    emphasis: str = "none"  # none/moderate/strong

    def __post_init__(self) -> None:
        """Reject values a speech synthesiser cannot act on."""
        if self.rate <= 0:
            msg = f"rate must be positive, got {self.rate}"
            raise ValueError(msg)
        if self.pitch <= 0:
            msg = f"pitch must be positive, got {self.pitch}"
            raise ValueError(msg)
        if self.emphasis not in VALID_EMPHASIS:
            msg = f"emphasis must be one of {sorted(VALID_EMPHASIS)}, got {self.emphasis!r}"
            raise ValueError(msg)

    @classmethod
    def preset(cls, utterance_type: str) -> ProsodyConfig:
        """Return the preset for an utterance type, or a neutral default."""
        return PROSODY_PRESETS.get(utterance_type, NEUTRAL_PROSODY)


#: The single source of truth for prosody presets.
#:
#: Built once at import. Previously this table was duplicated in two places -
#: the (crashing) ProsodyConfig.__post_init__ and ConversationManager.
#: get_prosody, which rebuilt all four objects on every call - so the two
#: copies could drift apart with nothing to catch it.
PROSODY_PRESETS: MappingProxyType[str, ProsodyConfig] = MappingProxyType(
    {
        "question": ProsodyConfig(rate=0.95, pitch=1.1, emphasis="moderate"),
        "statement": ProsodyConfig(rate=1.0, pitch=1.0, emphasis="none"),
        "warning": ProsodyConfig(rate=0.9, pitch=0.95, emphasis="strong"),
        "confirmation": ProsodyConfig(rate=1.05, pitch=1.05, emphasis="moderate"),
    },
)

#: Returned for utterance types with no preset of their own.
NEUTRAL_PROSODY = ProsodyConfig()

# Backwards-compatible attribute access: ProsodyConfig.PRESETS still resolves,
# now to the shared read-only table rather than per-instance state.
ProsodyConfig.PRESETS = PROSODY_PRESETS  # type: ignore[attr-defined]


@dataclass
class ConversationContext:
    """Per-speaker conversation context.

    ``turns`` is a bounded deque: the oldest turn is dropped once
    MAX_TURNS_PER_SPEAKER is reached. It was an unbounded list, so a long-lived
    session grew one dict per utterance forever.
    """

    speaker_id: str
    turns: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=MAX_TURNS_PER_SPEAKER),
    )
    last_active: float = field(default_factory=time.time)

    def add_turn(self, text: str, role: str = "user") -> None:
        """Record one utterance, evicting the oldest if the buffer is full."""
        now = time.time()
        self.turns.append({"role": role, "text": text, "ts": now})
        self.last_active = now


class BargeInHandler:
    """Handles barge-in detection and output halting."""

    # P2-75: Minimum speech duration before a barge-in is confirmed.
    # Sub-200ms audio is almost always noise (coughs, sighs, "mm-hmm").
    _MIN_SPEECH_DURATION_MS: float = 200.0

    def __init__(self) -> None:
        self._interrupted_response: str | None = None
        self._interrupted_at: float | None = None  # P2-76: timestamp of interrupt
        self._output_active = False
        self._speech_onset: float | None = None  # P2-75: when speech started

    async def detect_barge_in(self, audio_chunk: bytes) -> bool:
        """Detect speech onset with 200ms minimum-duration guard.

        Returns True only when speech has persisted for at least
        _MIN_SPEECH_DURATION_MS, preventing false triggers from
        coughs, sighs, and backchannels.
        """
        start = time.perf_counter()
        # Simulate VAD check
        await asyncio.sleep(0)
        elapsed_ms = (time.perf_counter() - start) * 1000
        # RELIABILITY FIX: this used to `raise AssertionError` when the
        # measured latency exceeded the target. What it actually measures is
        # how long the event loop took to resume this coroutine, so a busy
        # machine - a GC pause, another task hogging the loop, a laptop waking
        # from sleep - turned a transient scheduling hiccup into a hard failure
        # of the interrupt path, exactly when the user is trying to interrupt.
        # Worse, `assert`-style checks are the first thing stripped under
        # `python -O`, so the guard was simultaneously too aggressive in
        # development and absent in an optimised build. Missing a latency
        # target is a signal to record, not a reason to stop detecting speech.
        if elapsed_ms >= BARGE_IN_DETECTION_MS:
            logger.warning(
                "Barge-in detection latency %.1fms exceeds target %dms; "
                "the event loop is congested",
                elapsed_ms,
                BARGE_IN_DETECTION_MS,
            )

        # Simple energy-based detection stub
        has_speech = len(audio_chunk) > 0 and any(b > 128 for b in audio_chunk[:10])

        if has_speech:
            now = time.perf_counter()
            if self._speech_onset is None:
                # Speech just started - record onset, don't trigger yet
                self._speech_onset = now
                return False
            # P2-75: Only confirm barge-in after minimum duration
            speech_duration_ms = (now - self._speech_onset) * 1000
            if speech_duration_ms >= self._MIN_SPEECH_DURATION_MS:
                return True
            return False  # Too short - could be a cough or backchannel

        # No speech - reset onset tracker
        self._speech_onset = None
        return False

    async def halt_output(self, current_response: str) -> None:
        """Halt output within 200ms and preserve context."""
        start = time.perf_counter()
        self.preserve_context(current_response)
        self._output_active = False
        self._speech_onset = None  # Reset for next detection cycle
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("Output halted in %.1fms", elapsed_ms)

    def preserve_context(self, interrupted_response: str) -> None:
        """Store interrupted response for coherent resumption.

        P2-76: Also stores the interrupt timestamp so the orchestrator
        can decide whether to resume or pivot based on elapsed time.
        """
        self._interrupted_response = interrupted_response
        self._interrupted_at = time.time()

    def get_preserved_context(self) -> dict[str, Any] | None:
        """Return preserved context with metadata, or None."""
        if self._interrupted_response is None:
            return None
        return {
            "response": self._interrupted_response,
            "interrupted_at": self._interrupted_at,
        }

    def clear_preserved_context(self) -> None:
        self._interrupted_response = None
        self._interrupted_at = None


class SpeakerDiarization:
    """Multi-party speaker identification and context management."""

    def __init__(self, max_speakers: int = MAX_TRACKED_SPEAKERS) -> None:
        """Track per-speaker context, bounded to the most recently active.

        Args:
            max_speakers: How many speakers to retain context for.

        """
        if max_speakers <= 0:
            msg = f"max_speakers must be positive, got {max_speakers}"
            raise ValueError(msg)
        self._max_speakers = max_speakers
        self._contexts: OrderedDict[str, ConversationContext] = OrderedDict()

    async def identify_speakers(self, audio_chunk: bytes) -> list[str]:
        """Identify speakers in audio within 300ms."""
        start = time.perf_counter()
        # Stub: in production uses pyannote.audio
        await asyncio.sleep(0)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("Diarization in %.1fms", elapsed_ms)
        # Return generic speaker when confidence < 80%
        return ["speaker_1"]

    def get_or_create_context(self, speaker_id: str) -> ConversationContext:
        """Return this speaker's context, creating it on first sight.

        Access refreshes recency, so the speakers evicted when the table is
        full are the ones who have been silent longest - the right choice for a
        room where a few people talk regularly and others pass through.
        """
        context = self._contexts.get(speaker_id)
        if context is not None:
            self._contexts.move_to_end(speaker_id)
            return context

        context = ConversationContext(speaker_id=speaker_id)
        self._contexts[speaker_id] = context
        while len(self._contexts) > self._max_speakers:
            evicted, _ = self._contexts.popitem(last=False)
            logger.debug("Evicted context for least-recently-active speaker %s", evicted)
        return context

    def forget_speaker(self, speaker_id: str) -> bool:
        """Drop a speaker's context. Returns True if there was one."""
        return self._contexts.pop(speaker_id, None) is not None

    @property
    def tracked_speakers(self) -> int:
        """How many speakers currently have context in memory."""
        return len(self._contexts)

    def merge_contexts(self, speaker_ids: list[str]) -> ConversationContext:
        """Merge contexts for shared queries, oldest turn first.

        Each speaker's turns are already in timestamp order because add_turn
        appends them as they happen, so the merged stream is produced by a
        k-way merge - O(n log k) and streaming - rather than by concatenating
        everything and re-sorting the result, which threw that ordering away
        and paid O(n log n) to rediscover it.
        """
        merged = ConversationContext(speaker_id="merged_" + "_".join(speaker_ids))
        streams = [
            self._contexts[sid].turns for sid in speaker_ids if sid in self._contexts
        ]
        merged.turns.extend(heapq.merge(*streams, key=lambda t: t.get("ts", 0)))
        return merged


class ConversationManager:
    """Manages multi-turn conversation with resumption and prosody."""

    def __init__(self) -> None:
        self.barge_in = BargeInHandler()
        self.diarization = SpeakerDiarization()
        self._last_session_end: float | None = None
        self._session_context: str | None = None

    def can_resume(self) -> bool:
        """Check if within 30-minute resumption window."""
        if self._last_session_end is None:
            return False
        return (time.time() - self._last_session_end) <= RESUMPTION_WINDOW_S

    def end_session(self, context_summary: str) -> None:
        self._last_session_end = time.time()
        self._session_context = context_summary

    def get_prosody(self, utterance_type: str) -> ProsodyConfig:
        """Get prosody config for an utterance type.

        Reads the shared PROSODY_PRESETS table instead of rebuilding a private
        copy of it - four object constructions - on every call. The configs are
        frozen, so handing out the shared instance is safe.
        """
        return ProsodyConfig.preset(utterance_type)

    def detect_stress(self, text: str) -> bool:
        """Detect stress markers in text."""
        stress_words = {"stressed", "anxious", "worried", "overwhelmed", "frustrated"}
        return any(w in text.lower() for w in stress_words)
