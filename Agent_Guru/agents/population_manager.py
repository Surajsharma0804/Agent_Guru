"""Population Manager - Maintains optimal agent population size.

Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .agent_lifecycle import AgentStatus

if TYPE_CHECKING:
    from .agent_merger import AgentMerger
    from .agent_storage import AgentStorage

logger = logging.getLogger(__name__)


@dataclass
class PopulationSnapshot:
    """Point-in-time snapshot of agent population."""

    timestamp: datetime
    total_agents: int
    active_agents: int
    recommendations: list[str] = field(default_factory=list)


class PopulationManager:
    """Maintains optimal agent population size.

    Triggers aggressive merging when population exceeds max_agents,
    and becomes conservative with retirement when below min_agents.

    Time Complexity: O(n) for evaluation, where n = active agents
    Space Complexity: O(h) where h = history length

    Example:
        >>> pm = PopulationManager(storage, merger, min_agents=5, max_agents=50)
        >>> result = await pm.evaluate_population_size()
        >>> print(result["status"])

    Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5

    """

    def __init__(
        self,
        storage: "AgentStorage",
        merger: "AgentMerger",
        min_agents: int = 5,
        max_agents: int = 50,
    ) -> None:
        self.storage = storage
        self.merger = merger
        self.min_agents = min_agents
        self.max_agents = max_agents
        self._history: list[PopulationSnapshot] = []

    async def evaluate_population_size(
        self,
        task_diversity: int = 1,
        workload_volume: int = 1,
    ) -> dict[str, Any]:
        """Evaluate current population and return status with recommendations.

        Considers task_diversity and workload_volume when assessing optimality.

        Args:
            task_diversity: Number of distinct task types in current workload
            workload_volume: Current number of pending tasks

        Returns:
            Dict with keys: status, active_count, recommendations

        Time Complexity: O(n)
        Validates: Requirements 13.1, 13.2, 13.3, 13.4

        """
        active = await self.storage.query_agents(status=AgentStatus.ACTIVE)
        count = len(active)

        # Adjust thresholds based on workload
        effective_max = self.max_agents + max(0, task_diversity - 1) * 5
        effective_min = max(1, self.min_agents - max(0, workload_volume - 1))

        recommendations: list[str] = []

        if count > effective_max:
            status = "overpopulated"
            recommendations.append(
                f"Population {count} exceeds max {effective_max}. Trigger aggressive merging.",
            )
        elif count < effective_min:
            status = "underpopulated"
            recommendations.append(
                f"Population {count} below min {effective_min}. Be conservative with retirement.",
            )
        else:
            status = "optimal"

        if recommendations:
            logger.info("Population suboptimal: %s", "; ".join(recommendations))

        snapshot = PopulationSnapshot(
            timestamp=datetime.now(tz=UTC),
            total_agents=len(await self.storage.query_agents()),
            active_agents=count,
            recommendations=recommendations,
        )
        self._history.append(snapshot)

        return {
            "status": status,
            "active_count": count,
            "recommendations": recommendations,
        }

    async def trigger_aggressive_merging(self) -> int:
        """Trigger aggressive merging to reduce population.

        Returns:
            Number of merge operations performed

        Validates: Requirement 13.1

        """
        candidates = await self.merger.detect_merge_candidates()
        count = 0
        merged_ids: set[str] = set()
        for agent_a_id, agent_b_id, _similarity in candidates:
            # Skip if either agent was already merged in this pass
            if agent_a_id in merged_ids or agent_b_id in merged_ids:
                continue
            try:
                await self.merger.merge_agents(agent_a_id, agent_b_id)
                merged_ids.add(agent_a_id)
                merged_ids.add(agent_b_id)
                count += 1
            except (ValueError, Exception):
                logger.exception("Merge failed for %s + %s", agent_a_id, agent_b_id)
        return count

    def adjust_retirement_threshold(self, base_threshold: float) -> float:
        """Adjust retirement threshold based on population size.

        When underpopulated, raises the threshold (harder to retire).
        When overpopulated, lowers the threshold (easier to retire).

        Args:
            base_threshold: Base success rate threshold for retirement

        Returns:
            Adjusted threshold

        Validates: Requirement 13.2

        """
        if not self._history:
            return base_threshold

        last = self._history[-1]
        if last.active_agents < self.min_agents:
            # Conservative: raise threshold so fewer agents get retired
            return min(1.0, base_threshold + 0.1)
        if last.active_agents > self.max_agents:
            # Aggressive: lower threshold so more agents get retired
            return max(0.0, base_threshold - 0.1)
        return base_threshold

    def track_population_trends(self) -> dict[str, Any]:
        """Return population trend data for reporting.

        Validates: Requirement 13.5
        """
        if not self._history:
            return {"trend": "unknown", "snapshots": 0}

        counts = [s.active_agents for s in self._history]
        if len(counts) < 2:
            return {"trend": "stable", "snapshots": len(counts), "current": counts[-1]}

        delta = counts[-1] - counts[0]
        trend = "growing" if delta > 0 else ("shrinking" if delta < 0 else "stable")
        return {
            "trend": trend,
            "snapshots": len(counts),
            "current": counts[-1],
            "delta": delta,
        }
