"""
Automatic recovery mechanisms for error handling.

Provides intelligent recovery strategies:
- Retry logic with exponential backoff
- Circuit breaker pattern for failing services
- Automatic failover between backends
- Recovery success tracking
"""

import asyncio
import structlog
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional


logger = structlog.get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class RetryConfig:
    """Configuration for retry logic."""

    max_retries: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes before closing
    timeout: float = 60.0  # Seconds before trying half-open
    window_size: int = 100  # Rolling window size


class RetryHandler:
    """Handler for retry logic with exponential backoff."""

    def __init__(self, config: Optional[RetryConfig] = None):
        """Initialize retry handler.

        Args:
            config: Retry configuration
        """
        self.config = config or RetryConfig()
        self._retry_counts: Dict[str, int] = {}
        self._success_counts: Dict[str, int] = {}

    async def execute_with_retry(
        self,
        func: Callable,
        *args: Any,
        operation_id: str = "default",
        **kwargs: Any,
    ) -> Any:
        """Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Function arguments
            operation_id: Unique identifier for operation
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retries exhausted
        """
        last_exception = None
        retry_count = 0

        while retry_count <= self.config.max_retries:
            try:
                # Execute function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Success - reset retry count
                self._retry_counts[operation_id] = 0
                self._success_counts[operation_id] = (
                    self._success_counts.get(operation_id, 0) + 1
                )

                logger.info(
                    "retry_success",
                    operation_id=operation_id,
                    retry_count=retry_count,
                    success_count=self._success_counts[operation_id],
                )

                return result

            except Exception as e:
                last_exception = e
                retry_count += 1
                self._retry_counts[operation_id] = retry_count

                # Check if should retry
                if not self._should_retry(e, retry_count):
                    logger.error(
                        "retry_exhausted",
                        operation_id=operation_id,
                        retry_count=retry_count,
                        error=str(e),
                    )
                    raise

                # Calculate delay with exponential backoff
                delay = self._calculate_delay(retry_count)

                logger.warning(
                    "retry_attempt",
                    operation_id=operation_id,
                    retry_count=retry_count,
                    delay_seconds=delay,
                    error=str(e),
                )

                # Wait before retry
                await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(
            "all_retries_failed",
            operation_id=operation_id,
            max_retries=self.config.max_retries,
            error=str(last_exception) if last_exception else "Unknown error",
        )
        if last_exception:
            raise last_exception
        raise RuntimeError("All retries failed with unknown error")

    def _should_retry(self, exception: Exception, retry_count: int) -> bool:
        """Check if should retry after exception.

        Args:
            exception: Exception that occurred
            retry_count: Current retry count

        Returns:
            True if should retry
        """
        # Don't retry if max retries reached
        if retry_count > self.config.max_retries:
            return False

        # Retry on transient errors
        transient_errors = (
            TimeoutError,
            ConnectionError,
            asyncio.TimeoutError,
        )

        if isinstance(exception, transient_errors):
            return True

        # Check error message for transient indicators
        error_msg = str(exception).lower()
        transient_keywords = [
            "timeout",
            "connection",
            "temporary",
            "unavailable",
            "rate limit",
            "too many requests",
        ]

        return any(keyword in error_msg for keyword in transient_keywords)

    def _calculate_delay(self, retry_count: int) -> float:
        """Calculate delay for retry with exponential backoff.

        Args:
            retry_count: Current retry count

        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = min(
            self.config.initial_delay
            * (self.config.exponential_base ** (retry_count - 1)),
            self.config.max_delay,
        )

        # Add jitter to prevent thundering herd
        if self.config.jitter:
            import random

            delay = delay * (0.5 + random.random() * 0.5)

        return delay

    def get_retry_stats(self, operation_id: str) -> Dict[str, int]:
        """Get retry statistics for an operation.

        Args:
            operation_id: Operation identifier

        Returns:
            Statistics dictionary
        """
        return {
            "retry_count": self._retry_counts.get(operation_id, 0),
            "success_count": self._success_counts.get(operation_id, 0),
        }


class CircuitBreaker:
    """Circuit breaker for failing services."""

    def __init__(
        self,
        service_name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        """Initialize circuit breaker.

        Args:
            service_name: Name of service
            config: Circuit breaker configuration
        """
        self.service_name = service_name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_state_change: datetime = datetime.now()

    async def execute(
        self,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If circuit is open or function fails
        """
        # Check circuit state
        if self._state == CircuitState.OPEN:
            # Check if should try half-open
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                self._last_state_change = datetime.now()
                logger.info(
                    "circuit_half_open",
                    service=self.service_name,
                )
            else:
                # Circuit still open, reject request
                logger.warning(
                    "circuit_open_rejected",
                    service=self.service_name,
                )
                raise Exception(f"Circuit breaker open for {self.service_name}")

        try:
            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Success
            self._on_success()
            return result

        except Exception:
            # Failure
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful execution."""
        self._failure_count = 0
        self._success_count += 1

        # Check if should close circuit
        if self._state == CircuitState.HALF_OPEN:
            if self._success_count >= self.config.success_threshold:
                self._state = CircuitState.CLOSED
                self._success_count = 0
                self._last_state_change = datetime.now()
                logger.info(
                    "circuit_closed",
                    service=self.service_name,
                )

    def _on_failure(self) -> None:
        """Handle failed execution."""
        self._failure_count += 1
        self._success_count = 0
        self._last_failure_time = datetime.now()

        # Check if should open circuit
        if self._state == CircuitState.CLOSED:
            if self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                self._last_state_change = datetime.now()
                logger.warning(
                    "circuit_opened",
                    service=self.service_name,
                    failure_count=self._failure_count,
                )

        elif self._state == CircuitState.HALF_OPEN:
            # Failed during half-open, reopen circuit
            self._state = CircuitState.OPEN
            self._last_state_change = datetime.now()
            logger.warning(
                "circuit_reopened",
                service=self.service_name,
            )

    def _should_attempt_reset(self) -> bool:
        """Check if should attempt to reset circuit.

        Returns:
            True if should attempt reset
        """
        if self._last_failure_time is None:
            return True

        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self.config.timeout

    def get_state(self) -> CircuitState:
        """Get current circuit state.

        Returns:
            Circuit state
        """
        return self._state

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "service": self.service_name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": (
                self._last_failure_time.isoformat()
                if self._last_failure_time
                else None
            ),
            "last_state_change": self._last_state_change.isoformat(),
        }


class FailoverManager:
    """Manager for automatic failover between backends."""

    def __init__(self):
        """Initialize failover manager."""
        self._backends: Dict[str, list[str]] = {}
        self._current_backend: Dict[str, int] = {}
        self._backend_health: Dict[str, Dict[str, bool]] = {}

    def register_backends(
        self, service_type: str, backends: list[str]
    ) -> None:
        """Register backends for a service type.

        Args:
            service_type: Type of service (e.g., "llm", "database")
            backends: List of backend identifiers
        """
        self._backends[service_type] = backends
        self._current_backend[service_type] = 0
        self._backend_health[service_type] = {
            backend: True for backend in backends
        }

    async def execute_with_failover(
        self,
        service_type: str,
        func: Callable[[str], Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function with automatic failover.

        Args:
            service_type: Type of service
            func: Function that takes backend identifier as first argument
            *args: Additional function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all backends fail
        """
        backends = self._backends.get(service_type, [])
        if not backends:
            raise ValueError(f"No backends registered for {service_type}")

        last_exception = None
        attempts = 0

        # Try each backend
        for backend in backends:
            # Skip unhealthy backends
            if not self._backend_health[service_type].get(backend, True):
                continue

            try:
                attempts += 1
                logger.info(
                    "failover_attempt",
                    service_type=service_type,
                    backend=backend,
                    attempt=attempts,
                )

                # Execute with this backend
                if asyncio.iscoroutinefunction(func):
                    result = await func(backend, *args, **kwargs)
                else:
                    result = func(backend, *args, **kwargs)

                # Success - mark backend as healthy
                self._backend_health[service_type][backend] = True
                self._current_backend[service_type] = backends.index(backend)

                logger.info(
                    "failover_success",
                    service_type=service_type,
                    backend=backend,
                )

                return result

            except Exception as e:
                last_exception = e

                # Mark backend as unhealthy
                self._backend_health[service_type][backend] = False

                logger.warning(
                    "failover_backend_failed",
                    service_type=service_type,
                    backend=backend,
                    error=str(e),
                )

        # All backends failed
        logger.error(
            "failover_all_failed",
            service_type=service_type,
            attempts=attempts,
            error=str(last_exception) if last_exception else "Unknown error",
        )
        if last_exception:
            raise last_exception
        raise RuntimeError(f"All backends failed for {service_type}")

    def get_current_backend(self, service_type: str) -> Optional[str]:
        """Get current backend for a service type.

        Args:
            service_type: Type of service

        Returns:
            Current backend identifier or None
        """
        backends = self._backends.get(service_type, [])
        if not backends:
            return None

        index = self._current_backend.get(service_type, 0)
        return backends[index] if index < len(backends) else None

    def get_health_status(self) -> Dict[str, Dict[str, bool]]:
        """Get health status of all backends.

        Returns:
            Health status dictionary
        """
        return dict(self._backend_health)


# Global instances
_global_retry_handler: Optional[RetryHandler] = None
_global_circuit_breakers: Dict[str, CircuitBreaker] = {}
_global_failover_manager: Optional[FailoverManager] = None


def get_retry_handler() -> RetryHandler:
    """Get the global retry handler instance.

    Returns:
        Global RetryHandler instance
    """
    global _global_retry_handler
    if _global_retry_handler is None:
        _global_retry_handler = RetryHandler()
    return _global_retry_handler


def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """Get circuit breaker for a service.

    Args:
        service_name: Name of service

    Returns:
        CircuitBreaker instance
    """
    global _global_circuit_breakers
    if service_name not in _global_circuit_breakers:
        _global_circuit_breakers[service_name] = CircuitBreaker(service_name)
    return _global_circuit_breakers[service_name]


def get_failover_manager() -> FailoverManager:
    """Get the global failover manager instance.

    Returns:
        Global FailoverManager instance
    """
    global _global_failover_manager
    if _global_failover_manager is None:
        _global_failover_manager = FailoverManager()
    return _global_failover_manager
