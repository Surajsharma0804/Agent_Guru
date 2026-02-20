"""
Tests for vector database module.

This module tests the VectorDatabase class for semantic memory storage
and retrieval using ChromaDB.

Coverage Target: 80%+
Test Types: Unit tests, property-based tests, integration tests

NOTE: Uses in-memory ChromaDB on Windows to avoid file locking issues.

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import gc
import platform
import tempfile
import time
from pathlib import Path
from uuid import UUID, uuid4

import numpy as np
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from Agent_Guru.reasoning.memory.vector_db import VectorDatabase
from Agent_Guru.reasoning.models.memory import MemoryType


# Use in-memory mode on Windows to avoid file locking issues
IS_WINDOWS = platform.system() == "Windows"


class TestVectorDatabase:
    """Unit tests for VectorDatabase."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
            # Force cleanup
            gc.collect()
            time.sleep(0.1)
    
    @pytest.fixture
    def db(self, temp_db_path):
        """Create vector database for tests."""
        # Use in-memory mode on Windows to avoid file locking
        db_instance = VectorDatabase(db_path=temp_db_path, in_memory=IS_WINDOWS)
        yield db_instance
        # Reset database before cleanup to ensure clean state
        try:
            db_instance.reset()  # Clear all data
        except Exception:
            pass
        # Cleanup
        try:
            del db_instance
            gc.collect()
            time.sleep(0.1)
        except Exception:
            pass
    
    @pytest.fixture
    def sample_embedding(self):
        """Create sample 384-dimensional embedding."""
        # Create random normalized embedding
        emb = np.random.randn(384)
        emb = emb / np.linalg.norm(emb)
        return emb.tolist()
    
    def test_initialization(self, temp_db_path):
        """Test that database initializes correctly."""
        db = VectorDatabase(db_path=temp_db_path, in_memory=IS_WINDOWS)
        
        assert db.db_path == Path(temp_db_path)
        assert db.embedding_dimension == 384
        assert db.client is not None
        assert len(db.collections) == 4  # One per memory type
    
    def test_initialization_creates_directory(self):
        """Test that initialization creates database directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "new_db"
            assert not db_path.exists()
            
            db = VectorDatabase(db_path=str(db_path), in_memory=IS_WINDOWS)
            if not IS_WINDOWS:
                # Only check directory creation on non-Windows (in-memory doesn't create dir)
                assert db_path.exists()
            
            # Cleanup
            del db
            gc.collect()
            time.sleep(0.1)
    
    def test_collections_initialized(self, db):
        """Test that all collections are initialized."""
        for memory_type in MemoryType:
            assert memory_type in db.collections
            assert db.collections[memory_type] is not None
    
    def test_store_memory(self, db, sample_embedding):
        """Test storing a memory."""
        memory_id = uuid4()
        content = "User set a timer for 5 minutes"
        metadata = {"user_id": "user_123", "action": "set_timer"}
        
        result_id = db.store(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id,
            content=content,
            embedding=sample_embedding,
            metadata=metadata
        )
        
        assert result_id == str(memory_id)
    
    def test_store_memory_wrong_dimension_raises_error(self, db):
        """Test that wrong embedding dimension raises ValueError."""
        memory_id = uuid4()
        wrong_embedding = [0.1] * 256  # Wrong dimension
        
        with pytest.raises(ValueError, match="Embedding must be 384-dimensional"):
            db.store(
                memory_type=MemoryType.EPISODIC,
                memory_id=memory_id,
                content="Test",
                embedding=wrong_embedding,
                metadata={"user_id": "user_123"}
            )
    
    def test_store_memory_missing_user_id_raises_error(self, db, sample_embedding):
        """Test that missing user_id raises ValueError."""
        memory_id = uuid4()
        
        with pytest.raises(ValueError, match="metadata must include 'user_id'"):
            db.store(
                memory_type=MemoryType.EPISODIC,
                memory_id=memory_id,
                content="Test",
                embedding=sample_embedding,
                metadata={}  # Missing user_id
            )
    
    def test_search_memories(self, db, sample_embedding):
        """Test searching for similar memories."""
        # Store some memories
        memory_ids = []
        for i in range(3):
            memory_id = uuid4()
            memory_ids.append(memory_id)
            
            # Create slightly different embeddings
            emb = np.array(sample_embedding) + np.random.randn(384) * 0.1
            emb = emb / np.linalg.norm(emb)
            
            db.store(
                memory_type=MemoryType.EPISODIC,
                memory_id=memory_id,
                content=f"Memory {i}",
                embedding=emb.tolist(),
                metadata={"user_id": "user_123"}
            )
        
        # Search for similar memories
        results = db.search(
            memory_type=MemoryType.EPISODIC,
            query_embedding=sample_embedding,
            user_id="user_123",
            top_k=3
        )
        
        assert len(results) == 3
        assert all(len(r) == 4 for r in results)  # (id, content, similarity, metadata)
        
        # Results should be sorted by similarity (highest first)
        similarities = [r[2] for r in results]
        assert similarities == sorted(similarities, reverse=True)
    
    def test_search_filters_by_user_id(self, db, sample_embedding):
        """Test that search filters by user_id."""
        # Store memories for different users
        memory_id1 = uuid4()
        db.store(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id1,
            content="User 1 memory",
            embedding=sample_embedding,
            metadata={"user_id": "user_1"}
        )
        
        memory_id2 = uuid4()
        db.store(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id2,
            content="User 2 memory",
            embedding=sample_embedding,
            metadata={"user_id": "user_2"}
        )
        
        # Search for user_1 memories
        results = db.search(
            memory_type=MemoryType.EPISODIC,
            query_embedding=sample_embedding,
            user_id="user_1",
            top_k=10
        )
        
        # Should only return user_1 memories
        assert len(results) == 1
        assert results[0][3]["user_id"] == "user_1"
    
    def test_search_respects_top_k(self, db, sample_embedding):
        """Test that search respects top_k parameter."""
        # Store 10 memories
        for i in range(10):
            memory_id = uuid4()
            db.store(
                memory_type=MemoryType.EPISODIC,
                memory_id=memory_id,
                content=f"Memory {i}",
                embedding=sample_embedding,
                metadata={"user_id": "user_123"}
            )
        
        # Search with top_k=5
        results = db.search(
            memory_type=MemoryType.EPISODIC,
            query_embedding=sample_embedding,
            user_id="user_123",
            top_k=5
        )
        
        assert len(results) == 5
    
    def test_search_respects_min_similarity(self, db, sample_embedding):
        """Test that search filters by minimum similarity."""
        # Store memories with different similarities
        memory_id1 = uuid4()
        db.store(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id1,
            content="Very similar",
            embedding=sample_embedding,  # Identical
            metadata={"user_id": "user_123"}
        )
        
        # Create very different embedding
        different_emb = np.random.randn(384)
        different_emb = different_emb / np.linalg.norm(different_emb)
        
        memory_id2 = uuid4()
        db.store(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id2,
            content="Very different",
            embedding=different_emb.tolist(),
            metadata={"user_id": "user_123"}
        )
        
        # Search with high minimum similarity
        results = db.search(
            memory_type=MemoryType.EPISODIC,
            query_embedding=sample_embedding,
            user_id="user_123",
            top_k=10,
            min_similarity=0.9
        )
        
        # Should only return very similar memory
        assert len(results) >= 1
        assert all(r[2] >= 0.9 for r in results)
    
    def test_get_memory(self, db, sample_embedding):
        """Test retrieving a specific memory by ID."""
        memory_id = uuid4()
        content = "Test memory"
        metadata = {"user_id": "user_123"}
        
        db.store(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id,
            content=content,
            embedding=sample_embedding,
            metadata=metadata
        )
        
        # Retrieve memory
        result = db.get(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id
        )
        
        assert result is not None
        retrieved_content, retrieved_embedding, retrieved_metadata = result
        assert retrieved_content == content
        assert len(retrieved_embedding) == 384
        assert retrieved_metadata["user_id"] == "user_123"
    
    def test_get_nonexistent_memory_returns_none(self, db):
        """Test that getting nonexistent memory returns None."""
        result = db.get(
            memory_type=MemoryType.EPISODIC,
            memory_id=uuid4()
        )
        
        assert result is None
    
    def test_update_metadata(self, db, sample_embedding):
        """Test updating memory metadata."""
        memory_id = uuid4()
        metadata = {"user_id": "user_123", "relevance_score": 1.0}
        
        db.store(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id,
            content="Test",
            embedding=sample_embedding,
            metadata=metadata
        )
        
        # Update metadata
        new_metadata = {"user_id": "user_123", "relevance_score": 0.5}
        db.update_metadata(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id,
            metadata=new_metadata
        )
        
        # Verify update
        result = db.get(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id
        )
        
        assert result is not None
        _, _, retrieved_metadata = result
        assert retrieved_metadata["relevance_score"] == 0.5
    
    def test_delete_memory(self, db, sample_embedding):
        """Test deleting a memory."""
        memory_id = uuid4()
        
        db.store(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id,
            content="Test",
            embedding=sample_embedding,
            metadata={"user_id": "user_123"}
        )
        
        # Verify memory exists
        assert db.get(MemoryType.EPISODIC, memory_id) is not None
        
        # Delete memory
        db.delete(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id
        )
        
        # Verify memory is deleted
        assert db.get(MemoryType.EPISODIC, memory_id) is None
    
    def test_count_memories(self, db, sample_embedding):
        """Test counting memories in a collection."""
        # Initially empty
        assert db.count(MemoryType.EPISODIC) == 0
        
        # Store some memories
        for i in range(5):
            db.store(
                memory_type=MemoryType.EPISODIC,
                memory_id=uuid4(),
                content=f"Memory {i}",
                embedding=sample_embedding,
                metadata={"user_id": "user_123"}
            )
        
        # Count should be 5
        assert db.count(MemoryType.EPISODIC) == 5
    
    def test_reset_specific_collection(self, db, sample_embedding):
        """Test resetting a specific collection."""
        # Store memories in multiple collections
        db.store(
            memory_type=MemoryType.EPISODIC,
            memory_id=uuid4(),
            content="Episodic",
            embedding=sample_embedding,
            metadata={"user_id": "user_123"}
        )
        
        db.store(
            memory_type=MemoryType.SEMANTIC,
            memory_id=uuid4(),
            content="Semantic",
            embedding=sample_embedding,
            metadata={"user_id": "user_123"}
        )
        
        # Reset episodic collection
        db.reset(MemoryType.EPISODIC)
        
        # Episodic should be empty, semantic should still have data
        assert db.count(MemoryType.EPISODIC) == 0
        assert db.count(MemoryType.SEMANTIC) == 1
    
    def test_reset_all_collections(self, db, sample_embedding):
        """Test resetting all collections."""
        # Store memories in multiple collections
        for memory_type in MemoryType:
            db.store(
                memory_type=memory_type,
                memory_id=uuid4(),
                content="Test",
                embedding=sample_embedding,
                metadata={"user_id": "user_123"}
            )
        
        # Reset all
        db.reset()
        
        # All collections should be empty
        for memory_type in MemoryType:
            assert db.count(memory_type) == 0
    
    def test_separate_collections_per_memory_type(self, db, sample_embedding):
        """Test that different memory types use separate collections."""
        # Store same content in different collections
        content = "Test memory"
        
        episodic_id = uuid4()
        db.store(
            memory_type=MemoryType.EPISODIC,
            memory_id=episodic_id,
            content=content,
            embedding=sample_embedding,
            metadata={"user_id": "user_123"}
        )
        
        semantic_id = uuid4()
        db.store(
            memory_type=MemoryType.SEMANTIC,
            memory_id=semantic_id,
            content=content,
            embedding=sample_embedding,
            metadata={"user_id": "user_123"}
        )
        
        # Search in episodic should only return episodic
        episodic_results = db.search(
            memory_type=MemoryType.EPISODIC,
            query_embedding=sample_embedding,
            user_id="user_123",
            top_k=10
        )
        
        # Search in semantic should only return semantic
        semantic_results = db.search(
            memory_type=MemoryType.SEMANTIC,
            query_embedding=sample_embedding,
            user_id="user_123",
            top_k=10
        )
        
        assert len(episodic_results) == 1
        assert len(semantic_results) == 1
        assert episodic_results[0][0] == str(episodic_id)
        assert semantic_results[0][0] == str(semantic_id)


class TestVectorDatabaseProperties:
    """Property-based tests for VectorDatabase."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
            # Force cleanup
            gc.collect()
            time.sleep(0.1)
    
    @pytest.fixture
    def db(self, temp_db_path):
        """Create vector database for tests."""
        # Use in-memory mode on Windows to avoid file locking
        db_instance = VectorDatabase(db_path=temp_db_path, in_memory=IS_WINDOWS)
        yield db_instance
        # Reset database before cleanup to ensure clean state
        try:
            db_instance.reset()  # Clear all data
        except Exception:
            pass
        # Cleanup
        try:
            del db_instance
            gc.collect()
            time.sleep(0.1)
        except Exception:
            pass
    
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        max_examples=20,
        deadline=None
    )
    @given(
        content=st.text(min_size=1, max_size=100),
        user_id=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=50
        )
    )
    def test_store_and_retrieve_roundtrip(self, db, content, user_id):
        """Property: Stored memory can be retrieved."""
        # Reset database to ensure clean state for each test run
        db.reset(MemoryType.EPISODIC)
        
        # Create normalized embedding
        emb = np.random.randn(384)
        emb = emb / np.linalg.norm(emb)
        embedding = emb.tolist()
        
        memory_id = uuid4()
        metadata = {"user_id": user_id}
        
        # Store
        db.store(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id,
            content=content,
            embedding=embedding,
            metadata=metadata
        )
        
        # Retrieve
        result = db.get(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id
        )
        
        assert result is not None
        retrieved_content, _, retrieved_metadata = result
        assert retrieved_content == content
        assert retrieved_metadata["user_id"] == user_id
    
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        max_examples=20,
        deadline=None
    )
    @given(
        num_memories=st.integers(min_value=1, max_value=10)
    )
    def test_count_matches_stored(self, db, num_memories):
        """Property: Count matches number of stored memories."""
        # Reset database to ensure clean state for each test run
        db.reset(MemoryType.PREFERENCE)
        
        # Create normalized embedding
        emb = np.random.randn(384)
        emb = emb / np.linalg.norm(emb)
        embedding = emb.tolist()
        
        # Store memories
        for i in range(num_memories):
            db.store(
                memory_type=MemoryType.PREFERENCE,
                memory_id=uuid4(),
                content=f"Memory {i}",
                embedding=embedding,
                metadata={"user_id": "user_123"}
            )
        
        # Count should match
        assert db.count(MemoryType.PREFERENCE) == num_memories
    
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        max_examples=20,
        deadline=None
    )
    @given(
        top_k=st.integers(min_value=1, max_value=10)
    )
    def test_search_returns_at_most_top_k(self, db, top_k):
        """Property: Search returns at most top_k results."""
        # Reset database to ensure clean state for each test run
        db.reset(MemoryType.TASK)
        
        # Create normalized embedding
        emb = np.random.randn(384)
        emb = emb / np.linalg.norm(emb)
        embedding = emb.tolist()
        
        # Store more memories than top_k
        for i in range(top_k + 5):
            db.store(
                memory_type=MemoryType.TASK,
                memory_id=uuid4(),
                content=f"Memory {i}",
                embedding=embedding,
                metadata={"user_id": "user_123"}
            )
        
        # Search
        results = db.search(
            memory_type=MemoryType.TASK,
            query_embedding=embedding,
            user_id="user_123",
            top_k=top_k
        )
        
        assert len(results) <= top_k


class TestVectorDatabaseIntegration:
    """Integration tests for VectorDatabase."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
            # Force cleanup
            gc.collect()
            time.sleep(0.1)
    
    @pytest.fixture
    def db(self, temp_db_path):
        """Create vector database for tests."""
        # Use in-memory mode on Windows to avoid file locking
        db_instance = VectorDatabase(db_path=temp_db_path, in_memory=IS_WINDOWS)
        yield db_instance
        # Reset database before cleanup to ensure clean state
        try:
            db_instance.reset()  # Clear all data
        except Exception:
            pass
        # Cleanup
        try:
            del db_instance
            gc.collect()
            time.sleep(0.1)
        except Exception:
            pass
    
    def test_persistence_across_instances(self, temp_db_path):
        """Test that data persists across database instances."""
        if IS_WINDOWS:
            pytest.skip("Persistence test not applicable for in-memory mode on Windows")
        
        # Create normalized embedding
        emb = np.random.randn(384)
        emb = emb / np.linalg.norm(emb)
        embedding = emb.tolist()
        
        memory_id = uuid4()
        content = "Persistent memory"
        
        # Store in first instance
        db1 = VectorDatabase(db_path=temp_db_path, in_memory=IS_WINDOWS)
        db1.store(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id,
            content=content,
            embedding=embedding,
            metadata={"user_id": "user_123"}
        )
        
        # Cleanup first instance
        del db1
        gc.collect()
        time.sleep(0.1)
        
        # Create new instance and retrieve
        db2 = VectorDatabase(db_path=temp_db_path, in_memory=IS_WINDOWS)
        result = db2.get(
            memory_type=MemoryType.EPISODIC,
            memory_id=memory_id
        )
        
        assert result is not None
        retrieved_content, _, _ = result
        assert retrieved_content == content
        
        # Cleanup second instance
        del db2
        gc.collect()
        time.sleep(0.1)
    
    def test_semantic_search_workflow(self, db):
        """Test complete semantic search workflow."""
        # Create embeddings for related memories
        base_emb = np.random.randn(384)
        base_emb = base_emb / np.linalg.norm(base_emb)
        
        # Store similar memories
        similar_memories = []
        for i in range(3):
            # Add small noise to create similar embeddings
            emb = base_emb + np.random.randn(384) * 0.1
            emb = emb / np.linalg.norm(emb)
            
            memory_id = uuid4()
            similar_memories.append(memory_id)
            
            db.store(
                memory_type=MemoryType.EPISODIC,
                memory_id=memory_id,
                content=f"Similar memory {i}",
                embedding=emb.tolist(),
                metadata={"user_id": "user_123"}
            )
        
        # Store dissimilar memory
        different_emb = np.random.randn(384)
        different_emb = different_emb / np.linalg.norm(different_emb)
        
        different_id = uuid4()
        db.store(
            memory_type=MemoryType.EPISODIC,
            memory_id=different_id,
            content="Different memory",
            embedding=different_emb.tolist(),
            metadata={"user_id": "user_123"}
        )
        
        # Search with base embedding
        results = db.search(
            memory_type=MemoryType.EPISODIC,
            query_embedding=base_emb.tolist(),
            user_id="user_123",
            top_k=4
        )
        
        # Top 3 results should be similar memories
        top_3_ids = [r[0] for r in results[:3]]
        similar_ids_str = [str(mid) for mid in similar_memories]
        
        # At least 2 of top 3 should be similar memories
        matches = sum(1 for tid in top_3_ids if tid in similar_ids_str)
        assert matches >= 2
    
    def test_multi_user_isolation(self, db):
        """Test that users can only access their own memories."""
        # Create normalized embedding
        emb = np.random.randn(384)
        emb = emb / np.linalg.norm(emb)
        embedding = emb.tolist()
        
        # Store memories for multiple users
        users = ["user_1", "user_2", "user_3"]
        for user_id in users:
            for i in range(3):
                db.store(
                    memory_type=MemoryType.EPISODIC,
                    memory_id=uuid4(),
                    content=f"{user_id} memory {i}",
                    embedding=embedding,
                    metadata={"user_id": user_id}
                )
        
        # Each user should only see their own memories
        for user_id in users:
            results = db.search(
                memory_type=MemoryType.EPISODIC,
                query_embedding=embedding,
                user_id=user_id,
                top_k=10
            )
            
            assert len(results) == 3
            assert all(r[3]["user_id"] == user_id for r in results)
