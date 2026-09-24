"""Performance Tracker - Tracks agent performance metrics using sliding window.

Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5
"""

import statistics
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from .agent_lifecycle import PerformanceRecord

if TYPE_CHECKING:
    from .agent_storage import AgentStorage


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics for an agent on a task type."""

    agent_id: str
    task_type: str
    success_rate: float
    average_completion_time_ms: float
    average_resource_usage: dict[str, float]
    sample_size: int
    last_updated: datetime


class PerformanceTracker:
    """Tracks agent performance metrics using a sliding window.

    Uses the most recent `window_size` records to compute metrics,
    emphasizing recent performance over historical data.

    Time Complexity: O(w) per metrics query, where w = window_size
    Space Complexity: O(1) - delegates storage to AgentStorage

    Example:
        >>> tracker = PerformanceTracker(storage, window_size=100)
        >>> await tracker.record_performance("agent-1", "task-1", "analysis", True, 250.0, {})
        >>> metrics = await tracker.get_metrics("agent-1", "analysis")
        >>> print(metrics.success_rate)

    Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5

    """

    def __init__(self, storage: "AgentStorage", window_size: int = 100) -> None:
        self.storage = storage
        self.window_size = window_size

    async def record_performance(
        self,
        agent_id: str,
        task_id: str,
        task_type: str,
        success: bool,
        completion_time_ms: float,
        resource_usage: dict[str, float],
    ) -> None:
        """Record agent performance on a task.

        Persists the record and updates agent task statistics.

        Time Complexity: O(1)
        Validates: Requirements 12.1, 12.5
        """
        record = PerformanceRecord(
            task_id=task_id,
            task_type=task_type,
            success=success,
            completion_time_ms=completion_time_ms,
            resource_usage=resource_usage,
            timestamp=datetime.now(tz=UTC),
        )
        await self.storage.store_performance_record(agent_id, record)

        # Update agent task counters
        agent = await self.storage.get_agent(agent_id)
        if agent:
            agent.total_tasks += 1
            if success:
                agent.successful_tasks += 1
            agent.last_active = datetime.now(tz=UTC)
            await self.storage.update_agent(agent)

    async def get_metrics(self, agent_id: str, task_type: str) -> PerformanceMetrics:
        """Get performance metrics for an agent on a task type.

        Uses the most recent `window_size` records (sliding window).

        Time Complexity: O(w) where w = window_size
        Validates: Requirements 12.2, 12.3
        """
        records = await self.storage.get_performance_records(
            agent_id=agent_id,
            task_type=task_type,
            limit=self.window_size,
        )

        if not records:
            return PerformanceMetrics(
                agent_id=agent_id,
                task_type=task_type,
                success_rate=0.0,
                average_completion_time_ms=0.0,
                average_resource_usage={},
                sample_size=0,
                last_updated=datetime.now(tz=UTC),
            )

        success_rate = sum(1 for r in records if r.success) / len(records)
        avg_time = statistics.mean(r.completion_time_ms for r in records)

        # BUG FIX: was `if records[0].resource_usage: for key in
        # records[0].resource_usage:` -- only averaged keys present in
        # the single most recent record, silently dropping any
        # resource key that OTHER records in the window reported but
        # the most recent one happened not to. Union the keys across
        # the whole window instead, so a key reported by any record in
        # the window is included in the average (still defaulting to
        # 0.0 for records missing that specific key, same as before).
        resource_keys: set[str] = set()
        for r in records:
            resource_keys.update(r.resource_usage)

        avg_resources: dict[str, float] = {}
        for key in resource_keys:
            avg_resources[key] = statistics.mean(
                r.resource_usage.get(key, 0.0) for r in records
            )

        return PerformanceMetrics(
            agent_id=agent_id,
            task_type=task_type,
            success_rate=success_rate,
            average_completion_time_ms=avg_time,
            average_resource_usage=avg_resources,
            sample_size=len(records),
            last_updated=datetime.now(tz=UTC),
        )

    async def compare_agents(
        self,
        agent_ids: list[str],
        task_type: str,
    ) -> list[PerformanceMetrics]:
        """Compare multiple agents on a task type, sorted by success rate descending.

        Time Complexity: O(n * w) where n = agents, w = window_size
        Validates: Requirement 12.4
        """
        metrics = [await self.get_metrics(aid, task_type) for aid in agent_ids]
        metrics.sort(key=lambda m: m.success_rate, reverse=True)
        return metrics

    async def detect_performance_degradation(
        self,
        agent_id: str,
        task_type: str,
        threshold: float = 0.2,
    ) -> bool:
        """Detect if an agent's performance has degraded significantly.

        Splits the last 2*window_size records into old and recent halves
        and compares success rates. Returns True if the drop >= threshold.

        Time Complexity: O(w)
        Validates: Requirement 12.4
        """
        records = await self.storage.get_performance_records(
            agent_id=agent_id,
            task_type=task_type,
            limit=self.window_size * 2,
        )

        if len(records) < self.window_size:
            return False

        mid = len(records) // 2
        # storage returns most-recent-first; old = tail, recent = head
        recent = records[:mid]
        old = records[mid:]

        old_rate = sum(1 for r in old if r.success) / len(old)
        recent_rate = sum(1 for r in recent if r.success) / len(recent)

        return (old_rate - recent_rate) >= threshold
