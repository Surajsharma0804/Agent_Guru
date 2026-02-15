"""
Property-based tests for EmotionRecognizer module.

These tests validate universal properties that should hold across all inputs:
- Property 11: Emotion Classification Categories
- Property 12: Emotion Confidence Completeness

Uses Hypothesis for property-based testing to generate diverse test cases.
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings, assume
from guru_vision.emotion import EmotionRecognizer, EmotionResult


# Strategy for generating valid face images (112x112x3)
@st.composite
def valid_face_image(draw):
    """Generate a valid face image for testing."""
    # Generate random seed for reproducibility
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    rng = np.random.RandomState(seed)
    
    # Create face with some variation to avoid all-zero or invalid images
    face = rng.randint(10, 246, size=(112, 112, 3), dtype=np.uint8)
    
    return face


class TestEmotionRecognizerProperties:
    """Property-based tests for EmotionRecognizer."""
    
    @given(face=valid_face_image())
    @settings(max_examples=50, deadline=5000)
    def test_property_11_emotion_classification_categories(self, face):
        """
        Property 11: Emotion Classification Categories
        
        For any face input to the Emotion_Recognizer, the dominant emotion 
        should be one of exactly seven categories: neutral, happy, sad, angry, 
        surprised, fearful, or disgusted.
        
        Validates: Requirements 8.1
        """
        # Initialize recognizer
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Run recognition
        result = recognizer.recognize(face)
        
        # Property: dominant_emotion must be one of the seven categories
        expected_categories = [
            "neutral", "happy", "sad", "angry", 
            "surprised", "fearful", "disgusted"
        ]
        assert result.dominant_emotion in expected_categories, (
            f"Dominant emotion '{result.dominant_emotion}' is not in "
            f"expected categories: {expected_categories}"
        )
    
    @given(face=valid_face_image())
    @settings(max_examples=50, deadline=5000)
    def test_property_12_emotion_confidence_completeness(self, face):
        """
        Property 12: Emotion Confidence Completeness
        
        For any face analyzed for emotion, the result should include confidence 
        scores for all seven emotion categories.
        
        Validates: Requirements 8.2
        """
        # Initialize recognizer
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Run recognition
        result = recognizer.recognize(face)
        
        # Property: all_scores must contain all seven emotion categories
        expected_categories = [
            "neutral", "happy", "sad", "angry", 
            "surprised", "fearful", "disgusted"
        ]
        
        # Check that all categories are present
        for emotion in expected_categories:
            assert emotion in result.all_scores, (
                f"Emotion category '{emotion}' is missing from all_scores"
            )
        
        # Check that all scores are valid probabilities (0.0 to 1.0)
        for emotion, score in result.all_scores.items():
            assert 0.0 <= score <= 1.0, (
                f"Score for '{emotion}' is {score}, which is outside [0.0, 1.0]"
            )
        
        # Check that we have exactly 7 categories (no extra ones)
        assert len(result.all_scores) == 7, (
            f"Expected exactly 7 emotion categories, got {len(result.all_scores)}"
        )
    
    @given(face=valid_face_image())
    @settings(max_examples=30, deadline=5000)
    def test_dominant_emotion_has_highest_score(self, face):
        """
        Additional property: The dominant emotion should correspond to the 
        emotion with the highest confidence score (unless confidence is too low).
        """
        # Initialize recognizer
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Run recognition
        result = recognizer.recognize(face)
        
        # Find emotion with highest score
        max_emotion = max(result.all_scores, key=result.all_scores.get)
        max_score = result.all_scores[max_emotion]
        
        # Property: If max score >= 0.3, dominant should match
        # If max score < 0.3, dominant should be "neutral" (fallback)
        if max_score >= 0.3:
            assert result.dominant_emotion == max_emotion, (
                f"Dominant emotion '{result.dominant_emotion}' does not match "
                f"emotion with highest score '{max_emotion}' ({max_score})"
            )
        else:
            assert result.dominant_emotion == "neutral", (
                f"When max score is low ({max_score}), dominant emotion should "
                f"be 'neutral', but got '{result.dominant_emotion}'"
            )
    
    @given(face=valid_face_image())
    @settings(max_examples=30, deadline=5000)
    def test_confidence_matches_dominant_score(self, face):
        """
        Additional property: The confidence value should match the score of 
        the dominant emotion in all_scores.
        """
        # Initialize recognizer
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Run recognition
        result = recognizer.recognize(face)
        
        # Property: confidence should match the score of dominant_emotion
        dominant_score = result.all_scores[result.dominant_emotion]
        
        # Allow small floating point differences
        assert abs(result.confidence - dominant_score) < 0.01, (
            f"Confidence {result.confidence} does not match score for "
            f"dominant emotion '{result.dominant_emotion}' ({dominant_score})"
        )
    
    @given(face=valid_face_image())
    @settings(max_examples=30, deadline=5000)
    def test_result_structure_consistency(self, face):
        """
        Additional property: The EmotionResult should always have consistent 
        structure with all required fields.
        """
        # Initialize recognizer
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Run recognition
        result = recognizer.recognize(face)
        
        # Property: Result must be EmotionResult instance
        assert isinstance(result, EmotionResult)
        
        # Property: All fields must be present and correct types
        assert isinstance(result.dominant_emotion, str)
        assert isinstance(result.confidence, float)
        assert isinstance(result.all_scores, dict)
        
        # Property: Confidence must be in valid range
        assert 0.0 <= result.confidence <= 1.0
    
    def test_deterministic_recognition(self):
        """
        Additional property: Recognition should be deterministic - same input 
        should produce same output.
        """
        # Initialize recognizer
        recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
        
        # Create a specific test face
        test_face = np.random.RandomState(42).randint(1, 255, (112, 112, 3), dtype=np.uint8)
        
        # Run recognition multiple times
        result1 = recognizer.recognize(test_face)
        result2 = recognizer.recognize(test_face)
        result3 = recognizer.recognize(test_face)
        
        # Property: All results should be identical
        assert result1.dominant_emotion == result2.dominant_emotion == result3.dominant_emotion
        assert result1.confidence == result2.confidence == result3.confidence
        assert result1.all_scores == result2.all_scores == result3.all_scores


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
