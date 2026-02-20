"""
Tests for memory pruning and retention policy.

This module tests the memory pruning functionality including importance scoring,
automatic pruning, retention policies, and user control over memory deletion.

Coverage Target: 80%+ for all pruning methods
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from Agent_Guru.reasoning.memory_retriever import MemoryRetriever
from Agent_Guru.reasoning.models.memory import (
    EpisodicMemory,
    MemoryType,
    PreferenceMemory,
    SemanticMemory,
    TaskMemory,
)


class TestImportanceScoring:
    """Tests for compute_importance_score method."""

    def test_importance_score_range(self):
        """Test that importance scores are in valid range 0.0-1.0."""
        retriever = MemoryRetriever()

        memory = EpisodicMemory(
            content="Test memory",
            action_taken="test_action",
            result="success",
            success=True,
            user_id="user_123",
        )

        score = retriever.compute_importance_score(memory)
        assert 0.0 <= score <= 1.0

    def test_importance_score_recent_memory(self):
        """Test that recent memories have higher importance."""
        retriever = MemoryRetriever()

        # Recent memory
        recent = EpisodicMemory(
            content="Recent memory",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
            timestamp=datetime.utcnow(),
        )

        # Old memory
        old = EpisodicMemory(
            content="Old memory",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
            timestamp=datetime.utcnow() - timedelta(days=80),
        )

        recent_score = retriever.compute_importance_score(recent)
        old_score = retriever.compute_importance_score(old)

        assert recent_score > old_score

    def test_importance_score_high_relevance(self):
        """Test that high relevance increases importance."""
        retriever = MemoryRetriever()

        high_relevance = EpisodicMemory(
            content="High relevance",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
            relevance_score=0.9,
        )

        low_relevance = EpisodicMemory(
            content="Low relevance",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
            relevance_score=0.1,
        )

        high_score = retriever.compute_importance_score(high_relevance)
        low_score = retriever.compute_importance_score(low_relevance)

        assert high_score > low_score

    def test_importance_score_usage_tracking(self):
        """Test that retrieval count increases importance."""
        retriever = MemoryRetriever()

        # Memory with high usage
        high_usage = EpisodicMemory(
            content="High usage",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
            metadata={"retrieval_count": 50},
        )

        # Memory with low usage
        low_usage = EpisodicMemory(
            content="Low usage",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
            metadata={"retrieval_count": 1},
        )

        high_score = retriever.compute_importance_score(high_usage)
        low_score = retriever.compute_importance_score(low_usage)

        assert high_score > low_score

    def test_importance_score_memory_type_weights(self):
        """Test that different memory types have different importance."""
        retriever = MemoryRetriever()

        # Create memories of different types with same other attributes
        timestamp = datetime.utcnow()

        semantic = SemanticMemory(
            content="Semantic memory",
            fact="test_fact",
            source="user",
            confidence=1.0,
            user_id="user_123",
            timestamp=timestamp,
            relevance_score=0.5,
        )

        preference = PreferenceMemory(
            content="Preference memory",
            preference_key="test_key",
            preference_value="test_value",
            learned_from="explicit",
            user_id="user_123",
            timestamp=timestamp,
            relevance_score=0.5,
        )

        task = TaskMemory(
            content="Task memory",
            task_id="task_123",
            task_description="Test task",
            outcome="success",
            user_id="user_123",
            timestamp=timestamp,
            relevance_score=0.5,
        )

        episodic = EpisodicMemory(
            content="Episodic memory",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
            timestamp=timestamp,
            relevance_score=0.5,
        )

        semantic_score = retriever.compute_importance_score(semantic)
        preference_score = retriever.compute_importance_score(preference)
        task_score = retriever.compute_importance_score(task)
        episodic_score = retriever.compute_importance_score(episodic)

        # Semantic should be highest, episodic lowest
        assert semantic_score > preference_score > task_score > episodic_score


class TestMemoryPruning:
    """Tests for prune_memories method."""

    def test_prune_low_importance_memories(self):
        """Test that low-importance memories are pruned."""
        retriever = MemoryRetriever()

        # Add high-importance memory
        high_importance = EpisodicMemory(
            content="High importance",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
            relevance_score=0.9,
            timestamp=datetime.utcnow(),
        )
        retriever.store(high_importance)

        # Add low-importance memory (old + low relevance)
        low_importance = EpisodicMemory(
            content="Low importance",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
            relevance_score=0.1,
            timestamp=datetime.utcnow() - timedelta(days=80),
        )
        retriever.store(low_importance)

        # Prune with threshold 0.3
        pruned = retriever.prune_memories(
            user_id="user_123", importance_threshold=0.3, keep_minimum=0
        )

        assert pruned == 1
        assert retriever.get_memory_count("user_123") == 1
        assert high_importance.memory_id in retriever.memories
        assert low_importance.memory_id not in retriever.memories

    def test_prune_respects_minimum_count(self):
        """Test that pruning respects keep_minimum parameter."""
        retriever = MemoryRetriever()

        # Add 5 low-importance memories
        for i in range(5):
            memory = EpisodicMemory(
                content=f"Memory {i}",
                action_taken="test",
                result="success",
                success=True,
                user_id="user_123",
                relevance_score=0.1,
                timestamp=datetime.utcnow() - timedelta(days=80),
            )
            retriever.store(memory)

        # Prune with keep_minimum=3
        pruned = retriever.prune_memories(
            user_id="user_123", importance_threshold=0.5, keep_minimum=3  # High threshold
        )

        # Should keep 3 memories even though all are below threshold
        assert retriever.get_memory_count("user_123") == 3
        assert pruned == 2

    def test_prune_protects_high_importance(self):
        """Test that high-importance memories are protected from pruning."""
        retriever = MemoryRetriever()

        # Add high-importance memory (recent + high relevance + high usage = high importance)
        high_importance = SemanticMemory(
            content="Important fact",
            fact="critical_info",
            source="user",
            confidence=1.0,
            user_id="user_123",
            relevance_score=1.0,  # Maximum relevance
            timestamp=datetime.utcnow() - timedelta(days=10),  # Very recent
            metadata={"retrieval_count": 50},  # High usage
        )
        retriever.store(high_importance)

        # Add low-importance memory (old + low relevance = low importance)
        low_importance = EpisodicMemory(
            content="Low importance",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
            relevance_score=0.2,
            timestamp=datetime.utcnow() - timedelta(days=100),
        )
        retriever.store(low_importance)

        # Verify importance scores
        high_score = retriever.compute_importance_score(high_importance)
        low_score = retriever.compute_importance_score(low_importance)
        assert high_score >= 0.7  # Should be protected
        assert low_score < 0.7  # Should not be protected

        # Prune with age limit
        pruned = retriever.prune_memories(
            user_id="user_123", max_age_days=90, protect_high_importance=0.7, keep_minimum=0
        )

        # High-importance memory should be protected
        assert high_importance.memory_id in retriever.memories
        assert low_importance.memory_id not in retriever.memories
        assert pruned == 1

    def test_prune_by_age_limit(self):
        """Test that memories older than max_age_days are pruned."""
        retriever = MemoryRetriever()

        # Add recent memory
        recent = EpisodicMemory(
            content="Recent",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
            timestamp=datetime.utcnow() - timedelta(days=30),
        )
        retriever.store(recent)

        # Add old memory
        old = EpisodicMemory(
            content="Old",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
            timestamp=datetime.utcnow() - timedelta(days=100),
        )
        retriever.store(old)

        # Prune with age limit
        pruned = retriever.prune_memories(user_id="user_123", max_age_days=90, keep_minimum=0)

        assert pruned == 1
        assert recent.memory_id in retriever.memories
        assert old.memory_id not in retriever.memories

    def test_prune_only_user_memories(self):
        """Test that pruning only affects specified user's memories."""
        retriever = MemoryRetriever()

        # Add memories for user1
        user1_memory = EpisodicMemory(
            content="User 1 memory",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_1",
            relevance_score=0.1,
            timestamp=datetime.utcnow() - timedelta(days=80),
        )
        retriever.store(user1_memory)

        # Add memories for user2
        user2_memory = EpisodicMemory(
            content="User 2 memory",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_2",
            relevance_score=0.1,
            timestamp=datetime.utcnow() - timedelta(days=80),
        )
        retriever.store(user2_memory)

        # Prune user1's memories
        pruned = retriever.prune_memories(
            user_id="user_1", importance_threshold=0.5, keep_minimum=0
        )

        # Only user1's memory should be pruned
        assert pruned == 1
        assert user1_memory.memory_id not in retriever.memories
        assert user2_memory.memory_id in retriever.memories

    def test_prune_invalid_parameters(self):
        """Test that invalid parameters raise ValueError."""
        retriever = MemoryRetriever()

        with pytest.raises(ValueError, match="importance_threshold"):
            retriever.prune_memories("user_123", importance_threshold=1.5)

        with pytest.raises(ValueError, match="protect_high_importance"):
            retriever.prune_memories("user_123", protect_high_importance=-0.1)

        with pytest.raises(ValueError, match="keep_minimum"):
            retriever.prune_memories("user_123", keep_minimum=-1)

        with pytest.raises(ValueError, match="max_age_days"):
            retriever.prune_memories("user_123", max_age_days=0)

    def test_prune_no_memories_below_minimum(self):
        """Test that pruning returns 0 when memory count is below minimum."""
        retriever = MemoryRetriever()

        # Add only 2 memories
        for i in range(2):
            memory = EpisodicMemory(
                content=f"Memory {i}",
                action_taken="test",
                result="success",
                success=True,
                user_id="user_123",
            )
            retriever.store(memory)

        # Try to prune with keep_minimum=100
        pruned = retriever.prune_memories(user_id="user_123", keep_minimum=100)

        assert pruned == 0
        assert retriever.get_memory_count("user_123") == 2


class TestUserMemoryControl:
    """Tests for user control over memory deletion."""

    def test_delete_memory_success(self):
        """Test successful deletion of a specific memory."""
        retriever = MemoryRetriever()

        memory = EpisodicMemory(
            content="Test memory",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
        )
        retriever.store(memory)

        # Delete the memory
        deleted = retriever.delete_memory(memory.memory_id, "user_123")

        assert deleted is True
        assert memory.memory_id not in retriever.memories
        assert retriever.get_memory_count("user_123") == 0

    def test_delete_memory_not_found(self):
        """Test deletion of non-existent memory returns False."""
        retriever = MemoryRetriever()

        deleted = retriever.delete_memory(uuid4(), "user_123")

        assert deleted is False

    def test_delete_memory_unauthorized(self):
        """Test that users can only delete their own memories."""
        retriever = MemoryRetriever()

        memory = EpisodicMemory(
            content="User 1 memory",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_1",
        )
        retriever.store(memory)

        # Try to delete as different user
        deleted = retriever.delete_memory(memory.memory_id, "user_2")

        assert deleted is False
        assert memory.memory_id in retriever.memories

    def test_delete_memories_by_type(self):
        """Test deletion of all memories of a specific type."""
        retriever = MemoryRetriever()

        # Add episodic memories
        for i in range(3):
            memory = EpisodicMemory(
                content=f"Episodic {i}",
                action_taken="test",
                result="success",
                success=True,
                user_id="user_123",
            )
            retriever.store(memory)

        # Add semantic memory
        semantic = SemanticMemory(
            content="Semantic memory",
            fact="test_fact",
            source="user",
            confidence=1.0,
            user_id="user_123",
        )
        retriever.store(semantic)

        # Delete all episodic memories
        deleted = retriever.delete_memories_by_type("user_123", MemoryType.EPISODIC)

        assert deleted == 3
        assert retriever.get_memory_count("user_123") == 1
        assert semantic.memory_id in retriever.memories

    def test_delete_memories_by_type_only_user(self):
        """Test that deletion by type only affects specified user."""
        retriever = MemoryRetriever()

        # Add episodic memory for user1
        user1_memory = EpisodicMemory(
            content="User 1 episodic",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_1",
        )
        retriever.store(user1_memory)

        # Add episodic memory for user2
        user2_memory = EpisodicMemory(
            content="User 2 episodic",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_2",
        )
        retriever.store(user2_memory)

        # Delete user1's episodic memories
        deleted = retriever.delete_memories_by_type("user_1", MemoryType.EPISODIC)

        assert deleted == 1
        assert user1_memory.memory_id not in retriever.memories
        assert user2_memory.memory_id in retriever.memories


class TestRetrievalCountTracking:
    """Tests for retrieval count tracking in retrieve method."""

    def test_retrieve_updates_count(self):
        """Test that retrieve() updates retrieval_count in metadata."""
        retriever = MemoryRetriever()

        memory = EpisodicMemory(
            content="Test memory for retrieval tracking",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
        )
        retriever.store(memory)

        # Retrieve the memory
        results = retriever.retrieve("test", "user_123")

        assert len(results) == 1
        assert results[0].metadata.get("retrieval_count", 0) == 1

        # Retrieve again
        results = retriever.retrieve("test", "user_123")
        assert results[0].metadata.get("retrieval_count", 0) == 2

    def test_retrieval_count_affects_importance(self):
        """Test that retrieval count affects importance scoring."""
        retriever = MemoryRetriever()

        # Create two identical memories
        memory1 = EpisodicMemory(
            content="Memory 1",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
            relevance_score=0.5,
            timestamp=datetime.utcnow(),
        )
        retriever.store(memory1)

        memory2 = EpisodicMemory(
            content="Memory 2",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
            relevance_score=0.5,
            timestamp=datetime.utcnow(),
        )
        retriever.store(memory2)

        # Simulate high usage for memory1
        memory1.metadata["retrieval_count"] = 50
        retriever.memories[memory1.memory_id] = memory1

        # Compute importance scores
        score1 = retriever.compute_importance_score(memory1)
        score2 = retriever.compute_importance_score(memory2)

        # Memory1 should have higher importance due to usage
        assert score1 > score2


class TestEmbeddingsRebuild:
    """Tests for embeddings array rebuild after deletion."""

    def test_embeddings_rebuild_after_delete(self):
        """Test that embeddings array is correctly rebuilt after deletion."""
        retriever = MemoryRetriever()

        # Add multiple memories
        memories = []
        for i in range(5):
            memory = EpisodicMemory(
                content=f"Memory {i}",
                action_taken="test",
                result="success",
                success=True,
                user_id="user_123",
            )
            retriever.store(memory)
            memories.append(memory)

        initial_shape = retriever.embeddings.shape
        assert initial_shape[0] == 5

        # Delete one memory
        retriever.delete_memory(memories[2].memory_id, "user_123")

        # Check embeddings shape
        assert retriever.embeddings.shape[0] == 4
        assert retriever.embeddings.shape[1] == 768

    def test_embeddings_none_after_delete_all(self):
        """Test that embeddings is None after deleting all memories."""
        retriever = MemoryRetriever()

        memory = EpisodicMemory(
            content="Test memory",
            action_taken="test",
            result="success",
            success=True,
            user_id="user_123",
        )
        retriever.store(memory)

        # Delete the memory
        retriever.delete_memory(memory.memory_id, "user_123")

        assert retriever.embeddings is None
        assert len(retriever.memory_ids) == 0
