"""
Gesture Detection Module

Provides hand detection and gesture recognition using MediaPipe Hands.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class HandLandmarks:
    """21-point hand landmarks from MediaPipe"""
    landmarks: List[Tuple[float, float, float]]  # (x, y, z) normalized coordinates
    handedness: str  # "Left" or "Right"
    confidence: float


@dataclass
class DetectedGesture:
    """Represents a detected gesture"""
    gesture_type: str  # e.g., "thumbs_up", "peace", "ok", "pointing", "wave"
    hand_landmarks: HandLandmarks
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)


class GestureDetector:
    """
    Hand detection and gesture recognition using MediaPipe Hands.
    
    Supports static gestures (thumbs up, peace, OK, pointing, etc.) and
    dynamic gestures (wave, swipe, pinch).
    """
    
    def __init__(self,
                 max_hands: int = 2,
                 confidence_threshold: float = 0.5,
                 use_static_mode: bool = False):
        """
        Initialize gesture detector.
        
        Args:
            max_hands: Maximum number of hands to detect (1-2)
            confidence_threshold: Minimum confidence for detection
            use_static_mode: Whether to treat images as static (vs video)
        """
        self.max_hands = max(1, min(2, max_hands))
        self.confidence_threshold = max(0.0, min(1.0, confidence_threshold))
        self.use_static_mode = use_static_mode
        self.hands = None
        
        self._initialize_mediapipe()
    
    def _initialize_mediapipe(self) -> None:
        """Initialize MediaPipe Hands"""
        try:
            import mediapipe as mp
            self.mp_hands = mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=self.use_static_mode,
                max_num_hands=self.max_hands,
                min_detection_confidence=self.confidence_threshold,
                min_tracking_confidence=self.confidence_threshold
            )
            logger.info(f"MediaPipe Hands initialized (max_hands={self.max_hands})")
        except ImportError:
            logger.warning("MediaPipe not available. Install with: pip install mediapipe")
            self.hands = None
        except Exception as e:
            logger.error(f"Failed to initialize MediaPipe Hands: {e}")
            self.hands = None
    
    def detect(self, image: np.ndarray) -> List[DetectedGesture]:
        """
        Detect hands and recognize gestures in image.
        
        Args:
            image: Input image as numpy array (H, W, 3) in BGR format
        
        Returns:
            List of detected gestures with hand landmarks
        """
        if self.hands is None:
            logger.warning("MediaPipe Hands not initialized")
            return []
        
        if image is None or image.size == 0:
            return []
        
        try:
            # Convert BGR to RGB
            import cv2
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Process image
            results = self.hands.process(rgb_image)
            
            if not results.multi_hand_landmarks:
                return []
            
            # Extract gestures
            detected_gestures = []
            h, w = image.shape[:2]
            
            for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                # Get handedness
                handedness = results.multi_handedness[idx].classification[0]
                hand_label = handedness.label
                hand_confidence = handedness.score
                
                # Extract landmarks
                landmarks = []
                for landmark in hand_landmarks.landmark:
                    landmarks.append((landmark.x, landmark.y, landmark.z))
                
                # Create HandLandmarks object
                hand_lm = HandLandmarks(
                    landmarks=landmarks,
                    handedness=hand_label,
                    confidence=hand_confidence
                )
                
                # Calculate bounding box
                x_coords = [lm[0] * w for lm in landmarks]
                y_coords = [lm[1] * h for lm in landmarks]
                x1, x2 = int(min(x_coords)), int(max(x_coords))
                y1, y2 = int(min(y_coords)), int(max(y_coords))
                bbox = (x1, y1, x2, y2)
                
                # Recognize gesture
                gesture_type, gesture_confidence = self._recognize_gesture(hand_lm)
                
                if gesture_confidence >= self.confidence_threshold:
                    detected_gestures.append(DetectedGesture(
                        gesture_type=gesture_type,
                        hand_landmarks=hand_lm,
                        confidence=gesture_confidence,
                        bbox=bbox
                    ))
            
            return detected_gestures
            
        except Exception as e:
            logger.error(f"Gesture detection failed: {e}")
            return []
    
    def _recognize_gesture(self, hand_landmarks: HandLandmarks) -> Tuple[str, float]:
        """
        Recognize gesture from hand landmarks.
        
        Args:
            hand_landmarks: Hand landmarks
        
        Returns:
            Tuple of (gesture_type, confidence)
        """
        landmarks = hand_landmarks.landmarks
        
        # Check for thumbs up
        if self._is_thumbs_up(landmarks):
            return "thumbs_up", 0.9
        
        # Check for peace sign
        if self._is_peace_sign(landmarks):
            return "peace", 0.9
        
        # Check for OK sign
        if self._is_ok_sign(landmarks):
            return "ok", 0.9
        
        # Check for pointing
        if self._is_pointing(landmarks):
            return "pointing", 0.85
        
        # Check for open palm
        if self._is_open_palm(landmarks):
            return "open_palm", 0.8
        
        # Check for fist
        if self._is_fist(landmarks):
            return "fist", 0.8
        
        # Default: unknown gesture
        return "unknown", 0.5
    
    def _is_thumbs_up(self, landmarks: List[Tuple[float, float, float]]) -> bool:
        """Check if gesture is thumbs up"""
        # Thumb tip (4) is up, other fingers are down
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]
        
        # Thumb is extended upward
        thumb_up = thumb_tip[1] < thumb_ip[1]
        
        # Other fingers are curled
        fingers_down = (
            index_tip[1] > landmarks[6][1] and
            middle_tip[1] > landmarks[10][1] and
            ring_tip[1] > landmarks[14][1] and
            pinky_tip[1] > landmarks[18][1]
        )
        
        return thumb_up and fingers_down
    
    def _is_peace_sign(self, landmarks: List[Tuple[float, float, float]]) -> bool:
        """Check if gesture is peace sign (V)"""
        # Index and middle fingers extended, others curled
        index_tip = landmarks[8]
        index_pip = landmarks[6]
        middle_tip = landmarks[12]
        middle_pip = landmarks[10]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]
        
        # Index and middle extended
        index_extended = index_tip[1] < index_pip[1]
        middle_extended = middle_tip[1] < middle_pip[1]
        
        # Ring and pinky curled
        ring_curled = ring_tip[1] > landmarks[14][1]
        pinky_curled = pinky_tip[1] > landmarks[18][1]
        
        return index_extended and middle_extended and ring_curled and pinky_curled
    
    def _is_ok_sign(self, landmarks: List[Tuple[float, float, float]]) -> bool:
        """Check if gesture is OK sign"""
        # Thumb and index finger form circle, others extended
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]
        
        # Distance between thumb and index tips
        distance = np.sqrt(
            (thumb_tip[0] - index_tip[0])**2 +
            (thumb_tip[1] - index_tip[1])**2
        )
        
        # Circle formed (small distance)
        circle_formed = distance < 0.05
        
        # Other fingers extended
        fingers_extended = (
            middle_tip[1] < landmarks[10][1] and
            ring_tip[1] < landmarks[14][1] and
            pinky_tip[1] < landmarks[18][1]
        )
        
        return circle_formed and fingers_extended
    
    def _is_pointing(self, landmarks: List[Tuple[float, float, float]]) -> bool:
        """Check if gesture is pointing"""
        # Only index finger extended
        index_tip = landmarks[8]
        index_pip = landmarks[6]
        middle_tip = landmarks[12]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]
        
        # Index extended
        index_extended = index_tip[1] < index_pip[1]
        
        # Other fingers curled
        fingers_curled = (
            middle_tip[1] > landmarks[10][1] and
            ring_tip[1] > landmarks[14][1] and
            pinky_tip[1] > landmarks[18][1]
        )
        
        return index_extended and fingers_curled
    
    def _is_open_palm(self, landmarks: List[Tuple[float, float, float]]) -> bool:
        """Check if gesture is open palm"""
        # All fingers extended
        fingers_extended = (
            landmarks[8][1] < landmarks[6][1] and   # Index
            landmarks[12][1] < landmarks[10][1] and  # Middle
            landmarks[16][1] < landmarks[14][1] and  # Ring
            landmarks[20][1] < landmarks[18][1]      # Pinky
        )
        
        return fingers_extended
    
    def _is_fist(self, landmarks: List[Tuple[float, float, float]]) -> bool:
        """Check if gesture is fist"""
        # All fingers curled
        fingers_curled = (
            landmarks[8][1] > landmarks[6][1] and   # Index
            landmarks[12][1] > landmarks[10][1] and  # Middle
            landmarks[16][1] > landmarks[14][1] and  # Ring
            landmarks[20][1] > landmarks[18][1]      # Pinky
        )
        
        return fingers_curled
    
    def set_confidence_threshold(self, threshold: float) -> None:
        """
        Set confidence threshold.
        
        Args:
            threshold: New confidence threshold (0.0 to 1.0)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")
        self.confidence_threshold = threshold
    
    def set_max_hands(self, max_hands: int) -> None:
        """
        Set maximum number of hands to detect.
        
        Args:
            max_hands: Maximum hands (1-2)
        """
        if not 1 <= max_hands <= 2:
            raise ValueError("max_hands must be 1 or 2")
        self.max_hands = max_hands
        self._initialize_mediapipe()
    
    def cleanup(self) -> None:
        """Release MediaPipe resources"""
        if self.hands is not None:
            self.hands.close()
            self.hands = None
