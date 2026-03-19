"""
Error Handler with Circuit Breaker for the LLM Runtime.

Provides:
- Exponential backoff retry for transient errors
- Rate limit handling with configurable wait
- Circuit breaker pattern per provider
- Error classification (transient / rate_limit / permanent / timeout)

Performance:
    Time Complexity: O(1) per classification
    Space Complexity: O(p) where p = number of providers

Author: Agent Guru Team
Date: 2026-03-18
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, Optional, TypeVar

from Agent_Guru.llm.models import CircuitBreakerOpenError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorType(Enum):
    """Classification of LLM provider errors."""

    TRANSIENT = "transient"      # Retry with backoff
    RATE_LIMIT = "rate_limit"    # Wait then retry
    PERMANENT = "permanent"      # Do not retry
    TIMEOUT = "timeout"          # Retry with longer timeout


@dataclass
class CircuitBreakerState:
    """Per-provider circuit breaker state."""

    is_open: bool = False
    failure_count: int = 0
    last_failure: Optional[datetime] = None
    opened_at: Optional[datetime] = None


class ErrorHandler:
    """
    Handles LLM provider errors with retry logic and circuit breaker.

    Circuit Breaker States:
    - Closed: Normal operation
    - Open: After threshold failures, reject requests for timeout_s seconds
    - Half-Open: After timeout, allow one test request

    Example:
        >>> handler = ErrorHandler()
        >>> result = await handler.execute_with_retry(
        ...     lambda: adapter.complete(request),
        ...     provider="openai"
        ... )
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff_ms: float = 100.0,
        max_backoff_ms: float = 10_000.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout_s: float = 60.0,
    ) -> None:
        self.max_retries = max_retries
        self.initial_backoff_ms = initial_backoff_ms
        self.max_backoff_ms = max_backoff_ms
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout_s = circuit_breaker_timeout_s

        self._circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_with_retry(
        self,
        func: Callable[[], Coroutine[Any, Any, T]],
        provider: Optional[str] = None,
    ) -> T:
        """
        Execute an async callable with retry and circuit breaker logic.

        Args:
            func: Async callable (no arguments) to execute.
            provider: Provider name for circuit breaker tracking.

        Returns:
            Result of func().

        Raises:
            CircuitBreakerOpenError: If circuit is open for provider.
            Exception: If all retries are exhausted.
        """
        if provider and await self._is_circuit_open(provider):
            raise CircuitBreakerOpenError(
                f"Circuit breaker is open for provider '{provider}'. "
                f"Requests are blocked for {self.circuit_breaker_timeout_s}s."
            )

        last_error: Optional[Exception] = None
        backoff_ms = self.initial_backoff_ms

        for attempt in range(self.max_retries + 1):
            try:
                result = await func()

                if provider:
                    await self._record_success(provider)

                return result

            except Exception as exc:
                last_error = exc
                error_type = self._classify_error(exc)

                if provider:
                    # Only record failures for transient/timeout errors
                    # Permanent errors (4xx) should not trip the circuit breaker
                    if error_type != ErrorType.PERMANENT:
                        await self._record_failure(provider)

                logger.warning(
                    "LLM request failed (attempt %d/%d): %s — %s",
                    attempt + 1,
                    self.max_retries + 1,
                    error_type.value,
                    exc,
                )

                # Permanent errors: fail immediately
                if error_type == ErrorType.PERMANENT:
                    raise

                # Last attempt: raise
                if attempt >= self.max_retries:
                    raise

                # Rate limit: wait the specified duration
                if error_type == ErrorType.RATE_LIMIT:
                    wait_s = self._extract_rate_limit_wait(exc)
                    logger.info("Rate limited. Waiting %.1fs before retry.", wait_s)
                    await asyncio.sleep(wait_s)
                    continue

                # Transient / timeout: exponential backoff
                await asyncio.sleep(backoff_ms / 1000.0)
                backoff_ms = min(backoff_ms * 2, self.max_backoff_ms)

        # Should never reach here
        assert last_error is not None
        raise last_error

    # ------------------------------------------------------------------
    # Error classification
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_error(error: Exception) -> ErrorType:
        """Classify an exception into an ErrorType."""
        msg = str(error).lower()

        # Rate limit
        if "rate limit" in msg or "429" in msg or "too many requests" in msg:
            return ErrorType.RATE_LIMIT

        # Timeout
        if "timeout" in msg or "timed out" in msg or "deadline" in msg:
            return ErrorType.TIMEOUT

        # Permanent (4xx except 429)
        for code in ("400", "401", "403", "404", "422"):
            if code in msg:
                return ErrorType.PERMANENT

        # Default: transient (5xx, network errors, etc.)
        return ErrorType.TRANSIENT

    @staticmethod
    def _extract_rate_limit_wait(error: Exception) -> float:
        """
        Extract the wait duration from a rate limit error.

        Tries to parse a Retry-After value from the error message.
        Falls back to 1.0 second.
        """
        import re

        msg = str(error)
        match = re.search(r"retry.?after[:\s]+(\d+\.?\d*)", msg, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return 1.0

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------

    async def _is_circuit_open(self, provider: str) -> bool:
        """Return True if the circuit breaker is open for provider."""
        async with self._lock:
            if provider not in self._circuit_breakers:
                return False

            state = self._circuit_breakers[provider]

            if not state.is_open:
                return False

            # Check if the timeout has elapsed (half-open)
            if state.opened_at is not None:
                elapsed = (datetime.now() - state.opened_at).total_seconds()
                if elapsed >= self.circuit_breaker_timeout_s:
                    # Transition to half-open: allow one test request
                    state.is_open = False
                    state.failure_count = 0
                    logger.info(
                        "Circuit breaker for '%s' transitioning to half-open.", provider
                    )
                    return False

            return True

    async def _record_success(self, provider: str) -> None:
        """Reset circuit breaker on success."""
        async with self._lock:
            if provider in self._circuit_breakers:
                state = self._circuit_breakers[provider]
                state.failure_count = 0
                state.is_open = False

    async def _record_failure(self, provider: str) -> None:
        """Record a failure and open circuit if threshold exceeded."""
        async with self._lock:
            if provider not in self._circuit_breakers:
                self._circuit_breakers[provider] = CircuitBreakerState()

            state = self._circuit_breakers[provider]
            state.failure_count += 1
            state.last_failure = datetime.now()

            if state.failure_count >= self.circuit_breaker_threshold:
                if not state.is_open:
                    state.is_open = True
                    state.opened_at = datetime.now()
                    logger.warning(
                        "Circuit breaker OPENED for provider '%s' after %d failures.",
                        provider,
                        state.failure_count,
                    )

    def get_circuit_state(self, provider: str) -> Optional[CircuitBreakerState]:
        """Return the current circuit breaker state for a provider."""
        return self._circuit_breakers.get(provider)
