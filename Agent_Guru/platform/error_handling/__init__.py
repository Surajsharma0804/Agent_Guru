"""Error handling module for platform integration."""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    CircuitBreakerConfig,
    CircuitBreakerStats
)
from .retry_strategy import (
    RetryStrategy,
    RetryConfig,
    RetryResult,
    RetryDecision
)
from .error_response import (
    ErrorResponse,
    ErrorCategory,
    ErrorCode,
    create_error_response,
    generate_remediation_steps,
    categorize_exception
)

__all__ = [
    # Circuit Breaker
    'CircuitBreaker',
    'CircuitState',
    'CircuitBreakerOpenError',
    'CircuitBreakerConfig',
    'CircuitBreakerStats',
    # Retry Strategy
    'RetryStrategy',
    'RetryConfig',
    'RetryResult',
    'RetryDecision',
    # Error Response
    'ErrorResponse',
    'ErrorCategory',
    'ErrorCode',
    'create_error_response',
    'generate_remediation_steps',
    'categorize_exception'
]

