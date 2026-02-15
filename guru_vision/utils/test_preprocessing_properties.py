"""
Property-Based Tests for Preprocessing Module

This module contains property-based tests using Hypothesis to validate
universal correctness properties of the preprocessing operations.

Properties tested:
- Property 24: Low-Light Enhancement Trigger
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from guru_vision.utils.preprocessing import (
    enhance_low_light,
    check_brightness,
    preprocess_frame
)


# Custom strategies for generating test data

@st.composite
def image_frame(draw, min_brightness=0, max_brightness=255):
    """
    Generate a valid image frame with controlled brightness.
    
    Args:
        draw: Hypothesis draw function
        min_brightness: Minimum mean brightness value
        max_brightness: Maximum mean brightness value
    
    Returns:
        np.ndarray: BGR image with specified brightness range
    """
    # Generate image dimensions
    height = draw(st.integers(min_value=50, max_value=500))
    width = draw(st.integers(min_value=50, max_value=500))
    
    # Generate target brightness within specified range
    target_brightness = draw(st.floats(
        min_value=float(min_brightness),
        max_value=float(max_brightness),
        allow_nan=False,
        allow_infinity=False
    ))
    
    # Generate random image with approximately the target brightness
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    rng = np.random.RandomState(seed)
    
    # Create image with target brightness
    # Use normal distribution centered at target brightness
    frame = rng.normal(loc=target_brightness, scale=20, size=(height, width, 3))
    
    # Clip to valid range [0, 255]
    frame = np.clip(frame, 0, 255).astype(np.uint8)
    
    return frame


@st.composite
def low_brightness_frame(draw):
    """Generate a frame with low brightness (mean < 50)."""
    return draw(image_frame(min_brightness=0, max_brightness=49))


@st.composite
def adequate_brightness_frame(draw):
    """Generate a frame with adequate brightness (mean >= 50)."""
    return draw(image_frame(min_brightness=50, max_brightness=255))


@st.composite
def brightness_threshold(draw):
    """Generate a valid brightness threshold value."""
    return draw(st.floats(
        min_value=0.0,
        max_value=255.0,
        allow_nan=False,
        allow_infinity=False
    ))


# Property 24: Low-Light Enhancement Trigger
# **Validates: Requirements 22.1**

@given(frame=low_brightness_frame())
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_24_low_light_enhancement_trigger_dark_frames(frame):
    """
    Property 24: Low-Light Enhancement Trigger (Part 1 - Dark Frames)
    
    For any input frame with mean pixel brightness less than 50,
    the system should apply low-light enhancement preprocessing.
    
    **Validates: Requirements 22.1**
    """
    # Verify the frame actually has low brightness
    brightness = check_brightness(frame)
    assume(brightness < 50.0)  # Ensure we're testing low-brightness frames
    
    # Apply enhancement with default threshold (50.0)
    enhanced, was_enhanced = enhance_low_light(frame, brightness_threshold=50.0)
    
    # Verify enhancement was applied
    assert was_enhanced is True, \
        f"Enhancement should be applied when brightness {brightness:.2f} < 50.0"
    
    # Verify enhanced frame is returned
    assert enhanced is not None, \
        "Enhanced frame should not be None"
    
    # Verify frame dimensions are preserved
    assert enhanced.shape == frame.shape, \
        f"Enhanced frame should preserve dimensions, got {enhanced.shape} vs {frame.shape}"
    
    # Verify enhanced frame is different from original (enhancement was actually applied)
    assert not np.array_equal(enhanced, frame), \
        "Enhanced frame should be different from original frame"


@given(frame=adequate_brightness_frame())
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_24_low_light_enhancement_trigger_bright_frames(frame):
    """
    Property 24: Low-Light Enhancement Trigger (Part 2 - Bright Frames)
    
    For any input frame with mean pixel brightness >= 50,
    the system should NOT apply low-light enhancement preprocessing
    (to preserve processing speed).
    
    **Validates: Requirements 22.1, 22.5**
    """
    # Verify the frame actually has adequate brightness
    brightness = check_brightness(frame)
    assume(brightness >= 50.0)  # Ensure we're testing adequate-brightness frames
    
    # Apply enhancement with default threshold (50.0)
    enhanced, was_enhanced = enhance_low_light(frame, brightness_threshold=50.0)
    
    # Verify enhancement was NOT applied
    assert was_enhanced is False, \
        f"Enhancement should NOT be applied when brightness {brightness:.2f} >= 50.0"
    
    # Verify original frame is returned unchanged
    assert enhanced is not None, \
        "Returned frame should not be None"
    
    # Verify frame is unchanged (no enhancement applied)
    np.testing.assert_array_equal(enhanced, frame,
        err_msg="Frame should be unchanged when brightness is adequate")


@given(
    target_brightness=st.floats(min_value=0.0, max_value=255.0, allow_nan=False, allow_infinity=False),
    threshold=brightness_threshold()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_24_low_light_enhancement_trigger_threshold_boundary(target_brightness, threshold):
    """
    Property 24: Low-Light Enhancement Trigger (Part 3 - Threshold Boundary)
    
    For any input frame and any threshold value, the enhancement should be
    applied if and only if the frame's mean brightness is below the threshold.
    
    This tests the universal property across all possible threshold values.
    
    **Validates: Requirements 22.1**
    """
    # Create a frame with approximately the target brightness
    rng = np.random.RandomState(int(target_brightness * 1000) % (2**31))
    frame = rng.normal(loc=target_brightness, scale=15, size=(100, 100, 3))
    frame = np.clip(frame, 0, 255).astype(np.uint8)
    
    # Get actual brightness
    actual_brightness = check_brightness(frame)
    
    # Apply enhancement with the specified threshold
    enhanced, was_enhanced = enhance_low_light(frame, brightness_threshold=threshold)
    
    # Verify threshold-based behavior
    if actual_brightness < threshold:
        assert was_enhanced is True, \
            f"Enhancement should be applied when brightness {actual_brightness:.2f} < threshold {threshold:.2f}"
        assert not np.array_equal(enhanced, frame), \
            "Enhanced frame should differ from original when enhancement is applied"
    else:
        assert was_enhanced is False, \
            f"Enhancement should NOT be applied when brightness {actual_brightness:.2f} >= threshold {threshold:.2f}"
        np.testing.assert_array_equal(enhanced, frame,
            err_msg="Frame should be unchanged when brightness >= threshold")


@given(frame=low_brightness_frame())
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_24_enhancement_increases_brightness(frame):
    """
    Property 24: Low-Light Enhancement Effect
    
    When enhancement is applied to a low-brightness frame,
    the resulting frame should have increased brightness.
    
    This validates that the enhancement actually improves the image.
    
    **Validates: Requirements 22.1, 22.2**
    """
    # Get original brightness
    original_brightness = check_brightness(frame)
    assume(original_brightness < 50.0)
    
    # Apply enhancement
    enhanced, was_enhanced = enhance_low_light(frame, brightness_threshold=50.0)
    
    # If enhancement was applied, brightness should increase
    if was_enhanced:
        enhanced_brightness = check_brightness(enhanced)
        assert enhanced_brightness > original_brightness, \
            f"Enhanced brightness {enhanced_brightness:.2f} should be greater than original {original_brightness:.2f}"


@given(
    height=st.integers(min_value=50, max_value=500),
    width=st.integers(min_value=50, max_value=500),
    channels=st.sampled_from([1, 3])  # Grayscale or color
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_24_enhancement_preserves_dimensions(height, width, channels):
    """
    Property 24: Enhancement Preserves Dimensions
    
    For any frame dimensions, enhancement should preserve the original
    frame dimensions (height, width, channels).
    
    **Validates: Requirements 22.3**
    """
    # Create a low-brightness frame with specified dimensions
    if channels == 1:
        frame = np.ones((height, width), dtype=np.uint8) * 30
    else:
        frame = np.ones((height, width, channels), dtype=np.uint8) * 30
    
    # Apply enhancement
    enhanced, was_enhanced = enhance_low_light(frame, brightness_threshold=50.0)
    
    # Verify dimensions are preserved
    assert enhanced.shape == frame.shape, \
        f"Enhanced frame should preserve dimensions: expected {frame.shape}, got {enhanced.shape}"


@given(frame=low_brightness_frame())
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_24_enhancement_deterministic(frame):
    """
    Property 24: Enhancement Determinism
    
    Applying enhancement to the same frame multiple times should
    produce identical results (deterministic behavior).
    
    **Validates: Requirements 22.1**
    """
    # Verify frame has low brightness
    brightness = check_brightness(frame)
    assume(brightness < 50.0)
    
    # Apply enhancement twice
    enhanced1, was_enhanced1 = enhance_low_light(frame, brightness_threshold=50.0)
    enhanced2, was_enhanced2 = enhance_low_light(frame, brightness_threshold=50.0)
    
    # Verify both applications had same behavior
    assert was_enhanced1 == was_enhanced2, \
        "Enhancement decision should be deterministic"
    
    # Verify results are identical
    np.testing.assert_array_equal(enhanced1, enhanced2,
        err_msg="Enhancement should produce identical results for same input")


@given(frame=low_brightness_frame())
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
)
def test_property_24_preprocess_frame_integration(frame):
    """
    Property 24: Integration with preprocess_frame
    
    The preprocess_frame function should correctly apply enhancement
    based on the brightness threshold and report it in metadata.
    
    **Validates: Requirements 22.1**
    """
    # Get original brightness
    original_brightness = check_brightness(frame)
    assume(original_brightness < 50.0)
    
    # Preprocess with enhancement enabled
    processed, metadata = preprocess_frame(
        frame,
        enable_low_light_enhancement=True,
        brightness_threshold=50.0
    )
    
    # Verify metadata reports enhancement was applied
    assert metadata['low_light_enhanced'] is True, \
        f"Metadata should indicate enhancement was applied for brightness {original_brightness:.2f}"
    
    # Verify metadata contains brightness information
    assert 'original_brightness' in metadata, \
        "Metadata should contain original brightness"
    assert metadata['original_brightness'] == pytest.approx(original_brightness, abs=1.0), \
        "Metadata should report correct original brightness"
    
    # Verify enhanced brightness is reported
    assert 'enhanced_brightness' in metadata, \
        "Metadata should contain enhanced brightness when enhancement is applied"
    assert metadata['enhanced_brightness'] > metadata['original_brightness'], \
        "Enhanced brightness should be greater than original"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
