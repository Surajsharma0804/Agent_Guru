"""
Property-Based Tests for Face Database Module

This module contains property-based tests using Hypothesis to validate
universal correctness properties of the face database operations.

Properties tested:
- Property 7: Database Multi-Embedding Storage
- Property 8: Database Embedding Retrieval Completeness
- Property 16: Database CRUD Operations
- Property 17: Database Persistence
- Property 18: Database JSON Round-Trip
"""

import pytest
import numpy as np
import tempfile
import os
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from guru_vision.database.face_db import FaceDatabase, Identity, Embedding


# Custom strategies for generating test data

@st.composite
def embedding_vector(draw):
    """Generate a valid 512-dimensional embedding vector using numpy directly."""
    # Use numpy random state for efficiency - generate all 512 values at once
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    rng = np.random.RandomState(seed)
    vector = rng.randn(512).astype(np.float32)
    # Normalize to reasonable range
    vector = vector * 2.0  # Scale to roughly [-6, 6] range
    return vector


@st.composite
def identity_name(draw):
    """Generate a valid identity name."""
    # Use simpler strategy for efficiency
    return draw(st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters='\\/:*?"<>|'),
        min_size=1,
        max_size=30
    ))


@st.composite
def permission_level(draw):
    """Generate a valid permission level."""
    return draw(st.sampled_from(["admin", "user", "guest", "denied"]))


@st.composite
def embedding_list(draw, min_size=1, max_size=10):
    """Generate a list of embedding vectors."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    return [draw(embedding_vector()) for _ in range(size)]


# Property 7: Database Multi-Embedding Storage
# **Validates: Requirements 6.1, 6.2**

@given(
    name=identity_name(),
    initial_embeddings=embedding_list(min_size=1, max_size=5),
    additional_embedding=embedding_vector(),
    perm_level=permission_level()
)
@settings(
    max_examples=50, 
    deadline=None, 
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_7_multi_embedding_storage(name, initial_embeddings, additional_embedding, perm_level):
    """
    Property 7: Database Multi-Embedding Storage
    
    For any identity, the Face_Database should support storing multiple embeddings,
    and when a new embedding is added to an existing identity, the embedding count
    for that identity should increase by one.
    
    **Validates: Requirements 6.1, 6.2**
    """
    db = FaceDatabase()
    
    # Add identity with initial embeddings
    initial_count = len(initial_embeddings)
    result = db.add_identity(name, initial_embeddings, perm_level)
    assert result is True, "Should successfully add new identity"
    
    # Verify initial embedding count
    identity = db.get_identity(name)
    assert identity is not None, "Identity should exist after adding"
    assert len(identity.embeddings) == initial_count, \
        f"Should have {initial_count} embeddings initially"
    
    # Add one more embedding
    result = db.add_embedding(name, additional_embedding)
    assert result is True, "Should successfully add embedding to existing identity"
    
    # Verify embedding count increased by one
    identity = db.get_identity(name)
    assert len(identity.embeddings) == initial_count + 1, \
        f"Embedding count should increase from {initial_count} to {initial_count + 1}"


# Property 8: Database Embedding Retrieval Completeness
# **Validates: Requirements 6.4**

@given(
    name=identity_name(),
    embeddings=embedding_list(min_size=1, max_size=20),
    perm_level=permission_level()
)
@settings(
    max_examples=50, 
    deadline=None, 
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_8_embedding_retrieval_completeness(name, embeddings, perm_level):
    """
    Property 8: Database Embedding Retrieval Completeness
    
    For any identity with N stored embeddings, when querying that identity from
    the database, all N embeddings should be returned.
    
    **Validates: Requirements 6.4**
    """
    db = FaceDatabase()
    
    # Add identity with N embeddings
    n_embeddings = len(embeddings)
    result = db.add_identity(name, embeddings, perm_level)
    assert result is True, "Should successfully add identity"
    
    # Query the identity
    identity = db.get_identity(name)
    assert identity is not None, "Identity should be retrievable"
    
    # Verify all N embeddings are returned
    assert len(identity.embeddings) == n_embeddings, \
        f"Should return all {n_embeddings} embeddings"
    
    # Verify each embedding is a valid Embedding object with correct shape
    for i, emb in enumerate(identity.embeddings):
        assert isinstance(emb, Embedding), \
            f"Embedding {i} should be an Embedding object"
        assert emb.vector.shape == (512,), \
            f"Embedding {i} should have shape (512,)"


# Property 16: Database CRUD Operations
# **Validates: Requirements 12.1, 12.2, 12.3**

@given(
    name=identity_name(),
    embeddings=embedding_list(min_size=1, max_size=5),
    initial_perm=permission_level(),
    updated_perm=permission_level()
)
@settings(
    max_examples=50, 
    deadline=None, 
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_16_crud_operations(name, embeddings, initial_perm, updated_perm):
    """
    Property 16: Database CRUD Operations
    
    For any identity, the Face_Database should support adding the identity with
    embeddings and permission level, updating the identity's information, and
    deleting the identity such that it is no longer retrievable.
    
    **Validates: Requirements 12.1, 12.2, 12.3**
    """
    db = FaceDatabase()
    
    # CREATE: Add identity
    result = db.add_identity(name, embeddings, initial_perm)
    assert result is True, "Should successfully create identity"
    
    identity = db.get_identity(name)
    assert identity is not None, "Created identity should be retrievable"
    assert identity.name == name, "Identity name should match"
    assert identity.permission_level == initial_perm, \
        "Initial permission level should match"
    assert len(identity.embeddings) == len(embeddings), \
        "All embeddings should be stored"
    
    # UPDATE: Update permission level
    result = db.update_permission(name, updated_perm)
    assert result is True, "Should successfully update permission"
    
    identity = db.get_identity(name)
    assert identity.permission_level == updated_perm, \
        "Permission level should be updated"
    
    # DELETE: Remove identity
    result = db.remove_identity(name)
    assert result is True, "Should successfully delete identity"
    
    identity = db.get_identity(name)
    assert identity is None, "Deleted identity should not be retrievable"
    
    # Verify identity is completely removed
    all_identities = db.get_all_identities()
    assert name not in [id.name for id in all_identities], \
        "Deleted identity should not appear in all identities list"


# Property 17: Database Persistence
# **Validates: Requirements 12.5**

@given(
    name=identity_name(),
    embeddings=embedding_list(min_size=1, max_size=5),
    perm_level=permission_level()
)
@settings(
    max_examples=30, 
    deadline=None, 
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_17_database_persistence(name, embeddings, perm_level):
    """
    Property 17: Database Persistence
    
    For any database modification (add, update, delete), the changes should be
    immediately persisted to disk such that reloading the database reflects
    the modifications.
    
    **Validates: Requirements 12.5**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_persistence.json")
        
        # Test ADD persistence
        db1 = FaceDatabase(db_path)
        db1.add_identity(name, embeddings, perm_level)
        db1.save()
        
        # Reload and verify
        db2 = FaceDatabase(db_path)
        db2.load()
        identity = db2.get_identity(name)
        assert identity is not None, "Added identity should persist after reload"
        assert identity.name == name, "Identity name should persist"
        assert len(identity.embeddings) == len(embeddings), \
            "All embeddings should persist"
        
        # Test UPDATE persistence
        new_perm = "admin" if perm_level != "admin" else "user"
        db2.update_permission(name, new_perm)
        db2.save()
        
        # Reload and verify update
        db3 = FaceDatabase(db_path)
        db3.load()
        identity = db3.get_identity(name)
        assert identity.permission_level == new_perm, \
            "Updated permission should persist after reload"
        
        # Test DELETE persistence
        db3.remove_identity(name)
        db3.save()
        
        # Reload and verify deletion
        db4 = FaceDatabase(db_path)
        db4.load()
        identity = db4.get_identity(name)
        assert identity is None, "Deleted identity should not exist after reload"


# Property 18: Database JSON Round-Trip
# **Validates: Requirements 12.7**

@given(
    identities_data=st.lists(
        st.tuples(
            identity_name(),
            embedding_list(min_size=1, max_size=5),
            permission_level()
        ),
        min_size=1,
        max_size=5,
        unique_by=lambda x: x[0]  # Unique names
    )
)
@settings(
    max_examples=30, 
    deadline=None, 
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_18_json_round_trip(identities_data):
    """
    Property 18: Database JSON Round-Trip
    
    For any database state, exporting to JSON format and then importing should
    preserve all identities, embeddings, and metadata without loss.
    
    **Validates: Requirements 12.7**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        export_path = os.path.join(tmpdir, "export.json")
        
        # Create database with multiple identities
        db1 = FaceDatabase()
        for name, embeddings, perm_level in identities_data:
            db1.add_identity(name, embeddings, perm_level, metadata={"test": "data"})
        
        # Export to JSON
        db1.export_json(export_path)
        
        # Import into new database
        db2 = FaceDatabase()
        db2.import_json(export_path)
        
        # Verify all identities are preserved
        assert len(db2.identities) == len(identities_data), \
            "All identities should be preserved in round-trip"
        
        # Verify each identity's data is preserved
        for name, embeddings, perm_level in identities_data:
            identity = db2.get_identity(name)
            assert identity is not None, f"Identity '{name}' should exist after import"
            assert identity.name == name, "Identity name should be preserved"
            assert identity.permission_level == perm_level, \
                "Permission level should be preserved"
            assert len(identity.embeddings) == len(embeddings), \
                "All embeddings should be preserved"
            assert identity.metadata.get("test") == "data", \
                "Metadata should be preserved"
            
            # Verify embedding vectors are preserved (within floating point tolerance)
            for i, (original_emb, restored_emb) in enumerate(
                zip(embeddings, identity.embeddings)
            ):
                assert restored_emb.vector.shape == (512,), \
                    f"Embedding {i} shape should be preserved"
                # Check vectors are approximately equal (allowing for serialization precision)
                assert np.allclose(original_emb, restored_emb.vector, rtol=1e-5, atol=1e-7), \
                    f"Embedding {i} vector values should be preserved"


# Additional property test: Multiple identities with overlapping operations

@given(
    identities=st.lists(
        st.tuples(
            identity_name(),
            embedding_list(min_size=1, max_size=3),
            permission_level()
        ),
        min_size=2,
        max_size=5,
        unique_by=lambda x: x[0]  # Unique names
    )
)
@settings(
    max_examples=30, 
    deadline=None, 
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_multiple_identities_isolation(identities):
    """
    Property: Multiple Identity Isolation
    
    Operations on one identity should not affect other identities in the database.
    """
    db = FaceDatabase()
    
    # Add all identities
    for name, embeddings, perm_level in identities:
        result = db.add_identity(name, embeddings, perm_level)
        assert result is True, f"Should add identity '{name}'"
    
    # Verify all identities exist
    assert len(db.get_all_identities()) == len(identities), \
        "All identities should be stored"
    
    # Modify first identity
    first_name = identities[0][0]
    db.update_permission(first_name, "admin")
    
    # Verify other identities are unchanged
    for name, embeddings, perm_level in identities[1:]:
        identity = db.get_identity(name)
        assert identity is not None, f"Identity '{name}' should still exist"
        assert identity.permission_level == perm_level, \
            f"Permission for '{name}' should be unchanged"
        assert len(identity.embeddings) == len(embeddings), \
            f"Embeddings for '{name}' should be unchanged"
    
    # Delete first identity
    db.remove_identity(first_name)
    
    # Verify other identities still exist
    for name, embeddings, perm_level in identities[1:]:
        identity = db.get_identity(name)
        assert identity is not None, \
            f"Identity '{name}' should still exist after deleting '{first_name}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
