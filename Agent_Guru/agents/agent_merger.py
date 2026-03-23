"""
Agent Merger - Merges agents with overlapping specializations.

This module implements agent merging functionality to reduce redundancy in the
agent population by combining agents with similar specializations.

**Key Features**:
- Cosine similarity detection for overlapping specializations
- Weighted merging of capabilities and performance histories
- Automatic source agent retirement
- Evolution event recording

**Performance Characteristics**:
- Time Complexity: O(n²) for pairwise comparison (acceptable for agent population)
- Space Complexity: O(n) for agent storage
- Similarity calculation: O(k) where k is number of task types

Author: Agent Guru Team
Date: 2026-02-28
Version: 1.0.0
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .agent_lifecycle import Agent, AgentLifecycleManager
    from .agent_storage import AgentStorage


class AgentMerger:
    """
    Merges agents with overlapping specializations.

    Uses cosine similarity to detect overlap between agent specializations.
    When agents have similarity above threshold, they are merged into a single
    agent that combines their capabilities and performance histories.

    Time Complexity: O(n²) for pairwise comparison
    Space Complexity: O(n) for agent storage

    Example:
        >>> merger = AgentMerger(storage, lifecycle_manager, similarity_threshold=0.85)
        >>> candidates = await merger.detect_merge_candidates()
        >>> if candidates:
        ...     agent1_id, agent2_id, similarity = candidates[0]
        ...     merged_agent = await merger.merge_agents(agent1_id, agent2_id)
        ...     print(f"Merged agents with similarity {similarity:.2f}")

    Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 14.1, 14.2, 14.3
    """

    def __init__(
        self,
        storage: "AgentStorage",
        lifecycle_manager: "AgentLifecycleManager",
        similarity_threshold: float = 0.85,
    ):
        """
        Initialize agent merger.

        Args:
            storage: Agent storage backend for retrieving agents
            lifecycle_manager: Lifecycle manager for creating merged agents
            similarity_threshold: Minimum similarity for merge (0.0-1.0)

        Raises:
            ValueError: If similarity_threshold not in range [0.0, 1.0]

        Time Complexity: O(1)

        Validates: Requirements 3.1, 14.2
        """
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError(
                f"similarity_threshold must be in range [0.0, 1.0], " f"got {similarity_threshold}"
            )

        self.storage = storage
        self.lifecycle_manager = lifecycle_manager
        self.similarity_threshold = similarity_threshold
        # Cache similarity results for the same pair within a detection pass
        self._similarity_cache: dict[tuple, float] = {}

    async def detect_merge_candidates(self) -> list[tuple[str, str, float]]:
        """
        Detect pairs of agents with overlapping specializations.

        Performs pairwise comparison of all active agents using cosine similarity
        on their specialization vectors. Returns pairs that exceed the similarity
        threshold, sorted by similarity score descending.

        Returns:
            List of (agent_id_1, agent_id_2, similarity_score) tuples,
            sorted by similarity descending

        Time Complexity: O(n²) where n is number of active agents
        Space Complexity: O(n²) for candidate list (worst case)
        Performance Target: <100ms for 100 agents

        Example:
            >>> candidates = await merger.detect_merge_candidates()
            >>> for agent1_id, agent2_id, similarity in candidates:
            ...     print(f"Agents {agent1_id} and {agent2_id}: {similarity:.2f}")

        Validates: Requirements 3.1, 14.1, 14.2
        """
        agents = await self.storage.get_active_agents()
        candidates = []

        # Compare all pairs (O(n²) pairwise comparison)
        for i, agent1 in enumerate(agents):
            for agent2 in agents[i + 1 :]:
                similarity = self._calculate_similarity(
                    agent1.specializations, agent2.specializations
                )

                if similarity >= self.similarity_threshold:
                    candidates.append((agent1.id, agent2.id, similarity))

        # Sort by similarity descending (highest similarity first)
        candidates.sort(key=lambda x: x[2], reverse=True)

        return candidates

    async def merge_agents(self, agent_id_1: str, agent_id_2: str) -> "Agent":
        """
        Merge two agents into one.

        Creates a new agent that combines the specializations, capabilities,
        and performance histories of both source agents. The merged agent:
        - Takes maximum specialization score for each task type
        - Uses weighted average for capabilities based on task count
        - Combines performance histories sorted by timestamp
        - Retires source agents with reason "merged"
        - Records merge evolution event

        Args:
            agent_id_1: First agent to merge
            agent_id_2: Second agent to merge

        Returns:
            Merged agent with combined specializations and capabilities

        Raises:
            ValueError: If one or both agents not found

        Time Complexity: O(k + h) where k is task types, h is history size
        Space Complexity: O(k + h) for merged data
        Performance Target: <50ms per merge

        Example:
            >>> merged = await merger.merge_agents("agent_1", "agent_2")
            >>> print(f"Merged agent: {merged.id}")
            >>> print(f"Total tasks: {merged.total_tasks}")
            >>> print(f"Specializations: {merged.specializations}")

        Validates: Requirements 3.2, 3.3, 3.4, 3.5, 14.3
        """
        agent1 = await self.storage.get_agent(agent_id_1)
        agent2 = await self.storage.get_agent(agent_id_2)

        if not agent1 or not agent2:
            raise ValueError(f"One or both agents not found: {agent_id_1}, {agent_id_2}")

        # Get performance histories from storage
        agent1.performance_history = await self.storage.get_performance_records(agent_id_1)
        agent2.performance_history = await self.storage.get_performance_records(agent_id_2)

        # Combine specializations (take maximum score for each task type)
        # Validates: Requirement 3.3
        merged_specializations = {}
        all_task_types = set(agent1.specializations.keys()) | set(agent2.specializations.keys())

        for task_type in all_task_types:
            score1 = agent1.specializations.get(task_type, 0.0)
            score2 = agent2.specializations.get(task_type, 0.0)
            merged_specializations[task_type] = max(score1, score2)

        # Combine capabilities (weighted average by task count)
        # Validates: Requirement 3.2
        total_tasks = agent1.total_tasks + agent2.total_tasks
        weight1 = agent1.total_tasks / total_tasks if total_tasks > 0 else 0.5
        weight2 = agent2.total_tasks / total_tasks if total_tasks > 0 else 0.5

        merged_capabilities = {}
        all_capabilities = set(agent1.capabilities.keys()) | set(agent2.capabilities.keys())

        for capability in all_capabilities:
            cap1 = agent1.capabilities.get(capability, 0.0)
            cap2 = agent2.capabilities.get(capability, 0.0)
            merged_capabilities[capability] = weight1 * cap1 + weight2 * cap2

        # Combine performance histories (sorted by timestamp)
        # Validates: Requirement 3.2
        merged_history = agent1.performance_history + agent2.performance_history
        merged_history.sort(key=lambda x: x.timestamp)

        # Create merged agent
        # Validates: Requirement 3.4
        from .agent_lifecycle import Agent, AgentStatus

        merged_agent = Agent(
            id=str(uuid.uuid4()),
            status=AgentStatus.ACTIVE,
            capabilities=merged_capabilities,
            specializations=merged_specializations,
            performance_history=merged_history,
            created_at=datetime.now(),
            last_active=datetime.now(),
            total_tasks=agent1.total_tasks + agent2.total_tasks,
            successful_tasks=agent1.successful_tasks + agent2.successful_tasks,
            metadata={
                "merged_from": [agent_id_1, agent_id_2],
                "merge_reason": "overlapping_specializations",
                "merge_timestamp": datetime.now().isoformat(),
            },
        )

        # Store merged agent
        await self.storage.store_agent(merged_agent)

        # Retire source agents
        # Validates: Requirement 3.4
        await self.lifecycle_manager.retire_agent(agent_id_1, "merged")
        await self.lifecycle_manager.retire_agent(agent_id_2, "merged")

        # Record merge event
        # Validates: Requirement 3.5
        await self.lifecycle_manager._record_evolution_event(
            event_type="merge",
            agent_ids=[agent_id_1, agent_id_2, merged_agent.id],
            reason="overlapping_specializations",
            details={
                "source_agents": [agent_id_1, agent_id_2],
                "merged_agent": merged_agent.id,
                "merged_specializations": merged_specializations,
                "similarity_score": self._calculate_similarity(
                    agent1.specializations, agent2.specializations
                ),
            },
        )

        return merged_agent

    def _calculate_similarity(self, spec1: dict[str, float], spec2: dict[str, float]) -> float:
        """
        Calculate cosine similarity between specialization vectors.

        Results are cached by frozen key for repeated calls within the same session.

        Formula: similarity = (A · B) / (||A|| * ||B||)

        Args:
            spec1: First specialization dict (task_type -> score)
            spec2: Second specialization dict (task_type -> score)

        Returns:
            Similarity score in range [0.0, 1.0]

        Time Complexity: O(k) where k is number of unique task types
        Performance Target: <1ms per calculation

        Validates: Requirements 3.1, 14.1
        """
        # Handle empty specializations
        if not spec1 or not spec2:
            return 0.0

        # Cache key: frozensets of items for order-independence
        cache_key = (frozenset(spec1.items()), frozenset(spec2.items()))
        if cache_key in self._similarity_cache:
            return self._similarity_cache[cache_key]

        # Get all task types from both specializations
        all_types = set(spec1.keys()) | set(spec2.keys())

        # Create vectors (0.0 for missing task types)
        vec1 = np.array([spec1.get(t, 0.0) for t in all_types], dtype=np.float64)
        vec2 = np.array([spec2.get(t, 0.0) for t in all_types], dtype=np.float64)

        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        # Handle zero vectors (no specializations)
        if norm1 == 0 or norm2 == 0:
            result = 0.0
        else:
            result = float(np.clip(dot_product / (norm1 * norm2), 0.0, 1.0))

        self._similarity_cache[cache_key] = result
        return result
