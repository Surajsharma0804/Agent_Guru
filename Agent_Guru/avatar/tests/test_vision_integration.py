"""The avatar's emotion bridge reads the face the vision package finds, not the whole frame.

Before, the bridge imported a VisionEngine class that does not exist, so it
always ran without face detection and handed the full camera frame to the
emotion recognizer.
"""

from __future__ import annotations

import numpy as np

from Agent_Guru.avatar.models import EmotionState
from Agent_Guru.avatar.vision_integration import VisionAvatarBridge
from Agent_Guru.vision.detection.detector import Detection, FaceDetector


class RecordingRecognizer:
    def __init__(self):
        self.frames: list[np.ndarray] = []

    def detect_emotion_smooth(self, frame):
        self.frames.append(frame)
        return EmotionState.neutral()


class FixedDetector:
    def __init__(self, detections):
        self.detections = detections

    def detect(self, frame):
        return self.detections


def _bridge(detector):
    bridge = VisionAvatarBridge(emotion_callback=lambda state: None)
    bridge._vision_engine = detector
    recognizer = RecordingRecognizer()
    bridge._emotion_recognizer = recognizer
    return bridge, recognizer


def test_bridge_connects_to_the_vision_face_detector():
    bridge = VisionAvatarBridge(emotion_callback=lambda state: None)
    assert bridge._vision_available  # nosec B101
    assert isinstance(bridge._vision_engine, FaceDetector)  # nosec B101


def test_emotion_is_read_from_the_largest_face_only():
    frame = np.zeros((480, 640, 3), np.uint8)
    small = Detection(bbox=(10, 10, 20, 30), landmarks=None, confidence=0.9)
    large = Detection(bbox=(200, 100, 120, 150), landmarks=None, confidence=0.8)
    bridge, recognizer = _bridge(FixedDetector([small, large]))

    bridge.process_frame(frame)

    assert [f.shape for f in recognizer.frames] == [(150, 120, 3)]  # nosec B101


def test_face_box_past_the_frame_edge_is_clamped():
    frame = np.zeros((100, 100, 3), np.uint8)
    bridge, recognizer = _bridge(FixedDetector([Detection(bbox=(80, 90, 50, 50), landmarks=None, confidence=0.9)]))

    bridge.process_frame(frame)

    assert recognizer.frames[0].shape == (10, 20, 3)  # nosec B101


def test_cascade_detector_is_available():
    # opencv-python 5 removed CascadeClassifier. FaceDetector catches the
    # AttributeError and reports no faces, so with OpenCV 5 installed the
    # avatar saw no face in any frame and logged an error for every one.
    import cv2
    import cv2.data

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    assert not cascade.empty()  # nosec B101


def test_frame_without_a_face_is_neutral_and_not_read():
    states = []
    bridge = VisionAvatarBridge(emotion_callback=states.append)
    recognizer = RecordingRecognizer()
    bridge._emotion_recognizer = recognizer

    # The real detector on an empty frame: no face, so nothing is read.
    state = bridge.process_frame(np.zeros((240, 320, 3), np.uint8))

    assert recognizer.frames == []  # nosec B101
    assert state.emotion == "neutral" and states == [state]  # nosec B101
