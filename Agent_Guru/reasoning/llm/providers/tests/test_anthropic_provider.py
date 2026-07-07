"""
Unit tests for Anthropic LLM Provider.

Tests cover:
- Initialization with API key
- Request generation
- Rate limiting
- Circuit breaker
- Retry logic
- Error handling

Coverage Target: 80%+
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from anthropic import APIConnectionError, APIError, APIStatusError, RateLimitError

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.providers.anthropic_provider import AnthropicProvider
from Agent_Guru.reasoning.llm.providers.base import CircuitState, ProviderConfig

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def api_key():
    """Test API key."""
    return "sk-ant-test-key-12345"


@pytest.fixture
def config(api_key):
    """Provider configuration."""
    return ProviderConfig(
        api_key=api_key,
        max_retries=3,
        timeout_seconds=30.0,
        rate_limit_rpm=60,
        rate_limit_tpm=90000,
    )


@pytest.fixture
def provider(config):
    """Anthropic provider instance."""
    return AnthropicProvider(config)


@pytest.fixture
def llm_request():
    """Sample LLM request."""
    return LLMRequest(
        prompt="Hello, world!",
        temperature=0.7,
        top_p=0.9,
        max_tokens=512,
    )


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================


class TestInitialization:
    """Test provider initialization."""

    def test_init_with_config(self, config):
        """Test initialization with explicit config."""
        provider = AnthropicProvider(config)

        assert provider.config == config  # nosec B101
        assert provider.model == "claude-3-5-sonnet-20241022"  # nosec B101
        assert provider.client is not None  # nosec B101
        assert provider.get_provider_type() == LLMProvider.ANTHROPIC  # nosec B101

    def test_init_with_custom_model(self, config):
        """Test initialization with custom model."""
        provider = AnthropicProvider(config, model="claude-3-opus-20240229")

        assert provider.model == "claude-3-opus-20240229"  # nosec B101

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-env-key"})
    def test_init_from_env(self):
        """Test initialization from environment variable."""
        provider = AnthropicProvider()

        assert provider.config.api_key == "sk-ant-env-key"  # nosec B101

    @patch.dict(os.environ, {}, clear=True)
    def test_init_no_api_key(self):
        """Test initialization fails without API key."""
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY environment variable not set"):
            AnthropicProvider()

    def test_get_provider_type(self, provider):
        """Test provider type."""
        assert provider.get_provider_type() == LLMProvider.ANTHROPIC  # nosec B101


# ============================================================================
# GENERATION TESTS
# ============================================================================


class TestGeneration:
    """Test text generation."""

    @pytest.mark.asyncio
    async def test_generate_success(self, provider, llm_request):
        """Test successful generation."""
        # Mock Anthropic response
        mock_content = Mock()
        mock_content.type = "text"
        mock_content.text = "Hello! How can I assist you today?"

        mock_usage = Mock()
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 20

        mock_message = Mock()
        mock_message.content = [mock_content]
        mock_message.stop_reason = "end_turn"
        mock_message.usage = mock_usage

        # Mock the messages.create method
        provider.client.messages = Mock()
        provider.client.messages.create = AsyncMock(return_value=mock_message)

        # Generate
        response = await provider.generate(llm_request)

        # Verify
        assert isinstance(response, LLMResponse)  # nosec B101
        assert response.text == "Hello! How can I assist you today?"  # nosec B101
        assert response.provider == LLMProvider.ANTHROPIC  # nosec B101
        assert response.latency_ms > 0  # nosec B101
        assert response.tokens_generated == 20  # nosec B101
        assert response.finish_reason == "stop"  # nosec B101
        assert response.metadata["model"] == "claude-3-5-sonnet-20241022"  # nosec B101
        assert response.metadata["prompt_tokens"] == 10  # nosec B101
        assert response.metadata["total_tokens"] == 30  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_max_tokens(self, provider, llm_request):
        """Test generation with max tokens reached."""
        # Mock Anthropic response with max_tokens stop reason
        mock_content = Mock()
        mock_content.type = "text"
        mock_content.text = "This is a truncated response"

        mock_usage = Mock()
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 512

        mock_message = Mock()
        mock_message.content = [mock_content]
        mock_message.stop_reason = "max_tokens"
        mock_message.usage = mock_usage

        # Mock the messages.create method
        provider.client.messages = Mock()
        provider.client.messages.create = AsyncMock(return_value=mock_message)

        # Generate
        response = await provider.generate(llm_request)

        # Verify
        assert response.finish_reason == "length"  # nosec B101
        assert response.tokens_generated == 512  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_with_stop_sequences(self, provider):
        """Test generation with stop sequences."""
        llm_request = LLMRequest(
            prompt="Count to 5:",
            stop_sequences=["3", "4"],
        )

        mock_content = Mock()
        mock_content.type = "text"
        mock_content.text = "1, 2, "

        mock_usage = Mock()
        mock_usage.input_tokens = 5
        mock_usage.output_tokens = 5

        mock_message = Mock()
        mock_message.content = [mock_content]
        mock_message.stop_reason = "stop_sequence"
        mock_message.usage = mock_usage

        # Mock the messages.create method
        provider.client.messages = Mock()
        provider.client.messages.create = AsyncMock(return_value=mock_message)

        # Generate
        await provider.generate(llm_request)

        # Verify stop sequences were passed
        call_args = provider.client.messages.create.call_args
        assert call_args.kwargs["stop_sequences"] == ["3", "4"]  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_multiple_content_blocks(self, provider, llm_request):
        """Test generation with multiple content blocks."""
        # Mock Anthropic response with multiple text blocks
        mock_content1 = Mock()
        mock_content1.type = "text"
        mock_content1.text = "Hello! "

        mock_content2 = Mock()
        mock_content2.type = "text"
        mock_content2.text = "How can I help?"

        mock_usage = Mock()
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 15

        mock_message = Mock()
        mock_message.content = [mock_content1, mock_content2]
        mock_message.stop_reason = "end_turn"
        mock_message.usage = mock_usage

        # Mock the messages.create method
        provider.client.messages = Mock()
        provider.client.messages.create = AsyncMock(return_value=mock_message)

        # Generate
        response = await provider.generate(llm_request)

        # Verify text concatenation
        assert response.text == "Hello! How can I help?"  # nosec B101


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


class TestErrorHandling:
    """Test error handling and retries."""

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, provider, llm_request):
        """Test rate limit error handling."""
        # Mock the messages.create method
        provider.client.messages = Mock()
        provider.client.messages.create = AsyncMock(
            side_effect=RateLimitError("Rate limit exceeded", response=Mock(), body=None)
        )

        with pytest.raises(RuntimeError, match="Anthropic rate limit exceeded"):
            await provider.generate(llm_request)

        # Verify circuit breaker recorded failure
        assert provider.circuit_breaker.failure_count > 0  # nosec B101

    @pytest.mark.asyncio
    async def test_connection_error(self, provider, llm_request):
        """Test connection error handling."""
        # Mock the messages.create method
        provider.client.messages = Mock()
        provider.client.messages.create = AsyncMock(side_effect=APIConnectionError(request=Mock()))

        with pytest.raises(RuntimeError, match="Anthropic connection error"):
            await provider.generate(llm_request)

    @pytest.mark.asyncio
    async def test_status_error(self, provider, llm_request):
        """Test HTTP status error handling."""
        mock_response = Mock()
        mock_response.status_code = 500

        # Mock the messages.create method
        provider.client.messages = Mock()
        provider.client.messages.create = AsyncMock(
            side_effect=APIStatusError("Internal server error", response=mock_response, body=None)
        )

        with pytest.raises(RuntimeError, match="Anthropic status error"):
            await provider.generate(llm_request)

    @pytest.mark.asyncio
    async def test_api_error(self, provider, llm_request):
        """Test API error handling."""
        # Mock the messages.create method
        provider.client.messages = Mock()
        provider.client.messages.create = AsyncMock(
            side_effect=APIError("API error", request=Mock(), body=None)
        )

        with pytest.raises(RuntimeError, match="Anthropic API error"):
            await provider.generate(llm_request)

    @pytest.mark.asyncio
    async def test_retry_logic(self, provider, llm_request):
        """Test retry logic with exponential backoff."""
        # Fail twice, then succeed
        mock_content = Mock()
        mock_content.type = "text"
        mock_content.text = "Success!"

        mock_usage = Mock()
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 5

        mock_message = Mock()
        mock_message.content = [mock_content]
        mock_message.stop_reason = "end_turn"
        mock_message.usage = mock_usage

        # Mock the messages.create method
        provider.client.messages = Mock()
        provider.client.messages.create = AsyncMock(
            side_effect=[
                APIConnectionError(request=Mock()),
                APIConnectionError(request=Mock()),
                mock_message,
            ]
        )

        # Should succeed after retries
        response = await provider.generate(llm_request)
        assert response.text == "Success!"  # nosec B101

        # Verify 3 attempts were made
        assert provider.client.messages.create.call_count == 3  # nosec B101


# ============================================================================
# CIRCUIT BREAKER TESTS
# ============================================================================


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self, provider, llm_request):
        """Test circuit breaker opens after threshold failures."""
        # Configure low threshold for testing
        provider.config.circuit_breaker_threshold = 2
        provider.config.max_retries = 1  # Disable retries to test circuit breaker

        # Cause failures
        # Mock the messages.create method
        provider.client.messages = Mock()
        provider.client.messages.create = AsyncMock(side_effect=APIConnectionError(request=Mock()))

        # First failure
        with pytest.raises(RuntimeError):
            await provider.generate(llm_request)

        assert provider.circuit_breaker.state == CircuitState.CLOSED  # nosec B101
        assert provider.circuit_breaker.failure_count == 1  # nosec B101

        # Second failure - should open circuit
        with pytest.raises(RuntimeError):
            await provider.generate(llm_request)

        assert provider.circuit_breaker.state == CircuitState.OPEN  # nosec B101
        assert provider.circuit_breaker.failure_count == 2  # nosec B101

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_requests(self, provider, llm_request):
        """Test circuit breaker rejects requests when open."""
        # Open circuit
        provider.circuit_breaker.state = CircuitState.OPEN
        provider.circuit_breaker.last_failure_time = datetime.now(tz=timezone.utc)

        # Should reject immediately
        with pytest.raises(RuntimeError, match="Circuit breaker is OPEN"):
            await provider.generate(llm_request)

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open(self, provider, llm_request):
        """Test circuit breaker transitions to half-open."""
        # Open circuit with old failure time
        provider.circuit_breaker.state = CircuitState.OPEN
        provider.circuit_breaker.last_failure_time = datetime.now(tz=timezone.utc) - timedelta(seconds=61)
        provider.config.circuit_breaker_timeout = 60.0

        # Mock successful response
        mock_content = Mock()
        mock_content.type = "text"
        mock_content.text = "Success!"

        mock_usage = Mock()
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 5

        mock_message = Mock()
        mock_message.content = [mock_content]
        mock_message.stop_reason = "end_turn"
        mock_message.usage = mock_usage

        # Mock the messages.create method
        provider.client.messages = Mock()
        provider.client.messages.create = AsyncMock(return_value=mock_message)

        # Should allow test request and close circuit on success
        response = await provider.generate(llm_request)
        assert response.text == "Success!"  # nosec B101
        assert provider.circuit_breaker.state == CircuitState.CLOSED  # nosec B101


# ============================================================================
# RATE LIMITING TESTS
# ============================================================================


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limit_tracking(self, provider, llm_request):
        """Test rate limit tracking."""
        # Mock successful response
        mock_content = Mock()
        mock_content.type = "text"
        mock_content.text = "Response"

        mock_usage = Mock()
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 20

        mock_message = Mock()
        mock_message.content = [mock_content]
        mock_message.stop_reason = "end_turn"
        mock_message.usage = mock_usage

        # Mock the messages.create method
        provider.client.messages = Mock()
        provider.client.messages.create = AsyncMock(return_value=mock_message)

        # Make request
        await provider.generate(llm_request)

        # Verify rate limit state updated
        assert provider.rate_limit_state.requests_this_minute == 1  # nosec B101
        assert provider.rate_limit_state.tokens_this_minute == 20  # nosec B101

    @pytest.mark.asyncio
    async def test_rate_limit_reset(self, provider):
        """Test rate limit reset after minute."""
        # Set old minute start
        provider.rate_limit_state.minute_start = datetime.now(tz=timezone.utc) - timedelta(minutes=2)
        provider.rate_limit_state.requests_this_minute = 50
        provider.rate_limit_state.tokens_this_minute = 50000

        # Reset should occur
        provider.rate_limit_state.reset_if_needed()

        assert provider.rate_limit_state.requests_this_minute == 0  # nosec B101
        assert provider.rate_limit_state.tokens_this_minute == 0  # nosec B101


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================


class TestHealthCheck:
    """Test health check functionality."""

    def test_get_health(self, provider):
        """Test health status retrieval."""
        health = provider.get_health()

        assert health["provider"] == "anthropic"  # nosec B101
        assert health["circuit_state"] == "closed"  # nosec B101
        assert health["failure_count"] == 0  # nosec B101
        assert health["last_failure"] is None  # nosec B101
        assert health["last_success"] is None  # nosec B101
        assert health["requests_this_minute"] == 0  # nosec B101
        assert health["tokens_this_minute"] == 0  # nosec B101

    def test_get_health_after_failure(self, provider):
        """Test health status after failure."""
        # Record failure
        provider.circuit_breaker.record_failure(provider.config)

        health = provider.get_health()

        assert health["failure_count"] == 1  # nosec B101
        assert health["last_failure"] is not None  # nosec B101

    def test_get_health_after_success(self, provider):
        """Test health status after success."""
        # Record success
        provider.circuit_breaker.record_success()

        health = provider.get_health()

        assert health["failure_count"] == 0  # nosec B101
        assert health["last_success"] is not None  # nosec B101
