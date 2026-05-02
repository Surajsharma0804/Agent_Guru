"""
Ollama LLM Server Integration

Manages Ollama server integration for local inference.
Provides health checks, model selection, and inference endpoints.

Performance Targets:
- Inference latency: <400ms for 512 tokens (95th percentile)
- GPU utilization: >80% during inference
- Health check: <50ms
- Model switching: <100ms

Active Model (May 2025):
- gemma3:4b (3.3 GB) - 4B parameters - Best quality for 4GB VRAM

Requirements: 4.2, 4.5
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

from Agent_Guru.reasoning.llm.models import (
    GPUBackend,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ServerHealth,
)


@dataclass
class OllamaModelConfig:
    """Configuration for Ollama model."""

    name: str  # Model name (e.g., "gemma3:4b")
    size_gb: float  # Model size in GB
    parameters: str  # Parameter count (e.g., "4B")
    use_case: str  # "complex" or "simple"
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 512


# Predefined model configurations â€” gemma3:4b is the single active model
# Best choice for 4GB VRAM (RTX 2050/3050/4050) as of May 2025.
OLLAMA_MODELS = {
    "gemma3:4b": OllamaModelConfig(
        name="gemma3:4b",
        size_gb=3.3,
        parameters="4B",
        use_case="general",
        temperature=0.7,
        top_p=0.9,
        max_tokens=512,
    ),
}


class OllamaServer:
    """
    Ollama LLM server integration with intelligent model routing.

    Time Complexity: O(1) for health checks, O(n) for inference (n = tokens)
    Space Complexity: O(1) - models managed by Ollama

    Example:
        >>> server = OllamaServer(host="127.0.0.1", port=11434)
        >>> await server.start()
        >>> health = await server.health_check()
        >>> print(f"Server healthy: {health.is_healthy}")
        >>> request = LLMRequest(prompt="Hello, world!")
        >>> response = await server.generate(request, model="gemma3:4b")
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 11434,
        default_model: str = "gemma3:4b",
    ):
        """Initialize Ollama server client.

        Args:
            host: Ollama server host
            port: Ollama server port
            default_model: Default model to use for inference
        """
        self.host = host
        self.port = port
        self._base_url = f"http://{host}:{port}"

        # Accept any model â€” don't restrict to OLLAMA_MODELS dict
        # so env var overrides work without code changes
        self.default_model = default_model
        self._is_running = False
        self._available_models: list[str] = []

    async def start(self, timeout: float = 10.0) -> None:
        """Check Ollama server availability and list models.

        Time Complexity: O(1)
        Space Complexity: O(n) where n = number of models

        Args:
            timeout: Maximum time to wait for server check (seconds)

        Raises:
            RuntimeError: If server is not available
            TimeoutError: If check exceeds timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            health = await self.health_check()
            if health.is_healthy:
                # List available models
                self._available_models = await self._list_models()

                # Verify required models are available
                required_models = ["gemma3:4b"]
                missing_models = [m for m in required_models if m not in self._available_models]

                if missing_models:
                    raise RuntimeError(
                        f"Required models not found: {missing_models}. "
                        f"Run: ollama pull gemma3:4b\n"
                        f"Available models: {self._available_models}"
                    )

                self._is_running = True
                return

            await asyncio.sleep(0.5)

        raise TimeoutError(f"Ollama server not available within {timeout}s")

    async def _list_models(self) -> list[str]:
        """List available models from Ollama.

        Returns:
            List of model names

        Raises:
            RuntimeError: If listing fails
        """
        import asyncio
        import concurrent.futures

        try:
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                response = await loop.run_in_executor(
                    pool,
                    lambda: requests.get(f"{self._base_url}/api/tags", timeout=2.0),
                )

            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return [model.get("name", "") for model in models]
            else:
                raise RuntimeError(f"Failed to list models: {response.status_code}")

        except requests.RequestException as e:
            raise RuntimeError(f"Error listing models: {str(e)}") from e

    async def health_check(self) -> ServerHealth:
        """Check Ollama server health and availability.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            Server health status

        Requirements: 4.2
        """
        import asyncio
        import concurrent.futures

        start_time = time.time()

        try:
            # Run blocking HTTP call in thread pool to avoid blocking event loop
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                response = await loop.run_in_executor(
                    pool,
                    lambda: requests.get(f"{self._base_url}/api/tags", timeout=1.0),
                )

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return ServerHealth(
                    is_healthy=True,
                    model_loaded=len(self._available_models) > 0,
                    gpu_available=True,
                    gpu_backend=GPUBackend.CUDA,
                    latency_ms=latency_ms,
                )
            else:
                return ServerHealth(
                    is_healthy=False,
                    model_loaded=False,
                    gpu_available=False,
                    gpu_backend=None,
                    latency_ms=latency_ms,
                    error_message=f"Health check failed: {response.status_code}",
                )

        except requests.RequestException as e:
            return ServerHealth(
                is_healthy=False,
                model_loaded=False,
                gpu_available=False,
                gpu_backend=None,
                latency_ms=None,
                error_message=f"Ollama not available: {str(e)}",
            )

    async def generate(
        self,
        request: LLMRequest,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Generate text using Ollama model.

        Time Complexity: O(n) where n = tokens generated
        Space Complexity: O(n)

        Args:
            request: LLM request with prompt and parameters
            model: Model name to use (None = use default)

        Returns:
            LLM response with generated text

        Raises:
            RuntimeError: If server not running or generation fails

        Requirements: 4.2, 10.1
        """
        if not self._is_running:
            raise RuntimeError("Server not running. Call start() first.")

        # Use default model if not specified
        model_name = model or self.default_model

        # Verify model is available
        if model_name not in self._available_models:
            raise RuntimeError(
                f"Model not available: {model_name}. " f"Available: {self._available_models}"
            )

        start_time = time.time()

        try:
            # Build request payload for Ollama API
            payload: dict[str, Any] = {
                "model": model_name,
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

            # Run blocking HTTP call in thread pool to avoid blocking event loop
            import asyncio
            import concurrent.futures

            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                response = await loop.run_in_executor(
                    pool,
                    lambda: requests.post(
                        f"{self._base_url}/api/generate",
                        json=payload,
                        timeout=15.0,
                    ),
                )

            latency_ms = (time.time() - start_time) * 1000

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
                        "model": model_name,
                        "total_duration_ns": data.get("total_duration", 0),
                        "load_duration_ns": data.get("load_duration", 0),
                        "prompt_eval_count": data.get("prompt_eval_count", 0),
                        "eval_count": data.get("eval_count", 0),
                    },
                )
            else:
                raise RuntimeError(f"Generation failed: {response.status_code} - {response.text}")

        except requests.RequestException as e:
            raise RuntimeError(f"Generation error: {str(e)}") from e

    def select_model_for_task(self, complexity: str) -> str:
        """Select optimal model based on task complexity.

        Args:
            complexity: Task complexity ("simple" or "complex")

        Returns:
            Model name to use â€” always gemma3:4b (best for 4GB VRAM)

        Example:
            >>> server.select_model_for_task("simple")
            'gemma3:4b'
            >>> server.select_model_for_task("complex")
            'gemma3:4b'
        """
        import os
        return os.environ.get("OLLAMA_MODEL", "").strip() or "gemma3:4b"

    async def measure_latency(
        self,
        model: str,
        num_samples: int = 10,
    ) -> dict[str, float]:
        """Measure inference latency for a model.

        Args:
            model: Model name to test
            num_samples: Number of test samples

        Returns:
            Dictionary with latency statistics (mean, p50, p95, p99)

        Requirements: 10.1
        """
        latencies = []

        test_prompt = "Hello, how are you today?"
        request = LLMRequest(
            prompt=test_prompt,
            max_tokens=50,
            temperature=0.7,
        )

        for _ in range(num_samples):
            try:
                response = await self.generate(request, model=model)
                latencies.append(response.latency_ms)
            except Exception as e:
                continue

        if not latencies:
            return {
                "mean": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        latencies.sort()
        n = len(latencies)

        return {
            "mean": sum(latencies) / n,
            "p50": latencies[int(n * 0.50)],
            "p95": latencies[int(n * 0.95)],
            "p99": latencies[int(n * 0.99)],
        }

    async def stop(self) -> None:
        """Stop Ollama server client (no-op, Ollama runs independently).

        Time Complexity: O(1)
        Space Complexity: O(1)
        """
        self._is_running = False
        self._available_models = []

    def is_running(self) -> bool:
        """Check if server client is active."""
        return self._is_running

    def get_available_models(self) -> list[str]:
        """Get list of available models."""
        return self._available_models.copy()

    def get_model_config(self, model: str) -> Optional[OllamaModelConfig]:
        """Get configuration for a model.

        Args:
            model: Model name

        Returns:
            Model configuration or None if not found
        """
        return OLLAMA_MODELS.get(model)
