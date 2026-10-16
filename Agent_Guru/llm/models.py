"""Core data models for the LLM Runtime System.

Defines unified data structures used across all providers:
Message, CompletionRequest, CompletionResponse, TokenUsage,
StreamChunk, FunctionDefinition, and configuration classes.

Author: Agent Guru Team
Date: 2026-03-18
Version: 1.0.0
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from datetime import datetime


class ModelProvider(Enum):
    """Supported model providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    #: llama.cpp, vLLM, LM Studio, SGLang, or a cloud API in the OpenAI shape
    OPENAI_COMPATIBLE = "openai_compatible"


# ---------------------------------------------------------------------------
# Core message / request / response types
# ---------------------------------------------------------------------------


@dataclass
class Message:
    """Chat message in unified format."""

    role: str  # "system", "user", "assistant", "function", "tool"
    content: str
    name: str | None = None  # For function messages; the tool's name on a "tool" message
    function_call: dict[str, Any] | None = None
    #: The tools an assistant message asked for, sent back with it so the
    #: model sees which result answers which call.
    tool_calls: list[ToolCall] | None = None


@dataclass
class ToolCall:
    """One tool the model asked to run, with the arguments it wrote (untrusted)."""

    name: str
    arguments: dict[str, Any]


@dataclass
class FunctionDefinition:
    """Function definition for function calling."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema


@dataclass
class TokenUsage:
    """Token usage information."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float


@dataclass
class StreamChunk:
    """Streaming response chunk."""

    content: str
    finish_reason: str | None = None
    function_call: dict[str, Any] | None = None
    # Set on the last chunk only, and only when the provider reports them.
    # A stream used to end without either, so the spoken answer, the one
    # every question takes, left no token counts or model timings behind.
    usage: TokenUsage | None = None
    timings: dict[str, float] | None = None
    #: Tools the model asked to run, on the chunk that carried them.
    tool_calls: list[ToolCall] | None = None


@dataclass
class CompletionRequest:
    """Request for text completion or chat."""

    model: str
    messages: list[Message]
    temperature: float = 0.7
    max_tokens: int | None = None
    stream: bool = False
    functions: list[FunctionDefinition] | None = None
    function_call: str | dict[str, str] | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionResponse:
    """Response from completion request."""

    content: str
    model: str
    provider: ModelProvider
    finish_reason: str
    usage: TokenUsage
    latency_ms: float
    timestamp: datetime
    function_call: dict[str, Any] | None = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool_calls: list[ToolCall] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Configuration models (Pydantic for validation)
# ---------------------------------------------------------------------------


class OllamaConfig(BaseModel):
    """Configuration for Ollama local models."""

    host: str = "http://localhost:11434"
    timeout_s: float = 120.0
    max_retries: int = 3

    model_config = {"extra": "forbid"}


class RuntimeConfig(BaseModel):
    """Top-level runtime configuration."""

    ollama_config: OllamaConfig = Field(default_factory=OllamaConfig)

    # Context management
    compression_threshold: float = 0.8
    max_history_messages: int = 100

    # Error handling
    max_retries: int = 3
    initial_backoff_ms: float = 100.0
    max_backoff_ms: float = 10000.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_s: float = 60.0

    # Performance monitoring
    slow_threshold_ms: float = 5000.0
    failure_threshold: int = 5

    # GitHub sync (optional)
    github_repo_url: str | None = None
    github_branch: str = "main"
    github_auth_token: str | None = None

    @field_validator("compression_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0.0 < v <= 1.0:
            msg = "compression_threshold must be between 0 and 1"
            raise ValueError(msg)
        return v

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class ContextWindowExceededError(Exception):
    """Raised when a request would exceed the model's context window."""


class CircuitBreakerOpenError(Exception):
    """Raised when the circuit breaker is open for a provider."""


class ProviderNotSupportedError(Exception):
    """Raised when a feature is not supported by the provider."""
