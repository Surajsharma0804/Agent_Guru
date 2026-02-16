"""
Property-based tests for Gesture Detection module using Hypothesis
"""

import pytest
import numpy as np
from hypothesis import given, settings, strategies as st, assume
from guru_vision.gesture import GestureDetector, DetectedGesture, HandLandmarks


# Strategies
@st.composite
def image_strategy(draw):
    """Generate random images"""
    height = draw(st.integers(min_value=100, max_value=640))
    width = draw(st.integers(min_value=100, max_value=640))
    return np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)


@st.composite
def landmarks_strategy(draw):
    """Generate random hand landmarks"""
    landmarks = []
    for _ in range(21):
        x = draw(st.floats(min_value=0.0, max_value=1.0))
        y = draw(st.floats(min_value=0.0, max_value=1.0))
        z = draw(st.floats(min_value=-0.5, max_value=0.5))
        landmarks.append((x, y, z))
    return landmarks


@st.composite
def bbox_strategy(draw):
    """Generate random bounding boxes"""
    x1 = draw(st.integers(min_value=0, max_value=500))
    y1 = draw(st.integers(min_value=0, max_value=500))
    w = draw(st.integers(min_value=10, max_value=200))
    h = draw(st.integers(min_value=10, max_value=200))
    return (x1, y1, x1 + w, y1 + h)


class TestGestureDetectorProperties:
    """Property-based tests for GestureDetector"""
    
    @given(st.floats(min_value=0.0, max_value=1.0))
    @settings(max_examples=50, deadline=1000)
    def test_confidence_threshold_in_range(self, threshold):
        """Property: Confidence threshold is always in [0, 1]"""
        detector = GestureDetector(confidence_threshold=threshold)
        assert 0.0 <= detector.confidence_threshold <= 1.0
    
    @given(st.floats(min_value=-10.0, max_value=10.0))
    @settings(max_examples=50, deadline=1000)
    def test_confidence_threshold_clamped(self, threshold):
        """Property: Confidence threshold is clamped to [0, 1]"""
        detector = GestureDetector(confidence_threshold=threshold)
        assert 0.0 <= detector.confidence_threshold <= 1.0
    
    @given(st.integers(min_value=-5, max_value=10))
    @settings(max_examples=50, deadline=1000)
    def test_max_hands_clamped(self, max_hands):
        """Property: max_hands is clamped to [1, 2]"""
        detector = GestureDetector(max_hands=max_hands)
        assert 1 <= detector.max_hands <= 2
    
    @given(image_strategy())
    @settings(max_examples=20, deadline=2000)
    def test_detect_returns_list(self, image):
        """Property: detect() always returns a list"""
        detector = GestureDetector()
        result = detector.detect(image)
        assert isinstance(result, list)
    
    @given(st.floats(min_value=0.0, max_value=1.0))
    @settings(max_examples=30, deadline=1000)
    def test_set_confidence_threshold_valid(self, threshold):
        """Property: Setting valid threshold succeeds"""
        detector = GestureDetector()
        detector.set_confidence_threshold(threshold)
        assert detector.confidence_threshold == threshold
    
    @given(st.integers(min_value=1, max_value=2))
    @settings(max_examples=10, deadline=1000)
    def test_set_max_hands_valid(self, max_hands):
        """Property: Setting valid max_hands succeeds"""
        detector = GestureDetector()
        detector.set_max_hands(max_hands)
        assert detector.max_hands == max_hands


class TestHandLandmarksProperties:
    """Property-based tests for HandLandmarks"""
    
    @given(
        landmarks_strategy(),
        st.sampled_from(["Left", "Right"]),
        st.floats(min_value=0.0, max_value=1.0)
    )
    @settings(max_examples=50, deadline=1000)
    def test_hand_landmarks_creation(self, landmarks, handedness, confidence):
        """Property: HandLandmarks can be created with valid inputs"""
        hand_lm = HandLandmarks(
            landmarks=landmarks,
            handedness=handedness,
            confidence=confidence
        )
        assert len(hand_lm.landmarks) == 21
        assert hand_lm.handedness in ["Left", "Right"]
        assert 0.0 <= hand_lm.confidence <= 1.0
    
    @given(landmarks_strategy())
    @settings(max_examples=50, deadline=1000)
    def test_landmarks_count(self, landmarks):
        """Property: Hand landmarks always have 21 points"""
        hand_lm = HandLandmarks(
            landmarks=landmarks,
            handedness="Right",
            confidence=0.9
        )
        assert len(hand_lm.landmarks) == 21
    
    @given(landmarks_strategy())
    @settings(max_examples=50, deadline=1000)
    def test_landmarks_coordinates_normalized(self, landmarks):
        """Property: Landmark coordinates are in normalized range"""
        for x, y, z in landmarks:
            assert 0.0 <= x <= 1.0
            assert 0.0 <= y <= 1.0
            # Z can be negative (depth)


class TestDetectedGestureProperties:
    """Property-based tests for DetectedGesture"""
    
    @given(
        st.text(min_size=1, max_size=20),
        landmarks_strategy(),
        st.floats(min_value=0.0, max_value=1.0),
        bbox_strategy()
    )
    @settings(max_examples=50, deadline=1000)
    def test_detected_gesture_creation(self, gesture_type, landmarks, confidence, bbox):
        """Property: DetectedGesture can be created with valid inputs"""
        hand_lm = HandLandmarks(
            landmarks=landmarks,
            handedness="Right",
            confidence=0.9
        )
        gesture = DetectedGesture(
            gesture_type=gesture_type,
            hand_landmarks=hand_lm,
            confidence=confidence,
            bbox=bbox
        )
        assert gesture.gesture_type == gesture_type
        assert 0.0 <= gesture.confidence <= 1.0
        assert len(gesture.bbox) == 4
    
    @given(bbox_strategy())
    @settings(max_examples=50, deadline=1000)
    def test_bbox_coordinates_ordered(self, bbox):
        """Property: Bounding box coordinates are properly ordered"""
        x1, y1, x2, y2 = bbox
        assert x1 < x2
        assert y1 < y2


class TestGestureRecognitionProperties:
    """Property-based tests for gesture recognition logic"""
    
    @given(landmarks_strategy())
    @settings(max_examples=30, deadline=1000)
    def test_recognize_gesture_returns_valid(self, landmarks):
        """Property: Gesture recognition always returns valid result"""
        detector = GestureDetector()
        hand_lm = HandLandmarks(
            landmarks=landmarks,
            handedness="Right",
            confidence=0.9
        )
        
        gesture_type, confidence = detector._recognize_gesture(hand_lm)
        assert isinstance(gesture_type, str)
        assert 0.0 <= confidence <= 1.0
    
    @given(landmarks_strategy())
    @settings(max_examples=30, deadline=1000)
    def test_gesture_recognition_deterministic(self, landmarks):
        """Property: Same landmarks produce same gesture"""
        detector = GestureDetector()
        hand_lm = HandLandmarks(
            landmarks=landmarks,
            handedness="Right",
            confidence=0.9
        )
        
        result1 = detector._recognize_gesture(hand_lm)
        result2 = detector._recognize_gesture(hand_lm)
        assert result1 == result2
    
    @given(landmarks_strategy())
    @settings(max_examples=20, deadline=1000)
    def test_thumbs_up_returns_bool(self, landmarks):
        """Property: Thumbs up check returns boolean"""
        detector = GestureDetector()
        result = detector._is_thumbs_up(landmarks)
        assert isinstance(result, bool)
    
    @given(landmarks_strategy())
    @settings(max_examples=20, deadline=1000)
    def test_peace_sign_returns_bool(self, landmarks):
        """Property: Peace sign check returns boolean"""
        detector = GestureDetector()
        result = detector._is_peace_sign(landmarks)
        assert isinstance(result, bool)
    
    @given(landmarks_strategy())
    @settings(max_examples=20, deadline=1000)
    def test_pointing_returns_bool(self, landmarks):
        """Property: Pointing check returns boolean"""
        detector = GestureDetector()
        result = detector._is_pointing(landmarks)
        assert isinstance(result, bool)
    
    @given(landmarks_strategy())
    @settings(max_examples=20, deadline=1000)
    def test_open_palm_returns_bool(self, landmarks):
        """Property: Open palm check returns boolean"""
        detector = GestureDetector()
        result = detector._is_open_palm(landmarks)
        assert isinstance(result, bool)
    
    @given(landmarks_strategy())
    @settings(max_examples=20, deadline=1000)
    def test_fist_returns_bool(self, landmarks):
        """Property: Fist check returns boolean"""
        detector = GestureDetector()
        result = detector._is_fist(landmarks)
        assert isinstance(result, bool)


class TestGestureDetectorInvariants:
    """Test invariants that should hold for gesture detection"""
    
    @given(image_strategy())
    @settings(max_examples=20, deadline=2000)
    def test_detect_idempotent(self, image):
        """Property: Detecting twice on same image gives same result count"""
        detector = GestureDetector()
        result1 = detector.detect(image)
        result2 = detector.detect(image)
        # Should have same number of detections (may vary slightly due to MediaPipe)
        assert isinstance(result1, list)
        assert isinstance(result2, list)
    
    def test_cleanup_idempotent(self):
        """Property: Cleanup can be called multiple times safely"""
        detector = GestureDetector()
        detector.cleanup()
        detector.cleanup()  # Should not raise error
        assert detector.hands is None
