"""Personality Evolution Engine.

Adapts communication style based on user interaction feedback.
Parameter changes are bounded to ±0.1 per update (consistency constraint).
Supports rollback to any previous version.

Consistency formula:
  consistency = 1.0 - sum(|param[i] - param[i-1]|) / (n_params * max_change)
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from Agent_Guru.memory.models import (
    FeedbackType,
    InteractionFeedback,
    PersonalityParameters,
    PersonalityProfile,
    PersonalitySnapshot,
)

logger = logging.getLogger(__name__)

_PARAM_NAMES = ["formality", "verbosity", "humor", "technical_depth", "empathy", "proactivity"]
_MAX_CHANGE = 0.1
_N_PARAMS = len(_PARAM_NAMES)
_AUTO_ROLLBACK_THRESHOLD = 0.3  # Satisfaction below this triggers rollback


class PersonalityEvolutionEngine:
    """In-memory personality evolution with consistency bounds and rollback."""

    def __init__(self, max_change: float = _MAX_CHANGE) -> None:
        self.max_change = max_change
        # user_id -> PersonalityProfile
        self._profiles: dict[UUID, PersonalityProfile] = {}

    # ------------------------------------------------------------------
    # Profile management
    # ------------------------------------------------------------------

    def get_personality_profile(self, user_id: UUID) -> PersonalityProfile:
        """Return profile, creating default if not exists."""
        if user_id not in self._profiles:
            self._profiles[user_id] = PersonalityProfile(user_id=user_id)
        return self._profiles[user_id].model_copy(deep=True)

    def _get_or_create(self, user_id: UUID) -> PersonalityProfile:
        if user_id not in self._profiles:
            self._profiles[user_id] = PersonalityProfile(user_id=user_id)
        return self._profiles[user_id]

    # ------------------------------------------------------------------
    # Feedback processing
    # ------------------------------------------------------------------

    def process_interaction_feedback(self, feedback: InteractionFeedback) -> PersonalityProfile:
        """Update personality parameters based on interaction feedback."""
        profile = self._get_or_create(feedback.user_id)

        # Save snapshot before update
        snapshot = PersonalitySnapshot(
            version=profile.version,
            parameters=profile.parameters.model_copy(deep=True),
            trigger=f"feedback:{feedback.feedback_type.value}",
        )
        profile.evolution_history.append(snapshot)

        # Compute gradient direction based on feedback type
        delta = self._compute_delta(feedback)

        # Apply bounded updates
        old_params = profile.parameters
        new_params = self._apply_bounded_update(old_params, delta, feedback.feedback_aspects)

        profile.parameters = new_params
        profile.version += 1
        profile.metrics.interaction_count += 1
        profile.metrics.last_updated = datetime.utcnow()

        # Update satisfaction metric
        satisfaction_delta = {
            FeedbackType.POSITIVE: 0.05,
            FeedbackType.NEGATIVE: -0.1,
            FeedbackType.NEUTRAL: 0.0,
        }[feedback.feedback_type]
        profile.metrics.user_satisfaction = min(
            1.0, max(0.0, profile.metrics.user_satisfaction + satisfaction_delta)
        )

        # Auto-rollback on very negative feedback
        if profile.metrics.user_satisfaction < _AUTO_ROLLBACK_THRESHOLD and len(profile.evolution_history) >= 2:
            logger.info("Auto-rollback triggered for user %s", feedback.user_id)
            profile = self._do_rollback(profile, profile.version - 2)

        self._profiles[feedback.user_id] = profile
        return profile.model_copy(deep=True)

    def _compute_delta(self, feedback: InteractionFeedback) -> dict[str, float]:
        """Compute parameter adjustment direction from feedback."""
        base = {
            FeedbackType.POSITIVE: 0.05,
            FeedbackType.NEGATIVE: -0.05,
            FeedbackType.NEUTRAL: 0.0,
        }[feedback.feedback_type]

        delta: dict[str, float] = dict.fromkeys(_PARAM_NAMES, base)
        # Amplify aspects mentioned in feedback
        aspect_map = {
            "formal": "formality",
            "verbose": "verbosity",
            "humor": "humor",
            "technical": "technical_depth",
            "empathy": "empathy",
            "proactive": "proactivity",
        }
        for aspect in feedback.feedback_aspects:
            for keyword, param in aspect_map.items():
                if keyword in aspect.lower():
                    delta[param] = base * 2
        return delta

    def _apply_bounded_update(
        self,
        params: PersonalityParameters,
        delta: dict[str, float],
        aspects: list[str],
    ) -> PersonalityParameters:
        """Apply delta clamped to ±max_change."""
        updates: dict[str, float] = {}
        for name in _PARAM_NAMES:
            current = getattr(params, name)
            change = max(-self.max_change, min(self.max_change, delta.get(name, 0.0)))
            updates[name] = min(1.0, max(0.0, current + change))
        return PersonalityParameters(**updates)

    # ------------------------------------------------------------------
    # Consistency measurement
    # ------------------------------------------------------------------

    def calculate_consistency(self, profile: PersonalityProfile) -> float:
        """Measure consistency across evolution history."""
        if len(profile.evolution_history) < 2:
            return 1.0
        total_change = 0.0
        for i in range(1, len(profile.evolution_history)):
            prev = profile.evolution_history[i - 1].parameters
            curr = profile.evolution_history[i].parameters
            for name in _PARAM_NAMES:
                total_change += abs(getattr(curr, name) - getattr(prev, name))
        n_transitions = len(profile.evolution_history) - 1
        max_possible = n_transitions * _N_PARAMS * self.max_change
        if max_possible == 0:
            return 1.0
        return max(0.0, 1.0 - total_change / max_possible)

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def rollback_personality(self, user_id: UUID, version: int) -> PersonalityProfile:
        """Rollback to a specific version."""
        profile = self._get_or_create(user_id)
        profile = self._do_rollback(profile, version)
        self._profiles[user_id] = profile
        return profile.model_copy(deep=True)

    def _do_rollback(self, profile: PersonalityProfile, target_version: int) -> PersonalityProfile:
        """Find snapshot at target_version and restore parameters."""
        snapshot = next(
            (s for s in reversed(profile.evolution_history) if s.version == target_version),
            None,
        )
        if snapshot is None and profile.evolution_history:
            # Fall back to earliest snapshot
            snapshot = profile.evolution_history[0]
        if snapshot is not None:
            profile.parameters = snapshot.parameters.model_copy(deep=True)
            profile.version = snapshot.version
            logger.debug("Rolled back user %s to version %d", profile.user_id, profile.version)
        return profile
