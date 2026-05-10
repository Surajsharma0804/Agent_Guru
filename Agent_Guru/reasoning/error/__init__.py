"""Error handling and recovery module.

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
    "CircuitBreaker",
    "CircuitBreakerConfig",
    # Recovery mechanisms
    "CircuitState",
    "DegradationConfig",
    # Graceful degradation
    "DegradationLevel",
    "DegradationManager",
    "ErrorClassifier",
    "ErrorContext",
    "ErrorManager",
    "ErrorSeverity",
    # Error management
    "ErrorType",
    "FailoverManager",
    "FallbackHandler",
    "FallbackRegistry",
    "FallbackResult",
    # Fallback strategies
    "FallbackStrategy",
    "FeatureCategory",
    "LLMFallbackHandler",
    "RetryConfig",
    "RetryHandler",
    "StructuredError",
    "TimeoutFallbackHandler",
    "ToolFallbackHandler",
    "get_circuit_breaker",
    "get_degradation_manager",
    "get_error_manager",
    "get_failover_manager",
    "get_fallback_registry",
    "get_retry_handler",
]
