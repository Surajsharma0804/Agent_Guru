"""
Module: Agent_Guru.llm.model_router.router
Purpose: ModelRouter — top-level facade coordinating all sub-components.

Provides a single entry point for model selection with full observability.
"""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog

from Agent_Guru.llm.model_router.analyzer import TaskAnalyzer
from Agent_Guru.llm.model_router.cost_tracker import CostTracker
from Agent_Guru.llm.model_router.fallback_manager import FallbackManager
from Agent_Guru.llm.model_router.learning_engine import LearningEngine
from Agent_Guru.llm.model_router.models import (
    ModelFilter,
    ModelMetadata,
    PerformanceRecord,
    SelectionResult,
    TaskSpecification,
    TaskType,
)
from Agent_Guru.llm.model_router.performance_monitor import PerformanceMonitor
from Agent_Guru.llm.model_router.registry import ModelRegistry
from Agent_Guru.llm.model_router.selector import ModelSelector

logger = structlog.get_logger("model_router.router")


class ModelRouter:
    """Intelligent model router that selects optimal LLM for each task.

    Coordinates:
    - ModelRegistry: catalog of available models
    - TaskAnalyzer: extracts task requirements
    - ModelSelector: scores and selects models
    - PerformanceMonitor: tracks outcomes
    - CostTracker: records spending
    - FallbackManager: handles failures
    - LearningEngine: improves selection over time

    Args:
        registry: Model registry instance.
        budget_threshold: Optional total spend limit for alerts.
        prefer_local: Whether to prefer local (Ollama) models.
        max_registry_models: Maximum models in registry.
    """

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        budget_threshold: Optional[float] = None,
        prefer_local: bool = True,
        max_registry_models: int = 1000,
    ) -> None:
        self._registry = registry or ModelRegistry(max_models=max_registry_models)
        self._analyzer = TaskAnalyzer()
        self._selector = ModelSelector(prefer_local=prefer_local)
        self._monitor = PerformanceMonitor()
        self._cost_tracker = CostTracker(budget_threshold=budget_threshold)
        self._fallback_manager = FallbackManager()
        self._learning_engine = LearningEngine()
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def select_model(self, spec: TaskSpecification) -> SelectionResult:
        """Select the optimal model for a task specification.

        Args:
            spec: Task specification with content and constraints.

        Returns:
            SelectionResult with selected model and metadata.

        Raises:
            RuntimeError: If no suitable model can be found.
        """
        start = time.monotonic()

        # Handle explicit model override
        if spec.explicit_model_id:
            model = self._registry.get_model(spec.explicit_model_id)
            if model and model.is_available:
                return SelectionResult(
                    model_id=spec.explicit_model_id,
                    reasoning="Explicit model override",
                    estimated_cost=0.0,
                    estimated_latency_ms=model.average_latency_ms,
                    confidence=1.0,
                    fallback_models=[],
                )

        # Analyze task
        analysis = self._analyzer.analyze(spec)

        # Get candidates from registry
        model_filter = ModelFilter(
            capabilities=analysis.required_capabilities if analysis.required_capabilities else None,
            available_only=True,
        )
        candidates = self._registry.query_models(model_filter)

        if not candidates:
            raise RuntimeError(
                f"No available models found for task type '{analysis.task_type.value}'"
            )

        # Build performance map for scoring
        perf_map = {
            m.model_id: self._monitor.get_metrics(m.model_id, analysis.task_type)
            for m in candidates
        }

        # Get learning weights
        learning_weights = self._learning_engine.get_weights_for_task(analysis.task_type)

        # Get exploration rate
        exploration_rate = self._learning_engine.get_exploration_rate(analysis.task_type)

        # Select model
        result = self._selector.select(
            candidates=candidates,
            analysis=analysis,
            performance_map=perf_map,
            learning_weights=learning_weights,
            exploration_rate=exploration_rate,
        )

        if result is None:
            # Relax constraints and retry
            analysis.latency_constraint_ms = None
            analysis.cost_constraint = None
            result = self._selector.select(
                candidates=candidates,
                analysis=analysis,
                performance_map=perf_map,
                learning_weights=learning_weights,
                exploration_rate=0.0,
            )

        if result is None:
            raise RuntimeError(
                f"No model could be selected for task type '{analysis.task_type.value}' "
                "even after constraint relaxation"
            )

        # Set fallback sequence for this task type
        if result.fallback_models:
            self._fallback_manager.set_fallback_sequence(
                analysis.task_type, result.fallback_models
            )

        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info("selection_complete",
                    model_id=result.model_id,
                    task_type=analysis.task_type.value,
                    elapsed_ms=elapsed_ms)

        return result

    def record_outcome(
        self,
        model_id: str,
        task_type: TaskType,
        success: bool,
        latency_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        quality_score: Optional[float] = None,
        failure_reason: Optional[str] = None,
    ) -> None:
        """Record the outcome of a model invocation.

        Updates performance monitor, cost tracker, fallback manager,
        and learning engine.

        Args:
            model_id: Model that was used.
            task_type: Type of task performed.
            success: Whether the invocation succeeded.
            latency_ms: Observed latency in milliseconds.
            input_tokens: Input tokens consumed.
            output_tokens: Output tokens generated.
            quality_score: Optional quality score (0.0–1.0).
            failure_reason: Optional failure description.
        """
        model = self._registry.get_model(model_id)
        cost_per_input = model.cost_per_input_token if model else 0.0
        cost_per_output = model.cost_per_output_token if model else 0.0

        perf_record = PerformanceRecord(
            record_id=str(uuid.uuid4()),
            model_id=model_id,
            task_type=task_type,
            success=success,
            latency_ms=latency_ms,
            quality_score=quality_score,
            failure_reason=failure_reason,
            timestamp=datetime.now(timezone.utc),
        )

        self._monitor.record(perf_record)
        self._fallback_manager.record_outcome(model_id, success)
        self._learning_engine.update_weights(perf_record)

        if input_tokens > 0 or output_tokens > 0:
            self._cost_tracker.record_cost(
                model_id=model_id,
                task_type=task_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_per_input=cost_per_input,
                cost_per_output=cost_per_output,
            )

    # ------------------------------------------------------------------
    # Registry delegation
    # ------------------------------------------------------------------

    def register_model(self, metadata: ModelMetadata) -> None:
        """Register a model and initialize its learning weights."""
        self._registry.register_model(metadata)
        self._learning_engine.initialize_new_model(metadata.model_id)

    def mark_model_unavailable(self, model_id: str) -> bool:
        """Mark a model as unavailable."""
        return self._registry.mark_unavailable(model_id)

    def mark_model_available(self, model_id: str) -> bool:
        """Mark a model as available."""
        return self._registry.mark_available(model_id)

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    @property
    def registry(self) -> ModelRegistry:
        return self._registry

    @property
    def cost_tracker(self) -> CostTracker:
        return self._cost_tracker

    @property
    def performance_monitor(self) -> PerformanceMonitor:
        return self._monitor

    @property
    def fallback_manager(self) -> FallbackManager:
        return self._fallback_manager

    @property
    def learning_engine(self) -> LearningEngine:
        return self._learning_engine
