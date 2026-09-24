"""Agent Lifecycle Manager - Manages agent creation, retirement, and lifecycle transitions.

This module handles the complete lifecycle of agents in the orchestration system,
from creation through retirement, ensuring no pre-defined roles and tracking
all evolution events.

**Key Features**:
- Dynamic agent creation based on task requirements
- Forbidden role name validation
- Performance-based retirement
- Evolution event recording
- Lifecycle state management

Author: Agent Guru Team
Date: 2026-02-28
Version: 1.0.0
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .agent_storage import AgentStorage


class AgentStatus(Enum):
    """Agent lifecycle status."""

    CREATED = "created"
    ACTIVE = "active"
    SPECIALIZING = "specializing"
    MERGING = "merging"
    SPLITTING = "splitting"
    RETIRING = "retiring"
    RETIRED = "retired"


@dataclass
class PerformanceRecord:
    """Record of agent performance on a task."""

    task_id: str
    task_type: str
    success: bool
    completion_time_ms: float
    resource_usage: dict[str, float]
    timestamp: datetime


@dataclass
class Agent:
    """An agent with capabilities and performance history.

    Agents are dynamically created entities that execute tasks and develop
    specializations based on performance patterns. They are NOT pre-defined
    roles but emerge from task requirements.

    Attributes:
        id: Unique agent identifier (UUID)
        status: Current lifecycle status
        capabilities: Capability proficiency scores (0.0-1.0)
        specializations: Task type specialization scores (0.0-1.0)
        performance_history: Historical performance records
        created_at: Agent creation timestamp
        last_active: Last activity timestamp
        total_tasks: Total number of tasks attempted
        successful_tasks: Number of successfully completed tasks
        metadata: Additional agent metadata

    Validates: Requirements 1.1, 1.2

    """

    id: str
    status: AgentStatus
    capabilities: dict[str, float]
    specializations: dict[str, float]
    performance_history: list[PerformanceRecord]
    created_at: datetime
    last_active: datetime
    total_tasks: int
    successful_tasks: int
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentLifecycleManager:
    """Manages agent creation, retirement, and lifecycle transitions.

    Enforces constraints:
    - No pre-defined role names (researcher, coder, planner, etc.)
    - Unique agent identifiers
    - Performance-based retirement
    - Complete evolution event tracking

    Time Complexity: O(1) for most operations
    Space Complexity: O(n) where n is number of agents

    Example:
        >>> manager = AgentLifecycleManager(storage)
        >>> agent = await manager.create_agent(
        ...     task_requirements={"type": "analysis"},
        ...     initial_capabilities={"data_analysis": 0.5}
        ... )
        >>> print(f"Created agent: {agent.id}")

    Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3, 5.4, 5.5

    """

    def __init__(self, storage: "AgentStorage") -> None:
        """Initialize with storage backend.

        Args:
            storage: Agent storage backend for persistence

        Time Complexity: O(1)

        Validates: Requirement 1.1

        """
        self.storage = storage

        # Forbidden role names (pre-defined roles not allowed)
        # Validates: Requirement 1.3
        self.forbidden_role_names = {
            "researcher",
            "coder",
            "planner",
            "writer",
            "analyst",
            "reviewer",
            "tester",
            "designer",
            "architect",
            "developer",
            "programmer",
            "engineer",
            "scientist",
            "manager",
            "coordinator",
        }

    async def create_agent(
        self,
        task_requirements: dict[str, Any],
        initial_capabilities: dict[str, float],
    ) -> Agent:
        """Create new agent based on task requirements.

        Creates a dynamically generated agent with capabilities matching
        the task requirements. Validates that no forbidden role names are
        used in capabilities.

        Args:
            task_requirements: Requirements that triggered creation
            initial_capabilities: Initial capability set (capability -> proficiency)

        Returns:
            Created agent with unique ID and initial state

        Raises:
            ValueError: If capabilities contain forbidden role names

        Time Complexity: O(k) where k is number of capabilities
        Space Complexity: O(1)
        Performance Target: <10ms per creation

        Example:
            >>> agent = await manager.create_agent(
            ...     task_requirements={"type": "data_processing"},
            ...     initial_capabilities={"data_processing": 0.5, "validation": 0.4}
            ... )
            >>> print(f"Agent {agent.id} created with {len(agent.capabilities)} capabilities")

        Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5

        """
        # Validate no forbidden role names
        # Validates: Requirement 1.3
        for capability in initial_capabilities:
            if capability.lower() in self.forbidden_role_names:
                msg = (
                    f"Forbidden role name '{capability}' in capabilities. "
                    f"Use task-specific capability names instead."
                )
                raise ValueError(
                    msg,
                )

        # Create agent with unique ID - start directly as ACTIVE to avoid
        # a separate UPDATE round-trip.
        # Validates: Requirements 1.1, 1.2
        agent = Agent(
            id=str(uuid.uuid4()),
            status=AgentStatus.ACTIVE,
            capabilities=initial_capabilities.copy(),
            specializations={},
            performance_history=[],
            created_at=datetime.now(tz=UTC),
            last_active=datetime.now(tz=UTC),
            total_tasks=0,
            successful_tasks=0,
            metadata={
                "created_for_task": task_requirements,
                "creation_reason": "no_suitable_agent",
            },
        )

        # Persist agent + evolution event in a single transaction.
        # Validates: Requirements 1.1, 1.4
        await self.storage.create_agent_atomic(agent, task_requirements)

        return agent

    async def retire_agent(self, agent_id: str, reason: str) -> None:
        """Retire agent due to underperformance or redundancy.

        Transitions agent through retiring state to retired, recording
        final performance metrics and evolution event. Performance history
        is preserved in storage.

        Args:
            agent_id: Agent to retire
            reason: Retirement reason (e.g., "underperformance", "merged")

        Time Complexity: O(1)
        Performance Target: <20ms per retirement

        Example:
            >>> await manager.retire_agent("agent_123", "underperformance")

        Validates: Requirements 5.1, 5.2, 5.3, 5.4

        """
        agent = await self.storage.get_agent(agent_id)
        if not agent:
            return

        # Transition to retiring
        agent.status = AgentStatus.RETIRING
        await self.storage.update_agent(agent)

        # Calculate final metrics
        success_rate = agent.successful_tasks / agent.total_tasks if agent.total_tasks > 0 else 0.0

        # Record retirement event
        # Validates: Requirement 5.3
        await self._record_evolution_event(
            event_type="retirement",
            agent_ids=[agent_id],
            reason=reason,
            details={
                "total_tasks": agent.total_tasks,
                "success_rate": success_rate,
                "final_specializations": agent.specializations,
                "retirement_timestamp": datetime.now(tz=UTC).isoformat(),
            },
        )

        # Transition to retired
        # Validates: Requirement 5.1, 5.2
        agent.status = AgentStatus.RETIRED
        await self.storage.update_agent(agent)

        # Note: Performance history is NOT deleted (Requirement 5.4)

    async def get_active_agents(self) -> list[Agent]:
        """Get all active agents.

        Returns:
            List of agents with ACTIVE status

        Time Complexity: O(n) where n is total agents
        Performance Target: <50ms for 1000 agents

        Validates: Requirement 7.5

        """
        return await self.storage.query_agents(status=AgentStatus.ACTIVE)

    async def _record_evolution_event(
        self,
        event_type: str,
        agent_ids: list[str],
        reason: str,
        details: dict[str, Any],
    ) -> None:
        """Record evolution event for GitHub sync.

        Records significant changes in agent population for version control
        and analysis. Events include creation, merge, split, and retirement.

        Args:
            event_type: Type of evolution event
            agent_ids: Agents involved in event
            reason: Reason for event
            details: Additional event details

        Time Complexity: O(1)
        Performance Target: <5ms per event

        Validates: Requirements 1.4, 3.5, 5.3, 20.1

        """
        event = {
            "event_type": event_type,
            "agent_ids": agent_ids,
            "reason": reason,
            "details": details,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
        await self.storage.store_evolution_event(event)

    # BUG FIX: public wrapper for _record_evolution_event(). That
    # method already has a real external caller (agent_merger.py's
    # merge_agents(), which reaches into it directly despite the
    # leading underscore) -- a genuine encapsulation violation, since
    # this class's own maintainers have no signal that "private"
    # method has callers outside it. Added additively rather than
    # renaming, so any other not-yet-discovered caller of the old
    # private name keeps working unchanged.
    async def record_evolution_event(
        self,
        event_type: str,
        agent_ids: list[str],
        reason: str,
        details: dict[str, Any],
    ) -> None:
        """Record an evolution event for GitHub sync (public API).

        Public entry point for external callers (e.g. AgentMerger,
        AgentSplitter) that need to record a significant change in the
        agent population -- creation, merge, split, retirement, and
        similar events. Delegates to the same implementation this
        class uses internally.

        Args:
            event_type: Type of evolution event.
            agent_ids: Agents involved in the event.
            reason: Reason for the event.
            details: Additional event details.

        """
        await self._record_evolution_event(
            event_type=event_type,
            agent_ids=agent_ids,
            reason=reason,
            details=details,
        )
