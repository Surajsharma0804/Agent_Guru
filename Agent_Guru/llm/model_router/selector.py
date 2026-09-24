"""Module: Agent_Guru.llm.model_router.selector
Purpose: Model Selector - scores and selects optimal models for tasks.

Implements cost-performance scoring with epsilon-greedy exploration.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass

import structlog

from Agent_Guru.llm.model_router.models import (
    ModelMetadata,
    PerformanceMetrics,
    SelectionResult,
    TaskAnalysis,
)

logger = structlog.get_logger("model_router.selector")

# Default scoring weights
_W_COST = 0.4
_W_PERFORMANCE = 0.4
_W_CAPABILITY = 0.2
# Local provider bonus (prefer local over cloud)
_LOCAL_PROVIDER_BONUS = 0.1
_LOCAL_PROVIDERS = frozenset({"ollama"})
# Latency warning threshold (ms)
_LATENCY_WARNING_MS = 100.0


@dataclass
class ModelScore:
    """Scoring breakdown for a candidate model."""

    model_id: str
    total_score: float
    cost_score: float
    performance_score: float
    capability_score: float
    estimated_cost: float
    estimated_latency_ms: float


class ModelSelector:
    """Selects the optimal model for a task using multi-criteria scoring.

    Scoring formula:
        total = w_cost * cost_score + w_performance * perf_score
                + w_capability * cap_score + local_bonus

    Args:
        w_cost: Weight for cost score.
        w_performance: Weight for performance score.
        w_capability: Weight for capability score.
        prefer_local: Whether to apply a bonus for local (Ollama) models.

    """

    def __init__(
        self,
        w_cost: float = _W_COST,
        w_performance: float = _W_PERFORMANCE,
        w_capability: float = _W_CAPABILITY,
        prefer_local: bool = True,
    ) -> None:
        self._w_cost = w_cost
        self._w_performance = w_performance
        self._w_capability = w_capability
        self._prefer_local = prefer_local
        self._lock = threading.RLock()

    def select(
        self,
        candidates: list[ModelMetadata],
        analysis: TaskAnalysis,
        performance_map: dict[str, PerformanceMetrics] | None = None,
        learning_weights: dict[str, float] | None = None,
        exploration_rate: float = 0.0,
    ) -> SelectionResult | None:
        """Select the best model from candidates for the given task.

        Args:
            candidates: Available models to choose from.
            analysis: Task analysis with requirements and constraints.
            performance_map: Optional dict of model_id → PerformanceMetrics.
            learning_weights: Optional dict of model_id → learned weight.
            exploration_rate: Probability of exploring a non-top model.

        Returns:
            SelectionResult, or None if no suitable model found.

        """
        start = time.monotonic()

        # Filter to capable, available models
        eligible = self._filter_candidates(candidates, analysis)

        if not eligible:
            logger.warning(
                "no_eligible_models",
                task_type=analysis.task_type.value,
                required_caps=[c.value for c in analysis.required_capabilities],
            )
            return None

        # Score all eligible models
        scores = self._score_models(eligible, analysis, performance_map, learning_weights)
        scores.sort(key=lambda s: s.total_score, reverse=True)

        # Epsilon-greedy exploration
        selected_score = self._explore_or_exploit(scores, exploration_rate)

        fallbacks = [s.model_id for s in scores if s.model_id != selected_score.model_id][:3]

        elapsed_ms = (time.monotonic() - start) * 1000
        if elapsed_ms > _LATENCY_WARNING_MS:
            logger.warning(
                "selection_latency_high",
                elapsed_ms=elapsed_ms,
                task_type=analysis.task_type.value,
            )

        reasoning = (
            f"Selected {selected_score.model_id} "
            f"(cost={selected_score.cost_score:.3f}, "
            f"perf={selected_score.performance_score:.3f}, "
            f"cap={selected_score.capability_score:.3f}, "
            f"total={selected_score.total_score:.3f})"
        )

        logger.info(
            "model_selected",
            model_id=selected_score.model_id,
            task_type=analysis.task_type.value,
            total_score=selected_score.total_score,
            reasoning=reasoning,
        )

        return SelectionResult(
            model_id=selected_score.model_id,
            reasoning=reasoning,
            estimated_cost=selected_score.estimated_cost,
            estimated_latency_ms=selected_score.estimated_latency_ms,
            confidence=min(1.0, selected_score.total_score),
            fallback_models=fallbacks,
        )

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _filter_candidates(
        self,
        candidates: list[ModelMetadata],
        analysis: TaskAnalysis,
    ) -> list[ModelMetadata]:
        """Filter candidates to those meeting hard constraints."""
        eligible = []
        for model in candidates:
            if not model.is_available:
                continue
            # Must have all required capabilities
            if not analysis.required_capabilities.issubset(model.capabilities):
                continue
            # Latency constraint
            if (
                analysis.latency_constraint_ms is not None
                and model.average_latency_ms > analysis.latency_constraint_ms
            ):
                continue
            # Cost constraint
            if analysis.cost_constraint is not None:
                est_cost = model.estimated_cost(
                    analysis.estimated_input_tokens,
                    analysis.estimated_output_tokens,
                )
                if est_cost > analysis.cost_constraint:
                    continue
            eligible.append(model)
        return eligible

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_models(
        self,
        models: list[ModelMetadata],
        analysis: TaskAnalysis,
        performance_map: dict[str, PerformanceMetrics] | None,
        learning_weights: dict[str, float] | None,
    ) -> list[ModelScore]:
        scores = []
        for model in models:
            est_cost = model.estimated_cost(
                analysis.estimated_input_tokens,
                analysis.estimated_output_tokens,
            )
            cost_score = self._cost_score(est_cost)
            perf_score = self._performance_score(model.model_id, performance_map)
            cap_score = self._capability_score(model, analysis)

            total = (
                self._w_cost * cost_score
                + self._w_performance * perf_score
                + self._w_capability * cap_score
            )

            # Apply local provider bonus
            if self._prefer_local and model.provider.value in _LOCAL_PROVIDERS:
                total += _LOCAL_PROVIDER_BONUS

            # Apply learned weight multiplier
            if learning_weights:
                lw = learning_weights.get(model.model_id, 1.0)
                total *= max(0.01, lw)  # Prevent zero/negative total

            scores.append(
                ModelScore(
                    model_id=model.model_id,
                    total_score=total,
                    cost_score=cost_score,
                    performance_score=perf_score,
                    capability_score=cap_score,
                    estimated_cost=est_cost,
                    estimated_latency_ms=model.average_latency_ms,
                ),
            )
        return scores

    @staticmethod
    def _cost_score(estimated_cost: float) -> float:
        """Lower cost → higher score. Score in (0, 1]."""
        return 1.0 / (1.0 + estimated_cost)

    @staticmethod
    def _performance_score(
        model_id: str,
        performance_map: dict[str, PerformanceMetrics] | None,
    ) -> float:
        """Compute performance score from historical metrics."""
        if not performance_map or model_id not in performance_map:
            return 0.5  # Neutral default for unknown models

        m = performance_map[model_id]
        if m.sample_size == 0:
            return 0.5

        # Normalize latency: lower is better, cap at 5000ms
        normalized_latency = max(1.0, min(m.average_latency_ms, 5000.0))
        latency_score = 1000.0 / normalized_latency  # 0.2 at 5000ms, 1.0 at 1000ms

        return m.success_rate * 0.6 + latency_score * 0.3 + m.average_quality * 0.1

    @staticmethod
    def _capability_score(model: ModelMetadata, analysis: TaskAnalysis) -> float:
        """Score based on how well model capabilities match task needs."""
        if not analysis.required_capabilities:
            return 1.0
        matched = len(analysis.required_capabilities & model.capabilities)
        return matched / len(analysis.required_capabilities)

    # ------------------------------------------------------------------
    # Exploration
    # ------------------------------------------------------------------

    @staticmethod
    def _explore_or_exploit(scores: list[ModelScore], exploration_rate: float) -> ModelScore:
        """Epsilon-greedy: exploit top model or explore top-3."""
        if len(scores) == 1 or secrets.SystemRandom().random() > exploration_rate:
            return scores[0]
        # Explore: pick randomly from top 3
        top_k = scores[: min(3, len(scores))]
        return secrets.choice(top_k)
