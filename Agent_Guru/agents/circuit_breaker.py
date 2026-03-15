"""
Circuit Breaker - Prevents cascading failures from external system outages.

Validates: Requirements 26.1, 26.2, 26.3, 26.4, 26.5
"""

from typing import Callable, Awaitable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing — reject calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""

    failure_threshold: int = 5       # Failures before opening
    recovery_timeout_seconds: float = 30.0  # Time before trying half-open
    success_threshold: int = 2       # Successes in half-open before closing


class CircuitBreaker:
    """
    Circuit breaker pattern for external system calls.

    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Too many failures, calls rejected immediately
    - HALF_OPEN: Testing recovery, limited calls allowed

    Time Complexity: O(1) per call
    Space Complexity: O(1)

    Example:
        >>> cb = CircuitBreaker("model_router", CircuitBreakerConfig())
        >>> result = await cb.call(my_async_func, arg1, arg2)

    Validates: Requirements 26.1, 26.2, 26.3, 26.4, 26.5
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> None:
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None

    @property
    def state(self) -> CircuitState:
        return self._state

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open."""
        if self._last_failure_time is None:
            return False
        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self.config.recovery_timeout_seconds

    async def call(self, func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        """
        Execute func through the circuit breaker.

        Raises:
            CircuitOpenError: If circuit is OPEN and recovery timeout not elapsed
        """
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info("Circuit %s transitioning to HALF_OPEN", self.name)
            else:
                raise CircuitOpenError(f"Circuit '{self.name}' is OPEN")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info("Circuit %s CLOSED (recovered)", self.name)
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning("Circuit %s re-OPENED (half-open failure)", self.name)
        elif self._failure_count >= self.config.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit %s OPENED after %d failures", self.name, self._failure_count
            )

    def reset(self) -> None:
        """Manually reset circuit to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open."""
    pass
