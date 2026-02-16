"""
OCR Preprocessing Utilities

Provides image preprocessing for better OCR accuracy.
"""

import numpy as np
import cv2
from typing import Tuple


def denoise_image(image: np.ndarray, strength: int = 10) -> np.ndarray:
    """
    Remove noise from image using Non-local Means Denoising.
    
    Args:
        image: Input image
        strength: Denoising strength (higher = more denoising)
    
    Returns:
        Denoised image
    """
    if image is None or image.size == 0:
        return image
    
    if len(image.shape) == 3:
        return cv2.fastNlMeansDenoisingColored(image, None, strength, strength, 7, 21)
    else:
        return cv2.fastNlMeansDenoising(image, None, strength, 7, 21)


def enhance_contrast(image: np.ndarray) -> np.ndarray:
    """
    Enhance image contrast using CLAHE.
    
    Args:
        image: Input image
    
    Returns:
        Contrast-enhanced image
    """
    if image is None or image.size == 0:
        return image
    
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Apply CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Convert back to color if needed
    if len(image.shape) == 3:
        return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
    return enhanced


def correct_skew(image: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Detect and correct image skew.
    
    Args:
        image: Input image
    
    Returns:
        Tuple of (corrected image, skew angle in degrees)
    """
    if image is None or image.size == 0:
        return image, 0.0
    
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Detect edges
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # Detect lines using Hough transform
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)
    
    if lines is None or len(lines) == 0:
        return image, 0.0
    
    # Calculate average angle
    angles = []
    for line in lines:
        rho, theta = line[0]
        angle = np.degrees(theta) - 90
        if -45 < angle < 45:  # Only consider reasonable angles
            angles.append(angle)
    
    if not angles:
        return image, 0.0
    
    skew_angle = float(np.median(angles))
    
    # Rotate image to correct skew
    if abs(skew_angle) > 0.5:  # Only correct if significant
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
        corrected = cv2.warpAffine(image, rotation_matrix, (w, h),
                                   flags=cv2.INTER_CUBIC,
                                   borderMode=cv2.BORDER_REPLICATE)
        return corrected, skew_angle
    
    return image, skew_angle


def binarize_image(image: np.ndarray, method: str = 'otsu') -> np.ndarray:
    """
    Convert image to binary (black and white).
    
    Args:
        image: Input image
        method: Binarization method ('otsu' or 'adaptive')
    
    Returns:
        Binary image
    """
    if image is None or image.size == 0:
        return image
    
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    if method == 'otsu':
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif method == 'adaptive':
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
    else:
        raise ValueError(f"Unknown binarization method: {method}")
    
    return binary


def preprocess_for_ocr(image: np.ndarray,
                       denoise: bool = True,
                       enhance: bool = True,
                       correct_skew_flag: bool = True,
                       binarize: bool = False) -> np.ndarray:
    """
    Apply full preprocessing pipeline for OCR.
    
    Args:
        image: Input image
        denoise: Whether to apply denoising
        enhance: Whether to enhance contrast
        correct_skew_flag: Whether to correct skew
        binarize: Whether to binarize image
    
    Returns:
        Preprocessed image
    """
    if image is None or image.size == 0:
        return image
    
    result = image.copy()
    
    if denoise:
        result = denoise_image(result)
    
    if enhance:
        result = enhance_contrast(result)
    
    if correct_skew_flag:
        result, _ = correct_skew(result)
    
    if binarize:
        result = binarize_image(result)
    
    return result
