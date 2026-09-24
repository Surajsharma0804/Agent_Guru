"""Face alignment and normalization module.

Aligns detected faces to a standard 112x112 ArcFace template using
landmark-based similarity transforms (or bbox crop as fallback).

Performance target: <10ms per face on CPU.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 26.5**
"""

from __future__ import annotations

import logging
import warnings
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from Agent_Guru.vision.detection.detector import Detection

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

# ---------------------------------------------------------------------------
# ArcFace standard 5-point face template for 112x112 output
# Based on InsightFace / ArcFace standard alignment template.
# Points: left_eye, right_eye, nose, left_mouth, right_mouth
# ---------------------------------------------------------------------------

ARCFACE_TEMPLATE = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


# ---------------------------------------------------------------------------
# FaceAligner
# ---------------------------------------------------------------------------


class FaceAligner:
    """Align and normalize detected faces to a standard 112x112 image.

    When a :class:`~Agent_Guru.vision.detection.detector.Detection` includes
    5-point landmarks the aligner computes a similarity (partial affine)
    transform that maps the detected landmarks to the ArcFace standard
    template and applies it with ``cv2.warpAffine``.

    When landmarks are absent (e.g. OpenCV Haar cascade fallback) the aligner
    falls back to cropping the bounding-box region and resizing it to
    ``output_size``.

    The output is **always** an array of shape ``(H, W, 3)`` with dtype
    ``uint8``, where ``(H, W) == output_size``.  Edge cases are handled
    gracefully:

    - Bounding boxes that extend outside the frame are clamped before
      cropping.
    - Empty crops (zero area after clamping) return a black image.

    Args:
        output_size: Target ``(height, width)`` of the aligned face image.
            Defaults to ``(112, 112)`` - the ArcFace standard.

    Example::

        aligner = FaceAligner()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detection = Detection(bbox=(100, 80, 120, 140), landmarks=None, confidence=0.9)
        aligned = aligner.align(frame, detection)
        assert aligned.shape == (112, 112, 3)

    """

    def __init__(self, output_size: tuple[int, int] = (112, 112)) -> None:
        if len(output_size) != 2 or output_size[0] <= 0 or output_size[1] <= 0:
            msg = f"output_size must be a tuple of two positive integers, got {output_size}"
            raise ValueError(
                msg,
            )
        self.output_size = output_size  # (height, width)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def align(self, frame: np.ndarray, detection: Detection) -> np.ndarray:
        """Align a detected face and return a normalized face image.

        Args:
            frame: BGR image as a NumPy array of shape ``(H, W, 3)`` and
                dtype ``uint8``.
            detection: A :class:`~Agent_Guru.vision.detection.detector.Detection`
                object containing the bounding box and optional landmarks.

        Returns:
            Aligned face image of shape ``(output_size[0], output_size[1], 3)``
            with dtype ``uint8``.  Returns a black image on failure rather
            than raising.

        Raises:
            ValueError: If *frame* is not a valid 3-channel NumPy array.

        """
        if not isinstance(frame, np.ndarray):
            msg = "frame must be a numpy ndarray"
            raise ValueError(msg)
        if frame.ndim != 3 or frame.shape[2] != 3:
            msg = f"frame must have shape (H, W, 3), got {frame.shape}"
            raise ValueError(msg)

        _h_out, _w_out = self.output_size

        # ------------------------------------------------------------------
        # Path 1: landmark-based similarity transform
        # ------------------------------------------------------------------
        if detection.landmarks is not None:
            aligned = self._align_with_landmarks(frame, detection.landmarks)
            if aligned is not None:
                return aligned
            # Fall through to bbox crop on failure
            logger.debug("Landmark-based alignment failed; falling back to bbox crop.")

        # ------------------------------------------------------------------
        # Path 2: bbox crop + resize fallback
        # ------------------------------------------------------------------
        return self._align_with_bbox(frame, detection.bbox)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _align_with_landmarks(self, frame: np.ndarray, landmarks: np.ndarray) -> np.ndarray | None:
        """Compute similarity transform from landmarks and warp the frame.

        Args:
            frame: Source BGR image.
            landmarks: Array of shape ``(5, 2)`` with detected keypoint
                coordinates in ``(x, y)`` order.

        Returns:
            Warped face image of shape ``(H, W, 3)`` or ``None`` on failure.

        """
        if not _CV2_AVAILABLE:
            logger.warning("cv2 not available - cannot perform landmark-based alignment.")
            return None

        try:
            lm = np.array(landmarks, dtype=np.float32)
            if lm.shape != (5, 2):
                logger.warning("Unexpected landmarks shape %s; expected (5, 2).", lm.shape)
                return None

            # Scale the template to the requested output size
            template = self._scaled_template()

            # Estimate partial affine (similarity) transform: rotation, scale,
            # translation - no shear.
            transform_matrix, _ = cv2.estimateAffinePartial2D(lm, template, method=cv2.LMEDS)

            if transform_matrix is None:
                logger.debug("estimateAffinePartial2D returned None.")
                return None

            h_out, w_out = self.output_size
            warped = cv2.warpAffine(
                frame,
                transform_matrix,
                (w_out, h_out),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0),
            )
            return warped.astype(np.uint8)

        except Exception:
            logger.exception("Landmark alignment error")
            return None

    def _align_with_bbox(self, frame: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
        """Crop the bounding-box region and resize to output_size.

        Handles out-of-bounds bboxes by clamping to the frame dimensions.
        Returns a black image if the clamped crop has zero area.

        Args:
            frame: Source BGR image.
            bbox: Bounding box as ``(x, y, w, h)`` in pixel coordinates.

        Returns:
            Cropped and resized face image of shape ``(H, W, 3)``.

        """
        h_out, w_out = self.output_size
        frame_h, frame_w = frame.shape[:2]

        x, y, bw, bh = bbox

        # Clamp to frame bounds
        x1 = max(0, int(x))
        y1 = max(0, int(y))
        x2 = min(frame_w, int(x) + int(bw))
        y2 = min(frame_h, int(y) + int(bh))

        if x2 <= x1 or y2 <= y1:
            # Empty crop - return black image
            logger.debug(
                "Bbox %s results in empty crop after clamping to frame %dx%d; "
                "returning black image.",
                bbox,
                frame_w,
                frame_h,
            )
            return np.zeros((h_out, w_out, 3), dtype=np.uint8)

        crop = frame[y1:y2, x1:x2]

        if _CV2_AVAILABLE:
            resized = cv2.resize(crop, (w_out, h_out), interpolation=cv2.INTER_LINEAR)
        else:
            # Minimal fallback using numpy (nearest-neighbour)
            resized = self._numpy_resize(crop, h_out, w_out)

        return resized.astype(np.uint8)

    def _scaled_template(self) -> np.ndarray:
        """Return ARCFACE_TEMPLATE scaled to the current output_size.

        The canonical template is defined for 112x112.  When a different
        output size is requested the template is scaled proportionally.

        Returns:
            Scaled template array of shape ``(5, 2)``.

        """
        h_out, w_out = self.output_size
        scale_x = w_out / 112.0
        scale_y = h_out / 112.0
        scaled = ARCFACE_TEMPLATE.copy()
        scaled[:, 0] *= scale_x
        scaled[:, 1] *= scale_y
        return scaled

    @staticmethod
    def _numpy_resize(image: np.ndarray, h: int, w: int) -> np.ndarray:
        """Nearest-neighbour resize using only NumPy (cv2 fallback).

        Args:
            image: Source image array of shape ``(H_src, W_src, C)``.
            h: Target height.
            w: Target width.

        Returns:
            Resized image of shape ``(h, w, C)``.

        """
        src_h, src_w = image.shape[:2]
        row_idx = (np.arange(h) * src_h / h).astype(int)
        col_idx = (np.arange(w) * src_w / w).astype(int)
        return image[np.ix_(row_idx, col_idx)]
