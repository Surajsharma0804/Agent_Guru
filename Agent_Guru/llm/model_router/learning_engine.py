"""Module: Agent_Guru.llm.model_router.learning_engine
Purpose: Learns from historical performance to improve model selection weights.

Uses exponential moving average (EMA) for stable, bounded weight updates.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime

import structlog

from Agent_Guru.llm.model_router.models import LearningWeights, PerformanceRecord, TaskType

logger = structlog.get_logger("model_router.learning_engine")

# EMA learning rate — how fast weights adapt to new observations
_LEARNING_RATE = 0.1
# Minimum samples before confidence reaches 1.0
_MIN_SAMPLES_FOR_CONFIDENCE = 50
# Exploration rate bounds
_BASE_EXPLORATION_RATE = 0.3
_MIN_EXPLORATION_RATE = 0.05
# Reward components
# SUCCESS_BONUS > 1.0 ensures that successful calls with low latency
# produce a reward above the neutral weight of 1.0, driving EMA upward.
_SUCCESS_BONUS = 2.0
_FAILURE_PENALTY = -0.5
_LATENCY_PENALTY_SCALE = 0.0001  # per ms
_COST_PENALTY_SCALE = 10.0  # per dollar
# Degradation threshold (20% drop triggers weight reduction)
_DEGRADATION_THRESHOLD = 0.20


class LearningEngine:
    """Learns model selection weights from performance outcomes.

    Weights are updated using EMA so they remain bounded and stable.
    Exploration rate decays as confidence grows, with a minimum floor.

    Args:
        learning_rate: EMA learning rate (0 < lr < 1).
        min_samples_for_confidence: Samples needed for full confidence.
        base_exploration_rate: Starting exploration rate.
        min_exploration_rate: Minimum exploration rate floor.

    """

    def __init__(
        self,
        learning_rate: float = _LEARNING_RATE,
        min_samples_for_confidence: int = _MIN_SAMPLES_FOR_CONFIDENCE,
        base_exploration_rate: float = _BASE_EXPLORATION_RATE,
        min_exploration_rate: float = _MIN_EXPLORATION_RATE,
    ) -> None:
        # (model_id, task_type.value) → LearningWeights
        self._weights: dict[tuple[str, str], LearningWeights] = {}
        self._lock = threading.RLock()
        self._learning_rate = learning_rate
        self._min_samples = min_samples_for_confidence
        self._base_exploration = base_exploration_rate
        self._min_exploration = min_exploration_rate

    # ------------------------------------------------------------------
    # Weight management
    # ------------------------------------------------------------------

    def update_weights(self, record: PerformanceRecord) -> LearningWeights:
        """Update learning weights based on a performance outcome.

        Args:
            record: Performance record from a completed task.

        Returns:
            Updated LearningWeights.

        """
        key = (record.model_id, record.task_type.value)

        with self._lock:
            weights = self._weights.get(key)
            if weights is None:
                weights = LearningWeights(
                    model_id=record.model_id,
                    task_type=record.task_type,
                    weight=1.0,
                    confidence=0.0,
                    sample_size=0,
                )
                self._weights[key] = weights

            reward = self._calculate_reward(record)

            # EMA weight update
            weights.weight = (
                1 - self._learning_rate
            ) * weights.weight + self._learning_rate * reward
            weights.sample_size += 1
            weights.confidence = min(1.0, weights.sample_size / self._min_samples)
            weights.last_updated = datetime.now(UTC)

        logger.debug(
            "weights_updated",
            model_id=record.model_id,
            task_type=record.task_type.value,
            weight=weights.weight,
            confidence=weights.confidence,
        )
        return weights

    def get_weight(self, model_id: str, task_type: TaskType) -> float:
        """Get the current selection weight for a model+task_type pair.

        Returns 1.0 (neutral) if no data exists yet.
        """
        key = (model_id, task_type.value)
        with self._lock:
            w = self._weights.get(key)
        return w.weight if w is not None else 1.0

    def get_weights_for_task(self, task_type: TaskType) -> dict[str, float]:
        """Get all model weights for a given task type.

        Returns:
            Dict mapping model_id → weight.

        """
        with self._lock:
            return {
                model_id: w.weight
                for (model_id, tt), w in self._weights.items()
                if tt == task_type.value
            }

    def initialize_new_model(
        self,
        model_id: str,
        similar_model_ids: list[str] | None = None,
    ) -> None:
        """Initialize weights for a new model based on similar models.

        If similar models are provided, the new model starts with their
        average weight. Otherwise it starts at 1.0 (neutral).

        Args:
            model_id: New model to initialize.
            similar_model_ids: Optional list of similar model IDs.

        """
        with self._lock:
            # Collect all task types seen so far
            task_types = {tt for _, tt in self._weights}

            for tt in task_types:
                key = (model_id, tt)
                if key in self._weights:
                    continue  # Already initialized

                initial_weight = 1.0
                if similar_model_ids:
                    similar_weights = [
                        self._weights[(sid, tt)].weight
                        for sid in similar_model_ids
                        if (sid, tt) in self._weights
                    ]
                    if similar_weights:
                        initial_weight = sum(similar_weights) / len(similar_weights)

                self._weights[key] = LearningWeights(
                    model_id=model_id,
                    task_type=TaskType(tt),
                    weight=initial_weight,
                    confidence=0.0,
                    sample_size=0,
                )

        logger.info("new_model_initialized", model_id=model_id, similar_models=similar_model_ids)

    # ------------------------------------------------------------------
    # Exploration
    # ------------------------------------------------------------------

    def get_exploration_rate(self, task_type: TaskType) -> float:
        """Calculate the current exploration rate for a task type.

        Exploration decays as average confidence grows, but never below
        the minimum floor.

        Args:
            task_type: Task type to calculate exploration rate for.

        Returns:
            Exploration rate in [min_exploration_rate, base_exploration_rate].

        """
        with self._lock:
            weights = [w for (_, tt), w in self._weights.items() if tt == task_type.value]

        if not weights:
            return self._base_exploration

        avg_confidence = sum(w.confidence for w in weights) / len(weights)
        # Linear decay from base to min as confidence goes 0 → 1
        rate = self._base_exploration * (1 - avg_confidence) + self._min_exploration
        return max(self._min_exploration, min(self._base_exploration, rate))

    # ------------------------------------------------------------------
    # Degradation detection
    # ------------------------------------------------------------------

    def detect_degradation(
        self,
        model_id: str,
        task_type: TaskType,
        recent_success_rate: float,
    ) -> bool:
        """Detect if a model has degraded significantly.

        Compares recent success rate against the stored weight. If the
        recent rate is more than DEGRADATION_THRESHOLD below the weight,
        the model is considered degraded and its weight is reduced.

        Args:
            model_id: Model to check.
            task_type: Task type.
            recent_success_rate: Recent success rate (0.0–1.0).

        Returns:
            True if degradation was detected.

        """
        key = (model_id, task_type.value)
        with self._lock:
            w = self._weights.get(key)
            if w is None or w.sample_size < 5:
                return False

            # Normalize weight to [0, 1] range for comparison
            normalized = max(0.0, min(1.0, w.weight))
            drop = normalized - recent_success_rate

            if drop > _DEGRADATION_THRESHOLD:
                # Penalize weight
                w.weight = (
                    1 - self._learning_rate
                ) * w.weight + self._learning_rate * _FAILURE_PENALTY
                w.last_updated = datetime.now(UTC)
                logger.warning(
                    "degradation_detected",
                    model_id=model_id,
                    task_type=task_type.value,
                    drop=drop,
                )
                return True

        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calculate_reward(self, record: PerformanceRecord) -> float:
        """Calculate reward signal from a performance record."""
        base = _SUCCESS_BONUS if record.success else _FAILURE_PENALTY

        latency_penalty = record.latency_ms * _LATENCY_PENALTY_SCALE
        return base - latency_penalty
