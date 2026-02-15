"""
Property-Based Tests for Face Recognition Module

This module contains property-based tests using Hypothesis to validate
universal correctness properties of the face recognition operations.

Properties tested:
- Property 3: Embedding Vector Dimensions
- Property 4: Cosine Similarity Range
- Property 5: Threshold-Based Identity Matching
- Property 6: Multi-Embedding Maximum Similarity
"""

import pytest
import numpy as np
import tempfile
import os
from unittest.mock import MagicMock, patch
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from guru_vision.recognition.recognizer import FaceRecognizer, MatchResult
from guru_vision.database.face_db import FaceDatabase


# Custom strategies for generating test data

@st.composite
def aligned_face_image(draw):
    """Generate a valid aligned face image (112x112x3)."""
    # Generate random pixel values in uint8 range [0, 255]
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    rng = np.random.RandomState(seed)
    face = rng.randint(0, 256, size=(112, 112, 3), dtype=np.uint8)
    return face


@st.composite
def embedding_vector(draw):
    """Generate a valid 512-dimensional embedding vector."""
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    rng = np.random.RandomState(seed)
    vector = rng.randn(512).astype(np.float32)
    # L2-normalize to simulate real embeddings
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector


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
def threshold_value(draw):
    """Generate a valid threshold value between 0.0 and 1.0."""
    return draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))


def create_mock_recognizer():
    """Create a mocked FaceRecognizer for testing."""
    with patch('onnxruntime.InferenceSession'), patch('os.path.exists') as mock_exists:
        mock_exists.return_value = True
        recognizer = FaceRecognizer("dummy_model.onnx", use_gpu=False)
        
        # Mock the session to return deterministic embeddings
        def mock_run(output_names, input_dict):
            # Generate deterministic embedding based on input
            input_data = input_dict[recognizer.input_name]
            # Use input mean as seed for reproducibility
            seed = int(np.abs(input_data.mean() * 1000000)) % (2**31)
            rng = np.random.RandomState(seed)
            embedding = rng.randn(1, 512).astype(np.float32)
            return [embedding]
        
        recognizer.session.run = mock_run
        return recognizer


# Property 3: Embedding Vector Dimensions
# **Validates: Requirements 5.1**

@given(face=aligned_face_image())
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_3_embedding_vector_dimensions(face):
    """
    Property 3: Embedding Vector Dimensions
    
    For any aligned face image, when processed by the Embedding_Extractor,
    the resulting embedding vector should have exactly 512 dimensions.
    
    **Validates: Requirements 5.1**
    """
    recognizer = create_mock_recognizer()
    
    # Extract embedding
    embedding = recognizer.extract_embedding(face)
    
    # Verify embedding has exactly 512 dimensions
    assert isinstance(embedding, np.ndarray), \
        "Embedding should be a numpy array"
    assert embedding.shape == (512,), \
        f"Embedding should have shape (512,), got {embedding.shape}"
    assert embedding.dtype in [np.float32, np.float64], \
        f"Embedding should be float type, got {embedding.dtype}"


# Property 4: Cosine Similarity Range
# **Validates: Requirements 5.2**

@given(
    embedding1=embedding_vector(),
    embedding2=embedding_vector()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_4_cosine_similarity_range(embedding1, embedding2):
    """
    Property 4: Cosine Similarity Range
    
    For any two embedding vectors, when computing cosine similarity,
    the result should be a value between 0.0 and 1.0 inclusive.
    
    **Validates: Requirements 5.2**
    """
    # Use the database's cosine similarity function
    from guru_vision.database.face_db import FaceDatabase
    
    similarity = FaceDatabase._cosine_similarity(embedding1, embedding2)
    
    # Verify similarity is in valid range
    assert isinstance(similarity, (float, np.floating)), \
        f"Similarity should be a float, got {type(similarity)}"
    assert 0.0 <= similarity <= 1.0, \
        f"Cosine similarity should be between 0.0 and 1.0, got {similarity}"
    
    # Additional property: similarity with self should be 1.0 (or very close)
    self_similarity = FaceDatabase._cosine_similarity(embedding1, embedding1)
    assert np.isclose(self_similarity, 1.0, atol=1e-6), \
        f"Self-similarity should be 1.0, got {self_similarity}"


# Property 5: Threshold-Based Identity Matching
# **Validates: Requirements 5.3, 5.4**

@given(
    name=identity_name(),
    stored_embedding=embedding_vector(),
    query_embedding=embedding_vector(),
    threshold=threshold_value(),
    perm_level=permission_level()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_5_threshold_based_matching(name, stored_embedding, query_embedding, threshold, perm_level):
    """
    Property 5: Threshold-Based Identity Matching
    
    For any embedding and database, when the maximum similarity score is above
    the recognition threshold, a matched identity should be returned; when all
    similarities are below the threshold, "Unknown" should be returned.
    
    **Validates: Requirements 5.3, 5.4**
    """
    recognizer = create_mock_recognizer()
    
    # Create database with one identity
    db = FaceDatabase()
    db.add_identity(name, [stored_embedding], perm_level)
    
    # Compute actual similarity
    from guru_vision.database.face_db import FaceDatabase as DB
    actual_similarity = DB._cosine_similarity(query_embedding, stored_embedding)
    
    # Match identity
    result = recognizer.match_identity(query_embedding, db, threshold)
    
    # Verify threshold-based behavior
    assert isinstance(result, MatchResult), \
        "Result should be a MatchResult object"
    
    if actual_similarity >= threshold:
        # Should match the identity
        assert result.identity == name, \
            f"Should match identity '{name}' when similarity {actual_similarity:.4f} >= threshold {threshold:.4f}"
        assert result.confidence == pytest.approx(actual_similarity, abs=1e-6), \
            f"Confidence should equal similarity score"
        assert result.permission_level == perm_level, \
            f"Should return correct permission level"
    else:
        # Should return "Unknown"
        assert result.identity == "Unknown", \
            f"Should return 'Unknown' when similarity {actual_similarity:.4f} < threshold {threshold:.4f}"
        assert result.confidence == 0.0, \
            "Confidence should be 0.0 for unknown identity"
        assert result.permission_level == "guest", \
            "Permission level should be 'guest' for unknown identity"


# Property 6: Multi-Embedding Maximum Similarity
# **Validates: Requirements 5.7**

@given(
    name=identity_name(),
    num_embeddings=st.integers(min_value=2, max_value=10),
    query_embedding=embedding_vector(),
    threshold=st.floats(min_value=0.3, max_value=0.7),
    perm_level=permission_level()
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_6_multi_embedding_maximum_similarity(name, num_embeddings, query_embedding, threshold, perm_level):
    """
    Property 6: Multi-Embedding Maximum Similarity
    
    For any identity with multiple stored embeddings, when matching against
    a query embedding, the system should compare against all stored embeddings
    and return the highest similarity score.
    
    **Validates: Requirements 5.7**
    """
    recognizer = create_mock_recognizer()
    
    # Generate multiple embeddings for the identity
    seed = hash(name) % (2**31)
    rng = np.random.RandomState(seed)
    stored_embeddings = []
    for i in range(num_embeddings):
        emb = rng.randn(512).astype(np.float32)
        # Normalize
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        stored_embeddings.append(emb)
    
    # Create database with multiple embeddings
    db = FaceDatabase()
    db.add_identity(name, stored_embeddings, perm_level)
    
    # Compute similarity with each stored embedding
    from guru_vision.database.face_db import FaceDatabase as DB
    similarities = [
        DB._cosine_similarity(query_embedding, stored_emb)
        for stored_emb in stored_embeddings
    ]
    max_similarity = max(similarities)
    
    # Match identity
    result = recognizer.match_identity(query_embedding, db, threshold)
    
    # Verify the system uses the maximum similarity
    if max_similarity >= threshold:
        # Should match with the highest similarity
        assert result.identity == name, \
            f"Should match identity when max similarity {max_similarity:.4f} >= threshold {threshold:.4f}"
        assert result.confidence == pytest.approx(max_similarity, abs=1e-6), \
            f"Confidence should equal maximum similarity across all embeddings"
        assert result.permission_level == perm_level, \
            "Should return correct permission level"
        
        # Verify it's actually the maximum (not just any similarity above threshold)
        assert result.confidence >= max(similarities) - 1e-6, \
            "Returned confidence should be the maximum similarity, not just any above threshold"
    else:
        # All similarities below threshold - should return "Unknown"
        assert result.identity == "Unknown", \
            f"Should return 'Unknown' when max similarity {max_similarity:.4f} < threshold {threshold:.4f}"
        assert result.confidence == 0.0, \
            "Confidence should be 0.0 for unknown identity"


# Additional property: Embedding normalization
@given(face=aligned_face_image())
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_embedding_normalization(face):
    """
    Property: Embedding L2 Normalization
    
    All extracted embeddings should be L2-normalized (unit length).
    This is important for cosine similarity computation.
    """
    recognizer = create_mock_recognizer()
    
    # Extract embedding
    embedding = recognizer.extract_embedding(face)
    
    # Verify L2 normalization (unit length)
    norm = np.linalg.norm(embedding)
    assert np.isclose(norm, 1.0, atol=1e-6), \
        f"Embedding should be L2-normalized (unit length), got norm {norm}"


# Additional property: Consistent embedding extraction
@given(face=aligned_face_image())
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_consistent_embedding_extraction(face):
    """
    Property: Consistent Embedding Extraction
    
    Extracting embeddings from the same face image multiple times should
    produce identical results (deterministic behavior).
    """
    recognizer = create_mock_recognizer()
    
    # Extract embedding twice
    embedding1 = recognizer.extract_embedding(face)
    embedding2 = recognizer.extract_embedding(face)
    
    # Verify embeddings are identical
    assert np.allclose(embedding1, embedding2, rtol=1e-7, atol=1e-9), \
        "Extracting embedding from same face should produce identical results"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
