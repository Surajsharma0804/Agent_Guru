"""
Tests for Intent Detection Engine

This module tests the hybrid intent detection engine with all routing paths.

Coverage Target: 80%+
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from Agent_Guru.reasoning.intent.engine import (
    DetectionResult,
    IntentDetectionEngine,
    IntentEngineConfig,
)
from Agent_Guru.reasoning.intent.fast_router import MatchQuality, PatternMatch
from Agent_Guru.reasoning.intent.llm_fallback import LLMClassificationResult
from Agent_Guru.reasoning.intent.ner_extractor import ExtractionResult
from Agent_Guru.reasoning.intent.neural_classifier import ClassificationResult
from Agent_Guru.reasoning.models.intent import Entity, EntityType, Intent


class TestIntentDetectionEngine:
    """Unit tests for Intent Detection Engine."""

    def test_initialization_default_config(self):
        """Test engine initialization with default config."""
        engine = IntentDetectionEngine()

        assert engine.config is not None
        assert engine.config.enable_fast_path is True
        assert engine.config.enable_neural is True
        assert engine.config.enable_llm_fallback is True
        assert engine._initialized is False

    def test_initialization_custom_config(self):
        """Test engine initialization with custom config."""
        config = IntentEngineConfig(
            enable_fast_path=False,
            enable_neural=True,
            enable_llm_fallback=False,
        )
        engine = IntentDetectionEngine(config)

        assert engine.config.enable_fast_path is False
        assert engine.config.enable_neural is True
        assert engine.config.enable_llm_fallback is False

    @patch("Agent_Guru.reasoning.intent.engine.FastIntentRouter")
    @patch("Agent_Guru.reasoning.intent.engine.NeuralIntentClassifier")
    @patch("Agent_Guru.reasoning.intent.engine.NEREntityExtractor")
    @patch("Agent_Guru.reasoning.intent.engine.LLMFallbackClassifier")
    def test_initialize_all_components(self, mock_llm, mock_ner, mock_neural, mock_fast_router):
        """Test initialization of all components."""
        # Mock successful initialization
        mock_fast_router_instance = Mock()
        mock_fast_router_instance._patterns = [{"pattern": "test"}]
        mock_fast_router.return_value = mock_fast_router_instance

        mock_neural_instance = Mock()
        mock_neural.return_value = mock_neural_instance

        mock_ner_instance = Mock()
        mock_ner.return_value = mock_ner_instance

        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance

        # Create engine and initialize
        engine = IntentDetectionEngine()

        with patch("pathlib.Path.exists", return_value=True):
            engine.initialize()

        assert engine._initialized is True
        assert engine.fast_router is not None
        assert engine.neural_classifier is not None
        assert engine.ner_extractor is not None
        assert engine.llm_fallback is not None

    @patch("Agent_Guru.reasoning.intent.engine.FastIntentRouter")
    def test_initialize_fast_path_only(self, mock_fast_router):
        """Test initialization with only fast-path enabled."""
        mock_fast_router_instance = Mock()
        mock_fast_router_instance._patterns = [{"pattern": "test"}]
        mock_fast_router.return_value = mock_fast_router_instance

        config = IntentEngineConfig(
            enable_fast_path=True,
            enable_neural=False,
            enable_llm_fallback=False,
        )
        engine = IntentDetectionEngine(config)

        with patch("pathlib.Path.exists", return_value=True):
            engine.initialize()

        assert engine._initialized is True
        assert engine.fast_router is not None
        assert engine.neural_classifier is None
        assert engine.llm_fallback is None

    @pytest.mark.asyncio
    async def test_detect_intent_not_initialized(self):
        """Test detection fails if engine not initialized."""
        engine = IntentDetectionEngine()

        with pytest.raises(RuntimeError, match="Engine not initialized"):
            await engine.detect_intent_async("test input")

    @pytest.mark.asyncio
    async def test_detect_intent_fast_path_success(self):
        """Test successful detection via fast-path router."""
        engine = IntentDetectionEngine()
        engine._initialized = True

        # Mock fast-path router with high confidence match
        mock_router = Mock()
        mock_match = PatternMatch(
            intent_type="set_timer",
            entities={
                "duration": Entity(
                    entity_type=EntityType.DURATION,
                    value=300,
                    raw_text="5 minutes",
                    confidence=0.95,
                )
            },
            confidence=0.98,
            quality=MatchQuality.EXACT,
            pattern="set timer for {duration}",
            latency_ms=15.0,
        )
        mock_router.match.return_value = mock_match
        engine.fast_router = mock_router

        # Detect intent
        result = await engine.detect_intent_async("set timer for 5 minutes")

        assert result.detection_method == "fast_path"
        assert result.intent.intent_type == "set_timer"
        assert result.confidence == 0.98
        assert result.fast_path_attempted is True
        assert result.neural_attempted is False
        assert result.llm_attempted is False
        assert "duration" in result.intent.entities

    @pytest.mark.asyncio
    async def test_detect_intent_fast_path_low_confidence(self):
        """Test fast-path with low confidence falls back to neural."""
        engine = IntentDetectionEngine()
        engine._initialized = True

        # Mock fast-path router with low confidence
        mock_router = Mock()
        mock_match = PatternMatch(
            intent_type="set_timer",
            entities={},
            confidence=0.7,  # Below threshold
            quality=MatchQuality.PARTIAL,
            pattern="set timer",
            latency_ms=15.0,
        )
        mock_router.match.return_value = mock_match
        engine.fast_router = mock_router

        # Mock neural classifier with high confidence
        mock_neural = Mock()
        mock_neural_result = ClassificationResult(
            intent_type="set_timer",
            confidence=0.92,
            alternative_intents=[("set_alarm", 0.05), ("set_reminder", 0.03)],
            inference_time_ms=45.0,
            used_gpu=True,
        )
        mock_neural.classify.return_value = mock_neural_result
        engine.neural_classifier = mock_neural

        # Mock NER extractor
        mock_ner = Mock()
        mock_ner_result = ExtractionResult(
            entities=[
                Entity(
                    entity_type=EntityType.DURATION,
                    value=300,
                    raw_text="5 minutes",
                    confidence=0.9,
                )
            ],
            extraction_time_ms=20.0,
            used_gpu=True,
            entity_count=1,
        )
        mock_ner.extract.return_value = mock_ner_result
        engine.ner_extractor = mock_ner

        # Detect intent
        result = await engine.detect_intent_async("set timer for 5 minutes")

        assert result.detection_method == "neural"
        assert result.intent.intent_type == "set_timer"
        assert result.confidence == 0.92
        assert result.fast_path_attempted is True
        assert result.neural_attempted is True
        assert result.llm_attempted is False

    @pytest.mark.asyncio
    async def test_detect_intent_neural_low_confidence_llm_fallback(self):
        """Test neural with low confidence falls back to LLM."""
        engine = IntentDetectionEngine()
        engine._initialized = True

        # Mock fast-path router with no match
        mock_router = Mock()
        mock_router.match.return_value = None
        engine.fast_router = mock_router

        # Mock neural classifier with low confidence
        mock_neural = Mock()
        mock_neural_result = ClassificationResult(
            intent_type="unknown",
            confidence=0.5,  # Below threshold
            alternative_intents=[],
            inference_time_ms=45.0,
            used_gpu=True,
        )
        mock_neural.classify.return_value = mock_neural_result
        engine.neural_classifier = mock_neural

        # Mock LLM fallback
        mock_llm = Mock()
        mock_llm_result = LLMClassificationResult(
            intent_type="set_reminder",
            confidence=0.95,
            entities={
                "task": Entity(
                    entity_type=EntityType.TASK,
                    value="call mom",
                    raw_text="call mom",
                    confidence=1.0,
                )
            },
            reasoning="User wants to set a reminder",
            inference_time_ms=250.0,
            retries=0,
            provider="openai",
        )
        mock_llm.classify_async = AsyncMock(return_value=mock_llm_result)
        engine.llm_fallback = mock_llm

        # Detect intent
        result = await engine.detect_intent_async("remind me to call mom")

        assert result.detection_method == "llm_fallback"
        assert result.intent.intent_type == "set_reminder"
        assert result.confidence == 0.95
        assert result.fast_path_attempted is True
        assert result.neural_attempted is True
        assert result.llm_attempted is True

    @pytest.mark.asyncio
    async def test_detect_intent_all_fail_unknown(self):
        """Test all methods fail returns UNKNOWN intent."""
        engine = IntentDetectionEngine()
        engine._initialized = True

        # All components disabled
        engine.fast_router = None
        engine.neural_classifier = None
        engine.llm_fallback = None

        # Detect intent
        result = await engine.detect_intent_async("completely unknown input")

        assert result.detection_method == "fallback"
        assert result.intent.intent_type == "unknown"
        assert result.confidence == 0.0

    def test_detect_intent_sync_wrapper(self):
        """Test synchronous detect_intent wrapper."""
        engine = IntentDetectionEngine()
        engine._initialized = True

        # Mock fast-path router
        mock_router = Mock()
        mock_match = PatternMatch(
            intent_type="query_time",
            entities={},
            confidence=0.99,
            quality=MatchQuality.EXACT,
            pattern="what time is it",
            latency_ms=10.0,
        )
        mock_router.match.return_value = mock_match
        engine.fast_router = mock_router

        # Detect intent synchronously
        result = engine.detect_intent("what time is it")

        assert result.detection_method == "fast_path"
        assert result.intent.intent_type == "query_time"

    def test_create_intent_from_fast_path(self):
        """Test creating Intent from fast-path match."""
        engine = IntentDetectionEngine()

        match = PatternMatch(
            intent_type="set_timer",
            entities={
                "duration": Entity(
                    entity_type=EntityType.DURATION,
                    value=300,
                    raw_text="5 minutes",
                    confidence=0.95,
                )
            },
            confidence=0.98,
            quality=MatchQuality.EXACT,
            pattern="set timer for {duration}",
            latency_ms=15.0,
        )

        intent = engine._create_intent_from_fast_path(match, "set timer for 5 minutes")

        assert intent.intent_type == "set_timer"
        assert intent.confidence == 0.98
        assert intent.requires_reasoning is False
        assert intent.detection_method == "fast_path"
        assert "duration" in intent.entities

    def test_create_intent_from_neural(self):
        """Test creating Intent from neural classifier result."""
        engine = IntentDetectionEngine()

        neural_result = ClassificationResult(
            intent_type="query_weather",
            confidence=0.92,
            alternative_intents=[("query_forecast", 0.05)],
            inference_time_ms=45.0,
            used_gpu=True,
        )

        entities = {
            "location": Entity(
                entity_type=EntityType.LOCATION,
                value="Seattle",
                raw_text="Seattle",
                confidence=0.9,
            )
        }

        intent = engine._create_intent_from_neural(
            neural_result, "what's the weather in Seattle", entities
        )

        assert intent.intent_type == "query_weather"
        assert intent.confidence == 0.92
        assert intent.detection_method == "neural"
        assert "location" in intent.entities
        assert len(intent.alternative_intents) == 1

    def test_create_intent_from_llm(self):
        """Test creating Intent from LLM fallback result."""
        engine = IntentDetectionEngine()

        llm_result = LLMClassificationResult(
            intent_type="send_message",
            confidence=0.95,
            entities={
                "contact": Entity(
                    entity_type=EntityType.PERSON,
                    value="John",
                    raw_text="John",
                    confidence=1.0,
                )
            },
            reasoning="User wants to send a message",
            inference_time_ms=250.0,
            retries=0,
            provider="openai",
        )

        intent = engine._create_intent_from_llm(llm_result, "send message to John")

        assert intent.intent_type == "send_message"
        assert intent.confidence == 0.95
        assert intent.detection_method == "llm_fallback"
        assert "contact" in intent.entities

    def test_requires_reasoning_simple_intents(self):
        """Test simple intents don't require reasoning."""
        engine = IntentDetectionEngine()

        simple_intents = [
            "set_timer",
            "set_alarm",
            "query_time",
            "play_music",
            "pause_media",
        ]

        for intent_type in simple_intents:
            assert engine._requires_reasoning(intent_type) is False

    def test_requires_reasoning_complex_intents(self):
        """Test complex intents require reasoning."""
        engine = IntentDetectionEngine()

        complex_intents = [
            "send_message",
            "create_event",
            "query_weather",
            "search_web",
            "control_device",
        ]

        for intent_type in complex_intents:
            assert engine._requires_reasoning(intent_type) is True

    def test_record_feedback(self):
        """Test recording user feedback."""
        engine = IntentDetectionEngine()

        # Mock feedback store
        mock_store = Mock()
        engine.feedback_store = mock_store

        # Record feedback
        engine.record_feedback(
            text="set timer for 5 minutes",
            predicted_intent="set_alarm",
            correct_intent="set_timer",
            user_id="user123",
        )

        # Verify feedback was recorded
        mock_store.add_feedback.assert_called_once_with(
            input_text="set timer for 5 minutes",
            predicted_intent="set_alarm",
            correct_intent="set_timer",
            user_id="user123",
        )

    def test_trigger_retraining(self):
        """Test triggering model retraining."""
        engine = IntentDetectionEngine()

        # Mock online learner
        mock_learner = Mock()
        engine.online_learner = mock_learner

        # Trigger retraining
        engine.trigger_retraining()

        # Verify retraining was triggered
        mock_learner.retrain_models.assert_called_once()

    def test_update_metrics(self):
        """Test metrics tracking."""
        engine = IntentDetectionEngine()

        # Update metrics for different methods
        engine._update_metrics("fast_path", 15.0)
        engine._update_metrics("fast_path", 20.0)
        engine._update_metrics("neural", 50.0)
        engine._update_metrics("llm_fallback", 250.0)

        assert engine.total_detections == 4
        assert engine.fast_path_hits == 2
        assert engine.neural_hits == 1
        assert engine.llm_hits == 1
        assert engine.total_latency_ms == 335.0

    def test_get_metrics(self):
        """Test getting metrics."""
        engine = IntentDetectionEngine()

        # Add some metrics
        engine._update_metrics("fast_path", 15.0)
        engine._update_metrics("neural", 50.0)
        engine._update_metrics("llm_fallback", 250.0)

        metrics = engine.get_metrics()

        assert metrics["total_detections"] == 3
        assert metrics["average_latency_ms"] == pytest.approx(105.0, rel=0.01)
        assert metrics["fast_path_percent"] == pytest.approx(33.33, rel=0.01)
        assert metrics["neural_percent"] == pytest.approx(33.33, rel=0.01)
        assert metrics["llm_percent"] == pytest.approx(33.33, rel=0.01)

    def test_get_metrics_no_detections(self):
        """Test getting metrics with no detections."""
        engine = IntentDetectionEngine()

        metrics = engine.get_metrics()

        assert metrics["total_detections"] == 0
        assert metrics["average_latency_ms"] == 0.0
        assert metrics["fast_path_percent"] == 0.0

    def test_get_routing_stats(self):
        """Test getting routing statistics."""
        engine = IntentDetectionEngine()

        # Add metrics to simulate 80% fast-path coverage
        for _ in range(80):
            engine._update_metrics("fast_path", 15.0)
        for _ in range(15):
            engine._update_metrics("neural", 50.0)
        for _ in range(5):
            engine._update_metrics("llm_fallback", 250.0)

        stats = engine.get_routing_stats()

        assert stats["total_detections"] == 100
        assert stats["actual_fast_path_percent"] == 80.0
        assert stats["target_fast_path_percent"] == 80.0
        assert "✓ Meeting target" in stats["performance_vs_target"]

    def test_get_routing_stats_below_target(self):
        """Test routing stats when below target."""
        engine = IntentDetectionEngine()

        # Add metrics to simulate 60% fast-path coverage (below target)
        for _ in range(60):
            engine._update_metrics("fast_path", 15.0)
        for _ in range(40):
            engine._update_metrics("neural", 50.0)

        stats = engine.get_routing_stats()

        assert stats["actual_fast_path_percent"] == 60.0
        assert "⚠ Below target" in stats["performance_vs_target"]

    def test_get_routing_stats_no_detections(self):
        """Test routing stats with no detections."""
        engine = IntentDetectionEngine()

        stats = engine.get_routing_stats()

        assert stats["total_detections"] == 0
        assert stats["performance_vs_target"] == "N/A"


class TestIntentEngineConfig:
    """Tests for IntentEngineConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = IntentEngineConfig()

        assert config.enable_fast_path is True
        assert config.enable_neural is True
        assert config.enable_llm_fallback is True
        assert config.enable_online_learning is True
        assert "intent_patterns.yaml" in config.patterns_file
        assert "feedback.db" in config.feedback_db_path

    def test_custom_config(self):
        """Test custom configuration values."""
        config = IntentEngineConfig(
            patterns_file="/custom/patterns.yaml",
            enable_fast_path=False,
            enable_neural=True,
            enable_llm_fallback=False,
            enable_online_learning=False,
            feedback_db_path="/custom/feedback.db",
        )

        assert config.patterns_file == "/custom/patterns.yaml"
        assert config.enable_fast_path is False
        assert config.enable_neural is True
        assert config.enable_llm_fallback is False
        assert config.enable_online_learning is False
        assert config.feedback_db_path == "/custom/feedback.db"


class TestDetectionResult:
    """Tests for DetectionResult."""

    def test_detection_result_creation(self):
        """Test creating DetectionResult."""
        intent = Intent(
            intent_type="set_timer",
            entities={},
            confidence=0.95,
            requires_reasoning=False,
            original_input="set timer",
            resolved_input="set timer",
            detection_method="fast_path",
        )

        result = DetectionResult(
            intent=intent,
            detection_method="fast_path",
            latency_ms=15.0,
            fast_path_attempted=True,
            neural_attempted=False,
            llm_attempted=False,
            confidence=0.95,
        )

        assert result.intent.intent_type == "set_timer"
        assert result.detection_method == "fast_path"
        assert result.latency_ms == 15.0
        assert result.fast_path_attempted is True
        assert result.neural_attempted is False
        assert result.llm_attempted is False
        assert result.confidence == 0.95
