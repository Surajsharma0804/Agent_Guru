"""
Unit tests for EmotionRecognizer module.

Tests basic functionality of emotion recognition including:
- Initialization
- Input validation
- Emotion classification
- Result structure
"""

import pytest
import numpy as np
from guru_vision.emotion import EmotionRecognizer, EmotionResult


class TestEmotionRecognizer:
    """Test suite for EmotionRecognizer class."""
    
    def test_initialization(self):
        """Test that EmotionRecognizer initializes correctly."""
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        assert recognizer is not None
        assert recognizer.model_name == "fer"
        assert recognizer.use_gpu == False
    
    def test_emotion_categories(self):
        """Test that all seven emotion categories are defined."""
        expected_categories = [
            "neutral", "happy", "sad", "angry", 
            "surprised", "fearful", "disgusted"
        ]
        assert EmotionRecognizer.EMOTION_CATEGORIES == expected_categories
    
    def test_recognize_valid_input(self):
        """Test emotion recognition with valid input."""
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Create a valid test face (112x112x3)
        test_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        
        # Run recognition
        result = recognizer.recognize(test_face)
        
        # Verify result structure
        assert isinstance(result, EmotionResult)
        assert isinstance(result.dominant_emotion, str)
        assert isinstance(result.confidence, float)
        assert isinstance(result.all_scores, dict)
    
    def test_recognize_returns_valid_emotion(self):
        """Test that recognized emotion is one of the seven categories."""
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Create a valid test face
        test_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        
        # Run recognition
        result = recognizer.recognize(test_face)
        
        # Verify dominant emotion is valid
        assert result.dominant_emotion in EmotionRecognizer.EMOTION_CATEGORIES
    
    def test_recognize_confidence_range(self):
        """Test that confidence scores are in valid range [0, 1]."""
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Create a valid test face
        test_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        
        # Run recognition
        result = recognizer.recognize(test_face)
        
        # Verify confidence is in valid range
        assert 0.0 <= result.confidence <= 1.0
    
    def test_recognize_all_scores_completeness(self):
        """Test that all_scores contains all seven emotion categories."""
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Create a valid test face
        test_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        
        # Run recognition
        result = recognizer.recognize(test_face)
        
        # Verify all emotion categories are present
        for emotion in EmotionRecognizer.EMOTION_CATEGORIES:
            assert emotion in result.all_scores
            assert 0.0 <= result.all_scores[emotion] <= 1.0
    
    def test_recognize_invalid_shape(self):
        """Test that invalid input shape raises ValueError."""
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Create invalid input (wrong shape)
        invalid_face = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Input face must be 112x112x3"):
            recognizer.recognize(invalid_face)
    
    def test_recognize_all_zeros(self):
        """Test that all-zero input raises ValueError."""
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Create all-zero input
        zero_face = np.zeros((112, 112, 3), dtype=np.uint8)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="invalid data"):
            recognizer.recognize(zero_face)
    
    def test_recognize_nan_input(self):
        """Test that NaN input raises ValueError."""
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Create input with NaN
        nan_face = np.full((112, 112, 3), np.nan, dtype=np.float32)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="invalid data"):
            recognizer.recognize(nan_face)
    
    def test_dominant_emotion_matches_highest_score(self):
        """Test that dominant emotion corresponds to highest score."""
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Create a valid test face
        test_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        
        # Run recognition
        result = recognizer.recognize(test_face)
        
        # Find emotion with highest score
        max_emotion = max(result.all_scores, key=result.all_scores.get)
        max_score = result.all_scores[max_emotion]
        
        # Dominant emotion should match (or be neutral if confidence too low)
        if max_score >= 0.3:
            assert result.dominant_emotion == max_emotion
        else:
            # Low confidence should default to neutral
            assert result.dominant_emotion == "neutral"
    
    def test_multiple_recognitions_consistent(self):
        """Test that multiple recognitions of same face are consistent."""
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Create a valid test face
        test_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        
        # Run recognition twice
        result1 = recognizer.recognize(test_face)
        result2 = recognizer.recognize(test_face)
        
        # Results should be identical
        assert result1.dominant_emotion == result2.dominant_emotion
        assert result1.confidence == result2.confidence
        assert result1.all_scores == result2.all_scores


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
