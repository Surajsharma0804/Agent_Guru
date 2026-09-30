"""Ollama LLM Provider.

Provides local LLM inference using Ollama server.
Supports models like Mistral, Qwen, Llama, etc.

Performance Targets:
- Inference latency: <400ms for 512 tokens (95th percentile)
- GPU utilization: >80% during inference
- No API key required (local inference)

Implementation Notes:
- Uses aiohttp (truly async, cancellable) instead of requests in executor.
  The requests-in-executor pattern blocks the thread even after asyncio
  cancellation, causing event-loop shutdown hangs in tests.
- connect_timeout=2s: fail fast when Ollama is not running
- read_timeout=config.timeout_seconds: allow long inference when it IS running
"""

import time
from typing import Any

import aiohttp

from Agent_Guru.reasoning.llm.generation import (
    OLLAMA_THINK,
    context_fits,
    ollama_model,
    ollama_options,
)
from Agent_Guru.reasoning.llm.models import LLMProvider, LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.providers.base import BaseLLMProvider, ProviderConfig


class OllamaProviderConfig(ProviderConfig):
    """Configuration for Ollama provider."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 11434,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Ollama config.

        Args:
            host: Ollama server host
            port: Ollama server port
            model: Model name to use. Defaults to the one every other Ollama
                client uses (OLLAMA_MODEL, else the shared default). It was a
                fixed "gemma3:4b" that ignored OLLAMA_MODEL, so after the user
                changed models this client alone asked for the old one: a 404
                if it was removed, and if it was still pulled, Ollama swapped
                the two models in and out of a 4 GB GPU on every turn.
            **kwargs: Additional config parameters passed to ProviderConfig

        """
        # Ollama doesn't need an API key, but base class requires one.
        super().__init__(api_key="local", **kwargs)
        self.host = host
        self.port = port
        self.model = model or ollama_model()
        self.base_url = f"http://{host}:{port}"

class OllamaProvider(BaseLLMProvider):
    """Ollama LLM provider for local inference.

    The model comes from generation.ollama_model(), shared with every other
    Ollama client.

    Example:
        >>> config = OllamaProviderConfig()
        >>> provider = OllamaProvider(config)
        >>> request = LLMRequest(prompt="What is the time?")
        >>> response = await provider.generate(request)

    """

    # Short connect timeout so tests fail fast when Ollama is not running.
    _CONNECT_TIMEOUT_S: float = 2.0

    def __init__(self, config: OllamaProviderConfig) -> None:
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
        """Generate text using Ollama API (fully async via aiohttp).

        Using aiohttp instead of requests-in-executor ensures that asyncio
        cancellation (from asyncio.wait_for) propagates correctly and does
        not leave a blocking thread alive after the timeout fires.

        Args:
            request: LLM request

        Returns:
            LLM response

        Raises:
            RuntimeError: If Ollama server is not available or returns an error

        """
        start_time = time.perf_counter()

        # Options come from the shared generation policy. This client used to
        # send num_gpu but no num_ctx, so it ran at whatever context the
        # server defaulted to (131072 on a machine where the Ollama app's
        # slider was set high). It also disagreed with the voice client,
        # which made Ollama reload the model between their requests.
        # think: a thinking model otherwise spends num_predict on reasoning
        # this client never reads and returns an empty "response".
        payload: dict[str, Any] = {
            "model": self.ollama_config.model,
            "prompt": request.prompt,
            "stream": False,
            "think": OLLAMA_THINK,
            "options": ollama_options(
                num_predict=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                stop=request.stop_sequences,
            ),
        }

        # aiohttp timeout: short connect (fail fast offline), long read (allow inference)
        timeout = aiohttp.ClientTimeout(
            connect=self._CONNECT_TIMEOUT_S,
            total=self.config.timeout_seconds,
        )

        try:
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.post(
                    f"{self.ollama_config.base_url}/api/generate",
                    json=payload,
                ) as response,
            ):
                latency_ms = (time.perf_counter() - start_time) * 1000

                if response.status == 200:
                    data = await response.json()

                    text: str = data.get("response", "")

                    finish_reason = "stop"
                    if data.get("done_reason") == "length":
                        finish_reason = "length"
                    elif not data.get("done", False):
                        finish_reason = "error"

                    tokens_generated: int = data.get("eval_count", len(text.split()))
                    context_fits(
                        data.get("prompt_eval_count"),
                        request.max_tokens,
                        source="OllamaProvider",
                    )

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
                body = await response.text()
                msg = f"Ollama generation failed: {response.status} - {body}"
                raise RuntimeError(msg)

        except aiohttp.ClientConnectorError as e:
            msg = f"Ollama server not reachable at {self.ollama_config.base_url}: {e}"
            raise RuntimeError(
                msg,
            ) from e

    async def health_check(self) -> bool:
        """Check if Ollama server is available.

        Returns:
            True if server is healthy

        """
        try:
            timeout = aiohttp.ClientTimeout(connect=2.0, total=3.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.ollama_config.base_url}/api/tags") as response:
                    return response.status == 200

        except Exception:
            return False
