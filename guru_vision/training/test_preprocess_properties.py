"""
Property-Based Tests for Dataset Preprocessing Module

This module contains property-based tests using Hypothesis to validate
universal correctness properties of the dataset preprocessing operations.

Properties tested:
- Property 1: Dataset Preprocessing Completeness
- Property 26: Minimum Dataset Size Validation
- Property 28: Multiple Face Selection
- Property 29: No-Face Image Handling
- Property 30: Dataset Structure Acceptance
"""

import pytest
import numpy as np
import tempfile
import os
import shutil
import cv2
from pathlib import Path
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from unittest.mock import patch, MagicMock

from guru_vision.training.preprocess import (
    validate_dataset_structure,
    check_minimum_images,
    preprocess_dataset,
    PreprocessResult
)
from guru_vision.detection.detector import Detection


# Custom strategies for generating test data

@st.composite
def valid_identity_name(draw):
    """Generate a valid identity name."""
    # Use simple alphanumeric characters for identity names
    return draw(st.text(
        alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
        min_size=1,
        max_size=20
    ))


@st.composite
def image_count(draw):
    """Generate a valid image count."""
    return draw(st.integers(min_value=1, max_value=100))


@st.composite
def dataset_structure(draw):
    """Generate a dataset structure with identities and image counts."""
    num_identities = draw(st.integers(min_value=1, max_value=5))
    identities = {}
    for _ in range(num_identities):
        name = draw(valid_identity_name())
        count = draw(image_count())
        identities[name] = count
    return identities


def create_test_image(width=640, height=480, has_face=True, num_faces=1):
    """
    Create a test image with optional face-like patterns.
    
    Args:
        width: Image width
        height: Image height
        has_face: Whether to include a face pattern
        num_faces: Number of faces to include (if has_face=True)
    
    Returns:
        numpy array representing the image
    """
    # Create a blank image
    img = np.ones((height, width, 3), dtype=np.uint8) * 200
    
    if has_face:
        # Calculate positions for multiple faces
        face_positions = []
        if num_faces == 1:
            face_positions = [(width // 2, height // 2)]
        elif num_faces == 2:
            face_positions = [(width // 3, height // 2), (2 * width // 3, height // 2)]
        elif num_faces >= 3:
            # Arrange in a grid
            cols = int(np.ceil(np.sqrt(num_faces)))
            rows = int(np.ceil(num_faces / cols))
            for i in range(num_faces):
                row = i // cols
                col = i % cols
                x = (col + 1) * width // (cols + 1)
                y = (row + 1) * height // (rows + 1)
                face_positions.append((x, y))
        
        # Draw faces at each position
        for center_x, center_y in face_positions:
            # Face oval
            cv2.ellipse(img, (center_x, center_y), (80, 100), 0, 0, 360, (180, 150, 120), -1)
            
            # Eyes
            cv2.circle(img, (center_x - 25, center_y - 15), 8, (50, 50, 50), -1)
            cv2.circle(img, (center_x + 25, center_y - 15), 8, (50, 50, 50), -1)
            
            # Mouth
            cv2.ellipse(img, (center_x, center_y + 25), (25, 12), 0, 0, 180, (100, 50, 50), 2)
    
    return img


def create_mock_detector_with_behavior(has_face=True, num_faces=1):
    """
    Create a mock detector that returns specific detection behavior.
    
    Args:
        has_face: Whether to detect faces
        num_faces: Number of faces to detect
    
    Returns:
        Mock FaceDetector
    """
    mock_detector = MagicMock()
    
    if not has_face:
        # No faces detected
        mock_detector.detect.return_value = []
    else:
        # Create detections
        detections = []
        for i in range(num_faces):
            # Create detection with different sizes
            size = 100 - (i * 10)  # Largest first
            detection = Detection(
                bbox=(100 + i * 150, 100, size, size),
                landmarks=np.array([[150, 150], [200, 150], [175, 175], [160, 200], [190, 200]]),
                confidence=0.9 - (i * 0.1)
            )
            detections.append(detection)
        mock_detector.detect.return_value = detections
    
    return mock_detector


def create_mock_aligner():
    """Create a mock aligner that returns 112x112 aligned faces."""
    mock_aligner = MagicMock()
    
    def mock_align(frame, detection):
        # Return a 112x112 aligned face
        return np.ones((112, 112, 3), dtype=np.uint8) * 128
    
    mock_aligner.align = mock_align
    return mock_aligner


# Property 30: Dataset Structure Acceptance
# **Validates: Requirements 2.1**

@given(structure=dataset_structure())
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_30_dataset_structure_acceptance(structure):
    """
    Property 30: Dataset Structure Acceptance
    
    For any dataset organized in the structure dataset/{IdentityName}/{image_files},
    the system should successfully load and process the dataset.
    
    **Validates: Requirements 2.1**
    """
    # Create temporary dataset directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create dataset structure
        for identity_name, image_count in structure.items():
            identity_dir = os.path.join(temp_dir, identity_name)
            os.makedirs(identity_dir, exist_ok=True)
            
            # Create image files
            for i in range(image_count):
                img_path = os.path.join(identity_dir, f"image_{i}.jpg")
                img = create_test_image()
                cv2.imwrite(img_path, img)
        
        # Validate dataset structure
        is_valid, errors = validate_dataset_structure(temp_dir)
        
        # Property: Valid structure should be accepted
        assert is_valid is True, \
            f"Dataset with structure {list(structure.keys())} should be valid, got errors: {errors}"
        assert len(errors) == 0, \
            f"Valid dataset should have no errors, got: {errors}"
        
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


# Property 26: Minimum Dataset Size Validation
# **Validates: Requirements 29.1**

@given(
    identity_name=valid_identity_name(),
    image_count=st.integers(min_value=1, max_value=100),
    minimum=st.integers(min_value=10, max_value=60)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_26_minimum_dataset_size_validation(identity_name, image_count, minimum):
    """
    Property 26: Minimum Dataset Size Validation
    
    For any training dataset where an identity has fewer than the minimum images,
    the system should issue a warning about potential accuracy degradation.
    
    **Validates: Requirements 29.1**
    """
    # Create temporary dataset directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create identity directory with specific image count
        identity_dir = os.path.join(temp_dir, identity_name)
        os.makedirs(identity_dir, exist_ok=True)
        
        # Create image files
        for i in range(image_count):
            img_path = os.path.join(identity_dir, f"image_{i}.jpg")
            img = create_test_image()
            cv2.imwrite(img_path, img)
        
        # Check minimum images with logging
        import logging
        with patch.object(logging.getLogger('guru_vision.training.preprocess'), 'warning') as mock_warning:
            all_valid, counts = check_minimum_images(temp_dir, minimum=minimum)
            
            # Property: Validation result should match image count vs minimum
            if image_count < minimum:
                assert all_valid is False, \
                    f"Should return False when image count {image_count} < minimum {minimum}"
                # Should have logged a warning
                assert mock_warning.called, \
                    f"Should log warning when image count {image_count} < minimum {minimum}"
                warning_message = str(mock_warning.call_args)
                assert identity_name in warning_message, \
                    f"Warning should mention identity name '{identity_name}'"
                assert str(image_count) in warning_message, \
                    f"Warning should mention image count {image_count}"
            else:
                assert all_valid is True, \
                    f"Should return True when image count {image_count} >= minimum {minimum}"
            
            # Verify counts are correct
            assert counts[identity_name] == image_count, \
                f"Should report correct image count: expected {image_count}, got {counts[identity_name]}"
    
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


# Property 1: Dataset Preprocessing Completeness
# **Validates: Requirements 1.2**

@given(
    num_identities=st.integers(min_value=1, max_value=3),
    images_per_identity=st.integers(min_value=2, max_value=5)
)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_1_dataset_preprocessing_completeness(num_identities, images_per_identity):
    """
    Property 1: Dataset Preprocessing Completeness
    
    For any dataset directory with valid images, when preprocessing is executed,
    all images with detectable faces should be processed through detection and
    alignment before training begins.
    
    **Validates: Requirements 1.2**
    """
    # Create temporary directories
    temp_dataset_dir = tempfile.mkdtemp()
    temp_output_dir = tempfile.mkdtemp()
    
    try:
        # Create dataset with multiple identities
        total_images = 0
        for i in range(num_identities):
            identity_name = f"Identity{i}"
            identity_dir = os.path.join(temp_dataset_dir, identity_name)
            os.makedirs(identity_dir, exist_ok=True)
            
            # Create images
            for j in range(images_per_identity):
                img_path = os.path.join(identity_dir, f"image_{j}.jpg")
                img = create_test_image(has_face=True, num_faces=1)
                cv2.imwrite(img_path, img)
                total_images += 1
        
        # Create mock detector and aligner
        mock_detector = create_mock_detector_with_behavior(has_face=True, num_faces=1)
        mock_aligner = create_mock_aligner()
        
        # Preprocess dataset
        result = preprocess_dataset(
            temp_dataset_dir,
            temp_output_dir,
            detector=mock_detector,
            aligner=mock_aligner,
            use_gpu=False
        )
        
        # Property: All images should be processed
        assert result.total_images == total_images, \
            f"Should process all {total_images} images, got {result.total_images}"
        
        # Property: All identities should be processed
        assert result.identities_processed == num_identities, \
            f"Should process all {num_identities} identities, got {result.identities_processed}"
        
        # Property: Successful count should match total (since all have faces)
        assert result.successful == total_images, \
            f"All {total_images} images with faces should be successfully processed, got {result.successful}"
        
        # Property: Output directory should contain all identities
        for i in range(num_identities):
            identity_name = f"Identity{i}"
            output_identity_dir = os.path.join(temp_output_dir, identity_name)
            assert os.path.exists(output_identity_dir), \
                f"Output directory should contain {identity_name}"
            
            # Check that aligned images were created
            output_files = os.listdir(output_identity_dir)
            assert len(output_files) == images_per_identity, \
                f"Should create {images_per_identity} aligned images for {identity_name}, got {len(output_files)}"
    
    finally:
        # Cleanup
        if os.path.exists(temp_dataset_dir):
            shutil.rmtree(temp_dataset_dir)
        if os.path.exists(temp_output_dir):
            shutil.rmtree(temp_output_dir)


# Property 29: No-Face Image Handling
# **Validates: Requirements 2.4**

@given(
    num_no_face_images=st.integers(min_value=1, max_value=5),
    num_face_images=st.integers(min_value=1, max_value=5)
)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_29_no_face_image_handling(num_no_face_images, num_face_images):
    """
    Property 29: No-Face Image Handling
    
    For any dataset image containing no detectable face, the system should
    log a warning and skip that image without crashing.
    
    **Validates: Requirements 2.4**
    """
    # Create temporary directories
    temp_dataset_dir = tempfile.mkdtemp()
    temp_output_dir = tempfile.mkdtemp()
    
    try:
        # Create dataset with one identity
        identity_name = "TestIdentity"
        identity_dir = os.path.join(temp_dataset_dir, identity_name)
        os.makedirs(identity_dir, exist_ok=True)
        
        # Create images with and without faces
        total_images = num_no_face_images + num_face_images
        for i in range(total_images):
            img_path = os.path.join(identity_dir, f"image_{i}.jpg")
            # First num_no_face_images have no faces
            has_face = i >= num_no_face_images
            img = create_test_image(has_face=has_face)
            cv2.imwrite(img_path, img)
        
        # Create mock detector that returns no faces for first images
        mock_detector = MagicMock()
        call_count = [0]
        
        def mock_detect(frame, confidence_threshold=0.5):
            idx = call_count[0]
            call_count[0] += 1
            
            if idx < num_no_face_images:
                # No face detected
                return []
            else:
                # Face detected
                detection = Detection(
                    bbox=(100, 100, 100, 100),
                    landmarks=np.array([[150, 150], [200, 150], [175, 175], [160, 200], [190, 200]]),
                    confidence=0.9
                )
                return [detection]
        
        mock_detector.detect = mock_detect
        mock_aligner = create_mock_aligner()
        
        # Preprocess dataset with logging capture
        import logging
        with patch.object(logging.getLogger('guru_vision.training.preprocess'), 'warning') as mock_warning:
            result = preprocess_dataset(
                temp_dataset_dir,
                temp_output_dir,
                detector=mock_detector,
                aligner=mock_aligner,
                use_gpu=False
            )
            
            # Property: System should not crash
            assert result is not None, \
                "System should not crash when processing images without faces"
            
            # Property: No-face images should be counted
            assert result.no_face == num_no_face_images, \
                f"Should count {num_no_face_images} no-face images, got {result.no_face}"
            
            # Property: Only face images should be successful
            assert result.successful == num_face_images, \
                f"Should successfully process {num_face_images} images with faces, got {result.successful}"
            
            # Property: Total should match
            assert result.total_images == total_images, \
                f"Should process {total_images} total images, got {result.total_images}"
            
            # Property: Warnings should be logged for no-face images
            assert mock_warning.call_count >= num_no_face_images, \
                f"Should log at least {num_no_face_images} warnings for no-face images"
    
    finally:
        # Cleanup
        if os.path.exists(temp_dataset_dir):
            shutil.rmtree(temp_dataset_dir)
        if os.path.exists(temp_output_dir):
            shutil.rmtree(temp_output_dir)


# Property 28: Multiple Face Selection
# **Validates: Requirements 2.5**

@given(
    num_faces=st.integers(min_value=2, max_value=5),
    num_images=st.integers(min_value=1, max_value=3)
)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_28_multiple_face_selection(num_faces, num_images):
    """
    Property 28: Multiple Face Selection
    
    For any image containing multiple faces, when preprocessing for dataset
    alignment, the system should extract the face with the largest bounding
    box area.
    
    **Validates: Requirements 2.5**
    """
    # Create temporary directories
    temp_dataset_dir = tempfile.mkdtemp()
    temp_output_dir = tempfile.mkdtemp()
    
    try:
        # Create dataset with one identity
        identity_name = "TestIdentity"
        identity_dir = os.path.join(temp_dataset_dir, identity_name)
        os.makedirs(identity_dir, exist_ok=True)
        
        # Create images with multiple faces
        for i in range(num_images):
            img_path = os.path.join(identity_dir, f"image_{i}.jpg")
            img = create_test_image(has_face=True, num_faces=num_faces)
            cv2.imwrite(img_path, img)
        
        # Create mock detector that returns multiple faces with different sizes
        mock_detector = MagicMock()
        
        def mock_detect(frame, confidence_threshold=0.5):
            detections = []
            for j in range(num_faces):
                # Create faces with decreasing sizes (first is largest)
                size = 100 - (j * 10)
                detection = Detection(
                    bbox=(100 + j * 150, 100, size, size),
                    landmarks=np.array([[150, 150], [200, 150], [175, 175], [160, 200], [190, 200]]),
                    confidence=0.9 - (j * 0.05)
                )
                detections.append(detection)
            return detections
        
        mock_detector.detect = mock_detect
        
        # Track which detection was used for alignment
        aligned_detections = []
        mock_aligner = MagicMock()
        
        def mock_align(frame, detection):
            aligned_detections.append(detection)
            return np.ones((112, 112, 3), dtype=np.uint8) * 128
        
        mock_aligner.align = mock_align
        
        # Preprocess dataset with logging capture
        import logging
        with patch.object(logging.getLogger('guru_vision.training.preprocess'), 'info') as mock_info:
            result = preprocess_dataset(
                temp_dataset_dir,
                temp_output_dir,
                detector=mock_detector,
                aligner=mock_aligner,
                use_gpu=False
            )
            
            # Property: Multiple faces should be counted
            assert result.multiple_faces == num_images, \
                f"Should count {num_images} images with multiple faces, got {result.multiple_faces}"
            
            # Property: All images should be successfully processed
            assert result.successful == num_images, \
                f"Should successfully process all {num_images} images, got {result.successful}"
            
            # Property: Should use largest face for each image
            for detection in aligned_detections:
                # The detection used should be the first one (largest)
                # Verify by checking bbox size
                area = detection.bbox[2] * detection.bbox[3]
                # First detection has size 100x100 = 10000
                expected_area = 100 * 100
                assert area == expected_area, \
                    f"Should use largest face (area {expected_area}), got area {area}"
            
            # Property: Should log info about multiple faces
            # Check that info was logged about multiple faces
            info_calls = [str(call) for call in mock_info.call_args_list]
            multiple_face_logs = [call for call in info_calls if 'Multiple faces' in call or 'multiple faces' in call]
            assert len(multiple_face_logs) >= num_images, \
                f"Should log info about multiple faces for {num_images} images"
    
    finally:
        # Cleanup
        if os.path.exists(temp_dataset_dir):
            shutil.rmtree(temp_dataset_dir)
        if os.path.exists(temp_output_dir):
            shutil.rmtree(temp_output_dir)


# Additional property: PreprocessResult structure consistency
@given(
    successful=st.integers(min_value=0, max_value=100),
    no_face=st.integers(min_value=0, max_value=50),
    failed=st.integers(min_value=0, max_value=20)
)
@settings(max_examples=50, deadline=None)
def test_property_preprocess_result_totals(successful, no_face, failed):
    """
    Property: PreprocessResult Total Consistency
    
    The total_images field should equal the sum of successful, no_face, and failed counts.
    Note: multiple_faces is a subset of successful, not a separate category.
    """
    # multiple_faces must be <= successful
    multiple_faces = min(successful, successful // 2) if successful > 0 else 0
    
    # Create a PreprocessResult
    total = successful + no_face + failed
    result = PreprocessResult(
        total_images=total,
        successful=successful,
        no_face=no_face,
        multiple_faces=multiple_faces,
        failed=failed,
        identities_processed=1,
        statistics={}
    )
    
    # Property: Total should equal sum of categories
    assert result.total_images == result.successful + result.no_face + result.failed, \
        "Total images should equal sum of successful, no_face, and failed"
    
    # Property: Multiple faces should not exceed successful
    assert result.multiple_faces <= result.successful, \
        "Multiple faces count should not exceed successful count"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
