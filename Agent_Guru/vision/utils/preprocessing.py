"""Module: Agent_Guru.vision.utils.preprocessing
Purpose: Image preprocessing utilities for the GuruVision pipeline.

Provides low-light enhancement via CLAHE (Contrast Limited Adaptive
Histogram Equalisation).  When the mean brightness of a frame falls below
the configured threshold the image is enhanced before further processing,
improving face detection and recognition accuracy in dark environments.

Requirements: 22.1, 22.2, 22.3, 22.4, 22.5
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("guruvision.preprocessing")

# Mean pixel brightness (0-255) below which enhancement is triggered.
LOW_LIGHT_THRESHOLD: int = 50

# CLAHE clip limit — controls contrast amplification.
_CLAHE_CLIP_LIMIT: float = 2.0

# CLAHE tile grid size.
_CLAHE_TILE_GRID: tuple[int, int] = (8, 8)


def is_low_light(frame: np.ndarray) -> bool:
    """Return True if the frame mean brightness is below the threshold.

    Args:
        frame: BGR image, dtype uint8, any spatial size.

    Returns:
        True when mean pixel value < LOW_LIGHT_THRESHOLD.

    """
    mean_brightness = float(np.mean(frame))
    return mean_brightness < LOW_LIGHT_THRESHOLD


def enhance_low_light(frame: np.ndarray) -> np.ndarray:
    """Apply CLAHE-based low-light enhancement to a BGR frame.

    The function converts the image to the LAB colour space, applies CLAHE
    only to the L (luminance) channel, then converts back to BGR.  This
    preserves colour balance while boosting local contrast.

    When OpenCV is not available the function falls back to a pure-NumPy
    global histogram equalisation on the luminance channel.

    Args:
        frame: BGR image, dtype uint8, any spatial size.

    Returns:
        Enhanced BGR image with the same shape and dtype as the input.
        If the frame is already well-lit (mean >= LOW_LIGHT_THRESHOLD) the
        original array is returned unchanged.

    """
    if not is_low_light(frame):
        return frame

    logger.debug(
        "Low-light frame detected (mean=%.1f) — applying CLAHE enhancement",
        float(np.mean(frame)),
    )

    try:
        import cv2  # type: ignore[import]

        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(
            clipLimit=_CLAHE_CLIP_LIMIT,
            tileGridSize=_CLAHE_TILE_GRID,
        )
        l_enhanced = clahe.apply(l_channel)
        lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
        return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

    except ImportError:
        logger.exception("cv2 not available — falling back to numpy histogram equalisation")
        return _numpy_equalize(frame)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _numpy_equalize(frame: np.ndarray) -> np.ndarray:
    """Global histogram equalisation on the luminance channel (numpy fallback).

    Converts BGR → YCbCr, equalises Y, converts back.  Less adaptive than
    CLAHE but requires no external dependencies.

    Args:
        frame: BGR uint8 image.

    Returns:
        Equalised BGR uint8 image.

    """
    # Approximate YCbCr conversion (BT.601)
    r = frame[:, :, 2].astype(np.float32)
    g = frame[:, :, 1].astype(np.float32)
    b = frame[:, :, 0].astype(np.float32)

    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = -0.168736 * r - 0.331264 * g + 0.5 * b + 128.0
    cr = 0.5 * r - 0.418688 * g - 0.081312 * b + 128.0

    # Histogram equalisation on Y channel
    y_uint8 = np.clip(y, 0, 255).astype(np.uint8)
    hist, _ = np.histogram(y_uint8.ravel(), bins=256, range=(0, 256))
    cdf = hist.cumsum()
    cdf_min = int(cdf[cdf > 0][0])
    total_pixels = y_uint8.size
    denom = total_pixels - cdf_min
    if denom == 0:
        return frame.copy()
    lut = np.round((cdf - cdf_min) / denom * 255).astype(np.uint8)
    y_eq = lut[y_uint8].astype(np.float32)

    # Convert back to BGR
    r_out = np.clip(y_eq + 1.402 * (cr - 128.0), 0, 255).astype(np.uint8)
    g_out = np.clip(y_eq - 0.344136 * (cb - 128.0) - 0.714136 * (cr - 128.0), 0, 255).astype(
        np.uint8,
    )
    b_out = np.clip(y_eq + 1.772 * (cb - 128.0), 0, 255).astype(np.uint8)

    return np.stack([b_out, g_out, r_out], axis=2)
