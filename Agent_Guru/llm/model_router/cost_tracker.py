"""
Module: Agent_Guru.llm.model_router.cost_tracker
Purpose: Tracks and aggregates model usage costs with budget alerting.

Uses bounded deques for memory-safe time-series storage.
"""
from __future__ import annotations

import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional

import structlog

from Agent_Guru.llm.model_router.models import (
    CostRecord,
    CostSummary,
    TaskType,
)

logger = structlog.get_logger("model_router.cost_tracker")

_MAX_RECORDS = 10_000  # Bounded memory


class BudgetAlert:
    """Represents a triggered budget alert."""

    def __init__(self, threshold: float, current_spend: float,
                 period: str, triggered_at: datetime) -> None:
        self.threshold = threshold
        self.current_spend = current_spend
        self.period = period
        self.triggered_at = triggered_at

    def __repr__(self) -> str:
        return (f"BudgetAlert(threshold={self.threshold}, "
                f"current={self.current_spend:.4f}, period={self.period})")


class CostTracker:
    """Records and aggregates LLM usage costs with budget alerting.

    Args:
        max_records: Maximum number of cost records to retain (bounded memory).
        budget_threshold: Optional total spend threshold for alerts.
    """

    def __init__(self, max_records: int = _MAX_RECORDS,
                 budget_threshold: Optional[float] = None) -> None:
        self._records: Deque[CostRecord] = deque(maxlen=max_records)
        self._lock = threading.RLock()
        self._budget_threshold = budget_threshold

    def record_cost(self, model_id: str, task_type: TaskType,
                    input_tokens: int, output_tokens: int,
                    cost_per_input: float, cost_per_output: float) -> CostRecord:
        """Record cost for a completed task.

        Args:
            model_id: Model that was used.
            task_type: Type of task performed.
            input_tokens: Number of input tokens consumed.
            output_tokens: Number of output tokens generated.
            cost_per_input: Cost per input token.
            cost_per_output: Cost per output token.

        Returns:
            The created CostRecord.
        """
        cost = (input_tokens * cost_per_input) + (output_tokens * cost_per_output)
        record = CostRecord(
            record_id=str(uuid.uuid4()),
            model_id=model_id,
            task_type=task_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            timestamp=datetime.now(timezone.utc),
        )
        with self._lock:
            self._records.append(record)

        logger.debug("cost_recorded", model_id=model_id,
                     task_type=task_type.value, cost=cost)
        return record

    def get_summary(self, since: Optional[datetime] = None,
                    until: Optional[datetime] = None) -> CostSummary:
        """Get aggregated cost summary for a time period.

        Args:
            since: Start of period (inclusive). None = all records.
            until: End of period (inclusive). None = now.

        Returns:
            CostSummary with aggregated statistics.
        """
        now = datetime.now(timezone.utc)
        period_end = until or now
        period_start = since or datetime.min.replace(tzinfo=timezone.utc)

        with self._lock:
            records = list(self._records)

        filtered = [
            r for r in records
            if period_start <= r.timestamp <= period_end
        ]

        total = 0.0
        by_model: Dict[str, float] = {}
        by_task: Dict[str, float] = {}

        for r in filtered:
            total += r.cost
            by_model[r.model_id] = by_model.get(r.model_id, 0.0) + r.cost
            key = r.task_type.value
            by_task[key] = by_task.get(key, 0.0) + r.cost

        return CostSummary(
            total_cost=total,
            cost_by_model=by_model,
            cost_by_task_type=by_task,
            period_start=period_start,
            period_end=period_end,
            record_count=len(filtered),
        )

    def check_budget_alerts(self) -> List[BudgetAlert]:
        """Check if any budget thresholds have been exceeded.

        Returns:
            List of triggered BudgetAlert objects.
        """
        if self._budget_threshold is None:
            return []

        summary = self.get_summary()
        alerts: List[BudgetAlert] = []

        if summary.total_cost >= self._budget_threshold:
            alerts.append(BudgetAlert(
                threshold=self._budget_threshold,
                current_spend=summary.total_cost,
                period="all_time",
                triggered_at=datetime.now(timezone.utc),
            ))
            logger.warning("budget_threshold_exceeded",
                           threshold=self._budget_threshold,
                           current=summary.total_cost)

        return alerts

    def set_budget_threshold(self, threshold: float) -> None:
        """Update the budget threshold.

        Args:
            threshold: New threshold value (must be >= 0).

        Raises:
            ValueError: If threshold is negative.
        """
        if threshold < 0:
            raise ValueError(f"Budget threshold must be >= 0, got {threshold}")
        self._budget_threshold = threshold

    def calculate_savings(self, baseline_cost_per_token: float) -> float:
        """Calculate savings vs a flat baseline cost per token.

        Args:
            baseline_cost_per_token: Baseline cost applied to all tokens.

        Returns:
            Total savings (positive = saved money).
        """
        with self._lock:
            records = list(self._records)

        baseline_total = sum(
            (r.input_tokens + r.output_tokens) * baseline_cost_per_token
            for r in records
        )
        actual_total = sum(r.cost for r in records)
        return baseline_total - actual_total

    def total_records(self) -> int:
        """Return the number of stored cost records."""
        with self._lock:
            return len(self._records)
