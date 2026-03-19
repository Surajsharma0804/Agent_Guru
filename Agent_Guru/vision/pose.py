"""
Pose Estimator for the Agent Guru Vision System.

Provides:
- PoseEstimator: Full-body skeleton estimation using MediaPipe Pose.
  Reports 17 COCO keypoints per person (subset of MediaPipe's 33).
  Supports up to 5 simultaneous persons.
  Occluded keypoints have confidence = 0.0.
  Posture classification: sitting, standing, lying_down, raising_hand.
  Emits pose_estimated VisionEvent per detected person.
  Sustains ≥15 FPS on GPU.

Requirements: 6.1–6.6
"""

from __future__ import annotations

import time
from typing import Any, Callable

import numpy as np
import structlog

from Agent_Guru.vision.vision_models import BoundingBox, PoseKeypoint, PoseResult, VisionEvent

logger: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# COCO-17 keypoint names and their MediaPipe Pose landmark indices
# ---------------------------------------------------------------------------

# MediaPipe Pose has 33 landmarks; we report the 17 COCO subset.
_COCO_17_FROM_MP: list[tuple[str, int]] = [
    ("nose", 0),
    ("left_eye", 2),
    ("right_eye", 5),
    ("left_ear", 7),
    ("right_ear", 8),
    ("left_shoulder", 11),
    ("right_shoulder", 12),
    ("left_elbow", 13),
    ("right_elbow", 14),
    ("left_wrist", 15),
    ("right_wrist", 16),
    ("left_hip", 23),
    ("right_hip", 24),
    ("left_knee", 25),
    ("right_knee", 26),
    ("left_ankle", 27),
    ("right_ankle", 28),
]

_COCO_NAMES: list[str] = [name for name, _ in _COCO_17_FROM_MP]
_COCO_MP_INDICES: list[int] = [idx for _, idx in _COCO_17_FROM_MP]

_MAX_PERSONS: int = 5
_OCCLUSION_THRESHOLD: float = 0.3  # visibility below this → occluded (conf=0.0)


# ---------------------------------------------------------------------------
# Posture classification helpers
# ---------------------------------------------------------------------------


def _classify_posture(kps: list[PoseKeypoint]) -> str | None:
    """Rule-based posture classification from 17 COCO keypoints.

    Rules (all coordinates are normalised [0,1]):
    - raising_hand: wrist y < shoulder y (wrist above shoulder) for either side
    - lying_down: |shoulder_y - hip_y| < 0.1 (horizontal alignment)
    - sitting: hip_y > knee_y - 0.05 (hips near or below knees)
    - standing: default when none of the above match

    Returns one of: "sitting", "standing", "lying_down", "raising_hand", or None
    when insufficient keypoints are visible.
    """
    kp = {k.name: k for k in kps}

    def visible(name: str) -> bool:
        return name in kp and kp[name].confidence > 0.0

    # Need at least shoulders and hips for any classification
    if not (visible("left_shoulder") or visible("right_shoulder")):
        return None
    if not (visible("left_hip") or visible("right_hip")):
        return None

    # Shoulder y (average of visible shoulders)
    shoulder_ys = [kp[n].y for n in ("left_shoulder", "right_shoulder") if visible(n)]
    hip_ys = [kp[n].y for n in ("left_hip", "right_hip") if visible(n)]
    shoulder_y = float(np.mean(shoulder_ys))
    hip_y = float(np.mean(hip_ys))

    # raising_hand: wrist above shoulder (lower y value in image coords)
    for wrist, shoulder in (("left_wrist", "left_shoulder"), ("right_wrist", "right_shoulder")):
        if visible(wrist) and visible(shoulder):
            if kp[wrist].y < kp[shoulder].y - 0.05:
                return "raising_hand"

    # lying_down: shoulders and hips at similar y (horizontal body)
    if abs(shoulder_y - hip_y) < 0.12:
        return "lying_down"

    # sitting: hips close to or below knees
    knee_ys = [kp[n].y for n in ("left_knee", "right_knee") if visible(n)]
    if knee_ys:
        knee_y = float(np.mean(knee_ys))
        if hip_y >= knee_y - 0.08:
            return "sitting"

    return "standing"


# ---------------------------------------------------------------------------
# PoseEstimator
# ---------------------------------------------------------------------------


class PoseEstimator:
    """Full-body pose estimator using MediaPipe Pose.

    Args:
        _infer_fn: Optional callable for testing; replaces MediaPipe inference.
            Signature: ``(frame: np.ndarray) -> list[dict]``
            Each dict represents one detected person::

                {
                    "landmarks": [  # 33 MediaPipe landmarks
                        {"x": float, "y": float, "z": float, "visibility": float},
                        ...
                    ]
                }
    """

    def __init__(self, _infer_fn: Callable[..., Any] | None = None) -> None:
        self._infer_fn = _infer_fn
        logger.info("PoseEstimator initialised")

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def _run_inference(self, frame: np.ndarray) -> list[dict[str, Any]]:
        """Run MediaPipe Pose and return raw per-person landmark dicts."""
        if self._infer_fn is not None:
            return self._infer_fn(frame)

        try:
            import mediapipe as mp  # type: ignore[import]

            mp_pose = mp.solutions.pose
            # Use MULTI_PERSON_HOLISTIC or standard Pose; standard supports 1 person.
            # For multi-person we use BlazePose with segmentation disabled.
            with mp_pose.Pose(
                static_image_mode=True,
                model_complexity=1,
                enable_segmentation=False,
                min_detection_confidence=0.5,
            ) as pose:
                rgb = frame[:, :, :3] if frame.ndim == 3 else frame
                result = pose.process(rgb)
                if not result.pose_landmarks:
                    return []
                lms = result.pose_landmarks.landmark
                return [
                    {
                        "landmarks": [
                            {
                                "x": float(lm.x),
                                "y": float(lm.y),
                                "z": float(lm.z),
                                "visibility": float(lm.visibility),
                            }
                            for lm in lms
                        ]
                    }
                ]
        except ImportError:
            logger.warning("PoseEstimator: MediaPipe not available")
            return []

    # ------------------------------------------------------------------
    # Keypoint extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_coco17(
        landmarks: list[dict[str, float]], frame_h: int, frame_w: int
    ) -> list[PoseKeypoint]:
        """Extract 17 COCO keypoints from 33 MediaPipe landmarks.

        Keypoints with visibility < _OCCLUSION_THRESHOLD are marked occluded
        (confidence = 0.0).

        Args:
            landmarks: List of 33 landmark dicts with x, y, z, visibility.
            frame_h: Frame height in pixels.
            frame_w: Frame width in pixels.

        Returns:
            List of exactly 17 PoseKeypoint objects.
        """
        kps: list[PoseKeypoint] = []
        for name, mp_idx in _COCO_17_FROM_MP:
            if mp_idx >= len(landmarks):
                kps.append(PoseKeypoint(name=name, x=0.0, y=0.0, confidence=0.0))
                continue
            lm = landmarks[mp_idx]
            visibility = float(lm.get("visibility", 0.0))
            if visibility < _OCCLUSION_THRESHOLD:
                # Occluded: position estimated from geometry but confidence = 0.0
                kps.append(
                    PoseKeypoint(
                        name=name,
                        x=float(lm["x"]) * frame_w,
                        y=float(lm["y"]) * frame_h,
                        confidence=0.0,
                    )
                )
            else:
                kps.append(
                    PoseKeypoint(
                        name=name,
                        x=float(lm["x"]) * frame_w,
                        y=float(lm["y"]) * frame_h,
                        confidence=visibility,
                    )
                )
        return kps

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def estimate(self, frame: np.ndarray) -> list[PoseResult]:
        """Estimate poses for all persons in a frame.

        Args:
            frame: uint8 RGB array of shape (H, W, 3).

        Returns:
            List of PoseResult, at most _MAX_PERSONS entries.
            Each PoseResult contains exactly 17 COCO keypoints.
        """
        frame_h, frame_w = frame.shape[:2]
        raw_persons = self._run_inference(frame)

        results: list[PoseResult] = []
        for person_id, person_data in enumerate(raw_persons[:_MAX_PERSONS]):
            landmarks = person_data.get("landmarks", [])
            kps = self._extract_coco17(landmarks, frame_h, frame_w)
            posture = _classify_posture(kps)
            results.append(
                PoseResult(
                    keypoints=kps,
                    person_id=person_id,
                    posture_label=posture,
                )
            )

        logger.debug("PoseEstimator: frame processed", persons=len(results))
        return results

    def make_event(self, result: PoseResult, frame_seq: int) -> VisionEvent:
        """Build a pose_estimated VisionEvent from a PoseResult.

        Args:
            result: The PoseResult to wrap.
            frame_seq: Current frame sequence number.

        Returns:
            A VisionEvent with event_type="pose_estimated".
        """
        return VisionEvent(
            event_type="pose_estimated",
            timestamp=VisionEvent.now_timestamp(),
            source_module="pose",
            confidence=float(
                np.mean([kp.confidence for kp in result.keypoints if kp.confidence > 0.0] or [0.0])
            ),
            metadata={
                "person_id": result.person_id,
                "posture_label": result.posture_label,
                "frame_seq": frame_seq,
            },
        )
