"""Error handling module for Agent Guru platform integration.

This module provides robust error handling capabilities including:
- Exponential backoff with jitter for retries
- Circuit breaker pattern for external services
- Structured error responses with remediation steps
- Graceful degradation for resource-constrained environments
- Health check endpoints for monitoring

Modules:
    - retry_strategy: Exponential backoff retry logic
    - circuit_breaker: Circuit breaker pattern implementation
    - graceful_degradation: Resource-aware feature degradation
    - health_check: System health monitoring
    - health_endpoint: HTTP health check endpoints

Example:
    >>> from Agent_Guru.platform.error_handling import (
    ...     DegradationManager,
    ...     DegradationConfig,
    ...     FeaturePriority,
    ...     HealthCheckManager,
    ...     get_health_manager
    ... )
    >>>
    >>> # Initialize degradation manager
    >>> config = DegradationConfig(cpu_threshold=80.0)
    >>> manager = DegradationManager(config)
    >>>
    >>> # Register features
    >>> manager.register_feature(
    ...     "gpu_acceleration",
    ...     FeaturePriority.MEDIUM
    ... )
    >>>
    >>> # Check if feature is enabled
    >>> if manager.is_feature_enabled("gpu_acceleration"):
    ...     use_gpu()
    ... else:
    ...     use_cpu()
    >>>
    >>> # Health check example
    >>> health_manager = get_health_manager()
    >>> status = await health_manager.check_health()
    >>> print(f"System healthy: {status.is_healthy}")

"""

from Agent_Guru.platform.error_handling.graceful_degradation import (
    DegradationConfig,
    DegradationEvent,
    DegradationManager,
    FeatureConfig,
    FeaturePriority,
    OperationMode,
)
from Agent_Guru.platform.error_handling.health_check import (
    ComponentHealth,
    HealthCheckManager,
    HealthStatus,
    SystemHealth,
    check_platform_integration,
    check_system_resources,
    get_health_manager,
)
from Agent_Guru.platform.error_handling.health_endpoint import (
    create_health_app,
    create_simple_health_handler,
)

__all__ = [
    "ComponentHealth",
    "DegradationConfig",
    "DegradationEvent",
    # Graceful degradation
    "DegradationManager",
    "FeatureConfig",
    "FeaturePriority",
    # Health checks
    "HealthCheckManager",
    "HealthStatus",
    "OperationMode",
    "SystemHealth",
    "check_platform_integration",
    "check_system_resources",
    # Health endpoints
    "create_health_app",
    "create_simple_health_handler",
    "get_health_manager",
]

__version__ = "1.0.0"
