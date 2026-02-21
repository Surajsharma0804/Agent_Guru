"""
Data models for LLM infrastructure.

Defines request/response structures for local and cloud LLM interactions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime


class LLMProvider(str, Enum):
    """LLM provider types."""

    LOCAL = "local"  # llama.cpp local server
    OPENAI = "openai"  # OpenAI GPT-4
    ANTHROPIC = "anthropic"  # Claude 3.5
    GEMINI = "gemini"  # Google Gemini


class GPUBackend(str, Enum):
    """GPU acceleration backend."""

    CUDA = "cuda"  # NVIDIA CUDA
    METAL = "metal"  # Apple Metal
    CPU = "cpu"  # CPU-only fallback


@dataclass
class LLMRequest:
    """Request to LLM for inference."""

    prompt: str
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 512
    stop_sequences: List[str] = field(default_factory=list)
    stream: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate request parameters."""
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"temperature must be 0.0-2.0, got {self.temperature}")
        if not 0.0 <= self.top_p <= 1.0:
            raise ValueError(f"top_p must be 0.0-1.0, got {self.top_p}")
        if self.max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {self.max_tokens}")


@dataclass
class LLMResponse:
    """Response from LLM inference."""

    text: str
    provider: LLMProvider
    latency_ms: float
    tokens_generated: int
    finish_reason: str  # "stop", "length", "error"
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate response fields."""
        if self.latency_ms < 0:
            raise ValueError(f"latency_ms must be non-negative, got {self.latency_ms}")
        if self.tokens_generated < 0:
            raise ValueError(
                f"tokens_generated must be non-negative, got {self.tokens_generated}"
            )
        if self.finish_reason not in ["stop", "length", "error"]:
            raise ValueError(
                f"finish_reason must be 'stop', 'length', or 'error', got {self.finish_reason}"
            )


@dataclass
class LocalLLMConfig:
    """Configuration for local llama.cpp server."""

    model_path: str
    gpu_backend: GPUBackend = GPUBackend.CUDA
    n_gpu_layers: int = 35  # Number of layers to offload to GPU
    n_ctx: int = 2048  # Context window size
    n_threads: int = 8  # CPU threads for non-GPU layers
    host: str = "127.0.0.1"
    port: int = 8080
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 512

    def __post_init__(self):
        """Validate configuration."""
        if self.n_gpu_layers < 0:
            raise ValueError(f"n_gpu_layers must be non-negative, got {self.n_gpu_layers}")
        if self.n_ctx <= 0:
            raise ValueError(f"n_ctx must be positive, got {self.n_ctx}")
        if self.n_threads <= 0:
            raise ValueError(f"n_threads must be positive, got {self.n_threads}")
        if not 1024 <= self.port <= 65535:
            raise ValueError(f"port must be 1024-65535, got {self.port}")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"temperature must be 0.0-2.0, got {self.temperature}")
        if not 0.0 <= self.top_p <= 1.0:
            raise ValueError(f"top_p must be 0.0-1.0, got {self.top_p}")
        if self.max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {self.max_tokens}")


@dataclass
class ServerHealth:
    """Health status of LLM server."""

    is_healthy: bool
    model_loaded: bool
    gpu_available: bool
    gpu_backend: Optional[GPUBackend]
    latency_ms: Optional[float]
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
