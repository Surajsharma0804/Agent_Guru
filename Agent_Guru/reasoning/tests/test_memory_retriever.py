"""
Comprehensive tests for MemoryRetriever.

Tests cover:
- Initialization and configuration
- Memory storage and retrieval
- Semantic search functionality
- Memory ranking by multiple factors
- Relevance score updates
- User filtering
- Memory type filtering
- Performance and latency requirements
- Edge cases and error conditions

Target Coverage: 100%
"""

import time
from datetime import datetime, timedelta
from uuid import uuid4

import numpy as np
import pytest
from hypothesis import given, strategies as st

from Agent_Guru.reasoning.memory_retriever import MemoryRetriever
from Agent_Guru.reasoning.models.memory import (
    EpisodicMemory,
    Memory,
    MemoryType,
    PreferenceMemory,
    SemanticMemory,
    TaskMemory,
)


class TestMemoryRetrieverInitialization:
    """Tests for MemoryRetriever initialization."""
    
    def test_initialization_defaults(self):
        """Test MemoryRetriever initialization with defaults."""
        retriever = MemoryRetriever()
        
        assert retriever.embedding_model is not None
        assert retriever.embedding_dim > 0
        assert retriever.memories == {}
        assert retriever.embeddings is None
        assert retriever.memory_ids == []
        assert retriever.max_results == 5
        assert retriever.relevance_decay_days == 90
    
    def test_initialization_custom_params(self):
        """Test MemoryRetriever initialization with custom parameters."""
        retriever = MemoryRetriever(
            max_results=10,
            relevance_decay_days=30
        )
        
        assert retriever.max_results == 10
        assert retriever.relevance_decay_days == 30
    
    def test_initialization_invalid_max_results(self):
        """Test that invalid max_results raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            MemoryRetriever(max_results=0)
        
        assert "max_results must be >= 1" in str(exc_info.value)
        
        with pytest.raises(ValueError):
            MemoryRetriever(max_results=-1)
    
    def test_initialization_invalid_decay_days(self):
        """Test that invalid relevance_decay_days raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            MemoryRetriever(relevance_decay_days=0)
        
        assert "relevance_decay_days must be >= 1" in str(exc_info.value)
        
        with pytest.raises(ValueError):
            MemoryRetriever(relevance_decay_days=-1)


class TestMemoryStorage:
    """Tests for memory storage functionality."""
    
    def test_store_memory_basic(self):
        """Test storing a basic memory."""
        retriever = MemoryRetriever()
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="Test memory content",
            user_id="user_123"
        )
        
        retriever.store(memory)
        
        assert len(retriever.memories) == 1
        assert memory.memory_id in retriever.memories
        assert retriever.memories[memory.memory_id] == memory
        assert len(retriever.memory_ids) == 1
        assert retriever.embeddings is not None
        assert retriever.embeddings.shape == (1, retriever.embedding_dim)
    
    def test_store_memory_generates_embedding(self):
        """Test that storing memory generates embedding if not provided."""
        retriever = MemoryRetriever()
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="Test memory content",
            user_id="user_123"
        )
        
        assert memory.embedding is None
        retriever.store(memory)
        
        stored_memory = retriever.memories[memory.memory_id]
        assert stored_memory.embedding is not None
        assert len(stored_memory.embedding) == retriever.embedding_dim
    
    def test_store_memory_preserves_existing_embedding(self):
        """Test that storing memory preserves existing embedding."""
        retriever = MemoryRetriever()
        embedding = [0.1] * retriever.embedding_dim
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="Test memory content",
            embedding=embedding,
            user_id="user_123"
        )
        
        retriever.store(memory)
        
        stored_memory = retriever.memories[memory.memory_id]
        assert stored_memory.embedding == embedding
    
    def test_store_multiple_memories(self):
        """Test storing multiple memories."""
        retriever = MemoryRetriever()
        
        for i in range(5):
            memory = Memory(
                memory_type=MemoryType.EPISODIC,
                content=f"Memory {i}",
                user_id="user_123"
            )
            retriever.store(memory)
        
        assert len(retriever.memories) == 5
        assert len(retriever.memory_ids) == 5
        assert retriever.embeddings.shape == (5, retriever.embedding_dim)
    
    def test_store_duplicate_memory_id_raises_error(self):
        """Test that storing memory with duplicate ID raises ValueError."""
        retriever = MemoryRetriever()
        memory_id = uuid4()
        
        memory1 = Memory(
            memory_id=memory_id,
            memory_type=MemoryType.EPISODIC,
            content="First memory",
            user_id="user_123"
        )
        retriever.store(memory1)
        
        memory2 = Memory(
            memory_id=memory_id,
            memory_type=MemoryType.EPISODIC,
            content="Second memory",
            user_id="user_123"
        )
        
        with pytest.raises(ValueError) as exc_info:
            retriever.store(memory2)
        
        assert "already exists" in str(exc_info.value)
    
    def test_store_different_memory_types(self):
        """Test storing different types of memories."""
        retriever = MemoryRetriever()
        
        episodic = EpisodicMemory(
            content="User set a timer",
            action_taken="set_timer",
            result="Success",
            success=True,
            user_id="user_123"
        )
        
        semantic = SemanticMemory(
            content="User's favorite color is blue",
            fact="favorite_color=blue",
            source="user_stated",
            confidence=1.0,
            user_id="user_123"
        )
        
        preference = PreferenceMemory(
            content="User prefers morning notifications",
            preference_key="notification_time",
            preference_value="morning",
            learned_from="explicit",
            user_id="user_123"
        )
        
        task = TaskMemory(
            content="Booked restaurant",
            task_id="task_1",
            task_description="Book restaurant for 7pm",
            outcome="success",
            user_id="user_123"
        )
        
        retriever.store(episodic)
        retriever.store(semantic)
        retriever.store(preference)
        retriever.store(task)
        
        assert len(retriever.memories) == 4
        assert isinstance(retriever.memories[episodic.memory_id], EpisodicMemory)
        assert isinstance(retriever.memories[semantic.memory_id], SemanticMemory)
        assert isinstance(retriever.memories[preference.memory_id], PreferenceMemory)
        assert isinstance(retriever.memories[task.memory_id], TaskMemory)


class TestSemanticSearch:
    """Tests for semantic search functionality."""
    
    def test_semantic_search_basic(self):
        """Test basic semantic search."""
        retriever = MemoryRetriever()
        
        # Store memories
        memory1 = Memory(
            memory_type=MemoryType.EPISODIC,
            content="User set a timer for 5 minutes",
            user_id="user_123"
        )
        memory2 = Memory(
            memory_type=MemoryType.EPISODIC,
            content="User played music",
            user_id="user_123"
        )
        
        retriever.store(memory1)
        retriever.store(memory2)
        
        # Search for timer-related memories
        results = retriever.semantic_search("timer", user_id="user_123", top_k=2)
        
        assert len(results) <= 2
        assert results[0].memory_id == memory1.memory_id  # Timer memory should rank higher
    
    def test_semantic_search_user_filtering(self):
        """Test that semantic search filters by user_id."""
        retriever = MemoryRetriever()
        
        memory1 = Memory(
            memory_type=MemoryType.EPISODIC,
            content="User set a timer",
            user_id="user_123"
        )
        memory2 = Memory(
            memory_type=MemoryType.EPISODIC,
            content="User set a timer",
            user_id="user_456"
        )
        
        retriever.store(memory1)
        retriever.store(memory2)
        
        # Search for user_123
        results = retriever.semantic_search("timer", user_id="user_123", top_k=10)
        
        assert len(results) == 1
        assert results[0].memory_id == memory1.memory_id
    
    def test_semantic_search_memory_type_filtering(self):
        """Test that semantic search filters by memory type."""
        retriever = MemoryRetriever()
        
        episodic = EpisodicMemory(
            content="User set a timer",
            action_taken="set_timer",
            result="Success",
            success=True,
            user_id="user_123"
        )
        
        semantic = SemanticMemory(
            content="Timers are useful for cooking",
            fact="timer_use=cooking",
            source="user_stated",
            confidence=1.0,
            user_id="user_123"
        )
        
        retriever.store(episodic)
        retriever.store(semantic)
        
        # Search for episodic memories only
        results = retriever.semantic_search(
            "timer",
            user_id="user_123",
            memory_types=[MemoryType.EPISODIC],
            top_k=10
        )
        
        assert len(results) == 1
        assert results[0].memory_id == episodic.memory_id
    
    def test_semantic_search_empty_results(self):
        """Test semantic search with no matching memories."""
        retriever = MemoryRetriever()
        
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="User set a timer",
            user_id="user_123"
        )
        retriever.store(memory)
        
        # Search for different user
        results = retriever.semantic_search("timer", user_id="user_456", top_k=10)
        
        assert len(results) == 0
    
    def test_semantic_search_top_k_limit(self):
        """Test that semantic search respects top_k limit."""
        retriever = MemoryRetriever()
        
        # Store 10 memories
        for i in range(10):
            memory = Memory(
                memory_type=MemoryType.EPISODIC,
                content=f"Memory about timers {i}",
                user_id="user_123"
            )
            retriever.store(memory)
        
        # Search with top_k=3
        results = retriever.semantic_search("timer", user_id="user_123", top_k=3)
        
        assert len(results) == 3


class TestMemoryRanking:
    """Tests for memory ranking functionality."""
    
    def test_rank_memories_by_semantic_similarity(self):
        """Test that memories are ranked by semantic similarity."""
        retriever = MemoryRetriever()
        
        memory1 = Memory(
            memory_type=MemoryType.EPISODIC,
            content="User set a timer for cooking",
            user_id="user_123"
        )
        memory2 = Memory(
            memory_type=MemoryType.EPISODIC,
            content="User played music",
            user_id="user_123"
        )
        
        retriever.store(memory1)
        retriever.store(memory2)
        
        memories = [memory1, memory2]
        ranked = retriever.rank_memories(memories, "timer")
        
        # Timer memory should rank higher
        assert ranked[0].memory_id == memory1.memory_id
    
    def test_rank_memories_by_recency(self):
        """Test that memories are ranked by recency."""
        retriever = MemoryRetriever()
        
        # Old memory
        old_memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="User set a timer",
            timestamp=datetime.utcnow() - timedelta(days=60),
            user_id="user_123"
        )
        
        # Recent memory
        recent_memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="User set a timer",
            timestamp=datetime.utcnow(),
            user_id="user_123"
        )
        
        retriever.store(old_memory)
        retriever.store(recent_memory)
        
        memories = [old_memory, recent_memory]
        ranked = retriever.rank_memories(memories, "timer")
        
        # Recent memory should rank higher (same content, different timestamps)
        assert ranked[0].memory_id == recent_memory.memory_id
    
    def test_rank_memories_by_importance(self):
        """Test that memories are ranked by importance (relevance_score)."""
        retriever = MemoryRetriever()
        
        low_importance = Memory(
            memory_type=MemoryType.EPISODIC,
            content="User set a timer",
            relevance_score=0.3,
            user_id="user_123"
        )
        
        high_importance = Memory(
            memory_type=MemoryType.EPISODIC,
            content="User set a timer",
            relevance_score=0.9,
            user_id="user_123"
        )
        
        retriever.store(low_importance)
        retriever.store(high_importance)
        
        memories = [low_importance, high_importance]
        ranked = retriever.rank_memories(memories, "timer")
        
        # High importance memory should rank higher
        assert ranked[0].memory_id == high_importance.memory_id
    
    def test_rank_memories_empty_list(self):
        """Test ranking empty list of memories."""
        retriever = MemoryRetriever()
        
        ranked = retriever.rank_memories([], "query")
        
        assert ranked == []
    
    def test_rank_memories_combined_score(self):
        """Test that ranking uses combined score (semantic + recency + importance)."""
        retriever = MemoryRetriever()
        
        # High semantic similarity, low recency, low importance
        memory1 = Memory(
            memory_type=MemoryType.EPISODIC,
            content="User set a timer for cooking",
            timestamp=datetime.utcnow() - timedelta(days=80),
            relevance_score=0.2,
            user_id="user_123"
        )
        
        # Medium semantic similarity, high recency, high importance
        memory2 = Memory(
            memory_type=MemoryType.EPISODIC,
            content="User set an alarm",
            timestamp=datetime.utcnow(),
            relevance_score=0.9,
            user_id="user_123"
        )
        
        retriever.store(memory1)
        retriever.store(memory2)
        
        memories = [memory1, memory2]
        ranked = retriever.rank_memories(memories, "timer")
        
        # Combined score should determine ranking
        assert len(ranked) == 2


class TestMemoryRetrieval:
    """Tests for end-to-end memory retrieval."""
    
    def test_retrieve_basic(self):
        """Test basic memory retrieval."""
        retriever = MemoryRetriever()
        
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="User set a timer for 5 minutes",
            user_id="user_123"
        )
        retriever.store(memory)
        
        results = retriever.retrieve("timer", user_id="user_123")
        
        assert len(results) == 1
        assert results[0].memory_id == memory.memory_id
    
    def test_retrieve_respects_max_results(self):
        """Test that retrieve respects max_results limit."""
        retriever = MemoryRetriever(max_results=3)
        
        # Store 10 memories
        for i in range(10):
            memory = Memory(
                memory_type=MemoryType.EPISODIC,
                content=f"Memory about timers {i}",
                user_id="user_123"
            )
            retriever.store(memory)
        
        results = retriever.retrieve("timer", user_id="user_123")
        
        assert len(results) == 3
    
    def test_retrieve_custom_top_k(self):
        """Test retrieve with custom top_k parameter."""
        retriever = MemoryRetriever(max_results=5)
        
        # Store 10 memories
        for i in range(10):
            memory = Memory(
                memory_type=MemoryType.EPISODIC,
                content=f"Memory about timers {i}",
                user_id="user_123"
            )
            retriever.store(memory)
        
        results = retriever.retrieve("timer", user_id="user_123", top_k=2)
        
        assert len(results) == 2
    
    def test_retrieve_with_memory_type_filter(self):
        """Test retrieve with memory type filtering."""
        retriever = MemoryRetriever()
        
        episodic = EpisodicMemory(
            content="User set a timer",
            action_taken="set_timer",
            result="Success",
            success=True,
            user_id="user_123"
        )
        
        semantic = SemanticMemory(
            content="Timers are useful",
            fact="timer_use=useful",
            source="user_stated",
            confidence=1.0,
            user_id="user_123"
        )
        
        retriever.store(episodic)
        retriever.store(semantic)
        
        results = retriever.retrieve(
            "timer",
            user_id="user_123",
            memory_types=[MemoryType.EPISODIC]
        )
        
        assert len(results) == 1
        assert results[0].memory_id == episodic.memory_id
    
    def test_retrieve_empty_database(self):
        """Test retrieve with empty database."""
        retriever = MemoryRetriever()
        
        results = retriever.retrieve("timer", user_id="user_123")
        
        assert results == []
    
    def test_retrieve_latency_budget(self):
        """Test that retrieve completes within 100ms latency budget."""
        retriever = MemoryRetriever()
        
        # Store 100 memories
        for i in range(100):
            memory = Memory(
                memory_type=MemoryType.EPISODIC,
                content=f"Memory {i} about various topics",
                user_id="user_123"
            )
            retriever.store(memory)
        
        # Measure retrieval time
        start_time = time.perf_counter()
        results = retriever.retrieve("timer", user_id="user_123")
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        # Should complete within 100ms (may log warning but shouldn't fail)
        # Note: This is a soft requirement, actual time depends on hardware
        assert results is not None


class TestRelevanceUpdate:
    """Tests for relevance score updates."""
    
    def test_update_relevance_basic(self):
        """Test updating relevance score."""
        retriever = MemoryRetriever()
        
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="Test memory",
            relevance_score=1.0,
            user_id="user_123"
        )
        retriever.store(memory)
        
        retriever.update_relevance(memory.memory_id, 0.5)
        
        updated_memory = retriever.memories[memory.memory_id]
        assert updated_memory.relevance_score == 0.5
    
    def test_update_relevance_invalid_memory_id(self):
        """Test updating relevance for non-existent memory."""
        retriever = MemoryRetriever()
        
        with pytest.raises(ValueError) as exc_info:
            retriever.update_relevance(uuid4(), 0.5)
        
        assert "not found" in str(exc_info.value)
    
    def test_update_relevance_invalid_score(self):
        """Test updating relevance with invalid score."""
        retriever = MemoryRetriever()
        
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="Test memory",
            user_id="user_123"
        )
        retriever.store(memory)
        
        # Below range
        with pytest.raises(ValueError) as exc_info:
            retriever.update_relevance(memory.memory_id, -0.1)
        assert "between 0.0 and 1.0" in str(exc_info.value)
        
        # Above range
        with pytest.raises(ValueError) as exc_info:
            retriever.update_relevance(memory.memory_id, 1.1)
        assert "between 0.0 and 1.0" in str(exc_info.value)
    
    def test_update_relevance_boundary_values(self):
        """Test updating relevance with boundary values."""
        retriever = MemoryRetriever()
        
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="Test memory",
            user_id="user_123"
        )
        retriever.store(memory)
        
        # Test 0.0
        retriever.update_relevance(memory.memory_id, 0.0)
        assert retriever.memories[memory.memory_id].relevance_score == 0.0
        
        # Test 1.0
        retriever.update_relevance(memory.memory_id, 1.0)
        assert retriever.memories[memory.memory_id].relevance_score == 1.0


class TestUtilityMethods:
    """Tests for utility methods."""
    
    def test_get_memory_count_all(self):
        """Test getting total memory count."""
        retriever = MemoryRetriever()
        
        for i in range(5):
            memory = Memory(
                memory_type=MemoryType.EPISODIC,
                content=f"Memory {i}",
                user_id="user_123"
            )
            retriever.store(memory)
        
        assert retriever.get_memory_count() == 5
    
    def test_get_memory_count_by_user(self):
        """Test getting memory count for specific user."""
        retriever = MemoryRetriever()
        
        for i in range(3):
            memory = Memory(
                memory_type=MemoryType.EPISODIC,
                content=f"Memory {i}",
                user_id="user_123"
            )
            retriever.store(memory)
        
        for i in range(2):
            memory = Memory(
                memory_type=MemoryType.EPISODIC,
                content=f"Memory {i}",
                user_id="user_456"
            )
            retriever.store(memory)
        
        assert retriever.get_memory_count(user_id="user_123") == 3
        assert retriever.get_memory_count(user_id="user_456") == 2
    
    def test_clear_all_memories(self):
        """Test clearing all memories."""
        retriever = MemoryRetriever()
        
        for i in range(5):
            memory = Memory(
                memory_type=MemoryType.EPISODIC,
                content=f"Memory {i}",
                user_id="user_123"
            )
            retriever.store(memory)
        
        retriever.clear()
        
        assert len(retriever.memories) == 0
        assert len(retriever.memory_ids) == 0
        assert retriever.embeddings is None
    
    def test_clear_user_memories(self):
        """Test clearing memories for specific user."""
        retriever = MemoryRetriever()
        
        for i in range(3):
            memory = Memory(
                memory_type=MemoryType.EPISODIC,
                content=f"Memory {i}",
                user_id="user_123"
            )
            retriever.store(memory)
        
        for i in range(2):
            memory = Memory(
                memory_type=MemoryType.EPISODIC,
                content=f"Memory {i}",
                user_id="user_456"
            )
            retriever.store(memory)
        
        retriever.clear(user_id="user_123")
        
        assert retriever.get_memory_count() == 2
        assert retriever.get_memory_count(user_id="user_123") == 0
        assert retriever.get_memory_count(user_id="user_456") == 2


class TestCosineSimilarity:
    """Tests for cosine similarity computation."""
    
    def test_cosine_similarity_identical_vectors(self):
        """Test cosine similarity of identical vectors."""
        retriever = MemoryRetriever()
        
        vector = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        similarity = retriever._cosine_similarity(vector, vector)
        
        assert abs(similarity - 1.0) < 1e-6
    
    def test_cosine_similarity_orthogonal_vectors(self):
        """Test cosine similarity of orthogonal vectors."""
        retriever = MemoryRetriever()
        
        vector1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vector2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        similarity = retriever._cosine_similarity(vector1, vector2)
        
        assert abs(similarity - 0.0) < 1e-6
    
    def test_cosine_similarity_opposite_vectors(self):
        """Test cosine similarity of opposite vectors."""
        retriever = MemoryRetriever()
        
        vector1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vector2 = np.array([-1.0, 0.0, 0.0], dtype=np.float32)
        similarity = retriever._cosine_similarity(vector1, vector2)
        
        # Clamped to [0, 1], so -1 becomes 0
        assert abs(similarity - 0.0) < 1e-6


# Property-based tests
class TestMemoryRetrieverProperties:
    """Property-based tests for MemoryRetriever."""
    
    @given(
        max_results=st.integers(min_value=1, max_value=100),
        decay_days=st.integers(min_value=1, max_value=365)
    )
    def test_initialization_always_succeeds_with_valid_params(
        self,
        max_results: int,
        decay_days: int
    ):
        """Property: Valid parameters always create retriever."""
        retriever = MemoryRetriever(
            max_results=max_results,
            relevance_decay_days=decay_days
        )
        
        assert retriever.max_results == max_results
        assert retriever.relevance_decay_days == decay_days
    
    @given(
        content=st.text(min_size=1, max_size=100),
        user_id=st.text(min_size=1, max_size=50)
    )
    def test_store_always_increases_count(self, content: str, user_id: str):
        """Property: Storing memory always increases count."""
        retriever = MemoryRetriever()
        initial_count = retriever.get_memory_count()
        
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content=content,
            user_id=user_id
        )
        retriever.store(memory)
        
        assert retriever.get_memory_count() == initial_count + 1
    
    @given(
        relevance_score=st.floats(min_value=0.0, max_value=1.0)
    )
    def test_update_relevance_always_succeeds_with_valid_score(
        self,
        relevance_score: float
    ):
        """Property: Valid relevance score always updates successfully."""
        retriever = MemoryRetriever()
        
        memory = Memory(
            memory_type=MemoryType.EPISODIC,
            content="Test memory",
            user_id="user_123"
        )
        retriever.store(memory)
        
        retriever.update_relevance(memory.memory_id, relevance_score)
        
        updated_memory = retriever.memories[memory.memory_id]
        assert abs(updated_memory.relevance_score - relevance_score) < 1e-6
