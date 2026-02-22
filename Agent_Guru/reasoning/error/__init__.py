"""
Error handling and recovery module.

Provides comprehensive error management:
- Error classification and structured errors
- Fallback strategies for different error types
- Automatic recovery with retry and circuit breakers
- Graceful degradation under failure
"""

from Agent_Guru.reasoning.error.error_manager import (
    ErrorType,
    ErrorSeverity,
    ErrorContext,
    StructuredError,
    ErrorClassifier,
    ErrorManager,
    get_error_manager,
)

from Agent_Guru.reasoning.error.fallback import (
    FallbackStrategy,
    FallbackResult,
    FallbackHandler,
    LLMFallbackHandler,
    ToolFallbackHandler,
    TimeoutFallbackHandler,
    FallbackRegistry,
    get_fallback_registry,
)

from Agent_Guru.reasoning.error.recovery import (
    CircuitState,
    RetryConfig,
    CircuitBreakerConfig,
    RetryHandler,
    CircuitBreaker,
    FailoverManager,
    get_retry_handler,
    get_circuit_breaker,
    get_failover_manager,
)

from Agent_Guru.reasoning.error.degradation import (
    DegradationLevel,
    FeatureCategory,
    DegradationConfig,
    DegradationManager,
    get_degradation_manager,
)

__all__ = [
    # Error management
    "ErrorType",
    "ErrorSeverity",
    "ErrorContext",
    "StructuredError",
    "ErrorClassifier",
    "ErrorManager",
    "get_error_manager",
    # Fallback strategies
    "FallbackStrategy",
    "FallbackResult",
    "FallbackHandler",
    "LLMFallbackHandler",
    "ToolFallbackHandler",
    "TimeoutFallbackHandler",
    "FallbackRegistry",
    "get_fallback_registry",
    # Recovery mechanisms
    "CircuitState",
    "RetryConfig",
    "CircuitBreakerConfig",
    "RetryHandler",
    "CircuitBreaker",
    "FailoverManager",
    "get_retry_handler",
    "get_circuit_breaker",
    "get_failover_manager",
    # Graceful degradation
    "DegradationLevel",
    "FeatureCategory",
    "DegradationConfig",
    "DegradationManager",
    "get_degradation_manager",
]
