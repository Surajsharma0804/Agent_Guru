"""
Property-Based Tests for GuruVision Engine Identity Management

This module contains property-based tests using Hypothesis to validate
universal correctness properties of identity management operations.

Properties tested:
- Property 13: Permission Level Association
- Property 20: Incremental Identity Recognition
- Property 25: Admin Permission Access

Requirements validated: 9.1, 9.3, 16.3, 25.2
"""

import pytest
import numpy as np
import tempfile
import os
import shutil
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from guru_vision.engine import GuruVisionEngine, FaceResult, RecognitionResult
from guru_vision.database.face_db import FaceDatabase, Embedding
from guru_vision.config import GuruVisionConfig


# Custom strategies for generating test data

@st.composite
def identity_name(draw):
    """Generate a valid identity name."""
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
def embedding_vector(draw):
    """Generate a valid 512-dimensional embedding vector."""
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    rng = np.random.RandomState(seed)
    vector = rng.randn(512).astype(np.float32)
    # L2 normalize
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector


@st.composite
def face_image(draw):
    """Generate a simple face image for testing."""
    # Create a 112x112x3 BGR image with random pixel values
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    rng = np.random.RandomState(seed)
    image = rng.randint(0, 255, (112, 112, 3), dtype=np.uint8)
    return image


# Property 13: Permission Level Association
# **Validates: Requirements 9.1, 9.3**

@given(
    name=identity_name(),
    perm_level=permission_level()
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_13_permission_level_association(name, perm_level):
    """
    Property 13: Permission Level Association
    
    For any identity stored in the Face_Database, there should be an associated
    Permission_Level, and when that identity is recognized, the Permission_Level
    should be included in the recognition result.
    
    **Validates: Requirements 9.1, 9.3**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_db.json")
        
        # Create database and add identity with permission level
        db = FaceDatabase(db_path)
        
        # Create some embeddings (as numpy arrays)
        embeddings = []
        for _ in range(3):
            vector = np.random.randn(512).astype(np.float32)
            # L2 normalize
            vector = vector / np.linalg.norm(vector)
            embeddings.append(vector)
        
        # Add identity with specific permission level
        result = db.add_identity(name, embeddings, perm_level)
        assert result is True, "Should successfully add identity"
        
        # Verify identity has associated permission level
        identity = db.get_identity(name)
        assert identity is not None, "Identity should exist in database"
        assert identity.permission_level == perm_level, \
            f"Identity should have permission level '{perm_level}'"
        
        # Simulate recognition by searching with one of the embeddings
        # (slightly perturbed to simulate real recognition)
        query_embedding = embeddings[0] + np.random.randn(512).astype(np.float32) * 0.01
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        match_result = db.search(query_embedding, threshold=0.5)
        
        # When identity is recognized, permission level should be included
        if match_result is not None and match_result["identity"] == name:
            assert match_result["permission_level"] == perm_level, \
                f"Recognition result should include permission level '{perm_level}'"


# Property 20: Incremental Identity Recognition
# **Validates: Requirements 16.3**

@given(
    name=identity_name(),
    perm_level=permission_level()
)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_20_incremental_identity_recognition(name, perm_level):
    """
    Property 20: Incremental Identity Recognition
    
    For any newly added identity (without retraining), when that identity's face
    appears in subsequent frames, the system should recognize the identity with
    the same accuracy as pre-trained identities.
    
    **Validates: Requirements 16.3**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_db.json")
        
        # Create database
        db = FaceDatabase(db_path)
        
        # Add a "pre-trained" identity (simulating existing identity)
        pretrained_name = "PreTrained_User"
        pretrained_embeddings = []
        for _ in range(5):
            vector = np.random.randn(512).astype(np.float32)
            vector = vector / np.linalg.norm(vector)
            pretrained_embeddings.append(vector)
        
        db.add_identity(pretrained_name, pretrained_embeddings, "user")
        
        # Add a new identity incrementally (without retraining)
        new_embeddings = []
        for _ in range(5):
            vector = np.random.randn(512).astype(np.float32)
            vector = vector / np.linalg.norm(vector)
            new_embeddings.append(vector)
        
        result = db.add_identity(name, new_embeddings, perm_level)
        assert result is True, "Should successfully add new identity incrementally"
        
        # Test recognition of newly added identity
        # Use a slightly perturbed version of one of the new embeddings
        query_embedding = new_embeddings[0] + np.random.randn(512).astype(np.float32) * 0.01
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        match_result = db.search(query_embedding, threshold=0.5)
        
        # The newly added identity should be recognizable
        # (with same accuracy as pre-trained identities)
        assert match_result is not None, \
            "Newly added identity should be recognized in subsequent operations"
        assert match_result["identity"] == name, \
            "Newly added identity should be recognized in subsequent operations"
        assert match_result["confidence"] > 0.5, \
            "Recognition confidence should be above threshold"
        
        # Verify pre-trained identity is still recognizable (no interference)
        pretrained_query = pretrained_embeddings[0] + np.random.randn(512).astype(np.float32) * 0.01
        pretrained_query = pretrained_query / np.linalg.norm(pretrained_query)
        
        pretrained_match = db.search(pretrained_query, threshold=0.5)
        assert pretrained_match is not None, \
            "Pre-trained identity should still be recognizable after adding new identity"
        assert pretrained_match["identity"] == pretrained_name, \
            "Pre-trained identity should still be recognizable after adding new identity"


# Property 25: Admin Permission Access
# **Validates: Requirements 25.2**

@given(
    admin_name=identity_name(),
    other_perm=st.sampled_from(["user", "guest", "denied"])
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_25_admin_permission_access(admin_name, other_perm):
    """
    Property 25: Admin Permission Access
    
    For any identity with "admin" Permission_Level, when recognized, the system
    should grant full system access as indicated in the recognition result.
    
    **Validates: Requirements 25.2**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_db.json")
        
        # Create database
        db = FaceDatabase(db_path)
        
        # Add admin identity
        admin_embeddings = []
        for _ in range(3):
            vector = np.random.randn(512).astype(np.float32)
            vector = vector / np.linalg.norm(vector)
            admin_embeddings.append(vector)
        
        result = db.add_identity(admin_name, admin_embeddings, "admin")
        assert result is True, "Should successfully add admin identity"
        
        # Add non-admin identity for comparison
        other_name = "Other_User"
        other_embeddings = []
        for _ in range(3):
            vector = np.random.randn(512).astype(np.float32)
            vector = vector / np.linalg.norm(vector)
            other_embeddings.append(vector)
        
        db.add_identity(other_name, other_embeddings, other_perm)
        
        # Recognize admin identity
        admin_query = admin_embeddings[0] + np.random.randn(512).astype(np.float32) * 0.01
        admin_query = admin_query / np.linalg.norm(admin_query)
        
        admin_match = db.search(admin_query, threshold=0.5)
        
        # When admin is recognized, permission level should be "admin"
        if admin_match is not None and admin_match["identity"] == admin_name:
            assert admin_match["permission_level"] == "admin", \
                "Admin identity should have 'admin' permission level in recognition result"
            
            # Verify admin has different permission than other users
            other_query = other_embeddings[0] + np.random.randn(512).astype(np.float32) * 0.01
            other_query = other_query / np.linalg.norm(other_query)
            
            other_match = db.search(other_query, threshold=0.5)
            
            if other_match is not None and other_match["identity"] == other_name:
                assert other_match["permission_level"] == other_perm, \
                    f"Non-admin identity should have '{other_perm}' permission level"
                assert other_match["permission_level"] != "admin", \
                    "Non-admin identity should not have admin permission"


# Additional property: Permission level persistence across operations

@given(
    name=identity_name(),
    initial_perm=permission_level(),
    updated_perm=permission_level()
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_permission_persistence(name, initial_perm, updated_perm):
    """
    Property: Permission Level Persistence
    
    Permission levels should persist correctly through add, update, and recognition
    operations.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_db.json")
        
        # Create database
        db = FaceDatabase(db_path)
        
        # Add identity with initial permission
        embeddings = []
        for _ in range(3):
            vector = np.random.randn(512).astype(np.float32)
            vector = vector / np.linalg.norm(vector)
            embeddings.append(vector)
        
        db.add_identity(name, embeddings, initial_perm)
        
        # Verify initial permission
        identity = db.get_identity(name)
        assert identity.permission_level == initial_perm, \
            "Initial permission level should be set correctly"
        
        # Update permission
        db.update_permission(name, updated_perm)
        
        # Verify updated permission
        identity = db.get_identity(name)
        assert identity.permission_level == updated_perm, \
            "Permission level should be updated correctly"
        
        # Verify permission persists in recognition
        query = embeddings[0] + np.random.randn(512).astype(np.float32) * 0.01
        query = query / np.linalg.norm(query)
        
        match_result = db.search(query, threshold=0.5)
        
        if match_result is not None and match_result["identity"] == name:
            assert match_result["permission_level"] == updated_perm, \
                "Updated permission level should be reflected in recognition results"


# Additional property: Multiple identities with different permissions

@given(
    identities=st.lists(
        st.tuples(
            identity_name(),
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
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_multiple_permissions_isolation(identities):
    """
    Property: Multiple Permission Isolation
    
    Each identity should maintain its own permission level independently,
    and permission changes to one identity should not affect others.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_db.json")
        
        # Create database
        db = FaceDatabase(db_path)
        
        # Add all identities with their respective permissions
        identity_embeddings = {}
        for name, perm_level in identities:
            embeddings = []
            for _ in range(3):
                vector = np.random.randn(512).astype(np.float32)
                vector = vector / np.linalg.norm(vector)
                embeddings.append(vector)
            
            db.add_identity(name, embeddings, perm_level)
            identity_embeddings[name] = embeddings
        
        # Verify each identity has correct permission
        for name, perm_level in identities:
            identity = db.get_identity(name)
            assert identity.permission_level == perm_level, \
                f"Identity '{name}' should have permission '{perm_level}'"
        
        # Change permission of first identity
        first_name, first_perm = identities[0]
        new_perm = "admin" if first_perm != "admin" else "user"
        db.update_permission(first_name, new_perm)
        
        # Verify first identity has new permission
        identity = db.get_identity(first_name)
        assert identity.permission_level == new_perm, \
            f"First identity should have updated permission '{new_perm}'"
        
        # Verify other identities are unchanged
        for name, perm_level in identities[1:]:
            identity = db.get_identity(name)
            assert identity.permission_level == perm_level, \
                f"Identity '{name}' permission should remain '{perm_level}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
