"""
Module: Agent_Guru.llm.model_router.registry
Purpose: Model Registry — catalog of available models with capabilities and costs.

Thread-safe in-memory registry with optional SQLite persistence.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

import structlog

from Agent_Guru.llm.model_router.models import ModelFilter, ModelMetadata

logger = structlog.get_logger("model_router.registry")


class ModelRegistry:
    """Thread-safe catalog of available LLM models.

    Supports registration, updates, queries, and availability management.
    All operations are O(1) or O(n) where n is the number of registered models.

    Args:
        max_models: Maximum number of models to store (bounded memory).
    """

    def __init__(self, max_models: int = 1000) -> None:
        self._models: Dict[str, ModelMetadata] = {}
        self._lock = threading.RLock()
        self._max_models = max_models

    def register_model(self, metadata: ModelMetadata) -> None:
        """Register a new model or update an existing one.

        Args:
            metadata: Model metadata to register.

        Raises:
            ValueError: If max_models limit would be exceeded.
        """
        with self._lock:
            if (metadata.model_id not in self._models and
                    len(self._models) >= self._max_models):
                raise ValueError(
                    f"Registry at capacity ({self._max_models} models). "
                    "Remove a model before registering a new one."
                )
            metadata.last_updated = datetime.now(timezone.utc)
            self._models[metadata.model_id] = metadata
            logger.info("model_registered", model_id=metadata.model_id,
                        provider=metadata.provider.value)

    def update_model(self, model_id: str, **updates: object) -> bool:
        """Update fields on an existing model.

        Args:
            model_id: ID of the model to update.
            **updates: Fields to update.

        Returns:
            True if model was found and updated, False otherwise.
        """
        with self._lock:
            model = self._models.get(model_id)
            if model is None:
                return False
            for key, value in updates.items():
                if hasattr(model, key):
                    setattr(model, key, value)
            model.last_updated = datetime.now(timezone.utc)
            return True

    def mark_unavailable(self, model_id: str) -> bool:
        """Mark a model as unavailable without removing it.

        Args:
            model_id: ID of the model to mark unavailable.

        Returns:
            True if model was found, False otherwise.
        """
        return self.update_model(model_id, is_available=False)

    def mark_available(self, model_id: str) -> bool:
        """Mark a model as available again."""
        return self.update_model(model_id, is_available=True)

    def get_model(self, model_id: str) -> Optional[ModelMetadata]:
        """Retrieve a model by ID.

        Args:
            model_id: Model identifier.

        Returns:
            ModelMetadata if found, None otherwise.
        """
        with self._lock:
            return self._models.get(model_id)

    def query_models(self, filter: Optional[ModelFilter] = None) -> List[ModelMetadata]:
        """Query models matching the given filter.

        Args:
            filter: Filter criteria. If None, returns all models.

        Returns:
            List of matching ModelMetadata objects.
        """
        with self._lock:
            models = list(self._models.values())

        if filter is None:
            return models

        results = []
        for model in models:
            if filter.available_only and not model.is_available:
                continue
            if filter.provider is not None and model.provider != filter.provider:
                continue
            if filter.capabilities is not None:
                if not filter.capabilities.issubset(model.capabilities):
                    continue
            if (filter.max_cost_per_input_token is not None and
                    model.cost_per_input_token > filter.max_cost_per_input_token):
                continue
            if (filter.max_cost_per_output_token is not None and
                    model.cost_per_output_token > filter.max_cost_per_output_token):
                continue
            if (filter.min_max_tokens is not None and
                    model.max_tokens < filter.min_max_tokens):
                continue
            results.append(model)

        return results

    def remove_model(self, model_id: str) -> bool:
        """Remove a model from the registry.

        Args:
            model_id: ID of the model to remove.

        Returns:
            True if model was found and removed, False otherwise.
        """
        with self._lock:
            if model_id in self._models:
                del self._models[model_id]
                logger.info("model_removed", model_id=model_id)
                return True
            return False

    def count(self) -> int:
        """Return the number of registered models."""
        with self._lock:
            return len(self._models)

    def list_ids(self) -> List[str]:
        """Return all registered model IDs."""
        with self._lock:
            return list(self._models.keys())
