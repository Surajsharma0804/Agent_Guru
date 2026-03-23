"""Multi-Modal Input Fusion Engine."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

FUSION_WINDOW_MS = 500
LOW_CONFIDENCE_THRESHOLD = 0.4


@dataclass
class ModalityInput:
    """Input from a single modality."""
    modality: str          # "speech", "gesture", "touch", "gaze"
    intent: str
    confidence: float
    timestamp_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FusedIntent:
    """Result of fusing multiple modality inputs."""
    intent: str
    confidence: float
    modalities_used: list[str]
    timestamp_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


class ClarificationRequired(Exception):
    """Raised when all modality confidences are below threshold."""
    def __init__(self, inputs: list[ModalityInput]) -> None:
        self.inputs = inputs
        super().__init__("All modality confidences below threshold; clarification required")


class FusionEngine:
    """Fuses inputs from multiple modalities within a 500ms window."""

    def __init__(self, window_ms: float = FUSION_WINDOW_MS) -> None:
        self.window_ms = window_ms
        self._buffer: list[ModalityInput] = []

    def fuse(self, inputs: list[ModalityInput]) -> FusedIntent:
        """Fuse modality inputs within the fusion window.

        Raises ClarificationRequired if all confidences < 0.4.
        """
        if not inputs:
            raise ValueError("No inputs provided")

        now_ms = time.time() * 1000
        # Filter to window
        windowed = [i for i in inputs if (now_ms - i.timestamp_ms) <= self.window_ms]
        if not windowed:
            windowed = inputs  # fallback: use all

        # Check low confidence
        if all(i.confidence < LOW_CONFIDENCE_THRESHOLD for i in windowed):
            raise ClarificationRequired(windowed)

        # Confidence-weighted intent merging
        intent_scores: dict[str, float] = {}
        for inp in windowed:
            intent_scores[inp.intent] = intent_scores.get(inp.intent, 0.0) + inp.confidence

        best_intent = max(intent_scores, key=lambda k: intent_scores[k])
        total_weight = sum(intent_scores.values())
        fused_confidence = intent_scores[best_intent] / total_weight if total_weight > 0 else 0.0

        modalities = list({i.modality for i in windowed})

        fused = FusedIntent(
            intent=best_intent,
            confidence=fused_confidence,
            modalities_used=modalities,
            timestamp_ms=now_ms,
        )

        # Log to audit trail if available
        self._log_fusion(fused, windowed)
        return fused

    def resolve_deictic(self, reference: str, context: dict[str, Any]) -> Optional[str]:
        """Resolve deictic references like 'this'/'that' using context."""
        # Stub: in production uses CLIP embeddings
        if reference in ("this", "that", "it"):
            return context.get("last_object")
        return reference

    def _log_fusion(self, fused: FusedIntent, inputs: list[ModalityInput]) -> None:
        logger.debug(
            "Fused intent=%s confidence=%.2f modalities=%s",
            fused.intent, fused.confidence, fused.modalities_used,
        )
