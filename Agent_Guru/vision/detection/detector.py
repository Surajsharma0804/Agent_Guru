"""
Face detection module using RetinaFace (InsightFace) with OpenCV Haar cascade fallback.

Provides FaceDetector and Detection dataclass for locating faces in images/video frames.

Performance target: ≥10 FPS on CPU, ≥30 FPS on GPU.
InsightFace is initialised lazily on the first call to detect() with a 15-second
thread timeout to guard against hanging model loads.

**Validates: Requirements 3.1, 3.3, 3.4, 3.5, 26.4**
"""

from __future__ import annotations

import logging
import threading
import warnings
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency checks
# ---------------------------------------------------------------------------

try:
    import cv2  # type: ignore[import-untyped]

    _CV2_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CV2_AVAILABLE = False
    warnings.warn(
        "OpenCV (cv2) not installed. Install opencv-python for full functionality.",
        ImportWarning,
        stacklevel=2,
    )


def _check_insightface_available(timeout: float = 5.0) -> bool:
    """Check if InsightFace is importable within a timeout.

    Uses a daemon thread to avoid hanging the main thread if the insightface
    package triggers slow model loading on import.
    """
    result: list[bool] = []

    def _try_import() -> None:
        try:
            import insightface  # type: ignore[import-untyped]  # noqa: F401

            result.append(True)
        except ImportError:
            result.append(False)

    t = threading.Thread(target=_try_import, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if not result:
        return False
    return result[0]


_INSIGHTFACE_AVAILABLE: bool = _check_insightface_available()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Detection:
    """A single face detection result.

    Attributes:
        bbox: Bounding box as (x, y, w, h) in pixel coordinates.
        landmarks: Optional array of shape (5, 2) containing the five facial
            keypoints: left_eye, right_eye, nose, left_mouth, right_mouth.
            May be None when using the OpenCV Haar cascade fallback.
        confidence: Detection confidence score in [0.0, 1.0].
    """

    bbox: tuple[int, int, int, int]  # x, y, w, h
    landmarks: Optional[np.ndarray]  # shape (5, 2) — 5 facial keypoints
    confidence: float  # 0.0 to 1.0


# ---------------------------------------------------------------------------
# FaceDetector
# ---------------------------------------------------------------------------


class FaceDetector:
    """Detect faces in images using RetinaFace (InsightFace) or OpenCV fallback.

    InsightFace's RetinaFace is used when available; otherwise the detector
    falls back to OpenCV's Haar cascade so the module always works even
    without the optional insightface package.

    The underlying model is initialised lazily on the first call to
    :meth:`detect` (not in ``__init__``) to keep construction fast.

    Args:
        confidence_threshold: Minimum detection confidence to include a face
            in the results (default 0.5).
        use_gpu: Use GPU acceleration when InsightFace is available.
            Ignored when falling back to OpenCV (default False).

    Example::

        detector = FaceDetector(confidence_threshold=0.5, use_gpu=False)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.detect(frame)
        for d in detections:
            x, y, w, h = d.bbox
            print(f"Face at ({x},{y}) size {w}x{h}, conf={d.confidence:.2f}")
    """

    def __init__(
        self,
        confidence_threshold: float = 0.5,
        use_gpu: bool = False,
    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(
                f"confidence_threshold must be in [0.0, 1.0], got {confidence_threshold}"
            )
        self.confidence_threshold = confidence_threshold
        self._use_gpu = use_gpu

        # Lazy-init state — populated on first detect() call
        self._insightface_app: Optional[object] = None
        self._insightface_init_attempted: bool = False

        if not _INSIGHTFACE_AVAILABLE:
            logger.warning(
                "InsightFace not available — FaceDetector will use OpenCV Haar cascade fallback."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Detect all faces in *frame* and return a list of :class:`Detection` objects.

        Returns an empty list when no faces are found.  Never raises an
        exception due to an empty or featureless frame.

        Args:
            frame: BGR image as a NumPy array of shape (H, W, 3) and dtype
                uint8.  Greyscale or other shapes are handled gracefully.

        Returns:
            List of :class:`Detection` objects filtered by
            ``confidence_threshold``.  May be empty.

        Raises:
            ValueError: If *frame* is not a valid NumPy array.
        """
        if not isinstance(frame, np.ndarray):
            raise ValueError("frame must be a numpy ndarray")

        # Ensure we have a 3-channel uint8 image
        frame = self._ensure_bgr(frame)

        app = self._get_insightface_app()
        if app is not None:
            return self._detect_insightface(frame, app)
        return self._detect_opencv(frame)

    async def detect_async(self, frame: np.ndarray) -> list[Detection]:
        """Async wrapper around detect() — runs GPU inference in a thread pool.

        Use this from async contexts to avoid blocking the event loop during
        GPU/CPU inference.

        Args:
            frame: BGR image as a NumPy array of shape (H, W, 3), dtype uint8.

        Returns:
            List of :class:`Detection` objects.
        """
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.detect, frame)

    # ------------------------------------------------------------------
    # Lazy model initialisation
    # ------------------------------------------------------------------

    def _get_insightface_app(self) -> Optional[object]:
        """Lazily initialise InsightFace with a 15-second thread timeout."""
        if self._insightface_init_attempted:
            return self._insightface_app
        self._insightface_init_attempted = True

        if not _INSIGHTFACE_AVAILABLE:
            return None

        result_holder: list[object] = []
        error_holder: list[Exception] = []

        def _init() -> None:
            try:
                from insightface.app import FaceAnalysis  # type: ignore[import-untyped]

                ctx_id = 0 if self._use_gpu else -1
                providers = (
                    ["CUDAExecutionProvider"] if self._use_gpu else ["CPUExecutionProvider"]
                )
                app = FaceAnalysis(name="buffalo_l", providers=providers)
                app.prepare(ctx_id=ctx_id, det_size=(640, 640))
                result_holder.append(app)
            except Exception as exc:
                error_holder.append(exc)

        t = threading.Thread(target=_init, daemon=True)
        t.start()
        t.join(timeout=15)

        if t.is_alive():
            logger.warning(
                "InsightFace init timed out after 15s — falling back to OpenCV Haar cascade."
            )
        elif error_holder:
            logger.warning(
                "InsightFace init failed: %s — falling back to OpenCV Haar cascade.",
                error_holder[0],
            )
        elif result_holder:
            self._insightface_app = result_holder[0]
            logger.info("InsightFace FaceDetector initialised (gpu=%s)", self._use_gpu)

        return self._insightface_app

    # ------------------------------------------------------------------
    # Detection backends
    # ------------------------------------------------------------------

    def _detect_insightface(self, frame: np.ndarray, app: object) -> list[Detection]:
        """Run RetinaFace detection via InsightFace."""
        try:
            faces = app.get(frame)  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning("InsightFace detection failed: %s — returning empty list.", exc)
            return []

        results: list[Detection] = []
        for face in faces:
            try:
                box = face.bbox.astype(int)
                x, y, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
                w = max(1, x2 - x)
                h = max(1, y2 - y)
                conf = float(
                    max(
                        0.0,
                        min(
                            1.0,
                            float(face.det_score) if hasattr(face, "det_score") else 1.0,
                        ),
                    )
                )
                if conf < self.confidence_threshold:
                    continue
                landmarks: Optional[np.ndarray] = None
                if hasattr(face, "kps") and face.kps is not None:
                    landmarks = np.array(face.kps, dtype=np.float32)
                    if landmarks.shape != (5, 2):
                        landmarks = None
                results.append(Detection(bbox=(x, y, w, h), landmarks=landmarks, confidence=conf))
            except Exception as exc:  # pragma: no cover
                logger.warning("Skipping malformed InsightFace detection: %s", exc)

        return results

    def _detect_opencv(self, frame: np.ndarray) -> list[Detection]:
        """Run OpenCV Haar cascade detection as fallback."""
        if not _CV2_AVAILABLE:
            logger.warning("cv2 unavailable — returning empty detection list.")
            return []

        try:
            grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = cascade.detectMultiScale(
                grey, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )
        except Exception as exc:
            logger.warning("OpenCV Haar detection failed: %s — returning empty list.", exc)
            return []

        results: list[Detection] = []
        # detectMultiScale returns an empty tuple when no faces found
        if len(faces) == 0:
            return results

        for x, y, w, h in faces:
            conf = 0.8  # Haar cascade doesn't provide a confidence score
            if conf < self.confidence_threshold:
                continue
            results.append(
                Detection(
                    bbox=(int(x), int(y), int(w), int(h)),
                    landmarks=None,
                    confidence=conf,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_bgr(frame: np.ndarray) -> np.ndarray:
        """Convert frame to 3-channel uint8 BGR if needed."""
        if frame.ndim == 2:
            # Greyscale → BGR
            if _CV2_AVAILABLE:
                return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            return np.stack([frame, frame, frame], axis=-1).astype(np.uint8)
        if frame.ndim == 3 and frame.shape[2] == 4:
            # BGRA → BGR
            if _CV2_AVAILABLE:
                return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            return frame[:, :, :3].astype(np.uint8)
        if frame.dtype != np.uint8:
            # Clip and cast
            return np.clip(frame, 0, 255).astype(np.uint8)
        return frame
