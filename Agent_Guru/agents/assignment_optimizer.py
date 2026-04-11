"""
Assignment Optimizer - Verifies task assignment optimality vs random baseline.

Validates: Requirements 24.1, 24.2, 24.3, 24.4, 24.5
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .agent_storage import AgentStorage

logger = logging.getLogger(__name__)


@dataclass
class AssignmentOutcome:
    """Record of a single task assignment outcome."""

    task_id: str
    agent_id: str
    task_type: str
    expected_probability: float
    actual_success: bool
    timestamp: datetime


class AssignmentOptimizer:
    """
    Verifies that specialization-based assignment outperforms random assignment.

    Maintains a running comparison of:
    - Specialization-based success rate (actual outcomes)
    - Random baseline success rate (0.5 by default)

    Time Complexity: O(1) per record/compare call
    Space Complexity: O(n) where n = number of recorded outcomes

    Example:
        >>> optimizer = AssignmentOptimizer(storage)
        >>> prob = await optimizer.compute_expected_success_probability("agent-1", "analysis")
        >>> await optimizer.compare_actual_to_expected("task-1", "agent-1", "analysis", prob, True)
        >>> degraded = optimizer.detect_quality_degradation()

    Validates: Requirements 24.1, 24.2, 24.3, 24.4, 24.5
    """

    def __init__(
        self,
        storage: "AgentStorage",
        baseline_success_rate: float = 0.5,
        degradation_threshold: float = 0.1,
        window_size: int = 50,
    ) -> None:
        self.storage = storage
        self.baseline_success_rate = baseline_success_rate
        self.degradation_threshold = degradation_threshold
        self.window_size = window_size
        self._outcomes: list[AssignmentOutcome] = []

    async def compute_expected_success_probability(
        self, agent_id: str, task_type: str
    ) -> float:
        """
        Compute expected success probability based on agent specialization.

        Uses the agent's specialization score for the task type as the
        probability estimate. Falls back to 0.5 if no specialization exists.

        Time Complexity: O(1)
        Validates: Requirement 24.1
        """
        agent = await self.storage.get_agent(agent_id)
        if not agent:
            return self.baseline_success_rate
        return agent.specializations.get(task_type, self.baseline_success_rate)

    async def compare_actual_to_expected(
        self,
        task_id: str,
        agent_id: str,
        task_type: str,
        expected_probability: float,
        actual_success: bool,
    ) -> dict[str, Any]:
        """
        Record actual outcome and compare to expected probability.

        Returns a dict with 'expected', 'actual', and 'deviation'.

        Time Complexity: O(1)
        Validates: Requirement 24.2
        """
        outcome = AssignmentOutcome(
            task_id=task_id,
            agent_id=agent_id,
            task_type=task_type,
            expected_probability=expected_probability,
            actual_success=actual_success,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self._outcomes.append(outcome)

        actual_val = 1.0 if actual_success else 0.0
        deviation = abs(actual_val - expected_probability)

        return {
            "expected": expected_probability,
            "actual": actual_val,
            "deviation": deviation,
        }

    def detect_quality_degradation(self) -> bool:
        """
        Detect if assignment quality has degraded vs the random baseline.

        Compares the recent window's actual success rate to the baseline.
        Returns True if specialization-based rate is worse than baseline
        by more than degradation_threshold.

        Time Complexity: O(w) where w = window_size
        Validates: Requirement 24.3
        """
        recent = self._outcomes[-self.window_size :]
        if not recent:
            return False

        actual_rate = sum(1 for o in recent if o.actual_success) / len(recent)
        return (self.baseline_success_rate - actual_rate) >= self.degradation_threshold

    def maintain_baseline_comparison(self) -> dict[str, Any]:
        """
        Return running comparison of specialization-based vs random assignment.

        Validates: Requirements 24.4, 24.5
        """
        if not self._outcomes:
            return {
                "specialization_rate": None,
                "baseline_rate": self.baseline_success_rate,
                "sample_size": 0,
                "outperforming_baseline": None,
            }

        recent = self._outcomes[-self.window_size :]
        spec_rate = sum(1 for o in recent if o.actual_success) / len(recent)

        return {
            "specialization_rate": spec_rate,
            "baseline_rate": self.baseline_success_rate,
            "sample_size": len(recent),
            "outperforming_baseline": spec_rate > self.baseline_success_rate,
        }
