"""Liveness detection module - anti-spoofing for face recognition.

Primary: ONNX anti-spoofing model (e.g. Silent-Face / MiniFASNet).
Fallback: Laplacian variance (texture richness) only.

Real faces have high-frequency texture; printed photos and screens don't.

BUG FIX (Round 15): this module used to also accept 5-point ArcFace
landmarks (left_eye, right_eye, nose, left_mouth, right_mouth) in the
fallback path and add a "blink bonus" to the liveness score when a blink
was "detected" via `_detect_blink()`. That function computed
`|left_eye_y - right_eye_y| / inter_eye_distance` -- which is the standard
formula for a face's ROLL/TILT angle (how level the head is), not eye
closure. Genuine blink/eye-closure detection (the classic Eye Aspect
Ratio) needs per-eye eyelid contour points (upper lid vs. lower lid of the
SAME eye); a 5-point layout with a single center point per eye cannot
express eye openness at all, only the angle between the two eyes.

In practice this meant the "blink bonus" fired whenever the face was
roughly level/upright in the frame -- true for essentially any face photo
someone bothered to align well, including a printed photo or a screen
replay held up straight. So the bonus added score to spoofed inputs just
as readily as to live ones, providing no actual anti-spoofing signal while
giving a false impression that blink-based liveness was being checked.
Removed rather than "fixed in place": a 5-point landmark set fundamentally
cannot support real blink detection, so there is no correct version of
this check to keep with the data available here. Removing it makes the
system marginally STRICTER (a spoof can no longer pick up the +0.1 bonus),
which is the safe direction for a security check under uncertainty.
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
        method: Analysis method used - "onnx", "texture", or "combined".

    """

    is_live: bool
    score: float
    method: str


class LivenessDetector:
    """Detects whether a face is live or a spoof (photo/screen/mask).

    Primary method: ONNX anti-spoofing model (Silent-Face / MiniFASNet).
    Fallback method: Laplacian variance measures texture richness.

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
        # BUG FIX (Round 15): see _get_session() docstring below.
        self._session_load_failed: bool = False

    # ------------------------------------------------------------------
    # ONNX session
    # ------------------------------------------------------------------

    def _get_session(self) -> object | None:
        """Lazy-load the ONNX anti-spoofing model. Returns None if unavailable.

        BUG FIX (Round 15): this used to only check `self._session is not
        None` to decide whether loading had already been attempted, so a
        model path that exists but fails to load (corrupt file, incompatible
        opset, wrong providers, truncated download, ...) was never
        remembered as failed -- every single call to check_liveness()
        re-entered this method, re-imported onnxruntime, and re-attempted
        `ort.InferenceSession(...)` from scratch, only to hit the same
        exception again. On a hot path (this runs per-frame in the face
        pipeline via vision/engine.py) that means paying the full load-and-
        fail cost (disk I/O, exception construction, a full-traceback
        `logger.exception()` call) on every single frame instead of once.
        Fixed by caching the failure with `_session_load_failed`, which is
        checked before any load is attempted; behavior is otherwise
        identical -- a working model still loads exactly once and is
        reused, and the texture-heuristic fallback is unchanged either way.
        """
        if self._session is not None:
            return self._session
        if self._session_load_failed:
            return None
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
            self._session_load_failed = True
            logger.exception(
                "Failed to load liveness ONNX model from '%s': %s - using heuristic fallback "
                "(will not retry loading this session again)",
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
            logger.exception("Liveness ONNX inference failed - using heuristic")
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
            landmarks: Optional 5-point landmarks of shape (5, 2) - the
                standard ArcFace layout: left eye, right eye, nose tip,
                left mouth corner, right mouth corner. Accepted for API
                compatibility with callers (e.g. vision/engine.py passes
                `detection.landmarks`), but not currently used: see the
                module docstring's "Fixed" note on why a 5-point layout
                cannot support genuine blink/eye-closure detection. Kept
                as a parameter so a future round can add a real signal
                (e.g. from eyelid-contour landmarks) without changing this
                method's call sites.

        Returns:
            LivenessResult with is_live, score in [0.0, 1.0], and method.

        Raises:
            InvalidImageError: If aligned_face has wrong shape or dtype.

        """
        del landmarks  # not used -- see Args note above
        self._validate_face(aligned_face)

        # Try ONNX model first
        onnx_score = self._run_onnx(aligned_face)
        if onnx_score >= 0.0:
            score = float(np.clip(onnx_score, 0.0, 1.0))
            return LivenessResult(is_live=score >= self.threshold, score=score, method="onnx")

        # Fallback: Laplacian texture heuristic
        score = float(np.clip(self._texture_score(aligned_face), 0.0, 1.0))
        return LivenessResult(is_live=score >= self.threshold, score=score, method="texture")

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
            logger.exception("cv2 not available - falling back to numpy Laplacian")
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
