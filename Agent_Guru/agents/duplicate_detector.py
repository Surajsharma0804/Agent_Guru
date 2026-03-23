"""
Duplicate Detector - Detects and prevents duplicate agents.

This module implements duplicate detection functionality to prevent creating
agents with identical or near-identical capabilities and specializations.

**Key Features**:
- Pairwise similarity computation for all agents
- Pre-creation duplicate checking
- Automatic merging of detected duplicates
- Integration with AgentMerger

**Performance Characteristics**:
- Time Complexity: O(n²) for pairwise comparison
- Space Complexity: O(n²) for similarity matrix (worst case)
- Detection: O(n) per new agent check

Author: Agent Guru Team
Date: 2026-03-13
Version: 1.0.0
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .agent_lifecycle import Agent
    from .agent_merger import AgentMerger
    from .agent_storage import AgentStorage


class DuplicateDetector:
    """
    Detects and prevents duplicate agents.

    Uses pairwise similarity computation to identify agents with identical
    or near-identical capabilities. Integrates with AgentMerger to automatically
    merge detected duplicates.

    Time Complexity: O(n²) for pairwise comparison
    Space Complexity: O(n²) for similarity matrix

    Example:
        >>> detector = DuplicateDetector(storage, merger, duplication_threshold=0.95)
        >>> duplicates = await detector.detect_duplicates()
        >>> if duplicates:
        ...     agent1_id, agent2_id, similarity = duplicates[0]
        ...     print(f"Duplicates found: {similarity:.2f}")
        >>>
        >>> # Pre-creation check
        >>> is_duplicate = await detector.pre_creation_check(new_capabilities)
        >>> if not is_duplicate:
        ...     # Safe to create agent
        ...     pass

    Validates: Requirements 1.5, 14.1, 14.2, 14.3, 14.4, 14.5
    """

    def __init__(
        self,
        storage: "AgentStorage",
        merger: "AgentMerger",
        duplication_threshold: float = 0.95,
    ):
        """
        Initialize duplicate detector.

        Args:
            storage: Agent storage backend
            merger: Agent merger for automatic merging
            duplication_threshold: Minimum similarity for duplication (0.0-1.0)

        Raises:
            ValueError: If duplication_threshold not in range [0.0, 1.0]

        Time Complexity: O(1)

        Validates: Requirements 1.5, 14.2
        """
        if not 0.0 <= duplication_threshold <= 1.0:
            raise ValueError(
                f"duplication_threshold must be in range [0.0, 1.0], "
                f"got {duplication_threshold}"
            )

        self.storage = storage
        self.merger = merger
        self.duplication_threshold = duplication_threshold

    async def detect_duplicates(self) -> list[tuple[str, str, float]]:
        """
        Detect duplicate agents in the population.

        Performs pairwise similarity comparison of all active agents to find
        duplicates. Returns pairs that exceed the duplication threshold.

        Returns:
            List of (agent_id_1, agent_id_2, similarity_score) tuples,
            sorted by similarity descending

        Time Complexity: O(n²) where n is number of active agents
        Space Complexity: O(n²) for similarity matrix
        Performance Target: <200ms for 100 agents

        Example:
            >>> duplicates = await detector.detect_duplicates()
            >>> for agent1_id, agent2_id, similarity in duplicates:
            ...     print(f"Duplicates: {agent1_id}, {agent2_id} ({similarity:.2f})")

        Validates: Requirements 14.1, 14.2
        """
        agents = await self.storage.get_active_agents()
        duplicates = []

        # Pairwise comparison (O(n²))
        for i, agent1 in enumerate(agents):
            for agent2 in agents[i + 1 :]:
                # Calculate similarity using merger's similarity function
                similarity = self.merger._calculate_similarity(
                    agent1.specializations, agent2.specializations
                )

                if similarity >= self.duplication_threshold:
                    duplicates.append((agent1.id, agent2.id, similarity))

        # Sort by similarity descending (highest similarity first)
        duplicates.sort(key=lambda x: x[2], reverse=True)

        return duplicates

    async def pre_creation_check(
        self, proposed_capabilities: dict[str, float]
    ) -> Optional[str]:
        """
        Check if proposed agent would be duplicate before creation.

        Compares proposed capabilities against all existing active agents
        to prevent creating duplicates.

        Args:
            proposed_capabilities: Capabilities for proposed new agent

        Returns:
            Agent ID of duplicate if found, None otherwise

        Time Complexity: O(n) where n is number of active agents
        Space Complexity: O(1)
        Performance Target: <50ms for 100 agents

        Example:
            >>> proposed = {"coding": 0.9, "testing": 0.7}
            >>> duplicate_id = await detector.pre_creation_check(proposed)
            >>> if duplicate_id:
            ...     print(f"Would duplicate agent {duplicate_id}")
            ... else:
            ...     # Safe to create
            ...     agent = await lifecycle_manager.create_agent(...)

        Validates: Requirements 1.5, 14.4
        """
        agents = await self.storage.get_active_agents()

        for agent in agents:
            # Compare proposed capabilities with existing agent
            # Use specializations as proxy for capabilities
            similarity = self.merger._calculate_similarity(
                proposed_capabilities, agent.specializations
            )

            if similarity >= self.duplication_threshold:
                return agent.id

        return None

    async def auto_merge_duplicates(self) -> list["Agent"]:
        """
        Automatically merge all detected duplicates.

        Detects duplicate agents and merges them using the AgentMerger.
        Processes duplicates in order of highest similarity first.

        Returns:
            List of merged agents created

        Time Complexity: O(n² + m) where n is agents, m is merges
        Space Complexity: O(n²) for duplicate detection
        Performance Target: <500ms for 100 agents with 10 duplicates

        Example:
            >>> merged_agents = await detector.auto_merge_duplicates()
            >>> print(f"Merged {len(merged_agents)} duplicate pairs")

        Validates: Requirements 14.3, 14.5
        """
        duplicates = await self.detect_duplicates()
        merged_agents = []
        merged_ids = set()  # Track already merged agents

        for agent1_id, agent2_id, _similarity in duplicates:
            # Skip if either agent already merged
            if agent1_id in merged_ids or agent2_id in merged_ids:
                continue

            # Merge the duplicate agents
            try:
                merged_agent = await self.merger.merge_agents(agent1_id, agent2_id)
                merged_agents.append(merged_agent)

                # Mark as merged
                merged_ids.add(agent1_id)
                merged_ids.add(agent2_id)

            except ValueError:
                # Agent may have been merged by another operation
                continue

        return merged_agents

    async def get_similarity_matrix(self) -> dict[tuple[str, str], float]:
        """
        Compute full similarity matrix for all active agents.

        Useful for analysis and visualization of agent population structure.

        Returns:
            Dictionary mapping (agent_id_1, agent_id_2) to similarity score

        Time Complexity: O(n²) where n is number of active agents
        Space Complexity: O(n²) for matrix
        Performance Target: <300ms for 100 agents

        Example:
            >>> matrix = await detector.get_similarity_matrix()
            >>> for (id1, id2), similarity in matrix.items():
            ...     if similarity > 0.8:
            ...         print(f"{id1} <-> {id2}: {similarity:.2f}")

        Validates: Requirement 14.1
        """
        agents = await self.storage.get_active_agents()
        matrix = {}

        # Compute pairwise similarities
        for i, agent1 in enumerate(agents):
            for agent2 in agents[i + 1 :]:
                similarity = self.merger._calculate_similarity(
                    agent1.specializations, agent2.specializations
                )

                # Store both directions for convenience
                matrix[(agent1.id, agent2.id)] = similarity
                matrix[(agent2.id, agent1.id)] = similarity

        return matrix

    async def find_most_similar_agent(
        self, target_agent_id: str
    ) -> Optional[tuple[str, float]]:
        """
        Find the most similar agent to a target agent.

        Args:
            target_agent_id: Agent to find similar agents for

        Returns:
            Tuple of (most_similar_agent_id, similarity_score) or None

        Time Complexity: O(n) where n is number of active agents
        Space Complexity: O(1)
        Performance Target: <50ms for 100 agents

        Example:
            >>> result = await detector.find_most_similar_agent("agent_123")
            >>> if result:
            ...     similar_id, similarity = result
            ...     print(f"Most similar: {similar_id} ({similarity:.2f})")

        Validates: Requirement 14.1
        """
        target_agent = await self.storage.get_agent(target_agent_id)
        if not target_agent:
            return None

        agents = await self.storage.get_active_agents()
        max_similarity = 0.0
        most_similar_id = None

        for agent in agents:
            if agent.id == target_agent_id:
                continue

            similarity = self.merger._calculate_similarity(
                target_agent.specializations, agent.specializations
            )

            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_id = agent.id

        if most_similar_id:
            return (most_similar_id, max_similarity)

        return None

    async def get_duplicate_clusters(self) -> list[list[str]]:
        """
        Group agents into duplicate clusters.

        Identifies groups of agents that are all duplicates of each other
        (transitive closure of duplication relationship).

        Returns:
            List of agent ID clusters

        Time Complexity: O(n² + n*m) where n is agents, m is cluster size
        Space Complexity: O(n²) for similarity computation
        Performance Target: <400ms for 100 agents

        Example:
            >>> clusters = await detector.get_duplicate_clusters()
            >>> for cluster in clusters:
            ...     if len(cluster) > 1:
            ...         print(f"Duplicate cluster: {cluster}")

        Validates: Requirement 14.1
        """
        duplicates = await self.detect_duplicates()

        # Build adjacency list
        adjacency: dict[str, list[str]] = {}
        for agent1_id, agent2_id, _ in duplicates:
            if agent1_id not in adjacency:
                adjacency[agent1_id] = []
            if agent2_id not in adjacency:
                adjacency[agent2_id] = []

            adjacency[agent1_id].append(agent2_id)
            adjacency[agent2_id].append(agent1_id)

        # Find connected components (clusters)
        visited = set()
        clusters = []

        def dfs(agent_id: str, cluster: list[str]) -> None:
            """Depth-first search to find cluster."""
            visited.add(agent_id)
            cluster.append(agent_id)

            for neighbor_id in adjacency.get(agent_id, []):
                if neighbor_id not in visited:
                    dfs(neighbor_id, cluster)

        for agent_id in adjacency.keys():
            if agent_id not in visited:
                cluster: list[str] = []
                dfs(agent_id, cluster)
                clusters.append(cluster)

        return clusters
