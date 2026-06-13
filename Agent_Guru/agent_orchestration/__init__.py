"""Agent Orchestration System - Core innovation of Agent_Guru.

This module provides the complete agent orchestration system including:
- Dynamic agent creation and lifecycle management
- Emergent specialization through performance tracking
- Agent merging for redundancy reduction
- Agent splitting for sub-specialization
- Optimal task assignment based on specialization
- Performance-driven evolution
- Background service orchestration

The full implementation lives in Agent_Guru.agents. This module re-exports
the complete public API for backward compatibility.
"""

# Core data models (local implementations for backward compatibility)
from Agent_Guru.agent_orchestration.models import (
    Agent,
    AgentStatus,
    EvolutionEvent,
    PerformanceRecord,
    Task,
    TaskType,
)

# Full orchestration system from agents module
from Agent_Guru.agents import (
    AgentLifecycleManager,
    AgentOrchestrator,
    OrchestrationSystem,
    PerformanceTracker,
    TaskAssigner,
    TaskDecomposer,
    TaskResult,
    TaskStatus,
)

__all__ = [
    # Core models
    "Agent",
    "AgentLifecycleManager",
    "AgentOrchestrator",
    "AgentStatus",
    "EvolutionEvent",
    # Full orchestration system
    "OrchestrationSystem",
    "PerformanceRecord",
    "PerformanceTracker",
    "Task",
    "TaskAssigner",
    "TaskDecomposer",
    "TaskResult",
    "TaskStatus",
    "TaskType",
]
