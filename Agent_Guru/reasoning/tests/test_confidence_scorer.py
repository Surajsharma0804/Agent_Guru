"""
Unit tests for confidence scorer.

Tests the enhanced confidence scoring system including:
- Multi-dimensional scoring (LLM, completeness, consistency, quality, historical)
- Historical accuracy tracking
- Confidence calibration
- Context consistency checking

Coverage Target: >80%
"""

from datetime import datetime

import pytest

from Agent_Guru.reasoning.llm.confidence_scorer import (
    ConfidenceScorer,
    HistoricalAccuracy,
    get_confidence_scorer,
    score_task_confidence,
)
from Agent_Guru.reasoning.models.task import Task, TaskStep, TaskType


class TestHistoricalAccuracy:
    """Test HistoricalAccuracy data class."""

    def test_initialization(self):
        """Test HistoricalAccuracy initialization."""
        history = HistoricalAccuracy(task_type="single_step")

        assert history.task_type == "single_step"
        assert history.total_attempts == 0
        assert history.successful_attempts == 0
        assert history.confidence_sum == 0.0
        assert isinstance(history.last_updated, datetime)

    def test_success_rate_no_attempts(self):
        """Test success rate with no attempts returns neutral."""
        history = HistoricalAccuracy(task_type="single_step")
        assert history.success_rate == 0.5

    def test_success_rate_with_attempts(self):
        """Test success rate calculation."""
        history = HistoricalAccuracy(task_type="single_step")
        history.total_attempts = 10
        history.successful_attempts = 8

        assert history.success_rate == 0.8

    def test_average_confidence_no_attempts(self):
        """Test average confidence with no attempts returns neutral."""
        history = HistoricalAccuracy(task_type="single_step")
        assert history.average_confidence == 0.5

    def test_average_confidence_with_attempts(self):
        """Test average confidence calculation."""
        history = HistoricalAccuracy(task_type="single_step")
        history.total_attempts = 10
        history.confidence_sum = 7.5

        assert history.average_confidence == 0.75

    def test_calibration_factor_insufficient_data(self):
        """Test calibration factor with insufficient data returns 1.0."""
        history = HistoricalAccuracy(task_type="single_step")
        history.total_attempts = 5

        assert history.calibration_factor == 1.0

    def test_calibration_factor_overconfident(self):
        """Test calibration factor when model is overconfident."""
        history = HistoricalAccuracy(task_type="single_step")
        history.total_attempts = 20
        history.successful_attempts = 10  # 50% success
        history.confidence_sum = 16.0  # 80% average confidence

        # Should reduce confidence (0.5 / 0.8 = 0.625)
        assert history.calibration_factor < 1.0
        assert history.calibration_factor == pytest.approx(0.625, abs=0.01)

    def test_calibration_factor_underconfident(self):
        """Test calibration factor when model is underconfident."""
        history = HistoricalAccuracy(task_type="single_step")
        history.total_attempts = 20
        history.successful_attempts = 16  # 80% success
        history.confidence_sum = 10.0  # 50% average confidence

        # Should increase confidence (0.8 / 0.5 = 1.6, clamped to 1.5)
        assert history.calibration_factor > 1.0
        assert history.calibration_factor == 1.5  # Clamped

    def test_calibration_factor_clamping(self):
        """Test calibration factor is clamped to [0.5, 1.5]."""
        history = HistoricalAccuracy(task_type="single_step")
        history.total_attempts = 20

        # Test lower bound
        history.successful_attempts = 2  # 10% success
        history.confidence_sum = 18.0  # 90% confidence
        assert history.calibration_factor >= 0.5

        # Test upper bound
        history.successful_attempts = 18  # 90% success
        history.confidence_sum = 2.0  # 10% confidence
        assert history.calibration_factor <= 1.5


class TestConfidenceScorer:
    """Test ConfidenceScorer class."""

    @pytest.fixture
    def scorer(self):
        """Create fresh scorer for each test."""
        return ConfidenceScorer()

    @pytest.fixture
    def simple_task(self):
        """Create simple valid task."""
        return Task(
            goal="Set timer for 5 minutes",
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": "5 minutes"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set timer for 5 minutes",
                    tool_id="set_timer",
                    parameters={"duration": 300},
                    estimated_duration=0.5,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=0.5,
        )

    @pytest.fixture
    def simple_task_dict(self):
        """Create simple task dictionary."""
        return {
            "goal": "Set timer for 5 minutes",
            "task_type": "single_step",
            "entities": {"duration": "5 minutes"},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Set timer for 5 minutes",
                    "tool_id": "set_timer",
                    "parameters": {"duration": 300},
                    "estimated_duration": 0.5,
                }
            ],
            "confidence": 0.9,
            "requires_confirmation": False,
            "estimated_duration": 0.5,
        }

    def test_initialization(self, scorer):
        """Test scorer initialization."""
        assert len(scorer._history) == 0
        assert scorer.weights["llm_confidence"] == 0.35
        assert scorer.weights["completeness"] == 0.25
        assert scorer.weights["consistency"] == 0.20
        assert scorer.weights["quality"] == 0.10
        assert scorer.weights["historical"] == 0.10
        assert sum(scorer.weights.values()) == pytest.approx(1.0)

    def test_score_simple_task(self, scorer, simple_task, simple_task_dict):
        """Test scoring a simple valid task."""
        confidence = scorer.score(simple_task, simple_task_dict)

        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.7  # Should be high for valid task

    def test_score_llm_confidence(self, scorer, simple_task):
        """Test LLM confidence scoring."""
        score = scorer._score_llm_confidence(simple_task)
        assert score == simple_task.confidence

    def test_score_completeness_full(self, scorer, simple_task, simple_task_dict):
        """Test completeness scoring for complete task."""
        score = scorer._score_completeness(simple_task, simple_task_dict)
        assert score >= 0.8  # Should be high for complete task

    def test_score_completeness_missing_entities(self, scorer, simple_task_dict):
        """Test completeness penalty for missing entities."""
        task = Task(
            goal="Set timer",
            task_type=TaskType.SINGLE_STEP,
            entities={},  # No entities
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set timer",
                    tool_id="set_timer",
                    parameters={"duration": 300},
                    estimated_duration=0.5,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=0.5,
        )

        score = scorer._score_completeness(task, simple_task_dict)
        assert score < 1.0  # Should be penalized

    def test_score_completeness_empty_parameters(self, scorer, simple_task_dict):
        """Test completeness penalty for empty parameters."""
        task = Task(
            goal="Set timer",
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": "5 minutes"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set timer",
                    tool_id="set_timer",
                    parameters={},  # Empty parameters
                    estimated_duration=0.5,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=0.5,
        )

        score = scorer._score_completeness(task, simple_task_dict)
        assert score < 1.0  # Should be penalized

    def test_score_completeness_short_description(self, scorer, simple_task_dict):
        """Test completeness penalty for short descriptions."""
        task = Task(
            goal="Set",  # Too short
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": "5 minutes"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set",  # Too short
                    tool_id="set_timer",
                    parameters={"duration": 300},
                    estimated_duration=0.5,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=0.5,
        )

        score = scorer._score_completeness(task, simple_task_dict)
        assert score < 0.85  # Should be penalized

    def test_score_completeness_placeholder_text(self, scorer, simple_task_dict):
        """Test completeness penalty for placeholder text."""
        task = Task(
            goal="TODO: Set timer",  # Has placeholder
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": "5 minutes"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set timer",
                    tool_id="set_timer",
                    parameters={"duration": 300},
                    estimated_duration=0.5,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=0.5,
        )

        score = scorer._score_completeness(task, simple_task_dict)
        assert score < 0.85  # Should be penalized

    def test_score_consistency_valid(self, scorer, simple_task):
        """Test consistency scoring for valid task."""
        score = scorer._score_consistency(simple_task, None)
        assert score >= 0.9  # Should be high for consistent task

    def test_score_consistency_wrong_task_type(self, scorer):
        """Test consistency penalty for wrong task type."""
        # Note: Pydantic validation prevents creating invalid tasks,
        # so we test the scoring logic directly
        task = Task(
            goal="Multi-step task",
            task_type=TaskType.MULTI_STEP,  # Correct type for 2 steps
            entities={},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Step 1",
                    tool_id="tool1",
                    parameters={},
                    estimated_duration=0.5,
                ),
                TaskStep(
                    step_id=2,
                    description="Step 2",
                    tool_id="tool2",
                    parameters={},
                    estimated_duration=0.5,
                ),
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=1.0,
        )

        # Manually override task_type to test scoring logic
        task.task_type = TaskType.SINGLE_STEP  # Wrong type

        score = scorer._score_consistency(task, None)
        assert score < 0.8  # Should be penalized

    def test_score_consistency_duration_mismatch(self, scorer):
        """Test consistency penalty for duration mismatch."""
        # Create task with matching durations first
        task = Task(
            goal="Set timer",
            task_type=TaskType.SINGLE_STEP,
            entities={},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set timer",
                    tool_id="set_timer",
                    parameters={},
                    estimated_duration=0.5,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=0.5,
        )

        # Manually override estimated_duration to test scoring logic
        task.estimated_duration = 5.0  # Doesn't match step duration

        score = scorer._score_consistency(task, None)
        assert score < 1.0  # Should be penalized

    def test_score_consistency_invalid_dependencies(self, scorer):
        """Test consistency penalty for invalid dependencies."""
        # Create task with valid dependencies first
        task = Task(
            goal="Multi-step task",
            task_type=TaskType.MULTI_STEP,
            entities={},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Step 1",
                    tool_id="tool1",
                    parameters={},
                    depends_on=[],
                    estimated_duration=0.5,
                ),
                TaskStep(
                    step_id=2,
                    description="Step 2",
                    tool_id="tool2",
                    parameters={},
                    depends_on=[1],  # Valid dependency
                    estimated_duration=0.5,
                ),
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=1.0,
        )

        # Manually override dependencies to test scoring logic
        task.steps[0].depends_on = [2]  # Invalid: depends on later step

        score = scorer._score_consistency(task, None)
        assert score < 0.9  # Should be penalized

    def test_score_quality_valid(self, scorer, simple_task):
        """Test quality scoring for valid task."""
        score = scorer._score_quality(simple_task)
        assert score >= 0.8  # Should be high for quality task

    def test_score_quality_no_capitalization(self, scorer):
        """Test quality penalty for missing capitalization."""
        task = Task(
            goal="set timer",  # No capital
            task_type=TaskType.SINGLE_STEP,
            entities={},
            steps=[
                TaskStep(
                    step_id=1,
                    description="set timer",  # No capital
                    tool_id="set_timer",
                    parameters={},
                    estimated_duration=0.5,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=0.5,
        )

        score = scorer._score_quality(task)
        assert score < 0.9  # Should be penalized

    def test_score_quality_too_short(self, scorer):
        """Test quality penalty for too short descriptions."""
        task = Task(
            goal="Set",
            task_type=TaskType.SINGLE_STEP,
            entities={},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set",
                    tool_id="set_timer",
                    parameters={},
                    estimated_duration=0.5,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=0.5,
        )

        score = scorer._score_quality(task)
        assert score < 0.8  # Should be penalized

    def test_score_quality_repetition(self, scorer):
        """Test quality penalty for repeated descriptions."""
        task = Task(
            goal="Multi-step task",
            task_type=TaskType.MULTI_STEP,
            entities={},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Same description",
                    tool_id="tool1",
                    parameters={},
                    estimated_duration=0.5,
                ),
                TaskStep(
                    step_id=2,
                    description="Same description",  # Duplicate
                    tool_id="tool2",
                    parameters={},
                    estimated_duration=0.5,
                ),
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=1.0,
        )

        score = scorer._score_quality(task)
        assert score < 0.9  # Should be penalized

    def test_score_historical_no_data(self, scorer, simple_task):
        """Test historical scoring with no data returns neutral."""
        score = scorer._score_historical(simple_task)
        assert score == 0.5  # Neutral

    def test_score_historical_insufficient_data(self, scorer, simple_task):
        """Test historical scoring with insufficient data returns neutral."""
        # Add some history but not enough
        scorer._history[simple_task.task_type].total_attempts = 3
        scorer._history[simple_task.task_type].successful_attempts = 2

        score = scorer._score_historical(simple_task)
        assert score == 0.5  # Still neutral

    def test_score_historical_with_data(self, scorer, simple_task):
        """Test historical scoring with sufficient data."""
        # Add sufficient history
        history = scorer._history[simple_task.task_type]
        history.total_attempts = 10
        history.successful_attempts = 8

        score = scorer._score_historical(simple_task)
        assert score == 0.8  # Should match success rate

    def test_update_history(self, scorer, simple_task):
        """Test updating historical accuracy."""
        scorer.update_history(simple_task, success=True, confidence=0.85)

        history = scorer.get_history(simple_task.task_type)
        assert history is not None
        assert history.total_attempts == 1
        assert history.successful_attempts == 1
        assert history.confidence_sum == 0.85

    def test_update_history_multiple(self, scorer, simple_task):
        """Test updating history multiple times."""
        scorer.update_history(simple_task, success=True, confidence=0.9)
        scorer.update_history(simple_task, success=True, confidence=0.8)
        scorer.update_history(simple_task, success=False, confidence=0.7)

        history = scorer.get_history(simple_task.task_type)
        assert history.total_attempts == 3
        assert history.successful_attempts == 2
        assert history.confidence_sum == pytest.approx(2.4, abs=0.01)
        assert history.success_rate == pytest.approx(0.667, abs=0.01)

    def test_get_history_nonexistent(self, scorer):
        """Test getting history for nonexistent task type."""
        history = scorer.get_history("nonexistent")
        assert history is None

    def test_get_all_history(self, scorer, simple_task):
        """Test getting all history."""
        scorer.update_history(simple_task, success=True, confidence=0.9)

        all_history = scorer.get_all_history()
        assert len(all_history) == 1
        assert simple_task.task_type in all_history

    def test_clear_history(self, scorer, simple_task):
        """Test clearing history."""
        scorer.update_history(simple_task, success=True, confidence=0.9)
        assert len(scorer._history) > 0

        scorer.clear_history()
        assert len(scorer._history) == 0

    def test_apply_calibration_no_data(self, scorer, simple_task):
        """Test calibration with no data returns unchanged."""
        calibrated = scorer._apply_calibration(simple_task, 0.8)
        assert calibrated == 0.8

    def test_apply_calibration_insufficient_data(self, scorer, simple_task):
        """Test calibration with insufficient data returns unchanged."""
        scorer._history[simple_task.task_type].total_attempts = 5
        calibrated = scorer._apply_calibration(simple_task, 0.8)
        assert calibrated == 0.8

    def test_apply_calibration_with_data(self, scorer, simple_task):
        """Test calibration with sufficient data."""
        # Set up history with calibration factor
        history = scorer._history[simple_task.task_type]
        history.total_attempts = 20
        history.successful_attempts = 10  # 50% success
        history.confidence_sum = 16.0  # 80% confidence
        # Calibration factor = 0.5 / 0.8 = 0.625

        calibrated = scorer._apply_calibration(simple_task, 0.8)
        assert calibrated < 0.8  # Should be reduced
        assert calibrated == pytest.approx(0.5, abs=0.01)

    def test_apply_calibration_clamping(self, scorer, simple_task):
        """Test calibration clamping to [0.1, 0.95]."""
        history = scorer._history[simple_task.task_type]
        history.total_attempts = 20

        # Test lower bound
        history.successful_attempts = 2
        history.confidence_sum = 18.0
        calibrated = scorer._apply_calibration(simple_task, 0.8)
        assert calibrated >= 0.1

        # Test upper bound
        history.successful_attempts = 18
        history.confidence_sum = 2.0
        calibrated = scorer._apply_calibration(simple_task, 0.8)
        assert calibrated <= 0.95

    def test_check_context_consistency_no_context(self, scorer, simple_task):
        """Test context consistency with no context returns 1.0."""
        multiplier = scorer._check_context_consistency(simple_task, {})
        assert multiplier == 1.0

    def test_check_context_consistency_matching_entities(self, scorer, simple_task):
        """Test context consistency with matching entities."""
        context = {"entities": {"duration": "5 minutes", "extra": "value"}}

        multiplier = scorer._check_context_consistency(simple_task, context)
        assert multiplier == 1.0  # Task entities are subset

    def test_check_context_consistency_extra_entities(self, scorer, simple_task):
        """Test context consistency penalty for extra entities."""
        context = {"entities": {"other": "value"}}

        multiplier = scorer._check_context_consistency(simple_task, context)
        assert multiplier < 1.0  # Should be penalized


class TestGlobalScorer:
    """Test global scorer functions."""

    def test_get_confidence_scorer(self):
        """Test getting global scorer instance."""
        scorer1 = get_confidence_scorer()
        scorer2 = get_confidence_scorer()

        assert scorer1 is scorer2  # Should be same instance
        assert isinstance(scorer1, ConfidenceScorer)

    def test_score_task_confidence(self):
        """Test convenience function."""
        task = Task(
            goal="Set timer",
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": "5 minutes"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set timer",
                    tool_id="set_timer",
                    parameters={"duration": 300},
                    estimated_duration=0.5,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=0.5,
        )

        task_dict = {
            "goal": "Set timer",
            "task_type": "single_step",
            "entities": {"duration": "5 minutes"},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Set timer",
                    "tool_id": "set_timer",
                    "parameters": {"duration": 300},
                    "estimated_duration": 0.5,
                }
            ],
            "confidence": 0.9,
            "requires_confirmation": False,
            "estimated_duration": 0.5,
        }

        confidence = score_task_confidence(task, task_dict)
        assert 0.0 <= confidence <= 1.0


class TestIntegration:
    """Integration tests for confidence scorer."""

    def test_full_scoring_workflow(self):
        """Test complete scoring workflow with history updates."""
        scorer = ConfidenceScorer()

        # Create task
        task = Task(
            goal="Set timer for 5 minutes",
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": "5 minutes"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set timer for 5 minutes",
                    tool_id="set_timer",
                    parameters={"duration": 300},
                    estimated_duration=0.5,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=0.5,
        )

        task_dict = {
            "goal": "Set timer for 5 minutes",
            "task_type": "single_step",
            "entities": {"duration": "5 minutes"},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Set timer for 5 minutes",
                    "tool_id": "set_timer",
                    "parameters": {"duration": 300},
                    "estimated_duration": 0.5,
                }
            ],
            "confidence": 0.9,
            "requires_confirmation": False,
            "estimated_duration": 0.5,
        }

        # Score task (no history yet)
        confidence1 = scorer.score(task, task_dict)
        assert 0.7 <= confidence1 <= 1.0

        # Update history with successes
        for _ in range(15):
            scorer.update_history(task, success=True, confidence=confidence1)

        # Score again (should be similar or higher due to good history)
        confidence2 = scorer.score(task, task_dict)
        assert confidence2 >= confidence1 * 0.9  # Allow small variation

        # Update history with failures
        for _ in range(10):
            scorer.update_history(task, success=False, confidence=confidence2)

        # Score again (should be lower due to poor recent history)
        confidence3 = scorer.score(task, task_dict)
        # Success rate is now 15/25 = 0.6, so historical score should reflect this
        assert confidence3 < confidence2
