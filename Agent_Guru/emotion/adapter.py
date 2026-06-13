"""Empathy Adapter for companion-aware emotional response adaptation."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from Agent_Guru.emotion.detector import EmotionalState

DISTRESS_EMOTIONS = frozenset({"sad", "fearful", "frustrated", "tired"})
DISTRESS_CONFIDENCE_THRESHOLD = 0.8
DISTRESS_CONSECUTIVE_TURNS = 3


@dataclass
class AdaptedResponse:
    """Response adapted for emotional state."""
    original: str
    adapted: str
    tone: str
    pacing: str
    vocabulary_level: str  # simple/normal/complex


# ── Module-level constant maps — allocated once, shared across all instances ──
# Previously these were rebuilt inside adapt_response() on every call:
# 4 dicts × 14 entries = 56 allocations per call → 0 allocations per call.

_TONE_MAP: dict[str, str] = {
    # Original Ekman
    "happy": "warm",
    "sad": "gentle",
    "angry": "calm",
    "fearful": "reassuring",
    "disgusted": "neutral",
    "surprised": "engaged",
    "neutral": "conversational",
    # Companion extensions
    "frustrated": "empathetic",
    "tired": "gentle",
    "confused": "clear",
    "proud": "celebratory",
    "motivated": "energetic",
    "curious": "engaged",
    "excited": "enthusiastic",
}

_PACING_MAP: dict[str, str] = {
    "sad": "slow",
    "angry": "measured",
    "fearful": "slow",
    "frustrated": "measured",
    "tired": "slow",
    "confused": "slow",
    "happy": "normal",
    "excited": "normal",
    "motivated": "normal",
    "proud": "normal",
    "curious": "normal",
    "neutral": "normal",
}

_VOCAB_MAP: dict[str, str] = {
    "sad": "simple",
    "fearful": "simple",
    "angry": "simple",
    "frustrated": "simple",
    "tired": "simple",
    "confused": "simple",
    "happy": "normal",
    "excited": "normal",
    "motivated": "normal",
    "proud": "normal",
    "curious": "normal",
    "neutral": "normal",
}

_ACKNOWLEDGMENT_MAP: dict[str, str] = {
    "happy": "That's great to hear! ",
    "sad": "That sounds really hard. ",
    "fearful": "It's okay — I've got you. ",
    "frustrated": "Yeah, that's genuinely annoying. ",
    "tired": "Take a breath — let's keep this simple. ",
    "confused": "No worries, let me break that down. ",
    "angry": "I hear you. ",
    "proud": "That's actually a big deal — nice. ",
    "motivated": "Let's go! ",
    "curious": "Good question — ",
    "excited": "Okay, I'm with you on this! ",
    "surprised": "Whoa, didn't see that coming! ",
}


class EmpathyAdapter:
    """Adapts responses based on detected emotional state (14-emotion companion coverage).

    Complexity:
        adapt_response()      — O(1) — all lookups are dict.get(), deque.append()
        should_offer_support() — O(K) where K = DISTRESS_CONSECUTIVE_TURNS = 3 (constant)
    Space:
        O(10) for the recent_states deque (bounded)
    """

    def __init__(self) -> None:
        self._recent_states: deque[EmotionalState] = deque(maxlen=10)

    def adapt_response(self, text: str, state: EmotionalState) -> AdaptedResponse:
        """Adapt response tone, vocabulary, and pacing for emotional state.

        Time:  O(1) — 3 dict lookups + 1 string concat
        Space: O(1) — no allocations beyond the return value
        """
        self._recent_states.append(state)

        tone = _TONE_MAP.get(state.emotion, "conversational")
        pacing = _PACING_MAP.get(state.emotion, "normal")
        vocab = _VOCAB_MAP.get(state.emotion, "normal")

        adapted = text
        if state.confidence > 0.5 and state.emotion in _ACKNOWLEDGMENT_MAP:
            adapted = _ACKNOWLEDGMENT_MAP[state.emotion] + text

        return AdaptedResponse(
            original=text,
            adapted=adapted,
            tone=tone,
            pacing=pacing,
            vocabulary_level=vocab,
        )

    def should_offer_support(self) -> bool:
        """Check if distress support should be offered (3+ consecutive distress turns).

        Time:  O(K) where K = 3 (constant)
        Space: O(K) for the slice
        """
        if len(self._recent_states) < DISTRESS_CONSECUTIVE_TURNS:
            return False
        recent = list(self._recent_states)[-DISTRESS_CONSECUTIVE_TURNS:]
        return all(
            s.emotion in DISTRESS_EMOTIONS and s.confidence > DISTRESS_CONFIDENCE_THRESHOLD
            for s in recent
        )

    def get_ai_honesty_disclaimer(self) -> str:
        """Return AI honesty disclaimer in companion-appropriate language."""
        return "I should be real with you — I'm an AI, so I don't actually feel things. But I'm always here for you."
