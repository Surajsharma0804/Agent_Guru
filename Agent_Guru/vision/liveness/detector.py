"""Liveness detection module — anti-spoofing for face recognition.

Primary: ONNX anti-spoofing model (e.g. Silent-Face / MiniFASNet).
Fallback: Laplacian variance (texture richness) + optional EAR blink bonus.

Real faces have high-frequency texture; printed photos and screens don't.
When 5-point landmarks are provided, adds an EAR-based blink bonus.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import numpy as np

from Agent_Guru.vision.exceptions import InvalidImageError

logger = logging.getLogger("guruvision.liveness")


@dataclass
class LivenessResult:
    """Result of a liveness check.

    Attributes:
        is_live: True if the face is classified as live.
        score: Confidence score in [0.0, 1.0]; higher = more likely live.
        method: Analysis method used — "onnx", "texture", or "combined".

    """

    is_live: bool
    score: float
    method: str


class LivenessDetector:
    """Detects whether a face is live or a spoof (photo/screen/mask).

    Primary method: ONNX anti-spoofing model (Silent-Face / MiniFASNet).
    Fallback method: Laplacian variance measures texture richness.
    Secondary method (optional): vertical eye-closure ratio using 5-point
    ArcFace landmarks to detect blinks.

    Args:
        threshold: Score threshold above which a face is classified as live.
        model_path: Optional path to an ONNX anti-spoofing model.
            When provided and the file exists, ONNX inference is used.
            Otherwise falls back to the Laplacian heuristic.
        use_gpu: Use CUDAExecutionProvider when True.

    """

    # Laplacian variance normalisation constant.
    # Empirically, real faces typically have variance > 200; photos < 100.
    _TEXTURE_NORM: float = 500.0

    # Eye-closure threshold: ratio of vertical eye spread to inter-eye distance.
    _EYE_CLOSURE_THRESHOLD: float = 0.15

    # Bonus added to score when a blink is detected.
    _BLINK_BONUS: float = 0.1

    _EXPECTED_SHAPE: tuple[int, int, int] = (112, 112, 3)

    def __init__(
        self,
        threshold: float = 0.5,
        model_path: str | None = None,
        use_gpu: bool = False,
    ) -> None:
        self.threshold = threshold
        self._model_path = model_path
        self._use_gpu = use_gpu
        self._session: object | None = None

    # ------------------------------------------------------------------
    # ONNX session
    # ------------------------------------------------------------------

    def _get_session(self) -> object | None:
        """Lazy-load the ONNX anti-spoofing model. Returns None if unavailable."""
        if self._session is not None:
            return self._session
        if not self._model_path or not os.path.isfile(self._model_path):  # noqa: PTH113
            return None
        try:
            import onnxruntime as ort  # type: ignore[import]

            providers = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if self._use_gpu
                else ["CPUExecutionProvider"]
            )
            self._session = ort.InferenceSession(self._model_path, providers=providers)
            logger.info("Loaded liveness ONNX model from '%s'", self._model_path)
        except Exception as exc:
            logger.exception(
                "Failed to load liveness ONNX model from '%s': %s — using heuristic fallback",
                self._model_path,
                exc,
            )
        return self._session

    def _run_onnx(self, face: np.ndarray) -> float:
        """Run ONNX anti-spoofing inference. Returns liveness score in [0, 1]."""
        session = self._get_session()
        if session is None:
            return -1.0  # sentinel: ONNX not available

        try:
            # Determine model input spatial size from the session graph
            inp = session.get_inputs()[0]  # type: ignore[union-attr]
            # Shape is typically [1, 3, H, W]; fall back to 80 (MiniFASNet default)
            shape = inp.shape
            model_h = (
                int(shape[2])
                if len(shape) >= 4 and isinstance(shape[2], int) and shape[2] > 0
                else 80
            )
            model_w = (
                int(shape[3])
                if len(shape) >= 4 and isinstance(shape[3], int) and shape[3] > 0
                else 80
            )

            # Resize face to model input size, then normalise to [-1, 1]
            try:
                import cv2  # type: ignore[import]

                resized = cv2.resize(face, (model_w, model_h))
            except ImportError:
                row_idx = (np.arange(model_h) * face.shape[0] / model_h).astype(int)
                col_idx = (np.arange(model_w) * face.shape[1] / model_w).astype(int)
                resized = face[np.ix_(row_idx, col_idx)]

            # Preprocess: BGR uint8 → float32 NCHW, normalised to [-1, 1]
            rgb = resized[:, :, ::-1].astype(np.float32) / 127.5 - 1.0
            blob = rgb.transpose(2, 0, 1)[np.newaxis]
            input_name = inp.name
            outputs = session.run(None, {input_name: blob})  # type: ignore[union-attr]
            logits = outputs[0][0]
            # Assume binary output: [spoof_score, live_score]
            if len(logits) >= 2:
                exp = np.exp(logits - np.max(logits))
                probs = exp / exp.sum()
                return float(probs[1])  # live probability
            return float(1.0 / (1.0 + np.exp(-float(logits[0]))))
        except Exception:
            logger.exception("Liveness ONNX inference failed: %s — using heuristic")
            return -1.0

    def check_liveness(
        self,
        aligned_face: np.ndarray,
        landmarks: np.ndarray | None = None,
    ) -> LivenessResult:
        """Determine whether the face is live.

        Tries ONNX anti-spoofing model first; falls back to Laplacian heuristic.

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

        # Try ONNX model first
        onnx_score = self._run_onnx(aligned_face)
        if onnx_score >= 0.0:
            score = float(np.clip(onnx_score, 0.0, 1.0))
            return LivenessResult(is_live=score >= self.threshold, score=score, method="onnx")

        # Fallback: Laplacian texture heuristic
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
            msg = f"Expected face shape {LivenessDetector._EXPECTED_SHAPE}, got {face.shape}"
            raise InvalidImageError(
                msg,
            )
        if face.dtype != np.uint8:
            msg = f"Expected face dtype uint8, got {face.dtype}"
            raise InvalidImageError(msg)

    @staticmethod
    def _texture_score(face: np.ndarray) -> float:
        """Laplacian variance normalised to [0, 1]."""
        try:
            import cv2  # type: ignore[import]

            gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
            lap = cv2.Laplacian(gray, cv2.CV_64F)
        except ImportError:
            logger.exception("cv2 not available — falling back to numpy Laplacian")
            gray = (
                0.114 * face[:, :, 0].astype(np.float64)
                + 0.587 * face[:, :, 1].astype(np.float64)
                + 0.299 * face[:, :, 2].astype(np.float64)
            )
            kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
            from numpy.lib.stride_tricks import sliding_window_view

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
