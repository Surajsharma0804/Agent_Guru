"""Preference Learning Engine.

Learns user preferences from behavioral signals and explicit feedback.
Uses Bayesian confidence updating with temporal decay.

Confidence formula:
  confidence = sigmoid(sum(w_i * decay(t_i)) / n)
  decay(t) = exp(-lambda * (now - t).total_seconds())
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from Agent_Guru.memory.models import (
    EvidenceType,
    Preference,
    PreferenceEvidence,
    PreferenceQuery,
    PreferenceSignal,
    PreferenceType,
    SignalType,
)

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _temporal_decay(timestamp: datetime, decay_lambda: float) -> float:
    """Exponential decay weight for evidence age."""
    age_seconds = (datetime.now(tz=UTC) - timestamp).total_seconds()
    return math.exp(-decay_lambda * max(0.0, age_seconds))


class PreferenceLearningEngine:
    """In-memory preference learning with Bayesian confidence updates.

    Partitioned by user_id for isolation (Property 11).
    """

    def __init__(self, decay_lambda: float = 2.67e-7) -> None:
        # user_id -> list[Preference]
        self._preferences: dict[UUID, list[Preference]] = defaultdict(list)
        self.decay_lambda = decay_lambda

    # ------------------------------------------------------------------
    # Signal processing
    # ------------------------------------------------------------------

    def process_signal(self, signal: PreferenceSignal) -> list[Preference]:
        """Extract preferences from a user signal and update the model."""
        evidence = PreferenceEvidence(
            evidence_type=self._signal_to_evidence_type(signal.signal_type),
            timestamp=signal.timestamp,
            weight=self._signal_weight(signal.signal_type),
            description=f"Signal: {signal.signal_type.value}",
        )
        # Find matching preference or create new one
        pref = self._find_matching_preference(signal)
        if pref is None:
            pref = Preference(
                user_id=signal.user_id,
                preference_type=self._infer_preference_type(signal),
                context=signal.context,
                value=signal.value,
                confidence=0.5,
                evidence=[evidence],
            )
            self._preferences[signal.user_id].append(pref)
        else:
            pref.evidence.append(evidence)
            pref.updated_at = datetime.now(tz=UTC)

        # Recalculate confidence
        pref.confidence = self._calculate_confidence(pref)
        return [pref]

    def _signal_to_evidence_type(self, signal_type: SignalType) -> EvidenceType:
        mapping = {
            SignalType.EXPLICIT_CHOICE: EvidenceType.EXPLICIT_STATEMENT,
            SignalType.IMPLICIT_BEHAVIOR: EvidenceType.BEHAVIORAL_PATTERN,
            SignalType.FEEDBACK: EvidenceType.FEEDBACK,
            SignalType.CORRECTION: EvidenceType.EXPLICIT_STATEMENT,
        }
        return mapping.get(signal_type, EvidenceType.FEEDBACK)

    def _signal_weight(self, signal_type: SignalType) -> float:
        weights = {
            SignalType.EXPLICIT_CHOICE: 1.0,
            SignalType.CORRECTION: 1.2,
            SignalType.FEEDBACK: 0.8,
            SignalType.IMPLICIT_BEHAVIOR: 0.5,
        }
        return weights.get(signal_type, 0.5)

    def _infer_preference_type(self, signal: PreferenceSignal) -> PreferenceType:
        ctx_keys = set(signal.context.keys())
        if "format" in ctx_keys:
            return PreferenceType.FORMAT
        if "topic" in ctx_keys:
            return PreferenceType.TOPIC
        if "style" in ctx_keys:
            return PreferenceType.COMMUNICATION_STYLE
        return PreferenceType.OTHER

    def _find_matching_preference(self, signal: PreferenceSignal) -> Preference | None:
        for pref in self._preferences.get(signal.user_id, []):
            if pref.context == signal.context and str(pref.value) == str(signal.value):
                return pref
        return None

    def _calculate_confidence(self, pref: Preference) -> float:
        """Bayesian confidence with temporal decay."""
        if not pref.evidence:
            return 0.5
        weighted_sum = sum(
            ev.weight * _temporal_decay(ev.timestamp, self.decay_lambda) for ev in pref.evidence
        )
        n = len(pref.evidence)
        return min(1.0, max(0.0, _sigmoid(weighted_sum / n)))

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def query_preference(self, query: PreferenceQuery) -> Preference | None:
        """Return the highest-confidence matching preference."""
        candidates = self._preferences.get(query.user_id, [])
        matches = [
            p
            for p in candidates
            if (query.preference_type is None or p.preference_type == query.preference_type)
            and p.confidence >= query.min_confidence
            and self._context_matches(p.context, query.context)
        ]
        if not matches:
            return None
        return max(matches, key=lambda p: p.confidence)

    def _context_matches(self, pref_ctx: dict[str, str], query_ctx: dict[str, str]) -> bool:
        """Preference context must contain all query context keys."""
        return all(pref_ctx.get(k) == v for k, v in query_ctx.items())

    def get_user_preferences(self, user_id: UUID) -> list[Preference]:
        return list(self._preferences.get(user_id, []))

    # ------------------------------------------------------------------
    # Preference shift detection
    # ------------------------------------------------------------------

    def detect_preference_shift(
        self,
        user_id: UUID,
        preference_type: PreferenceType,
        window: int = 5,
    ) -> dict[str, Any]:
        """Detect consistent directional changes in recent evidence weights."""
        prefs = [
            p for p in self._preferences.get(user_id, []) if p.preference_type == preference_type
        ]
        if not prefs:
            return {"shift_detected": False, "direction": None}

        # Use the most recent preference's evidence
        pref = max(prefs, key=lambda p: p.updated_at)
        recent = sorted(pref.evidence, key=lambda e: e.timestamp)[-window:]
        if len(recent) < 2:
            return {"shift_detected": False, "direction": None}

        weights = [e.weight for e in recent]
        # Check for consistent increase or decrease
        diffs = [weights[i + 1] - weights[i] for i in range(len(weights) - 1)]
        all_positive = all(d > 0 for d in diffs)
        all_negative = all(d < 0 for d in diffs)

        if all_positive:
            return {"shift_detected": True, "direction": "increasing"}
        if all_negative:
            return {"shift_detected": True, "direction": "decreasing"}
        return {"shift_detected": False, "direction": None}

    # ------------------------------------------------------------------
    # Implicit preference learning
    # ------------------------------------------------------------------

    def learn_implicit_preferences(
        self,
        user_id: UUID,
        behavior_log: list[dict[str, Any]],
        frequency_threshold: int = 3,
    ) -> list[Preference]:
        """Extract implicit preferences from repeated behaviors."""
        # Count behavior patterns
        pattern_counts: dict[str, int] = defaultdict(int)
        pattern_examples: dict[str, dict[str, Any]] = {}
        for behavior in behavior_log:
            key = f"{behavior.get('action', '')}:{behavior.get('context', '')}"
            pattern_counts[key] += 1
            pattern_examples[key] = behavior

        new_prefs: list[Preference] = []
        for key, count in pattern_counts.items():
            if count >= frequency_threshold:
                example = pattern_examples[key]
                evidence = PreferenceEvidence(
                    evidence_type=EvidenceType.BEHAVIORAL_PATTERN,
                    weight=min(1.0, count / 10.0),
                    description=f"Repeated behavior ({count}x): {key}",
                )
                pref = Preference(
                    user_id=user_id,
                    preference_type=PreferenceType.OTHER,
                    context={"pattern": key},
                    value=example.get("action"),
                    confidence=min(1.0, 0.3 + count * 0.1),
                    evidence=[evidence],
                )
                self._preferences[user_id].append(pref)
                new_prefs.append(pref)
        return new_prefs

    # ------------------------------------------------------------------
    # Confidence update from outcome
    # ------------------------------------------------------------------

    def update_preference_confidence(self, preference_id: UUID, outcome: bool) -> Preference | None:
        """Update confidence based on whether preference prediction was correct."""
        for prefs in self._preferences.values():
            for pref in prefs:
                if pref.id == preference_id:
                    delta = 0.05 if outcome else -0.05
                    pref.confidence = min(1.0, max(0.0, pref.confidence + delta))
                    pref.updated_at = datetime.now(tz=UTC)
                    return pref
        return None
