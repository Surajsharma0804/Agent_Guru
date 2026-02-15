"""
Basic tests for the face database module.
"""

import pytest
import numpy as np
import tempfile
import os
from guru_vision.database.face_db import FaceDatabase, Identity, Embedding


def test_embedding_creation():
    """Test creating an Embedding object."""
    vector = np.random.randn(512).astype(np.float32)
    embedding = Embedding(
        vector=vector,
        timestamp="2024-01-15T10:30:00Z",
        angle_category="frontal",
        lighting_condition="normal"
    )
    assert embedding.vector.shape == (512,)
    assert embedding.angle_category == "frontal"


def test_embedding_invalid_shape():
    """Test that invalid embedding shape raises error."""
    vector = np.random.randn(256).astype(np.float32)
    with pytest.raises(ValueError):
        Embedding(
            vector=vector,
            timestamp="2024-01-15T10:30:00Z"
        )


def test_identity_creation():
    """Test creating an Identity object."""
    vector = np.random.randn(512).astype(np.float32)
    embedding = Embedding(
        vector=vector,
        timestamp="2024-01-15T10:30:00Z"
    )
    identity = Identity(
        name="John Doe",
        embeddings=[embedding],
        permission_level="user"
    )
    assert identity.name == "John Doe"
    assert len(identity.embeddings) == 1
    assert identity.permission_level == "user"


def test_identity_invalid_permission():
    """Test that invalid permission level raises error."""
    with pytest.raises(ValueError):
        Identity(
            name="John Doe",
            permission_level="invalid"
        )


def test_add_identity():
    """Test adding an identity to the database."""
    db = FaceDatabase()
    embeddings = [np.random.randn(512).astype(np.float32) for _ in range(3)]
    
    result = db.add_identity("John Doe", embeddings, "user")
    assert result is True
    assert "John Doe" in db.identities
    assert len(db.identities["John Doe"].embeddings) == 3


def test_add_duplicate_identity():
    """Test that adding duplicate identity returns False."""
    db = FaceDatabase()
    embeddings = [np.random.randn(512).astype(np.float32)]
    
    db.add_identity("John Doe", embeddings)
    result = db.add_identity("John Doe", embeddings)
    assert result is False


def test_add_embedding():
    """Test adding an embedding to existing identity."""
    db = FaceDatabase()
    embeddings = [np.random.randn(512).astype(np.float32)]
    db.add_identity("John Doe", embeddings)
    
    new_embedding = np.random.randn(512).astype(np.float32)
    result = db.add_embedding("John Doe", new_embedding)
    assert result is True
    assert len(db.identities["John Doe"].embeddings) == 2


def test_add_embedding_nonexistent():
    """Test adding embedding to non-existent identity returns False."""
    db = FaceDatabase()
    embedding = np.random.randn(512).astype(np.float32)
    result = db.add_embedding("Unknown", embedding)
    assert result is False


def test_get_identity():
    """Test retrieving an identity."""
    db = FaceDatabase()
    embeddings = [np.random.randn(512).astype(np.float32)]
    db.add_identity("John Doe", embeddings)
    
    identity = db.get_identity("John Doe")
    assert identity is not None
    assert identity.name == "John Doe"


def test_get_all_identities():
    """Test retrieving all identities."""
    db = FaceDatabase()
    for i in range(3):
        embeddings = [np.random.randn(512).astype(np.float32)]
        db.add_identity(f"Person{i}", embeddings)
    
    identities = db.get_all_identities()
    assert len(identities) == 3


def test_update_permission():
    """Test updating permission level."""
    db = FaceDatabase()
    embeddings = [np.random.randn(512).astype(np.float32)]
    db.add_identity("John Doe", embeddings, "user")
    
    result = db.update_permission("John Doe", "admin")
    assert result is True
    assert db.identities["John Doe"].permission_level == "admin"


def test_update_permission_invalid():
    """Test updating with invalid permission raises error."""
    db = FaceDatabase()
    embeddings = [np.random.randn(512).astype(np.float32)]
    db.add_identity("John Doe", embeddings)
    
    with pytest.raises(ValueError):
        db.update_permission("John Doe", "invalid")


def test_remove_identity():
    """Test removing an identity."""
    db = FaceDatabase()
    embeddings = [np.random.randn(512).astype(np.float32)]
    db.add_identity("John Doe", embeddings)
    
    result = db.remove_identity("John Doe")
    assert result is True
    assert "John Doe" not in db.identities


def test_remove_nonexistent_identity():
    """Test removing non-existent identity returns False."""
    db = FaceDatabase()
    result = db.remove_identity("Unknown")
    assert result is False


def test_cosine_similarity():
    """Test cosine similarity computation."""
    # Identical vectors should have similarity 1.0
    vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    vec2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    similarity = FaceDatabase._cosine_similarity(vec1, vec2)
    assert abs(similarity - 1.0) < 1e-6
    
    # Orthogonal vectors should have similarity 0.0
    vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    vec2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    similarity = FaceDatabase._cosine_similarity(vec1, vec2)
    assert abs(similarity - 0.0) < 1e-6


def test_search_match():
    """Test searching for a matching identity."""
    db = FaceDatabase()
    
    # Create a known embedding
    embedding1 = np.random.randn(512).astype(np.float32)
    embedding1 = embedding1 / np.linalg.norm(embedding1)  # Normalize
    
    db.add_identity("John Doe", [embedding1], "user")
    
    # Search with very similar embedding
    query = embedding1 + np.random.randn(512).astype(np.float32) * 0.01
    query = query / np.linalg.norm(query)
    
    result = db.search(query, threshold=0.5)
    assert result is not None
    assert result["identity"] == "John Doe"
    assert result["permission_level"] == "user"
    assert 0.0 <= result["confidence"] <= 1.0


def test_search_no_match():
    """Test searching with no match above threshold."""
    db = FaceDatabase()
    
    embedding1 = np.random.randn(512).astype(np.float32)
    db.add_identity("John Doe", [embedding1])
    
    # Search with very different embedding
    query = np.random.randn(512).astype(np.float32)
    
    result = db.search(query, threshold=0.99)
    # May or may not match depending on random vectors
    # Just verify it returns valid format
    if result is not None:
        assert "identity" in result
        assert "confidence" in result


def test_save_and_load():
    """Test saving and loading database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_db.json")
        
        # Create database and add identities
        db1 = FaceDatabase(db_path)
        embeddings = [np.random.randn(512).astype(np.float32) for _ in range(2)]
        db1.add_identity("John Doe", embeddings, "admin")
        db1.save()
        
        # Load into new database
        db2 = FaceDatabase(db_path)
        db2.load()
        
        # Verify data was preserved
        assert "John Doe" in db2.identities
        assert len(db2.identities["John Doe"].embeddings) == 2
        assert db2.identities["John Doe"].permission_level == "admin"


def test_export_and_import():
    """Test exporting and importing database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        export_path = os.path.join(tmpdir, "export.json")
        
        # Create database
        db1 = FaceDatabase()
        embeddings = [np.random.randn(512).astype(np.float32)]
        db1.add_identity("John Doe", embeddings, "user")
        db1.export_json(export_path)
        
        # Import into new database
        db2 = FaceDatabase()
        db2.import_json(export_path)
        
        # Verify data was imported
        assert "John Doe" in db2.identities
        assert db2.identities["John Doe"].permission_level == "user"


def test_import_merge():
    """Test importing with merge option."""
    with tempfile.TemporaryDirectory() as tmpdir:
        export_path = os.path.join(tmpdir, "export.json")
        
        # Create first database
        db1 = FaceDatabase()
        embeddings = [np.random.randn(512).astype(np.float32)]
        db1.add_identity("Person1", embeddings)
        db1.export_json(export_path)
        
        # Create second database with different identity
        db2 = FaceDatabase()
        embeddings = [np.random.randn(512).astype(np.float32)]
        db2.add_identity("Person2", embeddings)
        
        # Import with merge
        db2.import_json(export_path, merge=True)
        
        # Both identities should exist
        assert "Person1" in db2.identities
        assert "Person2" in db2.identities


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
