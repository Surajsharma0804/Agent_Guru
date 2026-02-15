"""
Basic tests for GuruVision Engine

This test file verifies the basic functionality of the GuruVisionEngine class
including initialization and data structure creation.
"""

import pytest
import numpy as np
from guru_vision.engine import GuruVisionEngine, FaceResult, RecognitionResult, IdentityInfo


def test_face_result_creation():
    """Test FaceResult dataclass creation."""
    face_result = FaceResult(
        tracking_id=1,
        bbox=(100, 100, 50, 50),
        identity="John Doe",
        confidence=0.85,
        permission_level="user",
        emotion="happy",
        emotion_confidence=0.75,
        is_live=True,
        liveness_confidence=0.90
    )
    
    assert face_result.tracking_id == 1
    assert face_result.bbox == (100, 100, 50, 50)
    assert face_result.identity == "John Doe"
    assert face_result.confidence == 0.85
    assert face_result.permission_level == "user"
    assert face_result.emotion == "happy"
    assert face_result.emotion_confidence == 0.75
    assert face_result.is_live is True
    assert face_result.liveness_confidence == 0.90


def test_recognition_result_creation():
    """Test RecognitionResult dataclass creation."""
    face1 = FaceResult(
        tracking_id=1,
        bbox=(100, 100, 50, 50),
        identity="John Doe",
        confidence=0.85,
        permission_level="user",
        emotion="happy",
        emotion_confidence=0.75,
        is_live=True,
        liveness_confidence=0.90
    )
    
    face2 = FaceResult(
        tracking_id=2,
        bbox=(200, 100, 50, 50),
        identity="Jane Smith",
        confidence=0.92,
        permission_level="admin",
        emotion="neutral",
        emotion_confidence=0.80,
        is_live=True,
        liveness_confidence=0.95
    )
    
    result = RecognitionResult(
        faces=[face1, face2],
        frame_id=42,
        timestamp="2024-01-15T10:30:00Z",
        processing_time_ms=45.5
    )
    
    assert len(result.faces) == 2
    assert result.frame_id == 42
    assert result.timestamp == "2024-01-15T10:30:00Z"
    assert result.processing_time_ms == 45.5
    assert result.faces[0].identity == "John Doe"
    assert result.faces[1].identity == "Jane Smith"


def test_identity_info_creation():
    """Test IdentityInfo dataclass creation."""
    identity_info = IdentityInfo(
        name="John Doe",
        permission_level="user",
        num_embeddings=5,
        date_added="2024-01-15T10:30:00Z",
        metadata={"department": "engineering"}
    )
    
    assert identity_info.name == "John Doe"
    assert identity_info.permission_level == "user"
    assert identity_info.num_embeddings == 5
    assert identity_info.date_added == "2024-01-15T10:30:00Z"
    assert identity_info.metadata["department"] == "engineering"


def test_engine_creation():
    """Test GuruVisionEngine instantiation."""
    engine = GuruVisionEngine()
    
    assert engine.config_path is None
    assert engine.config is None
    assert engine.logger is None
    assert engine.initialized is False
    assert engine.frame_counter == 0
    assert 'identity_recognized' in engine.callbacks
    assert 'new_identity' in engine.callbacks
    assert 'permission_changed' in engine.callbacks
    assert 'error' in engine.callbacks
    assert 'system_ready' in engine.callbacks


def test_engine_creation_with_config_path():
    """Test GuruVisionEngine instantiation with config path."""
    engine = GuruVisionEngine(config_path="config.yaml")
    
    assert engine.config_path == "config.yaml"
    assert engine.initialized is False


def test_process_frame_before_initialization():
    """Test that process_frame raises error before initialization."""
    engine = GuruVisionEngine()
    
    # Create a dummy frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    with pytest.raises(RuntimeError, match="Engine not initialized"):
        engine.process_frame(frame)


def test_process_frame_with_invalid_frame():
    """Test that process_frame validates frame input."""
    engine = GuruVisionEngine()
    engine.initialized = True  # Fake initialization for this test
    
    # Test with None frame
    with pytest.raises(ValueError, match="Invalid frame"):
        engine.process_frame(None)
    
    # Test with empty frame
    empty_frame = np.array([])
    with pytest.raises(ValueError, match="Invalid frame"):
        engine.process_frame(empty_frame)


def test_compute_iou():
    """Test IoU computation helper method."""
    engine = GuruVisionEngine()
    
    # Test identical boxes
    bbox1 = (100, 100, 50, 50)
    bbox2 = (100, 100, 50, 50)
    iou = engine._compute_iou(bbox1, bbox2)
    assert iou == 1.0
    
    # Test non-overlapping boxes
    bbox1 = (100, 100, 50, 50)
    bbox2 = (200, 200, 50, 50)
    iou = engine._compute_iou(bbox1, bbox2)
    assert iou == 0.0
    
    # Test partially overlapping boxes
    bbox1 = (100, 100, 50, 50)
    bbox2 = (125, 125, 50, 50)
    iou = engine._compute_iou(bbox1, bbox2)
    assert 0.0 < iou < 1.0


def test_emit_event():
    """Test event emission mechanism."""
    engine = GuruVisionEngine()
    
    # Track callback invocations
    callback_data = []
    
    def test_callback(data):
        callback_data.append(data)
    
    # Register callback
    engine.callbacks['system_ready'].append(test_callback)
    
    # Emit event
    event_data = {'status': 'ready', 'timestamp': '2024-01-15T10:30:00Z'}
    engine._emit_event('system_ready', event_data)
    
    # Verify callback was called
    assert len(callback_data) == 1
    assert callback_data[0]['status'] == 'ready'
    assert callback_data[0]['timestamp'] == '2024-01-15T10:30:00Z'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
