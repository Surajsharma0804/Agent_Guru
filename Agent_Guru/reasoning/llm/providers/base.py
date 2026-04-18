"""
Base LLM Provider Interface

Defines the common interface and utilities for all LLM providers.
Includes circuit breaker, rate limiting, and retry logic.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMRequest, LLMResponse


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class ProviderConfig:
    """Configuration for LLM provider."""

    api_key: str
    max_retries: int = 3
    timeout_seconds: float = 30.0
    rate_limit_rpm: int = 60  # Requests per minute
    rate_limit_tpm: int = 90000  # Tokens per minute
    circuit_breaker_threshold: int = 5  # Failures before opening
    circuit_breaker_timeout: float = 60.0  # Seconds before half-open
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration."""
        if not self.api_key:
            raise ValueError("api_key is required")
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be non-negative, got {self.max_retries}")
        if self.timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be positive, got {self.timeout_seconds}")
        if self.rate_limit_rpm <= 0:
            raise ValueError(f"rate_limit_rpm must be positive, got {self.rate_limit_rpm}")
        if self.rate_limit_tpm <= 0:
            raise ValueError(f"rate_limit_tpm must be positive, got {self.rate_limit_tpm}")
        if self.circuit_breaker_threshold <= 0:
            raise ValueError(
                f"circuit_breaker_threshold must be positive, got {self.circuit_breaker_threshold}"
            )
        if self.circuit_breaker_timeout <= 0:
            raise ValueError(
                f"circuit_breaker_timeout must be positive, got {self.circuit_breaker_timeout}"
            )


@dataclass
class RateLimitState:
    """State for rate limiting."""

    requests_this_minute: int = 0
    tokens_this_minute: int = 0
    minute_start: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def reset_if_needed(self) -> None:
        """Reset counters if minute has passed."""
        now = datetime.now(tz=timezone.utc)
        if now - self.minute_start >= timedelta(minutes=1):
            self.requests_this_minute = 0
            self.tokens_this_minute = 0
            self.minute_start = now

    def can_make_request(self, config: ProviderConfig, estimated_tokens: int) -> bool:
        """Check if request is within rate limits."""
        self.reset_if_needed()
        return (
            self.requests_this_minute < config.rate_limit_rpm
            and self.tokens_this_minute + estimated_tokens < config.rate_limit_tpm
        )

    def record_request(self, tokens_used: int) -> None:
        """Record a request for rate limiting."""
        self.reset_if_needed()
        self.requests_this_minute += 1
        self.tokens_this_minute += tokens_used


@dataclass
class CircuitBreakerState:
    """State for circuit breaker."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None

    def record_success(self) -> None:
        """Record successful request."""
        self.failure_count = 0
        self.last_success_time = datetime.now(tz=timezone.utc)
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED

    def record_failure(self, config: ProviderConfig) -> None:
        """Record failed request."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(tz=timezone.utc)

        if self.failure_count >= config.circuit_breaker_threshold:
            self.state = CircuitState.OPEN

    def can_attempt(self, config: ProviderConfig) -> bool:
        """Check if request can be attempted."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if self.last_failure_time:
                elapsed = (datetime.now(tz=timezone.utc) - self.last_failure_time).total_seconds()
                if elapsed >= config.circuit_breaker_timeout:
                    self.state = CircuitState.HALF_OPEN
                    return True
            return False

        # HALF_OPEN: allow one test request
        return True


class BaseLLMProvider(ABC):
    """
    Base class for LLM providers.

    Provides common functionality:
    - Rate limiting
    - Circuit breaker
    - Retry logic with exponential backoff
    - Error handling

    Subclasses must implement:
    - _generate_impl: Actual API call to provider
    """

    def __init__(self, config: ProviderConfig):
        """Initialize provider.

        Args:
            config: Provider configuration
        """
        self.config = config
        self.rate_limit_state = RateLimitState()
        self.circuit_breaker = CircuitBreakerState()

    @abstractmethod
    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """
        Implement actual API call to provider.

        Args:
            request: LLM request

        Returns:
            LLM response

        Raises:
            Exception: On API errors
        """

    @abstractmethod
    def get_provider_type(self) -> LLMProvider:
        """Get provider type enum value."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text with rate limiting, circuit breaker, and retries.

        Args:
            request: LLM request

        Returns:
            LLM response

        Raises:
            RuntimeError: If circuit breaker is open
            TimeoutError: If request times out
            Exception: On API errors after retries
        """
        # Check circuit breaker
        if not self.circuit_breaker.can_attempt(self.config):
            raise RuntimeError(
                f"Circuit breaker is OPEN for {self.get_provider_type()}. "
                f"Last failure: {self.circuit_breaker.last_failure_time}"
            )

        # Estimate tokens for rate limiting
        estimated_tokens = len(request.prompt.split()) + request.max_tokens

        # Check rate limits
        if not self.rate_limit_state.can_make_request(self.config, estimated_tokens):
            # Wait until next minute
            wait_time = 60 - (datetime.now(tz=timezone.utc) - self.rate_limit_state.minute_start).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.rate_limit_state.reset_if_needed()

        # Retry logic with exponential backoff
        last_exception: Optional[Exception] = None
        for attempt in range(self.config.max_retries):
            try:
                # Make request — do NOT wrap in asyncio.wait_for here.
                # The aiohttp ClientTimeout inside _generate_impl already
                # enforces the per-request deadline.  Adding a second
                # wait_for causes CancelledError to propagate incorrectly
                # when an outer timeout (e.g. ReasoningPlanGenerator) fires,
                # because the inner wait_for catches the cancellation and
                # converts it to TimeoutError before the outer one can see it.
                response = await self._generate_impl(request)

                # Record success
                self.circuit_breaker.record_success()
                self.rate_limit_state.record_request(response.tokens_generated)

                return response

            except asyncio.TimeoutError as e:
                last_exception = e
                self.circuit_breaker.record_failure(self.config)
                if attempt < self.config.max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    await asyncio.sleep(2**attempt)
                continue

            except asyncio.CancelledError:
                # Propagate cancellation immediately — do not retry.
                # This happens when an outer asyncio.wait_for fires.
                raise

            except Exception as e:
                last_exception = e
                self.circuit_breaker.record_failure(self.config)
                if attempt < self.config.max_retries - 1:
                    # Exponential backoff
                    await asyncio.sleep(2**attempt)
                continue

        # All retries failed
        raise last_exception or RuntimeError("All retries failed")

    def get_health(self) -> dict[str, Any]:
        """Get provider health status.

        Returns:
            Health status dictionary
        """
        return {
            "provider": self.get_provider_type().value,
            "circuit_state": self.circuit_breaker.state.value,
            "failure_count": self.circuit_breaker.failure_count,
            "last_failure": self.circuit_breaker.last_failure_time.isoformat()
            if self.circuit_breaker.last_failure_time
            else None,
            "last_success": self.circuit_breaker.last_success_time.isoformat()
            if self.circuit_breaker.last_success_time
            else None,
            "requests_this_minute": self.rate_limit_state.requests_this_minute,
            "tokens_this_minute": self.rate_limit_state.tokens_this_minute,
        }
