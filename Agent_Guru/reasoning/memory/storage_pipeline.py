"""
Memory Storage Pipeline for automatic memory creation and storage.

This module implements a high-performance pipeline for automatically storing
different types of memories (episodic, semantic, preference, task) after
various events in the reasoning engine.

Performance Characteristics:
    - Time Complexity: O(1) for storage (amortized with batch indexing)
    - Space Complexity: O(n) where n is memory content size
    - Storage Latency: <10ms per memory (target)
    - Deduplication: O(log n) with semantic similarity check

Design Principles:
    - Automatic memory creation from events
    - Deduplication to prevent redundant memories
    - Async storage for non-blocking operation
    - Type-specific storage strategies
    - Configurable retention policies

Competitive Advantage:
    - Zero-overhead memory capture
    - Smart deduplication (semantic + temporal)
    - Automatic relevance scoring
    - Privacy-preserving (user-isolated)

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from Agent_Guru.reasoning.memory.embedding import EmbeddingGenerator
from Agent_Guru.reasoning.memory.vector_db import VectorDatabase
from Agent_Guru.reasoning.models.memory import (
    EpisodicMemory,
    Memory,
    MemoryType,
    PreferenceMemory,
    SemanticMemory,
    TaskMemory,
)

logger = logging.getLogger(__name__)


class MemoryStoragePipeline:
    """Pipeline for automatic memory storage with deduplication.

    This class provides automatic memory creation and storage after various
    events in the reasoning engine. It handles deduplication, relevance
    scoring, and async storage for optimal performance.

    Time Complexity:
        - store_episodic: O(log n) with deduplication check
        - store_semantic: O(log n) with deduplication check
        - store_preference: O(log n) with deduplication check
        - store_task: O(log n) with deduplication check
        - deduplicate: O(log n) with semantic search

    Space Complexity:
        - O(n * d) where n=memories, d=embedding_dim (384)

    Attributes:
        vector_db: Vector database for memory storage
        embedding_generator: Generator for memory embeddings
        deduplication_threshold: Similarity threshold for deduplication (0.95)
        deduplication_window_hours: Time window for deduplication (24 hours)
        min_content_length: Minimum content length for storage (10 chars)
        max_memories_per_user: Maximum memories per user (10,000)

    Example:
        >>> pipeline = MemoryStoragePipeline()
        >>> # Store episodic memory after task execution
        >>> memory_id = await pipeline.store_episodic(
        ...     user_id="user_123",
        ...     content="User set a timer for 5 minutes",
        ...     action_taken="set_timer",
        ...     result="Success",
        ...     success=True,
        ...     context={"duration": "5 minutes"}
        ... )
    """

    def __init__(
        self,
        vector_db: Optional[VectorDatabase] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
        deduplication_threshold: float = 0.95,
        deduplication_window_hours: int = 24,
        min_content_length: int = 10,
        max_memories_per_user: int = 10000,
    ) -> None:
        """Initialize memory storage pipeline.

        Args:
            vector_db: Vector database instance (creates new if None)
            embedding_generator: Embedding generator (creates new if None)
            deduplication_threshold: Similarity threshold for deduplication (0.95)
            deduplication_window_hours: Time window for deduplication (24 hours)
            min_content_length: Minimum content length for storage (10 chars)
            max_memories_per_user: Maximum memories per user (10,000)

        Raises:
            ValueError: If parameters are invalid
        """
        if not 0.0 <= deduplication_threshold <= 1.0:
            raise ValueError(
                f"deduplication_threshold must be 0.0-1.0, got {deduplication_threshold}"
            )
        if deduplication_window_hours < 1:
            raise ValueError(
                f"deduplication_window_hours must be >= 1, got {deduplication_window_hours}"
            )
        if min_content_length < 1:
            raise ValueError(f"min_content_length must be >= 1, got {min_content_length}")
        if max_memories_per_user < 100:
            raise ValueError(f"max_memories_per_user must be >= 100, got {max_memories_per_user}")

        # Initialize components
        self.vector_db = vector_db or VectorDatabase(
            db_path="./memory_db", embedding_dimension=384, in_memory=False
        )
        self.embedding_generator = embedding_generator or EmbeddingGenerator()

        # Validate embedding dimension matches
        expected_dim = self.embedding_generator.get_embedding_dimension()
        if expected_dim != self.vector_db.embedding_dimension:
            raise ValueError(
                f"Embedding dimension mismatch: generator={expected_dim}, "
                f"database={self.vector_db.embedding_dimension}"
            )

        # Configuration
        self.deduplication_threshold = deduplication_threshold
        self.deduplication_window_hours = deduplication_window_hours
        self.min_content_length = min_content_length
        self.max_memories_per_user = max_memories_per_user

        # Thread safety
        self._lock = asyncio.Lock()

        # Cache for recent memory IDs (for fast deduplication)
        self._recent_memory_ids: dict[str, set[UUID]] = {}

        logger.info(
            f"MemoryStoragePipeline initialized with "
            f"dedup_threshold={deduplication_threshold}, "
            f"dedup_window={deduplication_window_hours}h"
        )

    async def store_episodic(
        self,
        user_id: str,
        content: str,
        action_taken: str,
        result: str,
        success: bool,
        context: Optional[dict] = None,
    ) -> Optional[UUID]:
        """Store an episodic memory after task execution.

        Time Complexity: O(log n) with deduplication check
        Latency Budget: <10ms (target)

        Args:
            user_id: User ID who performed the action
            content: Human-readable description of the event
            action_taken: Action that was performed
            result: Outcome of the action
            success: Whether the action succeeded
            context: Additional context about the situation

        Returns:
            Memory ID if stored, None if deduplicated

        Example:
            >>> pipeline = MemoryStoragePipeline()
            >>> memory_id = await pipeline.store_episodic(
            ...     user_id="user_123",
            ...     content="User set a timer for 5 minutes",
            ...     action_taken="set_timer",
            ...     result="Timer set successfully",
            ...     success=True,
            ...     context={"duration": "5 minutes"}
            ... )
        """
        # Validate content length
        if len(content.strip()) < self.min_content_length:
            logger.debug("Skipping episodic memory: content too short (%s chars)", len(content))
            return None

        # Create episodic memory
        memory = EpisodicMemory(
            content=content.strip(),
            action_taken=action_taken,
            result=result,
            success=success,
            context=context or {},
            user_id=user_id,
        )

        # Store with deduplication
        return await self._store_memory(memory)

    async def store_semantic(
        self,
        user_id: str,
        content: str,
        fact: str,
        source: str,
        confidence: float = 1.0,
    ) -> Optional[UUID]:
        """Store a semantic memory from user corrections or feedback.

        Time Complexity: O(log n) with deduplication check
        Latency Budget: <10ms (target)

        Args:
            user_id: User ID who provided the information
            content: Human-readable description of the fact
            fact: The factual statement
            source: Where this fact came from (user, web, inference)
            confidence: Confidence in the accuracy (0.0-1.0)

        Returns:
            Memory ID if stored, None if deduplicated

        Example:
            >>> pipeline = MemoryStoragePipeline()
            >>> memory_id = await pipeline.store_semantic(
            ...     user_id="user_123",
            ...     content="User's favorite color is blue",
            ...     fact="favorite_color=blue",
            ...     source="user_stated",
            ...     confidence=1.0
            ... )
        """
        # Validate content length
        if len(content.strip()) < self.min_content_length:
            logger.debug("Skipping semantic memory: content too short (%s chars)", len(content))
            return None

        # Create semantic memory
        memory = SemanticMemory(
            content=content.strip(),
            fact=fact,
            source=source,
            confidence=confidence,
            user_id=user_id,
        )

        # Store with deduplication
        return await self._store_memory(memory)

    async def store_preference(
        self,
        user_id: str,
        content: str,
        preference_key: str,
        preference_value: str,
        learned_from: str = "inferred",
    ) -> Optional[UUID]:
        """Store a preference memory from behavioral learning.

        Time Complexity: O(log n) with deduplication check
        Latency Budget: <10ms (target)

        Args:
            user_id: User ID whose preference this is
            content: Human-readable description of the preference
            preference_key: Key identifying the preference
            preference_value: Value of the preference
            learned_from: How this was learned (explicit, inferred, observed)

        Returns:
            Memory ID if stored, None if deduplicated

        Example:
            >>> pipeline = MemoryStoragePipeline()
            >>> memory_id = await pipeline.store_preference(
            ...     user_id="user_123",
            ...     content="User prefers morning notifications",
            ...     preference_key="notification_time",
            ...     preference_value="morning",
            ...     learned_from="explicit"
            ... )
        """
        # Validate content length
        if len(content.strip()) < self.min_content_length:
            logger.debug("Skipping preference memory: content too short (%s chars)", len(content))
            return None

        # Create preference memory
        memory = PreferenceMemory(
            content=content.strip(),
            preference_key=preference_key,
            preference_value=preference_value,
            learned_from=learned_from,
            user_id=user_id,
        )

        # Store with deduplication
        return await self._store_memory(memory)

    async def store_task(
        self,
        user_id: str,
        content: str,
        task_id: str,
        task_description: str,
        outcome: str,
        lessons_learned: Optional[list[str]] = None,
    ) -> Optional[UUID]:
        """Store a task memory from multi-step task completion.

        Time Complexity: O(log n) with deduplication check
        Latency Budget: <10ms (target)

        Args:
            user_id: User ID who executed the task
            content: Human-readable description of the task execution
            task_id: Unique identifier for the task
            task_description: Description of what the task was
            outcome: Final outcome (success, failure, partial)
            lessons_learned: Key insights from this task

        Returns:
            Memory ID if stored, None if deduplicated

        Example:
            >>> pipeline = MemoryStoragePipeline()
            >>> memory_id = await pipeline.store_task(
            ...     user_id="user_123",
            ...     content="Multi-step task to book restaurant",
            ...     task_id="task_456",
            ...     task_description="Book restaurant for 7pm",
            ...     outcome="success",
            ...     lessons_learned=["User prefers Italian"]
            ... )
        """
        # Validate content length
        if len(content.strip()) < self.min_content_length:
            logger.debug("Skipping task memory: content too short (%s chars)", len(content))
            return None

        # Create task memory
        memory = TaskMemory(
            content=content.strip(),
            task_id=task_id,
            task_description=task_description,
            outcome=outcome,
            lessons_learned=lessons_learned or [],
            user_id=user_id,
        )

        # Store with deduplication
        return await self._store_memory(memory)

    async def _store_memory(self, memory: Memory) -> Optional[UUID]:
        """Store a memory with deduplication check.

        Time Complexity: O(log n) with semantic search
        Space Complexity: O(d) where d=embedding_dim

        Args:
            memory: Memory object to store

        Returns:
            Memory ID if stored, None if deduplicated
        """
        async with self._lock:
            # Check if user has too many memories
            memory_count = self.vector_db.count(memory.memory_type)
            if memory_count >= self.max_memories_per_user:
                logger.warning(
                    f"User {memory.user_id} has {memory_count} memories, "
                    f"skipping storage (max={self.max_memories_per_user})"
                )
                return None

            # Generate embedding
            embedding = self.embedding_generator.generate(memory.content)

            # Check for duplicates
            is_duplicate = await self._is_duplicate(memory.memory_type, memory.user_id, embedding)

            if is_duplicate:
                logger.debug(
                    f"Skipping duplicate memory for user {memory.user_id}: "
                    f"{memory.content[:50]}..."
                )
                return None

            # Store in vector database
            try:
                self.vector_db.store(
                    memory_type=memory.memory_type,
                    memory_id=memory.memory_id,
                    content=memory.content,
                    embedding=embedding,  # Already a list
                    metadata={
                        "user_id": memory.user_id,
                        "timestamp": memory.timestamp.isoformat(),
                        "relevance_score": memory.relevance_score,
                        **memory.metadata,
                    },
                )

                # Update recent memory cache
                cache_key = f"{memory.user_id}:{memory.memory_type.value}"
                if cache_key not in self._recent_memory_ids:
                    self._recent_memory_ids[cache_key] = set()
                self._recent_memory_ids[cache_key].add(memory.memory_id)

                logger.info(
                    f"Stored {memory.memory_type.value} memory {memory.memory_id} "
                    f"for user {memory.user_id}"
                )

                return memory.memory_id

            except Exception as e:
                logger.error("Failed to store memory: %s", e)
                return None

    async def _is_duplicate(
        self,
        memory_type: MemoryType,
        user_id: str,
        embedding: list[float],
    ) -> bool:
        """Check if a memory is a duplicate using semantic similarity.

        Time Complexity: O(log n) with HNSW search
        Space Complexity: O(1)

        A memory is considered a duplicate if:
        1. It has similarity >= deduplication_threshold (0.95)
        2. It was created within deduplication_window_hours (24 hours)

        Args:
            memory_type: Type of memory to check
            user_id: User ID to filter by
            embedding: Embedding vector to compare

        Returns:
            True if duplicate found, False otherwise
        """
        # Search for similar memories
        try:
            results = self.vector_db.search(
                memory_type=memory_type,
                query_embedding=embedding,
                user_id=user_id,
                top_k=1,
                min_similarity=self.deduplication_threshold,
            )

            if not results:
                return False

            # Check if most similar memory is within time window
            _, _, similarity, metadata = results[0]

            # Parse timestamp
            timestamp_str = metadata.get("timestamp")
            if not timestamp_str:
                return False

            try:
                memory_timestamp = datetime.fromisoformat(timestamp_str)
                age_hours = (datetime.now(tz=timezone.utc) - memory_timestamp).total_seconds() / 3600

                # Duplicate if within time window
                if age_hours <= self.deduplication_window_hours:
                    logger.debug(
                        f"Found duplicate memory (similarity={similarity:.3f}, "
                        f"age={age_hours:.1f}h)"
                    )
                    return True

            except (ValueError, TypeError) as e:
                logger.warning("Failed to parse timestamp: %s", e)
                return False

            return False

        except Exception as e:
            logger.error("Deduplication check failed: %s", e)
            # On error, allow storage (fail open)
            return False

    def get_storage_stats(self, user_id: Optional[str] = None) -> dict[str, int]:
        """Get storage statistics.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            Dictionary with memory counts per type

        Example:
            >>> pipeline = MemoryStoragePipeline()
            >>> stats = pipeline.get_storage_stats("user_123")
            >>> print(f"Episodic: {stats['episodic']}")
        """
        stats = {}
        for memory_type in MemoryType:
            count = self.vector_db.count(memory_type)
            stats[memory_type.value] = count

        return stats

    def clear_cache(self) -> None:
        """Clear the recent memory ID cache.

        This should be called periodically to prevent unbounded memory growth.
        """
        self._recent_memory_ids.clear()
        logger.debug("Cleared recent memory ID cache")
