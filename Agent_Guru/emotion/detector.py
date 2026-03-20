"""Emotion Detector with 7-class Ekman classification."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

import numpy as np

# 7 Ekman emotions
EKMAN_EMOTIONS = ["happy", "sad", "angry", "fearful", "disgusted", "surprised", "neutral"]


@dataclass
class EmotionalState:
    """Detected emotional state."""
    emotion: str
    confidence: float
    timestamp: float = field(default_factory=time.time)
    source: str = "fused"  # speech/text/face/fused


@dataclass
class EmotionTrend:
    """7-day emotion trend."""
    dominant_emotion: str
    emotion_counts: Dict[str, int]
    period_days: int = 7


class EmotionDetector:
    """Fuses voice prosody, text sentiment, and facial expression for emotion detection."""

    def __init__(self, opted_out: bool = False) -> None:
        self._opted_out = opted_out
        self._history: Deque[EmotionalState] = deque(maxlen=1000)

    def opt_out(self) -> None:
        self._opted_out = True

    def opt_in(self) -> None:
        self._opted_out = False

    def detect(
        self,
        audio: Optional[np.ndarray] = None,
        text: Optional[str] = None,
        face_features: Optional[np.ndarray] = None,
    ) -> EmotionalState:
        """Detect emotion from available modalities."""
        if self._opted_out:
            return EmotionalState(emotion="neutral", confidence=1.0, source="opted_out")

        scores: Dict[str, float] = {e: 0.0 for e in EKMAN_EMOTIONS}

        if audio is not None:
            voice_scores = self._detect_from_voice(audio)
            for e, s in voice_scores.items():
                scores[e] += s * 0.4

        if text is not None:
            text_scores = self._detect_from_text(text)
            for e, s in text_scores.items():
                scores[e] += s * 0.4

        if face_features is not None:
            face_scores = self._detect_from_face(face_features)
            for e, s in face_scores.items():
                scores[e] += s * 0.2

        # Normalize
        total = sum(scores.values())
        if total > 0:
            scores = {e: s / total for e, s in scores.items()}

        best_emotion = max(scores, key=lambda k: scores[k])
        confidence = scores[best_emotion]

        state = EmotionalState(
            emotion=best_emotion,
            confidence=confidence,
            source="fused",
        )
        self._history.append(state)
        return state

    def _detect_from_voice(self, audio: np.ndarray) -> Dict[str, float]:
        """Stub: prosody-based emotion detection."""
        energy = float(np.mean(audio ** 2))
        if energy > 0.1:
            return {"happy": 0.5, "neutral": 0.3, "angry": 0.2}
        return {"neutral": 0.7, "sad": 0.2, "fearful": 0.1}

    def _detect_from_text(self, text: str) -> Dict[str, float]:
        """Stub: VADER-based sentiment."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["happy", "great", "wonderful", "love"]):
            return {"happy": 0.8, "neutral": 0.2}
        if any(w in text_lower for w in ["sad", "terrible", "awful", "cry"]):
            return {"sad": 0.8, "neutral": 0.2}
        if any(w in text_lower for w in ["angry", "furious", "hate"]):
            return {"angry": 0.8, "neutral": 0.2}
        return {"neutral": 0.8, "happy": 0.1, "sad": 0.1}

    def _detect_from_face(self, features: np.ndarray) -> Dict[str, float]:
        """Stub: facial expression classification."""
        return {"neutral": 0.6, "happy": 0.3, "sad": 0.1}

    def get_trend(self, days: int = 7) -> EmotionTrend:
        """Get emotion trend over the past N days."""
        cutoff = time.time() - days * 86400
        recent = [s for s in self._history if s.timestamp >= cutoff]
        counts: Dict[str, int] = {e: 0 for e in EKMAN_EMOTIONS}
        for s in recent:
            counts[s.emotion] = counts.get(s.emotion, 0) + 1
        dominant = max(counts, key=lambda k: counts[k]) if recent else "neutral"
        return EmotionTrend(dominant_emotion=dominant, emotion_counts=counts, period_days=days)
