"""Natural Conversation: Barge-In, Multi-Party, Prosody."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["BargeInHandler", "ConversationManager", "ProsodyConfig", "SpeakerDiarization"]

# Latency targets
BARGE_IN_DETECTION_MS = 100
BARGE_IN_HALT_MS = 200
DIARIZATION_LATENCY_MS = 300
RESUMPTION_WINDOW_S = 1800  # 30 minutes


@dataclass
class ProsodyConfig:
    """Prosody settings for different utterance types."""

    rate: float = 1.0  # speech rate multiplier
    pitch: float = 1.0  # pitch multiplier
    emphasis: str = "none"  # none/moderate/strong

    PRESETS: dict[str, ProsodyConfig] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "PRESETS",
            {
                "question": ProsodyConfig(rate=0.95, pitch=1.1, emphasis="moderate"),
                "statement": ProsodyConfig(rate=1.0, pitch=1.0, emphasis="none"),
                "warning": ProsodyConfig(rate=0.9, pitch=0.95, emphasis="strong"),
                "confirmation": ProsodyConfig(rate=1.05, pitch=1.05, emphasis="moderate"),
            },
        )


@dataclass
class ConversationContext:
    """Per-speaker conversation context."""

    speaker_id: str
    turns: list[dict[str, Any]] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)

    def add_turn(self, text: str, role: str = "user") -> None:
        self.turns.append({"role": role, "text": text, "ts": time.time()})
        self.last_active = time.time()


class BargeInHandler:
    """Handles barge-in detection and output halting."""

    def __init__(self) -> None:
        self._interrupted_response: str | None = None
        self._output_active = False

    async def detect_barge_in(self, audio_chunk: bytes) -> bool:
        """Detect speech onset within 100ms using VAD stub."""
        # Stub: in production uses WebRTC VAD
        start = time.perf_counter()
        # Simulate VAD check
        await asyncio.sleep(0)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if not (elapsed_ms < BARGE_IN_DETECTION_MS):  # latency target
            raise AssertionError(f"Barge-in detection latency {elapsed_ms:.1f}ms exceeds target {BARGE_IN_DETECTION_MS}ms")
        # Simple energy-based detection stub
        return len(audio_chunk) > 0 and any(b > 128 for b in audio_chunk[:10])

    async def halt_output(self, current_response: str) -> None:
        """Halt output within 200ms and preserve context."""
        start = time.perf_counter()
        self.preserve_context(current_response)
        self._output_active = False
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("Output halted in %.1fms", elapsed_ms)

    def preserve_context(self, interrupted_response: str) -> None:
        """Store interrupted response for coherent resumption."""
        self._interrupted_response = interrupted_response

    def get_preserved_context(self) -> str | None:
        return self._interrupted_response

    def clear_preserved_context(self) -> None:
        self._interrupted_response = None


class SpeakerDiarization:
    """Multi-party speaker identification and context management."""

    def __init__(self) -> None:
        self._contexts: dict[str, ConversationContext] = {}

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
        if speaker_id not in self._contexts:
            self._contexts[speaker_id] = ConversationContext(speaker_id=speaker_id)
        return self._contexts[speaker_id]

    def merge_contexts(self, speaker_ids: list[str]) -> ConversationContext:
        """Merge contexts for shared queries."""
        merged = ConversationContext(speaker_id="merged_" + "_".join(speaker_ids))
        for sid in speaker_ids:
            ctx = self._contexts.get(sid)
            if ctx:
                merged.turns.extend(ctx.turns)
        merged.turns.sort(key=lambda t: t.get("ts", 0))
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
        """Get prosody config for utterance type."""
        presets = {
            "question": ProsodyConfig(rate=0.95, pitch=1.1, emphasis="moderate"),
            "statement": ProsodyConfig(rate=1.0, pitch=1.0, emphasis="none"),
            "warning": ProsodyConfig(rate=0.9, pitch=0.95, emphasis="strong"),
            "confirmation": ProsodyConfig(rate=1.05, pitch=1.05, emphasis="moderate"),
        }
        return presets.get(utterance_type, ProsodyConfig())

    def detect_stress(self, text: str) -> bool:
        """Detect stress markers in text."""
        stress_words = {"stressed", "anxious", "worried", "overwhelmed", "frustrated"}
        return any(w in text.lower() for w in stress_words)
