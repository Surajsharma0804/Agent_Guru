"""
Tests for Reasoning Pipeline with Knowledge Synthesis Integration.

This module tests the complete reasoning pipeline including:
- Input normalization
- Memory retrieval integration
- Knowledge query detection and routing
- Knowledge synthesis integration
- Response generation
- Metrics tracking
- Error handling

Coverage Target: 80%+

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from Agent_Guru.reasoning.models.knowledge import (
    KnowledgeAnswer,
    KnowledgeQuery,
    KnowledgeQueryType,
    Pattern,
    TimeRange,
)
from Agent_Guru.reasoning.pipeline import (
    PipelineMetrics,
    PipelineResult,
    PipelineStage,
    ReasoningPipeline,
)


class TestPipelineMetrics:
    """Test PipelineMetrics data class."""

    def test_metrics_initialization(self):
        """Test metrics initialization with defaults."""
        metrics = PipelineMetrics()

        assert metrics.total_latency_ms == 0.0
        assert metrics.stage_latencies == {}
        assert metrics.knowledge_query_detected is False
        assert metrics.knowledge_query_type is None
        assert metrics.knowledge_confidence is None
        assert metrics.error is None
        assert isinstance(metrics.timestamp, datetime)

    def test_add_stage_latency(self):
        """Test adding stage latency."""
        metrics = PipelineMetrics()

        metrics.add_stage_latency(PipelineStage.INPUT_NORMALIZATION, 25.5)
        metrics.add_stage_latency(PipelineStage.KNOWLEDGE_DETECTION, 45.2)

        assert metrics.stage_latencies["input_normalization"] == 25.5
        assert metrics.stage_latencies["knowledge_detection"] == 45.2

    def test_to_dict(self):
        """Test converting metrics to dictionary."""
        metrics = PipelineMetrics()
        metrics.total_latency_ms = 150.5
        metrics.add_stage_latency(PipelineStage.INPUT_NORMALIZATION, 25.5)
        metrics.knowledge_query_detected = True
        metrics.knowledge_query_type = "temporal"
        metrics.knowledge_confidence = 0.95

        result = metrics.to_dict()

        assert result["total_latency_ms"] == 150.5
        assert result["stage_latencies"]["input_normalization"] == 25.5
        assert result["knowledge_query_detected"] is True
        assert result["knowledge_query_type"] == "temporal"
        assert result["knowledge_confidence"] == 0.95
        assert result["error"] is None
        assert "timestamp" in result


class TestPipelineResult:
    """Test PipelineResult data class."""

    def test_result_initialization(self):
        """Test result initialization."""
        result = PipelineResult(
            response="Test response",
            confidence=0.95,
        )

        assert result.response == "Test response"
        assert result.confidence == 0.95
        assert result.knowledge_answer is None
        assert isinstance(result.metrics, PipelineMetrics)
        assert result.success is True

    def test_result_with_knowledge_answer(self):
        """Test result with knowledge answer."""
        knowledge_answer = KnowledgeAnswer(
            summary="You last called John yesterday",
            confidence=0.95,
            supporting_memories=["mem_123"],
            patterns=[],
            statistics={"total_count": 1},
        )

        result = PipelineResult(
            response="You last called John yesterday",
            confidence=0.95,
            knowledge_answer=knowledge_answer,
        )

        assert result.knowledge_answer == knowledge_answer
        assert result.response == knowledge_answer.summary


class TestReasoningPipelineInitialization:
    """Test ReasoningPipeline initialization."""

    def test_initialization_with_memory_retriever(self):
        """Test initialization with memory retriever."""
        memory_retriever = Mock()

        pipeline = ReasoningPipeline(memory_retriever=memory_retriever)

        assert pipeline.memory_retriever == memory_retriever
        assert pipeline.enable_knowledge_synthesis is True
        assert pipeline.metrics_enabled is True
        assert pipeline.knowledge_detector is not None
        assert pipeline.knowledge_synthesizer is not None

    def test_initialization_without_memory_retriever(self):
        """Test initialization fails without memory retriever."""
        with pytest.raises(ValueError, match="memory_retriever cannot be None"):
            ReasoningPipeline(memory_retriever=None)

    def test_initialization_with_custom_components(self):
        """Test initialization with custom components."""
        memory_retriever = Mock()
        knowledge_detector = Mock()
        knowledge_synthesizer = Mock()

        pipeline = ReasoningPipeline(
            memory_retriever=memory_retriever,
            knowledge_detector=knowledge_detector,
            knowledge_synthesizer=knowledge_synthesizer,
        )

        assert pipeline.knowledge_detector == knowledge_detector
        assert pipeline.knowledge_synthesizer == knowledge_synthesizer

    def test_initialization_with_knowledge_synthesis_disabled(self):
        """Test initialization with knowledge synthesis disabled."""
        memory_retriever = Mock()

        pipeline = ReasoningPipeline(
            memory_retriever=memory_retriever,
            enable_knowledge_synthesis=False,
        )

        assert pipeline.enable_knowledge_synthesis is False
        assert pipeline.knowledge_detector is None
        assert pipeline.knowledge_synthesizer is None


class TestReasoningPipelineInputNormalization:
    """Test input normalization."""

    def test_normalize_valid_input(self):
        """Test normalizing valid input."""
        memory_retriever = Mock()
        pipeline = ReasoningPipeline(memory_retriever=memory_retriever)

        normalized = pipeline._normalize_input("  when did I last call John?  ")

        assert normalized == "when did I last call John?"

    def test_normalize_input_with_extra_whitespace(self):
        """Test normalizing input with extra whitespace."""
        memory_retriever = Mock()
        pipeline = ReasoningPipeline(memory_retriever=memory_retriever)

        normalized = pipeline._normalize_input("when   did   I   last   call   John?")

        assert normalized == "when did I last call John?"

    def test_normalize_empty_input(self):
        """Test normalizing empty input raises error."""
        memory_retriever = Mock()
        pipeline = ReasoningPipeline(memory_retriever=memory_retriever)

        with pytest.raises(ValueError, match="Input cannot be empty"):
            pipeline._normalize_input("")

    def test_normalize_whitespace_only_input(self):
        """Test normalizing whitespace-only input raises error."""
        memory_retriever = Mock()
        pipeline = ReasoningPipeline(memory_retriever=memory_retriever)

        with pytest.raises(ValueError, match="Input cannot be empty"):
            pipeline._normalize_input("   ")


class TestReasoningPipelineKnowledgeQueryRouting:
    """Test knowledge query detection and routing."""

    def test_process_knowledge_query_temporal(self):
        """Test processing temporal knowledge query."""
        # Setup mocks
        memory_retriever = Mock()
        knowledge_detector = Mock()
        knowledge_synthesizer = Mock()

        # Mock knowledge query detection
        knowledge_query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_month(),
            entities={"person": "John", "action": "call"},
            confidence=0.95,
        )
        knowledge_detector.detect_knowledge_query.return_value = knowledge_query

        # Mock knowledge synthesis
        knowledge_answer = KnowledgeAnswer(
            summary="You last called John 3 days ago",
            confidence=0.95,
            supporting_memories=["mem_123"],
            patterns=[],
            statistics={"total_count": 1},
        )
        knowledge_synthesizer.synthesize_answer.return_value = knowledge_answer

        # Create pipeline
        pipeline = ReasoningPipeline(
            memory_retriever=memory_retriever,
            knowledge_detector=knowledge_detector,
            knowledge_synthesizer=knowledge_synthesizer,
        )

        # Process query
        result = pipeline.process("when did I last call John?", user_id="user_123")

        # Verify result
        assert result.success is True
        assert result.response == "You last called John 3 days ago"
        assert result.confidence == 0.95
        assert result.knowledge_answer == knowledge_answer

        # Verify metrics
        assert result.metrics.knowledge_query_detected is True
        assert result.metrics.knowledge_query_type == "temporal"
        assert result.metrics.knowledge_confidence == 0.95
        assert result.metrics.total_latency_ms > 0

        # Verify stage latencies
        assert "input_normalization" in result.metrics.stage_latencies
        assert "knowledge_detection" in result.metrics.stage_latencies
        assert "knowledge_synthesis" in result.metrics.stage_latencies
        assert "response_generation" in result.metrics.stage_latencies

        # Verify calls
        knowledge_detector.detect_knowledge_query.assert_called_once()
        knowledge_synthesizer.synthesize_answer.assert_called_once_with(knowledge_query, "user_123")

    def test_process_knowledge_query_aggregation(self):
        """Test processing aggregation knowledge query."""
        # Setup mocks
        memory_retriever = Mock()
        knowledge_detector = Mock()
        knowledge_synthesizer = Mock()

        # Mock knowledge query detection
        knowledge_query = KnowledgeQuery(
            query_text="who do I message most?",
            query_type=KnowledgeQueryType.AGGREGATION,
            entities={"action": "message"},
            confidence=0.90,
        )
        knowledge_detector.detect_knowledge_query.return_value = knowledge_query

        # Mock knowledge synthesis
        knowledge_answer = KnowledgeAnswer(
            summary="You message Alice most often (15 times this month)",
            confidence=0.92,
            supporting_memories=["mem_456", "mem_789"],
            patterns=[],
            statistics={"total_count": 15, "top_person": "Alice"},
        )
        knowledge_synthesizer.synthesize_answer.return_value = knowledge_answer

        # Create pipeline
        pipeline = ReasoningPipeline(
            memory_retriever=memory_retriever,
            knowledge_detector=knowledge_detector,
            knowledge_synthesizer=knowledge_synthesizer,
        )

        # Process query
        result = pipeline.process("who do I message most?", user_id="user_123")

        # Verify result
        assert result.success is True
        assert "Alice" in result.response
        assert result.confidence == 0.92
        assert result.metrics.knowledge_query_type == "aggregation"

    def test_process_knowledge_query_pattern(self):
        """Test processing pattern knowledge query."""
        # Setup mocks
        memory_retriever = Mock()
        knowledge_detector = Mock()
        knowledge_synthesizer = Mock()

        # Mock knowledge query detection
        knowledge_query = KnowledgeQuery(
            query_text="what do I usually do in the morning?",
            query_type=KnowledgeQueryType.PATTERN,
            entities={},
            confidence=0.88,
        )
        knowledge_detector.detect_knowledge_query.return_value = knowledge_query

        # Mock knowledge synthesis with patterns
        pattern = Pattern(
            pattern_type="daily",
            description="You typically check email at 9am",
            frequency=0.85,
            confidence=0.90,
            examples=["2024-01-15 09:00", "2024-01-16 09:05"],
        )
        knowledge_answer = KnowledgeAnswer(
            summary="You typically check email at 9am (about 85% of the time)",
            confidence=0.88,
            supporting_memories=["mem_111", "mem_222"],
            patterns=[pattern],
            statistics={"total_count": 20},
        )
        knowledge_synthesizer.synthesize_answer.return_value = knowledge_answer

        # Create pipeline
        pipeline = ReasoningPipeline(
            memory_retriever=memory_retriever,
            knowledge_detector=knowledge_detector,
            knowledge_synthesizer=knowledge_synthesizer,
        )

        # Process query
        result = pipeline.process("what do I usually do in the morning?", user_id="user_123")

        # Verify result
        assert result.success is True
        assert "email" in result.response
        assert result.knowledge_answer.patterns == [pattern]
        assert result.metrics.knowledge_query_type == "pattern"


class TestReasoningPipelineNonKnowledgeQueries:
    """Test handling of non-knowledge queries."""

    def test_process_non_knowledge_query(self):
        """Test processing non-knowledge query falls back."""
        # Setup mocks
        memory_retriever = Mock()
        knowledge_detector = Mock()

        # Mock no knowledge query detected
        knowledge_detector.detect_knowledge_query.return_value = None

        # Create pipeline
        pipeline = ReasoningPipeline(
            memory_retriever=memory_retriever,
            knowledge_detector=knowledge_detector,
        )

        # Process query
        result = pipeline.process("set a timer for 5 minutes", user_id="user_123")

        # Verify fallback response
        assert result.success is True
        assert "still learning" in result.response.lower()
        assert result.confidence == 0.5  # Low confidence for fallback
        assert result.knowledge_answer is None
        assert result.metrics.knowledge_query_detected is False

        # Verify stage latencies
        assert "input_normalization" in result.metrics.stage_latencies
        assert "knowledge_detection" in result.metrics.stage_latencies
        assert "normal_reasoning" in result.metrics.stage_latencies

    def test_process_with_knowledge_synthesis_disabled(self):
        """Test processing with knowledge synthesis disabled."""
        # Setup mocks
        memory_retriever = Mock()

        # Create pipeline with knowledge synthesis disabled
        pipeline = ReasoningPipeline(
            memory_retriever=memory_retriever,
            enable_knowledge_synthesis=False,
        )

        # Process query
        result = pipeline.process("when did I last call John?", user_id="user_123")

        # Verify fallback response (knowledge synthesis disabled)
        assert result.success is True
        assert result.confidence == 0.5
        assert result.knowledge_answer is None
        assert result.metrics.knowledge_query_detected is False


class TestReasoningPipelineErrorHandling:
    """Test error handling in pipeline."""

    def test_process_with_detector_error(self):
        """Test processing when detector raises error."""
        # Setup mocks
        memory_retriever = Mock()
        knowledge_detector = Mock()

        # Mock detector error
        knowledge_detector.detect_knowledge_query.side_effect = Exception("Detector error")

        # Create pipeline
        pipeline = ReasoningPipeline(
            memory_retriever=memory_retriever,
            knowledge_detector=knowledge_detector,
        )

        # Process query
        result = pipeline.process("when did I last call John?", user_id="user_123")

        # Verify error handling
        assert result.success is False
        assert "error" in result.response.lower()
        assert result.confidence == 0.0
        assert result.metrics.error == "Detector error"
        assert result.metrics.total_latency_ms > 0

    def test_process_with_synthesizer_error(self):
        """Test processing when synthesizer raises error."""
        # Setup mocks
        memory_retriever = Mock()
        knowledge_detector = Mock()
        knowledge_synthesizer = Mock()

        # Mock knowledge query detection
        knowledge_query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_month(),
            entities={"person": "John", "action": "call"},
            confidence=0.95,
        )
        knowledge_detector.detect_knowledge_query.return_value = knowledge_query

        # Mock synthesizer error
        knowledge_synthesizer.synthesize_answer.side_effect = Exception("Synthesis error")

        # Create pipeline
        pipeline = ReasoningPipeline(
            memory_retriever=memory_retriever,
            knowledge_detector=knowledge_detector,
            knowledge_synthesizer=knowledge_synthesizer,
        )

        # Process query
        result = pipeline.process("when did I last call John?", user_id="user_123")

        # Verify error handling
        assert result.success is False
        assert "error" in result.response.lower()
        assert result.confidence == 0.0
        assert result.metrics.error == "Synthesis error"


class TestReasoningPipelineMetricsTracking:
    """Test metrics tracking in pipeline."""

    def test_metrics_tracking_for_knowledge_query(self):
        """Test comprehensive metrics tracking for knowledge query."""
        # Setup mocks
        memory_retriever = Mock()
        knowledge_detector = Mock()
        knowledge_synthesizer = Mock()

        # Mock knowledge query detection
        knowledge_query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_month(),
            entities={"person": "John", "action": "call"},
            confidence=0.95,
        )
        knowledge_detector.detect_knowledge_query.return_value = knowledge_query

        # Mock knowledge synthesis
        knowledge_answer = KnowledgeAnswer(
            summary="You last called John 3 days ago",
            confidence=0.95,
            supporting_memories=["mem_123"],
            patterns=[],
            statistics={"total_count": 1},
        )
        knowledge_synthesizer.synthesize_answer.return_value = knowledge_answer

        # Create pipeline
        pipeline = ReasoningPipeline(
            memory_retriever=memory_retriever,
            knowledge_detector=knowledge_detector,
            knowledge_synthesizer=knowledge_synthesizer,
            metrics_enabled=True,
        )

        # Process query
        result = pipeline.process("when did I last call John?", user_id="user_123")

        # Verify comprehensive metrics
        metrics = result.metrics

        # Check all stages are tracked
        assert "input_normalization" in metrics.stage_latencies
        assert "memory_retrieval" in metrics.stage_latencies
        assert "knowledge_detection" in metrics.stage_latencies
        assert "knowledge_synthesis" in metrics.stage_latencies
        assert "response_generation" in metrics.stage_latencies

        # Check all latencies are positive
        for stage, latency in metrics.stage_latencies.items():
            assert latency >= 0, f"Stage {stage} has negative latency"

        # Check total latency is sum of stages (approximately)
        total_stage_latency = sum(metrics.stage_latencies.values())
        assert abs(metrics.total_latency_ms - total_stage_latency) < 10  # Allow 10ms tolerance

        # Check knowledge query metrics
        assert metrics.knowledge_query_detected is True
        assert metrics.knowledge_query_type == "temporal"
        assert metrics.knowledge_confidence == 0.95

        # Check timestamp
        assert isinstance(metrics.timestamp, datetime)
        assert (datetime.utcnow() - metrics.timestamp).total_seconds() < 1

    def test_metrics_to_dict_conversion(self):
        """Test converting metrics to dictionary for logging."""
        # Setup mocks
        memory_retriever = Mock()
        knowledge_detector = Mock()
        knowledge_synthesizer = Mock()

        # Mock knowledge query
        knowledge_query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_month(),
            entities={"person": "John", "action": "call"},
            confidence=0.95,
        )
        knowledge_detector.detect_knowledge_query.return_value = knowledge_query

        # Mock knowledge answer
        knowledge_answer = KnowledgeAnswer(
            summary="You last called John 3 days ago",
            confidence=0.95,
            supporting_memories=["mem_123"],
            patterns=[],
            statistics={"total_count": 1},
        )
        knowledge_synthesizer.synthesize_answer.return_value = knowledge_answer

        # Create pipeline
        pipeline = ReasoningPipeline(
            memory_retriever=memory_retriever,
            knowledge_detector=knowledge_detector,
            knowledge_synthesizer=knowledge_synthesizer,
        )

        # Process query
        result = pipeline.process("when did I last call John?", user_id="user_123")

        # Convert metrics to dict
        metrics_dict = result.metrics.to_dict()

        # Verify dict structure
        assert "total_latency_ms" in metrics_dict
        assert "stage_latencies" in metrics_dict
        assert "knowledge_query_detected" in metrics_dict
        assert "knowledge_query_type" in metrics_dict
        assert "knowledge_confidence" in metrics_dict
        assert "error" in metrics_dict
        assert "timestamp" in metrics_dict

        # Verify values
        assert metrics_dict["knowledge_query_detected"] is True
        assert metrics_dict["knowledge_query_type"] == "temporal"
        assert metrics_dict["knowledge_confidence"] == 0.95
        assert metrics_dict["error"] is None


class TestReasoningPipelineResponseGeneration:
    """Test response generation from knowledge answers."""

    def test_generate_response_from_knowledge_answer(self):
        """Test generating response from knowledge answer."""
        memory_retriever = Mock()
        pipeline = ReasoningPipeline(memory_retriever=memory_retriever)

        knowledge_answer = KnowledgeAnswer(
            summary="You last called John 3 days ago",
            confidence=0.95,
            supporting_memories=["mem_123"],
            patterns=[],
            statistics={"total_count": 1},
        )

        response = pipeline._generate_response_from_knowledge_answer(knowledge_answer)

        assert response == "You last called John 3 days ago"

    def test_fallback_response(self):
        """Test fallback response for non-knowledge queries."""
        memory_retriever = Mock()
        pipeline = ReasoningPipeline(memory_retriever=memory_retriever)

        response = pipeline._fallback_response("set a timer for 5 minutes")

        assert "still learning" in response.lower()
        assert "when did i last..." in response.lower()  # Fixed: use exact text from response


class TestReasoningPipelineIntegration:
    """Integration tests for complete pipeline."""

    def test_end_to_end_knowledge_query_processing(self):
        """Test complete end-to-end knowledge query processing."""
        # Simplified integration test using mocks
        memory_retriever = Mock()
        knowledge_detector = Mock()
        knowledge_synthesizer = Mock()

        # Mock knowledge query detection
        knowledge_query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_month(),
            entities={"person": "John", "action": "call"},
            confidence=0.95,
        )
        knowledge_detector.detect_knowledge_query.return_value = knowledge_query

        # Mock knowledge synthesis
        knowledge_answer = KnowledgeAnswer(
            summary="You last called John 3 days ago",
            confidence=0.95,
            supporting_memories=["mem_123"],
            patterns=[],
            statistics={"total_count": 1},
        )
        knowledge_synthesizer.synthesize_answer.return_value = knowledge_answer

        # Create pipeline with mocked components
        pipeline = ReasoningPipeline(
            memory_retriever=memory_retriever,
            knowledge_detector=knowledge_detector,
            knowledge_synthesizer=knowledge_synthesizer,
        )

        # Process knowledge query
        result = pipeline.process("when did I last call John?", user_id="user_123")

        # Verify result
        assert result.success is True
        assert result.confidence == 0.95
        assert result.metrics.knowledge_query_detected is True
        assert result.metrics.total_latency_ms > 0
        assert result.response == "You last called John 3 days ago"

    def test_get_metrics_summary(self):
        """Test getting metrics summary."""
        memory_retriever = Mock()
        pipeline = ReasoningPipeline(memory_retriever=memory_retriever)

        summary = pipeline.get_metrics_summary()

        # Verify summary structure (placeholder for now)
        assert "knowledge_queries_processed" in summary
        assert "normal_queries_processed" in summary
        assert "average_latency_ms" in summary
        assert "average_confidence" in summary
        assert "error_rate" in summary
