"""
Adversarial Handler - Detects and handles adversarial agent behavior.

Validates: Requirements 22.1, 22.2, 22.3, 22.4, 22.5
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent_lifecycle import AgentLifecycleManager
    from .agent_storage import AgentStorage

logger = logging.getLogger(__name__)


@dataclass
class AdversarialEvent:
    """Record of an adversarial incident."""

    timestamp: datetime
    event_type: str
    agent_ids: list[str]
    details: str


class AdversarialHandler:
    """
    Detects and handles adversarial or pathological agent behavior.

    Tracks invalid output counts, resource usage, delegation counts,
    and coordinated behavior patterns to keep the system stable.

    Time Complexity: O(1) per detection call
    Space Complexity: O(n) where n = number of tracked agents

    Example:
        >>> handler = AdversarialHandler(storage, lifecycle)
        >>> quarantined = await handler.detect_invalid_outputs("agent-1", 6)
        >>> print(quarantined)  # True if threshold exceeded

    Validates: Requirements 22.1, 22.2, 22.3, 22.4, 22.5
    """

    def __init__(
        self,
        storage: "AgentStorage",
        lifecycle: "AgentLifecycleManager",
        invalid_output_threshold: int = 5,
        delegation_limit: int = 10,
    ) -> None:
        self.storage = storage
        self.lifecycle = lifecycle
        self.invalid_output_threshold = invalid_output_threshold
        self.delegation_limit = delegation_limit

        self._invalid_counts: dict[str, int] = {}
        self._quarantined: set[str] = set()
        self._delegation_counts: dict[str, int] = {}
        self._delegation_limited: set[str] = set()
        self._security_log: list[AdversarialEvent] = []

    def _log_event(self, event_type: str, agent_ids: list[str], details: str) -> None:
        event = AdversarialEvent(
            timestamp=datetime.now(tz=timezone.utc),
            event_type=event_type,
            agent_ids=agent_ids,
            details=details,
        )
        self._security_log.append(event)
        logger.warning("Adversarial event [%s] agents=%s: %s", event_type, agent_ids, details)

    async def detect_invalid_outputs(self, agent_id: str, invalid_count: int) -> bool:
        """
        Check if agent has exceeded invalid output threshold and quarantine if so.

        Args:
            agent_id: Agent to check
            invalid_count: Current invalid output count for this agent

        Returns:
            True if agent was quarantined

        Validates: Requirement 22.1
        """
        self._invalid_counts[agent_id] = invalid_count

        if invalid_count >= self.invalid_output_threshold:
            self._quarantined.add(agent_id)
            self._log_event(
                "quarantine",
                [agent_id],
                f"Invalid output count {invalid_count} >= threshold {self.invalid_output_threshold}",
            )
            return True
        return False

    def is_quarantined(self, agent_id: str) -> bool:
        """Return True if agent is quarantined (blocked from task assignments)."""
        return agent_id in self._quarantined

    async def detect_resource_exhaustion(
        self, agent_id: str, resource_usage: dict[str, float], limits: dict[str, float]
    ) -> bool:
        """
        Detect resource exhaustion and terminate offending agent.

        Args:
            agent_id: Agent to check
            resource_usage: Current resource usage dict
            limits: Maximum allowed values per resource key

        Returns:
            True if agent was terminated

        Validates: Requirement 22.2
        """
        exceeded = [k for k, v in resource_usage.items() if v > limits.get(k, float("inf"))]
        if exceeded:
            await self.lifecycle.retire_agent(agent_id, "resource_exhaustion")
            self._log_event(
                "resource_exhaustion",
                [agent_id],
                f"Exceeded limits for: {exceeded}",
            )
            return True
        return False

    async def detect_excessive_delegation(self, agent_id: str) -> bool:
        """
        Track delegation count and limit privileges if excessive.

        Returns:
            True if delegation was limited

        Validates: Requirement 22.3
        """
        self._delegation_counts[agent_id] = self._delegation_counts.get(agent_id, 0) + 1
        count = self._delegation_counts[agent_id]

        if count >= self.delegation_limit:
            self._delegation_limited.add(agent_id)
            self._log_event(
                "delegation_limit",
                [agent_id],
                f"Delegation count {count} >= limit {self.delegation_limit}",
            )
            return True
        return False

    def is_delegation_limited(self, agent_id: str) -> bool:
        """Return True if agent has had delegation privileges limited."""
        return agent_id in self._delegation_limited

    async def detect_coordinated_behavior(
        self, agent_ids: list[str], similarity_threshold: float = 0.9
    ) -> bool:
        """
        Detect coordinated malicious behavior and retire all involved agents.

        Uses the fraction of agents with identical invalid output patterns
        as a proxy for coordination.

        Args:
            agent_ids: Agents to check for coordination
            similarity_threshold: Fraction of agents that must be quarantined

        Returns:
            True if coordinated behavior detected and agents retired

        Validates: Requirement 22.4
        """
        if not agent_ids:
            return False

        quarantined_in_group = [a for a in agent_ids if a in self._quarantined]
        fraction = len(quarantined_in_group) / len(agent_ids)

        if fraction >= similarity_threshold:
            for agent_id in agent_ids:
                await self.lifecycle.retire_agent(agent_id, "coordinated_malicious_behavior")
            self._log_event(
                "coordinated_behavior",
                agent_ids,
                f"Coordinated behavior detected: {fraction:.0%} quarantined",
            )
            return True
        return False

    def get_security_log(self) -> list[AdversarialEvent]:
        """Return all recorded adversarial events. Validates: Requirement 22.5"""
        return list(self._security_log)
