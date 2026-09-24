"""Duplicate Detector - Detects and prevents duplicate agents.

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

import logging
from collections import deque
from typing import TYPE_CHECKING

# Runtime import (not TYPE_CHECKING): the pairwise scan below needs the actual
# function. agent_merger only imports its own siblings under TYPE_CHECKING, so
# this does not create a cycle.
from .agent_merger import specialization_norm

if TYPE_CHECKING:
    from .agent_lifecycle import Agent
    from .agent_merger import AgentMerger
    from .agent_storage import AgentStorage

logger = logging.getLogger(__name__)

# BUG FIX: every method below used to reach into AgentMerger's PRIVATE
# (underscore-prefixed) similarity method from outside, 4 times in this
# file alone. AgentMerger now exposes a public `calculate_similarity()`
# wrapper (added when this was fixed), and every call site below has
# been updated to use it instead.


class DuplicateDetector:
    """Detects and prevents duplicate agents.

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
    ) -> None:
        """Initialize duplicate detector.

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
            msg = f"duplication_threshold must be in range [0.0, 1.0], got {duplication_threshold}"
            raise ValueError(
                msg,
            )

        self.storage = storage
        self.merger = merger
        self.duplication_threshold = duplication_threshold

    async def detect_duplicates(self) -> list[tuple[str, str, float]]:
        """Detect duplicate agents in the population.

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

        # An agent's norm depends only on that agent, so compute it once per
        # agent instead of once per pair: the old scan recomputed every norm
        # n-1 times inside the O(n²) loop.
        norms = [specialization_norm(a.specializations) for a in agents]

        # Pairwise comparison (O(n²))
        for i, agent1 in enumerate(agents):
            for j in range(i + 1, len(agents)):
                agent2 = agents[j]
                # Calculate similarity using merger's similarity function
                similarity = self.merger.calculate_similarity(
                    agent1.specializations,
                    agent2.specializations,
                    norms[i],
                    norms[j],
                )

                if similarity >= self.duplication_threshold:
                    duplicates.append((agent1.id, agent2.id, similarity))

        # Sort by similarity descending (highest similarity first)
        duplicates.sort(key=lambda x: x[2], reverse=True)

        return duplicates

    async def pre_creation_check(self, proposed_capabilities: dict[str, float]) -> str | None:
        """Check if proposed agent would be duplicate before creation.

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
        proposed_norm = specialization_norm(proposed_capabilities)

        for agent in agents:
            # Compare proposed capabilities with existing agent
            # Use specializations as proxy for capabilities. The proposed
            # vector does not change during the scan, so its norm is computed
            # once rather than once per existing agent.
            similarity = self.merger.calculate_similarity(
                proposed_capabilities,
                agent.specializations,
                proposed_norm,
            )

            if similarity >= self.duplication_threshold:
                return agent.id

        return None

    async def auto_merge_duplicates(self) -> list["Agent"]:
        """Automatically merge all detected duplicates.

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

            except Exception:
                # FIX: previously caught only `ValueError` - but this loop's
                # own intent (documented in the comment below) is "an agent
                # may have been merged/modified concurrently by another
                # operation, skip and keep going". Any other exception type
                # from merge_agents() (a storage error, a KeyError from a
                # concurrently-deleted agent, etc.) previously propagated
                # straight out of this method, silently discarding every
                # merge already completed in this call (merged_agents /
                # merged_ids built so far were never returned - the whole
                # batch was lost on the first unexpected error type).
                # Also previously logged NOTHING on failure - a silent
                # `continue` - making merge failures completely invisible.
                # PopulationManager.trigger_aggressive_merging (a sibling
                # "merge in a loop, keep going" function calling the same
                # merger.merge_agents()) already caught broadly AND logged;
                # this brings auto_merge_duplicates in line with that.
                logger.exception(
                    "Merge failed for %s + %s - skipping, continuing with remaining duplicates",
                    agent1_id,
                    agent2_id,
                )
                continue

        return merged_agents

    async def get_similarity_matrix(self) -> dict[tuple[str, str], float]:
        """Compute full similarity matrix for all active agents.

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

        # One norm per agent, not one per pair (see detect_duplicates).
        norms = [specialization_norm(a.specializations) for a in agents]

        # Compute pairwise similarities
        for i, agent1 in enumerate(agents):
            for j in range(i + 1, len(agents)):
                agent2 = agents[j]
                similarity = self.merger.calculate_similarity(
                    agent1.specializations,
                    agent2.specializations,
                    norms[i],
                    norms[j],
                )

                # Store both directions for convenience
                matrix[(agent1.id, agent2.id)] = similarity
                matrix[(agent2.id, agent1.id)] = similarity

        return matrix

    async def find_most_similar_agent(self, target_agent_id: str) -> tuple[str, float] | None:
        """Find the most similar agent to a target agent.

        Args:
            target_agent_id: Agent to find similar agents for

        Returns:
            Tuple of (most_similar_agent_id, similarity_score) or None if
            there are no other agents to compare against.

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
        # FIX: was initialized to 0.0, which meant that if EVERY other agent
        # had similarity of exactly 0.0 (completely dissimilar, not merely
        # "below some threshold"), the strict `similarity > max_similarity`
        # comparison would never fire even once, and this would silently
        # return None - even though there WAS another agent to compare
        # against, and the docstring promises to find "the most similar
        # agent" unconditionally (no threshold mentioned), not "the most
        # similar agent, or None if the best match happens to be weak".
        # -1.0 is below the valid similarity range (validated elsewhere in
        # this class to be in [0.0, 1.0] via duplication_threshold's own
        # bounds check), so the first real candidate always wins the
        # comparison, exactly matching the literal docstring contract.
        max_similarity = -1.0
        most_similar_id = None
        # The target is fixed for the whole scan, so its norm is computed once.
        target_norm = specialization_norm(target_agent.specializations)

        for agent in agents:
            if agent.id == target_agent_id:
                continue

            similarity = self.merger.calculate_similarity(
                target_agent.specializations,
                agent.specializations,
                target_norm,
            )

            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_id = agent.id

        # BUG FIX: was `if most_similar_id:` -- a truthy check on a
        # string ID. No agent ID is ever an empty string anywhere else
        # in this codebase (IDs are always uuid4 strings), but an empty
        # string is falsy in Python, so if one ever occurred it would be
        # silently treated as "no match found" even though
        # most_similar_id was genuinely set. `is not None` says exactly
        # what this means ("was a candidate found"), matching the same
        # defensive precision already used for max_similarity's -1.0
        # sentinel above.
        if most_similar_id is not None:
            return (most_similar_id, max_similarity)

        return None

    async def get_duplicate_clusters(self) -> list[list[str]]:
        """Group agents into duplicate clusters.

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

        # Find connected components (clusters) - iterative BFS to avoid recursion limit
        #
        # FIX: this used to be `queue = [start_id]` / `queue.pop()` (pop with
        # no index pops from the END of a list - LIFO - which is actually
        # DFS, not BFS, despite the comment). Verified concretely with a
        # small graph: the old code visited nodes in DFS order (deeper
        # before wider), not BFS order. For finding connected components
        # specifically this didn't change WHICH agents end up in the same
        # cluster (component membership doesn't depend on traversal order)
        # - so it wasn't a functional bug for this particular use - but the
        # comment claiming BFS while the code did DFS is exactly the kind
        # of mismatch that misleads whoever edits this next. Fixed with a
        # real deque-based FIFO so the code now actually does what it says.
        # (Using `collections.deque.popleft()` rather than `list.pop(0)` -
        # `list.pop(0)` is O(n) per call, an anti-pattern already found and
        # fixed elsewhere in this codebase; deque.popleft() is O(1).)
        visited = set()
        clusters = []

        for start_id in adjacency:
            if start_id in visited:
                continue
            cluster: list[str] = []
            queue: deque[str] = deque([start_id])
            while queue:
                agent_id = queue.popleft()
                if agent_id in visited:
                    continue
                visited.add(agent_id)
                cluster.append(agent_id)
                for neighbor_id in adjacency.get(agent_id, []):
                    if neighbor_id not in visited:
                        queue.append(neighbor_id)
            clusters.append(cluster)

        return clusters
