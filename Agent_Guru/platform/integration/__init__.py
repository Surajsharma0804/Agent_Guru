"""
Module: Agent_Guru.platform.integration
Purpose: Component integration clients for Platform Integration System

This module provides client interfaces for integrating with other Agent_Guru
components including Goal Manager, Memory System, Verifier System, and
Self-Improvement Engine.

Author: Agent Guru Platform Team
Date: 2026-02-26
"""

from Agent_Guru.platform.integration.goal_manager_client import (
    GoalManagerClient,
    TaskCompletionNotification,
    OperationResult,
    NotificationStatus,
)
from Agent_Guru.platform.integration.memory_client import (
    MemorySystemClient,
    OperationMetadata,
    MemoryQueryResult,
)
from Agent_Guru.platform.integration.verifier_client import (
    VerifierClient,
    ValidationRequest,
    ValidationResult,
    ValidationStatus,
)
from Agent_Guru.platform.integration.self_improvement_client import (
    SelfImprovementClient,
    PerformanceMetrics,
    ErrorStatistics,
    ImprovementSuggestion,
)
from Agent_Guru.platform.integration.service_discovery import (
    ServiceRegistry,
    ServiceEndpoint,
    ServiceStatus,
)
from Agent_Guru.platform.integration.tracing import (
    Tracer,
    Span,
    SpanContext,
    SpanManager,
)
from Agent_Guru.platform.integration.metrics_exporter import (
    MetricsRegistry,
    Counter,
    Gauge,
    Histogram,
    get_default_registry,
)
from Agent_Guru.platform.integration.graceful_shutdown import (
    GracefulShutdownManager,
    ShutdownPhase,
    ShutdownState,
    OperationTracker,
)

__all__ = [
    # Goal Manager
    "GoalManagerClient",
    "TaskCompletionNotification",
    "OperationResult",
    "NotificationStatus",
    # Memory System
    "MemorySystemClient",
    "OperationMetadata",
    "MemoryQueryResult",
    # Verifier
    "VerifierClient",
    "ValidationRequest",
    "ValidationResult",
    "ValidationStatus",
    # Self-Improvement
    "SelfImprovementClient",
    "PerformanceMetrics",
    "ErrorStatistics",
    "ImprovementSuggestion",
    # Service Discovery
    "ServiceRegistry",
    "ServiceEndpoint",
    "ServiceStatus",
    # Tracing
    "Tracer",
    "Span",
    "SpanContext",
    "SpanManager",
    # Metrics
    "MetricsRegistry",
    "Counter",
    "Gauge",
    "Histogram",
    "get_default_registry",
    # Graceful Shutdown
    "GracefulShutdownManager",
    "ShutdownPhase",
    "ShutdownState",
    "OperationTracker",
]
