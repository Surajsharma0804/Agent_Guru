"""
Unit tests for face alignment module.

Requirements: 4.1, 4.2, 4.3, 4.4
"""

import pytest
import numpy as np
import cv2
from guru_vision.alignment import FaceAligner
from guru_vision.detection import Detection


class TestFaceAligner:
    """Unit tests for FaceAligner class"""
    
    def test_init_default_size(self):
        """Test FaceAligner initialization with default output size"""
        aligner = FaceAligner()
        assert aligner.output_size == (112, 112)
        assert aligner.src_landmarks.shape == (5, 2)
    
    def test_init_custom_size(self):
        """Test FaceAligner initialization with custom output size"""
        aligner = FaceAligner(output_size=(224, 224))
        assert aligner.output_size == (224, 224)
        # Landmarks should be scaled proportionally
        assert aligner.src_landmarks.shape == (5, 2)
    
    def test_align_with_valid_detection(self):
        """Test face alignment with valid detection and landmarks"""
        aligner = FaceAligner()
        
        # Create a test image (640x480 color image)
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        # Create realistic facial landmarks (5 points)
        # Simulating a face in the center of the image
        landmarks = np.array([
            [250, 200],  # left eye
            [390, 200],  # right eye
            [320, 280],  # nose
            [270, 350],  # left mouth
            [370, 350]   # right mouth
        ], dtype=np.float32)
        
        detection = Detection(
            bbox=(200, 150, 240, 300),
            landmarks=landmarks,
            confidence=0.95
        )
        
        # Align the face
        aligned_face = aligner.align(frame, detection)
        
        # Verify output dimensions
        assert aligned_face.shape == (112, 112, 3)
        assert aligned_face.dtype == np.uint8
    
    def test_align_invalid_landmarks_shape(self):
        """Test that align raises ValueError for invalid landmark shape"""
        aligner = FaceAligner()
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        # Invalid landmarks (wrong shape)
        invalid_landmarks = np.array([[250, 200], [390, 200]], dtype=np.float32)
        
        detection = Detection(
            bbox=(200, 150, 240, 300),
            landmarks=invalid_landmarks,
            confidence=0.95
        )
        
        with pytest.raises(ValueError, match="Invalid landmarks shape"):
            aligner.align(frame, detection)
    
    def test_align_none_landmarks(self):
        """Test that align raises ValueError for None landmarks"""
        aligner = FaceAligner()
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        detection = Detection(
            bbox=(200, 150, 240, 300),
            landmarks=None,
            confidence=0.95
        )
        
        with pytest.raises(ValueError, match="Invalid landmarks shape"):
            aligner.align(frame, detection)
    
    def test_align_preserves_color_channels(self):
        """Test that alignment preserves color channels"""
        aligner = FaceAligner()
        
        # Create a test image with distinct colors
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:, :, 0] = 100  # Blue channel
        frame[:, :, 1] = 150  # Green channel
        frame[:, :, 2] = 200  # Red channel
        
        landmarks = np.array([
            [250, 200],  # left eye
            [390, 200],  # right eye
            [320, 280],  # nose
            [270, 350],  # left mouth
            [370, 350]   # right mouth
        ], dtype=np.float32)
        
        detection = Detection(
            bbox=(200, 150, 240, 300),
            landmarks=landmarks,
            confidence=0.95
        )
        
        aligned_face = aligner.align(frame, detection)
        
        # Verify it's still a 3-channel image
        assert aligned_face.shape[2] == 3
    
    def test_align_different_output_sizes(self):
        """Test alignment with different output sizes"""
        sizes = [(112, 112), (224, 224), (96, 96)]
        
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        landmarks = np.array([
            [250, 200], [390, 200], [320, 280], [270, 350], [370, 350]
        ], dtype=np.float32)
        
        detection = Detection(
            bbox=(200, 150, 240, 300),
            landmarks=landmarks,
            confidence=0.95
        )
        
        for size in sizes:
            aligner = FaceAligner(output_size=size)
            aligned_face = aligner.align(frame, detection)
            assert aligned_face.shape == (size[1], size[0], 3)
