"""Delegation Manager - Manages agent-to-agent task delegation with loop prevention.

Uses a directed graph (NetworkX) to track delegation chains and detect cycles.
Self-delegation and depth-limit violations are rejected immediately.

Performance Characteristics:
    - Time Complexity: O(V + E) for cycle detection
    - Space Complexity: O(V + E) for delegation graph
    - Latency: <10ms per delegation check

Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import networkx as nx

if TYPE_CHECKING:
    from datetime import datetime

    from .task_assigner import TaskAssigner
    from .task_decomposer import Task


@dataclass
class DelegationRequest:
    """A request from one agent to delegate a sub-task to another.

    Attributes:
        requesting_agent_id: Agent that wants to delegate.
        subtask: The sub-task to delegate.
        timestamp: When the request was made.

    """

    requesting_agent_id: str
    subtask: Task
    timestamp: datetime


class DelegationManager:
    """Manages agent-to-agent delegation with cycle and depth prevention.

    Maintains a directed graph of delegation edges.  Before accepting a
    delegation it checks:
    1. Self-delegation (rejected immediately).
    2. Depth limit (chain length >= max_delegation_depth → rejected).
    3. Cycle detection (adding the edge would create a cycle → rejected).

    Time Complexity: O(V + E) for cycle detection
    Space Complexity: O(V + E) for delegation graph

    Example:
        >>> manager = DelegationManager(task_assigner, max_delegation_depth=3)
        >>> request = DelegationRequest(
        ...     requesting_agent_id="agent_a",
        ...     subtask=task,
        ...     timestamp=datetime.now(tz=timezone.utc),
        ... )
        >>> assigned_id = await manager.delegate_task(request)

    Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2

    """

    def __init__(
        self,
        task_assigner: TaskAssigner,
        max_delegation_depth: int = 3,
    ) -> None:
        """Initialise the delegation manager.

        Args:
            task_assigner: Used to assign the delegated sub-task.
            max_delegation_depth: Maximum allowed delegation chain length.

        Raises:
            ValueError: If max_delegation_depth < 1.

        Validates: Requirements 10.3, 10.4

        """
        if max_delegation_depth < 1:
            msg = "max_delegation_depth must be >= 1"
            raise ValueError(msg)

        self.task_assigner = task_assigner
        self.max_depth = max_delegation_depth
        # Directed graph: edge (A → B) means A delegated to B
        self._graph: nx.DiGraph = nx.DiGraph()
        # task_id -> ordered list of agent IDs in the delegation chain
        self._chains: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def delegate_task(self, request: DelegationRequest) -> str | None:
        """Attempt to delegate a sub-task to another agent.

        Rejects delegation if:
        - The requesting agent would delegate to itself.
        - The delegation chain for this task already reached max depth.
        - Adding the delegation edge would create a cycle.

        Args:
            request: Delegation request.

        Returns:
            Assigned agent ID on success, None if delegation was rejected.

        Time Complexity: O(V + E) for cycle check
        Validates: Requirements 10.1, 10.2, 10.3, 11.1, 11.2

        """
        task_id = request.subtask.id
        requester = request.requesting_agent_id

        # Rule 1: reject self-delegation
        # Validates: Requirement 11.1
        chain = self._chains.get(task_id, [])
        if requester in chain:
            return None

        # Rule 2: depth limit
        # Validates: Requirements 10.3, 10.4
        if len(chain) >= self.max_depth:
            return None

        # Assign to best available agent (excluding the requester to prevent self-assignment)
        assigned_id = await self.task_assigner.assign_task(
            request.subtask,
            exclude_agent_id=requester,
        )

        # Rule 3: cycle detection – reject if adding requester→assigned creates cycle
        # Validates: Requirements 10.2, 11.2
        if self.would_create_cycle(requester, assigned_id):
            # Undo the workload increment from assign_task
            await self.task_assigner.task_completed(assigned_id)
            return None

        # Commit the edge
        self._graph.add_edge(requester, assigned_id, task_id=task_id)

        # Update chain
        if task_id not in self._chains:
            self._chains[task_id] = []
        self._chains[task_id].append(assigned_id)

        return assigned_id

    def would_create_cycle(self, from_agent: str, to_agent: str) -> bool:
        """Check whether adding a delegation edge would create a cycle.

        Temporarily adds the edge, checks for cycles, then removes it.

        Args:
            from_agent: Delegating agent.
            to_agent: Receiving agent.

        Returns:
            True if the edge would create a cycle.

        Time Complexity: O(V + E)
        Validates: Requirements 10.2, 11.2

        """
        if from_agent == to_agent:
            return True
        self._graph.add_edge(from_agent, to_agent)
        try:
            has_cycle = not nx.is_directed_acyclic_graph(self._graph)
        finally:
            self._graph.remove_edge(from_agent, to_agent)
        return has_cycle

    def get_delegation_chain(self, task_id: str) -> list[str]:
        """Return the ordered delegation chain for a task.

        Args:
            task_id: Task identifier.

        Returns:
            List of agent IDs in delegation order (empty if no delegation).

        Time Complexity: O(1)
        Validates: Requirement 10.5

        """
        return list(self._chains.get(task_id, []))

    def get_graph(self) -> nx.DiGraph:
        """Return a copy of the delegation graph (for inspection/testing).

        Returns:
            Copy of the internal directed graph.

        """
        return self._graph.copy()
