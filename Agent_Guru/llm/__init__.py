"""
Agent Guru LLM Runtime Package.

Provides a unified interface for running language models across
Ollama, OpenAI, Anthropic, and Google providers.

Public API:
    LLMRuntime: Main runtime interface
    RuntimeConfig: Configuration class
    CompletionRequest / CompletionResponse: Request/response models
    Message, StreamChunk, TokenUsage: Core data types
    ModelProvider: Provider enum
    load_config_from_env / load_config_from_file: Config loaders
"""

from Agent_Guru.llm.config_loader import load_config_from_env, load_config_from_file
from Agent_Guru.llm.context_manager import ContextManager
from Agent_Guru.llm.error_handler import ErrorHandler
from Agent_Guru.llm.llm_runtime import LLMRuntime
from Agent_Guru.llm.models import (
    AnthropicConfig,
    CircuitBreakerOpenError,
    CompletionRequest,
    CompletionResponse,
    ContextWindowExceededError,
    FunctionDefinition,
    GoogleConfig,
    Message,
    ModelProvider,
    OllamaConfig,
    OpenAIConfig,
    ProviderNotSupportedError,
    RuntimeConfig,
    StreamChunk,
    TokenUsage,
)
from Agent_Guru.llm.performance_monitor import PerformanceMonitor
from Agent_Guru.llm.token_counter import TokenCounter

__all__ = [
    "LLMRuntime",
    "RuntimeConfig",
    "CompletionRequest",
    "CompletionResponse",
    "Message",
    "StreamChunk",
    "TokenUsage",
    "FunctionDefinition",
    "ModelProvider",
    "OllamaConfig",
    "OpenAIConfig",
    "AnthropicConfig",
    "GoogleConfig",
    "ContextWindowExceededError",
    "CircuitBreakerOpenError",
    "ProviderNotSupportedError",
    "load_config_from_env",
    "load_config_from_file",
    "TokenCounter",
    "ContextManager",
    "ErrorHandler",
    "PerformanceMonitor",
]
