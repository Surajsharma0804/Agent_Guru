"""
Integration test for alignment module with detection module.

This test verifies that the FaceAligner works correctly with real Detection objects.
"""

import pytest
import numpy as np
import cv2
from guru_vision.alignment import FaceAligner
from guru_vision.detection import Detection


def test_alignment_with_detection_object():
    """Test that FaceAligner works with Detection objects from detector"""
    aligner = FaceAligner()
    
    # Create a realistic test image
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Create a Detection object with realistic landmarks
    # These landmarks represent a typical face detection result
    landmarks = np.array([
        [250.5, 200.3],  # left eye
        [390.2, 198.7],  # right eye
        [320.1, 280.5],  # nose
        [270.8, 350.2],  # left mouth
        [370.3, 349.8]   # right mouth
    ], dtype=np.float32)
    
    detection = Detection(
        bbox=(200, 150, 240, 300),
        landmarks=landmarks,
        confidence=0.95
    )
    
    # Align the face
    aligned_face = aligner.align(frame, detection)
    
    # Verify the output
    assert aligned_face.shape == (112, 112, 3), "Aligned face should be 112x112x3"
    assert aligned_face.dtype == np.uint8, "Aligned face should be uint8"
    assert np.any(aligned_face >= 0), "Aligned face should have valid pixel values"


def test_alignment_multiple_faces():
    """Test alignment of multiple faces from the same frame"""
    aligner = FaceAligner()
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Simulate two faces detected in the same frame
    detections = [
        Detection(
            bbox=(100, 100, 150, 200),
            landmarks=np.array([
                [120, 130], [160, 130], [140, 160], [125, 185], [155, 185]
            ], dtype=np.float32),
            confidence=0.92
        ),
        Detection(
            bbox=(400, 200, 150, 200),
            landmarks=np.array([
                [420, 230], [460, 230], [440, 260], [425, 285], [455, 285]
            ], dtype=np.float32),
            confidence=0.88
        )
    ]
    
    # Align both faces
    aligned_faces = [aligner.align(frame, det) for det in detections]
    
    # Verify both alignments
    assert len(aligned_faces) == 2
    for aligned_face in aligned_faces:
        assert aligned_face.shape == (112, 112, 3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
