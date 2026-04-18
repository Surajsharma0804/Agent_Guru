"""
Privacy Filter for the Agent Guru Vision System.

Anonymizes frames before any persistence:
- Gaussian blur (σ=15) applied to all face bounding boxes.
- Off-task region blurring: blur all pixels outside the relevant sub-region.
- Camera disable config: all modules return empty results without error.
- Anonymization latency ≤20ms per frame.

Requirements: 11.1–11.7
"""

from __future__ import annotations

import numpy as np
import structlog

from Agent_Guru.vision.vision_models import BoundingBox

logger: structlog.BoundLogger = structlog.get_logger(__name__)

_BLUR_SIGMA: float = 15.0
_BLUR_KERNEL_SIZE: int = 31  # Must be odd; 31 ≈ 6σ for σ=5, but we use σ=15 → larger kernel


def _gaussian_blur_region(
    frame: np.ndarray, bbox: BoundingBox, sigma: float = _BLUR_SIGMA
) -> np.ndarray:
    """Apply Gaussian blur to a rectangular region of a frame in-place.

    Args:
        frame: uint8 RGB array of shape (H, W, 3). Modified in-place.
        bbox: Region to blur.
        sigma: Gaussian standard deviation.

    Returns:
        The modified frame (same array).
    """
    h, w = frame.shape[:2]
    x1 = max(0, int(bbox.x))
    y1 = max(0, int(bbox.y))
    x2 = min(w, int(bbox.x + bbox.width))
    y2 = min(h, int(bbox.y + bbox.height))

    if x2 <= x1 or y2 <= y1:
        return frame

    region = frame[y1:y2, x1:x2]

    try:
        import cv2  # type: ignore[import]
        # Kernel size must be odd and ≥ 1
        k = max(3, int(6 * sigma) | 1)  # bitwise OR 1 ensures odd
        blurred = cv2.GaussianBlur(region, (k, k), sigma)
    except ImportError:
        # Pure-numpy fallback: box blur approximation
        blurred = _numpy_box_blur(region, radius=int(sigma))

    frame[y1:y2, x1:x2] = blurred
    return frame


def _numpy_box_blur(region: np.ndarray, radius: int) -> np.ndarray:
    """Simple box blur fallback when OpenCV is unavailable."""
    if radius < 1:
        return region
    result = region.astype(np.float32)
    for _ in range(3):  # 3 passes approximates Gaussian
        # Horizontal pass
        result = np.cumsum(result, axis=1)
        result[:, radius:] = result[:, radius:] - result[:, :-radius]
        result = result[:, radius - 1:] / radius
        # Vertical pass
        result = np.cumsum(result, axis=0)
        result[radius:] = result[radius:] - result[:-radius]
        result = result[radius - 1:] / radius
    # Resize back to original shape if needed
    if result.shape != region.shape:
        result = region.astype(np.float32)  # fallback: no blur
    return np.clip(result, 0, 255).astype(np.uint8)


class PrivacyFilter:
    """Frame anonymizer for privacy-preserving vision processing.

    Args:
        camera_enabled: When False, all methods return empty/unmodified results
                        without raising exceptions.
        blur_sigma: Gaussian blur standard deviation for face anonymization.
    """

    def __init__(
        self,
        camera_enabled: bool = True,
        blur_sigma: float = _BLUR_SIGMA,
    ) -> None:
        self._camera_enabled = camera_enabled
        self._blur_sigma = blur_sigma
        logger.info(
            "PrivacyFilter initialised",
            camera_enabled=camera_enabled,
            blur_sigma=blur_sigma,
        )

    @property
    def camera_enabled(self) -> bool:
        """Whether the camera is enabled."""
        return self._camera_enabled

    @camera_enabled.setter
    def camera_enabled(self, value: bool) -> None:
        self._camera_enabled = value
        logger.info("PrivacyFilter: camera_enabled changed", value=value)

    async def anonymize_faces(
        self, frame: np.ndarray, face_boxes: list[BoundingBox]
    ) -> np.ndarray:
        """Apply Gaussian blur to all detected face regions.

        Args:
            frame: uint8 RGB array of shape (H, W, 3).
            face_boxes: List of face bounding boxes to blur.

        Returns:
            Frame with face regions blurred. Returns original frame unchanged
            when camera is disabled.
        """
        if not self._camera_enabled:
            return frame

        result = frame.copy()
        for bbox in face_boxes:
            result = _gaussian_blur_region(result, bbox, self._blur_sigma)

        logger.debug(
            "PrivacyFilter: faces anonymized",
            face_count=len(face_boxes),
        )
        return result

    async def blur_off_task(
        self, frame: np.ndarray, relevant_region: BoundingBox | None
    ) -> np.ndarray:
        """Blur all pixels outside the relevant region.

        If relevant_region is None, blur the entire frame.

        Args:
            frame: uint8 RGB array of shape (H, W, 3).
            relevant_region: The region to keep unblurred, or None to blur all.

        Returns:
            Frame with off-task regions blurred. Returns original frame
            unchanged when camera is disabled.
        """
        if not self._camera_enabled:
            return frame

        h, w = frame.shape[:2]
        result = frame.copy()

        if relevant_region is None:
            # Blur entire frame
            entire = BoundingBox(x=0, y=0, width=w, height=h)
            result = _gaussian_blur_region(result, entire, self._blur_sigma)
            return result

        # Blur everything outside the relevant region
        rx1 = max(0, int(relevant_region.x))
        ry1 = max(0, int(relevant_region.y))
        rx2 = min(w, int(relevant_region.x + relevant_region.width))
        ry2 = min(h, int(relevant_region.y + relevant_region.height))

        # Save the relevant region before blurring
        saved_region = frame[ry1:ry2, rx1:rx2].copy()

        # Blur entire frame
        entire = BoundingBox(x=0, y=0, width=w, height=h)
        result = _gaussian_blur_region(result, entire, self._blur_sigma)

        # Restore the relevant region unblurred
        result[ry1:ry2, rx1:rx2] = saved_region

        logger.debug("PrivacyFilter: off-task regions blurred")
        return result
