"""Error handling module for platform integration."""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    CircuitBreakerConfig,
    CircuitBreakerStats
)

__all__ = [
    'CircuitBreaker',
    'CircuitState',
    'CircuitBreakerOpenError',
    'CircuitBreakerConfig',
    'CircuitBreakerStats'
]
