"""LLM Infrastructure Module.

This module provides local and cloud LLM integration for Agent_Guru's reasoning engine.
Supports hybrid deployment with Ollama server and cloud API fallback.

Components:
- OllamaServer: Ollama server integration with existing models
- LocalLLMServer: llama.cpp server management with GPU acceleration (legacy)
- LLMClient: Unified client for local and cloud LLM providers
- LLMRouter: Intelligent routing between local and cloud based on complexity
"""

from Agent_Guru.reasoning.llm.client import LLMClient
from Agent_Guru.reasoning.llm.local_server import LocalLLMServer
from Agent_Guru.reasoning.llm.models import (
    GPUBackend,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LocalLLMConfig,
    ServerHealth,
)
from Agent_Guru.reasoning.llm.ollama_server import OLLAMA_MODELS, OllamaModelConfig, OllamaServer

__all__ = [
    "OLLAMA_MODELS",
    "GPUBackend",
    "LLMClient",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "LocalLLMConfig",
    "LocalLLMServer",
    "OllamaModelConfig",
    "OllamaServer",
    "ServerHealth",
]
