"""Module: Agent_Guru.platform.integration
Purpose: Component integration clients for Platform Integration System.

This module provides client interfaces for integrating with other Agent_Guru
components including Goal Manager, Memory System, Verifier System, and
Self-Improvement Engine.

Author: Agent Guru Platform Team
Date: 2026-02-26
"""

from Agent_Guru.platform.integration.goal_manager_client import (
    GoalManagerClient,
    NotificationStatus,
    OperationResult,
    TaskCompletionNotification,
)
from Agent_Guru.platform.integration.graceful_shutdown import (
    GracefulShutdownManager,
    OperationTracker,
    ShutdownPhase,
    ShutdownState,
)
from Agent_Guru.platform.integration.memory_client import (
    MemoryQueryResult,
    MemorySystemClient,
    OperationMetadata,
)
from Agent_Guru.platform.integration.metrics_exporter import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    get_default_registry,
)
from Agent_Guru.platform.integration.self_improvement_client import (
    ErrorStatistics,
    ImprovementSuggestion,
    PerformanceMetrics,
    SelfImprovementClient,
)
from Agent_Guru.platform.integration.service_discovery import (
    ServiceEndpoint,
    ServiceRegistry,
    ServiceStatus,
)
from Agent_Guru.platform.integration.tracing import (
    Span,
    SpanContext,
    SpanManager,
    Tracer,
)
from Agent_Guru.platform.integration.verifier_client import (
    ValidationRequest,
    ValidationResult,
    ValidationStatus,
    VerifierClient,
)

__all__ = [
    "Counter",
    "ErrorStatistics",
    "Gauge",
    # Goal Manager
    "GoalManagerClient",
    # Graceful Shutdown
    "GracefulShutdownManager",
    "Histogram",
    "ImprovementSuggestion",
    "MemoryQueryResult",
    # Memory System
    "MemorySystemClient",
    # Metrics
    "MetricsRegistry",
    "NotificationStatus",
    "OperationMetadata",
    "OperationResult",
    "OperationTracker",
    "PerformanceMetrics",
    # Self-Improvement
    "SelfImprovementClient",
    "ServiceEndpoint",
    # Service Discovery
    "ServiceRegistry",
    "ServiceStatus",
    "ShutdownPhase",
    "ShutdownState",
    "Span",
    "SpanContext",
    "SpanManager",
    "TaskCompletionNotification",
    # Tracing
    "Tracer",
    "ValidationRequest",
    "ValidationResult",
    "ValidationStatus",
    # Verifier
    "VerifierClient",
    "get_default_registry",
]
