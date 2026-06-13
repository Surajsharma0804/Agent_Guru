"""Module: Agent_Guru.avatar.vision_integration
Purpose: Integration between Avatar system and Agent_Guru.vision.

Handles:
    - User emotion detection via Agent_Guru.vision face recognition
    - Face detection result routing to emotion recognizer
    - Fallback to standalone emotion recognition when vision unavailable

Requirements: Req 11.7, Task 17
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from Agent_Guru.avatar.models import EmotionState

if TYPE_CHECKING:
    from collections.abc import Callable

    import numpy as np

logger = logging.getLogger("guruvision.avatar.vision_integration")


class VisionAvatarBridge:
    """Bridge between Agent_Guru.vision and the avatar emotion system.

    Routes face detection results from the vision engine to the avatar's
    emotion recognizer, avoiding duplicate face detection work.

    Args:
        emotion_callback: Called with EmotionState when emotion is detected.
        use_vision_engine: Whether to use Agent_Guru.vision for face detection.

    """

    def __init__(
        self,
        emotion_callback: Callable[[EmotionState], None],
        use_vision_engine: bool = True,
    ) -> None:
        self._emotion_callback = emotion_callback
        self._use_vision_engine = use_vision_engine
        self._vision_engine: Any | None = None
        self._emotion_recognizer: Any | None = None
        self._vision_available = False

        if use_vision_engine:
            self._init_vision_engine()
        self._init_emotion_recognizer()

    # ------------------------------------------------------------------
    # Frame processing
    # ------------------------------------------------------------------

    def process_frame(self, frame: np.ndarray) -> EmotionState:
        """Process a video frame for emotion detection.

        Uses Agent_Guru.vision for face detection when available,
        then runs emotion recognition on the detected face region.

        Args:
            frame: BGR uint8 image array.

        Returns:
            Detected :class:`EmotionState`.

        """
        if frame is None or frame.size == 0:
            return EmotionState.neutral()

        # Try to use vision engine for face detection
        face_frame = self._extract_face_region(frame)

        # Run emotion recognition
        if self._emotion_recognizer is not None:
            try:
                state = self._emotion_recognizer.detect_emotion_smooth(face_frame)
                self._emotion_callback(state)
                return state
            except Exception:
                logger.exception("Emotion recognition failed")

        neutral = EmotionState.neutral()
        self._emotion_callback(neutral)
        return neutral

    # ------------------------------------------------------------------
    # Vision engine integration
    # ------------------------------------------------------------------

    def on_face_detected(self, face_frame: np.ndarray, face_id: str | None = None) -> None:
        """Called by Agent_Guru.vision when a face is detected.

        Args:
            face_frame: Cropped face region (BGR uint8).
            face_id: Optional face identity from recognition.

        """
        if self._emotion_recognizer is None:
            return
        try:
            state = self._emotion_recognizer.detect_emotion_smooth(face_frame)
            self._emotion_callback(state)
        except Exception:
            logger.exception("Emotion detection on face region failed")

    def on_no_face(self) -> None:
        """Called by Agent_Guru.vision when no face is detected."""
        self._emotion_callback(EmotionState.neutral())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_face_region(self, frame: np.ndarray) -> np.ndarray:
        """Extract the primary face region from a frame.

        Uses Agent_Guru.vision if available, otherwise returns full frame.
        """
        if not self._vision_available or self._vision_engine is None:
            return frame

        try:
            # Attempt to use vision engine's face detection
            faces = self._vision_engine.detect_faces(frame)
            if faces:
                # Select primary face (largest)
                primary = max(faces, key=lambda f: f.get("area", 0))
                x, y, w, h = (
                    primary.get("x", 0),
                    primary.get("y", 0),
                    primary.get("w", frame.shape[1]),
                    primary.get("h", frame.shape[0]),
                )
                # Clamp to frame bounds
                x1 = max(0, x)
                y1 = max(0, y)
                x2 = min(frame.shape[1], x + w)
                y2 = min(frame.shape[0], y + h)
                if x2 > x1 and y2 > y1:
                    return frame[y1:y2, x1:x2]
        except Exception as exc:
            logger.debug("Vision engine face extraction failed: %s", exc)

        return frame

    def _init_vision_engine(self) -> None:
        """Try to initialize Agent_Guru.vision engine."""
        try:
            from Agent_Guru.vision.engine import VisionEngine  # type: ignore[import]

            self._vision_engine = VisionEngine()
            self._vision_available = True
            logger.info("Agent_Guru.vision engine connected")
        except Exception as exc:
            logger.debug("Agent_Guru.vision not available: %s — using standalone detection", exc)
            self._vision_available = False

    def _init_emotion_recognizer(self) -> None:
        """Initialize the standalone emotion recognizer."""
        try:
            from Agent_Guru.avatar.emotion.recognizer import EmotionRecognizer

            self._emotion_recognizer = EmotionRecognizer(
                model="auto",
                confidence_threshold=0.5,
                smoothing_window=5,
                map_to_27=True,
            )
        except Exception:
            logger.exception("Failed to initialize EmotionRecognizer")
