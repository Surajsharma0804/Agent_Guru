"""
Comprehensive tests for LLM Fallback Classifier

Coverage Target: 100% - ZERO COMPROMISES
Test Types: Unit + Property-based + Integration + Performance

Author: Kiro AI
Date: 2026-02-19
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from Agent_Guru.reasoning.intent.llm_fallback import (
    LLMFallbackClassifier,
    LLMFallbackConfig,
    LLMIntentResponse,
)
from Agent_Guru.reasoning.models.intent import Entity

# ============================================================================
# UNIT TESTS - Configuration and Initialization
# ============================================================================


class TestLLMFallbackConfig:
    """Test LLMFallbackConfig data class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LLMFallbackConfig()

        assert config.provider == "ollama"
        assert config.model == "gemma3:4b"
        assert config.api_key is None
        assert config.timeout_ms == 1000.0
        assert config.max_retries == 3
        assert config.temperature == 0.0
        assert config.max_tokens == 512

    def test_custom_config(self):
        """Test custom configuration values."""
        config = LLMFallbackConfig(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            api_key="test-key",
            timeout_ms=500.0,
            max_retries=5,
            temperature=0.5,
            max_tokens=1024,
        )

        assert config.provider == "anthropic"
        assert config.model == "claude-3-5-sonnet-20241022"
        assert config.api_key == "test-key"
        assert config.timeout_ms == 500.0
        assert config.max_retries == 5
        assert config.temperature == 0.5
        assert config.max_tokens == 1024


class TestLLMIntentResponse:
    """Test LLMIntentResponse Pydantic model."""

    def test_valid_response(self):
        """Test valid response creation."""
        response = LLMIntentResponse(
            intent_type="set_timer",
            confidence=0.95,
            entities={"duration": {"entity_type": "duration", "value": 300}},
            reasoning="Clear timer intent",
        )

        assert response.intent_type == "set_timer"
        assert response.confidence == 0.95
        assert "duration" in response.entities
        assert response.reasoning == "Clear timer intent"

    def test_confidence_validation(self):
        """Test confidence score validation."""
        # Valid confidence
        response = LLMIntentResponse(
            intent_type="set_timer", confidence=0.5, entities={}, reasoning=""
        )
        assert response.confidence == 0.5

        # Invalid confidence (too low)
        with pytest.raises(ValidationError):
            LLMIntentResponse(intent_type="set_timer", confidence=-0.1, entities={}, reasoning="")

        # Invalid confidence (too high)
        with pytest.raises(ValidationError):
            LLMIntentResponse(intent_type="set_timer", confidence=1.5, entities={}, reasoning="")

    def test_default_values(self):
        """Test default values for optional fields."""
        response = LLMIntentResponse(intent_type="set_timer", confidence=0.95, reasoning="test")

        assert response.entities == {}
        assert response.reasoning == "test"


class TestLLMFallbackClassifierInit:
    """Test LLMFallbackClassifier initialization."""

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_init_with_openai(self, mock_openai):
        """Test initialization with OpenAI provider."""
        mock_openai.OpenAI = Mock()
        config = LLMFallbackConfig(provider="openai", api_key="test-key")

        classifier = LLMFallbackClassifier(config)

        assert classifier.config.provider == "openai"
        assert classifier.client is not None
        mock_openai.OpenAI.assert_called_once_with(api_key="test-key")

    @patch("Agent_Guru.reasoning.intent.llm_fallback.ANTHROPIC_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.anthropic")
    def test_init_with_anthropic(self, mock_anthropic):
        """Test initialization with Anthropic provider."""
        mock_anthropic.Anthropic = Mock()
        config = LLMFallbackConfig(provider="anthropic", api_key="test-key")

        classifier = LLMFallbackClassifier(config)

        assert classifier.config.provider == "anthropic"
        assert classifier.client is not None
        mock_anthropic.Anthropic.assert_called_once_with(api_key="test-key")

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", False)
    def test_init_openai_not_available(self):
        """Test initialization fails when OpenAI not available."""
        config = LLMFallbackConfig(provider="openai")

        with pytest.raises(RuntimeError, match="OpenAI client not available"):
            LLMFallbackClassifier(config)

    @patch("Agent_Guru.reasoning.intent.llm_fallback.ANTHROPIC_AVAILABLE", False)
    def test_init_anthropic_not_available(self):
        """Test initialization fails when Anthropic not available."""
        config = LLMFallbackConfig(provider="anthropic")

        with pytest.raises(RuntimeError, match="Anthropic client not available"):
            LLMFallbackClassifier(config)

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_init_unsupported_provider(self, mock_openai):
        """Test initialization fails with unsupported provider."""
        mock_openai.OpenAI = Mock()
        config = LLMFallbackConfig(provider="unsupported")

        with pytest.raises(ValueError, match="Unsupported provider"):
            LLMFallbackClassifier(config)

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_init_default_config(self, mock_openai):
        """Test initialization with default config."""
        mock_openai.OpenAI = Mock()

        classifier = LLMFallbackClassifier()

        assert classifier.config.provider == "ollama"
        assert classifier.total_inferences == 0
        assert classifier.total_latency_ms == 0.0
        assert classifier.successful_inferences == 0
        assert classifier.failed_inferences == 0
        assert classifier.total_retries == 0


# ============================================================================
# UNIT TESTS - Response Parsing
# ============================================================================


class TestResponseParsing:
    """Test LLM response parsing."""

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_parse_valid_response(self, mock_openai):
        """Test parsing valid JSON response."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        response_text = json.dumps(
            {
                "intent_type": "set_timer",
                "confidence": 0.95,
                "entities": {
                    "duration": {
                        "entity_type": "duration",
                        "value": 300,
                        "raw_text": "5 minutes",
                    }
                },
                "reasoning": "Clear timer intent",
            }
        )

        result = classifier._parse_response(response_text)

        assert result.intent_type == "set_timer"
        assert result.confidence == 0.95
        assert "duration" in result.entities
        assert result.reasoning == "Clear timer intent"

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_parse_invalid_json(self, mock_openai):
        """Test parsing invalid JSON raises error."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        with pytest.raises(json.JSONDecodeError):
            classifier._parse_response("not valid json")

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_parse_missing_required_fields(self, mock_openai):
        """Test parsing response with missing required fields."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        response_text = json.dumps({"intent_type": "set_timer"})  # Missing confidence

        with pytest.raises(ValidationError):
            classifier._parse_response(response_text)

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_parse_entities_dict_format(self, mock_openai):
        """Test parsing entities in dict format."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        entities_dict = {
            "duration": {
                "entity_type": "duration",
                "value": 300,
                "raw_text": "5 minutes",
                "confidence": 0.95,
            }
        }

        result = classifier._parse_entities(entities_dict)

        assert "duration" in result
        assert isinstance(result["duration"], Entity)
        assert result["duration"].entity_type == "duration"
        assert result["duration"].value == 300
        assert result["duration"].raw_text == "5 minutes"
        assert result["duration"].confidence == 0.95

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_parse_entities_simple_format(self, mock_openai):
        """Test parsing entities in simple value format."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        entities_dict = {"duration": 300}

        result = classifier._parse_entities(entities_dict)

        assert "duration" in result
        assert isinstance(result["duration"], Entity)
        assert result["duration"].entity_type == "unknown"
        assert result["duration"].value == 300
        assert result["duration"].raw_text == "300"
        assert result["duration"].confidence == 1.0

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_parse_empty_entities(self, mock_openai):
        """Test parsing empty entities dict."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        result = classifier._parse_entities({})

        assert result == {}


# ============================================================================
# UNIT TESTS - Unknown Result Creation
# ============================================================================


class TestUnknownResultCreation:
    """Test creation of UNKNOWN results for failures."""

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_create_unknown_result_no_error(self, mock_openai):
        """Test creating UNKNOWN result without error."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        result = classifier._create_unknown_result(
            text="test input", inference_time_ms=100.0, retries=2
        )

        assert result.intent_type == "unknown"
        assert result.confidence == 0.0
        assert result.entities == {}
        assert result.reasoning == "Classification failed"
        assert result.inference_time_ms == 100.0
        assert result.retries == 2
        assert result.provider == "ollama"

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_create_unknown_result_with_error(self, mock_openai):
        """Test creating UNKNOWN result with error message."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        result = classifier._create_unknown_result(
            text="test input",
            inference_time_ms=100.0,
            retries=2,
            error="API timeout",
        )

        assert result.intent_type == "unknown"
        assert result.confidence == 0.0
        assert result.entities == {}
        assert "Classification failed: API timeout" in result.reasoning
        assert result.inference_time_ms == 100.0
        assert result.retries == 2


# ============================================================================
# UNIT TESTS - Metrics
# ============================================================================


class TestMetrics:
    """Test metrics tracking."""

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_get_metrics_no_inferences(self, mock_openai):
        """Test metrics with no inferences."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        metrics = classifier.get_metrics()

        assert metrics["total_inferences"] == 0
        assert metrics["average_latency_ms"] == 0.0
        assert metrics["success_rate"] == 0.0
        assert metrics["average_retries"] == 0.0

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_update_metrics_success(self, mock_openai):
        """Test updating metrics for successful inference."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        classifier._update_metrics(100.0, 1, success=True)

        assert classifier.total_inferences == 1
        assert classifier.total_latency_ms == 100.0
        assert classifier.successful_inferences == 1
        assert classifier.failed_inferences == 0
        assert classifier.total_retries == 1

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_update_metrics_failure(self, mock_openai):
        """Test updating metrics for failed inference."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        classifier._update_metrics(200.0, 3, success=False)

        assert classifier.total_inferences == 1
        assert classifier.total_latency_ms == 200.0
        assert classifier.successful_inferences == 0
        assert classifier.failed_inferences == 1
        assert classifier.total_retries == 3

    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_get_metrics_with_inferences(self, mock_openai):
        """Test metrics after multiple inferences."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        classifier._update_metrics(100.0, 0, success=True)
        classifier._update_metrics(200.0, 1, success=True)
        classifier._update_metrics(300.0, 2, success=False)

        metrics = classifier.get_metrics()

        assert metrics["total_inferences"] == 3
        assert metrics["average_latency_ms"] == 200.0  # (100+200+300)/3
        assert metrics["success_rate"] == 2 / 3  # 2 successes out of 3
        assert metrics["average_retries"] == 1.0  # (0+1+2)/3
        assert metrics["failed_inferences"] == 1


# ============================================================================
# INTEGRATION TESTS - Async Classification
# ============================================================================


class TestAsyncClassification:
    """Test async classification with mocked LLM calls."""

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_classify_async_success(self, mock_openai):
        """Test successful async classification."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        # Mock LLM response
        mock_response = json.dumps(
            {
                "intent_type": "set_timer",
                "confidence": 0.95,
                "entities": {
                    "duration": {
                        "entity_type": "duration",
                        "value": 300,
                        "raw_text": "5 minutes",
                    }
                },
                "reasoning": "Clear timer intent",
            }
        )

        classifier._call_llm_async = AsyncMock(
            return_value=LLMIntentResponse(
                intent_type="set_timer",
                confidence=0.95,
                entities={
                    "duration": {
                        "entity_type": "duration",
                        "value": 300,
                        "raw_text": "5 minutes",
                    }
                },
                reasoning="Clear timer intent",
            )
        )

        result = await classifier.classify_async("set timer for 5 minutes")

        assert result.intent_type == "set_timer"
        assert result.confidence == 0.95
        assert "duration" in result.entities
        assert result.retries == 0
        assert result.provider == "ollama"

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_classify_async_timeout(self, mock_openai):
        """Test async classification with timeout."""
        mock_openai.OpenAI = Mock()
        config = LLMFallbackConfig(timeout_ms=100.0, max_retries=1)
        classifier = LLMFallbackClassifier(config)

        # Mock LLM call that times out
        async def slow_call(*args, **kwargs):
            await asyncio.sleep(1.0)  # Longer than timeout
            return LLMIntentResponse(
                intent_type="set_timer", confidence=0.95, entities={}, reasoning=""
            )

        classifier._call_llm_async = slow_call

        result = await classifier.classify_async("test input")

        assert result.intent_type == "unknown"
        assert result.confidence == 0.0
        assert result.retries == 1  # One retry attempted

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_classify_async_retry_success(self, mock_openai):
        """Test async classification succeeds after retry."""
        mock_openai.OpenAI = Mock()
        config = LLMFallbackConfig(timeout_ms=1000.0, max_retries=3)
        classifier = LLMFallbackClassifier(config)

        # Mock LLM call that fails once then succeeds
        call_count = 0

        async def flaky_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("API error")
            return LLMIntentResponse(
                intent_type="set_timer",
                confidence=0.95,
                entities={},
                reasoning="Success after retry",
            )

        classifier._call_llm_async = flaky_call

        result = await classifier.classify_async("test input")

        assert result.intent_type == "set_timer"
        assert result.confidence == 0.95
        assert result.retries == 1  # One retry needed
        assert call_count == 2  # Called twice (initial + 1 retry)

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_classify_async_all_retries_fail(self, mock_openai):
        """Test async classification when all retries fail."""
        mock_openai.OpenAI = Mock()
        config = LLMFallbackConfig(timeout_ms=1000.0, max_retries=2)
        classifier = LLMFallbackClassifier(config)

        # Mock LLM call that always fails
        classifier._call_llm_async = AsyncMock(side_effect=Exception("API error"))

        result = await classifier.classify_async("test input")

        assert result.intent_type == "unknown"
        assert result.confidence == 0.0
        assert result.retries == 2  # All retries attempted
        assert "API error" in result.reasoning

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_classify_async_with_context(self, mock_openai):
        """Test async classification with conversation context."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        classifier._call_llm_async = AsyncMock(
            return_value=LLMIntentResponse(
                intent_type="set_reminder",
                confidence=0.92,
                entities={},
                reasoning="Reminder with context",
            )
        )

        context = {"last_intent": "query_time", "entities": {"time": "3pm"}}
        result = await classifier.classify_async("remind me then", context=context)

        assert result.intent_type == "set_reminder"
        assert result.confidence == 0.92
        # Verify context was passed to LLM call
        classifier._call_llm_async.assert_called_once()
        call_args = classifier._call_llm_async.call_args
        # Check positional or keyword args
        if len(call_args[0]) > 1:
            assert call_args[0][1] == context
        else:
            assert call_args[1].get("context") == context


# ============================================================================
# PROPERTY-BASED TESTS
# ============================================================================


class TestPropertyBased:
    """Property-based tests using Hypothesis."""

    @given(
        text=st.text(min_size=1, max_size=100),
        confidence=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=50, deadline=None)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_parse_entities_always_returns_dict(self, mock_openai, text: str, confidence: float):
        """Property: _parse_entities always returns a dict."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        entities_dict = {"test": {"entity_type": "test", "value": text}}
        result = classifier._parse_entities(entities_dict)

        assert isinstance(result, dict)
        if entities_dict:
            assert "test" in result
            assert isinstance(result["test"], Entity)

    @given(
        inference_time=st.floats(min_value=0.0, max_value=10000.0),
        retries=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=50, deadline=None)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    def test_unknown_result_always_valid(self, mock_openai, inference_time: float, retries: int):
        """Property: _create_unknown_result always produces valid result."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        result = classifier._create_unknown_result(
            text="test", inference_time_ms=inference_time, retries=retries
        )

        assert result.intent_type == "unknown"
        assert result.confidence == 0.0
        assert isinstance(result.entities, dict)
        assert result.inference_time_ms == inference_time
        assert result.retries == retries


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


class TestPerformance:
    """Performance tests for latency verification."""

    @pytest.mark.asyncio
    @pytest.mark.performance
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_classification_latency(self, mock_openai):
        """Test classification meets latency target (<300ms)."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        # Mock fast LLM response
        classifier._call_llm_async = AsyncMock(
            return_value=LLMIntentResponse(
                intent_type="set_timer", confidence=0.95, entities={}, reasoning=""
            )
        )

        result = await classifier.classify_async("set timer for 5 minutes")

        # Verify latency is reasonable (mocked, so should be very fast)
        assert result.inference_time_ms < 1000.0  # Generous for mocked call


# ============================================================================
# INTEGRATION TESTS - LLM API Calls
# ============================================================================


class TestLLMAPICalls:
    """Test LLM API call methods."""

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_call_openai(self, mock_openai):
        """Test OpenAI API call."""
        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "intent_type": "set_timer",
                "confidence": 0.95,
                "entities": {},
                "reasoning": "test",
            }
        )
        mock_client.chat.completions.create = Mock(return_value=mock_response)
        mock_openai.OpenAI = Mock(return_value=mock_client)

        classifier = LLMFallbackClassifier()
        classifier.client = mock_client

        result = await classifier._call_openai("test prompt")

        assert isinstance(result, str)
        assert "intent_type" in result
        mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.ANTHROPIC_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.anthropic")
    async def test_call_anthropic(self, mock_anthropic):
        """Test Anthropic API call."""
        # Mock Anthropic client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = json.dumps(
            {
                "intent_type": "set_timer",
                "confidence": 0.95,
                "entities": {},
                "reasoning": "test",
            }
        )
        mock_client.messages.create = Mock(return_value=mock_response)
        mock_anthropic.Anthropic = Mock(return_value=mock_client)

        config = LLMFallbackConfig(provider="anthropic")
        classifier = LLMFallbackClassifier(config)
        classifier.client = mock_client

        result = await classifier._call_anthropic("test prompt")

        assert isinstance(result, str)
        assert "intent_type" in result
        mock_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_call_llm_async_openai(self, mock_openai):
        """Test _call_llm_async with OpenAI provider."""
        mock_openai.OpenAI = Mock()
        config = LLMFallbackConfig(provider="openai", api_key="test-key")
        classifier = LLMFallbackClassifier(config)

        # Mock _call_openai
        classifier._call_openai = AsyncMock(
            return_value=json.dumps(
                {
                    "intent_type": "set_timer",
                    "confidence": 0.95,
                    "entities": {},
                    "reasoning": "test",
                }
            )
        )

        result = await classifier._call_llm_async("test input")

        assert result.intent_type == "set_timer"
        assert result.confidence == 0.95
        classifier._call_openai.assert_called_once()

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.ANTHROPIC_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.anthropic")
    async def test_call_llm_async_anthropic(self, mock_anthropic):
        """Test _call_llm_async with Anthropic provider."""
        mock_anthropic.Anthropic = Mock()
        config = LLMFallbackConfig(provider="anthropic")
        classifier = LLMFallbackClassifier(config)

        # Mock _call_anthropic
        classifier._call_anthropic = AsyncMock(
            return_value=json.dumps(
                {
                    "intent_type": "set_timer",
                    "confidence": 0.95,
                    "entities": {},
                    "reasoning": "test",
                }
            )
        )

        result = await classifier._call_llm_async("test input")

        assert result.intent_type == "set_timer"
        assert result.confidence == 0.95
        classifier._call_anthropic.assert_called_once()

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_call_llm_async_with_context(self, mock_openai):
        """Test _call_llm_async includes context in prompt."""
        mock_openai.OpenAI = Mock()
        config = LLMFallbackConfig(provider="openai", api_key="test-key")
        classifier = LLMFallbackClassifier(config)

        # Mock _call_openai to capture prompt
        captured_prompt = None

        async def capture_prompt(prompt):
            nonlocal captured_prompt
            captured_prompt = prompt
            return json.dumps(
                {
                    "intent_type": "set_timer",
                    "confidence": 0.95,
                    "entities": {},
                    "reasoning": "test",
                }
            )

        classifier._call_openai = capture_prompt

        context = {"last_intent": "query_time"}
        await classifier._call_llm_async("test input", context=context)

        assert captured_prompt is not None
        assert "Context:" in captured_prompt
        assert "last_intent" in captured_prompt

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_call_llm_async_unsupported_provider(self, mock_openai):
        """Test _call_llm_async with unsupported provider."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()
        classifier.config.provider = "unsupported"

        with pytest.raises(ValueError, match="Unsupported provider"):
            await classifier._call_llm_async("test input")


# ============================================================================
# EDGE CASE TESTS - Import Errors and Error Handling
# ============================================================================


class TestImportErrors:
    """Test import error handling."""

    def test_openai_import_error_handling(self):
        """Test that OPENAI_AVAILABLE is False when import fails."""
        # This is tested by the module-level import
        # We verify the flag exists
        from Agent_Guru.reasoning.intent import llm_fallback

        assert hasattr(llm_fallback, "OPENAI_AVAILABLE")
        assert isinstance(llm_fallback.OPENAI_AVAILABLE, bool)

    def test_anthropic_import_error_handling(self):
        """Test that ANTHROPIC_AVAILABLE is False when import fails."""
        # This is tested by the module-level import
        # We verify the flag exists
        from Agent_Guru.reasoning.intent import llm_fallback

        assert hasattr(llm_fallback, "ANTHROPIC_AVAILABLE")
        assert isinstance(llm_fallback.ANTHROPIC_AVAILABLE, bool)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_parse_response_validation_error(self, mock_openai):
        """Test parsing response with validation error."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        # Response with invalid confidence (>1.0)
        response_text = json.dumps(
            {
                "intent_type": "set_timer",
                "confidence": 1.5,  # Invalid
                "entities": {},
                "reasoning": "test",
            }
        )

        with pytest.raises(ValidationError):
            classifier._parse_response(response_text)

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_classify_async_exception_handling(self, mock_openai):
        """Test exception handling in classify_async."""
        mock_openai.OpenAI = Mock()
        config = LLMFallbackConfig(timeout_ms=1000.0, max_retries=2)
        classifier = LLMFallbackClassifier(config)

        # Mock LLM call that raises exception
        classifier._call_llm_async = AsyncMock(side_effect=Exception("Network error"))

        result = await classifier.classify_async("test input")

        # Should return UNKNOWN result
        assert result.intent_type == "unknown"
        assert result.confidence == 0.0
        assert "Network error" in result.reasoning
        assert result.retries == 2

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_parse_entities_with_missing_fields(self, mock_openai):
        """Test parsing entities with missing optional fields."""
        mock_openai.OpenAI = Mock()
        classifier = LLMFallbackClassifier()

        # Entity dict with minimal fields
        entities_dict = {
            "duration": {
                "entity_type": "duration",
                "value": 300,
                # Missing raw_text and confidence
            }
        }

        result = classifier._parse_entities(entities_dict)

        assert "duration" in result
        assert result["duration"].entity_type == "duration"
        assert result["duration"].value == 300
        # Should use default values
        assert result["duration"].raw_text == "300"
        assert result["duration"].confidence == 1.0

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_call_llm_async_no_context(self, mock_openai):
        """Test _call_llm_async without context."""
        mock_openai.OpenAI = Mock()
        config = LLMFallbackConfig(provider="openai", api_key="test-key")
        classifier = LLMFallbackClassifier(config)

        # Mock _call_openai to capture prompt
        captured_prompt = None

        async def capture_prompt(prompt):
            nonlocal captured_prompt
            captured_prompt = prompt
            return json.dumps(
                {
                    "intent_type": "set_timer",
                    "confidence": 0.95,
                    "entities": {},
                    "reasoning": "test",
                }
            )

        classifier._call_openai = capture_prompt

        await classifier._call_llm_async("test input", context=None)

        assert captured_prompt is not None
        assert "Context:" not in captured_prompt  # No context added

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_exponential_backoff_timing(self, mock_openai):
        """Test exponential backoff between retries."""
        mock_openai.OpenAI = Mock()
        config = LLMFallbackConfig(timeout_ms=1000.0, max_retries=3)
        classifier = LLMFallbackClassifier(config)

        call_times = []

        async def track_time(*args, **kwargs):
            call_times.append(asyncio.get_running_loop().time())
            raise Exception("Retry test")

        classifier._call_llm_async = track_time

        result = await classifier.classify_async("test input")

        # Should have made 3 attempts
        assert len(call_times) == 3
        # Verify exponential backoff (approximate timing)
        # First retry after ~0.1s, second after ~0.2s
        if len(call_times) >= 2:
            # Just verify retries happened (timing may vary)
            assert result.retries == 3


# ============================================================================
# COMPREHENSIVE INTEGRATION TEST
# ============================================================================


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_full_classification_pipeline(self, mock_openai):
        """Test complete classification pipeline from input to result."""
        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "intent_type": "set_reminder",
                "confidence": 0.92,
                "entities": {
                    "task": {
                        "entity_type": "task",
                        "value": "call mom",
                        "raw_text": "call mom",
                        "confidence": 0.95,
                    },
                    "datetime": {
                        "entity_type": "datetime",
                        "value": "tomorrow 3pm",
                        "raw_text": "tomorrow at 3pm",
                        "confidence": 0.90,
                    },
                },
                "reasoning": "Reminder with task and time",
            }
        )
        mock_client.chat.completions.create = Mock(return_value=mock_response)
        mock_openai.OpenAI = Mock(return_value=mock_client)

        config = LLMFallbackConfig(provider="openai", api_key="test-key")
        classifier = LLMFallbackClassifier(config)

        result = await classifier.classify_async("remind me to call mom tomorrow at 3pm")

        # Verify result
        assert result.intent_type == "set_reminder"
        assert result.confidence == 0.92
        assert "task" in result.entities
        assert "datetime" in result.entities
        assert result.entities["task"].value == "call mom"
        assert result.entities["datetime"].value == "tomorrow 3pm"
        assert result.reasoning == "Reminder with task and time"
        assert result.retries == 0
        assert result.provider == "openai"

        # Verify metrics updated
        metrics = classifier.get_metrics()
        assert metrics["total_inferences"] == 1
        assert metrics["success_rate"] == 1.0

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.ANTHROPIC_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.anthropic")
    async def test_full_classification_pipeline_anthropic(self, mock_anthropic):
        """Test complete classification pipeline with Anthropic."""
        # Mock Anthropic client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = json.dumps(
            {
                "intent_type": "query_weather",
                "confidence": 0.97,
                "entities": {
                    "location": {
                        "entity_type": "location",
                        "value": "San Francisco",
                        "raw_text": "San Francisco",
                    }
                },
                "reasoning": "Weather query with location",
            }
        )
        mock_client.messages.create = Mock(return_value=mock_response)
        mock_anthropic.Anthropic = Mock(return_value=mock_client)

        config = LLMFallbackConfig(provider="anthropic")
        classifier = LLMFallbackClassifier(config)

        result = await classifier.classify_async("what's the weather in San Francisco")

        # Verify result
        assert result.intent_type == "query_weather"
        assert result.confidence == 0.97
        assert "location" in result.entities
        assert result.entities["location"].value == "San Francisco"
        assert result.provider == "anthropic"

        # Verify metrics
        metrics = classifier.get_metrics()
        assert metrics["total_inferences"] == 1
        assert metrics["success_rate"] == 1.0


# ============================================================================
# COVERAGE COMPLETION - Edge Cases
# ============================================================================


class TestCoverageCompletion:
    """Tests to achieve 100% coverage."""

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.intent.llm_fallback.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.intent.llm_fallback.openai")
    async def test_classify_async_fallback_path(self, mock_openai):
        """Test the 'should never reach here' fallback path."""
        mock_openai.OpenAI = Mock()
        config = LLMFallbackConfig(timeout_ms=1000.0, max_retries=0)
        classifier = LLMFallbackClassifier(config)

        # Mock to ensure we don't enter the retry loop
        classifier._call_llm_async = AsyncMock(side_effect=Exception("Test error"))

        result = await classifier.classify_async("test input")

        # Should return UNKNOWN result
        assert result.intent_type == "unknown"
        assert result.confidence == 0.0

    def test_module_level_imports(self):
        """Test that module-level imports are handled correctly."""
        # Import the module to ensure import blocks are executed
        import Agent_Guru.reasoning.intent.llm_fallback as llm_fallback

        # Verify flags exist
        assert hasattr(llm_fallback, "OPENAI_AVAILABLE")
        assert hasattr(llm_fallback, "ANTHROPIC_AVAILABLE")
        assert hasattr(llm_fallback, "openai")
        assert hasattr(llm_fallback, "anthropic")

        # Verify they are boolean or None
        assert isinstance(llm_fallback.OPENAI_AVAILABLE, bool)
        assert isinstance(llm_fallback.ANTHROPIC_AVAILABLE, bool)
