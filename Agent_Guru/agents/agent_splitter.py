"""
Agent Splitter - Splits agents with divergent specializations.

This module implements agent splitting functionality to optimize the agent
population by dividing agents that have developed distinct sub-specializations
into multiple focused agents.

**Key Features**:
- Divergence analysis for specialization clustering
- History partitioning by task type clusters
- Automatic source agent retirement
- Evolution event recording

**Performance Characteristics**:
- Time Complexity: O(k²) where k is number of task types
- Space Complexity: O(n) for agent storage
- Divergence calculation: O(k²) for pairwise task type comparison

Author: Agent Guru Team
Date: 2026-03-13
Version: 1.0.0
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .agent_lifecycle import Agent, AgentLifecycleManager, PerformanceRecord
    from .agent_storage import AgentStorage


class AgentSplitter:
    """
    Splits agents with divergent specializations.

    Analyzes agent specializations to detect when an agent has developed
    expertise in multiple distinct domains. When divergence exceeds threshold,
    splits the agent into multiple focused agents.

    Time Complexity: O(k²) for divergence calculation
    Space Complexity: O(n) for agent storage

    Example:
        >>> splitter = AgentSplitter(storage, lifecycle_manager, divergence_threshold=0.7)
        >>> candidates = await splitter.detect_split_candidates()
        >>> if candidates:
        ...     agent_id, divergence = candidates[0]
        ...     new_agents = await splitter.split_agent(agent_id)
        ...     print(f"Split into {len(new_agents)} agents")

    Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5
    """

    def __init__(
        self,
        storage: "AgentStorage",
        lifecycle_manager: "AgentLifecycleManager",
        divergence_threshold: float = 0.7,
        min_task_count: int = 20,
    ):
        """
        Initialize agent splitter.

        Args:
            storage: Agent storage backend
            lifecycle_manager: Lifecycle manager for creating split agents
            divergence_threshold: Minimum divergence for split (0.0-1.0)
            min_task_count: Minimum tasks before allowing split

        Raises:
            ValueError: If divergence_threshold not in range [0.0, 1.0]
            ValueError: If min_task_count < 1

        Time Complexity: O(1)

        Validates: Requirements 4.1, 4.5
        """
        if not 0.0 <= divergence_threshold <= 1.0:
            raise ValueError(
                f"divergence_threshold must be in range [0.0, 1.0], "
                f"got {divergence_threshold}"
            )

        if min_task_count < 1:
            raise ValueError(f"min_task_count must be >= 1, got {min_task_count}")

        self.storage = storage
        self.lifecycle_manager = lifecycle_manager
        self.divergence_threshold = divergence_threshold
        self.min_task_count = min_task_count

    async def detect_split_candidates(self) -> list[tuple[str, float]]:
        """
        Detect agents with divergent specializations.

        Analyzes all active agents to find those with specializations in
        multiple distinct domains. Returns agents that exceed divergence
        threshold and have sufficient task history.

        Returns:
            List of (agent_id, divergence_score) tuples,
            sorted by divergence descending

        Time Complexity: O(n * k²) where n is agents, k is task types
        Space Complexity: O(n) for candidate list
        Performance Target: <200ms for 100 agents

        Example:
            >>> candidates = await splitter.detect_split_candidates()
            >>> for agent_id, divergence in candidates:
            ...     print(f"Agent {agent_id}: divergence {divergence:.2f}")

        Validates: Requirements 4.1, 4.5
        """
        agents = await self.storage.get_active_agents()
        candidates = []

        for agent in agents:
            # Check minimum task count
            if agent.total_tasks < self.min_task_count:
                continue

            # Calculate divergence
            divergence = self._calculate_divergence(agent.specializations)

            if divergence >= self.divergence_threshold:
                candidates.append((agent.id, divergence))

        # Sort by divergence descending (highest divergence first)
        candidates.sort(key=lambda x: x[1], reverse=True)

        return candidates

    async def split_agent(self, agent_id: str) -> list["Agent"]:
        """
        Split agent into multiple focused agents.

        Creates new agents with non-overlapping specialization sets by
        clustering task types into distinct domains. Each new agent receives
        a partition of the source agent's performance history.

        Args:
            agent_id: Agent to split

        Returns:
            List of newly created agents

        Raises:
            ValueError: If agent not found
            ValueError: If agent has insufficient task count

        Time Complexity: O(k² + h) where k is task types, h is history size
        Space Complexity: O(k + h) for partitioned data
        Performance Target: <100ms per split

        Example:
            >>> new_agents = await splitter.split_agent("agent_123")
            >>> print(f"Split into {len(new_agents)} agents")
            >>> for agent in new_agents:
            ...     print(f"Agent {agent.id}: {agent.specializations}")

        Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5
        """
        agent = await self.storage.get_agent(agent_id)

        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        # Check minimum task count
        if agent.total_tasks < self.min_task_count:
            raise ValueError(
                f"Agent {agent_id} has insufficient task count "
                f"({agent.total_tasks} < {self.min_task_count})"
            )

        # Get performance history
        agent.performance_history = await self.storage.get_performance_records(agent_id)

        # Partition specializations into clusters
        clusters = self._partition_specializations(agent.specializations)

        if len(clusters) < 2:
            raise ValueError(
                f"Agent {agent_id} cannot be split: "
                f"only {len(clusters)} cluster(s) found"
            )

        # Partition performance history by clusters
        history_partitions = self._partition_history(
            agent.performance_history,
            clusters
        )

        # Create new agents for each cluster
        from .agent_lifecycle import Agent, AgentStatus

        new_agents = []
        for i, (cluster_types, cluster_specs) in enumerate(clusters.items()):
            # Get history for this cluster
            cluster_history = history_partitions.get(cluster_types, [])

            # Calculate task counts for this cluster
            cluster_total = len(cluster_history)
            cluster_successful = sum(1 for r in cluster_history if r.success)

            # Create capabilities from specializations
            cluster_capabilities = {
                task_type: score * 0.8  # Capabilities slightly lower than specialization
                for task_type, score in cluster_specs.items()
            }

            # Create new agent
            new_agent = Agent(
                id=str(uuid.uuid4()),
                status=AgentStatus.ACTIVE,
                capabilities=cluster_capabilities,
                specializations=cluster_specs.copy(),
                performance_history=cluster_history,
                created_at=datetime.now(tz=timezone.utc),
                last_active=datetime.now(tz=timezone.utc),
                total_tasks=cluster_total,
                successful_tasks=cluster_successful,
                metadata={
                    "split_from": agent_id,
                    "split_reason": "divergent_specializations",
                    "split_cluster": i,
                    "split_timestamp": datetime.now(tz=timezone.utc).isoformat(),
                },
            )

            # Store new agent
            await self.storage.store_agent(new_agent)
            new_agents.append(new_agent)

        # Retire source agent
        await self.lifecycle_manager.retire_agent(agent_id, "split")

        # Record split event
        await self.lifecycle_manager._record_evolution_event(
            event_type="split",
            agent_ids=[agent_id] + [a.id for a in new_agents],
            reason="divergent_specializations",
            details={
                "source_agent": agent_id,
                "new_agents": [a.id for a in new_agents],
                "divergence_score": self._calculate_divergence(agent.specializations),
                "clusters": {
                    str(i): list(cluster_types)
                    for i, cluster_types in enumerate(clusters.keys())
                },
            },
        )

        return new_agents

    def _calculate_divergence(self, specializations: dict[str, float]) -> float:
        """
        Calculate divergence score for specializations.

        Measures how distinct the specializations are by analyzing pairwise
        dissimilarity between task types. High divergence indicates the agent
        has expertise in multiple unrelated domains.

        Formula: divergence = 1 - average_similarity
        where similarity is based on co-occurrence patterns

        Args:
            specializations: Task type specialization scores

        Returns:
            Divergence score in range [0.0, 1.0]
            - 0.0: All specializations highly related
            - 1.0: Specializations completely unrelated

        Time Complexity: O(k²) where k is number of task types
        Space Complexity: O(k²) for similarity matrix
        Performance Target: <10ms for 10 task types

        Example:
            >>> specs = {"coding": 0.9, "design": 0.8, "testing": 0.85}
            >>> divergence = splitter._calculate_divergence(specs)
            >>> print(f"Divergence: {divergence:.2f}")

        Validates: Requirement 4.1
        """
        if len(specializations) < 2:
            return 0.0

        task_types = list(specializations.keys())
        n = len(task_types)

        # Calculate pairwise dissimilarity based on task type names
        # In production, would use semantic similarity or co-occurrence data
        dissimilarities = []

        for i in range(n):
            for j in range(i + 1, n):
                type1 = task_types[i]
                type2 = task_types[j]

                # Simple heuristic: dissimilarity based on string distance
                # In production: use semantic embeddings or co-occurrence stats
                dissimilarity = self._task_type_dissimilarity(type1, type2)
                dissimilarities.append(dissimilarity)

        if not dissimilarities:
            return 0.0

        # Average dissimilarity is the divergence score
        divergence = float(np.mean(dissimilarities))

        return np.clip(divergence, 0.0, 1.0)

    # Domain synonym groups: terms in the same group are semantically similar
    _DOMAIN_GROUPS: tuple = (
        {"coding", "coder", "coders", "code", "programming", "programmer", "development", "developer",
         "software", "engineering", "engineer", "implementation", "implement"},
        {"testing", "tester", "qa", "quality", "validation", "verification", "test"},
        {"design", "designer", "architecture", "architect", "planning", "modeling", "blueprint"},
        {"data", "analytics", "analysis", "statistics", "ml", "machine_learning", "ai"},
        {"devops", "deployment", "infrastructure", "ops", "ci", "cd", "pipeline"},
        {"documentation", "writing", "docs", "readme", "specification"},
        {"security", "auth", "authentication", "authorization", "crypto", "encryption"},
        {"database", "storage", "persistence", "sql", "nosql", "db"},
        {"frontend", "ui", "ux", "interface", "web", "css", "html"},
        {"backend", "api", "server", "service", "microservice", "rest"},
    )

    def _task_type_dissimilarity(self, type1: str, type2: str) -> float:
        """
        Calculate dissimilarity between two task types.

        Uses domain synonym groups for semantic similarity, falling back to
        bigram-based string similarity for unknown terms.

        Args:
            type1: First task type
            type2: Second task type

        Returns:
            Dissimilarity score in range [0.0, 1.0]

        Time Complexity: O(G) where G is number of domain groups
        """
        t1 = type1.lower().strip()
        t2 = type2.lower().strip()

        if t1 == t2:
            return 0.0

        # Check if one is a prefix/stem of the other (e.g. "coding" / "coder")
        shorter, longer = (t1, t2) if len(t1) <= len(t2) else (t2, t1)
        if len(shorter) >= 3 and longer.startswith(shorter[:min(len(shorter), 4)]):
            return 0.2  # Morphologically related

        # Check if both terms belong to the same domain group
        for group in self._DOMAIN_GROUPS:
            if t1 in group and t2 in group:
                return 0.1  # Very similar — same domain

        # Bigram-based similarity (better than character sets)
        def bigrams(s: str) -> set:
            return {s[i:i+2] for i in range(len(s) - 1)} if len(s) > 1 else {s}

        bg1 = bigrams(t1)
        bg2 = bigrams(t2)

        if not bg1 or not bg2:
            return 1.0

        overlap = len(bg1 & bg2)
        union = len(bg1 | bg2)
        similarity = overlap / union if union > 0 else 0.0
        return 1.0 - similarity

    def _partition_specializations(
        self, specializations: dict[str, float]
    ) -> dict[tuple[str, ...], dict[str, float]]:
        """
        Partition specializations into clusters.

        Groups task types into distinct clusters based on similarity.
        Each cluster represents a focused domain of expertise.

        Args:
            specializations: Task type specialization scores

        Returns:
            Dictionary mapping cluster task types to specialization scores

        Time Complexity: O(k²) where k is number of task types
        Space Complexity: O(k) for clusters

        Validates: Requirement 4.3
        """
        if len(specializations) < 2:
            return {tuple(specializations.keys()): specializations}

        task_types = list(specializations.keys())
        n = len(task_types)

        # Build similarity matrix
        similarity_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i == j:
                    similarity_matrix[i][j] = 1.0
                else:
                    dissim = self._task_type_dissimilarity(task_types[i], task_types[j])
                    similarity_matrix[i][j] = 1.0 - dissim

        # Simple clustering: group by similarity threshold
        clusters: dict[int, list[int]] = {}
        assigned = set()
        cluster_id = 0

        for i in range(n):
            if i in assigned:
                continue

            # Start new cluster
            clusters[cluster_id] = [i]
            assigned.add(i)

            # Add similar task types to cluster
            for j in range(i + 1, n):
                if j in assigned:
                    continue

                # Check similarity with cluster members
                avg_similarity = float(np.mean([similarity_matrix[member_idx][j] for member_idx in clusters[cluster_id]]))

                if avg_similarity > 0.5:  # Similarity threshold
                    clusters[cluster_id].append(j)
                    assigned.add(j)

            cluster_id += 1

        # Convert to result format
        result = {}
        for cluster_indices in clusters.values():
            cluster_types = tuple(task_types[i] for i in cluster_indices)
            cluster_specs = {
                task_types[i]: specializations[task_types[i]]
                for i in cluster_indices
            }
            result[cluster_types] = cluster_specs

        return result

    def _partition_history(
        self,
        history: list["PerformanceRecord"],
        clusters: dict[tuple[str, ...], dict[str, float]],
    ) -> dict[tuple[str, ...], list["PerformanceRecord"]]:
        """
        Partition performance history by task type clusters.

        Assigns each performance record to the cluster containing its task type.

        Args:
            history: Performance history to partition
            clusters: Task type clusters

        Returns:
            Dictionary mapping cluster task types to performance records

        Time Complexity: O(h * k) where h is history size, k is task types
        Space Complexity: O(h) for partitioned history

        Example:
            >>> history = [record1, record2, record3]
            >>> clusters = {("coding", "testing"): {...}, ("design",): {...}}
            >>> partitions = splitter._partition_history(history, clusters)

        Validates: Requirement 4.2
        """
        partitions: dict[tuple[str, ...], list["PerformanceRecord"]] = {
            cluster_types: [] for cluster_types in clusters.keys()
        }

        for record in history:
            # Find which cluster this task type belongs to
            for cluster_types in clusters.keys():
                if record.task_type in cluster_types:
                    partitions[cluster_types].append(record)
                    break

        return partitions
