"""Latency tracking and budget enforcement module.

Provides comprehensive latency management for all pipeline stages:
- High-resolution timing and tracking
- Budget enforcement with timeouts
- Monitoring and alerting
- Degraded mode management
- Performance dashboards
"""

from Agent_Guru.reasoning.latency.controller import (
    LatencyController,
    StageTimer,
    get_latency_controller,
)
from Agent_Guru.reasoning.latency.tracker import (
    LATENCY_BUDGETS,
    DegradedModeManager,
    LatencyEnforcer,
    LatencyStatistics,
    LatencyTracker,
    PipelineStage,
    StageMetrics,
    get_degraded_mode_manager,
    get_latency_enforcer,
    get_latency_tracker,
)

__all__ = [
    "LATENCY_BUDGETS",
    "DegradedModeManager",
    "LatencyController",
    "LatencyEnforcer",
    "LatencyStatistics",
    "LatencyTracker",
    "PipelineStage",
    "StageMetrics",
    "StageTimer",
    "get_degraded_mode_manager",
    "get_latency_controller",
    "get_latency_enforcer",
    "get_latency_tracker",
]
