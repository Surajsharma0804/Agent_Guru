"""Task Assigner - Assigns tasks to optimal agents based on specialization.

Implements specialization-based assignment with workload balancing.
When no suitable agent exists, a new one is created on-demand.

Performance Characteristics:
    - Time Complexity: O(n) where n is number of active agents
    - Space Complexity: O(n) for workload tracking
    - Latency: <50ms for 1000 agents

Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent_lifecycle import Agent, AgentLifecycleManager
    from .agent_storage import AgentStorage
    from .specialization_tracker import SpecializationTracker
    from .task_decomposer import Task


class TaskAssigner:
    """Assigns tasks to the most suitable active agent.

    Selection algorithm:
    1. Score every active agent: 70 % specialization + 30 % workload headroom.
    2. Pick the highest-scoring agent that still has capacity.
    3. If no agent has capacity (or no agents exist), create a new one.

    Workload is tracked in-memory; call ``task_completed`` when a task
    finishes so the slot is freed.

    Time Complexity: O(n) per assignment where n is active agent count
    Space Complexity: O(n) for workload dict

    Example:
        >>> assigner = TaskAssigner(storage, spec_tracker, lifecycle_manager)
        >>> agent_id = await assigner.assign_task(task)

    Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5

    """

    def __init__(
        self,
        storage: AgentStorage,
        specialization_tracker: SpecializationTracker,
        lifecycle_manager: AgentLifecycleManager,
        max_workload_per_agent: int = 5,
    ) -> None:
        """Initialise the task assigner.

        Args:
            storage: Agent storage backend.
            specialization_tracker: Tracker for specialization scores.
            lifecycle_manager: Used to create new agents on demand.
            max_workload_per_agent: Maximum concurrent tasks per agent.

        Raises:
            ValueError: If max_workload_per_agent < 1.

        Validates: Requirements 7.3, 7.5

        """
        if max_workload_per_agent < 1:
            msg = "max_workload_per_agent must be >= 1"
            raise ValueError(msg)

        self.storage = storage
        self.specialization_tracker = specialization_tracker
        self.lifecycle_manager = lifecycle_manager
        self.max_workload = max_workload_per_agent
        # agent_id -> current active task count
        self._workloads: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def assign_task(self, task: Task, exclude_agent_id: str | None = None) -> str:
        """Assign a task to the best available agent.

        Args:
            task: Task to assign.
            exclude_agent_id: Agent ID to exclude from selection (e.g. the delegating agent).

        Returns:
            ID of the agent assigned to the task.

        Time Complexity: O(n) where n is active agent count
        Performance Target: <50ms for 1000 agents

        Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5

        """
        agents = await self.storage.get_active_agents()

        # Score and sort agents, excluding the specified agent
        scored: list[tuple[str, float]] = [
            (agent.id, self._score_agent_for_task(agent, task))
            for agent in agents
            if agent.id != exclude_agent_id
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Pick highest-scoring agent with capacity
        selected_id: str | None = None
        for agent_id, _score in scored:
            if self._has_capacity(agent_id):
                selected_id = agent_id
                break

        # No suitable agent – create one on demand
        if selected_id is None:
            new_agent = await self.lifecycle_manager.create_agent(
                task_requirements=task.requirements,
                initial_capabilities={task.task_type: 0.5},
            )
            selected_id = new_agent.id

        # Update workload
        self._workloads[selected_id] = self._workloads.get(selected_id, 0) + 1

        # Persist assignment
        await self.storage.record_task_assignment(
            task_id=task.id,
            agent_id=selected_id,
            timestamp=datetime.now(tz=UTC),
        )

        return selected_id

    async def task_completed(self, agent_id: str) -> None:
        """Decrement workload counter when a task finishes.

        Args:
            agent_id: Agent that completed the task.

        Time Complexity: O(1)
        Validates: Requirement 7.3

        """
        if agent_id in self._workloads:
            self._workloads[agent_id] = max(0, self._workloads[agent_id] - 1)

    def get_workload(self, agent_id: str) -> int:
        """Return current workload for an agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            Number of active tasks assigned to the agent.

        """
        return self._workloads.get(agent_id, 0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _score_agent_for_task(self, agent: Agent, task: Task) -> float:
        """Score an agent for a given task.

        Score = 0.7 * specialization_score + 0.3 * workload_headroom

        Args:
            agent: Candidate agent.
            task: Task to score against.

        Returns:
            Score in [0.0, 1.0].

        Time Complexity: O(1)
        Validates: Requirements 7.1, 7.2, 7.3

        """
        spec_score = agent.specializations.get(task.task_type, 0.0)

        current_workload = self._workloads.get(agent.id, 0)
        workload_headroom = max(0.0, 1.0 - current_workload / self.max_workload)

        return 0.7 * spec_score + 0.3 * workload_headroom

    def _has_capacity(self, agent_id: str) -> bool:
        """Return True if the agent can accept another task.

        Args:
            agent_id: Agent identifier.

        Returns:
            True if current workload < max_workload.

        Time Complexity: O(1)
        Validates: Requirement 7.3

        """
        return self._workloads.get(agent_id, 0) < self.max_workload
