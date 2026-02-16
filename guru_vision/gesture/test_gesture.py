"""
Unit tests for Gesture Detection module
"""

import pytest
import numpy as np
from guru_vision.gesture import GestureDetector, DetectedGesture, HandLandmarks


class TestHandLandmarks:
    """Tests for HandLandmarks dataclass"""
    
    def test_create_hand_landmarks(self):
        """Test creating HandLandmarks instance"""
        landmarks = [(0.5, 0.5, 0.0) for _ in range(21)]
        hand_lm = HandLandmarks(
            landmarks=landmarks,
            handedness="Right",
            confidence=0.95
        )
        assert len(hand_lm.landmarks) == 21
        assert hand_lm.handedness == "Right"
        assert hand_lm.confidence == 0.95


class TestDetectedGesture:
    """Tests for DetectedGesture dataclass"""
    
    def test_create_detected_gesture(self):
        """Test creating DetectedGesture instance"""
        landmarks = [(0.5, 0.5, 0.0) for _ in range(21)]
        hand_lm = HandLandmarks(
            landmarks=landmarks,
            handedness="Right",
            confidence=0.95
        )
        gesture = DetectedGesture(
            gesture_type="thumbs_up",
            hand_landmarks=hand_lm,
            confidence=0.9,
            bbox=(100, 100, 200, 200)
        )
        assert gesture.gesture_type == "thumbs_up"
        assert gesture.confidence == 0.9
        assert gesture.bbox == (100, 100, 200, 200)


class TestGestureDetector:
    """Tests for GestureDetector class"""
    
    def test_init_default(self):
        """Test initialization with default parameters"""
        detector = GestureDetector()
        assert detector.max_hands == 2
        assert detector.confidence_threshold == 0.5
        assert detector.use_static_mode is False
    
    def test_init_custom(self):
        """Test initialization with custom parameters"""
        detector = GestureDetector(
            max_hands=1,
            confidence_threshold=0.7,
            use_static_mode=True
        )
        assert detector.max_hands == 1
        assert detector.confidence_threshold == 0.7
        assert detector.use_static_mode is True
    
    def test_init_clamps_max_hands(self):
        """Test that max_hands is clamped to [1, 2]"""
        detector = GestureDetector(max_hands=5)
        assert detector.max_hands == 2
        
        detector = GestureDetector(max_hands=0)
        assert detector.max_hands == 1
    
    def test_init_clamps_confidence(self):
        """Test that confidence threshold is clamped to [0, 1]"""
        detector = GestureDetector(confidence_threshold=1.5)
        assert detector.confidence_threshold == 1.0
        
        detector = GestureDetector(confidence_threshold=-0.5)
        assert detector.confidence_threshold == 0.0
    
    def test_detect_empty_image(self):
        """Test detection with empty image"""
        detector = GestureDetector()
        result = detector.detect(np.array([]))
        assert result == []
    
    def test_detect_none_image(self):
        """Test detection with None image"""
        detector = GestureDetector()
        result = detector.detect(None)
        assert result == []
    
    def test_detect_without_mediapipe(self):
        """Test detection when MediaPipe is not initialized"""
        detector = GestureDetector()
        detector.hands = None
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(image)
        assert result == []
    
    def test_detect_returns_list(self):
        """Test that detect always returns a list"""
        detector = GestureDetector()
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(image)
        assert isinstance(result, list)
    
    def test_set_confidence_threshold_valid(self):
        """Test setting valid confidence threshold"""
        detector = GestureDetector()
        detector.set_confidence_threshold(0.8)
        assert detector.confidence_threshold == 0.8
    
    def test_set_confidence_threshold_invalid(self):
        """Test setting invalid confidence threshold"""
        detector = GestureDetector()
        with pytest.raises(ValueError):
            detector.set_confidence_threshold(1.5)
        with pytest.raises(ValueError):
            detector.set_confidence_threshold(-0.1)
    
    def test_set_max_hands_valid(self):
        """Test setting valid max_hands"""
        detector = GestureDetector()
        detector.set_max_hands(1)
        assert detector.max_hands == 1
    
    def test_set_max_hands_invalid(self):
        """Test setting invalid max_hands"""
        detector = GestureDetector()
        with pytest.raises(ValueError):
            detector.set_max_hands(0)
        with pytest.raises(ValueError):
            detector.set_max_hands(3)
    
    def test_cleanup(self):
        """Test cleanup releases resources"""
        detector = GestureDetector()
        detector.cleanup()
        assert detector.hands is None


class TestGestureRecognition:
    """Tests for gesture recognition logic"""
    
    def test_is_thumbs_up(self):
        """Test thumbs up recognition"""
        detector = GestureDetector()
        
        # Create landmarks for thumbs up (thumb up, others down)
        landmarks = [(0.5, 0.5, 0.0) for _ in range(21)]
        landmarks[4] = (0.5, 0.2, 0.0)  # Thumb tip up
        landmarks[3] = (0.5, 0.3, 0.0)  # Thumb IP
        landmarks[8] = (0.5, 0.7, 0.0)  # Index tip down
        landmarks[6] = (0.5, 0.6, 0.0)  # Index PIP
        landmarks[12] = (0.5, 0.7, 0.0)  # Middle tip down
        landmarks[10] = (0.5, 0.6, 0.0)  # Middle PIP
        landmarks[16] = (0.5, 0.7, 0.0)  # Ring tip down
        landmarks[14] = (0.5, 0.6, 0.0)  # Ring PIP
        landmarks[20] = (0.5, 0.7, 0.0)  # Pinky tip down
        landmarks[18] = (0.5, 0.6, 0.0)  # Pinky PIP
        
        result = detector._is_thumbs_up(landmarks)
        assert result is True
    
    def test_is_peace_sign(self):
        """Test peace sign recognition"""
        detector = GestureDetector()
        
        # Create landmarks for peace sign (index and middle up, others down)
        landmarks = [(0.5, 0.5, 0.0) for _ in range(21)]
        landmarks[8] = (0.5, 0.2, 0.0)  # Index tip up
        landmarks[6] = (0.5, 0.3, 0.0)  # Index PIP
        landmarks[12] = (0.5, 0.2, 0.0)  # Middle tip up
        landmarks[10] = (0.5, 0.3, 0.0)  # Middle PIP
        landmarks[16] = (0.5, 0.7, 0.0)  # Ring tip down
        landmarks[14] = (0.5, 0.6, 0.0)  # Ring PIP
        landmarks[20] = (0.5, 0.7, 0.0)  # Pinky tip down
        landmarks[18] = (0.5, 0.6, 0.0)  # Pinky PIP
        
        result = detector._is_peace_sign(landmarks)
        assert result is True
    
    def test_is_pointing(self):
        """Test pointing recognition"""
        detector = GestureDetector()
        
        # Create landmarks for pointing (only index up)
        landmarks = [(0.5, 0.5, 0.0) for _ in range(21)]
        landmarks[8] = (0.5, 0.2, 0.0)  # Index tip up
        landmarks[6] = (0.5, 0.3, 0.0)  # Index PIP
        landmarks[12] = (0.5, 0.7, 0.0)  # Middle tip down
        landmarks[10] = (0.5, 0.6, 0.0)  # Middle PIP
        landmarks[16] = (0.5, 0.7, 0.0)  # Ring tip down
        landmarks[14] = (0.5, 0.6, 0.0)  # Ring PIP
        landmarks[20] = (0.5, 0.7, 0.0)  # Pinky tip down
        landmarks[18] = (0.5, 0.6, 0.0)  # Pinky PIP
        
        result = detector._is_pointing(landmarks)
        assert result is True
    
    def test_is_open_palm(self):
        """Test open palm recognition"""
        detector = GestureDetector()
        
        # Create landmarks for open palm (all fingers up)
        landmarks = [(0.5, 0.5, 0.0) for _ in range(21)]
        landmarks[8] = (0.5, 0.2, 0.0)  # Index tip up
        landmarks[6] = (0.5, 0.3, 0.0)  # Index PIP
        landmarks[12] = (0.5, 0.2, 0.0)  # Middle tip up
        landmarks[10] = (0.5, 0.3, 0.0)  # Middle PIP
        landmarks[16] = (0.5, 0.2, 0.0)  # Ring tip up
        landmarks[14] = (0.5, 0.3, 0.0)  # Ring PIP
        landmarks[20] = (0.5, 0.2, 0.0)  # Pinky tip up
        landmarks[18] = (0.5, 0.3, 0.0)  # Pinky PIP
        
        result = detector._is_open_palm(landmarks)
        assert result is True
    
    def test_is_fist(self):
        """Test fist recognition"""
        detector = GestureDetector()
        
        # Create landmarks for fist (all fingers down)
        landmarks = [(0.5, 0.5, 0.0) for _ in range(21)]
        landmarks[8] = (0.5, 0.7, 0.0)  # Index tip down
        landmarks[6] = (0.5, 0.6, 0.0)  # Index PIP
        landmarks[12] = (0.5, 0.7, 0.0)  # Middle tip down
        landmarks[10] = (0.5, 0.6, 0.0)  # Middle PIP
        landmarks[16] = (0.5, 0.7, 0.0)  # Ring tip down
        landmarks[14] = (0.5, 0.6, 0.0)  # Ring PIP
        landmarks[20] = (0.5, 0.7, 0.0)  # Pinky tip down
        landmarks[18] = (0.5, 0.6, 0.0)  # Pinky PIP
        
        result = detector._is_fist(landmarks)
        assert result is True
    
    def test_recognize_gesture(self):
        """Test gesture recognition returns valid result"""
        detector = GestureDetector()
        
        # Create sample landmarks
        landmarks = [(0.5, 0.5, 0.0) for _ in range(21)]
        hand_lm = HandLandmarks(
            landmarks=landmarks,
            handedness="Right",
            confidence=0.95
        )
        
        gesture_type, confidence = detector._recognize_gesture(hand_lm)
        assert isinstance(gesture_type, str)
        assert 0.0 <= confidence <= 1.0
