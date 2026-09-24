"""Module: Agent_Guru.llm.model_router.models
Purpose: Core data models for the Model Router system.

All models use Pydantic v2 for validation with full type annotations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ModelCapability(str, Enum):
    """Capabilities a model may support."""

    CODE_GENERATION = "code_generation"
    REASONING = "reasoning"
    DATA_ANALYSIS = "data_analysis"
    CREATIVE_WRITING = "creative_writing"
    CONVERSATION = "conversation"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    LONG_CONTEXT = "long_context"


class TaskType(str, Enum):
    """Types of tasks the router handles."""

    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    REASONING = "reasoning"
    DATA_ANALYSIS = "data_analysis"
    CREATIVE_WRITING = "creative_writing"
    CONVERSATION = "conversation"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"


class Provider(str, Enum):
    """LLM providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class ModelMetadata(BaseModel):
    """Metadata for a registered model."""

    model_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    provider: Provider
    capabilities: set[ModelCapability] = Field(default_factory=set)
    cost_per_input_token: float = Field(default=0.0, ge=0.0)
    cost_per_output_token: float = Field(default=0.0, ge=0.0)
    max_tokens: int = Field(default=4096, ge=1)
    average_latency_ms: float = Field(default=1000.0, ge=0.0)
    is_available: bool = Field(default=True)
    registered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": False}

    def estimated_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a given token count."""
        return input_tokens * self.cost_per_input_token + output_tokens * self.cost_per_output_token


class ModelFilter(BaseModel):
    """Filter criteria for querying models."""

    capabilities: set[ModelCapability] | None = None
    provider: Provider | None = None
    max_cost_per_input_token: float | None = None
    max_cost_per_output_token: float | None = None
    available_only: bool = True
    min_max_tokens: int | None = None

    model_config = {"frozen": False}


class TaskSpecification(BaseModel):
    """Specification for a task to be routed."""

    content: str = Field(..., min_length=1)
    explicit_model_id: str | None = None
    max_latency_ms: float | None = None
    max_cost: float | None = None
    required_capabilities: set[ModelCapability] = Field(default_factory=set)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": False}


class TaskAnalysis(BaseModel):
    """Result of analyzing a task specification."""

    task_type: TaskType
    complexity: str = Field(default="medium")  # low, medium, high
    domain: str = Field(default="general")
    estimated_input_tokens: int = Field(default=100, ge=0)
    estimated_output_tokens: int = Field(default=200, ge=0)
    required_capabilities: set[ModelCapability] = Field(default_factory=set)
    latency_constraint_ms: float | None = None
    cost_constraint: float | None = None

    @field_validator("complexity")
    @classmethod
    def validate_complexity(cls, v: str) -> str:
        if v not in ("low", "medium", "high"):
            msg = f"complexity must be low/medium/high, got '{v}'"
            raise ValueError(msg)
        return v

    model_config = {"frozen": False}


class SelectionResult(BaseModel):
    """Result of model selection."""

    model_id: str
    reasoning: str = ""
    estimated_cost: float = Field(default=0.0, ge=0.0)
    estimated_latency_ms: float = Field(default=0.0, ge=0.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    fallback_models: list[str] = Field(default_factory=list)

    model_config = {"frozen": False}


class CostRecord(BaseModel):
    """Record of cost for a single task execution."""

    record_id: str
    model_id: str
    task_type: TaskType
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost: float = Field(default=0.0, ge=0.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"frozen": False}


class CostSummary(BaseModel):
    """Aggregated cost summary over a period."""

    total_cost: float = Field(default=0.0, ge=0.0)
    cost_by_model: dict[str, float] = Field(default_factory=dict)
    cost_by_task_type: dict[str, float] = Field(default_factory=dict)
    period_start: datetime
    period_end: datetime
    record_count: int = Field(default=0, ge=0)

    model_config = {"frozen": False}


class PerformanceRecord(BaseModel):
    """Record of performance for a single task execution."""

    record_id: str
    model_id: str
    task_type: TaskType
    success: bool
    latency_ms: float = Field(default=0.0, ge=0.0)
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    failure_reason: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Cost of this invocation (input_tokens * cost_per_input + output_tokens *
    # cost_per_output), mirroring CostTracker's cost formula. Defaults to 0.0
    # for callers that don't have token/cost data available. Consumed by
    # LearningEngine._calculate_reward() to apply the cost penalty component
    # of the reward signal - see model_router/learning_engine.py.
    cost: float = Field(default=0.0, ge=0.0)

    model_config = {"frozen": False}


class PerformanceMetrics(BaseModel):
    """Aggregated performance metrics for a model+task_type pair."""

    model_id: str
    task_type: TaskType
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    average_latency_ms: float = Field(default=0.0, ge=0.0)
    average_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    sample_size: int = Field(default=0, ge=0)

    model_config = {"frozen": False}


class FallbackEvent(BaseModel):
    """Record of a fallback event."""

    original_model: str
    fallback_model: str
    task_type: TaskType
    reason: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"frozen": False}


class LearningWeights(BaseModel):
    """Learned weights for a model+task_type pair."""

    model_id: str
    task_type: TaskType
    weight: float = Field(default=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sample_size: int = Field(default=0, ge=0)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"frozen": False}
