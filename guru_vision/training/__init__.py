"""
GuruVision Training Module

This module provides dataset preprocessing and model training functionality.

Available functions:
- validate_dataset_structure: Validate dataset organization
- check_minimum_images: Check minimum image requirements
- preprocess_dataset: Preprocess dataset for training

Example:
    >>> from guru_vision.training.preprocess import preprocess_dataset
    >>> result = preprocess_dataset("dataset", "aligned_dataset")
    >>> print(f"Processed: {result.successful}/{result.total_images}")
"""

from guru_vision.training.preprocess import (
    validate_dataset_structure,
    check_minimum_images,
    preprocess_dataset,
    PreprocessResult
)

__all__ = [
    'validate_dataset_structure',
    'check_minimum_images',
    'preprocess_dataset',
    'PreprocessResult'
]
