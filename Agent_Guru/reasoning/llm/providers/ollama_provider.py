"""
Ollama LLM Provider

Provides local LLM inference using Ollama server.
Supports models like Mistral, Qwen, Llama, etc.

Performance Targets:
- Inference latency: <400ms for 512 tokens (95th percentile)
- GPU utilization: >80% during inference
- No API key required (local inference)
"""

import asyncio
import time
from typing import Optional, Dict, Any

import requests

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.providers.base import BaseLLMProvider, ProviderConfig


class OllamaProviderConfig(ProviderConfig):
    """Configuration for Ollama provider."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 11434,
        model: str = "mistral:7b-instruct",
        **kwargs
    ):
        """Initialize Ollama config.

        Args:
            host: Ollama server host
            port: Ollama server port
            model: Model name to use
            **kwargs: Additional config parameters
        """
        # Ollama doesn't need API key, but base class requires it
        super().__init__(api_key="local", **kwargs)
        self.host = host
        self.port = port
        self.model = model
        self.base_url = f"http://{host}:{port}"


class OllamaProvider(BaseLLMProvider):
    """
    Ollama LLM provider for local inference.

    Supports models:
    - mistral:7b-instruct (fast, simple tasks)
    - qwen2.5:14b-instruct (complex reasoning)
    - llama3:8b-instruct (balanced)

    Example:
        >>> config = OllamaProviderConfig(model="mistral:7b-instruct")
        >>> provider = OllamaProvider(config)
        >>> request = LLMRequest(prompt="What is the time?")
        >>> response = await provider.generate(request)
    """

    def __init__(self, config: OllamaProviderConfig):
        """Initialize Ollama provider.

        Args:
            config: Ollama provider configuration
        """
        super().__init__(config)
        self.ollama_config = config

    def get_provider_type(self) -> LLMProvider:
        """Get provider type."""
        return LLMProvider.LOCAL

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text using Ollama API.

        Args:
            request: LLM request

        Returns:
            LLM response

        Raises:
            RuntimeError: If Ollama server is not available
        """
        start_time = time.perf_counter()

        # Build request payload
        payload: Dict[str, Any] = {
            "model": self.ollama_config.model,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "top_p": request.top_p,
                "num_predict": request.max_tokens,
            },
        }

        # Add stop sequences if provided
        if request.stop_sequences:
            options = payload["options"]
            if isinstance(options, dict):
                options["stop"] = request.stop_sequences

        try:
            # Call Ollama generate endpoint (synchronous, run in executor)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    f"{self.ollama_config.base_url}/api/generate",
                    json=payload,
                    timeout=self.config.timeout_seconds,
                ),
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()

                # Extract response text
                text = data.get("response", "")

                # Determine finish reason
                finish_reason = "stop"
                if data.get("done_reason") == "length":
                    finish_reason = "length"
                elif not data.get("done", False):
                    finish_reason = "error"

                # Count tokens (approximate from eval_count)
                tokens_generated = data.get("eval_count", len(text.split()))

                return LLMResponse(
                    text=text,
                    provider=LLMProvider.LOCAL,
                    latency_ms=latency_ms,
                    tokens_generated=tokens_generated,
                    finish_reason=finish_reason,
                    metadata={
                        "model": self.ollama_config.model,
                        "total_duration_ns": data.get("total_duration", 0),
                        "load_duration_ns": data.get("load_duration", 0),
                        "prompt_eval_count": data.get("prompt_eval_count", 0),
                        "eval_count": data.get("eval_count", 0),
                    },
                )
            else:
                raise RuntimeError(
                    f"Ollama generation failed: {response.status_code} - {response.text}"
                )

        except requests.RequestException as e:
            raise RuntimeError(f"Ollama server error: {str(e)}")

    async def health_check(self) -> bool:
        """Check if Ollama server is available.

        Returns:
            True if server is healthy
        """
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    f"{self.ollama_config.base_url}/api/tags",
                    timeout=2.0,
                ),
            )
            return response.status_code == 200
        except Exception:
            return False
