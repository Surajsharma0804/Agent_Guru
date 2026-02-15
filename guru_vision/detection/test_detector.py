"""
Unit tests for the face detection module.

These tests verify the basic functionality of the FaceDetector class.
"""

import pytest
import numpy as np
from guru_vision.detection import FaceDetector, Detection
from guru_vision.exceptions import DetectionError


class TestDetection:
    """Tests for the Detection dataclass."""
    
    def test_detection_creation(self):
        """Test that Detection objects can be created with valid data."""
        bbox = (10, 20, 100, 120)
        landmarks = np.array([[30, 40], [70, 40], [50, 60], [35, 80], [65, 80]], dtype=np.float32)
        confidence = 0.95
        
        detection = Detection(bbox=bbox, landmarks=landmarks, confidence=confidence)
        
        assert detection.bbox == bbox
        assert np.array_equal(detection.landmarks, landmarks)
        assert detection.confidence == confidence


class TestFaceDetector:
    """Tests for the FaceDetector class."""
    
    def test_detector_initialization_cpu(self):
        """Test that FaceDetector can be initialized in CPU mode."""
        detector = FaceDetector(use_gpu=False)
        assert detector.use_gpu is False
        assert detector.session is not None
    
    def test_detector_initialization_with_custom_model(self):
        """Test that FaceDetector can be initialized with custom model path."""
        # Use default model path
        detector = FaceDetector(model_path=None, use_gpu=False)
        assert detector.model_path is not None
    
    def test_detect_with_invalid_frame(self):
        """Test that detect() raises DetectionError for invalid frames."""
        detector = FaceDetector(use_gpu=False)
        
        # Test with None
        with pytest.raises(DetectionError, match="Invalid frame"):
            detector.detect(None)
        
        # Test with empty array
        with pytest.raises(DetectionError, match="Invalid frame"):
            detector.detect(np.array([]))
    
    def test_detect_returns_list(self):
        """Test that detect() returns a list."""
        detector = FaceDetector(use_gpu=False)
        
        # Create a simple test image (blank image)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        result = detector.detect(frame)
        
        assert isinstance(result, list)
    
    def test_detect_with_no_faces(self):
        """Test that detect() returns empty list when no faces are present."""
        detector = FaceDetector(use_gpu=False)
        
        # Create a blank image with no faces
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        detections = detector.detect(frame)
        
        # Should return empty list for blank image
        assert isinstance(detections, list)
        assert len(detections) == 0
    
    def test_detect_confidence_threshold(self):
        """Test that detect() filters by confidence threshold."""
        detector = FaceDetector(use_gpu=False)
        
        # Create a test image
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Test with different thresholds
        detections_low = detector.detect(frame, confidence_threshold=0.3)
        detections_high = detector.detect(frame, confidence_threshold=0.9)
        
        # Both should return lists
        assert isinstance(detections_low, list)
        assert isinstance(detections_high, list)
        
        # Higher threshold should have fewer or equal detections
        assert len(detections_high) <= len(detections_low)
    
    def test_detection_format(self):
        """Test that detections have the correct format when faces are found."""
        detector = FaceDetector(use_gpu=False)
        
        # Create a simple test image
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        detections = detector.detect(frame)
        
        # If any detections are found, verify their format
        for detection in detections:
            assert isinstance(detection, Detection)
            assert len(detection.bbox) == 4
            assert detection.landmarks.shape == (5, 2)
            assert 0.0 <= detection.confidence <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
