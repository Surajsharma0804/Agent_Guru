"""
GuruVision Training Dataset Preprocessing Module

This module provides dataset preprocessing functions for training the ArcFace model.
It validates dataset structure, checks minimum image requirements, and preprocesses
images by detecting, aligning, and saving faces.

Requirements: 1.2, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 29.1
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np
import cv2

from guru_vision.detection.detector import FaceDetector
from guru_vision.alignment.aligner import FaceAligner


# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class PreprocessResult:
    """
    Result of dataset preprocessing operation.
    
    Attributes:
        total_images: Total number of images processed
        successful: Number of images successfully processed
        no_face: Number of images with no detectable face
        multiple_faces: Number of images with multiple faces (largest used)
        failed: Number of images that failed to process
        identities_processed: Number of identities processed
        statistics: Per-identity statistics
    """
    total_images: int
    successful: int
    no_face: int
    multiple_faces: int
    failed: int
    identities_processed: int
    statistics: Dict[str, Dict[str, int]]


def validate_dataset_structure(dataset_dir: str) -> Tuple[bool, List[str]]:
    """
    Validate that dataset follows the required structure: dataset/{IdentityName}/*.jpg
    
    Checks that:
    - Dataset directory exists
    - Contains subdirectories (one per identity)
    - Each subdirectory contains image files
    
    Requirements: 2.1, 29.1
    
    Args:
        dataset_dir: Path to the dataset directory
    
    Returns:
        Tuple of (is_valid, error_messages)
        - is_valid: True if structure is valid, False otherwise
        - error_messages: List of validation error messages (empty if valid)
    
    Example:
        >>> is_valid, errors = validate_dataset_structure("dataset")
        >>> if not is_valid:
        ...     for error in errors:
        ...         print(error)
    """
    errors = []
    
    # Check if dataset directory exists
    if not os.path.exists(dataset_dir):
        errors.append(f"Dataset directory does not exist: {dataset_dir}")
        return False, errors
    
    if not os.path.isdir(dataset_dir):
        errors.append(f"Dataset path is not a directory: {dataset_dir}")
        return False, errors
    
    # Get all subdirectories (identity folders)
    try:
        entries = os.listdir(dataset_dir)
    except PermissionError:
        errors.append(f"Permission denied accessing dataset directory: {dataset_dir}")
        return False, errors
    
    identity_dirs = [
        entry for entry in entries
        if os.path.isdir(os.path.join(dataset_dir, entry))
    ]
    
    if not identity_dirs:
        errors.append(
            f"No identity subdirectories found in {dataset_dir}. "
            "Expected structure: dataset/{{IdentityName}}/*.jpg"
        )
        return False, errors
    
    # Validate each identity directory contains images
    supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
    
    for identity_name in identity_dirs:
        identity_path = os.path.join(dataset_dir, identity_name)
        
        try:
            files = os.listdir(identity_path)
        except PermissionError:
            errors.append(f"Permission denied accessing identity directory: {identity_path}")
            continue
        
        # Check for image files
        image_files = [
            f for f in files
            if os.path.isfile(os.path.join(identity_path, f)) and
            os.path.splitext(f.lower())[1] in supported_extensions
        ]
        
        if not image_files:
            errors.append(
                f"No image files found in identity directory: {identity_path}. "
                f"Supported formats: {', '.join(supported_extensions)}"
            )
    
    # Return validation result
    is_valid = len(errors) == 0
    return is_valid, errors


def check_minimum_images(dataset_dir: str, minimum: int = 50) -> Tuple[bool, Dict[str, int]]:
    """
    Validate that each identity has at least the minimum number of images.
    
    Requirements: 2.7, 29.1
    
    Args:
        dataset_dir: Path to the dataset directory
        minimum: Minimum number of images required per identity (default: 50)
    
    Returns:
        Tuple of (all_valid, identity_counts)
        - all_valid: True if all identities meet minimum, False otherwise
        - identity_counts: Dictionary mapping identity names to image counts
    
    Example:
        >>> all_valid, counts = check_minimum_images("dataset", minimum=50)
        >>> for identity, count in counts.items():
        ...     if count < 50:
        ...         print(f"Warning: {identity} has only {count} images")
    """
    identity_counts = {}
    supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
    
    if not os.path.exists(dataset_dir):
        logger.error(f"Dataset directory does not exist: {dataset_dir}")
        return False, identity_counts
    
    # Get all identity directories
    try:
        entries = os.listdir(dataset_dir)
    except PermissionError:
        logger.error(f"Permission denied accessing dataset directory: {dataset_dir}")
        return False, identity_counts
    
    identity_dirs = [
        entry for entry in entries
        if os.path.isdir(os.path.join(dataset_dir, entry))
    ]
    
    # Count images for each identity
    for identity_name in identity_dirs:
        identity_path = os.path.join(dataset_dir, identity_name)
        
        try:
            files = os.listdir(identity_path)
        except PermissionError:
            logger.error(f"Permission denied accessing identity directory: {identity_path}")
            identity_counts[identity_name] = 0
            continue
        
        # Count image files
        image_count = sum(
            1 for f in files
            if os.path.isfile(os.path.join(identity_path, f)) and
            os.path.splitext(f.lower())[1] in supported_extensions
        )
        
        identity_counts[identity_name] = image_count
        
        # Log warning if below minimum
        if image_count < minimum:
            logger.warning(
                f"Identity '{identity_name}' has only {image_count} images "
                f"(minimum recommended: {minimum}). This may result in reduced accuracy."
            )
    
    # Check if all identities meet minimum
    all_valid = all(count >= minimum for count in identity_counts.values())
    
    return all_valid, identity_counts


def preprocess_dataset(
    dataset_dir: str,
    output_dir: str,
    detector: Optional[FaceDetector] = None,
    aligner: Optional[FaceAligner] = None,
    use_gpu: bool = True
) -> PreprocessResult:
    """
    Preprocess dataset by detecting, aligning, and saving faces.
    
    For each image in the dataset:
    1. Load the image
    2. Detect faces using FaceDetector
    3. Handle no-face images: log warning and skip
    4. Handle multiple-face images: extract largest by bounding box area
    5. Align the face using FaceAligner
    6. Save aligned face to output directory
    
    Requirements: 1.2, 2.2, 2.3, 2.4, 2.5, 2.6
    
    Args:
        dataset_dir: Path to input dataset directory (dataset/{IdentityName}/*.jpg)
        output_dir: Path to output directory for aligned faces (aligned_dataset/{IdentityName}/)
        detector: FaceDetector instance (creates new one if None)
        aligner: FaceAligner instance (creates new one if None)
        use_gpu: Whether to use GPU acceleration (default: True)
    
    Returns:
        PreprocessResult with statistics about the preprocessing operation
    
    Raises:
        ValueError: If dataset structure is invalid
        RuntimeError: If preprocessing fails critically
    
    Example:
        >>> result = preprocess_dataset("dataset", "aligned_dataset")
        >>> print(f"Processed {result.successful}/{result.total_images} images")
        >>> print(f"No face: {result.no_face}, Multiple faces: {result.multiple_faces}")
    """
    # Validate dataset structure first
    is_valid, errors = validate_dataset_structure(dataset_dir)
    if not is_valid:
        error_msg = "Invalid dataset structure:\n" + "\n".join(errors)
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Check minimum images and log warnings
    all_valid, identity_counts = check_minimum_images(dataset_dir, minimum=50)
    if not all_valid:
        logger.warning(
            "Some identities have fewer than 50 images. "
            "This may result in reduced recognition accuracy."
        )
    
    # Initialize detector and aligner if not provided
    if detector is None:
        logger.info("Initializing FaceDetector...")
        detector = FaceDetector(use_gpu=use_gpu)
    
    if aligner is None:
        logger.info("Initializing FaceAligner...")
        aligner = FaceAligner(output_size=(112, 112))
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize statistics
    total_images = 0
    successful = 0
    no_face = 0
    multiple_faces = 0
    failed = 0
    per_identity_stats = {}
    
    supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
    
    # Get all identity directories
    identity_dirs = [
        entry for entry in os.listdir(dataset_dir)
        if os.path.isdir(os.path.join(dataset_dir, entry))
    ]
    
    logger.info(f"Starting preprocessing of {len(identity_dirs)} identities...")
    
    # Process each identity
    for identity_name in identity_dirs:
        identity_input_path = os.path.join(dataset_dir, identity_name)
        identity_output_path = os.path.join(output_dir, identity_name)
        
        # Create output directory for this identity
        os.makedirs(identity_output_path, exist_ok=True)
        
        # Initialize per-identity statistics
        identity_stats = {
            'total': 0,
            'successful': 0,
            'no_face': 0,
            'multiple_faces': 0,
            'failed': 0
        }
        
        # Get all image files for this identity
        try:
            files = os.listdir(identity_input_path)
        except PermissionError:
            logger.error(f"Permission denied accessing: {identity_input_path}")
            continue
        
        image_files = [
            f for f in files
            if os.path.isfile(os.path.join(identity_input_path, f)) and
            os.path.splitext(f.lower())[1] in supported_extensions
        ]
        
        logger.info(f"Processing identity '{identity_name}': {len(image_files)} images")
        
        # Process each image
        for image_file in image_files:
            image_path = os.path.join(identity_input_path, image_file)
            total_images += 1
            identity_stats['total'] += 1
            
            try:
                # Load image
                frame = cv2.imread(image_path)
                if frame is None:
                    logger.warning(f"Failed to load image: {image_path}")
                    failed += 1
                    identity_stats['failed'] += 1
                    continue
                
                # Detect faces
                detections = detector.detect(frame, confidence_threshold=0.5)
                
                # Handle no-face images
                if len(detections) == 0:
                    logger.warning(f"No face detected in image: {image_path}")
                    no_face += 1
                    identity_stats['no_face'] += 1
                    continue
                
                # Handle multiple-face images: extract largest by area
                if len(detections) > 1:
                    logger.info(
                        f"Multiple faces detected in {image_path}, "
                        f"using largest face"
                    )
                    multiple_faces += 1
                    identity_stats['multiple_faces'] += 1
                    
                    # Find detection with largest bounding box area
                    largest_detection = max(
                        detections,
                        key=lambda d: d.bbox[2] * d.bbox[3]  # width * height
                    )
                    detection = largest_detection
                else:
                    detection = detections[0]
                
                # Align face
                aligned_face = aligner.align(frame, detection)
                
                # Save aligned face
                output_path = os.path.join(identity_output_path, image_file)
                cv2.imwrite(output_path, aligned_face)
                
                successful += 1
                identity_stats['successful'] += 1
                
            except Exception as e:
                logger.error(f"Error processing {image_path}: {str(e)}")
                failed += 1
                identity_stats['failed'] += 1
                continue
        
        # Store per-identity statistics
        per_identity_stats[identity_name] = identity_stats
        
        logger.info(
            f"Identity '{identity_name}' complete: "
            f"{identity_stats['successful']}/{identity_stats['total']} successful"
        )
    
    # Create preprocessing result
    result = PreprocessResult(
        total_images=total_images,
        successful=successful,
        no_face=no_face,
        multiple_faces=multiple_faces,
        failed=failed,
        identities_processed=len(identity_dirs),
        statistics=per_identity_stats
    )
    
    # Log summary
    logger.info("=" * 60)
    logger.info("Preprocessing Complete")
    logger.info("=" * 60)
    logger.info(f"Total images processed: {total_images}")
    logger.info(f"Successfully aligned: {successful}")
    logger.info(f"No face detected: {no_face}")
    logger.info(f"Multiple faces (largest used): {multiple_faces}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Identities processed: {len(identity_dirs)}")
    logger.info(f"Output directory: {output_dir}")
    logger.info("=" * 60)
    
    return result
