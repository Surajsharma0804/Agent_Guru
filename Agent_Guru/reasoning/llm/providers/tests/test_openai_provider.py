"""
Unit tests for OpenAI LLM Provider.

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
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.providers.base import CircuitState, ProviderConfig
from Agent_Guru.reasoning.llm.providers.openai_provider import OpenAIProvider

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def api_key():
    """Test API key."""
    return "sk-test-key-12345"


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
    """OpenAI provider instance."""
    return OpenAIProvider(config)


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
        provider = OpenAIProvider(config)

        assert provider.config == config  # nosec B101
        assert provider.model == "gpt-4-turbo-preview"  # nosec B101
        assert provider.client is not None  # nosec B101
        assert provider.get_provider_type() == LLMProvider.OPENAI  # nosec B101

    def test_init_with_custom_model(self, config):
        """Test initialization with custom model."""
        provider = OpenAIProvider(config, model="gpt-4")

        assert provider.model == "gpt-4"  # nosec B101

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-key"})
    def test_init_from_env(self):
        """Test initialization from environment variable."""
        provider = OpenAIProvider()

        assert provider.config.api_key == "sk-env-key"  # nosec B101

    @patch.dict(os.environ, {}, clear=True)
    def test_init_no_api_key(self):
        """Test initialization fails without API key."""
        with pytest.raises(ValueError, match="OPENAI_API_KEY environment variable not set"):
            OpenAIProvider()

    def test_get_provider_type(self, provider):
        """Test provider type."""
        assert provider.get_provider_type() == LLMProvider.OPENAI  # nosec B101


# ============================================================================
# GENERATION TESTS
# ============================================================================


class TestGeneration:
    """Test text generation."""

    @pytest.mark.asyncio
    async def test_generate_success(self, provider, llm_request):
        """Test successful generation."""
        # Mock OpenAI response
        mock_choice = Mock()
        mock_choice.message.content = "Hello! How can I help you?"
        mock_choice.finish_reason = "stop"

        mock_usage = Mock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20
        mock_usage.total_tokens = 30

        mock_completion = Mock()
        mock_completion.choices = [mock_choice]
        mock_completion.usage = mock_usage

        # Mock the chat.completions.create method
        provider.client.chat = Mock()
        provider.client.chat.completions = Mock()
        provider.client.chat.completions.create = AsyncMock(return_value=mock_completion)

        # Generate
        response = await provider.generate(llm_request)

        # Verify
        assert isinstance(response, LLMResponse)  # nosec B101
        assert response.text == "Hello! How can I help you?"  # nosec B101
        assert response.provider == LLMProvider.OPENAI  # nosec B101
        assert response.latency_ms > 0  # nosec B101
        assert response.tokens_generated == 20  # nosec B101
        assert response.finish_reason == "stop"  # nosec B101
        assert response.metadata["model"] == "gpt-4-turbo-preview"  # nosec B101
        assert response.metadata["prompt_tokens"] == 10  # nosec B101
        assert response.metadata["total_tokens"] == 30  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_max_tokens(self, provider, llm_request):
        """Test generation with max tokens reached."""
        # Mock OpenAI response with length finish reason
        mock_choice = Mock()
        mock_choice.message.content = "This is a truncated response"
        mock_choice.finish_reason = "length"

        mock_usage = Mock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 512
        mock_usage.total_tokens = 522

        mock_completion = Mock()
        mock_completion.choices = [mock_choice]
        mock_completion.usage = mock_usage

        # Mock the chat.completions.create method
        provider.client.chat = Mock()
        provider.client.chat.completions = Mock()
        provider.client.chat.completions.create = AsyncMock(return_value=mock_completion)

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

        mock_choice = Mock()
        mock_choice.message.content = "1, 2, "
        mock_choice.finish_reason = "stop"

        mock_usage = Mock()
        mock_usage.prompt_tokens = 5
        mock_usage.completion_tokens = 5
        mock_usage.total_tokens = 10

        mock_completion = Mock()
        mock_completion.choices = [mock_choice]
        mock_completion.usage = mock_usage

        # Mock the chat.completions.create method
        provider.client.chat = Mock()
        provider.client.chat.completions = Mock()
        provider.client.chat.completions.create = AsyncMock(return_value=mock_completion)

        # Generate
        await provider.generate(llm_request)

        # Verify stop sequences were passed
        call_args = provider.client.chat.completions.create.call_args
        assert call_args.kwargs["stop"] == ["3", "4"]  # nosec B101


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


class TestErrorHandling:
    """Test error handling and retries."""

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, provider, llm_request):
        """Test rate limit error handling."""
        # Mock the chat.completions.create method
        provider.client.chat = Mock()
        provider.client.chat.completions = Mock()
        provider.client.chat.completions.create = AsyncMock(
            side_effect=RateLimitError("Rate limit exceeded", response=Mock(), body=None)
        )

        with pytest.raises(RuntimeError, match="OpenAI rate limit exceeded"):
            await provider.generate(llm_request)

        # Verify circuit breaker recorded failure
        assert provider.circuit_breaker.failure_count > 0  # nosec B101

    @pytest.mark.asyncio
    async def test_connection_error(self, provider, llm_request):
        """Test connection error handling."""
        # Mock the chat.completions.create method
        provider.client.chat = Mock()
        provider.client.chat.completions = Mock()
        provider.client.chat.completions.create = AsyncMock(
            side_effect=APIConnectionError(request=Mock())
        )

        with pytest.raises(RuntimeError, match="OpenAI connection error"):
            await provider.generate(llm_request)

    @pytest.mark.asyncio
    async def test_timeout_error(self, provider, llm_request):
        """Test timeout error handling."""
        # Mock the chat.completions.create method
        provider.client.chat = Mock()
        provider.client.chat.completions = Mock()
        provider.client.chat.completions.create = AsyncMock(
            side_effect=APITimeoutError(request=Mock())
        )

        with pytest.raises(TimeoutError, match="OpenAI request timeout"):
            await provider.generate(llm_request)

    @pytest.mark.asyncio
    async def test_api_error(self, provider, llm_request):
        """Test API error handling."""
        # Mock the chat.completions.create method
        provider.client.chat = Mock()
        provider.client.chat.completions = Mock()
        provider.client.chat.completions.create = AsyncMock(
            side_effect=APIError("API error", request=Mock(), body=None)
        )

        with pytest.raises(RuntimeError, match="OpenAI API error"):
            await provider.generate(llm_request)

    @pytest.mark.asyncio
    async def test_retry_logic(self, provider, llm_request):
        """Test retry logic with exponential backoff."""
        # Fail twice, then succeed
        mock_choice = Mock()
        mock_choice.message.content = "Success!"
        mock_choice.finish_reason = "stop"

        mock_usage = Mock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_usage.total_tokens = 15

        mock_completion = Mock()
        mock_completion.choices = [mock_choice]
        mock_completion.usage = mock_usage

        # Mock the chat.completions.create method
        provider.client.chat = Mock()
        provider.client.chat.completions = Mock()
        provider.client.chat.completions.create = AsyncMock(
            side_effect=[
                APIConnectionError(request=Mock()),
                APIConnectionError(request=Mock()),
                mock_completion,
            ]
        )

        # Should succeed after retries
        response = await provider.generate(llm_request)
        assert response.text == "Success!"  # nosec B101

        # Verify 3 attempts were made
        assert provider.client.chat.completions.create.call_count == 3  # nosec B101


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
        # Mock the chat.completions.create method
        provider.client.chat = Mock()
        provider.client.chat.completions = Mock()
        provider.client.chat.completions.create = AsyncMock(
            side_effect=APIConnectionError(request=Mock())
        )

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
        mock_choice = Mock()
        mock_choice.message.content = "Success!"
        mock_choice.finish_reason = "stop"

        mock_usage = Mock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_usage.total_tokens = 15

        mock_completion = Mock()
        mock_completion.choices = [mock_choice]
        mock_completion.usage = mock_usage

        # Mock the chat.completions.create method
        provider.client.chat = Mock()
        provider.client.chat.completions = Mock()
        provider.client.chat.completions.create = AsyncMock(return_value=mock_completion)

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
        mock_choice = Mock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"

        mock_usage = Mock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20
        mock_usage.total_tokens = 30

        mock_completion = Mock()
        mock_completion.choices = [mock_choice]
        mock_completion.usage = mock_usage

        # Mock the chat.completions.create method
        provider.client.chat = Mock()
        provider.client.chat.completions = Mock()
        provider.client.chat.completions.create = AsyncMock(return_value=mock_completion)

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

        assert health["provider"] == "openai"  # nosec B101
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
