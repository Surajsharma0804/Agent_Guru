"""
Unit tests for fallback processor.

Tests the rule-based fallback mechanism that creates Task objects
when LLM is unavailable.

Requirements: 16.5, 16.7
"""

from unittest.mock import Mock, patch

import pytest

from Agent_Guru.reasoning.config.metrics import MetricsCollector
from Agent_Guru.reasoning.intent.fast_router import (
    FastIntentRouter,
    MatchQuality,
    PatternMatch,
)
from Agent_Guru.reasoning.llm.fallback_processor import (
    FallbackMetrics,
    FallbackProcessor,
)
from Agent_Guru.reasoning.models.task import Task, TaskStatus, TaskType
import logging

logger = logging.getLogger(__name__)

# Unit Tests - FallbackMetrics


class TestFallbackMetrics:
    """Test fallback metrics tracking."""

    def test_initialization(self):
        """Test metrics initialization."""
        metrics = FallbackMetrics()

        assert metrics.total_fallbacks == 0  # nosec B101
        assert metrics.successful_fallbacks == 0  # nosec B101
        assert metrics.failed_fallbacks == 0  # nosec B101
        assert metrics.total_latency_ms == 0.0  # nosec B101

    def test_record_successful_fallback(self):
        """Test recording successful fallback."""
        metrics = FallbackMetrics()

        metrics.record_fallback(success=True, latency_ms=15.5)

        assert metrics.total_fallbacks == 1  # nosec B101
        assert metrics.successful_fallbacks == 1  # nosec B101
        assert metrics.failed_fallbacks == 0  # nosec B101
        assert metrics.total_latency_ms == 15.5  # nosec B101

    def test_record_failed_fallback(self):
        """Test recording failed fallback."""
        metrics = FallbackMetrics()

        metrics.record_fallback(success=False, latency_ms=10.0)

        assert metrics.total_fallbacks == 1  # nosec B101
        assert metrics.successful_fallbacks == 0  # nosec B101
        assert metrics.failed_fallbacks == 1  # nosec B101
        assert metrics.total_latency_ms == 10.0  # nosec B101

    def test_record_multiple_fallbacks(self):
        """Test recording multiple fallbacks."""
        metrics = FallbackMetrics()

        metrics.record_fallback(success=True, latency_ms=15.0)
        metrics.record_fallback(success=True, latency_ms=20.0)
        metrics.record_fallback(success=False, latency_ms=5.0)

        assert metrics.total_fallbacks == 3  # nosec B101
        assert metrics.successful_fallbacks == 2  # nosec B101
        assert metrics.failed_fallbacks == 1  # nosec B101
        assert metrics.total_latency_ms == 40.0  # nosec B101

    def test_get_fallback_rate_with_data(self):
        """Test calculating fallback success rate."""
        metrics = FallbackMetrics()

        metrics.record_fallback(success=True, latency_ms=10.0)
        metrics.record_fallback(success=True, latency_ms=10.0)
        metrics.record_fallback(success=False, latency_ms=10.0)
        metrics.record_fallback(success=False, latency_ms=10.0)

        rate = metrics.get_fallback_rate()
        assert rate == 50.0  # 2 out of 4 successful  # nosec B101

    def test_get_fallback_rate_no_data(self):
        """Test fallback rate with no data."""
        metrics = FallbackMetrics()

        rate = metrics.get_fallback_rate()
        assert rate == 0.0  # nosec B101

    def test_get_average_latency_with_data(self):
        """Test calculating average latency."""
        metrics = FallbackMetrics()

        metrics.record_fallback(success=True, latency_ms=10.0)
        metrics.record_fallback(success=True, latency_ms=20.0)
        metrics.record_fallback(success=True, latency_ms=30.0)

        avg = metrics.get_average_latency()
        assert avg == 20.0  # (10 + 20 + 30) / 3  # nosec B101

    def test_get_average_latency_no_data(self):
        """Test average latency with no data."""
        metrics = FallbackMetrics()

        avg = metrics.get_average_latency()
        assert avg == 0.0  # nosec B101

    def test_reset_metrics(self):
        """Test resetting metrics."""
        metrics = FallbackMetrics()

        metrics.record_fallback(success=True, latency_ms=15.0)
        metrics.record_fallback(success=False, latency_ms=10.0)

        metrics.reset()

        assert metrics.total_fallbacks == 0  # nosec B101
        assert metrics.successful_fallbacks == 0  # nosec B101
        assert metrics.failed_fallbacks == 0  # nosec B101
        assert metrics.total_latency_ms == 0.0  # nosec B101


# Unit Tests - FallbackProcessor


class TestFallbackProcessor:
    """Test fallback processor initialization and configuration."""

    def test_initialization_default(self):
        """Test processor initialization with defaults."""
        processor = FallbackProcessor()

        assert processor.router is not None  # nosec B101
        assert isinstance(processor.router, FastIntentRouter)  # nosec B101
        assert processor.metrics is not None  # nosec B101
        assert isinstance(processor.metrics, FallbackMetrics)  # nosec B101
        assert processor.metrics_collector is None  # nosec B101

    def test_initialization_with_router(self):
        """Test processor initialization with custom router."""
        custom_router = FastIntentRouter()
        processor = FallbackProcessor(router=custom_router)

        assert processor.router is custom_router  # nosec B101

    def test_initialization_with_metrics_collector(self):
        """Test processor initialization with metrics collector."""
        collector = MetricsCollector()
        processor = FallbackProcessor(metrics_collector=collector)

        assert processor.metrics_collector is collector  # nosec B101

    def test_detect_llm_unavailable_timeout(self):
        """Test detecting timeout errors."""
        processor = FallbackProcessor()

        error = TimeoutError("Request timed out after 30 seconds")
        assert processor.detect_llm_unavailable(error) is True  # nosec B101

    def test_detect_llm_unavailable_connection(self):
        """Test detecting connection errors."""
        processor = FallbackProcessor()

        error = ConnectionError("Connection refused")
        assert processor.detect_llm_unavailable(error) is True  # nosec B101

    def test_detect_llm_unavailable_service(self):
        """Test detecting service unavailable errors."""
        processor = FallbackProcessor()

        error = Exception("Service unavailable (503)")
        assert processor.detect_llm_unavailable(error) is True  # nosec B101

    def test_detect_llm_unavailable_rate_limit(self):
        """Test detecting rate limit errors."""
        processor = FallbackProcessor()

        error = Exception("Rate limit exceeded: too many requests")
        assert processor.detect_llm_unavailable(error) is True  # nosec B101

    def test_detect_llm_unavailable_other_error(self):
        """Test detecting non-unavailability errors."""
        processor = FallbackProcessor()

        error = ValueError("Invalid input format")
        assert processor.detect_llm_unavailable(error) is False  # nosec B101

    def test_determine_task_type_conversational(self):
        """Test determining conversational task type."""
        processor = FallbackProcessor()

        assert processor._determine_task_type("greeting") == TaskType.CONVERSATIONAL  # nosec B101
        assert processor._determine_task_type("farewell") == TaskType.CONVERSATIONAL  # nosec B101
        assert processor._determine_task_type("help") == TaskType.CONVERSATIONAL  # nosec B101

    def test_determine_task_type_memory_query(self):
        """Test determining memory query task type."""
        processor = FallbackProcessor()

        assert processor._determine_task_type("query_history") == TaskType.MEMORY_QUERY  # nosec B101
        assert processor._determine_task_type("when_did_i") == TaskType.MEMORY_QUERY  # nosec B101

    def test_determine_task_type_single_step(self):
        """Test determining single-step task type."""
        processor = FallbackProcessor()

        assert processor._determine_task_type("set_timer") == TaskType.SINGLE_STEP  # nosec B101
        assert processor._determine_task_type("play_music") == TaskType.SINGLE_STEP  # nosec B101
        assert processor._determine_task_type("query_weather") == TaskType.SINGLE_STEP  # nosec B101

    def test_requires_confirmation_sensitive(self):
        """Test confirmation required for sensitive intents."""
        processor = FallbackProcessor()

        assert processor._requires_confirmation("delete_file") is True  # nosec B101
        assert processor._requires_confirmation("send_message") is True  # nosec B101
        assert processor._requires_confirmation("make_payment") is True  # nosec B101

    def test_requires_confirmation_non_sensitive(self):
        """Test confirmation not required for non-sensitive intents."""
        processor = FallbackProcessor()

        assert processor._requires_confirmation("set_timer") is False  # nosec B101
        assert processor._requires_confirmation("play_music") is False  # nosec B101
        assert processor._requires_confirmation("query_weather") is False  # nosec B101


# Unit Tests - Task Creation


class TestCreateTaskFromMatch:
    """Test creating Task objects from pattern matches."""

    def test_create_task_single_step(self):
        """Test creating single-step task."""
        processor = FallbackProcessor()

        match = PatternMatch(
            intent_type="set_timer",
            entities={"duration": "5 minutes"},
            confidence=0.95,
            quality=MatchQuality.EXACT,
            pattern="set timer {duration}",
            latency_ms=15.0,
        )

        task = processor.create_task_from_match(match, "set timer for 5 minutes")

        assert task.goal == "set timer for 5 minutes"  # nosec B101
        assert task.task_type == TaskType.SINGLE_STEP  # nosec B101
        assert task.entities == {"duration": "5 minutes"}  # nosec B101
        assert len(task.steps) == 1  # nosec B101
        assert task.confidence == 0.95  # nosec B101
        assert task.requires_confirmation is False  # nosec B101
        assert task.status == TaskStatus.PENDING  # nosec B101

    def test_create_task_step_details(self):
        """Test task step details."""
        processor = FallbackProcessor()

        match = PatternMatch(
            intent_type="play_music",
            entities={"artist": "Beatles", "song": "Yesterday"},
            confidence=0.90,
            quality=MatchQuality.EXACT,
            pattern="play {song} by {artist}",
            latency_ms=18.0,
        )

        task = processor.create_task_from_match(match, "play Yesterday by Beatles")

        step = task.steps[0]
        assert step.step_id == 1  # nosec B101
        assert step.description == "Execute play_music with parameters"  # nosec B101
        assert step.tool_id == "play_music"  # nosec B101
        assert step.parameters == {"artist": "Beatles", "song": "Yesterday"}  # nosec B101
        assert step.depends_on == []  # nosec B101
        assert step.estimated_duration == 1.0  # nosec B101
        assert step.status == TaskStatus.PENDING  # nosec B101

    def test_create_task_conversational(self):
        """Test creating conversational task."""
        processor = FallbackProcessor()

        match = PatternMatch(
            intent_type="greeting",
            entities={},
            confidence=0.99,
            quality=MatchQuality.EXACT,
            pattern="hello",
            latency_ms=10.0,
        )

        task = processor.create_task_from_match(match, "hello")

        assert task.task_type == TaskType.CONVERSATIONAL  # nosec B101
        assert task.requires_confirmation is False  # nosec B101

    def test_create_task_memory_query(self):
        """Test creating memory query task."""
        processor = FallbackProcessor()

        match = PatternMatch(
            intent_type="when_did_i",
            entities={"action": "call", "person": "John"},
            confidence=0.85,
            quality=MatchQuality.PARTIAL,
            pattern="when did i {action} {person}",
            latency_ms=20.0,
        )

        task = processor.create_task_from_match(match, "when did I last call John")

        assert task.task_type == TaskType.MEMORY_QUERY  # nosec B101
        assert task.entities == {"action": "call", "person": "John"}  # nosec B101

    def test_create_task_requires_confirmation(self):
        """Test creating task that requires confirmation."""
        processor = FallbackProcessor()

        match = PatternMatch(
            intent_type="delete_file",
            entities={"path": "/important/file.txt"},
            confidence=0.92,
            quality=MatchQuality.EXACT,
            pattern="delete {path}",
            latency_ms=12.0,
        )

        task = processor.create_task_from_match(match, "delete file.txt")

        assert task.requires_confirmation is True  # nosec B101


# Unit Tests - Process with Fallback


class TestProcessWithFallback:
    """Test processing input with fallback."""

    @patch("Agent_Guru.reasoning.llm.fallback_processor.FastIntentRouter")
    def test_process_successful_match(self, mock_router_class):
        """Test successful fallback processing."""
        # Mock router with successful match
        mock_router = Mock()
        mock_match = PatternMatch(
            intent_type="set_timer",
            entities={"duration": "5 minutes"},
            confidence=0.95,
            quality=MatchQuality.EXACT,
            pattern="set timer {duration}",
            latency_ms=15.0,
        )
        mock_router.match.return_value = mock_match

        processor = FallbackProcessor(router=mock_router)

        task = processor.process_with_fallback("set timer for 5 minutes")

        assert task is not None  # nosec B101
        assert task.task_type == TaskType.SINGLE_STEP  # nosec B101
        assert task.confidence == 0.95  # nosec B101
        assert processor.metrics.total_fallbacks == 1  # nosec B101
        assert processor.metrics.successful_fallbacks == 1  # nosec B101

    @patch("Agent_Guru.reasoning.llm.fallback_processor.FastIntentRouter")
    def test_process_no_match(self, mock_router_class):
        """Test fallback with no pattern match."""
        # Mock router with no match
        mock_router = Mock()
        mock_router.match.return_value = None

        processor = FallbackProcessor(router=mock_router)

        task = processor.process_with_fallback("unknown command")

        assert task is None  # nosec B101
        assert processor.metrics.total_fallbacks == 1  # nosec B101
        assert processor.metrics.failed_fallbacks == 1  # nosec B101

    @patch("Agent_Guru.reasoning.llm.fallback_processor.FastIntentRouter")
    def test_process_with_metrics_collector(self, mock_router_class):
        """Test fallback with metrics collector."""
        # Mock router with successful match
        mock_router = Mock()
        mock_match = PatternMatch(
            intent_type="set_timer",
            entities={"duration": "5 minutes"},
            confidence=0.95,
            quality=MatchQuality.EXACT,
            pattern="set timer {duration}",
            latency_ms=15.0,
        )
        mock_router.match.return_value = mock_match

        # Mock metrics collector
        mock_collector = Mock(spec=MetricsCollector)

        processor = FallbackProcessor(router=mock_router, metrics_collector=mock_collector)

        task = processor.process_with_fallback("set timer for 5 minutes")

        assert task is not None  # nosec B101
        # Verify metrics collector was called
        mock_collector.record_stage_latency.assert_called_once()
        call_args = mock_collector.record_stage_latency.call_args
        assert call_args[0][0] == "fallback_processing"  # nosec B101
        assert call_args[0][1] > 0  # Latency should be positive  # nosec B101

    @patch("Agent_Guru.reasoning.llm.fallback_processor.FastIntentRouter")
    def test_process_no_match_with_metrics_collector(self, mock_router_class):
        """Test fallback no match with metrics collector."""
        # Mock router with no match
        mock_router = Mock()
        mock_router.match.return_value = None

        # Mock metrics collector
        mock_collector = Mock(spec=MetricsCollector)

        processor = FallbackProcessor(router=mock_router, metrics_collector=mock_collector)

        task = processor.process_with_fallback("unknown command")

        assert task is None  # nosec B101
        # Verify error was recorded
        mock_collector.increment_errors.assert_called_once_with("fallback_no_match")

    @patch("Agent_Guru.reasoning.llm.fallback_processor.FastIntentRouter")
    def test_process_router_exception(self, mock_router_class):
        """Test fallback with router exception."""
        # Mock router that raises exception
        mock_router = Mock()
        mock_router.match.side_effect = ValueError("Invalid pattern")

        processor = FallbackProcessor(router=mock_router)

        with pytest.raises(ValueError, match="Invalid pattern"):
            processor.process_with_fallback("test input")

        # Verify metrics recorded failure
        assert processor.metrics.total_fallbacks == 1  # nosec B101
        assert processor.metrics.failed_fallbacks == 1  # nosec B101

    @patch("Agent_Guru.reasoning.llm.fallback_processor.FastIntentRouter")
    def test_process_exception_with_metrics_collector(self, mock_router_class):
        """Test fallback exception with metrics collector."""
        # Mock router that raises exception
        mock_router = Mock()
        mock_router.match.side_effect = RuntimeError("Router error")

        # Mock metrics collector
        mock_collector = Mock(spec=MetricsCollector)

        processor = FallbackProcessor(router=mock_router, metrics_collector=mock_collector)

        with pytest.raises(RuntimeError, match="Router error"):
            processor.process_with_fallback("test input")

        # Verify error was recorded
        mock_collector.increment_errors.assert_called_once_with("fallback_error_RuntimeError")


# Unit Tests - Metrics


class TestFallbackProcessorMetrics:
    """Test fallback processor metrics."""

    def test_get_metrics_no_data(self):
        """Test getting metrics with no data."""
        processor = FallbackProcessor()

        metrics = processor.get_metrics()

        assert metrics["total_fallbacks"] == 0.0  # nosec B101
        assert metrics["successful_fallbacks"] == 0.0  # nosec B101
        assert metrics["failed_fallbacks"] == 0.0  # nosec B101
        assert metrics["fallback_success_rate"] == 0.0  # nosec B101
        assert metrics["average_latency_ms"] == 0.0  # nosec B101

    @patch("Agent_Guru.reasoning.llm.fallback_processor.FastIntentRouter")
    def test_get_metrics_with_data(self, mock_router_class):
        """Test getting metrics with data."""
        # Mock router with successful matches
        mock_router = Mock()
        mock_match = PatternMatch(
            intent_type="set_timer",
            entities={"duration": "5 minutes"},
            confidence=0.95,
            quality=MatchQuality.EXACT,
            pattern="set timer {duration}",
            latency_ms=15.0,
        )
        mock_router.match.return_value = mock_match

        processor = FallbackProcessor(router=mock_router)

        # Process multiple inputs
        processor.process_with_fallback("set timer 5 minutes")
        processor.process_with_fallback("set timer 10 minutes")

        # Mock no match for third attempt
        mock_router.match.return_value = None
        processor.process_with_fallback("unknown command")

        metrics = processor.get_metrics()

        assert metrics["total_fallbacks"] == 3.0  # nosec B101
        assert metrics["successful_fallbacks"] == 2.0  # nosec B101
        assert metrics["failed_fallbacks"] == 1.0  # nosec B101
        assert metrics["fallback_success_rate"] == pytest.approx(66.67, rel=0.01)  # nosec B101
        assert metrics["average_latency_ms"] > 0.0  # nosec B101

    def test_reset_metrics(self):
        """Test resetting processor metrics."""
        processor = FallbackProcessor()

        # Add some metrics
        processor.metrics.record_fallback(success=True, latency_ms=15.0)
        processor.metrics.record_fallback(success=False, latency_ms=10.0)

        processor.reset_metrics()

        metrics = processor.get_metrics()
        assert metrics["total_fallbacks"] == 0.0  # nosec B101
        assert metrics["successful_fallbacks"] == 0.0  # nosec B101
        assert metrics["failed_fallbacks"] == 0.0  # nosec B101


# Integration Tests


class TestFallbackProcessorIntegration:
    """Integration tests with real Fast Intent Router."""

    def test_integration_with_real_router(self):
        """Test fallback processor with real router."""
        # Create processor with real router
        processor = FallbackProcessor()

        # Load patterns (assuming patterns file exists)
        try:
            processor.router.load_patterns("Agent_Guru/reasoning/data/intent_patterns.yaml")
        except FileNotFoundError:
            pytest.skip("Patterns file not found")

        # Test with common command
        task = processor.process_with_fallback("set timer for 5 minutes")

        if task is not None:
            assert isinstance(task, Task)  # nosec B101
            assert task.task_type in [TaskType.SINGLE_STEP, TaskType.MULTI_STEP]  # nosec B101
            assert len(task.steps) >= 1  # nosec B101
            assert task.confidence > 0.0  # nosec B101

    def test_integration_metrics_tracking(self):
        """Test metrics tracking in integration."""
        processor = FallbackProcessor()

        # Try to load patterns
        try:
            processor.router.load_patterns("Agent_Guru/reasoning/data/intent_patterns.yaml")
        except FileNotFoundError:
            pytest.skip("Patterns file not found")

        # Process multiple inputs
        inputs = [
            "set timer for 5 minutes",
            "play music",
            "unknown command xyz",
        ]

        for input_text in inputs:
            try:
                processor.process_with_fallback(input_text)
            except OSError as exc:
                logger.debug("Cleanup skipped: %s", exc)  # Ignore errors for this test

        # Verify metrics were tracked
        metrics = processor.get_metrics()
        assert metrics["total_fallbacks"] == len(inputs)  # nosec B101
        assert metrics["average_latency_ms"] > 0.0  # nosec B101
