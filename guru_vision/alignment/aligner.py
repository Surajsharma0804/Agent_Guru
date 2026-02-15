"""
GuruVision Face Alignment Module

This module provides face alignment functionality using landmark-based
similarity transforms to normalize face orientation and scale.

Requirements: 4.1, 4.2, 4.3, 4.4, 26.5
"""

from typing import Tuple
import numpy as np
import cv2
from dataclasses import dataclass


# Standard face template for 112x112 output
# These are the target positions for the 5 facial landmarks
# Based on standard face alignment templates used in face recognition
ARCFACE_SRC = np.array([
    [38.2946, 51.6963],  # left eye
    [73.5318, 51.5014],  # right eye
    [56.0252, 71.7366],  # nose tip
    [41.5493, 92.3655],  # left mouth corner
    [70.7299, 92.2041]   # right mouth corner
], dtype=np.float32)


class FaceAligner:
    """
    Face alignment using landmark-based similarity transforms.
    
    This class normalizes face orientation and scale by aligning facial landmarks
    to a standard template, ensuring consistent input for the recognition model.
    
    Attributes:
        output_size: Target output dimensions (width, height) for aligned faces
        src_landmarks: Standard face template landmarks for alignment
    """
    
    def __init__(self, output_size: Tuple[int, int] = (112, 112)):
        """
        Initialize the face aligner.
        
        Args:
            output_size: Target output dimensions (width, height). Default is (112, 112)
                        which is the standard input size for ArcFace models.
        
        Requirements: 4.2, 26.5
        """
        self.output_size = output_size
        
        # Scale the standard template if output size differs from 112x112
        if output_size != (112, 112):
            scale_x = output_size[0] / 112.0
            scale_y = output_size[1] / 112.0
            self.src_landmarks = ARCFACE_SRC.copy()
            self.src_landmarks[:, 0] *= scale_x
            self.src_landmarks[:, 1] *= scale_y
        else:
            self.src_landmarks = ARCFACE_SRC
    
    def align(self, frame: np.ndarray, detection) -> np.ndarray:
        """
        Align a detected face using its landmarks.
        
        This method:
        1. Extracts landmarks from the detection
        2. Computes a similarity transform to the standard face template
        3. Applies the affine transformation to normalize the face
        4. Resizes to the target output size (112x112)
        
        Args:
            frame: Input image containing the face (BGR format from OpenCV)
            detection: Detection object with bbox, landmarks, and confidence
        
        Returns:
            Aligned face image of size (output_size[1], output_size[0], 3)
        
        Raises:
            ValueError: If landmarks are invalid or transformation fails
        
        Requirements: 4.1, 4.3, 4.4
        """
        # Extract landmarks from detection
        # Landmarks should be (5, 2) array with x, y coordinates
        landmarks = detection.landmarks
        
        if landmarks is None or landmarks.shape != (5, 2):
            raise ValueError(
                f"Invalid landmarks shape. Expected (5, 2), got {landmarks.shape if landmarks is not None else None}"
            )
        
        # Ensure landmarks are float32 for cv2.estimateAffinePartial2D
        dst_landmarks = landmarks.astype(np.float32)
        
        # Compute similarity transform from detected landmarks to standard template
        # estimateAffinePartial2D computes a 2x3 affine transformation matrix
        # that maps dst_landmarks to src_landmarks using similarity transform
        # (rotation, scale, translation - no shear)
        transform_matrix, inliers = cv2.estimateAffinePartial2D(
            dst_landmarks,
            self.src_landmarks,
            method=cv2.RANSAC,
            ransacReprojThreshold=5.0
        )
        
        if transform_matrix is None:
            raise ValueError(
                "Failed to compute alignment transformation. "
                "Landmarks may be too noisy or face pose too extreme."
            )
        
        # Apply affine transformation to align the face
        # This warps the image so that the facial landmarks align with the standard template
        aligned_face = cv2.warpAffine(
            frame,
            transform_matrix,
            self.output_size,
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0
        )
        
        return aligned_face
