"""Ollama LLM Server Integration.

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
import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from Agent_Guru.reasoning.llm.generation import context_fits, ollama_options
from Agent_Guru.reasoning.llm.models import (
    GPUBackend,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ServerHealth,
)
from Agent_Guru.reasoning.llm.timeouts import generate_timeout, start_timeout

# The vocabulary `OllamaModelConfig.use_case` is allowed to take. It used to
# be documented inline as `"complex" or "simple"` while the only registered
# model actually carried `"general"`, so the documented vocabulary and the
# real data disagreed and nothing enforced either.
OLLAMA_USE_CASES = frozenset({"general", "simple", "complex"})


@dataclass
class OllamaModelConfig:
    """Configuration for Ollama model.

    Validated on construction: a malformed entry in ``OLLAMA_MODELS`` (or one
    built by a caller) used to be accepted silently and only surfaced much
    later as a confusing inference failure or a nonsensical sampling setting.
    """

    name: str  # Model name (e.g., "gemma3:4b")
    size_gb: float  # Model size in GB
    parameters: str  # Parameter count (e.g., "4B")
    use_case: str  # One of OLLAMA_USE_CASES
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 512

    def __post_init__(self) -> None:
        """Reject configurations Ollama could not honour."""
        if not self.name or not self.name.strip():
            msg = "OllamaModelConfig.name must be a non-empty model name"
            raise ValueError(msg)
        if self.size_gb <= 0:
            msg = f"OllamaModelConfig.size_gb must be positive, got {self.size_gb}"
            raise ValueError(msg)
        if self.use_case not in OLLAMA_USE_CASES:
            msg = (
                f"OllamaModelConfig.use_case must be one of "
                f"{sorted(OLLAMA_USE_CASES)}, got {self.use_case!r}"
            )
            raise ValueError(msg)
        if not 0.0 <= self.temperature <= 2.0:
            msg = f"OllamaModelConfig.temperature must be in [0.0, 2.0], got {self.temperature}"
            raise ValueError(msg)
        if not 0.0 < self.top_p <= 1.0:
            msg = f"OllamaModelConfig.top_p must be in (0.0, 1.0], got {self.top_p}"
            raise ValueError(msg)
        if self.max_tokens <= 0:
            msg = f"OllamaModelConfig.max_tokens must be positive, got {self.max_tokens}"
            raise ValueError(msg)


# Predefined model configurations - gemma3:4b is the single active model
# Best choice for 4GB VRAM (RTX 2050/3050/4050) as of May 2025.
# FIX: this comment previously contained mojibake ("-" instead of "-") -
# UTF-8 bytes that had been decoded once as Latin-1/CP1252 and re-saved,
# a classic double-encoding corruption. Harmless to execution (it was only
# ever inside a comment) but real file-encoding damage worth fixing.
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
    """Ollama LLM server integration with intelligent model routing.

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
    ) -> None:
        """Initialize Ollama server client.

        Args:
            host: Ollama server host
            port: Ollama server port
            default_model: Default model to use for inference

        """
        if not host or not host.strip():
            msg = "OllamaServer host must be a non-empty hostname or IP address"
            raise ValueError(msg)
        if not 1 <= port <= 65535:
            msg = f"OllamaServer port must be in [1, 65535], got {port}"
            raise ValueError(msg)

        self.host = host
        self.port = port
        self._base_url = f"http://{host}:{port}"

        # Deliberately NOT restricted to the OLLAMA_MODELS dict. That dict is a
        # table of models whose sampling parameters this project has tuned, not
        # an allow-list: Ollama serves whatever the operator has pulled, and
        # five call sites (orchestrator, llm_manager, presentation, intent
        # engine, select_model_for_task) let OLLAMA_MODEL name one. Rejecting
        # unknown names here would break every one of those overrides.
        #
        # A blank name, though, can never be a model Ollama serves - it is
        # always a configuration mistake (an empty OLLAMA_MODEL, a stripped
        # config value), and letting it through only postponed the failure to
        # an opaque HTTP 400 from the Ollama daemon at first inference.
        if not default_model or not default_model.strip():
            msg = (
                "Unknown model: default_model must be a non-empty Ollama model "
                "name (e.g. 'gemma3:4b')"
            )
            raise ValueError(msg)

        self.default_model = default_model
        self._is_running = False
        self._available_models: list[str] = []

        # Single executor reused across all blocking HTTP calls
        import concurrent.futures
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    async def start(self, timeout: float | None = None) -> None:
        """Check Ollama server availability and list models.

        Time Complexity: O(1)
        Space Complexity: O(n) where n = number of models

        Args:
            timeout: Maximum time to wait for the server (seconds). Defaults
                to the OLLAMA_START_TIMEOUT_SECONDS policy. The old default of
                10 s assumed a server that was already warm; a cold Ollama
                still reading model weights off disk on a machine without a
                GPU routinely needs longer, and timing out there reports
                "not available" for a server that was merely still starting.

        Raises:
            RuntimeError: If server is not available
            TimeoutError: If check exceeds timeout

        """
        # FIX: was `time.time()`, wall-clock time that can jump backward or
        # forward on NTP sync, manual clock changes, or VM pause/resume -
        # any of which could make this loop run far longer than `timeout`
        # (or exit early) since `time.time() - start_time` is not guaranteed
        # monotonic. `time.monotonic()` is specifically designed for
        # measuring elapsed durations and is immune to wall-clock
        # adjustments. Applied consistently below and in health_check() /
        # generate() for the same reason.
        if timeout is None:
            timeout = start_timeout()

        start_time = time.monotonic()

        while time.monotonic() - start_time < timeout:
            health = await self.health_check()
            if health.is_healthy:
                # List available models
                self._available_models = await self._list_models()

                # Verify the configured model is available.
                #
                # DEFECT FIX: this used to require the literal "gemma3:4b"
                # regardless of what select_model() would actually request.
                # select_model_for_task() honours the OLLAMA_MODEL environment
                # variable, so a user who pulled a smaller model to suit
                # weaker hardware - the exact reason to change it - had the
                # server refuse to start, naming a model they had
                # deliberately not installed. The two now agree by
                # construction because start() asks the same selector the
                # generate path uses.
                required_model = self.select_model_for_task("general")
                if required_model not in self._available_models:
                    msg = (
                        f"Configured model not found: {required_model}. "
                        f"Run: ollama pull {required_model}\n"
                        f"Available models: {self._available_models}"
                    )
                    raise RuntimeError(
                        msg,
                    )

                self._is_running = True
                return

            await asyncio.sleep(0.5)

        msg = f"Ollama server not available within {timeout}s"
        raise TimeoutError(msg)

    async def _list_models(self) -> list[str]:
        """List available models from Ollama.

        Returns:
            List of model names

        Raises:
            RuntimeError: If listing fails

        """
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                self._executor,
                lambda: requests.get(f"{self._base_url}/api/tags", timeout=2.0),  # noqa: ASYNC210
            )

            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return [model.get("name", "") for model in models]
            msg = f"Failed to list models: {response.status_code}"
            raise RuntimeError(msg)

        except requests.RequestException as e:
            msg = f"Error listing models: {e!s}"
            raise RuntimeError(msg) from e

    async def health_check(self) -> ServerHealth:
        """Check Ollama server health and availability.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            Server health status

        Requirements: 4.2

        """
        # FIX: removed a redundant `import asyncio` here - the module
        # already imports asyncio at the top of the file; re-importing
        # locally added nothing but noise (Python caches sys.modules, so
        # it wasn't a bug, just dead weight).
        start_time = time.monotonic()  # FIX: was time.time(), see start()

        try:
            # Run blocking HTTP call in thread pool to avoid blocking event loop
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                self._executor,
                lambda: requests.get(f"{self._base_url}/api/tags", timeout=1.0),  # noqa: ASYNC210
            )

            latency_ms = (time.monotonic() - start_time) * 1000

            if response.status_code == 200:
                return ServerHealth(
                    is_healthy=True,
                    model_loaded=len(self._available_models) > 0,
                    gpu_available=True,
                    gpu_backend=GPUBackend.CUDA,
                    latency_ms=latency_ms,
                )
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
                error_message=f"Ollama not available: {e!s}",
            )

    async def generate(
        self,
        request: LLMRequest,
        model: str | None = None,
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
            msg = "Server not running. Call start() first."
            raise RuntimeError(msg)

        # Use default model if not specified
        model_name = model or self.default_model

        # Verify model is available
        if model_name not in self._available_models:
            msg = f"Model not available: {model_name}. Available: {self._available_models}"
            raise RuntimeError(
                msg,
            )

        start_time = time.monotonic()  # FIX: was time.time(), see start()

        try:
            # Options come from the shared generation policy. This client used
            # to send no num_ctx and no num_gpu, so it loaded the model with
            # the server's default context (131072 where the Ollama app's
            # slider is set high) and forced a reload whenever any other
            # client ran next.
            payload: dict[str, Any] = {
                "model": model_name,
                "prompt": request.prompt,
                "stream": False,
                "options": ollama_options(
                    num_predict=request.max_tokens,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    stop=request.stop_sequences,
                ),
            }

            # Run blocking HTTP call in thread pool to avoid blocking event loop
            # FIX: removed a redundant second `import asyncio` here too
            # (already imported at module top, and again pointlessly local
            # to health_check() before this fix).
            # Was a hard-coded 15 s. On CPU-only hardware a small model emits
            # single-digit tokens per second, so any answer of real length
            # exceeded that and surfaced as a timeout rather than a slow
            # success. Resolved once here rather than inside the lambda so the
            # value this call actually used is a plain local - stable if the
            # environment changes mid-flight, and visible to static analysis.
            request_timeout_s = generate_timeout()
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                self._executor,
                lambda: requests.post(  # noqa: ASYNC210
                    f"{self._base_url}/api/generate",
                    json=payload,
                    timeout=request_timeout_s,
                ),
            )

            latency_ms = (time.monotonic() - start_time) * 1000

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
                context_fits(
                    data.get("prompt_eval_count"),
                    request.max_tokens,
                    source="OllamaServer",
                )

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
            msg = f"Generation failed: {response.status_code} - {response.text}"
            raise RuntimeError(msg)

        except requests.RequestException as e:
            msg = f"Generation error: {e!s}"
            raise RuntimeError(msg) from e

    def select_model_for_task(self, complexity: str) -> str:  # noqa: ARG002
        """Return the model to use for a task.

        NOTE (fixed docstring - was misleading): the `complexity` parameter
        is currently NOT used to route between models - `OLLAMA_MODELS`
        has exactly one entry (gemma3:4b, chosen as the best fit for 4GB
        VRAM), so there is nothing to route between yet. The original
        docstring's doctest examples implied `"simple"` vs `"complex"`
        selected different models, which was never true and would mislead
        a caller into thinking this does more than it does. The parameter
        is kept in the signature for forward API compatibility (adding
        real complexity-based routing later won't be a breaking change),
        but currently always returns the same env-var-or-default model
        regardless of what's passed in.

        Args:
            complexity: Reserved for future use; currently ignored.

        Returns:
            Model name to use - the OLLAMA_MODEL env var override if set,
            otherwise "gemma3:4b".

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
            except Exception:  # nosec B112
                logging.getLogger(__name__).debug("Benchmark sample failed", exc_info=True)
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
        self._executor.shutdown(wait=False)

    def is_running(self) -> bool:
        """Check if server client is active."""
        return self._is_running

    def get_available_models(self) -> list[str]:
        """Get list of available models."""
        return self._available_models.copy()

    def get_model_config(self, model: str) -> OllamaModelConfig | None:
        """Get configuration for a model.

        Args:
            model: Model name

        Returns:
            Model configuration or None if not found

        """
        return OLLAMA_MODELS.get(model)
