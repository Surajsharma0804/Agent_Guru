"""
Convergence Analyzer - Tracks specialization convergence and system improvement.

Validates: Requirements 21.1, 21.2, 21.3, 21.4
"""

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .agent_storage import AgentStorage
    from .performance_tracker import PerformanceTracker


@dataclass
class ConvergenceMetrics:
    """Snapshot of convergence state at a point in time."""

    timestamp: datetime
    task_type: str
    success_rate: float
    specialization_variance: float
    reassignment_count: int


class ConvergenceAnalyzer:
    """
    Analyzes whether agent specializations are converging toward optimal assignment.

    Tracks success rates over time, specialization variance, and reassignment
    frequency to determine if the system is improving.

    Time Complexity: O(n) per analysis, where n = active agents
    Space Complexity: O(h) where h = history length

    Example:
        >>> analyzer = ConvergenceAnalyzer(storage, tracker)
        >>> await analyzer.track_success_rates_over_time("analysis", 0.8)
        >>> stable = await analyzer.detect_population_stability()

    Validates: Requirements 21.1, 21.2, 21.3, 21.4
    """

    def __init__(
        self,
        storage: "AgentStorage",
        tracker: "PerformanceTracker",
        stability_window: int = 5,
        stability_threshold: float = 0.05,
    ) -> None:
        self.storage = storage
        self.tracker = tracker
        self.stability_window = stability_window
        self.stability_threshold = stability_threshold
        self._history: dict[str, list[ConvergenceMetrics]] = {}
        self._reassignment_counts: dict[str, int] = {}

    async def track_success_rates_over_time(
        self, task_type: str, current_success_rate: float
    ) -> None:
        """
        Record a success rate snapshot for a task type.

        Validates: Requirement 21.1
        """
        agents = await self.storage.query_agents()
        variance = self.calculate_specialization_variance(agents, task_type)

        snapshot = ConvergenceMetrics(
            timestamp=datetime.now(),
            task_type=task_type,
            success_rate=current_success_rate,
            specialization_variance=variance,
            reassignment_count=self._reassignment_counts.get(task_type, 0),
        )
        self._history.setdefault(task_type, []).append(snapshot)

    def calculate_specialization_variance(self, agents: list, task_type: str) -> float:
        """
        Calculate variance of specialization scores across agents for a task type.

        Returns 0.0 if fewer than 2 agents have a score for this task type.

        Validates: Requirement 21.2
        """
        scores = [
            a.specializations.get(task_type, 0.0)
            for a in agents
            if task_type in a.specializations
        ]
        if len(scores) < 2:
            return 0.0
        return statistics.variance(scores)

    def measure_reassignment_frequency(self, task_type: str) -> int:
        """
        Return the recorded reassignment count for a task type.

        Validates: Requirement 21.3
        """
        return self._reassignment_counts.get(task_type, 0)

    def record_reassignment(self, task_type: str) -> None:
        """Increment reassignment counter for a task type."""
        self._reassignment_counts[task_type] = self._reassignment_counts.get(task_type, 0) + 1

    async def detect_population_stability(self) -> bool:
        """
        Detect if the system has reached a stable convergence state.

        Stability is defined as: for all tracked task types with enough history,
        the variance of recent success rates is below stability_threshold.

        Validates: Requirement 21.4
        """
        if not self._history:
            return False

        for _task_type, snapshots in self._history.items():
            if len(snapshots) < self.stability_window:
                return False
            recent_rates = [s.success_rate for s in snapshots[-self.stability_window :]]
            if statistics.variance(recent_rates) > self.stability_threshold:
                return False

        return True

    def get_convergence_report(self) -> dict[str, Any]:
        """
        Return convergence metrics for reporting to Self-Improvement Engine.

        Validates: Requirement 21.5
        """
        report: dict[str, Any] = {}
        for task_type, snapshots in self._history.items():
            if not snapshots:
                continue
            rates = [s.success_rate for s in snapshots]
            report[task_type] = {
                "snapshots": len(snapshots),
                "latest_success_rate": rates[-1],
                "improving": len(rates) >= 2 and rates[-1] > rates[0],
                "latest_variance": snapshots[-1].specialization_variance,
                "reassignments": self._reassignment_counts.get(task_type, 0),
            }
        return report
