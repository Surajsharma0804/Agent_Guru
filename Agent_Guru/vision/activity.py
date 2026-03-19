"""
Activity Recognizer for the Agent Guru Vision System.

Classifies human activities from temporal sequences of video frames using
SlowFast R50 or VideoMAE-S ONNX models.

Design:
- Requires a minimum 8-frame buffer before producing any output.
- Supports 11 activity categories.
- Emits activity_detected event when confidence ≥ 0.7.
- Emits activity_changed event with previous + new labels on transition.
- Update rate ≥ 1 Hz during continuous operation.

Requirements: 10.1–10.6
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Callable

import numpy as np
import structlog

from Agent_Guru.vision.vision_models import ActivityResult, VisionEvent

logger: structlog.BoundLogger = structlog.get_logger(__name__)

ACTIVITY_CATEGORIES: list[str] = [
    "walking", "running", "sitting", "standing", "typing",
    "eating", "drinking", "reading", "writing", "phone_use", "idle",
]

_MIN_BUFFER_FRAMES: int = 8
_CONFIDENCE_GATE: float = 0.7
_INPUT_FRAMES: int = 8       # SlowFast/VideoMAE temporal window
_FRAME_SIZE: tuple[int, int] = (224, 224)  # H x W for model input


class ActivityRecognizer:
    """Temporal activity classifier using SlowFast/VideoMAE ONNX.

    Args:
        _infer_fn: Optional callable for testing; replaces ONNX inference.
            Signature: ``(frames: np.ndarray) -> np.ndarray``
            Input shape: (1, T, H, W, 3) float32 normalised [0,1].
            Output shape: (1, 11) float32 logits.
    """

    def __init__(self, _infer_fn: Callable[..., Any] | None = None) -> None:
        self._infer_fn = _infer_fn
        self._frame_buffer: deque[np.ndarray] = deque(maxlen=_INPUT_FRAMES)
        self._previous_label: str | None = None
        self._last_update_time: float = 0.0
        logger.info("ActivityRecognizer initialised")

    # ------------------------------------------------------------------
    # Internal inference
    # ------------------------------------------------------------------

    def _run_inference(self, frames: list[np.ndarray]) -> np.ndarray:
        """Run ONNX model on a stack of frames.

        Args:
            frames: List of _INPUT_FRAMES uint8 RGB arrays (H, W, 3).

        Returns:
            Softmax probabilities of shape (11,).
        """
        # Preprocess: resize, normalise to [0,1], stack → (1, T, H, W, 3)
        processed: list[np.ndarray] = []
        for f in frames:
            try:
                import cv2  # type: ignore[import]
                resized = cv2.resize(f, (_FRAME_SIZE[1], _FRAME_SIZE[0]))
            except ImportError:
                # Fallback: nearest-neighbour resize via numpy slicing
                h, w = f.shape[:2]
                y_idx = (np.arange(_FRAME_SIZE[0]) * h / _FRAME_SIZE[0]).astype(int)
                x_idx = (np.arange(_FRAME_SIZE[1]) * w / _FRAME_SIZE[1]).astype(int)
                resized = f[np.ix_(y_idx, x_idx)]
            processed.append(resized.astype(np.float32) / 255.0)

        batch = np.stack(processed, axis=0)[np.newaxis]  # (1, T, H, W, 3)

        if self._infer_fn is not None:
            logits = self._infer_fn(batch)
        else:
            # Real ONNX inference path
            try:
                from Agent_Guru.vision.model_manager import ModelManager
                import os

                model_path = os.path.join("models", "activity_slowfast.onnx")
                if not os.path.exists(model_path):
                    # Graceful fallback: uniform distribution
                    return np.ones(len(ACTIVITY_CATEGORIES), dtype=np.float32) / len(ACTIVITY_CATEGORIES)

                mm = ModelManager()
                session = mm.load_model("activity_slowfast", model_path)
                input_name = session.get_inputs()[0].name
                logits = session.run(None, {input_name: batch})[0]
            except Exception as exc:
                logger.warning("ActivityRecognizer: inference failed", error=str(exc))
                return np.ones(len(ACTIVITY_CATEGORIES), dtype=np.float32) / len(ACTIVITY_CATEGORIES)

        # Softmax
        logits = np.asarray(logits).ravel()[:len(ACTIVITY_CATEGORIES)]
        exp_l = np.exp(logits - logits.max())
        return exp_l / exp_l.sum()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def push_frame(self, frame: np.ndarray) -> None:
        """Add a frame to the temporal buffer.

        Args:
            frame: uint8 RGB array of shape (H, W, 3).
        """
        self._frame_buffer.append(frame)

    async def classify(self, frame_buffer: list[np.ndarray] | None = None) -> ActivityResult | None:
        """Classify activity from the current frame buffer.

        Args:
            frame_buffer: Optional explicit frame list (overrides internal buffer).
                          Must contain ≥ _MIN_BUFFER_FRAMES frames.

        Returns:
            ActivityResult when buffer is sufficient and confidence ≥ gate,
            None when buffer is insufficient.
        """
        buf = frame_buffer if frame_buffer is not None else list(self._frame_buffer)

        if len(buf) < _MIN_BUFFER_FRAMES:
            logger.debug(
                "ActivityRecognizer: insufficient frames",
                have=len(buf),
                need=_MIN_BUFFER_FRAMES,
            )
            return None

        # Use the last _INPUT_FRAMES frames
        frames = buf[-_INPUT_FRAMES:]
        probs = self._run_inference(frames)

        top_idx = int(np.argmax(probs))
        confidence = float(probs[top_idx])
        label = ACTIVITY_CATEGORIES[top_idx]

        changed = label != self._previous_label
        result = ActivityResult(
            activity_label=label,
            confidence=confidence,
            previous_label=self._previous_label,
            changed=changed,
        )

        self._previous_label = label
        self._last_update_time = time.monotonic()

        logger.debug(
            "ActivityRecognizer: classified",
            label=label,
            confidence=confidence,
            changed=changed,
        )
        return result

    def make_events(self, result: ActivityResult, frame_seq: int) -> list[VisionEvent]:
        """Build VisionEvents for an ActivityResult.

        Emits:
        - activity_detected when confidence ≥ _CONFIDENCE_GATE
        - activity_changed (additionally) when activity transitioned

        Args:
            result: The ActivityResult to wrap.
            frame_seq: Current frame sequence number.

        Returns:
            List of 0–2 VisionEvents.
        """
        events: list[VisionEvent] = []
        if result.confidence < _CONFIDENCE_GATE:
            return events

        events.append(
            VisionEvent(
                event_type="activity_detected",
                timestamp=VisionEvent.now_timestamp(),
                source_module="activity",
                confidence=result.confidence,
                metadata={
                    "activity_label": result.activity_label,
                    "frame_seq": frame_seq,
                },
            )
        )

        if result.changed and result.previous_label is not None:
            events.append(
                VisionEvent(
                    event_type="activity_changed",
                    timestamp=VisionEvent.now_timestamp(),
                    source_module="activity",
                    confidence=result.confidence,
                    metadata={
                        "previous_label": result.previous_label,
                        "new_label": result.activity_label,
                        "frame_seq": frame_seq,
                    },
                )
            )

        return events
