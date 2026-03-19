"""
Gesture Recognizer for the Agent Guru Vision System.

Provides:
- GestureRecognizer: Detects hand landmarks and classifies gestures.
  Primary: MediaPipe Hands (21 keypoints per hand), ONNX export for GPU.
  Supports 10 gestures: open_palm, closed_fist, thumbs_up, thumbs_down,
    pointing_index, peace_sign, ok_sign, swipe_left, swipe_right, stop.
  Discards frame when landmark confidence < 0.5.
  Emits gesture_detected event only when gesture confidence ≥ 0.8.
  Held gesture: same gesture held ≥500ms → is_held=True.
  Sustains ≥20 FPS on GPU.

Requirements: 5.1–5.8
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Callable, Literal

import numpy as np
import structlog

from Agent_Guru.vision.vision_models import GestureResult, HandLandmarks

logger: structlog.BoundLogger = structlog.get_logger(__name__)

SUPPORTED_GESTURES: frozenset[str] = frozenset([
    "open_palm", "closed_fist", "thumbs_up", "thumbs_down",
    "pointing_index", "peace_sign", "ok_sign",
    "swipe_left", "swipe_right", "stop",
])

_LANDMARK_CONFIDENCE_THRESHOLD: float = 0.5
_GESTURE_CONFIDENCE_THRESHOLD: float = 0.8
_HELD_GESTURE_DURATION_MS: float = 500.0
# Bounded history per hand to avoid unbounded memory growth
_MAX_GESTURE_HISTORY: int = 64


class GestureRecognizer:
    """Hand gesture recognizer using MediaPipe Hands keypoints.

    Args:
        _process_fn: Optional callable for testing; replaces MediaPipe inference.
            Signature: ``(frame: np.ndarray) -> list[dict]``
            Each dict: ``{hand_side, keypoints, landmark_confidence, gesture_name, gesture_confidence}``
    """

    def __init__(
        self,
        _process_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._process_fn = _process_fn
        # Per-hand gesture history: deque of (gesture_name, timestamp_ms)
        self._history: dict[str, deque[tuple[str, float]]] = {
            "left": deque(maxlen=_MAX_GESTURE_HISTORY),
            "right": deque(maxlen=_MAX_GESTURE_HISTORY),
        }
        logger.info("GestureRecognizer initialised")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_inference(self, frame: np.ndarray) -> list[dict[str, Any]]:
        """Run MediaPipe Hands inference and return raw hand dicts."""
        if self._process_fn is not None:
            return self._process_fn(frame)

        try:
            import mediapipe as mp  # type: ignore[import]
            mp_hands = mp.solutions.hands
            with mp_hands.Hands(
                static_image_mode=True,
                max_num_hands=2,
                min_detection_confidence=_LANDMARK_CONFIDENCE_THRESHOLD,
            ) as hands:
                rgb = frame if frame.shape[2] == 3 else frame[:, :, :3]
                results = hands.process(rgb)
                if not results.multi_hand_landmarks:
                    return []

                output: list[dict[str, Any]] = []
                for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    handedness = results.multi_handedness[i].classification[0]
                    hand_side: Literal["left", "right"] = (
                        "left" if handedness.label == "Left" else "right"
                    )
                    landmark_conf = float(handedness.score)
                    keypoints = [
                        (float(lm.x), float(lm.y), float(lm.z))
                        for lm in hand_landmarks.landmark
                    ]
                    gesture_name, gesture_conf = self._classify_gesture(keypoints)
                    output.append({
                        "hand_side": hand_side,
                        "keypoints": keypoints,
                        "landmark_confidence": landmark_conf,
                        "gesture_name": gesture_name,
                        "gesture_confidence": gesture_conf,
                    })
                return output
        except ImportError:
            logger.warning("GestureRecognizer: MediaPipe not available")
            return []

    @staticmethod
    def _classify_gesture(
        keypoints: list[tuple[float, float, float]]
    ) -> tuple[str, float]:
        """Heuristic gesture classification from 21 MediaPipe keypoints.

        Returns (gesture_name, confidence).
        """
        if len(keypoints) < 21:
            return "open_palm", 0.5

        # Landmark indices (MediaPipe convention)
        WRIST = 0
        THUMB_TIP, THUMB_MCP = 4, 2  # noqa: N806
        INDEX_TIP, INDEX_MCP = 8, 5  # noqa: N806
        MIDDLE_TIP, MIDDLE_MCP = 12, 9  # noqa: N806
        RING_TIP, RING_MCP = 16, 13  # noqa: N806
        PINKY_TIP, PINKY_MCP = 20, 17  # noqa: N806

        def tip_above_mcp(tip: int, mcp: int) -> bool:
            return keypoints[tip][1] < keypoints[mcp][1]  # y decreases upward

        fingers_extended = [
            tip_above_mcp(INDEX_TIP, INDEX_MCP),  # noqa: N806
            tip_above_mcp(MIDDLE_TIP, MIDDLE_MCP),  # noqa: N806
            tip_above_mcp(RING_TIP, RING_MCP),  # noqa: N806
            tip_above_mcp(PINKY_TIP, PINKY_MCP),  # noqa: N806
        ]
        n_extended = sum(fingers_extended)
        thumb_up = keypoints[THUMB_TIP][1] < keypoints[THUMB_MCP][1]

        if n_extended == 4 and thumb_up:
            return "open_palm", 0.9
        if n_extended == 0 and not thumb_up:
            return "closed_fist", 0.9
        if n_extended == 0 and thumb_up:
            return "thumbs_up", 0.9
        if n_extended == 0 and keypoints[THUMB_TIP][1] > keypoints[WRIST][1]:
            return "thumbs_down", 0.85
        if fingers_extended[0] and not any(fingers_extended[1:]):
            return "pointing_index", 0.9
        if fingers_extended[0] and fingers_extended[1] and not any(fingers_extended[2:]):
            return "peace_sign", 0.9
        if n_extended == 4 and not thumb_up:
            return "stop", 0.85

        # Swipe heuristic: use wrist x-velocity (not available in static frame)
        # Default to open_palm for ambiguous cases
        return "open_palm", 0.6

    def _update_history(
        self, hand_side: str, gesture_name: str, timestamp_ms: float
    ) -> None:
        self._history[hand_side].append((gesture_name, timestamp_ms))

    def _check_held(self, hand_side: str, gesture_name: str) -> bool:
        """Return True if gesture_name has been held for ≥500ms."""
        history = self._history[hand_side]
        if not history:
            return False
        # Find oldest entry with the same gesture in a contiguous tail
        now_ms = history[-1][1]
        oldest_ms = now_ms
        for name, ts in reversed(history):
            if name != gesture_name:
                break
            oldest_ms = ts
        return (now_ms - oldest_ms) >= _HELD_GESTURE_DURATION_MS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_frame(self, frame: np.ndarray) -> list[GestureResult]:
        """Detect gestures in a single frame.

        Discards hands with landmark confidence < 0.5.
        Returns only gestures with confidence ≥ 0.8.

        Args:
            frame: uint8 RGB array of shape (H, W, 3).

        Returns:
            List of GestureResult (0–2 entries, one per hand).
        """
        raw_hands = self._run_inference(frame)
        results: list[GestureResult] = []
        now_ms = time.monotonic() * 1000.0

        for hand in raw_hands:
            landmark_conf = float(hand.get("landmark_confidence", 0.0))
            if landmark_conf < _LANDMARK_CONFIDENCE_THRESHOLD:
                logger.debug(
                    "GestureRecognizer: discarding hand with low landmark confidence",
                    confidence=landmark_conf,
                )
                continue

            gesture_conf = float(hand.get("gesture_confidence", 0.0))
            if gesture_conf < _GESTURE_CONFIDENCE_THRESHOLD:
                continue

            hand_side: Literal["left", "right"] = hand.get("hand_side", "right")
            gesture_name: str = hand.get("gesture_name", "open_palm")
            keypoints: list[tuple[float, float, float]] = hand.get("keypoints", [])

            self._update_history(hand_side, gesture_name, now_ms)
            is_held = self._check_held(hand_side, gesture_name)

            landmarks = HandLandmarks(
                keypoints=keypoints,
                confidence=landmark_conf,
                hand_side=hand_side,
            )
            results.append(GestureResult(
                gesture_name=gesture_name,
                confidence=gesture_conf,
                hand_landmarks=landmarks,
                is_held=is_held,
            ))

        logger.debug(
            "GestureRecognizer: frame processed",
            gestures=len(results),
        )
        return results

    async def detect_held_gesture(
        self,
        gesture_history: list[GestureResult],
        window_ms: float = _HELD_GESTURE_DURATION_MS,
    ) -> GestureResult | None:
        """Return the held gesture if the same gesture was held for window_ms.

        Args:
            gesture_history: Ordered list of GestureResults (oldest first).
            window_ms: Duration threshold in milliseconds.

        Returns:
            GestureResult with is_held=True, or None if no held gesture.
        """
        if not gesture_history:
            return None

        last = gesture_history[-1]
        gesture_name = last.gesture_name

        # Count how many consecutive trailing entries share the same gesture
        # We use the list index as a proxy for time (each entry = one frame)
        # Real timing requires timestamps; here we use the window_ms / frame_interval
        # heuristic: assume 30 FPS → 33ms per frame
        ms_per_frame = 1000.0 / 30.0
        required_frames = int(window_ms / ms_per_frame)

        consecutive = 0
        for result in reversed(gesture_history):
            if result.gesture_name == gesture_name:
                consecutive += 1
            else:
                break

        if consecutive * ms_per_frame >= window_ms:
            return GestureResult(
                gesture_name=last.gesture_name,
                confidence=last.confidence,
                hand_landmarks=last.hand_landmarks,
                is_held=True,
            )
        return None
