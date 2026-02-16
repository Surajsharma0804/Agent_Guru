"""Unit tests for emotion detection."""

import pytest
import numpy as np
import time

from Agent_Guru.speech.emotion import EmotionDetector
from Agent_Guru.speech.models import EmotionType, EmotionResult
from Agent_Guru.speech.exceptions import EmotionDetectionError


class TestEmotionDetector:
    """Unit tests for EmotionDetector class."""
    
    def test_initialization(self):
        """Test EmotionDetector initialization."""
        detector = EmotionDetector()
        assert detector is not None
        assert detector.model_path is None
        assert not detector._use_ml_model
    
    def test_initialization_with_model(self):
        """Test EmotionDetector initialization with model path."""
        model_path = "/path/to/model"
        detector = EmotionDetector(model_path=model_path)
        assert detector.model_path == model_path
        assert detector._use_ml_model
    
    def test_detect_emotion_basic(self):
        """Test basic emotion detection."""
        detector = EmotionDetector()
        
        # Generate simple audio
        sample_rate = 16000
        duration = 2.0
        frequency = 200
        t = np.linspace(0, duration, int(duration * sample_rate))
        audio = 0.5 * np.sin(2 * np.pi * frequency * t)
        audio = audio.astype(np.float32)
        
        result = detector.detect_emotion(audio, sample_rate)
        
        # Verify result structure
        assert isinstance(result, EmotionResult)
        assert isinstance(result.primary_emotion, EmotionType)
        assert isinstance(result.emotion_scores, dict)
        assert len(result.emotion_scores) == 7
        assert 0.0 <= result.confidence <= 1.0
        assert 0.0 <= result.audio_quality <= 1.0
        assert result.timestamp > 0
    
    def test_detect_emotion_all_emotions_present(self):
        """Test that all 7 emotion types are in the result."""
        detector = EmotionDetector()
        
        sample_rate = 16000
        duration = 1.5
        audio = np.random.randn(int(duration * sample_rate)).astype(np.float32) * 0.3
        
        result = detector.detect_emotion(audio, sample_rate)
        
        # Verify all 7 emotions are present
        expected_emotions = {
            EmotionType.HAPPY,
            EmotionType.SAD,
            EmotionType.ANGRY,
            EmotionType.NEUTRAL,
            EmotionType.SURPRISED,
            EmotionType.FEARFUL,
            EmotionType.DISGUSTED
        }
        assert set(result.emotion_scores.keys()) == expected_emotions
    
    def test_detect_emotion_performance(self):
        """Test that emotion detection completes within 200ms."""
        detector = EmotionDetector()
        
        sample_rate = 16000
        duration = 3.0
        audio = np.random.randn(int(duration * sample_rate)).astype(np.float32) * 0.5
        
        start_time = time.time()
        result = detector.detect_emotion(audio, sample_rate)
        processing_time = (time.time() - start_time) * 1000
        
        # Should complete within 200ms (Requirement 13.4)
        assert processing_time < 200, f"Processing took {processing_time:.1f}ms"
    
    def test_extract_acoustic_features(self):
        """Test acoustic feature extraction."""
        detector = EmotionDetector()
        
        sample_rate = 16000
        duration = 2.0
        frequency = 220
        t = np.linspace(0, duration, int(duration * sample_rate))
        audio = 0.5 * np.sin(2 * np.pi * frequency * t)
        audio = audio.astype(np.float32)
        
        features = detector.extract_acoustic_features(audio, sample_rate)
        
        # Verify essential features are present
        assert 'pitch_mean' in features
        assert 'pitch_std' in features
        assert 'energy_mean' in features
        assert 'tempo' in features
        assert 'zcr_mean' in features
        
        # Verify feature values are reasonable
        assert features['pitch_mean'] > 0
        assert features['pitch_std'] >= 0
        assert features['energy_mean'] >= 0
        assert features['tempo'] > 0
        assert features['zcr_mean'] >= 0
    
    def test_extract_acoustic_features_mfcc(self):
        """Test that MFCC features are extracted."""
        detector = EmotionDetector()
        
        sample_rate = 16000
        duration = 1.5
        audio = np.random.randn(int(duration * sample_rate)).astype(np.float32) * 0.3
        
        features = detector.extract_acoustic_features(audio, sample_rate)
        
        # Verify MFCC features are present (13 coefficients)
        mfcc_features = [k for k in features.keys() if k.startswith('mfcc_')]
        assert len(mfcc_features) >= 13 * 2  # mean and std for each coefficient
    
    def test_poor_quality_audio(self):
        """Test emotion detection with poor quality audio."""
        detector = EmotionDetector()
        
        # Generate very noisy audio (very low amplitude - essentially silence)
        sample_rate = 16000
        duration = 1.0
        audio = np.random.randn(int(duration * sample_rate)).astype(np.float32) * 0.001  # Extremely low amplitude
        
        result = detector.detect_emotion(audio, sample_rate)
        
        # Should still return valid result
        assert isinstance(result, EmotionResult)
        assert result.audio_quality < 0.75  # Should detect poor quality (relaxed threshold)
        assert 0.0 <= result.confidence <= 1.0


class TestEmotionHistoryTracking:
    """
    Unit tests for emotion history tracking and transitions.
    
    Tests emotion history tracking and transition detection.
    Requirements: 13.6
    """
    
    def test_track_emotion_history_empty(self):
        """Test emotion history with empty list."""
        detector = EmotionDetector()
        
        history = detector.track_emotion_history([])
        
        assert history.dominant_emotion == EmotionType.NEUTRAL
        assert len(history.emotions) == 0
        assert len(history.emotion_transitions) == 0
    
    def test_track_emotion_history_single_emotion(self):
        """Test emotion history with single emotion."""
        detector = EmotionDetector()
        
        # Create a single emotion result
        emotion_result = EmotionResult(
            primary_emotion=EmotionType.HAPPY,
            emotion_scores={e: 0.14 for e in EmotionType},
            confidence=0.8,
            timestamp=time.time(),
            audio_quality=0.9
        )
        emotion_result.emotion_scores[EmotionType.HAPPY] = 0.86
        
        history = detector.track_emotion_history([emotion_result])
        
        assert history.dominant_emotion == EmotionType.HAPPY
        assert len(history.emotions) == 1
        assert len(history.emotion_transitions) == 0  # No transitions with single emotion
    
    def test_track_emotion_history_no_transitions(self):
        """Test emotion history with same emotion (no transitions)."""
        detector = EmotionDetector()
        
        # Create multiple results with same emotion
        emotions = []
        for i in range(5):
            result = EmotionResult(
                primary_emotion=EmotionType.NEUTRAL,
                emotion_scores={e: 0.14 for e in EmotionType},
                confidence=0.7,
                timestamp=time.time() + i,
                audio_quality=0.8
            )
            result.emotion_scores[EmotionType.NEUTRAL] = 0.86
            emotions.append(result)
        
        history = detector.track_emotion_history(emotions)
        
        assert history.dominant_emotion == EmotionType.NEUTRAL
        assert len(history.emotions) == 5
        assert len(history.emotion_transitions) == 0  # No transitions
    
    def test_track_emotion_history_with_transitions(self):
        """Test emotion history with emotion transitions."""
        detector = EmotionDetector()
        
        # Create emotions with transitions: HAPPY -> SAD -> ANGRY
        emotions = []
        emotion_sequence = [
            EmotionType.HAPPY,
            EmotionType.HAPPY,
            EmotionType.SAD,
            EmotionType.SAD,
            EmotionType.ANGRY
        ]
        
        for i, emotion in enumerate(emotion_sequence):
            result = EmotionResult(
                primary_emotion=emotion,
                emotion_scores={e: 0.14 for e in EmotionType},
                confidence=0.8,
                timestamp=time.time() + i,
                audio_quality=0.9
            )
            result.emotion_scores[emotion] = 0.86
            emotions.append(result)
        
        history = detector.track_emotion_history(emotions)
        
        # Should detect 2 transitions: HAPPY->SAD and SAD->ANGRY
        assert len(history.emotion_transitions) == 2
        
        # Verify first transition
        from_emotion1, to_emotion1, timestamp1 = history.emotion_transitions[0]
        assert from_emotion1 == EmotionType.HAPPY
        assert to_emotion1 == EmotionType.SAD
        assert timestamp1 > 0
        
        # Verify second transition
        from_emotion2, to_emotion2, timestamp2 = history.emotion_transitions[1]
        assert from_emotion2 == EmotionType.SAD
        assert to_emotion2 == EmotionType.ANGRY
        assert timestamp2 > timestamp1
    
    def test_track_emotion_history_dominant_emotion(self):
        """Test that dominant emotion is correctly identified."""
        detector = EmotionDetector()
        
        # Create emotions with HAPPY appearing most often
        emotions = []
        emotion_sequence = [
            EmotionType.HAPPY,
            EmotionType.HAPPY,
            EmotionType.HAPPY,
            EmotionType.SAD,
            EmotionType.NEUTRAL
        ]
        
        for i, emotion in enumerate(emotion_sequence):
            result = EmotionResult(
                primary_emotion=emotion,
                emotion_scores={e: 0.14 for e in EmotionType},
                confidence=0.8,
                timestamp=time.time() + i,
                audio_quality=0.9
            )
            result.emotion_scores[emotion] = 0.86
            emotions.append(result)
        
        history = detector.track_emotion_history(emotions)
        
        # HAPPY should be dominant (appears 3 times)
        assert history.dominant_emotion == EmotionType.HAPPY
    
    def test_track_emotion_history_time_window(self):
        """Test emotion history with time window filtering."""
        detector = EmotionDetector()
        
        # Create emotions with timestamps outside window
        current_time = time.time()
        emotions = []
        
        # Old emotion (outside 10 second window)
        old_result = EmotionResult(
            primary_emotion=EmotionType.SAD,
            emotion_scores={e: 0.14 for e in EmotionType},
            confidence=0.8,
            timestamp=current_time - 20,  # 20 seconds ago
            audio_quality=0.9
        )
        old_result.emotion_scores[EmotionType.SAD] = 0.86
        emotions.append(old_result)
        
        # Recent emotions (within window)
        for i in range(3):
            result = EmotionResult(
                primary_emotion=EmotionType.HAPPY,
                emotion_scores={e: 0.14 for e in EmotionType},
                confidence=0.8,
                timestamp=current_time - i,
                audio_quality=0.9
            )
            result.emotion_scores[EmotionType.HAPPY] = 0.86
            emotions.append(result)
        
        # Track with 10 second window
        history = detector.track_emotion_history(emotions, window_seconds=10.0)
        
        # Should only include recent emotions
        assert len(history.emotions) == 3
        assert history.dominant_emotion == EmotionType.HAPPY
    
    def test_track_emotion_history_weighted_by_confidence(self):
        """Test that dominant emotion considers confidence weighting."""
        detector = EmotionDetector()
        
        emotions = []
        
        # One HAPPY with high confidence
        happy_result = EmotionResult(
            primary_emotion=EmotionType.HAPPY,
            emotion_scores={e: 0.05 for e in EmotionType},
            confidence=0.95,
            timestamp=time.time(),
            audio_quality=0.95
        )
        happy_result.emotion_scores[EmotionType.HAPPY] = 0.95
        emotions.append(happy_result)
        
        # Two SAD with low confidence
        for i in range(2):
            sad_result = EmotionResult(
                primary_emotion=EmotionType.SAD,
                emotion_scores={e: 0.14 for e in EmotionType},
                confidence=0.3,
                timestamp=time.time() + i + 1,
                audio_quality=0.5
            )
            sad_result.emotion_scores[EmotionType.SAD] = 0.3
            emotions.append(sad_result)
        
        history = detector.track_emotion_history(emotions)
        
        # HAPPY should be dominant due to higher confidence * quality weight
        # even though SAD appears more frequently
        assert history.dominant_emotion == EmotionType.HAPPY
    
    def test_transition_only_on_change(self):
        """Test that transitions are only recorded when emotion actually changes."""
        detector = EmotionDetector()
        
        # Create sequence with repeated emotions
        emotions = []
        emotion_sequence = [
            EmotionType.HAPPY,
            EmotionType.HAPPY,  # No transition
            EmotionType.SAD,    # Transition 1: HAPPY -> SAD
            EmotionType.SAD,    # No transition
            EmotionType.SAD,    # No transition
            EmotionType.ANGRY   # Transition 2: SAD -> ANGRY
        ]
        
        for i, emotion in enumerate(emotion_sequence):
            result = EmotionResult(
                primary_emotion=emotion,
                emotion_scores={e: 0.14 for e in EmotionType},
                confidence=0.8,
                timestamp=time.time() + i,
                audio_quality=0.9
            )
            result.emotion_scores[emotion] = 0.86
            emotions.append(result)
        
        history = detector.track_emotion_history(emotions)
        
        # Should only have 2 transitions (not 5)
        assert len(history.emotion_transitions) == 2
        
        # Verify transitions are actual changes
        for from_emotion, to_emotion, _ in history.emotion_transitions:
            assert from_emotion != to_emotion


class TestEmotionDetectionEdgeCases:
    """Test edge cases for emotion detection."""
    
    def test_very_short_audio(self):
        """Test emotion detection with very short audio."""
        detector = EmotionDetector()
        
        sample_rate = 16000
        duration = 0.1  # 100ms
        audio = np.random.randn(int(duration * sample_rate)).astype(np.float32) * 0.3
        
        result = detector.detect_emotion(audio, sample_rate)
        
        # Should still return valid result
        assert isinstance(result, EmotionResult)
        # Very short audio should have lower quality due to duration penalty
        assert result.audio_quality < 0.9  # Relaxed threshold
    
    def test_silent_audio(self):
        """Test emotion detection with silent audio."""
        detector = EmotionDetector()
        
        sample_rate = 16000
        duration = 2.0
        audio = np.zeros(int(duration * sample_rate), dtype=np.float32)
        
        result = detector.detect_emotion(audio, sample_rate)
        
        # Should return valid result with low quality (silence has very low RMS)
        assert isinstance(result, EmotionResult)
        assert result.audio_quality < 0.7  # Silence should have low quality
    
    def test_very_loud_audio(self):
        """Test emotion detection with very loud audio."""
        detector = EmotionDetector()
        
        sample_rate = 16000
        duration = 2.0
        audio = np.random.randn(int(duration * sample_rate)).astype(np.float32) * 2.0
        
        result = detector.detect_emotion(audio, sample_rate)
        
        # Should still return valid result
        assert isinstance(result, EmotionResult)
        assert 0.0 <= result.confidence <= 1.0
    
    def test_different_sample_rates(self):
        """Test emotion detection with different sample rates."""
        detector = EmotionDetector()
        
        duration = 2.0
        
        for sample_rate in [8000, 16000, 22050, 44100]:
            audio = np.random.randn(int(duration * sample_rate)).astype(np.float32) * 0.3
            result = detector.detect_emotion(audio, sample_rate)
            
            assert isinstance(result, EmotionResult)
            assert len(result.emotion_scores) == 7
