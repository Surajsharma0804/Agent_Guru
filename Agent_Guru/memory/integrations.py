"""Integration interfaces for Goal Manager, Self-Improvement Engine, and Model Router.

Each integration provides context from the memory system to the requesting component
and stores outcomes back into memory.

Properties validated:
  35: Complete Context Provision
  36: Success-Prioritized Experience Return
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from Agent_Guru.memory.experience_repository import ExperienceRepository
from Agent_Guru.memory.knowledge_graph import KnowledgeGraph
from Agent_Guru.memory.models import (
    CausalLink,
    Entity,
    Experience,
    ExperienceQuery,
    Preference,
    TimeRange,
)
from Agent_Guru.memory.preference_engine import PreferenceLearningEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared context data classes (plain dicts for simplicity; typed below)
# ---------------------------------------------------------------------------


class GoalContext:
    """Context provided to the Goal Manager."""

    def __init__(
        self,
        relevant_experiences: list[Experience],
        relevant_knowledge: list[Entity],
        learned_preferences: list[Preference],
        success_factors: list[CausalLink],
    ) -> None:
        self.relevant_experiences = relevant_experiences
        self.relevant_knowledge = relevant_knowledge
        self.learned_preferences = learned_preferences
        self.success_factors = success_factors


class PerformanceData:
    """Performance data provided to the Self-Improvement Engine."""

    def __init__(
        self,
        success_rate_by_task_type: dict[str, float],
        failure_patterns: list[Any],
        metric_trends: dict[str, Any],
    ) -> None:
        self.success_rate_by_task_type = success_rate_by_task_type
        self.failure_patterns = failure_patterns
        self.metric_trends = metric_trends


class ClassificationContext:
    """Context provided to the Model Router."""

    def __init__(
        self,
        similar_tasks: list[Experience],
        model_performance_history: dict[str, float],
        task_characteristics: dict[str, Any],
    ) -> None:
        self.similar_tasks = similar_tasks
        self.model_performance_history = model_performance_history
        self.task_characteristics = task_characteristics


# ---------------------------------------------------------------------------
# Goal Manager Integration
# ---------------------------------------------------------------------------


class GoalManagerIntegration:
    """Provides memory context to the Goal Manager component."""

    def __init__(
        self,
        experience_repo: ExperienceRepository,
        knowledge_graph: KnowledgeGraph,
        preference_engine: PreferenceLearningEngine,
    ) -> None:
        self._experiences = experience_repo
        self._kg = knowledge_graph
        self._prefs = preference_engine
        # goal_id -> outcome dict
        self._goal_outcomes: dict[UUID, dict[str, Any]] = {}

    async def provide_goal_context(
        self,
        goal_task_type: str,
        user_id: UUID | None = None,
        max_experiences: int = 10,
    ) -> GoalContext:
        """Return experiences, knowledge, preferences, and success factors for a goal."""
        # Get similar successful experiences, ranked by success score
        reference = Experience(task_type=goal_task_type)
        query = ExperienceQuery(
            task_type=goal_task_type,
            similarity_threshold=0.0,
            min_success_score=0.5,
            max_results=max_experiences,
            include_failures=False,
        )
        experiences = self._experiences.query_similar_experiences(query, reference)
        # Sort by success score descending (Property 36)
        experiences.sort(key=lambda e: e.success_score, reverse=True)

        # Get all entities from knowledge graph
        from Agent_Guru.memory.models import SemanticQuery
        kg_result = await self._kg.query_semantic(SemanticQuery(max_depth=2))
        knowledge = kg_result.entities

        # Get user preferences if user_id provided
        preferences: list[Preference] = []
        if user_id is not None:
            preferences = self._prefs.get_user_preferences(user_id)

        # Collect success factors from top experiences
        success_factors: list[CausalLink] = []
        for exp in experiences[:3]:
            success_factors.extend(self._experiences.get_success_factors(exp.id))

        return GoalContext(
            relevant_experiences=experiences,
            relevant_knowledge=knowledge,
            learned_preferences=preferences,
            success_factors=success_factors,
        )

    def store_goal_outcome(self, goal_id: UUID, outcome: dict[str, Any]) -> None:
        """Store the outcome of a completed goal."""
        self._goal_outcomes[goal_id] = {**outcome, "stored_at": datetime.now(tz=timezone.utc).isoformat()}
        logger.debug("Stored goal outcome for %s", goal_id)

    def identify_knowledge_gaps(self, goal_task_type: str) -> list[str]:
        """Identify what knowledge is missing for a goal type."""
        experiences = self._experiences.get_experiences_by_time(task_type=goal_task_type)
        if not experiences:
            return [f"No experiences found for task type: {goal_task_type}"]
        gaps: list[str] = []
        # Flag task types with low success rates
        success_rate = sum(1 for e in experiences if e.success) / len(experiences)
        if success_rate < 0.5:
            gaps.append(f"Low success rate ({success_rate:.0%}) for {goal_task_type}")
        return gaps


# ---------------------------------------------------------------------------
# Self-Improvement Engine Integration
# ---------------------------------------------------------------------------


class SelfImprovementIntegration:
    """Provides performance data to the Self-Improvement Engine."""

    def __init__(self, experience_repo: ExperienceRepository) -> None:
        self._experiences = experience_repo
        # improvement_id -> outcome
        self._improvement_outcomes: dict[UUID, dict[str, Any]] = {}

    def provide_performance_data(self, time_range: TimeRange | None = None) -> PerformanceData:
        """Aggregate success rates and failure patterns across task types."""
        all_exps = list(self._experiences._experiences.values())
        if time_range:
            all_exps = [
                e for e in all_exps
                if time_range.start <= e.start_time <= time_range.end
            ]

        # Group by task type
        by_type: dict[str, list[Experience]] = {}
        for exp in all_exps:
            by_type.setdefault(exp.task_type, []).append(exp)

        success_rates: dict[str, float] = {}
        for task_type, exps in by_type.items():
            success_rates[task_type] = sum(1 for e in exps if e.success) / len(exps)

        # Identify failure patterns
        failure_exps = [e for e in all_exps if not e.success]
        patterns = self._experiences.identify_patterns(failure_exps)

        return PerformanceData(
            success_rate_by_task_type=success_rates,
            failure_patterns=patterns,
            metric_trends={},
        )

    def identify_improvement_opportunities(self) -> list[dict[str, Any]]:
        """Find task types with below-average success rates."""
        data = self.provide_performance_data()
        if not data.success_rate_by_task_type:
            return []
        avg = sum(data.success_rate_by_task_type.values()) / len(data.success_rate_by_task_type)
        return [
            {"task_type": tt, "success_rate": rate, "gap": avg - rate}
            for tt, rate in data.success_rate_by_task_type.items()
            if rate < avg
        ]

    def store_improvement_outcome(
        self, improvement_id: UUID, outcome: dict[str, Any]
    ) -> None:
        self._improvement_outcomes[improvement_id] = {
            **outcome,
            "stored_at": datetime.now(tz=timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# Model Router Integration
# ---------------------------------------------------------------------------


class ModelRouterIntegration:
    """Provides task classification context to the Model Router."""

    def __init__(self, experience_repo: ExperienceRepository) -> None:
        self._experiences = experience_repo
        # task_id -> {model: str, performance: float}
        self._model_performance: dict[str, list[dict[str, Any]]] = {}

    def provide_task_classification_context(
        self, task_type: str, max_similar: int = 5
    ) -> ClassificationContext:
        """Return similar past tasks and model performance history."""
        reference = Experience(task_type=task_type)
        query = ExperienceQuery(
            task_type=task_type,
            similarity_threshold=0.0,
            max_results=max_similar,
            include_failures=True,
        )
        similar = self._experiences.query_similar_experiences(query, reference)
        # Sort by success score (Property 36)
        similar.sort(key=lambda e: e.success_score, reverse=True)

        # Aggregate model performance
        model_perf: dict[str, float] = {}
        for model, records in self._model_performance.items():
            if records:
                model_perf[model] = sum(r["performance"] for r in records) / len(records)

        return ClassificationContext(
            similar_tasks=similar,
            model_performance_history=model_perf,
            task_characteristics={"task_type": task_type, "sample_count": len(similar)},
        )

    def store_model_performance(
        self, task_id: UUID, model: str, performance: float
    ) -> None:
        """Record how well a model performed on a task."""
        if model not in self._model_performance:
            self._model_performance[model] = []
        self._model_performance[model].append(
            {"task_id": str(task_id), "performance": performance, "timestamp": datetime.now(tz=timezone.utc).isoformat()}
        )
