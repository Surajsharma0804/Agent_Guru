"""Memory Storage Pipeline for automatic memory creation and storage.

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
from datetime import UTC, datetime
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
        vector_db: VectorDatabase | None = None,
        embedding_generator: EmbeddingGenerator | None = None,
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
            msg = f"deduplication_threshold must be 0.0-1.0, got {deduplication_threshold}"
            raise ValueError(
                msg,
            )
        if deduplication_window_hours < 1:
            msg = f"deduplication_window_hours must be >= 1, got {deduplication_window_hours}"
            raise ValueError(
                msg,
            )
        if min_content_length < 1:
            msg = f"min_content_length must be >= 1, got {min_content_length}"
            raise ValueError(msg)
        if max_memories_per_user < 100:
            msg = f"max_memories_per_user must be >= 100, got {max_memories_per_user}"
            raise ValueError(msg)

        # Initialize components
        self.vector_db = vector_db or VectorDatabase(
            db_path="./memory_db",
            embedding_dimension=384,
            in_memory=False,
        )
        self.embedding_generator = embedding_generator or EmbeddingGenerator()

        # Validate embedding dimension matches
        expected_dim = self.embedding_generator.get_embedding_dimension()
        if expected_dim != self.vector_db.embedding_dimension:
            msg = (
                f"Embedding dimension mismatch: generator={expected_dim}, "
                f"database={self.vector_db.embedding_dimension}"
            )
            raise ValueError(
                msg,
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
            "MemoryStoragePipeline initialized with dedup_threshold=%s, dedup_window=%sh",
            deduplication_threshold,
            deduplication_window_hours,
        )

    async def store_episodic(
        self,
        user_id: str,
        content: str,
        action_taken: str,
        result: str,
        success: bool,
        context: dict | None = None,
    ) -> UUID | None:
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
    ) -> UUID | None:
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
    ) -> UUID | None:
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
        lessons_learned: list[str] | None = None,
    ) -> UUID | None:
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

    async def _store_memory(self, memory: Memory) -> UUID | None:
        """Store a memory with deduplication check.

        Time Complexity: O(log n) with semantic search
        Space Complexity: O(d) where d=embedding_dim

        Args:
            memory: Memory object to store

        Returns:
            Memory ID if stored, None if deduplicated

        """
        # BUG FIX (Round 20): every operation in this critical section --
        # vector_db.count(), embedding_generator.generate(),
        # vector_db.search() (inside _is_duplicate), vector_db.store() --
        # is a BLOCKING, synchronous call (ChromaDB's Python client isn't
        # async, and real sentence-transformer inference is documented
        # elsewhere in this codebase as costing ~20-200ms). All of them used
        # to run directly on the event loop while ALSO holding self._lock,
        # meaning every memory-store call for EVERY user was serialized
        # behind a single lock AND froze the entire event loop -- all other
        # concurrent async work (voice pipeline callbacks, other users'
        # requests, IPC) -- for the full duration of an embedding
        # computation plus a database write, every single time. Each
        # blocking call now runs via run_in_executor so it no longer stalls
        # the event loop; the lock is kept around the whole sequence
        # (unchanged) because the count-check-then-store and
        # dedup-check-then-store logic below is a genuine check-then-act
        # that still needs to stay serialized per pipeline instance.
        loop = asyncio.get_running_loop()
        async with self._lock:
            # Check if user has too many memories.
            # BUG FIX (Round 20): now scoped to this user via vector_db's
            # new user_id parameter -- previously this counted ALL users'
            # memories of this type combined, so max_memories_per_user was
            # actually a shared global cap: one busy user could exhaust it
            # and silently block storage for every other user.
            memory_count = await loop.run_in_executor(
                None, self.vector_db.count, memory.memory_type, memory.user_id,
            )
            if memory_count >= self.max_memories_per_user:
                logger.warning(
                    "User %s has %d memories, skipping storage (max=%d)",
                    memory.user_id,
                    memory_count,
                    self.max_memories_per_user,
                )
                return None

            # Generate embedding
            embedding = await loop.run_in_executor(
                None, self.embedding_generator.generate, memory.content,
            )

            # Check for duplicates
            is_duplicate = await self._is_duplicate(memory.memory_type, memory.user_id, embedding)

            if is_duplicate:
                logger.debug(
                    "Skipping duplicate memory for user %s: %s...",
                    memory.user_id,
                    memory.content[:50],
                )
                return None

            # Store in vector database
            try:
                await loop.run_in_executor(
                    None,
                    lambda: self.vector_db.store(
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
                    ),
                )

                # Update recent memory cache
                cache_key = f"{memory.user_id}:{memory.memory_type.value}"
                if cache_key not in self._recent_memory_ids:
                    self._recent_memory_ids[cache_key] = set()
                self._recent_memory_ids[cache_key].add(memory.memory_id)

                logger.info(
                    "Stored %s memory %s for user %s",
                    memory.memory_type.value,
                    memory.memory_id,
                    memory.user_id,
                )

                return memory.memory_id

            except Exception:
                logger.exception("Failed to store memory")
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
        # BUG FIX (Round 20): completes the fix started in _store_memory() --
        # this was still a blocking, synchronous ChromaDB call made directly
        # on the event loop (and, via _store_memory()'s caller, while holding
        # self._lock), stalling all other concurrent async work for the
        # duration of the vector search every time a memory was stored.
        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.vector_db.search(
                    memory_type=memory_type,
                    query_embedding=embedding,
                    user_id=user_id,
                    top_k=1,
                    min_similarity=self.deduplication_threshold,
                ),
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
                age_hours = (datetime.now(tz=UTC) - memory_timestamp).total_seconds() / 3600

                # Duplicate if within time window
                if age_hours <= self.deduplication_window_hours:
                    logger.debug(
                        "Found duplicate memory (similarity=%.3f, age=%.1fh)",
                        similarity,
                        age_hours,
                    )
                    return True

            except (ValueError, TypeError):
                logger.exception("Failed to parse timestamp")
                return False

            return False

        except Exception:
            logger.exception("Deduplication check failed")
            # On error, allow storage (fail open)
            return False

    def get_storage_stats(self, user_id: str | None = None) -> dict[str, int]:
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
        # BUG FIX (Round 20): this previously ignored its own `user_id`
        # parameter entirely and always passed vector_db.count() only a
        # memory_type -- so "get_storage_stats(user_id='alice')" silently
        # returned the GLOBAL count across every user for each memory type,
        # not alice's own counts. Now forwarded to vector_db.count()'s new
        # user_id filter.
        stats = {}
        for memory_type in MemoryType:
            count = self.vector_db.count(memory_type, user_id)
            stats[memory_type.value] = count

        return stats

    def clear_cache(self) -> None:
        """Clear the recent memory ID cache.

        This should be called periodically to prevent unbounded memory growth.
        """
        self._recent_memory_ids.clear()
        logger.debug("Cleared recent memory ID cache")
