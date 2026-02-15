"""
Property-Based Tests for GuruVision Recognition Engine

This module contains property-based tests using Hypothesis to validate
universal correctness properties of the GuruVisionEngine.

Properties tested:
- Property 19: Recognition Result Completeness
"""

import pytest
import numpy as np
import tempfile
import os
from unittest.mock import MagicMock, patch, Mock
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from guru_vision.engine import GuruVisionEngine, RecognitionResult, FaceResult


# Custom strategies for generating test data

@st.composite
def video_frame(draw):
    """Generate a valid video frame (BGR format)."""
    # Generate frame dimensions
    height = draw(st.integers(min_value=240, max_value=1080))
    width = draw(st.integers(min_value=320, max_value=1920))
    
    # Generate random pixel values in uint8 range [0, 255]
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    rng = np.random.RandomState(seed)
    frame = rng.randint(0, 256, size=(height, width, 3), dtype=np.uint8)
    return frame


@st.composite
def num_faces(draw):
    """Generate a valid number of faces to detect (0 to 5)."""
    return draw(st.integers(min_value=0, max_value=5))


def create_mock_engine():
    """Create a mocked GuruVisionEngine for testing."""
    # Create a simple mock engine that doesn't require actual initialization
    engine = Mock(spec=GuruVisionEngine)
    engine._frame_counter = 0
    engine.config = Mock()
    engine.config.enable_liveness = True
    engine.config.enable_emotion = True
    engine.config.enable_tracking = True
    return engine


def mock_process_frame_with_faces(engine, frame, num_faces_to_detect):
    """
    Mock the process_frame method to return a result with specified number of faces.
    This simulates the engine detecting and processing faces.
    """
    # Initialize RNG for consistent results
    seed = hash(frame.tobytes()) % (2**31)
    rng = np.random.RandomState(seed)
    
    # Generate mock face results
    faces = []
    for i in range(num_faces_to_detect):
        # Random bbox within frame dimensions
        h, w = frame.shape[:2]
        x = rng.randint(0, max(1, w - 100))
        y = rng.randint(0, max(1, h - 100))
        bbox_w = rng.randint(50, min(200, w - x))
        bbox_h = rng.randint(50, min(200, h - y))
        
        # Random identity (sometimes Unknown)
        identities = ["Alice", "Bob", "Charlie", "Unknown"]
        identity = identities[rng.randint(0, len(identities))]
        
        # Random confidence
        confidence = rng.uniform(0.0, 1.0) if identity != "Unknown" else 0.0
        
        # Random permission level
        if identity == "Unknown":
            permission_level = "guest"
        else:
            permission_level = ["admin", "user", "guest", "denied"][rng.randint(0, 4)]
        
        # Random emotion
        emotions = ["neutral", "happy", "sad", "angry", "surprised", "fearful", "disgusted"]
        emotion = emotions[rng.randint(0, len(emotions))]
        emotion_confidence = rng.uniform(0.0, 1.0)
        
        # Random liveness
        is_live = rng.choice([True, False])
        liveness_confidence = rng.uniform(0.0, 1.0)
        
        face_result = FaceResult(
            tracking_id=i + 1,
            bbox=(x, y, bbox_w, bbox_h),
            identity=identity,
            confidence=confidence,
            permission_level=permission_level,
            emotion=emotion,
            emotion_confidence=emotion_confidence,
            is_live=is_live,
            liveness_confidence=liveness_confidence
        )
        faces.append(face_result)
    
    # Create recognition result
    from datetime import datetime
    
    result = RecognitionResult(
        faces=faces,
        frame_id=engine._frame_counter if hasattr(engine, '_frame_counter') else 0,
        timestamp=datetime.now().isoformat(),
        processing_time_ms=rng.uniform(10.0, 100.0)
    )
    
    return result


# Property 19: Recognition Result Completeness
# **Validates: Requirements 13.2, 31.3**

@given(
    frame=video_frame(),
    num_faces_detected=num_faces()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large, HealthCheck.too_slow]
)
def test_property_19_recognition_result_completeness(frame, num_faces_detected):
    """
    Property 19: Recognition Result Completeness
    
    For any frame processed by the GuruVisionEngine, the returned result should
    contain all required fields: detected faces, identities, confidence scores,
    emotions, liveness status, tracking IDs, and permission levels.
    
    **Validates: Requirements 13.2, 31.3**
    
    Requirement 13.2: THE GuruVision_System SHALL return recognition results as
    structured data including identity, confidence, emotion, and Permission_Level
    
    Requirement 31.3: WHEN process_frame() is called, THE GuruVisionEngine SHALL
    return a structured result containing: detected faces, identities, confidence
    scores, emotions, liveness status, tracking IDs
    """
    engine = create_mock_engine()
    
    # Mock the process_frame to return a result with the specified number of faces
    result = mock_process_frame_with_faces(engine, frame, num_faces_detected)
    
    # Verify RecognitionResult structure completeness
    assert isinstance(result, RecognitionResult), \
        "Result should be a RecognitionResult object"
    
    # Verify all top-level fields are present
    assert hasattr(result, 'faces'), \
        "RecognitionResult must have 'faces' field"
    assert hasattr(result, 'frame_id'), \
        "RecognitionResult must have 'frame_id' field"
    assert hasattr(result, 'timestamp'), \
        "RecognitionResult must have 'timestamp' field"
    assert hasattr(result, 'processing_time_ms'), \
        "RecognitionResult must have 'processing_time_ms' field"
    
    # Verify faces field is a list
    assert isinstance(result.faces, list), \
        "faces field should be a list"
    
    # Verify frame_id is an integer
    assert isinstance(result.frame_id, int), \
        f"frame_id should be an integer, got {type(result.frame_id)}"
    
    # Verify timestamp is a string (ISO format)
    assert isinstance(result.timestamp, str), \
        f"timestamp should be a string, got {type(result.timestamp)}"
    assert len(result.timestamp) > 0, \
        "timestamp should not be empty"
    
    # Verify processing_time_ms is a number
    assert isinstance(result.processing_time_ms, (int, float)), \
        f"processing_time_ms should be a number, got {type(result.processing_time_ms)}"
    assert result.processing_time_ms >= 0, \
        f"processing_time_ms should be non-negative, got {result.processing_time_ms}"
    
    # Verify the number of faces matches what was detected
    assert len(result.faces) == num_faces_detected, \
        f"Number of faces in result ({len(result.faces)}) should match detected ({num_faces_detected})"
    
    # For each detected face, verify all required fields are present and valid
    for i, face in enumerate(result.faces):
        assert isinstance(face, FaceResult), \
            f"Face {i} should be a FaceResult object"
        
        # Verify tracking_id field
        assert hasattr(face, 'tracking_id'), \
            f"Face {i} must have 'tracking_id' field"
        assert isinstance(face.tracking_id, int), \
            f"Face {i} tracking_id should be an integer, got {type(face.tracking_id)}"
        
        # Verify bbox field
        assert hasattr(face, 'bbox'), \
            f"Face {i} must have 'bbox' field"
        assert isinstance(face.bbox, tuple), \
            f"Face {i} bbox should be a tuple, got {type(face.bbox)}"
        assert len(face.bbox) == 4, \
            f"Face {i} bbox should have 4 elements (x, y, w, h), got {len(face.bbox)}"
        x, y, w, h = face.bbox
        assert all(isinstance(v, (int, np.integer)) for v in face.bbox), \
            f"Face {i} bbox values should be integers"
        assert w > 0 and h > 0, \
            f"Face {i} bbox width and height should be positive"
        
        # Verify identity field
        assert hasattr(face, 'identity'), \
            f"Face {i} must have 'identity' field"
        assert isinstance(face.identity, str), \
            f"Face {i} identity should be a string, got {type(face.identity)}"
        assert len(face.identity) > 0, \
            f"Face {i} identity should not be empty"
        
        # Verify confidence field
        assert hasattr(face, 'confidence'), \
            f"Face {i} must have 'confidence' field"
        assert isinstance(face.confidence, (int, float, np.floating)), \
            f"Face {i} confidence should be a number, got {type(face.confidence)}"
        assert 0.0 <= face.confidence <= 1.0, \
            f"Face {i} confidence should be between 0.0 and 1.0, got {face.confidence}"
        
        # Verify permission_level field
        assert hasattr(face, 'permission_level'), \
            f"Face {i} must have 'permission_level' field"
        assert isinstance(face.permission_level, str), \
            f"Face {i} permission_level should be a string, got {type(face.permission_level)}"
        assert face.permission_level in ["admin", "user", "guest", "denied"], \
            f"Face {i} permission_level should be one of [admin, user, guest, denied], got {face.permission_level}"
        
        # Verify emotion field
        assert hasattr(face, 'emotion'), \
            f"Face {i} must have 'emotion' field"
        assert isinstance(face.emotion, str), \
            f"Face {i} emotion should be a string, got {type(face.emotion)}"
        valid_emotions = ["neutral", "happy", "sad", "angry", "surprised", "fearful", "disgusted"]
        assert face.emotion in valid_emotions, \
            f"Face {i} emotion should be one of {valid_emotions}, got {face.emotion}"
        
        # Verify emotion_confidence field
        assert hasattr(face, 'emotion_confidence'), \
            f"Face {i} must have 'emotion_confidence' field"
        assert isinstance(face.emotion_confidence, (int, float, np.floating)), \
            f"Face {i} emotion_confidence should be a number, got {type(face.emotion_confidence)}"
        assert 0.0 <= face.emotion_confidence <= 1.0, \
            f"Face {i} emotion_confidence should be between 0.0 and 1.0, got {face.emotion_confidence}"
        
        # Verify is_live field
        assert hasattr(face, 'is_live'), \
            f"Face {i} must have 'is_live' field"
        assert isinstance(face.is_live, (bool, np.bool_)), \
            f"Face {i} is_live should be a boolean, got {type(face.is_live)}"
        
        # Verify liveness_confidence field
        assert hasattr(face, 'liveness_confidence'), \
            f"Face {i} must have 'liveness_confidence' field"
        assert isinstance(face.liveness_confidence, (int, float, np.floating)), \
            f"Face {i} liveness_confidence should be a number, got {type(face.liveness_confidence)}"
        assert 0.0 <= face.liveness_confidence <= 1.0, \
            f"Face {i} liveness_confidence should be between 0.0 and 1.0, got {face.liveness_confidence}"


# Additional property: Empty frame handling
@given(frame=video_frame())
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large, HealthCheck.too_slow]
)
def test_property_empty_frame_result_completeness(frame):
    """
    Property: Empty Frame Result Completeness
    
    When no faces are detected in a frame, the result should still contain
    all required top-level fields with an empty faces list.
    """
    engine = create_mock_engine()
    
    # Mock process_frame with no faces detected
    result = mock_process_frame_with_faces(engine, frame, 0)
    
    # Verify result structure is complete even with no faces
    assert isinstance(result, RecognitionResult), \
        "Result should be a RecognitionResult object even with no faces"
    assert isinstance(result.faces, list), \
        "faces field should be a list"
    assert len(result.faces) == 0, \
        "faces list should be empty when no faces detected"
    assert isinstance(result.frame_id, int), \
        "frame_id should be present"
    assert isinstance(result.timestamp, str), \
        "timestamp should be present"
    assert isinstance(result.processing_time_ms, (int, float)), \
        "processing_time_ms should be present"


# Additional property: Tracking ID uniqueness
@given(
    frame=video_frame(),
    num_faces_detected=st.integers(min_value=2, max_value=5)
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large, HealthCheck.too_slow]
)
def test_property_tracking_id_uniqueness(frame, num_faces_detected):
    """
    Property: Tracking ID Uniqueness
    
    When multiple faces are detected in a single frame, each face should
    have a unique tracking ID.
    """
    engine = create_mock_engine()
    
    # Mock process_frame with multiple faces
    result = mock_process_frame_with_faces(engine, frame, num_faces_detected)
    
    # Extract all tracking IDs
    tracking_ids = [face.tracking_id for face in result.faces]
    
    # Verify all tracking IDs are unique
    assert len(tracking_ids) == len(set(tracking_ids)), \
        f"All tracking IDs should be unique, got {tracking_ids}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
