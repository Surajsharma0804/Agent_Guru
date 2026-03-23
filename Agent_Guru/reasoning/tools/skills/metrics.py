"""
Skill metrics for tracking skill usage and performance.

Tracks execution count, success rate, and latency for each skill.
"""

import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class SkillMetrics:
    """Metrics for a skill."""

    skill_id: str
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0
    last_executed: Optional[float] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.execution_count == 0:
            return 0.0
        return self.success_count / self.execution_count

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency."""
        if self.execution_count == 0:
            return 0.0
        return self.total_latency_ms / self.execution_count

    def record_execution(self, success: bool, latency_ms: float) -> None:
        """Record a skill execution.

        Args:
            success: Whether execution succeeded
            latency_ms: Execution latency in milliseconds
        """
        self.execution_count += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

        self.total_latency_ms += latency_ms
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        self.last_executed = time.time()


class SkillMetricsTracker:
    """Tracker for skill metrics."""

    def __init__(self):
        """Initialize metrics tracker."""
        self.metrics: dict[str, SkillMetrics] = {}

    def get_metrics(self, skill_id: str) -> SkillMetrics:
        """Get metrics for a skill.

        Args:
            skill_id: Skill ID

        Returns:
            Skill metrics
        """
        if skill_id not in self.metrics:
            self.metrics[skill_id] = SkillMetrics(skill_id=skill_id)
        return self.metrics[skill_id]

    def record_execution(
        self, skill_id: str, success: bool, latency_ms: float
    ) -> None:
        """Record a skill execution.

        Args:
            skill_id: Skill ID
            success: Whether execution succeeded
            latency_ms: Execution latency in milliseconds
        """
        metrics = self.get_metrics(skill_id)
        metrics.record_execution(success, latency_ms)

    def get_all_metrics(self) -> dict[str, SkillMetrics]:
        """Get metrics for all skills.

        Returns:
            Dictionary of skill ID to metrics
        """
        return self.metrics.copy()

    def reset_metrics(self, skill_id: Optional[str] = None) -> None:
        """Reset metrics.

        Args:
            skill_id: Skill ID to reset, or None to reset all
        """
        if skill_id:
            if skill_id in self.metrics:
                del self.metrics[skill_id]
        else:
            self.metrics.clear()


# Global metrics tracker instance
_global_tracker = SkillMetricsTracker()


def get_metrics_tracker() -> SkillMetricsTracker:
    """Get the global metrics tracker instance.

    Returns:
        Global SkillMetricsTracker instance
    """
    return _global_tracker
