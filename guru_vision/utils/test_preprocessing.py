"""
Unit tests for preprocessing utilities.
"""

import pytest
import numpy as np
import cv2
from guru_vision.utils.preprocessing import (
    enhance_low_light,
    check_brightness,
    preprocess_frame
)


class TestEnhanceLowLight:
    """Test cases for enhance_low_light function."""
    
    def test_low_brightness_triggers_enhancement(self):
        """Test that low brightness (< 50) triggers enhancement."""
        # Create a dark image (mean brightness < 50)
        dark_frame = np.ones((100, 100, 3), dtype=np.uint8) * 30
        
        enhanced, was_enhanced = enhance_low_light(dark_frame, brightness_threshold=50.0)
        
        assert was_enhanced is True
        assert enhanced is not None
        assert enhanced.shape == dark_frame.shape
    
    def test_adequate_brightness_skips_enhancement(self):
        """Test that adequate brightness (>= 50) skips enhancement."""
        # Create a bright image (mean brightness >= 50)
        bright_frame = np.ones((100, 100, 3), dtype=np.uint8) * 150
        
        enhanced, was_enhanced = enhance_low_light(bright_frame, brightness_threshold=50.0)
        
        assert was_enhanced is False
        # Should return original frame unchanged
        np.testing.assert_array_equal(enhanced, bright_frame)
    
    def test_enhancement_increases_brightness(self):
        """Test that enhancement increases mean brightness."""
        # Create a dark image
        dark_frame = np.ones((100, 100, 3), dtype=np.uint8) * 30
        
        original_brightness = check_brightness(dark_frame)
        enhanced, was_enhanced = enhance_low_light(dark_frame)
        enhanced_brightness = check_brightness(enhanced)
        
        assert was_enhanced is True
        assert enhanced_brightness > original_brightness
    
    def test_grayscale_image_enhancement(self):
        """Test enhancement works on grayscale images."""
        # Create a dark grayscale image
        dark_gray = np.ones((100, 100), dtype=np.uint8) * 30
        
        enhanced, was_enhanced = enhance_low_light(dark_gray)
        
        assert was_enhanced is True
        assert enhanced is not None
        assert len(enhanced.shape) == 2  # Still grayscale
    
    def test_empty_frame_handling(self):
        """Test handling of empty or invalid frames."""
        empty_frame = np.array([])
        
        result, was_enhanced = enhance_low_light(empty_frame)
        
        assert was_enhanced is False
    
    def test_none_frame_handling(self):
        """Test handling of None frame."""
        result, was_enhanced = enhance_low_light(None)
        
        assert was_enhanced is False
    
    def test_custom_brightness_threshold(self):
        """Test custom brightness threshold."""
        # Create image with brightness = 60
        frame = np.ones((100, 100, 3), dtype=np.uint8) * 60
        
        # With threshold 50, should not enhance
        _, was_enhanced_50 = enhance_low_light(frame, brightness_threshold=50.0)
        assert was_enhanced_50 is False
        
        # With threshold 70, should enhance
        _, was_enhanced_70 = enhance_low_light(frame, brightness_threshold=70.0)
        assert was_enhanced_70 is True
    
    def test_preserves_image_dimensions(self):
        """Test that enhancement preserves image dimensions."""
        dark_frame = np.ones((120, 160, 3), dtype=np.uint8) * 30
        
        enhanced, _ = enhance_low_light(dark_frame)
        
        assert enhanced.shape == dark_frame.shape


class TestCheckBrightness:
    """Test cases for check_brightness function."""
    
    def test_brightness_calculation_color(self):
        """Test brightness calculation on color images."""
        # Create image with known brightness
        frame = np.ones((100, 100, 3), dtype=np.uint8) * 100
        
        brightness = check_brightness(frame)
        
        assert brightness == pytest.approx(100.0, abs=1.0)
    
    def test_brightness_calculation_grayscale(self):
        """Test brightness calculation on grayscale images."""
        frame = np.ones((100, 100), dtype=np.uint8) * 75
        
        brightness = check_brightness(frame)
        
        assert brightness == pytest.approx(75.0, abs=1.0)
    
    def test_empty_frame_returns_zero(self):
        """Test that empty frame returns 0 brightness."""
        empty_frame = np.array([])
        
        brightness = check_brightness(empty_frame)
        
        assert brightness == 0.0
    
    def test_none_frame_returns_zero(self):
        """Test that None frame returns 0 brightness."""
        brightness = check_brightness(None)
        
        assert brightness == 0.0


class TestPreprocessFrame:
    """Test cases for preprocess_frame function."""
    
    def test_preprocess_with_enhancement_enabled(self):
        """Test preprocessing with low-light enhancement enabled."""
        dark_frame = np.ones((100, 100, 3), dtype=np.uint8) * 30
        
        processed, metadata = preprocess_frame(
            dark_frame,
            enable_low_light_enhancement=True
        )
        
        assert metadata['low_light_enhanced'] is True
        assert 'original_brightness' in metadata
        assert 'enhanced_brightness' in metadata
        assert metadata['enhanced_brightness'] > metadata['original_brightness']
    
    def test_preprocess_with_enhancement_disabled(self):
        """Test preprocessing with low-light enhancement disabled."""
        dark_frame = np.ones((100, 100, 3), dtype=np.uint8) * 30
        
        processed, metadata = preprocess_frame(
            dark_frame,
            enable_low_light_enhancement=False
        )
        
        assert metadata['low_light_enhanced'] is False
        assert 'original_brightness' in metadata
        assert 'enhanced_brightness' not in metadata
        np.testing.assert_array_equal(processed, dark_frame)
    
    def test_preprocess_bright_frame(self):
        """Test preprocessing on bright frame (no enhancement needed)."""
        bright_frame = np.ones((100, 100, 3), dtype=np.uint8) * 150
        
        processed, metadata = preprocess_frame(bright_frame)
        
        assert metadata['low_light_enhanced'] is False
        assert metadata['original_brightness'] >= 50.0
        np.testing.assert_array_equal(processed, bright_frame)
    
    def test_metadata_structure(self):
        """Test that metadata has expected structure."""
        frame = np.ones((100, 100, 3), dtype=np.uint8) * 100
        
        _, metadata = preprocess_frame(frame)
        
        assert 'low_light_enhanced' in metadata
        assert 'original_brightness' in metadata
        assert isinstance(metadata['low_light_enhanced'], bool)
        assert isinstance(metadata['original_brightness'], float)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
