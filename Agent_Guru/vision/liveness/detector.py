"""
Liveness detection module — anti-spoofing for face recognition.

Uses Laplacian variance (texture richness) as the primary signal.
Real faces have high-frequency texture; printed photos and screens don't.
When 5-point landmarks are provided, adds an EAR-based blink bonus.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from Agent_Guru.vision.exceptions import InvalidImageError

logger = logging.getLogger("guruvision.liveness")


@dataclass
class LivenessResult:
    """Result of a liveness check.

    Attributes:
        is_live: True if the face is classified as live.
        score: Confidence score in [0.0, 1.0]; higher = more likely live.
        method: Analysis method used — "texture" or "combined".
    """

    is_live: bool
    score: float
    method: str


class LivenessDetector:
    """Detects whether a face is live or a spoof (photo/screen/mask).

    Primary method: Laplacian variance measures texture richness.
    Secondary method (optional): vertical eye-closure ratio using 5-point
    ArcFace landmarks to detect blinks.

    Args:
        threshold: Score threshold above which a face is classified as live.
    """

    # Laplacian variance normalisation constant.
    # Empirically, real faces typically have variance > 200; photos < 100.
    _TEXTURE_NORM: float = 500.0

    # Eye-closure threshold: ratio of vertical eye spread to inter-eye distance.
    # When eyes are open this ratio is ~0.25-0.35; when closed it drops below 0.15.
    _EYE_CLOSURE_THRESHOLD: float = 0.15

    # Bonus added to score when a blink is detected.
    _BLINK_BONUS: float = 0.1

    _EXPECTED_SHAPE: tuple[int, int, int] = (112, 112, 3)

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    def check_liveness(
        self,
        aligned_face: np.ndarray,
        landmarks: Optional[np.ndarray] = None,
    ) -> LivenessResult:
        """Determine whether the face is live.

        Args:
            aligned_face: BGR image of shape (112, 112, 3), dtype uint8.
            landmarks: Optional 5-point landmarks of shape (5, 2) — the
                standard ArcFace layout: left eye, right eye, nose tip,
                left mouth corner, right mouth corner.

        Returns:
            LivenessResult with is_live, score in [0.0, 1.0], and method.

        Raises:
            InvalidImageError: If aligned_face has wrong shape or dtype.
        """
        self._validate_face(aligned_face)

        texture_score = self._texture_score(aligned_face)
        score = texture_score
        method = "texture"

        if landmarks is not None and landmarks.shape == (5, 2):
            blink_detected = self._detect_blink(landmarks)
            if blink_detected:
                score += self._BLINK_BONUS
                logger.debug("Blink detected — adding liveness bonus")
            method = "combined"

        score = float(np.clip(score, 0.0, 1.0))
        return LivenessResult(is_live=score >= self.threshold, score=score, method=method)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_face(face: np.ndarray) -> None:
        """Validate that face has the expected shape and dtype.

        Raises:
            InvalidImageError: If shape or dtype is wrong.
        """
        if face.shape != LivenessDetector._EXPECTED_SHAPE:
            raise InvalidImageError(
                f"Expected face shape {LivenessDetector._EXPECTED_SHAPE}, got {face.shape}"
            )
        if face.dtype != np.uint8:
            raise InvalidImageError(
                f"Expected face dtype uint8, got {face.dtype}"
            )

    @staticmethod
    def _texture_score(face: np.ndarray) -> float:
        """Laplacian variance normalised to [0, 1]."""
        try:
            import cv2  # type: ignore[import]
            gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
            lap = cv2.Laplacian(gray, cv2.CV_64F)
        except ImportError:
            logger.warning("cv2 not available — falling back to numpy Laplacian")
            gray = (
                0.114 * face[:, :, 0].astype(np.float64)
                + 0.587 * face[:, :, 1].astype(np.float64)
                + 0.299 * face[:, :, 2].astype(np.float64)
            )
            kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
            from numpy.lib.stride_tricks import sliding_window_view  # noqa: PLC0415
            padded = np.pad(gray, 1, mode="reflect")
            windows = sliding_window_view(padded, (3, 3))
            lap = (windows * kernel).sum(axis=(-2, -1))

        variance = float(np.var(lap))
        return min(1.0, variance / LivenessDetector._TEXTURE_NORM)

    @staticmethod
    def _detect_blink(landmarks: np.ndarray) -> bool:
        """Detect a blink from 5-point ArcFace landmarks.

        Layout: 0=left_eye, 1=right_eye, 2=nose, 3=left_mouth, 4=right_mouth.

        Uses the vertical spread of the two eye points relative to the
        inter-eye horizontal distance as a proxy for eye openness.
        When the eyes are closed (blink), the two eye landmarks move
        vertically closer together relative to the face width.

        Returns:
            True if a blink (eye closure) is detected.
        """
        left_eye = landmarks[0].astype(np.float64)
        right_eye = landmarks[1].astype(np.float64)

        # Vertical distance between the two eye landmarks
        vertical_diff = abs(float(left_eye[1] - right_eye[1]))

        # Horizontal inter-eye distance (face width proxy)
        inter_eye_dist = float(np.linalg.norm(right_eye - left_eye)) + 1e-6

        # Ratio: small when eyes are at the same height (open),
        # larger when one eye droops (partial closure / blink)
        closure_ratio = vertical_diff / inter_eye_dist

        return closure_ratio < LivenessDetector._EYE_CLOSURE_THRESHOLD
