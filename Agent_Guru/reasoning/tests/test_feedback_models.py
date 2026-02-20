"""
Unit tests for feedback data models.

Tests cover:
- IntentFeedback validation and methods
- ModelPerformanceMetrics validation and drift detection
- Edge cases and error handling
"""

import pytest
from datetime import datetime
from Agent_Guru.reasoning.models.feedback import (
    IntentFeedback,
    FeedbackType,
    ModelPerformanceMetrics
)


class TestIntentFeedback:
    """Unit tests for IntentFeedback model."""
    
    def test_valid_feedback_creation(self):
        """Test creating valid feedback."""
        feedback = IntentFeedback(
            feedback_id="test-123",
            user_id="user-456",
            original_input="set timer for 5 minutes",
            predicted_intent="set_timer",
            predicted_entities={"duration": "5 minutes"},
            predicted_confidence=0.95,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v1.0"
        )
        
        assert feedback.feedback_id == "test-123"
        assert feedback.user_id == "user-456"
        assert feedback.original_input == "set timer for 5 minutes"
        assert feedback.predicted_intent == "set_timer"
        assert feedback.predicted_confidence == 0.95
        assert feedback.feedback_type == FeedbackType.POSITIVE
    
    def test_feedback_with_correction(self):
        """Test feedback with intent correction."""
        feedback = IntentFeedback(
            feedback_id="test-123",
            user_id="user-456",
            original_input="play some music",
            predicted_intent="search_music",
            predicted_entities={},
            predicted_confidence=0.75,
            correct_intent="play_music",
            feedback_type=FeedbackType.INTENT_CORRECTION,
            model_version="v1.0"
        )
        
        assert feedback.correct_intent == "play_music"
        assert feedback.is_correction()
        assert not feedback.was_correct()
        assert feedback.get_training_label() == "play_music"
    
    def test_empty_input_validation(self):
        """Test validation rejects empty input."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            IntentFeedback(
                feedback_id="test-123",
                user_id="user-456",
                original_input="",
                predicted_intent="test",
                predicted_entities={},
                predicted_confidence=0.9,
                feedback_type=FeedbackType.POSITIVE,
                model_version="v1.0"
            )
    
    def test_whitespace_input_validation(self):
        """Test validation rejects whitespace-only input."""
        with pytest.raises(ValueError, match="Original input cannot be empty"):
            IntentFeedback(
                feedback_id="test-123",
                user_id="user-456",
                original_input="   ",
                predicted_intent="test",
                predicted_entities={},
                predicted_confidence=0.9,
                feedback_type=FeedbackType.POSITIVE,
                model_version="v1.0"
            )
    
    def test_empty_predicted_intent_validation(self):
        """Test validation rejects empty predicted intent."""
        with pytest.raises(ValueError, match="Predicted intent cannot be empty"):
            IntentFeedback(
                feedback_id="test-123",
                user_id="user-456",
                original_input="test input",
                predicted_intent="",
                predicted_entities={},
                predicted_confidence=0.9,
                feedback_type=FeedbackType.POSITIVE,
                model_version="v1.0"
            )
    
    def test_confidence_range_validation(self):
        """Test confidence must be between 0 and 1."""
        with pytest.raises(ValueError):
            IntentFeedback(
                feedback_id="test-123",
                user_id="user-456",
                original_input="test",
                predicted_intent="test",
                predicted_entities={},
                predicted_confidence=1.5,
                feedback_type=FeedbackType.POSITIVE,
                model_version="v1.0"
            )
    
    def test_is_correction_method(self):
        """Test is_correction method."""
        # Positive feedback is not a correction
        feedback = IntentFeedback(
            feedback_id="test-123",
            user_id="user-456",
            original_input="test",
            predicted_intent="test",
            predicted_entities={},
            predicted_confidence=0.9,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v1.0"
        )
        assert not feedback.is_correction()
        
        # Intent correction is a correction
        feedback.feedback_type = FeedbackType.INTENT_CORRECTION
        assert feedback.is_correction()
        
        # Entity correction is a correction
        feedback.feedback_type = FeedbackType.ENTITY_CORRECTION
        assert feedback.is_correction()
        
        # Negative feedback is a correction
        feedback.feedback_type = FeedbackType.NEGATIVE
        assert feedback.is_correction()
    
    def test_was_correct_method(self):
        """Test was_correct method."""
        feedback = IntentFeedback(
            feedback_id="test-123",
            user_id="user-456",
            original_input="test",
            predicted_intent="test",
            predicted_entities={},
            predicted_confidence=0.9,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v1.0"
        )
        
        assert feedback.was_correct()
        
        feedback.feedback_type = FeedbackType.NEGATIVE
        assert not feedback.was_correct()
    
    def test_get_training_label_with_correction(self):
        """Test get_training_label returns correct intent."""
        feedback = IntentFeedback(
            feedback_id="test-123",
            user_id="user-456",
            original_input="test",
            predicted_intent="wrong_intent",
            predicted_entities={},
            predicted_confidence=0.9,
            correct_intent="correct_intent",
            feedback_type=FeedbackType.INTENT_CORRECTION,
            model_version="v1.0"
        )
        
        assert feedback.get_training_label() == "correct_intent"
    
    def test_get_training_label_without_correction(self):
        """Test get_training_label returns predicted intent when no correction."""
        feedback = IntentFeedback(
            feedback_id="test-123",
            user_id="user-456",
            original_input="test",
            predicted_intent="test_intent",
            predicted_entities={},
            predicted_confidence=0.9,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v1.0"
        )
        
        assert feedback.get_training_label() == "test_intent"
    
    def test_default_timestamp(self):
        """Test timestamp defaults to current time."""
        before = datetime.utcnow()
        feedback = IntentFeedback(
            feedback_id="test-123",
            user_id="user-456",
            original_input="test",
            predicted_intent="test",
            predicted_entities={},
            predicted_confidence=0.9,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v1.0"
        )
        after = datetime.utcnow()
        
        assert before <= feedback.timestamp <= after
    
    def test_metadata_defaults_to_empty_dict(self):
        """Test metadata defaults to empty dictionary."""
        feedback = IntentFeedback(
            feedback_id="test-123",
            user_id="user-456",
            original_input="test",
            predicted_intent="test",
            predicted_entities={},
            predicted_confidence=0.9,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v1.0"
        )
        
        assert feedback.metadata == {}
    
    def test_input_trimming(self):
        """Test input is trimmed of whitespace."""
        feedback = IntentFeedback(
            feedback_id="test-123",
            user_id="user-456",
            original_input="  test input  ",
            predicted_intent="  test  ",
            predicted_entities={},
            predicted_confidence=0.9,
            feedback_type=FeedbackType.POSITIVE,
            model_version="v1.0"
        )
        
        assert feedback.original_input == "test input"
        assert feedback.predicted_intent == "test"


class TestModelPerformanceMetrics:
    """Unit tests for ModelPerformanceMetrics model."""
    
    def test_valid_metrics_creation(self):
        """Test creating valid metrics."""
        metrics = ModelPerformanceMetrics(
            metric_id="metric-123",
            model_version="v1.0",
            total_predictions=100,
            correct_predictions=95,
            accuracy=0.95,
            intent_accuracies={"set_timer": 0.98, "play_music": 0.92},
            avg_confidence=0.93,
            low_confidence_rate=0.05,
            correction_rate=0.03
        )
        
        assert metrics.metric_id == "metric-123"
        assert metrics.model_version == "v1.0"
        assert metrics.total_predictions == 100
        assert metrics.correct_predictions == 95
        assert metrics.accuracy == 0.95
    
    def test_correct_predictions_validation(self):
        """Test correct predictions cannot exceed total."""
        with pytest.raises(ValueError, match="Correct predictions cannot exceed total"):
            ModelPerformanceMetrics(
                metric_id="metric-123",
                model_version="v1.0",
                total_predictions=100,
                correct_predictions=150,
                accuracy=0.95,
                avg_confidence=0.93,
                low_confidence_rate=0.05,
                correction_rate=0.03
            )
    
    def test_accuracy_range_validation(self):
        """Test accuracy must be between 0 and 1."""
        with pytest.raises(ValueError):
            ModelPerformanceMetrics(
                metric_id="metric-123",
                model_version="v1.0",
                total_predictions=100,
                correct_predictions=95,
                accuracy=1.5,
                avg_confidence=0.93,
                low_confidence_rate=0.05,
                correction_rate=0.03
            )
    
    def test_has_drift_no_drift(self):
        """Test has_drift returns False when no drift."""
        metrics = ModelPerformanceMetrics(
            metric_id="metric-123",
            model_version="v1.0",
            total_predictions=100,
            correct_predictions=94,
            accuracy=0.94,
            avg_confidence=0.93,
            low_confidence_rate=0.05,
            correction_rate=0.03
        )
        
        # Baseline 0.95, current 0.94, drop 0.01 < threshold 0.05
        assert not metrics.has_drift(baseline_accuracy=0.95, threshold=0.05)
    
    def test_has_drift_with_drift(self):
        """Test has_drift returns True when drift detected."""
        metrics = ModelPerformanceMetrics(
            metric_id="metric-123",
            model_version="v1.0",
            total_predictions=100,
            correct_predictions=88,
            accuracy=0.88,
            avg_confidence=0.93,
            low_confidence_rate=0.05,
            correction_rate=0.03
        )
        
        # Baseline 0.95, current 0.88, drop 0.07 > threshold 0.05
        assert metrics.has_drift(baseline_accuracy=0.95, threshold=0.05)
    
    def test_has_drift_custom_threshold(self):
        """Test has_drift with custom threshold."""
        metrics = ModelPerformanceMetrics(
            metric_id="metric-123",
            model_version="v1.0",
            total_predictions=100,
            correct_predictions=92,
            accuracy=0.92,
            avg_confidence=0.93,
            low_confidence_rate=0.05,
            correction_rate=0.03
        )
        
        # Drop 0.03 > threshold 0.02
        assert metrics.has_drift(baseline_accuracy=0.95, threshold=0.02)
        
        # Drop 0.03 < threshold 0.05
        assert not metrics.has_drift(baseline_accuracy=0.95, threshold=0.05)
    
    def test_default_timestamp(self):
        """Test timestamp defaults to current time."""
        before = datetime.utcnow()
        metrics = ModelPerformanceMetrics(
            metric_id="metric-123",
            model_version="v1.0",
            total_predictions=100,
            correct_predictions=95,
            accuracy=0.95,
            avg_confidence=0.93,
            low_confidence_rate=0.05,
            correction_rate=0.03
        )
        after = datetime.utcnow()
        
        assert before <= metrics.timestamp <= after
    
    def test_intent_accuracies_defaults_to_empty_dict(self):
        """Test intent_accuracies defaults to empty dictionary."""
        metrics = ModelPerformanceMetrics(
            metric_id="metric-123",
            model_version="v1.0",
            total_predictions=100,
            correct_predictions=95,
            accuracy=0.95,
            avg_confidence=0.93,
            low_confidence_rate=0.05,
            correction_rate=0.03
        )
        
        assert metrics.intent_accuracies == {}
    
    def test_metadata_defaults_to_empty_dict(self):
        """Test metadata defaults to empty dictionary."""
        metrics = ModelPerformanceMetrics(
            metric_id="metric-123",
            model_version="v1.0",
            total_predictions=100,
            correct_predictions=95,
            accuracy=0.95,
            avg_confidence=0.93,
            low_confidence_rate=0.05,
            correction_rate=0.03
        )
        
        assert metrics.metadata == {}
    
    def test_negative_predictions_validation(self):
        """Test predictions cannot be negative."""
        with pytest.raises(ValueError):
            ModelPerformanceMetrics(
                metric_id="metric-123",
                model_version="v1.0",
                total_predictions=-1,
                correct_predictions=0,
                accuracy=0.95,
                avg_confidence=0.93,
                low_confidence_rate=0.05,
                correction_rate=0.03
            )
