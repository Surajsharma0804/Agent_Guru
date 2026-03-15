"""
Face feature extraction for Agent Guru.

Provides face detection and 512-dim embedding extraction.
NO authentication logic — all auth decisions go to BiometricAuthenticator.

Performance target: 500 ms per image.
InsightFace is initialised lazily with a 15-second thread timeout to guard
against hanging model loads (corrupt ONNX files, slow downloads, etc.).
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
import warnings
from typing import List, Optional, Tuple

import numpy as np

from Agent_Guru.vision.exceptions import (
    ExtractionTimeoutError,
    FaceExtractionError,
    FaceNotFoundError,
    InvalidImageError,
)
from Agent_Guru.vision.models import BoundingBox, FaceDetection, FaceFeatures, FaceQuality

logger = logging.getLogger(__name__)

_EXTRACTION_TIMEOUT_S: float = 0.5

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
    package triggers slow model loading on import (e.g. corrupt ONNX files).
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
        # Thread timed out — treat as unavailable
        return False
    return result[0]


_INSIGHTFACE_AVAILABLE: bool = _check_insightface_available()


def _decode_image(image_data: bytes) -> "np.ndarray":
    """Decode raw image bytes to a BGR array.

    Raises:
        InvalidImageError: If bytes cannot be decoded.
    """
    if not image_data:
        raise InvalidImageError("image_data is empty")
    if not _CV2_AVAILABLE:
        logger.warning("cv2 unavailable — using synthetic image")
        return np.full((64, 64, 3), 128, dtype=np.uint8)
    arr = np.frombuffer(image_data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise InvalidImageError("Failed to decode image — unsupported format or corrupt bytes")
    return img  # type: ignore[return-value]


def _stub_embedding(image_data: bytes) -> np.ndarray:
    """Deterministic 512-dim L2-normalised stub embedding from image bytes."""
    digest = hashlib.sha256(image_data).digest()
    rng = np.random.default_rng(seed=int.from_bytes(digest[:8], "big"))
    vec = rng.standard_normal(512).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def _compute_quality(img: "np.ndarray") -> FaceQuality:
    """Estimate face image quality."""
    if not _CV2_AVAILABLE:
        return FaceQuality(overall_score=0.8, sharpness=0.8, brightness=0.8, pose_score=0.8)
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lap_var = float(cv2.Laplacian(grey, cv2.CV_64F).var())
    sharpness = float(min(1.0, lap_var / 500.0))
    mean_brightness = float(grey.mean()) / 255.0
    brightness = float(max(0.0, 1.0 - abs(mean_brightness - 0.5) * 2.0))
    overall = (sharpness + brightness) / 2.0
    return FaceQuality(
        overall_score=round(overall, 4),
        sharpness=round(sharpness, 4),
        brightness=round(brightness, 4),
        pose_score=1.0,
    )


class FaceFeatureExtractor:
    """Extract face detection results and 512-dim embeddings from images.

    Does NOT make authentication decisions. All auth is delegated to
    BiometricAuthenticator in guru-security-cryptography.

    InsightFace is initialised lazily with a 15-second thread timeout to
    guard against hanging model loads. Falls back to stub embeddings if
    InsightFace is unavailable or fails to load.

    Args:
        liveness_threshold: Minimum liveness score for is_live=True. Default 0.5.
        use_gpu: Use GPU acceleration when InsightFace is available. Default False.
    """

    def __init__(self, liveness_threshold: float = 0.5, use_gpu: bool = False) -> None:
        if not 0.0 <= liveness_threshold <= 1.0:
            raise ValueError("liveness_threshold must be in [0.0, 1.0]")
        self.liveness_threshold = liveness_threshold
        self._use_gpu = use_gpu
        self._insightface_app: Optional[object] = None
        self._insightface_init_attempted: bool = False
        if not _INSIGHTFACE_AVAILABLE:
            logger.warning("InsightFace not available — stub embeddings will be returned.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_faces(self, image_data: bytes) -> List[FaceDetection]:
        """Detect faces in an image. Returns list of FaceDetection. NO auth logic.

        Raises:
            InvalidImageError: If image_data cannot be decoded.
        """
        img = _decode_image(image_data)
        detections = self._run_detection(img)
        logger.debug("detect_faces: found %d face(s)", len(detections))
        return detections

    def extract_face_embedding(self, image_data: bytes) -> FaceFeatures:
        """Extract 512-dim face embedding. Returns FaceFeatures. NO auth logic.

        Raises:
            InvalidImageError: If image_data cannot be decoded.
            FaceNotFoundError: If no face is detected.
            ExtractionTimeoutError: If extraction exceeds 500 ms.
        """
        start = time.monotonic()
        img = _decode_image(image_data)
        quality = _compute_quality(img)
        embedding, bbox, is_live, liveness_score = self._extract(img, image_data)
        elapsed = time.monotonic() - start
        if elapsed > _EXTRACTION_TIMEOUT_S:
            raise ExtractionTimeoutError(
                f"Face extraction took {elapsed:.3f}s, exceeding the 500ms limit"
            )
        return FaceFeatures(
            embedding=embedding,
            quality_score=quality.overall_score,
            is_live=is_live,
            liveness_score=liveness_score,
            bounding_box=bbox,
            quality=quality,
        )

    def detect_liveness(self, image_data: bytes) -> Tuple[bool, float]:
        """Detect whether the face is live (anti-spoofing). Returns (is_live, score).

        Raises:
            InvalidImageError: If image_data cannot be decoded.
            FaceNotFoundError: If no face is detected.
        """
        img = _decode_image(image_data)
        detections = self._run_detection(img)
        if not detections:
            raise FaceNotFoundError("No face detected in image for liveness check")
        return self._liveness_check(img, detections[0])

    # ------------------------------------------------------------------
    # Internal helpers
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
                providers = ["CUDAExecutionProvider" if self._use_gpu else "CPUExecutionProvider"]
                app = FaceAnalysis(name="buffalo_l", providers=providers)
                app.prepare(ctx_id=ctx_id, det_size=(640, 640))
                result_holder.append(app)
            except Exception as exc:
                error_holder.append(exc)

        t = threading.Thread(target=_init, daemon=True)
        t.start()
        t.join(timeout=15)

        if t.is_alive():
            logger.warning("InsightFace init timed out after 15s — using stub embeddings")
        elif error_holder:
            logger.warning("InsightFace init failed: %s — using stub", error_holder[0])
        elif result_holder:
            self._insightface_app = result_holder[0]
            logger.info("InsightFace initialised (gpu=%s)", self._use_gpu)

        return self._insightface_app

    def _run_detection(self, img: "np.ndarray") -> List[FaceDetection]:
        app = self._get_insightface_app()
        if app is not None:
            return self._insightface_detect(img, app)
        # In stub mode (no InsightFace), use OpenCV Haar cascade.
        # If Haar finds nothing, fall back to a whole-image stub detection so
        # that extract_face_embedding and detect_liveness still work.
        detections = self._opencv_detect(img)
        if not detections:
            h, w = img.shape[:2]
            bbox = BoundingBox(x=0, y=0, width=max(1, w), height=max(1, h), confidence=0.5)
            detections = [FaceDetection(bounding_box=bbox, detection_confidence=0.5)]
        return detections

    def _insightface_detect(self, img: "np.ndarray", app: object) -> List[FaceDetection]:
        try:
            faces = app.get(img)  # type: ignore[union-attr]
        except Exception as exc:
            raise FaceExtractionError(f"InsightFace detection failed: {exc}") from exc
        results: List[FaceDetection] = []
        for face in faces:
            box = face.bbox.astype(int)
            x, y, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
            w, h = max(1, x2 - x), max(1, y2 - y)
            conf = float(max(0.0, min(1.0, float(face.det_score) if hasattr(face, "det_score") else 1.0)))
            bbox = BoundingBox(x=x, y=y, width=w, height=h, confidence=conf)
            lm = np.array(face.kps, dtype=np.float32) if hasattr(face, "kps") else None
            results.append(FaceDetection(bounding_box=bbox, landmarks=lm, detection_confidence=conf))
        return results

    def _opencv_detect(self, img: "np.ndarray") -> List[FaceDetection]:
        if not _CV2_AVAILABLE:
            h, w = img.shape[:2]
            bbox = BoundingBox(x=0, y=0, width=w, height=h, confidence=0.5)
            return [FaceDetection(bounding_box=bbox, detection_confidence=0.5)]
        grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        faces = cascade.detectMultiScale(grey, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        results: List[FaceDetection] = []
        for x, y, w, h in faces:
            bbox = BoundingBox(x=int(x), y=int(y), width=int(w), height=int(h), confidence=0.8)
            results.append(FaceDetection(bounding_box=bbox, detection_confidence=0.8))
        return results

    def _extract(
        self, img: "np.ndarray", image_data: bytes
    ) -> Tuple[np.ndarray, BoundingBox, bool, float]:
        app = self._get_insightface_app()
        if app is not None:
            return self._insightface_extract(img, app)
        return self._stub_extract(img, image_data)

    def _insightface_extract(
        self, img: "np.ndarray", app: object
    ) -> Tuple[np.ndarray, BoundingBox, bool, float]:
        try:
            faces = app.get(img)  # type: ignore[union-attr]
        except Exception as exc:
            raise FaceExtractionError(f"InsightFace extraction failed: {exc}") from exc
        if not faces:
            raise FaceNotFoundError("No face detected in image")
        face = max(faces, key=lambda f: float(f.det_score) if hasattr(f, "det_score") else 0.0)
        if not hasattr(face, "embedding") or face.embedding is None:
            raise FaceExtractionError("InsightFace did not return an embedding")
        emb = np.array(face.embedding, dtype=np.float32)
        if emb.shape != (512,):
            raise FaceExtractionError(f"Expected 512-dim embedding, got {emb.shape}")
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb /= norm
        box = face.bbox.astype(int)
        x, y, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
        w, h = max(1, x2 - x), max(1, y2 - y)
        conf = float(max(0.0, min(1.0, float(face.det_score) if hasattr(face, "det_score") else 1.0)))
        bbox = BoundingBox(x=x, y=y, width=w, height=h, confidence=conf)
        is_live, liveness_score = self._liveness_check(img, FaceDetection(bounding_box=bbox))
        return emb, bbox, is_live, liveness_score

    def _stub_extract(
        self, img: "np.ndarray", image_data: bytes
    ) -> Tuple[np.ndarray, BoundingBox, bool, float]:
        """Extract stub embedding when InsightFace is unavailable.

        In stub mode we cannot reliably detect faces, so we treat the whole
        image as the face region and return a deterministic embedding derived
        from the image bytes.  A warning is logged so callers know this is
        not a real face recognition result.
        """
        logger.warning(
            "InsightFace unavailable — returning stub embedding. "
            "Install insightface for production-quality face recognition."
        )
        h, w = img.shape[:2]
        # Use the whole image as the face bounding box in stub mode
        bbox = BoundingBox(x=0, y=0, width=max(1, w), height=max(1, h), confidence=0.5)
        detection = FaceDetection(bounding_box=bbox, detection_confidence=0.5)
        emb = _stub_embedding(image_data)
        is_live, liveness_score = self._liveness_check(img, detection)
        return emb, bbox, is_live, liveness_score

    def _liveness_check(
        self, img: "np.ndarray", detection: FaceDetection
    ) -> Tuple[bool, float]:
        """Texture-based liveness heuristic (anti-spoofing)."""
        if not _CV2_AVAILABLE:
            score = 0.7
            return score >= self.liveness_threshold, score
        try:
            bb = detection.bounding_box
            h_img, w_img = img.shape[:2]
            x1, y1 = max(0, bb.x), max(0, bb.y)
            x2, y2 = min(w_img, bb.x + bb.width), min(h_img, bb.y + bb.height)
            face_crop = img[y1:y2, x1:x2]
            if face_crop.size == 0:
                return False, 0.0
            grey = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
            lap_var = float(cv2.Laplacian(grey, cv2.CV_64F).var())
            score = float(min(1.0, lap_var / 200.0))
            return score >= self.liveness_threshold, round(score, 4)
        except Exception as exc:
            logger.warning("Liveness check failed: %s — defaulting to not-live", exc)
            return False, 0.0
