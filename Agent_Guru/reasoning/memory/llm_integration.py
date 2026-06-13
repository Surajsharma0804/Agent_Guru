"""Memory Integration for LLM Reasoning.

This module provides utilities for integrating memory retrieval with LLM reasoning,
including memory formatting for prompts, usage tracking, and relevance updates.

Performance Characteristics:
    - Time Complexity: O(log n) for retrieval + O(k) for formatting
    - Space Complexity: O(k) where k=top_k memories
    - Retrieval Latency: <100ms (target)
    - Formatting: <10ms (target)

Design Principles:
    - Retrieve relevant memories before LLM reasoning
    - Format memories for optimal LLM comprehension
    - Track memory usage for relevance scoring
    - Update relevance based on actual usage
    - Provide clean integration points for LLM components

Competitive Advantage:
    - Retrieval-augmented reasoning for better accuracy
    - Automatic relevance learning from usage patterns
    - Efficient memory formatting for token optimization
    - Real-time usage tracking for adaptive memory

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from Agent_Guru.reasoning.memory_retriever import MemoryRetriever
from Agent_Guru.reasoning.models.intent import Intent
from Agent_Guru.reasoning.models.memory import Memory, MemoryType


@dataclass
class MemoryContext:
    """Context containing retrieved memories for LLM reasoning.

    Attributes:
        memories: List of retrieved Memory objects (max 5)
        formatted_prompt: Formatted string for LLM prompt injection
        retrieval_time_ms: Time taken to retrieve memories (ms)
        memory_ids: List of memory IDs for usage tracking
        query: Original query used for retrieval

    """

    memories: list[Memory]
    formatted_prompt: str
    retrieval_time_ms: float
    memory_ids: list[UUID]
    query: str


@dataclass
class MemoryUsageStats:
    """Statistics for memory usage tracking.

    Attributes:
        memory_id: ID of the memory
        usage_count: Number of times memory was retrieved
        last_used: Timestamp of last usage
        relevance_boost: Boost to relevance score based on usage

    """

    memory_id: UUID
    usage_count: int
    last_used: datetime
    relevance_boost: float


class MemoryLLMIntegration:
    """Integration layer between Memory Retrieval and LLM Reasoning.

    This class provides utilities for retrieving memories before LLM reasoning,
    formatting them for prompt injection, tracking usage, and updating relevance
    scores based on actual usage patterns.

    Time Complexity:
        - retrieve_for_reasoning: O(log n + k) where k=top_k
        - format_memories_for_prompt: O(k) where k=len(memories)
        - track_memory_usage: O(k) where k=len(memory_ids)
        - update_relevance_from_usage: O(1) per memory

    Space Complexity:
        - O(k) where k=top_k memories
        - O(u) where u=tracked usage stats

    Attributes:
        memory_retriever: MemoryRetriever instance for semantic search
        usage_stats: Dictionary mapping memory_id to usage statistics
        max_memories: Maximum memories to retrieve (default 5)
        relevance_boost_factor: Factor for boosting relevance (default 0.1)

    Example:
        >>> integration = MemoryLLMIntegration(memory_retriever)
        >>> context = integration.retrieve_for_reasoning(
        ...     intent=intent,
        ...     user_id="user_123"
        ... )
        >>> print(context.formatted_prompt)
        >>> integration.track_memory_usage(context.memory_ids)

    """

    def __init__(
        self,
        memory_retriever: MemoryRetriever,
        max_memories: int = 5,
        relevance_boost_factor: float = 0.1,
    ) -> None:
        """Initialize MemoryLLMIntegration.

        Args:
            memory_retriever: MemoryRetriever instance for semantic search
            max_memories: Maximum memories to retrieve (default 5)
            relevance_boost_factor: Factor for boosting relevance (default 0.1)

        Raises:
            ValueError: If max_memories < 1 or relevance_boost_factor < 0

        """
        if max_memories < 1:
            msg = f"max_memories must be >= 1, got {max_memories}"
            raise ValueError(msg)
        if relevance_boost_factor < 0:
            msg = f"relevance_boost_factor must be >= 0, got {relevance_boost_factor}"
            raise ValueError(msg)

        self.memory_retriever = memory_retriever
        self.max_memories = max_memories
        self.relevance_boost_factor = relevance_boost_factor

        # Usage tracking
        self.usage_stats: dict[UUID, MemoryUsageStats] = {}

    def retrieve_for_reasoning(
        self,
        intent: Intent,
        user_id: str,
        memory_types: list[MemoryType] | None = None,
    ) -> MemoryContext:
        """Retrieve relevant memories for LLM reasoning.

        Time Complexity: O(log n + k) where k=max_memories
        Latency Budget: <100ms (target)

        This method retrieves the most relevant memories for the given intent
        and formats them for LLM prompt injection. It tracks retrieval time
        and returns a MemoryContext for usage tracking.

        Args:
            intent: Intent object containing user's request
            user_id: User ID for filtering memories
            memory_types: Optional list of memory types to filter

        Returns:
            MemoryContext with retrieved memories and formatted prompt

        Example:
            >>> integration = MemoryLLMIntegration(memory_retriever)
            >>> context = integration.retrieve_for_reasoning(
            ...     intent=intent,
            ...     user_id="user_123",
            ...     memory_types=[MemoryType.EPISODIC, MemoryType.PREFERENCE]
            ... )

        """
        import time

        start_time = time.perf_counter()

        # Build query from intent
        query = self._build_query_from_intent(intent)

        # Retrieve memories
        memories = self.memory_retriever.retrieve(
            query=query,
            user_id=user_id,
            memory_types=memory_types,
            top_k=self.max_memories,
        )

        # Format for LLM prompt
        formatted_prompt = self.format_memories_for_prompt(memories)

        # Calculate retrieval time
        retrieval_time_ms = (time.perf_counter() - start_time) * 1000

        # Extract memory IDs for tracking
        memory_ids = [memory.memory_id for memory in memories]

        return MemoryContext(
            memories=memories,
            formatted_prompt=formatted_prompt,
            retrieval_time_ms=retrieval_time_ms,
            memory_ids=memory_ids,
            query=query,
        )

    def format_memories_for_prompt(self, memories: list[Memory]) -> str:
        """Format memories for LLM prompt injection.

        Time Complexity: O(k) where k=len(memories)
        Latency Budget: <10ms (target)

        This method formats memories into a structured string suitable for
        injection into LLM prompts. It includes memory type, content, and
        relevant metadata for context.

        Args:
            memories: List of Memory objects to format

        Returns:
            Formatted string for LLM prompt injection

        Example:
            >>> integration = MemoryLLMIntegration(memory_retriever)
            >>> formatted = integration.format_memories_for_prompt(memories)
            >>> print(formatted)

        """
        if not memories:
            return "No relevant memories found."

        lines = ["## Relevant Memories"]
        lines.append("")

        for i, memory in enumerate(memories, 1):
            # Memory header - extract string value from memory_type
            if hasattr(memory.memory_type, "value"):
                # It's an Enum
                memory_type = memory.memory_type.value
            elif isinstance(memory.memory_type, str):
                # It's already a string
                memory_type = memory.memory_type
            else:
                # Fallback: convert to string
                memory_type = str(memory.memory_type).lower().replace("memorytype.", "")

            timestamp = memory.timestamp.strftime("%Y-%m-%d %H:%M")
            lines.append(f"### Memory {i} ({memory_type}, {timestamp})")

            # Memory content
            lines.append(f"**Content**: {memory.content}")

            # Type-specific details
            if memory.memory_type == MemoryType.EPISODIC:
                from Agent_Guru.reasoning.models.memory import EpisodicMemory

                if isinstance(memory, EpisodicMemory):
                    lines.append(f"**Action**: {memory.action_taken}")
                    lines.append(f"**Result**: {memory.result}")
                    lines.append(f"**Success**: {memory.success}")

            elif memory.memory_type == MemoryType.SEMANTIC:
                from Agent_Guru.reasoning.models.memory import SemanticMemory

                if isinstance(memory, SemanticMemory):
                    lines.append(f"**Fact**: {memory.fact}")
                    lines.append(f"**Confidence**: {memory.confidence:.2f}")

            elif memory.memory_type == MemoryType.PREFERENCE:
                from Agent_Guru.reasoning.models.memory import PreferenceMemory

                if isinstance(memory, PreferenceMemory):
                    lines.append(
                        f"**Preference**: {memory.preference_key} = {memory.preference_value}",
                    )
                    lines.append(f"**Learned From**: {memory.learned_from}")

            elif memory.memory_type == MemoryType.TASK:
                from Agent_Guru.reasoning.models.memory import TaskMemory

                if isinstance(memory, TaskMemory):
                    lines.append(f"**Task**: {memory.task_description}")
                    lines.append(f"**Outcome**: {memory.outcome}")
                    if memory.lessons_learned:
                        lessons = ", ".join(memory.lessons_learned)
                        lines.append(f"**Lessons**: {lessons}")

            # Relevance score
            lines.append(f"**Relevance**: {memory.relevance_score:.2f}")
            lines.append("")

        return "\n".join(lines)

    def track_memory_usage(self, memory_ids: list[UUID]) -> None:
        """Track memory usage for relevance scoring.

        Time Complexity: O(k) where k=len(memory_ids)
        Space Complexity: O(k) for new usage stats

        This method tracks which memories were used in reasoning, updating
        usage counts and timestamps for relevance scoring.

        Args:
            memory_ids: List of memory IDs that were used

        Example:
            >>> integration = MemoryLLMIntegration(memory_retriever)
            >>> integration.track_memory_usage(context.memory_ids)

        """
        now = datetime.now(tz=UTC)

        for memory_id in memory_ids:
            if memory_id in self.usage_stats:
                # Update existing stats
                stats = self.usage_stats[memory_id]
                stats.usage_count += 1
                stats.last_used = now
                # Increase boost with diminishing returns
                stats.relevance_boost = min(
                    0.5,  # Max boost of 0.5
                    stats.relevance_boost + self.relevance_boost_factor / stats.usage_count,
                )
            else:
                # Create new stats
                self.usage_stats[memory_id] = MemoryUsageStats(
                    memory_id=memory_id,
                    usage_count=1,
                    last_used=now,
                    relevance_boost=self.relevance_boost_factor,
                )

    def update_relevance_from_usage(self) -> int:
        """Update memory relevance scores based on usage patterns.

        Time Complexity: O(u) where u=len(usage_stats)
        Space Complexity: O(1)

        This method updates the relevance scores of memories based on their
        usage patterns. Frequently used memories get higher relevance scores.

        Returns:
            Number of memories updated

        Example:
            >>> integration = MemoryLLMIntegration(memory_retriever)
            >>> updated_count = integration.update_relevance_from_usage()
            >>> print(f"Updated {updated_count} memories")

        """
        updated_count = 0

        for memory_id, stats in self.usage_stats.items():
            try:
                # Get current memory
                memory = self.memory_retriever.memories.get(memory_id)
                if memory is None:
                    continue

                # Calculate new relevance score
                # Base score + usage boost, clamped to [0.0, 1.0]
                new_score = min(1.0, memory.relevance_score + stats.relevance_boost)

                # Update relevance
                self.memory_retriever.update_relevance(memory_id, new_score)
                updated_count += 1

            except ValueError:
                # Memory not found, skip
                continue

        return updated_count

    def get_usage_stats(self, memory_id: UUID) -> MemoryUsageStats | None:
        """Get usage statistics for a memory.

        Args:
            memory_id: ID of memory to get stats for

        Returns:
            MemoryUsageStats if found, None otherwise

        """
        return self.usage_stats.get(memory_id)

    def clear_usage_stats(self) -> None:
        """Clear all usage statistics."""
        self.usage_stats.clear()

    def _build_query_from_intent(self, intent: Intent) -> str:
        """Build search query from intent.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            intent: Intent object to build query from

        Returns:
            Query string for semantic search

        """
        # Start with intent type
        query_parts = [intent.intent_type.value.replace("_", " ")]

        # Add entity values from Entity objects
        from Agent_Guru.reasoning.models.intent import Entity

        for entity in intent.entities.values():
            if isinstance(entity, Entity):
                # Use raw_text for better semantic matching
                query_parts.append(entity.raw_text)

        return " ".join(query_parts)
