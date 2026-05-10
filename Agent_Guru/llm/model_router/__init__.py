"""Agent_Guru.llm.model_router — Intelligent LLM Model Selection.

Dynamically selects optimal language models based on task requirements,
cost constraints, performance history, and learned patterns.

Components:
    - ModelRegistry: Catalog of available models with capabilities and costs
    - TaskAnalyzer: Extracts task features and requirements
    - ModelSelector: Chooses optimal model using scoring and learning weights
    - CostTracker: Monitors spending per model and task type
    - PerformanceMonitor: Tracks success rates and latency
    - FallbackManager: Handles failures with fallback strategies
    - LearningEngine: Improves selection over time from historical data
    - ModelRouter: Top-level facade coordinating all components
"""

from Agent_Guru.llm.model_router.analyzer import TaskAnalyzer
from Agent_Guru.llm.model_router.cost_tracker import CostTracker
from Agent_Guru.llm.model_router.fallback_manager import FallbackManager
from Agent_Guru.llm.model_router.learning_engine import LearningEngine
from Agent_Guru.llm.model_router.models import (
    CostRecord,
    CostSummary,
    FallbackEvent,
    LearningWeights,
    ModelCapability,
    ModelFilter,
    ModelMetadata,
    PerformanceMetrics,
    PerformanceRecord,
    Provider,
    SelectionResult,
    TaskAnalysis,
    TaskSpecification,
    TaskType,
)
from Agent_Guru.llm.model_router.performance_monitor import PerformanceMonitor
from Agent_Guru.llm.model_router.registry import ModelRegistry
from Agent_Guru.llm.model_router.router import ModelRouter
from Agent_Guru.llm.model_router.selector import ModelSelector

__all__ = [
    "CostRecord",
    "CostSummary",
    "CostTracker",
    "FallbackEvent",
    "FallbackManager",
    "LearningEngine",
    "LearningWeights",
    "ModelCapability",
    "ModelFilter",
    "ModelMetadata",
    "ModelRegistry",
    "ModelRouter",
    "ModelSelector",
    "PerformanceMetrics",
    "PerformanceMonitor",
    "PerformanceRecord",
    "Provider",
    "SelectionResult",
    "TaskAnalysis",
    "TaskAnalyzer",
    "TaskSpecification",
    "TaskType",
]
