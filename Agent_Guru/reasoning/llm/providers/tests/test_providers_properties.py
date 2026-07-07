"""
Property-based tests for LLM providers.

Tests universal properties that should hold for all providers:
- Rate limiting behavior
- Circuit breaker state transitions
- Retry logic
- Configuration validation

Uses Hypothesis for property-based testing with 100 iterations.

Coverage Target: 80%+
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.providers.anthropic_provider import AnthropicProvider
from Agent_Guru.reasoning.llm.providers.base import (
    CircuitBreakerState,
    CircuitState,
    ProviderConfig,
    RateLimitState,
)
from Agent_Guru.reasoning.llm.providers.openai_provider import OpenAIProvider

# ============================================================================
# PROPERTY: Configuration Validation
# ============================================================================


class TestConfigurationProperties:
    """Property tests for configuration validation."""

    @given(
        api_key=st.text(min_size=1, max_size=100),
        max_retries=st.integers(min_value=0, max_value=10),
        timeout_seconds=st.floats(min_value=0.1, max_value=300.0),
        rate_limit_rpm=st.integers(min_value=1, max_value=1000),
        rate_limit_tpm=st.integers(min_value=1000, max_value=1000000),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_config_always_works(
        self,
        api_key: str,
        max_retries: int,
        timeout_seconds: float,
        rate_limit_rpm: int,
        rate_limit_tpm: int,
    ):
        """Property: Valid configuration always creates config object."""
        config = ProviderConfig(
            api_key=api_key,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            rate_limit_rpm=rate_limit_rpm,
            rate_limit_tpm=rate_limit_tpm,
        )

        assert config.api_key == api_key  # nosec B101
        assert config.max_retries == max_retries  # nosec B101
        assert config.timeout_seconds == timeout_seconds  # nosec B101
        assert config.rate_limit_rpm == rate_limit_rpm  # nosec B101
        assert config.rate_limit_tpm == rate_limit_tpm  # nosec B101

    @given(
        max_retries=st.integers(max_value=-1),
    )
    @settings(max_examples=100)
    def test_negative_max_retries_fails(self, max_retries: int):
        """Property: Negative max_retries always fails."""
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            ProviderConfig(
                api_key="test-key",
                max_retries=max_retries,
            )

    @given(
        timeout_seconds=st.floats(max_value=0.0),
    )
    @settings(max_examples=100)
    def test_non_positive_timeout_fails(self, timeout_seconds: float):
        """Property: Non-positive timeout always fails."""
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            ProviderConfig(
                api_key="test-key",
                timeout_seconds=timeout_seconds,
            )


# ============================================================================
# PROPERTY: Rate Limiting
# ============================================================================


class TestRateLimitingProperties:
    """Property tests for rate limiting."""

    @given(
        requests=st.integers(min_value=0, max_value=100),
        tokens=st.integers(min_value=0, max_value=100000),
    )
    @settings(max_examples=100)
    def test_rate_limit_state_tracks_usage(self, requests: int, tokens: int):
        """Property: Rate limit state accurately tracks usage."""
        state = RateLimitState()

        # Record usage
        for _ in range(requests):
            state.record_request(tokens)

        # Verify tracking
        assert state.requests_this_minute == requests  # nosec B101
        assert state.tokens_this_minute == requests * tokens  # nosec B101

    @given(
        rpm_limit=st.integers(min_value=1, max_value=100),
        tpm_limit=st.integers(min_value=1000, max_value=100000),
        requests=st.integers(min_value=0, max_value=150),
    )
    @settings(max_examples=100)
    def test_rate_limit_enforcement(self, rpm_limit: int, tpm_limit: int, requests: int):
        """Property: Rate limits are enforced correctly."""
        config = ProviderConfig(
            api_key="test-key",
            rate_limit_rpm=rpm_limit,
            rate_limit_tpm=tpm_limit,
        )
        state = RateLimitState()

        # Make requests
        allowed_requests = 0
        for _ in range(requests):
            if state.can_make_request(config, 100):
                state.record_request(100)
                allowed_requests += 1

        # Verify limits enforced
        assert allowed_requests <= rpm_limit  # nosec B101
        assert state.tokens_this_minute <= tpm_limit  # nosec B101

    def test_rate_limit_reset_after_minute(self):
        """Property: Rate limits reset after minute boundary."""
        state = RateLimitState()
        state.requests_this_minute = 50
        state.tokens_this_minute = 50000
        state.minute_start = datetime.now(tz=timezone.utc) - timedelta(minutes=2)

        # Reset should occur
        state.reset_if_needed()

        assert state.requests_this_minute == 0  # nosec B101
        assert state.tokens_this_minute == 0  # nosec B101


# ============================================================================
# PROPERTY: Circuit Breaker
# ============================================================================


class TestCircuitBreakerProperties:
    """Property tests for circuit breaker."""

    @given(
        threshold=st.integers(min_value=1, max_value=10),
        failures=st.integers(min_value=0, max_value=20),
    )
    @settings(max_examples=100)
    def test_circuit_opens_at_threshold(self, threshold: int, failures: int):
        """Property: Circuit opens when failures reach threshold."""
        config = ProviderConfig(
            api_key="test-key",
            circuit_breaker_threshold=threshold,
        )
        breaker = CircuitBreakerState()

        # Record failures
        for _ in range(failures):
            breaker.record_failure(config)

        # Verify state
        if failures >= threshold:
            assert breaker.state == CircuitState.OPEN  # nosec B101
        else:
            assert breaker.state == CircuitState.CLOSED  # nosec B101

    def test_circuit_closes_on_success(self):
        """Property: Circuit closes on successful request."""
        breaker = CircuitBreakerState()
        breaker.state = CircuitState.HALF_OPEN
        breaker.failure_count = 5

        # Record success
        breaker.record_success()

        assert breaker.state == CircuitState.CLOSED  # nosec B101
        assert breaker.failure_count == 0  # nosec B101

    @given(
        timeout=st.floats(min_value=1.0, max_value=300.0),
        elapsed=st.floats(min_value=0.0, max_value=400.0),
    )
    @settings(max_examples=100)
    def test_circuit_half_open_after_timeout(self, timeout: float, elapsed: float):
        """Property: Circuit transitions to half-open after timeout."""
        config = ProviderConfig(
            api_key="test-key",
            circuit_breaker_timeout=timeout,
        )
        breaker = CircuitBreakerState()
        breaker.state = CircuitState.OPEN
        # Add a small buffer to account for test execution time
        breaker.last_failure_time = datetime.now(tz=timezone.utc) - timedelta(seconds=elapsed + 0.001)

        # Check if can attempt
        can_attempt = breaker.can_attempt(config)

        if elapsed >= timeout:
            assert can_attempt  # nosec B101
            assert breaker.state == CircuitState.HALF_OPEN  # nosec B101
        else:
            assert not can_attempt  # nosec B101
            assert breaker.state == CircuitState.OPEN  # nosec B101


# ============================================================================
# PROPERTY: Request/Response Validation
# ============================================================================


class TestRequestResponseProperties:
    """Property tests for request/response validation."""

    @given(
        prompt=st.text(min_size=1, max_size=1000),
        temperature=st.floats(min_value=0.0, max_value=2.0),
        top_p=st.floats(min_value=0.0, max_value=1.0),
        max_tokens=st.integers(min_value=1, max_value=4096),
    )
    @settings(max_examples=100)
    def test_valid_request_always_works(
        self,
        prompt: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
    ):
        """Property: Valid request parameters always create request."""
        request = LLMRequest(
            prompt=prompt,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

        assert request.prompt == prompt  # nosec B101
        assert request.temperature == temperature  # nosec B101
        assert request.top_p == top_p  # nosec B101
        assert request.max_tokens == max_tokens  # nosec B101

    @given(
        temperature=st.floats(min_value=2.1, max_value=10.0)
        | st.floats(min_value=-10.0, max_value=-0.1),
    )
    @settings(max_examples=100)
    def test_invalid_temperature_fails(self, temperature: float):
        """Property: Invalid temperature always fails."""
        with pytest.raises(ValueError, match="temperature must be 0.0-2.0"):
            LLMRequest(
                prompt="test",
                temperature=temperature,
            )

    @given(
        top_p=st.floats(min_value=1.1, max_value=10.0) | st.floats(min_value=-10.0, max_value=-0.1),
    )
    @settings(max_examples=100)
    def test_invalid_top_p_fails(self, top_p: float):
        """Property: Invalid top_p always fails."""
        with pytest.raises(ValueError, match="top_p must be 0.0-1.0"):
            LLMRequest(
                prompt="test",
                top_p=top_p,
            )

    @given(
        text=st.text(min_size=0, max_size=10000),
        latency_ms=st.floats(min_value=0.0, max_value=10000.0),
        tokens_generated=st.integers(min_value=0, max_value=4096),
        finish_reason=st.sampled_from(["stop", "length", "error"]),
    )
    @settings(max_examples=100)
    def test_valid_response_always_works(
        self,
        text: str,
        latency_ms: float,
        tokens_generated: int,
        finish_reason: str,
    ):
        """Property: Valid response parameters always create response."""
        response = LLMResponse(
            text=text,
            provider=LLMProvider.OPENAI,
            latency_ms=latency_ms,
            tokens_generated=tokens_generated,
            finish_reason=finish_reason,
        )

        assert response.text == text  # nosec B101
        assert response.latency_ms == latency_ms  # nosec B101
        assert response.tokens_generated == tokens_generated  # nosec B101
        assert response.finish_reason == finish_reason  # nosec B101


# ============================================================================
# PROPERTY: Provider Behavior
# ============================================================================


class TestProviderBehaviorProperties:
    """Property tests for provider behavior."""

    @pytest.mark.asyncio
    @given(
        provider_type=st.sampled_from([OpenAIProvider, AnthropicProvider]),
    )
    @settings(max_examples=10, deadline=500)  # Reduced for async tests, 500ms deadline
    async def test_provider_returns_response_on_success(self, provider_type):
        """Property: Provider always returns LLMResponse on success."""
        config = ProviderConfig(api_key="test-key")
        provider = provider_type(config)

        # Mock successful response
        if provider_type == OpenAIProvider:
            mock_choice = Mock()
            mock_choice.message.content = "Test response"
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
        else:  # AnthropicProvider
            mock_content = Mock()
            mock_content.type = "text"
            mock_content.text = "Test response"

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
        request = LLMRequest(prompt="Test")
        response = await provider.generate(request)

        # Verify
        assert isinstance(response, LLMResponse)  # nosec B101
        assert response.text == "Test response"  # nosec B101
        assert response.latency_ms > 0  # nosec B101
        assert response.tokens_generated > 0  # nosec B101

    @pytest.mark.asyncio
    @given(
        provider_type=st.sampled_from([OpenAIProvider, AnthropicProvider]),
    )
    @settings(max_examples=10, deadline=500)  # Reduced for async tests, 500ms deadline
    async def test_provider_health_always_returns_dict(self, provider_type):
        """Property: get_health always returns valid dictionary."""
        config = ProviderConfig(api_key="test-key")
        provider = provider_type(config)

        health = provider.get_health()

        # Verify required fields
        assert isinstance(health, dict)  # nosec B101
        assert "provider" in health  # nosec B101
        assert "circuit_state" in health  # nosec B101
        assert "failure_count" in health  # nosec B101
        assert "requests_this_minute" in health  # nosec B101
        assert "tokens_this_minute" in health  # nosec B101
