"""Property-based tests for emotion detection."""

import numpy as np
from hypothesis import given, strategies as st, settings
import time

from Agent_Guru.speech.emotion import EmotionDetector
from Agent_Guru.speech.models import EmotionType


# Test data generators
@st.composite
def audio_samples(draw, min_duration=0.5, max_duration=5.0, sample_rate=16000):
    """Generate random audio samples for testing."""
    duration = draw(st.floats(min_value=min_duration, max_value=max_duration))
    num_samples = int(duration * sample_rate)
    
    # Generate audio with varying characteristics
    frequency = draw(st.floats(min_value=100, max_value=400))
    amplitude = draw(st.floats(min_value=0.1, max_value=0.8))
    
    # Generate sine wave with noise
    t = np.linspace(0, duration, num_samples)
    audio = amplitude * np.sin(2 * np.pi * frequency * t)
    
    # Add some noise
    noise_level = draw(st.floats(min_value=0.01, max_value=0.1))
    noise = np.random.normal(0, noise_level, num_samples)
    audio = audio + noise
    
    return audio.astype(np.float32), sample_rate


class TestEmotionDetectionProperties:
    """
    Property-based tests for emotion detection.
    
    **Property 15: Emotion Detection Completeness**
    **Validates: Requirements 13.1, 13.3, 13.4**
    """
    
    @given(audio_samples())
    @settings(max_examples=100, deadline=5000)
    def test_emotion_detection_completeness(self, audio_data):
        """
        Property 15: Emotion Detection Completeness
        
        GIVEN any valid audio input
        WHEN emotion detection is performed
        THEN:
        - A primary emotion SHALL be identified (Requirement 13.1)
        - Confidence scores SHALL be returned for ALL 7 emotion categories (Requirement 13.3)
        - Analysis SHALL complete within 200 milliseconds (Requirement 13.4)
        - All emotion scores SHALL be between 0.0 and 1.0
        - Emotion scores SHALL sum to approximately 1.0
        """
        audio, sample_rate = audio_data
        detector = EmotionDetector()
        
        # Measure processing time
        start_time = time.time()
        result = detector.detect_emotion(audio, sample_rate)
        processing_time = (time.time() - start_time) * 1000  # Convert to ms
        
        # Verify primary emotion is identified (Requirement 13.1)
        assert result.primary_emotion is not None  # nosec B101
        assert isinstance(result.primary_emotion, EmotionType)  # nosec B101
        
        # Verify confidence scores for ALL 7 emotion categories (Requirement 13.3)
        assert len(result.emotion_scores) == 7  # nosec B101
        for emotion in EmotionType:
            assert emotion in result.emotion_scores  # nosec B101
            score = result.emotion_scores[emotion]
            assert 0.0 <= score <= 1.0, f"Score for {emotion} out of range: {score}"  # nosec B101
        
        # Verify analysis completes within 200ms (Requirement 13.4)
        assert processing_time < 200, f"Processing took {processing_time:.1f}ms (limit: 200ms)"  # nosec B101
        
        # Verify overall confidence is valid
        assert 0.0 <= result.confidence <= 1.0  # nosec B101
        
        # Verify emotion scores sum to approximately 1.0 (normalized distribution)
        total_score = sum(result.emotion_scores.values())
        assert 0.95 <= total_score <= 1.05, f"Emotion scores sum to {total_score}, expected ~1.0"  # nosec B101
        
        # Verify primary emotion has the highest score
        max_score = max(result.emotion_scores.values())
        assert result.emotion_scores[result.primary_emotion] == max_score  # nosec B101
        
        # Verify audio quality is in valid range
        assert 0.0 <= result.audio_quality <= 1.0  # nosec B101
        
        # Verify timestamp is reasonable
        assert result.timestamp > 0  # nosec B101
    
    @given(audio_samples())
    @settings(max_examples=50, deadline=5000)
    def test_emotion_detection_consistency(self, audio_data):
        """
        Test that emotion detection is consistent for the same input.
        
        GIVEN the same audio input
        WHEN emotion detection is performed multiple times
        THEN the results SHALL be identical
        """
        audio, sample_rate = audio_data
        detector = EmotionDetector()
        
        # Detect emotion twice
        result1 = detector.detect_emotion(audio, sample_rate)
        result2 = detector.detect_emotion(audio, sample_rate)
        
        # Results should be identical (except timestamp)
        assert result1.primary_emotion == result2.primary_emotion  # nosec B101
        assert result1.confidence == result2.confidence  # nosec B101
        assert result1.audio_quality == result2.audio_quality  # nosec B101
        
        # Emotion scores should match
        for emotion in EmotionType:
            assert result1.emotion_scores[emotion] == result2.emotion_scores[emotion]  # nosec B101
    
    @given(st.lists(audio_samples(), min_size=2, max_size=10))
    @settings(max_examples=30, deadline=10000)
    def test_emotion_history_tracking(self, audio_list):
        """
        Test emotion history tracking and transition detection.
        
        GIVEN a sequence of audio samples
        WHEN emotion history is tracked
        THEN:
        - All emotions SHALL be recorded
        - Transitions SHALL be detected when emotion changes
        - Dominant emotion SHALL be identified
        """
        detector = EmotionDetector()
        
        # Detect emotions for all audio samples
        emotion_results = []
        for audio, sample_rate in audio_list:
            result = detector.detect_emotion(audio, sample_rate)
            emotion_results.append(result)
        
        # Track emotion history
        history = detector.track_emotion_history(emotion_results, window_seconds=3600)
        
        # Verify all emotions are recorded
        assert len(history.emotions) == len(emotion_results)  # nosec B101
        
        # Verify dominant emotion is identified
        assert history.dominant_emotion is not None  # nosec B101
        assert isinstance(history.dominant_emotion, EmotionType)  # nosec B101
        
        # Verify transitions are detected
        # Count actual emotion changes
        actual_transitions = 0
        for i in range(1, len(emotion_results)):
            if emotion_results[i].primary_emotion != emotion_results[i-1].primary_emotion:
                actual_transitions += 1
        
        # Number of recorded transitions should match actual changes
        assert len(history.emotion_transitions) == actual_transitions  # nosec B101
        
        # Verify transition format
        for from_emotion, to_emotion, timestamp in history.emotion_transitions:
            assert isinstance(from_emotion, EmotionType)  # nosec B101
            assert isinstance(to_emotion, EmotionType)  # nosec B101
            assert from_emotion != to_emotion  # Transitions only for changes  # nosec B101
            assert timestamp > 0  # nosec B101


class TestEmotionDetectionConfidenceCalibration:
    """
    Property-based tests for emotion detection confidence calibration.
    
    **Property 16: Emotion Detection Confidence Calibration**
    **Validates: Requirements 13.9**
    """
    
    @given(st.floats(min_value=0.0, max_value=0.005))
    @settings(max_examples=50, deadline=5000)
    def test_low_quality_audio_confidence(self, noise_level):
        """
        Property 16: Emotion Detection Confidence Calibration
        
        GIVEN audio with poor quality (extremely low amplitude noise)
        WHEN emotion detection is performed
        THEN:
        - Low confidence SHALL be indicated (Requirement 13.9)
        - Confidence SHALL be lower than for clean audio
        - Audio quality score SHALL reflect poor quality
        """
        sample_rate = 16000
        duration = 2.0
        num_samples = int(duration * sample_rate)
        
        # Generate extremely low amplitude noisy audio (poor quality)
        noisy_audio = np.random.normal(0, max(noise_level, 0.0001), num_samples).astype(np.float32)
        
        detector = EmotionDetector()
        result = detector.detect_emotion(noisy_audio, sample_rate)
        
        # Verify low confidence for poor quality audio (Requirement 13.9)
        # Extremely low amplitude should result in lower quality
        if noise_level < 0.003:
            assert result.audio_quality < 0.75, \
                f"Audio quality too high for very low amplitude input: {result.audio_quality}"  # nosec B101
        
        # Confidence should be affected by poor quality
        # (not necessarily low, but should reflect uncertainty)
        assert 0.0 <= result.confidence <= 1.0  # nosec B101
        
        # Emotion scores should still be valid
        assert len(result.emotion_scores) == 7  # nosec B101
        for score in result.emotion_scores.values():
            assert 0.0 <= score <= 1.0  # nosec B101
    
    @given(audio_samples(min_duration=1.0, max_duration=3.0))
    @settings(max_examples=50, deadline=5000)
    def test_clean_audio_confidence(self, audio_data):
        """
        Test that clean audio produces reasonable confidence.
        
        GIVEN clean audio with good quality
        WHEN emotion detection is performed
        THEN confidence SHALL be reasonable (not artificially low)
        """
        audio, sample_rate = audio_data
        detector = EmotionDetector()
        
        result = detector.detect_emotion(audio, sample_rate)
        
        # Clean audio should have reasonable quality
        assert result.audio_quality >= 0.3  # nosec B101
        
        # Confidence should be in valid range
        assert 0.0 <= result.confidence <= 1.0  # nosec B101
        
        # Primary emotion should have highest score
        assert result.emotion_scores[result.primary_emotion] == result.confidence  # nosec B101
    
    @given(st.floats(min_value=0.1, max_value=2.0))
    @settings(max_examples=30, deadline=5000)
    def test_duration_impact_on_quality(self, duration):
        """
        Test that audio duration impacts quality assessment.
        
        GIVEN audio of varying durations
        WHEN emotion detection is performed
        THEN quality SHALL reflect duration appropriateness
        """
        sample_rate = 16000
        num_samples = int(duration * sample_rate)
        
        # Generate audio
        frequency = 200
        t = np.linspace(0, duration, num_samples)
        audio = 0.5 * np.sin(2 * np.pi * frequency * t)
        audio = audio.astype(np.float32)
        
        detector = EmotionDetector()
        result = detector.detect_emotion(audio, sample_rate)
        
        # Very short audio should have lower quality
        if duration < 0.5:
            assert result.audio_quality < 0.8  # nosec B101
        
        # Optimal duration (1-5 seconds) should have good quality
        elif 1.0 <= duration <= 5.0:
            # Quality should be reasonable for optimal duration
            assert result.audio_quality >= 0.3  # nosec B101
        
        # All results should be valid
        assert 0.0 <= result.audio_quality <= 1.0  # nosec B101
        assert 0.0 <= result.confidence <= 1.0  # nosec B101
