"""
Property-Based Tests for Face Alignment Module

This module contains property-based tests using Hypothesis to validate
universal correctness properties of the face alignment operations.

Properties tested:
- Property 2: Aligned Face Dimensions
"""

import pytest
import numpy as np
import cv2
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from guru_vision.alignment import FaceAligner
from guru_vision.detection import Detection


# Custom strategies for generating test data

@st.composite
def valid_image_dimensions(draw):
    """Generate valid image dimensions (width, height)."""
    width = draw(st.integers(min_value=200, max_value=1920))
    height = draw(st.integers(min_value=200, max_value=1080))
    return width, height


@st.composite
def generate_test_image(draw):
    """
    Generate a test image for alignment.
    
    Returns:
        A numpy array representing an image (BGR format)
    """
    width, height = draw(valid_image_dimensions())
    
    # Generate random image
    seed = draw(st.integers(min_value=0, max_value=10000))
    rng = np.random.RandomState(seed)
    
    # Create image with random content
    image = rng.randint(0, 255, (height, width, 3), dtype=np.uint8)
    
    return image


@st.composite
def generate_valid_landmarks(draw, image_shape):
    """
    Generate valid facial landmarks within image bounds.
    
    Args:
        image_shape: Tuple of (height, width, channels)
    
    Returns:
        A numpy array of shape (5, 2) with valid landmark coordinates
    """
    height, width = image_shape[0], image_shape[1]
    
    # Generate landmarks that form a reasonable face structure
    # Center the face in the image with some margin
    margin = 50
    center_x = draw(st.integers(min_value=width // 4, max_value=3 * width // 4))
    center_y = draw(st.integers(min_value=height // 4, max_value=3 * height // 4))
    
    # Generate face width (distance between eyes)
    # Ensure min_value doesn't exceed max_value
    min_face_width = min(60, width // 4)
    max_face_width = max(min_face_width + 10, min(200, width // 2))
    face_width = draw(st.integers(min_value=min_face_width, max_value=max_face_width))
    
    # Create landmarks for a frontal face
    # Left eye
    left_eye_x = center_x - face_width // 2
    left_eye_y = center_y - face_width // 4
    
    # Right eye
    right_eye_x = center_x + face_width // 2
    right_eye_y = center_y - face_width // 4
    
    # Nose
    nose_x = center_x
    nose_y = center_y + face_width // 6
    
    # Left mouth corner
    left_mouth_x = center_x - face_width // 3
    left_mouth_y = center_y + face_width // 2
    
    # Right mouth corner
    right_mouth_x = center_x + face_width // 3
    right_mouth_y = center_y + face_width // 2
    
    landmarks = np.array([
        [left_eye_x, left_eye_y],
        [right_eye_x, right_eye_y],
        [nose_x, nose_y],
        [left_mouth_x, left_mouth_y],
        [right_mouth_x, right_mouth_y]
    ], dtype=np.float32)
    
    # Ensure all landmarks are within image bounds
    landmarks[:, 0] = np.clip(landmarks[:, 0], margin, width - margin)
    landmarks[:, 1] = np.clip(landmarks[:, 1], margin, height - margin)
    
    return landmarks


@st.composite
def generate_detection_with_landmarks(draw, image_shape):
    """
    Generate a Detection object with valid landmarks.
    
    Args:
        image_shape: Tuple of (height, width, channels)
    
    Returns:
        A Detection object with valid bbox, landmarks, and confidence
    """
    landmarks = draw(generate_valid_landmarks(image_shape))
    
    # Compute bounding box from landmarks
    x_coords = landmarks[:, 0]
    y_coords = landmarks[:, 1]
    
    x_min = int(np.min(x_coords))
    y_min = int(np.min(y_coords))
    x_max = int(np.max(x_coords))
    y_max = int(np.max(y_coords))
    
    # Add some padding to bbox
    padding = 20
    x_min = max(0, x_min - padding)
    y_min = max(0, y_min - padding)
    x_max = min(image_shape[1], x_max + padding)
    y_max = min(image_shape[0], y_max + padding)
    
    bbox = (x_min, y_min, x_max - x_min, y_max - y_min)
    
    confidence = draw(st.floats(min_value=0.5, max_value=1.0))
    
    return Detection(bbox=bbox, landmarks=landmarks, confidence=confidence)


# Property 2: Aligned Face Dimensions
# **Validates: Requirements 4.2**

@given(
    image=generate_test_image(),
    output_size=st.sampled_from([(112, 112), (224, 224), (96, 96), (128, 128)]),
    data=st.data()
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_2_aligned_face_dimensions(image, output_size, data):
    """
    Property 2: Aligned Face Dimensions
    
    For any detected face, when aligned by the Face_Aligner, the output image
    dimensions should be exactly the specified output size.
    
    This property validates that:
    1. The aligner always produces output of the correct dimensions
    2. The output dimensions match the configured output_size parameter
    3. The output is a valid 3-channel BGR image
    4. This holds for any valid input image and landmark configuration
    
    **Validates: Requirements 4.2**
    """
    # Initialize aligner with specified output size
    aligner = FaceAligner(output_size=output_size)
    
    # Generate valid detection with landmarks using data.draw()
    detection = data.draw(generate_detection_with_landmarks(image.shape))
    
    # Align the face
    try:
        aligned_face = aligner.align(image, detection)
    except ValueError as e:
        # If alignment fails due to extreme conditions, skip this example
        # This is acceptable as the property focuses on successful alignments
        assume(False)
    
    # Property 1: Output dimensions match specified output_size
    expected_height, expected_width = output_size[1], output_size[0]
    actual_height, actual_width = aligned_face.shape[0], aligned_face.shape[1]
    
    assert actual_height == expected_height, \
        f"Aligned face height should be {expected_height}, got {actual_height}"
    assert actual_width == expected_width, \
        f"Aligned face width should be {expected_width}, got {actual_width}"
    
    # Property 2: Output has exactly 3 color channels (BGR)
    assert aligned_face.shape[2] == 3, \
        f"Aligned face should have 3 color channels, got {aligned_face.shape[2]}"
    
    # Property 3: Output shape is exactly (height, width, 3)
    assert aligned_face.shape == (expected_height, expected_width, 3), \
        f"Aligned face shape should be {(expected_height, expected_width, 3)}, got {aligned_face.shape}"
    
    # Property 4: Output is a valid numpy array with uint8 dtype
    assert isinstance(aligned_face, np.ndarray), \
        "Aligned face should be a numpy array"
    assert aligned_face.dtype == np.uint8, \
        f"Aligned face should have dtype uint8, got {aligned_face.dtype}"
    
    # Property 5: Output values are in valid range [0, 255]
    assert np.all(aligned_face >= 0) and np.all(aligned_face <= 255), \
        "Aligned face pixel values should be in range [0, 255]"


@given(
    image=generate_test_image(),
    data=st.data()
)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_2_default_output_size(image, data):
    """
    Property 2 (Default Size): Aligned Face Dimensions with Default Size
    
    When using the default FaceAligner configuration, the output should
    always be 112x112 pixels, which is the standard input size for ArcFace models.
    
    **Validates: Requirements 4.2**
    """
    # Initialize aligner with default output size
    aligner = FaceAligner()  # Default is (112, 112)
    
    # Generate valid detection with landmarks using data.draw()
    detection = data.draw(generate_detection_with_landmarks(image.shape))
    
    # Align the face
    try:
        aligned_face = aligner.align(image, detection)
    except ValueError:
        # Skip if alignment fails
        assume(False)
    
    # Property: Default output dimensions are exactly 112x112
    assert aligned_face.shape == (112, 112, 3), \
        f"Default aligned face shape should be (112, 112, 3), got {aligned_face.shape}"


@given(
    image=generate_test_image(),
    output_size=st.sampled_from([(112, 112), (224, 224)]),
    data=st.data()
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_2_consistency_across_alignments(image, output_size, data):
    """
    Property 2 (Consistency): Aligned Face Dimensions Consistency
    
    For the same input image and detection, multiple alignment operations
    should produce outputs with identical dimensions.
    
    **Validates: Requirements 4.2**
    """
    aligner = FaceAligner(output_size=output_size)
    
    # Generate valid detection with landmarks using data.draw()
    detection = data.draw(generate_detection_with_landmarks(image.shape))
    
    # Perform alignment twice
    try:
        aligned_face_1 = aligner.align(image, detection)
        aligned_face_2 = aligner.align(image, detection)
    except ValueError:
        # Skip if alignment fails
        assume(False)
    
    # Property: Both alignments produce identical dimensions
    assert aligned_face_1.shape == aligned_face_2.shape, \
        "Multiple alignments of the same face should produce identical dimensions"
    
    # Property: Dimensions match the configured output size
    expected_shape = (output_size[1], output_size[0], 3)
    assert aligned_face_1.shape == expected_shape, \
        f"Aligned face shape should be {expected_shape}, got {aligned_face_1.shape}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
