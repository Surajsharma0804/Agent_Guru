"""Emotion Detector with expanded companion emotion classification."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np

# Original 7 Ekman emotions + companion-required emotions
EKMAN_EMOTIONS = ["happy", "sad", "angry", "fearful", "disgusted", "surprised", "neutral"]

COMPANION_EMOTIONS = [
    # Core Ekman
    "happy", "sad", "angry", "fearful", "disgusted", "surprised", "neutral",
    # Companion-layer emotions
    "frustrated", "tired", "confused", "proud", "motivated", "curious", "excited",
]

# ── Precompiled keyword → emotion mapping ─────────────────────────────────
# Each entry: (tuple of keyword phrases, emotion_scores dict)
# Built once at import time — zero per-call allocation.
#
# DESIGN RULE: Every keyword must be specific enough to avoid false positives
# on normal commands. Single common words like "ready", "lost", "love", "great"
# are BANNED unless they appear in a multi-word phrase that signals genuine
# emotion (e.g. "i love" vs just "love").
_EMOTION_KEYWORDS: list[tuple[tuple[str, ...], dict[str, float]]] = [
    # Priority order: most specific first
    (
        ("frustrated", "frustrating", "ugh", "so annoying", "doesnt work",
         "not working", "keeps failing", "why wont", "cant get this",
         "wont work", "this is broken", "useless", "sick of this"),
        {"frustrated": 0.8, "angry": 0.1, "neutral": 0.1},
    ),
    (
        ("so tired", "really tired", "exhausted", "sleepy", "drained",
         "worn out", "cant focus", "no energy", "need sleep",
         "i am tired", "im tired", "feel tired"),
        {"tired": 0.8, "sad": 0.1, "neutral": 0.1},
    ),
    (
        ("confused", "dont understand", "makes no sense", "doesnt make sense",
         "i dont get", "what do you mean", "not sure what",
         "i am lost", "im lost", "so unclear"),
        {"confused": 0.8, "neutral": 0.2},
    ),
    (
        ("so proud", "nailed it", "nailed the", "nailed my", "finally did it",
         "i did it", "accomplished", "got it working", "it works now",
         "crushed it", "aced it", "aced the", "pulled it off"),
        {"proud": 0.8, "happy": 0.15, "neutral": 0.05},
    ),
    (
        ("motivated", "lets do this", "im pumped", "lets go",
         "fired up", "in the zone", "on a roll", "bring it on",
         "im ready for", "so ready"),
        {"motivated": 0.8, "excited": 0.1, "neutral": 0.1},
    ),
    (
        ("curious", "wondering", "i wonder", "tell me more",
         "what if", "have you heard", "did you know", "how does"),
        {"curious": 0.8, "neutral": 0.2},
    ),
    (
        ("so excited", "cant wait", "this is amazing", "thats awesome",
         "incredible", "this is great", "omg", "oh my god",
         "no way", "im excited"),
        {"excited": 0.7, "happy": 0.2, "neutral": 0.1},
    ),
    (
        ("so happy", "im happy", "i feel happy", "wonderful",
         "i love this", "i love it", "fantastic", "thats perfect"),
        {"happy": 0.8, "neutral": 0.2},
    ),
    (
        ("so sad", "i feel sad", "terrible", "i feel awful", "want to cry",
         "upset", "heartbroken", "feel bad", "feel down"),
        {"sad": 0.8, "neutral": 0.2},
    ),
    (
        ("angry", "furious", "i hate", "pissed", "rage", "so mad"),
        {"angry": 0.8, "neutral": 0.2},
    ),
    (
        ("scared", "afraid", "nervous", "anxious", "worried",
         "freaking out", "terrified"),
        {"fearful": 0.8, "neutral": 0.2},
    ),
]

_NEUTRAL_SCORES: dict[str, float] = {"neutral": 0.8, "happy": 0.1, "sad": 0.1}


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
    emotion_counts: dict[str, int]
    period_days: int = 7


class EmotionDetector:
    """Fuses voice prosody, text sentiment, and facial expression for emotion detection.

    Complexity:
        detect()           — O(E) where E = number of emotions (14), constant
        _detect_from_text() — O(K × L) where K = total keywords (~100), L = avg keyword length
                              Effectively O(1) since K and L are bounded constants.
        _detect_from_voice() — O(N) where N = audio samples (np.mean)
        get_trend()         — O(H) where H = history size (capped at 1000)
    Space:
        O(1000) for history deque (bounded)
    """

    def __init__(self, opted_out: bool = False) -> None:
        self._opted_out = opted_out
        self._history: deque[EmotionalState] = deque(maxlen=1000)

    def opt_out(self) -> None:
        self._opted_out = True

    def opt_in(self) -> None:
        self._opted_out = False

    def detect(
        self,
        audio: np.ndarray | None = None,
        text: str | None = None,
        face_features: np.ndarray | None = None,
    ) -> EmotionalState:
        """Detect emotion from available modalities.

        Time:  O(E) where E = |COMPANION_EMOTIONS| = 14 (constant)
        Space: O(E) for the scores dict
        """
        if self._opted_out:
            return EmotionalState(emotion="neutral", confidence=1.0, source="opted_out")

        scores: dict[str, float] = dict.fromkeys(COMPANION_EMOTIONS, 0.0)

        if audio is not None:
            voice_scores = self._detect_from_voice(audio)
            for e, s in voice_scores.items():
                scores[e] = scores.get(e, 0.0) + s * 0.4

        if text is not None:
            text_scores = self._detect_from_text(text)
            for e, s in text_scores.items():
                scores[e] = scores.get(e, 0.0) + s * 0.4

        if face_features is not None:
            face_scores = self._detect_from_face(face_features)
            for e, s in face_scores.items():
                scores[e] = scores.get(e, 0.0) + s * 0.2

        # Normalize — O(E)
        total = sum(scores.values())
        if total > 0:
            scores = {e: s / total for e, s in scores.items()}

        best_emotion = max(scores, key=scores.__getitem__)  # O(E), avoids lambda overhead
        confidence = scores[best_emotion]

        # Determine source — O(1)
        sources_mask = (
            (audio is not None) + (text is not None) + (face_features is not None)
        )
        if sources_mask > 1:
            source = "fused"
        elif audio is not None:
            source = "voice"
        elif text is not None:
            source = "text"
        elif face_features is not None:
            source = "face"
        else:
            source = "none"

        state = EmotionalState(
            emotion=best_emotion,
            confidence=confidence,
            source=source,
        )
        self._history.append(state)
        return state

    def _detect_from_voice(self, audio: np.ndarray) -> dict[str, float]:
        """Stub: prosody-based emotion detection.

        Time:  O(N) for np.mean where N = audio samples
        Space: O(1)
        """
        energy = float(np.mean(audio ** 2))
        if energy > 0.1:
            return {"happy": 0.5, "neutral": 0.3, "angry": 0.2}
        return {"neutral": 0.7, "sad": 0.2, "fearful": 0.1}

    def _detect_from_text(self, text: str) -> dict[str, float]:
        """Keyword-based emotion detection covering all companion emotions.

        Time:  O(T + K×L) where T = text length (for lower+replace),
               K = total keywords (~100), L = avg keyword length (~8 chars).
               Since K and L are bounded constants, effectively O(T).
               The `any(w in t ...)` short-circuits on first match.
        Space: O(T) for the normalized text copy
        """
        # Normalize: lowercase, strip apostrophes — O(T)
        t = text.lower().replace("'", "").replace("\u2019", "")

        # Check each emotion group — short-circuits on first match
        for keywords, scores in _EMOTION_KEYWORDS:
            if any(w in t for w in keywords):
                return scores

        return _NEUTRAL_SCORES

    def _detect_from_face(self, features: np.ndarray) -> dict[str, float]:
        """Stub: facial expression classification.

        Time:  O(1)
        Space: O(1)
        """
        return {"neutral": 0.6, "happy": 0.3, "sad": 0.1}

    def get_trend(self, days: int = 7) -> EmotionTrend:
        """Get emotion trend over the past N days.

        Time:  O(H) where H = history size (max 1000)
        Space: O(E) for the counts dict
        """
        cutoff = time.time() - days * 86400
        recent = [s for s in self._history if s.timestamp >= cutoff]
        counts: dict[str, int] = dict.fromkeys(COMPANION_EMOTIONS, 0)
        for s in recent:
            counts[s.emotion] = counts.get(s.emotion, 0) + 1
        dominant = max(counts, key=counts.__getitem__) if recent else "neutral"
        return EmotionTrend(dominant_emotion=dominant, emotion_counts=counts, period_days=days)
