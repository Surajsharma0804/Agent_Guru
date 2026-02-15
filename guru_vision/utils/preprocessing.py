"""
Preprocessing utilities for GuruVision facial recognition system.

This module provides image preprocessing functions including low-light enhancement
to improve recognition accuracy in challenging lighting conditions.
"""

import cv2
import numpy as np
from typing import Tuple, Optional


def _log_debug(message: str):
    """Simple debug logging without importing logging module."""
    # Avoid importing logging to prevent conflicts with local logging.py
    pass


def _log_warning(message: str):
    """Simple warning logging without importing logging module."""
    # Avoid importing logging to prevent conflicts with local logging.py
    pass


def _log_error(message: str):
    """Simple error logging without importing logging module."""
    # Avoid importing logging to prevent conflicts with local logging.py
    pass


def _log_info(message: str):
    """Simple info logging without importing logging module."""
    # Avoid importing logging to prevent conflicts with local logging.py
    pass


def enhance_low_light(
    frame: np.ndarray,
    brightness_threshold: float = 50.0,
    clip_limit: float = 2.0,
    tile_grid_size: Tuple[int, int] = (8, 8)
) -> Tuple[np.ndarray, bool]:
    """
    Enhance low-light images using CLAHE (Contrast Limited Adaptive Histogram Equalization).
    
    This function checks if the input frame has low brightness (mean pixel value < threshold)
    and applies adaptive histogram equalization to improve face visibility while preserving
    facial features without introducing artifacts.
    
    Args:
        frame: Input image in BGR format (OpenCV standard)
        brightness_threshold: Mean brightness threshold below which enhancement is applied (default: 50.0)
        clip_limit: Threshold for contrast limiting in CLAHE (default: 2.0)
        tile_grid_size: Size of grid for histogram equalization (default: (8, 8))
    
    Returns:
        Tuple of (enhanced_frame, was_enhanced):
            - enhanced_frame: Enhanced image if brightness was low, otherwise original frame
            - was_enhanced: Boolean indicating whether enhancement was applied
    
    Requirements:
        - 22.1: Apply enhancement when mean pixel value < 50
        - 22.2: Use adaptive histogram equalization (CLAHE)
        - 22.3: Preserve facial features without artifacts
        - 22.4: Complete within 50ms per frame
        - 22.5: Skip enhancement when lighting is adequate
    
    Example:
        >>> frame = cv2.imread('dark_image.jpg')
        >>> enhanced, was_enhanced = enhance_low_light(frame)
        >>> if was_enhanced:
        ...     print("Low-light enhancement was applied")
    """
    if frame is None or frame.size == 0:
        _log_warning("Empty or invalid frame provided to enhance_low_light")
        return frame, False
    
    # Check mean brightness threshold (Requirement 22.1)
    # Convert to grayscale for brightness calculation
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    
    mean_brightness = np.mean(gray)
    
    # Skip enhancement if lighting is adequate (Requirement 22.5)
    if mean_brightness >= brightness_threshold:
        return frame, False
    
    _log_debug(f"Low brightness detected (mean={mean_brightness:.2f}), applying enhancement")
    
    # Apply CLAHE for adaptive histogram equalization (Requirement 22.2)
    # CLAHE preserves facial features better than global histogram equalization (Requirement 22.3)
    try:
        if len(frame.shape) == 3:
            # For color images, convert to LAB color space
            # Apply CLAHE only to L channel to preserve color information
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            
            # Create CLAHE object
            clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
            
            # Apply CLAHE to L channel
            l_channel_enhanced = clahe.apply(l_channel)
            
            # Merge channels back
            lab_enhanced = cv2.merge([l_channel_enhanced, a_channel, b_channel])
            
            # Convert back to BGR
            enhanced_frame = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
        else:
            # For grayscale images, apply CLAHE directly
            clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
            enhanced_frame = clahe.apply(gray)
        
        return enhanced_frame, True
        
    except Exception as e:
        _log_error(f"Error during low-light enhancement: {e}")
        return frame, False


def check_brightness(frame: np.ndarray) -> float:
    """
    Calculate the mean brightness of a frame.
    
    Args:
        frame: Input image in BGR or grayscale format
    
    Returns:
        Mean brightness value (0-255)
    
    Example:
        >>> frame = cv2.imread('image.jpg')
        >>> brightness = check_brightness(frame)
        >>> print(f"Mean brightness: {brightness:.2f}")
    """
    if frame is None or frame.size == 0:
        return 0.0
    
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    
    return float(np.mean(gray))


def preprocess_frame(
    frame: np.ndarray,
    enable_low_light_enhancement: bool = True,
    brightness_threshold: float = 50.0
) -> Tuple[np.ndarray, dict]:
    """
    Apply all preprocessing steps to a frame.
    
    This is a convenience function that applies all enabled preprocessing
    operations and returns metadata about what was applied.
    
    Args:
        frame: Input image in BGR format
        enable_low_light_enhancement: Whether to apply low-light enhancement
        brightness_threshold: Brightness threshold for enhancement
    
    Returns:
        Tuple of (processed_frame, metadata):
            - processed_frame: Preprocessed image
            - metadata: Dictionary with preprocessing information
    
    Example:
        >>> frame = cv2.imread('image.jpg')
        >>> processed, info = preprocess_frame(frame)
        >>> if info['low_light_enhanced']:
        ...     print(f"Enhanced from brightness {info['original_brightness']:.2f}")
    """
    metadata = {
        'low_light_enhanced': False,
        'original_brightness': check_brightness(frame)
    }
    
    processed_frame = frame.copy()
    
    # Apply low-light enhancement if enabled
    if enable_low_light_enhancement:
        processed_frame, was_enhanced = enhance_low_light(
            processed_frame,
            brightness_threshold=brightness_threshold
        )
        metadata['low_light_enhanced'] = was_enhanced
        
        if was_enhanced:
            metadata['enhanced_brightness'] = check_brightness(processed_frame)
            _log_info(
                f"Low-light enhancement applied: "
                f"{metadata['original_brightness']:.2f} -> {metadata['enhanced_brightness']:.2f}"
            )
    
    return processed_frame, metadata
