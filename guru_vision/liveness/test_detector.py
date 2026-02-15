"""
Unit tests for LivenessDetector module.

Tests basic functionality of the liveness detection system.
"""

import pytest
import numpy as np
from guru_vision.liveness import LivenessDetector, LivenessResult


class TestLivenessDetector:
    """Test suite for LivenessDetector class."""
    
    def test_detector_initialization_without_model(self):
        """Test that detector can be initialized without a model file."""
        detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
        assert detector is not None
        assert detector.use_gpu is False
        assert detector.model_loaded is False
    
    def test_detect_with_valid_face(self):
        """Test detection with a valid aligned face image."""
        detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
        
        # Create a synthetic face image (112x112x3)
        face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        
        # Run detection
        result = detector.detect(face)
        
        # Verify result structure
        assert isinstance(result, LivenessResult)
        assert isinstance(result.is_live, bool)
        assert isinstance(result.confidence, float)
        assert isinstance(result.attack_type, str)
        
        # Verify confidence is in valid range
        assert 0.0 <= result.confidence <= 1.0
        
        # Verify attack_type is one of the expected values
        assert result.attack_type in ["none", "photo", "screen", "mask", "unknown"]
    
    def test_detect_with_invalid_shape(self):
        """Test that detector raises error for invalid input shape."""
        detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
        
        # Create image with wrong shape
        face = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Input face must be 112x112x3"):
            detector.detect(face)
    
    def test_detect_with_all_zeros(self):
        """Test that detector raises error for all-zero input."""
        detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
        
        # Create all-zero image
        face = np.zeros((112, 112, 3), dtype=np.uint8)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="invalid data"):
            detector.detect(face)
    
    def test_detect_with_nan_values(self):
        """Test that detector raises error for NaN input."""
        detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
        
        # Create image with NaN values
        face = np.full((112, 112, 3), np.nan, dtype=np.float32)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="invalid data"):
            detector.detect(face)
    
    def test_liveness_result_binary_classification(self):
        """Test that is_live is always boolean (binary classification)."""
        detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
        
        # Test with multiple random faces
        for _ in range(10):
            face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
            result = detector.detect(face)
            
            # is_live must be exactly True or False (binary)
            assert result.is_live in [True, False]
            assert isinstance(result.is_live, bool)
    
    def test_attack_type_values(self):
        """Test that attack_type is one of the expected values."""
        detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
        
        # Test with multiple random faces
        valid_attack_types = ["none", "photo", "screen", "mask", "unknown"]
        
        for _ in range(10):
            face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
            result = detector.detect(face)
            
            # attack_type must be one of the expected values
            assert result.attack_type in valid_attack_types
    
    def test_confidence_range(self):
        """Test that confidence is always in [0, 1] range."""
        detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
        
        # Test with multiple random faces
        for _ in range(10):
            face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
            result = detector.detect(face)
            
            # Confidence must be in [0, 1]
            assert 0.0 <= result.confidence <= 1.0
    
    def test_texture_analysis_fallback(self):
        """Test that texture analysis fallback works."""
        detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
        
        # Create a face with high texture (should be more likely to be live)
        high_texture_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        
        # Create a face with low texture (should be more likely to be spoof)
        low_texture_face = np.ones((112, 112, 3), dtype=np.uint8) * 128
        
        result_high = detector.detect(high_texture_face)
        result_low = detector.detect(low_texture_face)
        
        # Both should return valid results
        assert isinstance(result_high, LivenessResult)
        assert isinstance(result_low, LivenessResult)
    
    def test_consistent_results_for_same_input(self):
        """Test that detector returns consistent results for the same input."""
        detector = LivenessDetector(model_path="/nonexistent/path.onnx", use_gpu=False)
        
        # Create a face
        face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        
        # Run detection twice
        result1 = detector.detect(face)
        result2 = detector.detect(face)
        
        # Results should be identical
        assert result1.is_live == result2.is_live
        assert result1.confidence == result2.confidence
        assert result1.attack_type == result2.attack_type


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
