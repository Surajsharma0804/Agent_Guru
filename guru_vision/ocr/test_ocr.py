"""
Unit tests for OCR module
"""

import pytest
import numpy as np
from guru_vision.ocr import TextRecognizer, RecognizedText
from guru_vision.ocr.preprocessing import (
    denoise_image, enhance_contrast, correct_skew,
    binarize_image, preprocess_for_ocr
)


class TestRecognizedText:
    """Tests for RecognizedText dataclass"""
    
    def test_create_recognized_text(self):
        """Test creating RecognizedText instance"""
        text = RecognizedText(
            text="Hello",
            bbox=(10, 20, 100, 50),
            confidence=0.95,
            language='en'
        )
        assert text.text == "Hello"
        assert text.bbox == (10, 20, 100, 50)
        assert text.confidence == 0.95
        assert text.language == 'en'


class TestTextRecognizer:
    """Tests for TextRecognizer class"""
    
    def test_init_default(self):
        """Test initialization with default parameters"""
        recognizer = TextRecognizer()
        assert recognizer.languages == ['en']
        assert recognizer.confidence_threshold == 0.5
        assert recognizer.use_gpu is False
    
    def test_init_custom(self):
        """Test initialization with custom parameters"""
        recognizer = TextRecognizer(
            languages=['en', 'es'],
            confidence_threshold=0.7,
            use_gpu=True
        )
        assert recognizer.languages == ['en', 'es']
        assert recognizer.confidence_threshold == 0.7
        assert recognizer.use_gpu is True
    
    def test_init_clamps_confidence(self):
        """Test that confidence threshold is clamped to [0, 1]"""
        recognizer = TextRecognizer(confidence_threshold=1.5)
        assert recognizer.confidence_threshold == 1.0
        
        recognizer = TextRecognizer(confidence_threshold=-0.5)
        assert recognizer.confidence_threshold == 0.0
    
    def test_recognize_empty_image(self):
        """Test recognition with empty image"""
        recognizer = TextRecognizer()
        result = recognizer.recognize(np.array([]))
        assert result == []
    
    def test_recognize_none_image(self):
        """Test recognition with None image"""
        recognizer = TextRecognizer()
        result = recognizer.recognize(None)
        assert result == []
    
    def test_recognize_without_reader(self):
        """Test recognition when reader is not initialized"""
        recognizer = TextRecognizer()
        recognizer.reader = None
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        result = recognizer.recognize(image)
        assert result == []
    
    def test_set_confidence_threshold_valid(self):
        """Test setting valid confidence threshold"""
        recognizer = TextRecognizer()
        recognizer.set_confidence_threshold(0.8)
        assert recognizer.confidence_threshold == 0.8
    
    def test_set_confidence_threshold_invalid(self):
        """Test setting invalid confidence threshold"""
        recognizer = TextRecognizer()
        with pytest.raises(ValueError):
            recognizer.set_confidence_threshold(1.5)
        with pytest.raises(ValueError):
            recognizer.set_confidence_threshold(-0.1)
    
    def test_set_languages_valid(self):
        """Test setting valid languages"""
        recognizer = TextRecognizer()
        recognizer.set_languages(['fr', 'de'])
        assert recognizer.languages == ['fr', 'de']
    
    def test_set_languages_empty(self):
        """Test setting empty languages list"""
        recognizer = TextRecognizer()
        with pytest.raises(ValueError):
            recognizer.set_languages([])


class TestPreprocessing:
    """Tests for preprocessing utilities"""
    
    def test_denoise_empty_image(self):
        """Test denoising empty image"""
        result = denoise_image(np.array([]))
        assert result.size == 0
    
    def test_denoise_none_image(self):
        """Test denoising None image"""
        result = denoise_image(None)
        assert result is None
    
    def test_denoise_color_image(self):
        """Test denoising color image"""
        image = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        result = denoise_image(image, strength=10)
        assert result.shape == image.shape
        assert result.dtype == np.uint8
    
    def test_denoise_gray_image(self):
        """Test denoising grayscale image"""
        image = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
        result = denoise_image(image, strength=10)
        assert result.shape == image.shape
        assert result.dtype == np.uint8
    
    def test_enhance_contrast_empty_image(self):
        """Test contrast enhancement on empty image"""
        result = enhance_contrast(np.array([]))
        assert result.size == 0
    
    def test_enhance_contrast_none_image(self):
        """Test contrast enhancement on None image"""
        result = enhance_contrast(None)
        assert result is None
    
    def test_enhance_contrast_color_image(self):
        """Test contrast enhancement on color image"""
        image = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        result = enhance_contrast(image)
        assert result.shape == image.shape
        assert result.dtype == np.uint8
    
    def test_enhance_contrast_gray_image(self):
        """Test contrast enhancement on grayscale image"""
        image = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
        result = enhance_contrast(image)
        assert result.shape == image.shape
        assert result.dtype == np.uint8
    
    def test_correct_skew_empty_image(self):
        """Test skew correction on empty image"""
        result, angle = correct_skew(np.array([]))
        assert result.size == 0
        assert angle == 0.0
    
    def test_correct_skew_none_image(self):
        """Test skew correction on None image"""
        result, angle = correct_skew(None)
        assert result is None
        assert angle == 0.0
    
    def test_correct_skew_color_image(self):
        """Test skew correction on color image"""
        image = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        result, angle = correct_skew(image)
        assert result.shape == image.shape
        assert isinstance(angle, float)
    
    def test_correct_skew_gray_image(self):
        """Test skew correction on grayscale image"""
        image = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
        result, angle = correct_skew(image)
        assert result.shape == image.shape
        assert isinstance(angle, float)
    
    def test_binarize_empty_image(self):
        """Test binarization on empty image"""
        result = binarize_image(np.array([]))
        assert result.size == 0
    
    def test_binarize_none_image(self):
        """Test binarization on None image"""
        result = binarize_image(None)
        assert result is None
    
    def test_binarize_otsu(self):
        """Test Otsu binarization"""
        image = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        result = binarize_image(image, method='otsu')
        assert result.shape == (100, 100)
        assert result.dtype == np.uint8
        assert np.all((result == 0) | (result == 255))
    
    def test_binarize_adaptive(self):
        """Test adaptive binarization"""
        image = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        result = binarize_image(image, method='adaptive')
        assert result.shape == (100, 100)
        assert result.dtype == np.uint8
        assert np.all((result == 0) | (result == 255))
    
    def test_binarize_invalid_method(self):
        """Test binarization with invalid method"""
        image = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
        with pytest.raises(ValueError):
            binarize_image(image, method='invalid')
    
    def test_preprocess_for_ocr_empty_image(self):
        """Test full preprocessing on empty image"""
        result = preprocess_for_ocr(np.array([]))
        assert result.size == 0
    
    def test_preprocess_for_ocr_none_image(self):
        """Test full preprocessing on None image"""
        result = preprocess_for_ocr(None)
        assert result is None
    
    def test_preprocess_for_ocr_all_steps(self):
        """Test full preprocessing with all steps"""
        image = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        result = preprocess_for_ocr(
            image,
            denoise=True,
            enhance=True,
            correct_skew_flag=True,
            binarize=True
        )
        assert result.shape == (100, 100)
        assert result.dtype == np.uint8
    
    def test_preprocess_for_ocr_no_steps(self):
        """Test preprocessing with no steps"""
        image = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        result = preprocess_for_ocr(
            image,
            denoise=False,
            enhance=False,
            correct_skew_flag=False,
            binarize=False
        )
        assert result.shape == image.shape
        np.testing.assert_array_equal(result, image)
    
    def test_preprocess_for_ocr_selective_steps(self):
        """Test preprocessing with selective steps"""
        image = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        result = preprocess_for_ocr(
            image,
            denoise=True,
            enhance=False,
            correct_skew_flag=True,
            binarize=False
        )
        assert result.shape == image.shape
        assert result.dtype == np.uint8
