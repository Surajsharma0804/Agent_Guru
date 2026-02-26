"""
Module: agent_guru.platform.error_handling.circuit_breaker
Purpose: Circuit breaker pattern for fault tolerance and graceful degradation

This module implements the Circuit Breaker pattern to prevent cascading failures
when external services or operations fail repeatedly. The circuit breaker monitors
failures and automatically "opens" to prevent further attempts, allowing the system
to recover.

Performance Characteristics:
    - Time Complexity: O(1) for all operations
    - Space Complexity: O(1) (fixed state storage)
    - Overhead: <1ms per operation
    - Thread-safe: Yes (with threading.Lock)

States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests fail fast
    - HALF_OPEN: Testing if service recovered, limited requests allowed

Architecture:
    The circuit breaker tracks consecutive failures and successes. When failures
    exceed the threshold, it opens the circuit. After a cooldown period, it enters
    half-open state to test recovery. If successful, it closes; otherwise, reopens.

Usage Example:
    >>> from agent_guru.platform.error_handling.circuit_breaker import CircuitBreaker
    >>>
    >>> # Initialize circuit breaker
    >>> breaker = CircuitBreaker(
    ...     failure_threshold=5,
    ...     success_threshold=2,
    ...     timeout=60.0
    ... )
    >>>
    >>> # Execute operation with circuit breaker
    >>> try:
    ...     result = breaker.call(risky_operation, arg1, arg2)
    ...     print(f"Success: {result}")
    ... except CircuitBreakerOpenError:
    ...     print("Circuit breaker is open, using fallback")
    ...     result = fallback_operation()

Author: Agent Guru Team
Date: 2026-02-26
Version: 1.0.0
"""

import time
import threading
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, Generic
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states.
    
    Attributes:
        CLOSED: Normal operation, requests pass through
        OPEN: Circuit is open, requests fail fast
        HALF_OPEN: Testing recovery, limited requests allowed
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejects requests.
    
    This exception indicates that the circuit breaker has detected too many
    failures and is preventing further requests to allow the system to recover.
    """
    pass


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker.
    
    Attributes:
        failure_threshold: Number of consecutive failures before opening (default: 5)
        success_threshold: Number of successes needed to close from half-open (default: 2)
        timeout: Cooldown period in seconds before trying half-open (default: 60.0)
        expected_exception: Exception type to count as failure (default: Exception)
    """
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 60.0
    expected_exception: type = Exception
    
    def __post_init__(self):
        """Validate configuration parameters."""
        if self.failure_threshold <= 0:
            raise ValueError(f"failure_threshold must be positive, got {self.failure_threshold}")
        if self.success_threshold <= 0:
            raise ValueError(f"success_threshold must be positive, got {self.success_threshold}")
        if self.timeout <= 0:
            raise ValueError(f"timeout must be positive, got {self.timeout}")


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring.
    
    Attributes:
        state: Current circuit state
        failure_count: Current consecutive failure count
        success_count: Current consecutive success count (in half-open)
        last_failure_time: Timestamp of last failure (None if no failures)
        total_failures: Total number of failures
        total_successes: Total number of successes
        total_rejections: Total number of rejected requests (when open)
        state_changes: Number of state transitions
    """
    state: CircuitState
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    total_failures: int = 0
    total_successes: int = 0
    total_rejections: int = 0
    state_changes: int = 0


class CircuitBreaker(Generic[T]):
    """Circuit breaker for fault tolerance and graceful degradation.
    
    Time Complexity: O(1) for all operations
    Space Complexity: O(1) (fixed state storage)
    
    The circuit breaker monitors operation failures and automatically opens
    to prevent cascading failures. After a cooldown period, it tests recovery
    in half-open state before fully closing.
    
    Thread Safety: All operations are thread-safe using threading.Lock
    
    Example:
        >>> breaker = CircuitBreaker(
        ...     failure_threshold=5,
        ...     success_threshold=2,
        ...     timeout=60.0
        ... )
        >>>
        >>> # Use as context manager
        >>> with breaker:
        ...     result = risky_operation()
        >>>
        >>> # Or call directly
        >>> result = breaker.call(risky_operation, arg1, arg2)
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
        expected_exception: type = Exception,
        name: Optional[str] = None
    ):
        """Initialize circuit breaker.
        
        Args:
            failure_threshold: Consecutive failures before opening circuit
            success_threshold: Successes needed to close from half-open
            timeout: Cooldown period in seconds before half-open
            expected_exception: Exception type to count as failure
            name: Optional name for logging and monitoring
            
        Raises:
            ValueError: If any threshold or timeout is invalid
        """
        self.config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout=timeout,
            expected_exception=expected_exception
        )
        self.name = name or "CircuitBreaker"
        
        # State management
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        
        # Statistics
        self._total_failures = 0
        self._total_successes = 0
        self._total_rejections = 0
        self._state_changes = 0
        
        # Thread safety
        self._lock = threading.Lock()
        
        logger.info(
            f"{self.name} initialized: "
            f"failure_threshold={failure_threshold}, "
            f"success_threshold={success_threshold}, "
            f"timeout={timeout}s"
        )
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state.
        
        Returns:
            Current circuit state (CLOSED, OPEN, or HALF_OPEN)
        """
        with self._lock:
            return self._state
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation).
        
        Returns:
            True if circuit is closed
        """
        return self.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast).
        
        Returns:
            True if circuit is open
        """
        return self.state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery).
        
        Returns:
            True if circuit is half-open
        """
        return self.state == CircuitState.HALF_OPEN
    
    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function with circuit breaker protection.
        
        Time Complexity: O(1) + O(func)
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Result from function execution
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception from function execution
        """
        # Check if we can proceed
        if not self._allow_request():
            self._record_rejection()
            raise CircuitBreakerOpenError(
                f"{self.name} is open, rejecting request"
            )
        
        # Execute function
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except self.config.expected_exception as e:
            self._record_failure()
            raise
    
    def __enter__(self):
        """Context manager entry.
        
        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        if not self._allow_request():
            self._record_rejection()
            raise CircuitBreakerOpenError(
                f"{self.name} is open, rejecting request"
            )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit.
        
        Records success or failure based on exception.
        """
        if exc_type is None:
            self._record_success()
        elif issubclass(exc_type, self.config.expected_exception):
            self._record_failure()
        # Don't suppress exceptions
        return False
    
    def _allow_request(self) -> bool:
        """Check if request should be allowed.
        
        Time Complexity: O(1)
        
        Returns:
            True if request should proceed, False otherwise
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                # Check if cooldown period has elapsed
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                    return True
                return False
            
            # HALF_OPEN state - allow request to test recovery
            return True
    
    def _should_attempt_reset(self) -> bool:
        """Check if cooldown period has elapsed.
        
        Time Complexity: O(1)
        
        Returns:
            True if enough time has passed to attempt reset
        """
        if self._last_failure_time is None:
            return False
        
        elapsed = time.time() - self._last_failure_time
        return elapsed >= self.config.timeout
    
    def _record_success(self) -> None:
        """Record successful operation.
        
        Time Complexity: O(1)
        """
        with self._lock:
            self._total_successes += 1
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.debug(
                    f"{self.name} success in HALF_OPEN: "
                    f"{self._success_count}/{self.config.success_threshold}"
                )
                
                if self._success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0
    
    def _record_failure(self) -> None:
        """Record failed operation.
        
        Time Complexity: O(1)
        """
        with self._lock:
            self._total_failures += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open returns to open
                logger.warning(
                    f"{self.name} failure in HALF_OPEN, reopening circuit"
                )
                self._transition_to_open()
            
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                logger.debug(
                    f"{self.name} failure in CLOSED: "
                    f"{self._failure_count}/{self.config.failure_threshold}"
                )
                
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to_open()
    
    def _record_rejection(self) -> None:
        """Record rejected request (circuit open).
        
        Time Complexity: O(1)
        """
        with self._lock:
            self._total_rejections += 1
    
    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state.
        
        Time Complexity: O(1)
        """
        old_state = self._state
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._state_changes += 1
        
        logger.info(
            f"{self.name} transitioned: {old_state.value} -> CLOSED"
        )
    
    def _transition_to_open(self) -> None:
        """Transition to OPEN state.
        
        Time Complexity: O(1)
        """
        old_state = self._state
        self._state = CircuitState.OPEN
        self._failure_count = 0
        self._success_count = 0
        self._state_changes += 1
        
        logger.warning(
            f"{self.name} transitioned: {old_state.value} -> OPEN "
            f"(cooldown: {self.config.timeout}s)"
        )
    
    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state.
        
        Time Complexity: O(1)
        """
        old_state = self._state
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        self._state_changes += 1
        
        logger.info(
            f"{self.name} transitioned: {old_state.value} -> HALF_OPEN "
            f"(testing recovery)"
        )
    
    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state.
        
        Time Complexity: O(1)
        
        Use this for manual intervention or testing.
        """
        with self._lock:
            old_state = self._state
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._state_changes += 1
            
            logger.info(
                f"{self.name} manually reset: {old_state.value} -> CLOSED"
            )
    
    def get_stats(self) -> CircuitBreakerStats:
        """Get current statistics.
        
        Time Complexity: O(1)
        
        Returns:
            Current circuit breaker statistics
        """
        with self._lock:
            return CircuitBreakerStats(
                state=self._state,
                failure_count=self._failure_count,
                success_count=self._success_count,
                last_failure_time=self._last_failure_time,
                total_failures=self._total_failures,
                total_successes=self._total_successes,
                total_rejections=self._total_rejections,
                state_changes=self._state_changes
            )
