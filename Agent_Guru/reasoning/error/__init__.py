"""
Error handling and recovery module.

Provides comprehensive error management:
- Error classification and structured errors
- Fallback strategies for different error types
- Automatic recovery with retry and circuit breakers
- Graceful degradation under failure
"""

from Agent_Guru.reasoning.error.degradation import (
    DegradationConfig,
    DegradationLevel,
    DegradationManager,
    FeatureCategory,
    get_degradation_manager,
)
from Agent_Guru.reasoning.error.error_manager import (
    ErrorClassifier,
    ErrorContext,
    ErrorManager,
    ErrorSeverity,
    ErrorType,
    StructuredError,
    get_error_manager,
)
from Agent_Guru.reasoning.error.fallback import (
    FallbackHandler,
    FallbackRegistry,
    FallbackResult,
    FallbackStrategy,
    LLMFallbackHandler,
    TimeoutFallbackHandler,
    ToolFallbackHandler,
    get_fallback_registry,
)
from Agent_Guru.reasoning.error.recovery import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    FailoverManager,
    RetryConfig,
    RetryHandler,
    get_circuit_breaker,
    get_failover_manager,
    get_retry_handler,
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
