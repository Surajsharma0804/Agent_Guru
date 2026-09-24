"""
Property-based tests for Agent_Guru.vision.utils.preprocessing.

Property 24: Low-Light Enhancement Trigger
  - enhance_low_light() must return an array with the same shape and dtype
    as the input for any valid BGR uint8 frame.
  - is_low_light() must return True iff mean pixel value < LOW_LIGHT_THRESHOLD.
  - A dark frame (mean < threshold) must be returned with mean >= original
    mean after enhancement (brightness never decreases).
  - A bright frame (mean >= threshold) must be returned unchanged.

Validates: Requirements 22.1, 22.2, 22.3, 22.4, 22.5
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from Agent_Guru.vision.utils.preprocessing import (
    LOW_LIGHT_THRESHOLD,
    enhance_low_light,
    is_low_light,
)

# ---------------------------------------------------------------------------
# Hypothesis strategies - use a seed + numpy to avoid Hypothesis list limits
# ---------------------------------------------------------------------------

@st.composite
def bgr_frame(draw: st.DrawFn) -> np.ndarray:
    """Any valid BGR uint8 frame up to 64x64."""
    h = draw(st.integers(min_value=8, max_value=64))
    w = draw(st.integers(min_value=8, max_value=64))
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


@st.composite
def dark_frame(draw: st.DrawFn) -> np.ndarray:
    """Frame whose every pixel is in [0, threshold-1] → mean < threshold."""
    h = draw(st.integers(min_value=8, max_value=64))
    w = draw(st.integers(min_value=8, max_value=64))
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    max_val = max(0, LOW_LIGHT_THRESHOLD - 1)
    rng = np.random.default_rng(seed)
    return rng.integers(0, max_val + 1, size=(h, w, 3), dtype=np.uint8)


@st.composite
def bright_frame(draw: st.DrawFn) -> np.ndarray:
    """Frame whose every pixel is in [threshold, 255] → mean >= threshold."""
    h = draw(st.integers(min_value=8, max_value=64))
    w = draw(st.integers(min_value=8, max_value=64))
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    rng = np.random.default_rng(seed)
    return rng.integers(LOW_LIGHT_THRESHOLD, 256, size=(h, w, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Property 24a: is_low_light correctness
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(frame=bgr_frame())
@settings(max_examples=100)
def test_is_low_light_matches_threshold(frame: np.ndarray) -> None:
    """is_low_light() must agree with mean < LOW_LIGHT_THRESHOLD."""
    expected = float(np.mean(frame)) < LOW_LIGHT_THRESHOLD
    assert is_low_light(frame) == expected  # nosec B101


@pytest.mark.property
@given(frame=dark_frame())
@settings(max_examples=100)
def test_is_low_light_true_for_dark_frames(frame: np.ndarray) -> None:
    """Dark frames (all pixels < threshold) must always be flagged."""
    assert is_low_light(frame) is True  # nosec B101


@pytest.mark.property
@given(frame=bright_frame())
@settings(max_examples=100)
def test_is_low_light_false_for_bright_frames(frame: np.ndarray) -> None:
    """Bright frames (all pixels >= threshold) must never be flagged."""
    assert is_low_light(frame) is False  # nosec B101


# ---------------------------------------------------------------------------
# Property 24b: enhance_low_light shape and dtype preservation
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(frame=bgr_frame())
@settings(max_examples=100)
def test_enhance_preserves_shape_and_dtype(frame: np.ndarray) -> None:
    """Output must have the same shape and dtype as the input."""
    result = enhance_low_light(frame)
    assert result.shape == frame.shape  # nosec B101
    assert result.dtype == frame.dtype  # nosec B101


# ---------------------------------------------------------------------------
# Property 24c: bright frames returned unchanged
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(frame=bright_frame())
@settings(max_examples=100)
def test_enhance_bright_frame_unchanged(frame: np.ndarray) -> None:
    """Frames above the threshold must be returned pixel-identical."""
    result = enhance_low_light(frame)
    np.testing.assert_array_equal(result, frame)


# ---------------------------------------------------------------------------
# Property 24d: dark frames are brightened (mean never decreases)
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(frame=dark_frame())
@settings(max_examples=50)
def test_enhance_dark_frame_increases_mean(frame: np.ndarray) -> None:
    """After enhancement a dark frame must have mean >= original mean."""
    original_mean = float(np.mean(frame))
    result = enhance_low_light(frame)
    enhanced_mean = float(np.mean(result))
    assert enhanced_mean >= original_mean - 1e-6  # nosec B101


# ---------------------------------------------------------------------------
# Property 24e: idempotency - shape/dtype preserved on double enhancement
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(frame=dark_frame())
@settings(max_examples=50)
def test_enhance_idempotent_shape(frame: np.ndarray) -> None:
    """Applying enhancement twice must still preserve shape and dtype."""
    once = enhance_low_light(frame)
    twice = enhance_low_light(once)
    assert twice.shape == frame.shape  # nosec B101
    assert twice.dtype == frame.dtype  # nosec B101
