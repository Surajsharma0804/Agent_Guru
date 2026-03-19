"""
Module: Agent_Guru.llm.model_router.performance_monitor
Purpose: Tracks model performance metrics for learning and analysis.

Uses bounded deques for memory-safe rolling window calculations.
"""
from __future__ import annotations

import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional, Tuple

import structlog

from Agent_Guru.llm.model_router.models import (
    PerformanceMetrics,
    PerformanceRecord,
    TaskType,
)

logger = structlog.get_logger("model_router.performance_monitor")

_WINDOW_SIZE = 100  # Rolling window for success rate
_EMA_DECAY = 0.9    # Exponential moving average decay for latency


class PerformanceMonitor:
    """Tracks model performance with bounded memory usage.

    Uses rolling windows (deque with maxlen) to prevent unbounded growth.

    Args:
        window_size: Number of recent records to keep per model+task_type pair.
    """

    def __init__(self, window_size: int = _WINDOW_SIZE) -> None:
        self._window_size = window_size
        # (model_id, task_type) → deque of (success, latency_ms, quality)
        self._records: Dict[Tuple[str, str], Deque[Tuple[bool, float, float]]] = {}
        # (model_id, task_type) → EMA latency
        self._ema_latency: Dict[Tuple[str, str], float] = {}
        self._lock = threading.RLock()

    def record(self, record: PerformanceRecord) -> None:
        """Record a performance observation.

        Args:
            record: Performance record to store.
        """
        key = (record.model_id, record.task_type.value)
        quality = record.quality_score if record.quality_score is not None else 0.5

        with self._lock:
            if key not in self._records:
                self._records[key] = deque(maxlen=self._window_size)
                self._ema_latency[key] = record.latency_ms

            self._records[key].append((record.success, record.latency_ms, quality))

            # Update EMA latency
            old_ema = self._ema_latency[key]
            self._ema_latency[key] = (
                _EMA_DECAY * old_ema + (1 - _EMA_DECAY) * record.latency_ms
            )

        logger.debug("performance_recorded",
                     model_id=record.model_id,
                     task_type=record.task_type.value,
                     success=record.success,
                     latency_ms=record.latency_ms)

    def get_metrics(self, model_id: str, task_type: TaskType) -> PerformanceMetrics:
        """Get aggregated performance metrics for a model+task_type pair.

        Args:
            model_id: Model identifier.
            task_type: Task type.

        Returns:
            PerformanceMetrics with aggregated statistics.
        """
        key = (model_id, task_type.value)

        with self._lock:
            records = list(self._records.get(key, []))
            ema_latency = self._ema_latency.get(key, 0.0)

        if not records:
            return PerformanceMetrics(
                model_id=model_id,
                task_type=task_type,
                success_rate=0.0,
                average_latency_ms=0.0,
                average_quality=0.5,
                sample_size=0,
            )

        successes = sum(1 for s, _, _ in records if s)
        avg_quality = sum(q for _, _, q in records) / len(records)

        return PerformanceMetrics(
            model_id=model_id,
            task_type=task_type,
            success_rate=successes / len(records),
            average_latency_ms=ema_latency,
            average_quality=avg_quality,
            sample_size=len(records),
        )

    def detect_degradation(self, model_id: str, task_type: TaskType,
                           threshold: float = 0.7) -> bool:
        """Detect if a model's performance has degraded below threshold.

        Args:
            model_id: Model identifier.
            task_type: Task type.
            threshold: Success rate below which degradation is flagged.

        Returns:
            True if performance has degraded.
        """
        metrics = self.get_metrics(model_id, task_type)
        if metrics.sample_size < 5:
            return False  # Not enough data
        return metrics.success_rate < threshold

    def compare_models(self, model_ids: List[str],
                       task_type: TaskType) -> List[PerformanceMetrics]:
        """Compare performance metrics across multiple models.

        Args:
            model_ids: List of model IDs to compare.
            task_type: Task type to compare on.

        Returns:
            List of PerformanceMetrics sorted by success_rate descending.
        """
        metrics = [self.get_metrics(mid, task_type) for mid in model_ids]
        return sorted(metrics, key=lambda m: m.success_rate, reverse=True)
