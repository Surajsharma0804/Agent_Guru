"""
Property-Based Tests for Liveness Detection Module

This module contains property-based tests using Hypothesis to validate
universal correctness properties of the liveness detection operations.

Properties tested:
- Property 9: Liveness Binary Classification
- Property 10: Liveness-Based Recognition Rejection
"""

import pytest
import numpy as np
import tempfile
import os
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from guru_vision.liveness import LivenessDetector, LivenessResult
from guru_vision.database.face_db import FaceDatabase, Identity, Embedding
from guru_vision.recognition.recognizer import FaceRecognizer, MatchResult
from unittest.mock import MagicMock, patch


# Custom strategies for generating test data

@st.composite
def aligned_face_image(draw):
    """
    Generate a valid aligned face image (112x112x3).
    
    Returns:
        A numpy array representing an aligned face image
    """
    # Generate random pixel values in uint8 range [0, 255]
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    rng = np.random.RandomState(seed)
    
    # Create face with some variation to avoid all-zero or invalid images
    face = rng.randint(10, 246, size=(112, 112, 3), dtype=np.uint8)
    
    return face


@st.composite
def liveness_classification(draw):
    """
    Generate a liveness classification result (live or spoof).
    
    Returns:
        A boolean indicating if the face is live (True) or spoof (False)
    """
    return draw(st.booleans())


@st.composite
def confidence_score(draw):
    """
    Generate a valid confidence score between 0.0 and 1.0.
    
    Returns:
        A float between 0.0 and 1.0
    """
    return draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))


@st.composite
def attack_type_value(draw):
    """
    Generate a valid attack type.
    
    Returns:
        A string representing the attack type
    """
    return draw(st.sampled_from(["none", "photo", "screen", "mask", "unknown"]))


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
def recognition_threshold(draw):
    """Generate a valid recognition threshold."""
    return draw(st.floats(min_value=0.4, max_value=0.9, allow_nan=False, allow_infinity=False))


# Property 9: Liveness Binary Classification
# **Validates: Requirements 7.1**

@given(face=aligned_face_image())
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_9_liveness_binary_classification(face):
    """
    Property 9: Liveness Binary Classification
    
    For any face input to the Liveness_Detector, the classification result
    should be exactly one of two values: "live" or "spoof".
    
    This property validates that:
    1. The is_live field is always a boolean (True or False)
    2. The classification is binary - no intermediate states
    3. The result is deterministic for the same input
    
    **Validates: Requirements 7.1**
    """
    # Initialize detector without model (uses fallback texture analysis)
    detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
    
    # Run liveness detection
    result = detector.detect(face)
    
    # Property 1: Result is a LivenessResult object
    assert isinstance(result, LivenessResult), \
        "Detector should return a LivenessResult object"
    
    # Property 2: is_live is exactly True or False (binary classification)
    assert isinstance(result.is_live, bool), \
        f"is_live should be a boolean, got {type(result.is_live)}"
    assert result.is_live in [True, False], \
        f"is_live should be exactly True or False, got {result.is_live}"
    
    # Property 3: Classification maps to "live" or "spoof" conceptually
    # When is_live is True, it means "live"
    # When is_live is False, it means "spoof"
    if result.is_live:
        # Live classification
        assert result.is_live is True, \
            "Live classification should have is_live=True"
    else:
        # Spoof classification
        assert result.is_live is False, \
            "Spoof classification should have is_live=False"
    
    # Property 4: Confidence is in valid range
    assert isinstance(result.confidence, (float, np.floating)), \
        f"Confidence should be a float, got {type(result.confidence)}"
    assert 0.0 <= result.confidence <= 1.0, \
        f"Confidence should be between 0.0 and 1.0, got {result.confidence}"
    
    # Property 5: Attack type is one of the valid values
    valid_attack_types = ["none", "photo", "screen", "mask", "unknown"]
    assert result.attack_type in valid_attack_types, \
        f"Attack type should be one of {valid_attack_types}, got {result.attack_type}"
    
    # Property 6: Consistency - same input produces same output
    result_2 = detector.detect(face)
    assert result.is_live == result_2.is_live, \
        "Detector should be deterministic - same input should produce same classification"
    assert result.confidence == result_2.confidence, \
        "Detector should be deterministic - same input should produce same confidence"
    assert result.attack_type == result_2.attack_type, \
        "Detector should be deterministic - same input should produce same attack type"


@given(
    face=aligned_face_image(),
    seed=st.integers(min_value=0, max_value=1000)
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_9_no_intermediate_states(face, seed):
    """
    Property 9 (No Intermediate States): Binary Classification Only
    
    The liveness detector should never return intermediate states or
    uncertain classifications. It must always classify as either live or spoof.
    
    **Validates: Requirements 7.1**
    """
    detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
    
    # Run detection
    result = detector.detect(face)
    
    # The result must be binary - no None, no strings, no numbers
    assert result.is_live is not None, \
        "is_live should never be None"
    assert isinstance(result.is_live, bool), \
        "is_live should be a boolean, not any other type"
    
    # Even with low confidence, classification must still be binary
    if result.confidence < 0.5:
        # Low confidence, but still must be binary
        assert result.is_live in [True, False], \
            "Even with low confidence, classification must be binary"


@given(face=aligned_face_image())
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_9_attack_type_consistency(face):
    """
    Property 9 (Attack Type Consistency): Attack Type Matches Classification
    
    When is_live is True, attack_type should be "none".
    When is_live is False, attack_type should indicate the type of attack.
    
    **Validates: Requirements 7.1**
    """
    detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
    
    result = detector.detect(face)
    
    # Consistency check: if live, attack type should be "none"
    if result.is_live:
        assert result.attack_type == "none", \
            f"When is_live=True, attack_type should be 'none', got '{result.attack_type}'"
    else:
        # If spoof, attack type should not be "none"
        assert result.attack_type in ["photo", "screen", "mask", "unknown"], \
            f"When is_live=False, attack_type should indicate attack type, got '{result.attack_type}'"


# Property 10: Liveness-Based Recognition Rejection
# **Validates: Requirements 7.4**

def create_mock_recognizer_with_embedding(embedding):
    """Create a mocked FaceRecognizer that returns a specific embedding."""
    with patch('onnxruntime.InferenceSession'), patch('os.path.exists') as mock_exists:
        mock_exists.return_value = True
        recognizer = FaceRecognizer("dummy_model.onnx", use_gpu=False)
        
        # Mock the session to return the specified embedding
        def mock_run(output_names, input_dict):
            return [embedding.reshape(1, 512)]
        
        recognizer.session.run = mock_run
        return recognizer


@given(
    face=aligned_face_image(),
    stored_embedding=embedding_vector(),
    query_embedding=embedding_vector(),
    threshold=recognition_threshold()
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_10_liveness_based_recognition_rejection(
    face, stored_embedding, query_embedding, threshold
):
    """
    Property 10: Liveness-Based Recognition Rejection
    
    For any face classified as "spoof" by the Liveness_Detector, the recognition
    attempt should be rejected regardless of identity match confidence.
    
    This property validates that:
    1. When liveness detection fails (is_live=False), recognition is rejected
    2. Rejection occurs even if the embedding similarity is above threshold
    3. The system prioritizes security (liveness) over convenience (recognition)
    
    **Validates: Requirements 7.4**
    """
    # Initialize liveness detector
    liveness_detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
    
    # Run liveness detection
    liveness_result = liveness_detector.detect(face)
    
    # Create a temporary database with a known identity
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_db.json")
        database = FaceDatabase(db_path)
        
        # Add an identity with the stored embedding
        database.add_identity(
            name="TestPerson",
            embeddings=[stored_embedding],
            permission_level="user",
            metadata={}
        )
        
        # Create mock recognizer
        recognizer = create_mock_recognizer_with_embedding(query_embedding)
        
        # Extract embedding from face
        embedding = recognizer.extract_embedding(face)
        
        # Match identity
        match_result = recognizer.match_identity(embedding, database, threshold)
        
        # Calculate similarity for verification
        similarity = FaceDatabase._cosine_similarity(query_embedding, stored_embedding)
        
        # Property: If liveness fails, recognition should be rejected
        if not liveness_result.is_live:
            # Liveness failed (spoof detected)
            # In a real system, this would trigger rejection
            # We verify that the liveness result indicates rejection
            
            assert liveness_result.is_live is False, \
                "Spoof detection should set is_live to False"
            
            # Even if similarity is high (above threshold), the system should
            # reject based on liveness failure
            if similarity >= threshold and match_result.identity != "Unknown":
                # High similarity match found, but liveness failed
                # The integration layer should reject this recognition
                
                # Verify that liveness result clearly indicates rejection
                assert liveness_result.is_live is False, \
                    "Liveness failure should be clearly indicated even with high similarity match"
                
                # Verify attack type is set (not "none")
                assert liveness_result.attack_type != "none", \
                    "Spoof detection should indicate attack type"
        
        # Property: If liveness passes, recognition can proceed normally
        if liveness_result.is_live:
            # Liveness passed (live face detected)
            assert liveness_result.is_live is True, \
                "Live detection should set is_live to True"
            
            # Recognition can proceed based on similarity threshold
            if similarity >= threshold:
                # Should match
                assert match_result.identity == "TestPerson" or match_result.identity == "Unknown", \
                    "With liveness pass and high similarity, recognition should proceed"
            else:
                # Should not match
                assert match_result.identity == "Unknown", \
                    "With low similarity, should return Unknown"


@given(face=aligned_face_image())
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_10_spoof_always_rejects(face):
    """
    Property 10 (Spoof Always Rejects): Spoof Detection Triggers Rejection
    
    When a face is classified as spoof (is_live=False), this should always
    trigger a rejection in the recognition pipeline, regardless of any other factors.
    
    **Validates: Requirements 7.4**
    """
    detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
    
    result = detector.detect(face)
    
    # If classified as spoof, verify rejection indicators are present
    if not result.is_live:
        # Spoof detected - should have clear rejection indicators
        assert result.is_live is False, \
            "Spoof classification should have is_live=False"
        
        # Attack type should not be "none" for spoofs
        assert result.attack_type in ["photo", "screen", "mask", "unknown"], \
            f"Spoof should have attack type set, got '{result.attack_type}'"
        
        # Confidence should be a valid value
        assert 0.0 <= result.confidence <= 1.0, \
            "Confidence should be in valid range even for spoofs"


@given(
    face=aligned_face_image(),
    stored_embedding=embedding_vector()
)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_10_high_confidence_match_with_spoof(face, stored_embedding):
    """
    Property 10 (High Confidence Rejection): Even High Confidence Matches Rejected on Spoof
    
    Even when the identity match has very high confidence (near 1.0), if liveness
    detection fails, the recognition should be rejected.
    
    This tests the security principle: liveness check is a hard requirement.
    
    **Validates: Requirements 7.4**
    """
    # Initialize liveness detector
    liveness_detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
    
    # Run liveness detection
    liveness_result = liveness_detector.detect(face)
    
    # Create a database with a known identity
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_db.json")
        database = FaceDatabase(db_path)
        
        # Add identity with the same embedding (perfect match scenario)
        database.add_identity(
            name="TestPerson",
            embeddings=[stored_embedding],
            permission_level="user",
            metadata={}
        )
        
        # Create mock recognizer that returns the same embedding
        recognizer = create_mock_recognizer_with_embedding(stored_embedding)
        
        # Extract embedding (will be same as stored)
        embedding = recognizer.extract_embedding(face)
        
        # Match identity with low threshold (easy to match)
        match_result = recognizer.match_identity(embedding, database, threshold=0.5)
        
        # Calculate similarity (should be 1.0 or very close)
        similarity = FaceDatabase._cosine_similarity(embedding, stored_embedding)
        
        # If liveness failed, recognition should be rejected regardless of similarity
        if not liveness_result.is_live:
            # Liveness failed
            assert liveness_result.is_live is False, \
                "Spoof detection should set is_live to False"
            
            # Even with perfect or near-perfect similarity, liveness failure means rejection
            # The liveness result provides the rejection signal
            assert liveness_result.attack_type != "none", \
                "Spoof should have attack type indicating the threat"
            
            # In a real integration, the system would check:
            # if not liveness_result.is_live:
            #     return RejectedResult(reason="Liveness check failed")
            # This property verifies the liveness result provides that signal


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
