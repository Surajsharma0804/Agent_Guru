"""
Comprehensive Failure Handling and Safe Degradation System

This module implements production-grade failure detection, monitoring, and safe
degradation for all GURU components. It ensures that any component failure
results in immediate safe halt rather than degraded operation.

Core Components:
- ComponentHealthMonitor: Monitors health of all core components
- FailureDetector: Detects and classifies component failures
- SafeDegradationManager: Manages safe system degradation
- DependencyMapper: Maps component dependencies and cascade failures
- RecoveryOrchestrator: Coordinates recovery procedures

Security Principles:
- Fail-safe, never fail-open
- No silent degradation
- Immediate authority revocation on critical failures
- Comprehensive audit logging of all failures
- Component isolation to prevent cascade failures

Requirements Coverage:
- 21.1: Core component failure detection and authority revocation
- 21.2: Audit log failure handling
- 21.4: No degraded security state operation
- 21.5: Comprehensive failure logging
"""

from .dependency_mapper import (
    CascadeAnalysis,
    ComponentCriticality,
    ComponentDependency,
    DependencyGraph,
    DependencyMapper,
    DependencyType,
)
from .exceptions import (
    ComponentFailureError,
    CriticalSystemFailureError,
    DegradationNotAllowedError,
    RecoveryFailedError,
)
from .failure_detector import (
    ComponentFailure,
    FailureDetectable,
    FailureDetectionConfig,
    FailureDetector,
    FailureSeverity,
    FailureType,
)
from .health_monitor import ComponentHealth, ComponentHealthMonitor, HealthLimits, HealthMetrics, HealthStatus
from .recovery_orchestrator import (
    RecoveryAction,
    RecoveryActionType,
    RecoveryOrchestrator,
    RecoveryPlan,
    RecoveryResult,
    RecoveryStatus,
)
from .safe_degradation import SafeDegradationManager  # Alias
from .safe_degradation import (
    DegradationAction,
    DegradationLevel,
    DegradationPlan,
    SystemDegradationOrchestrator,
    SystemState,
)
from .system_failure_orchestrator import SystemFailureOrchestrator, SystemFailureReport, SystemFailureState

__all__ = [
    # Health Monitoring
    "ComponentHealthMonitor",
    "ComponentHealth",
    "HealthStatus",
    "HealthMetrics",
    "HealthLimits",
    # Failure Detection
    "FailureDetector",
    "ComponentFailure",
    "FailureType",
    "FailureSeverity",
    "FailureDetectionConfig",
    "FailureDetectable",
    # Safe Degradation
    "SystemDegradationOrchestrator",
    "SafeDegradationManager",  # Alias
    "DegradationLevel",
    "DegradationAction",
    "DegradationPlan",
    "SystemState",
    # Dependency Management
    "DependencyMapper",
    "ComponentDependency",
    "DependencyGraph",
    "CascadeAnalysis",
    "DependencyType",
    "ComponentCriticality",
    # Recovery
    "RecoveryOrchestrator",
    "RecoveryPlan",
    "RecoveryAction",
    "RecoveryResult",
    "RecoveryActionType",
    "RecoveryStatus",
    # System Management
    "SystemFailureOrchestrator",
    "SystemFailureState",
    "SystemFailureReport",
    # Exceptions
    "ComponentFailureError",
    "CriticalSystemFailureError",
    "RecoveryFailedError",
    "DegradationNotAllowedError",
]
