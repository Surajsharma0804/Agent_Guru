"""Empathy Adapter for emotional response adaptation."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from Agent_Guru.emotion.detector import EmotionalState

DISTRESS_EMOTIONS = {"sad", "fearful"}
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


class EmpathyAdapter:
    """Adapts responses based on detected emotional state."""

    def __init__(self) -> None:
        self._recent_states: deque[EmotionalState] = deque(maxlen=10)

    def adapt_response(self, text: str, state: EmotionalState) -> AdaptedResponse:
        """Adapt response tone, vocabulary, and pacing for emotional state."""
        self._recent_states.append(state)

        tone_map = {
            "happy": "warm",
            "sad": "gentle",
            "angry": "calm",
            "fearful": "reassuring",
            "disgusted": "neutral",
            "surprised": "engaged",
            "neutral": "professional",
        }
        pacing_map = {
            "sad": "slow",
            "angry": "measured",
            "fearful": "slow",
            "happy": "normal",
            "neutral": "normal",
        }
        vocab_map = {
            "sad": "simple",
            "fearful": "simple",
            "angry": "simple",
            "happy": "normal",
            "neutral": "normal",
        }

        tone = tone_map.get(state.emotion, "neutral")
        pacing = pacing_map.get(state.emotion, "normal")
        vocab = vocab_map.get(state.emotion, "normal")

        # Adapt text (stub: prepend empathetic acknowledgment)
        adapted = text
        if state.emotion in DISTRESS_EMOTIONS and state.confidence > 0.5:
            adapted = f"I understand this might be difficult. {text}"

        return AdaptedResponse(
            original=text,
            adapted=adapted,
            tone=tone,
            pacing=pacing,
            vocabulary_level=vocab,
        )

    def should_offer_support(self) -> bool:
        """Check if distress support should be offered (3+ consecutive distress turns)."""
        if len(self._recent_states) < DISTRESS_CONSECUTIVE_TURNS:
            return False
        recent = list(self._recent_states)[-DISTRESS_CONSECUTIVE_TURNS:]
        return all(
            s.emotion in DISTRESS_EMOTIONS and s.confidence > DISTRESS_CONFIDENCE_THRESHOLD
            for s in recent
        )

    def get_ai_honesty_disclaimer(self) -> str:
        """Return AI honesty disclaimer (no simulated emotions)."""
        return "I'm an AI assistant. I don't experience emotions, but I'm here to help."
