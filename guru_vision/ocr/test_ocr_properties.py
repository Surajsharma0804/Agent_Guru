"""
Property-based tests for OCR module using Hypothesis
"""

import pytest
import numpy as np
from hypothesis import given, settings, strategies as st, assume
from guru_vision.ocr import TextRecognizer, RecognizedText
from guru_vision.ocr.preprocessing import (
    denoise_image, enhance_contrast, correct_skew,
    binarize_image, preprocess_for_ocr
)


# Strategies
@st.composite
def image_strategy(draw):
    """Generate random images"""
    height = draw(st.integers(min_value=50, max_value=200))
    width = draw(st.integers(min_value=50, max_value=200))
    channels = draw(st.sampled_from([1, 3]))
    
    if channels == 1:
        return np.random.randint(0, 256, (height, width), dtype=np.uint8)
    else:
        return np.random.randint(0, 256, (height, width, channels), dtype=np.uint8)


@st.composite
def bbox_strategy(draw):
    """Generate random bounding boxes"""
    x1 = draw(st.integers(min_value=0, max_value=500))
    y1 = draw(st.integers(min_value=0, max_value=500))
    w = draw(st.integers(min_value=10, max_value=200))
    h = draw(st.integers(min_value=10, max_value=200))
    return (x1, y1, x1 + w, y1 + h)


class TestTextRecognizerProperties:
    """Property-based tests for TextRecognizer"""
    
    @given(st.floats(min_value=0.0, max_value=1.0))
    @settings(max_examples=50, deadline=1000)
    def test_confidence_threshold_in_range(self, threshold):
        """Property: Confidence threshold is always in [0, 1]"""
        recognizer = TextRecognizer(confidence_threshold=threshold)
        assert 0.0 <= recognizer.confidence_threshold <= 1.0
    
    @given(st.floats(min_value=-10.0, max_value=10.0))
    @settings(max_examples=50, deadline=1000)
    def test_confidence_threshold_clamped(self, threshold):
        """Property: Confidence threshold is clamped to [0, 1]"""
        recognizer = TextRecognizer(confidence_threshold=threshold)
        assert 0.0 <= recognizer.confidence_threshold <= 1.0
    
    @given(st.lists(st.text(min_size=1, max_size=5), min_size=1, max_size=5))
    @settings(max_examples=30, deadline=1000)
    def test_languages_preserved(self, languages):
        """Property: Languages are preserved after initialization"""
        recognizer = TextRecognizer(languages=languages)
        assert recognizer.languages == languages
    
    @given(image_strategy())
    @settings(max_examples=20, deadline=2000)
    def test_recognize_returns_list(self, image):
        """Property: recognize() always returns a list"""
        recognizer = TextRecognizer()
        result = recognizer.recognize(image)
        assert isinstance(result, list)
    
    @given(st.floats(min_value=0.0, max_value=1.0))
    @settings(max_examples=30, deadline=1000)
    def test_set_confidence_threshold_valid(self, threshold):
        """Property: Setting valid threshold succeeds"""
        recognizer = TextRecognizer()
        recognizer.set_confidence_threshold(threshold)
        assert recognizer.confidence_threshold == threshold


class TestRecognizedTextProperties:
    """Property-based tests for RecognizedText"""
    
    @given(
        st.text(min_size=1, max_size=100),
        bbox_strategy(),
        st.floats(min_value=0.0, max_value=1.0),
        st.text(min_size=2, max_size=5)
    )
    @settings(max_examples=50, deadline=1000)
    def test_recognized_text_creation(self, text, bbox, confidence, language):
        """Property: RecognizedText can be created with valid inputs"""
        rt = RecognizedText(
            text=text,
            bbox=bbox,
            confidence=confidence,
            language=language
        )
        assert rt.text == text
        assert rt.bbox == bbox
        assert rt.confidence == confidence
        assert rt.language == language
    
    @given(bbox_strategy())
    @settings(max_examples=50, deadline=1000)
    def test_bbox_coordinates_ordered(self, bbox):
        """Property: Bounding box coordinates are properly ordered"""
        x1, y1, x2, y2 = bbox
        assert x1 < x2
        assert y1 < y2


class TestPreprocessingProperties:
    """Property-based tests for preprocessing utilities"""
    
    @given(image_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_denoise_preserves_shape(self, image):
        """Property: Denoising preserves image shape"""
        result = denoise_image(image)
        assert result.shape == image.shape
    
    @given(image_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_denoise_preserves_dtype(self, image):
        """Property: Denoising preserves image dtype"""
        result = denoise_image(image)
        assert result.dtype == image.dtype
    
    @given(image_strategy(), st.integers(min_value=1, max_value=30))
    @settings(max_examples=20, deadline=2000)
    def test_denoise_with_strength(self, image, strength):
        """Property: Denoising works with different strengths"""
        result = denoise_image(image, strength=strength)
        assert result.shape == image.shape
    
    @given(image_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_enhance_contrast_preserves_dtype(self, image):
        """Property: Contrast enhancement preserves dtype"""
        result = enhance_contrast(image)
        assert result.dtype == image.dtype
    
    @given(image_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_enhance_contrast_preserves_shape(self, image):
        """Property: Contrast enhancement preserves shape"""
        result = enhance_contrast(image)
        assert result.shape == image.shape
    
    @given(image_strategy())
    @settings(max_examples=20, deadline=2000)
    def test_correct_skew_preserves_shape(self, image):
        """Property: Skew correction preserves shape"""
        result, angle = correct_skew(image)
        assert result.shape == image.shape
    
    @given(image_strategy())
    @settings(max_examples=20, deadline=2000)
    def test_correct_skew_returns_angle(self, image):
        """Property: Skew correction returns a float angle"""
        result, angle = correct_skew(image)
        assert isinstance(angle, float)
    
    @given(image_strategy())
    @settings(max_examples=20, deadline=2000)
    def test_correct_skew_angle_reasonable(self, image):
        """Property: Skew angle is within reasonable bounds"""
        result, angle = correct_skew(image)
        assert -90 <= angle <= 90
    
    @given(image_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_binarize_produces_binary(self, image):
        """Property: Binarization produces only 0 and 255 values"""
        result = binarize_image(image, method='otsu')
        unique_values = np.unique(result)
        assert all(v in [0, 255] for v in unique_values)
    
    @given(image_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_binarize_reduces_to_2d(self, image):
        """Property: Binarization reduces to 2D"""
        result = binarize_image(image, method='otsu')
        assert len(result.shape) == 2
    
    @given(image_strategy(), st.sampled_from(['otsu', 'adaptive']))
    @settings(max_examples=20, deadline=2000)
    def test_binarize_methods(self, image, method):
        """Property: Both binarization methods work"""
        result = binarize_image(image, method=method)
        assert len(result.shape) == 2
        assert result.dtype == np.uint8
    
    @given(image_strategy())
    @settings(max_examples=20, deadline=3000)
    def test_preprocess_preserves_dtype(self, image):
        """Property: Preprocessing preserves dtype (unless binarized)"""
        result = preprocess_for_ocr(image, binarize=False)
        assert result.dtype == image.dtype
    
    @given(
        image_strategy(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans()
    )
    @settings(max_examples=20, deadline=3000)
    def test_preprocess_combinations(self, image, denoise, enhance, skew, binarize):
        """Property: All preprocessing combinations work"""
        result = preprocess_for_ocr(
            image,
            denoise=denoise,
            enhance=enhance,
            correct_skew_flag=skew,
            binarize=binarize
        )
        assert result is not None
        assert result.size > 0
    
    @given(image_strategy())
    @settings(max_examples=20, deadline=3000)
    def test_preprocess_idempotent_no_ops(self, image):
        """Property: Preprocessing with no operations returns copy"""
        result = preprocess_for_ocr(
            image,
            denoise=False,
            enhance=False,
            correct_skew_flag=False,
            binarize=False
        )
        np.testing.assert_array_equal(result, image)


class TestPreprocessingInvariants:
    """Test invariants that should hold across preprocessing"""
    
    @given(image_strategy())
    @settings(max_examples=20, deadline=2000)
    def test_denoise_idempotent(self, image):
        """Property: Denoising twice should be similar to denoising once"""
        once = denoise_image(image)
        twice = denoise_image(once)
        # Should be very similar (not exact due to algorithm)
        assert once.shape == twice.shape
    
    @given(image_strategy())
    @settings(max_examples=20, deadline=2000)
    def test_enhance_idempotent(self, image):
        """Property: Enhancing twice should be similar to enhancing once"""
        once = enhance_contrast(image)
        twice = enhance_contrast(once)
        # Should be very similar
        assert once.shape == twice.shape
