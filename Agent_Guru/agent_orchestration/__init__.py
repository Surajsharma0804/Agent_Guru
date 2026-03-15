"""
Agent Orchestration System - Core innovation of Agent_Guru.

This module enables emergent multi-agent behavior through dynamic agent creation,
specialization, merging, and evolution based on performance patterns.

Key Features:
- Dynamic agent creation based on task requirements
- Emergent specialization through performance tracking
- Agent merging for redundancy reduction
- Agent splitting for sub-specialization
- Optimal task assignment based on specialization
- Performance-driven evolution

Architecture:
- No pre-defined agent roles (researcher, coder, planner)
- Agents emerge from task patterns
- Measurable improvement over time
- Self-organizing agent population
"""

from Agent_Guru.agent_orchestration.models import (
    Agent,
    AgentStatus,
    Task,
    TaskType,
    PerformanceRecord,
    EvolutionEvent,
)

__all__ = [
    "Agent",
    "AgentStatus",
    "Task",
    "TaskType",
    "PerformanceRecord",
    "EvolutionEvent",
]
