"""
Liveness detection module — anti-spoofing for face recognition.

Uses Laplacian variance (texture richness) as the primary signal.
Real faces have high-frequency texture; printed photos and screens don't.
When 5-point landmarks are provided, adds an EAR-based blink bonus.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


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
    Secondary method (optional): Eye Aspect Ratio (EAR) blink detection
    using 5-point landmarks.

    Args:
        threshold: Score threshold above which a face is classified as live.
    """

    # Laplacian variance normalisation constant.
    # Empirically, real faces typically have variance > 200; photos < 100.
    _TEXTURE_NORM: float = 500.0

    # EAR threshold — below this value the eye is considered closed (blinking).
    _EAR_BLINK_THRESHOLD: float = 0.2

    # Bonus added to score when a blink is detected.
    _BLINK_BONUS: float = 0.1

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
        """
        texture_score = self._texture_score(aligned_face)
        score = texture_score
        method = "texture"

        if landmarks is not None and landmarks.shape == (5, 2):
            ear = self._eye_aspect_ratio(landmarks)
            if ear < self._EAR_BLINK_THRESHOLD:
                score += self._BLINK_BONUS
            method = "combined"

        score = float(np.clip(score, 0.0, 1.0))
        return LivenessResult(is_live=score >= self.threshold, score=score, method=method)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _texture_score(face: np.ndarray) -> float:
        """Laplacian variance normalised to [0, 1]."""
        try:
            import cv2  # type: ignore[import]
            gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
            lap = cv2.Laplacian(gray, cv2.CV_64F)
        except Exception:
            # cv2 not available — fall back to numpy
            gray = (
                0.114 * face[:, :, 0].astype(np.float64)
                + 0.587 * face[:, :, 1].astype(np.float64)
                + 0.299 * face[:, :, 2].astype(np.float64)
            )
            kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
            from numpy.lib.stride_tricks import sliding_window_view  # noqa: PLC0415
            # Simple convolution via sliding window (no scipy dependency)
            padded = np.pad(gray, 1, mode="reflect")
            windows = sliding_window_view(padded, (3, 3))
            lap = (windows * kernel).sum(axis=(-2, -1))

        variance = float(np.var(lap))
        return min(1.0, variance / LivenessDetector._TEXTURE_NORM)

    @staticmethod
    def _eye_aspect_ratio(landmarks: np.ndarray) -> float:
        """Approximate EAR from 5-point ArcFace landmarks.

        Layout: 0=left_eye, 1=right_eye, 2=nose, 3=left_mouth, 4=right_mouth.
        With only 2 eye points we use the inter-eye distance as a proxy.
        A very small distance (eyes close together in the image) hints at
        a closed-eye / blink state.
        """
        left_eye = landmarks[0].astype(np.float64)
        right_eye = landmarks[1].astype(np.float64)
        inter_eye = float(np.linalg.norm(right_eye - left_eye))
        # Normalise by face width (approx. distance between mouth corners)
        left_mouth = landmarks[3].astype(np.float64)
        right_mouth = landmarks[4].astype(np.float64)
        mouth_width = float(np.linalg.norm(right_mouth - left_mouth)) + 1e-6
        return inter_eye / mouth_width
