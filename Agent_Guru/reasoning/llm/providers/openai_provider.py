"""OpenAI LLM Provider.

Provides OpenAI GPT API integration with circuit breaker, rate limiting, and retry logic.

Performance Targets:
- Inference latency: <2s for 512 tokens (95th percentile)
- Rate limits: 60 RPM, 90,000 TPM (configurable)
- Circuit breaker: Opens after 5 consecutive failures

Implementation Notes:
- Uses openai SDK (async native)
- Supports GPT-4 Turbo (default), GPT-4, GPT-3.5 Turbo
- Handles rate limiting, connection errors, and API errors
- Circuit breaker prevents cascading failures
"""

import os
import time
from typing import Any

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.providers.base import BaseLLMProvider, ProviderConfig


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT LLM provider.

    Default model: gpt-4-turbo-preview (best quality/speed balance)

    Example:
        >>> config = ProviderConfig(api_key="sk-...")
        >>> provider = OpenAIProvider(config)
        >>> request = LLMRequest(prompt="What is the time?")
        >>> response = await provider.generate(request)

    """

    def __init__(
        self,
        config: ProviderConfig | None = None,
        model: str = "gpt-4-turbo-preview",
    ) -> None:
        """Initialize OpenAI provider.

        Args:
            config: Provider configuration. If None, loads from OPENAI_API_KEY env var.
            model: GPT model to use.

        Raises:
            ValueError: If no API key is provided and OPENAI_API_KEY is not set.

        """
        if config is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                msg = "OPENAI_API_KEY environment variable not set"
                raise ValueError(msg)
            config = ProviderConfig(api_key=api_key)

        super().__init__(config)
        self.model = model
        # config.timeout_seconds was never given to the SDK, which then used
        # its own 600 s read timeout and 2 retries of its own. BaseLLMProvider
        # does not wrap calls in asyncio.wait_for, on the assumption that
        # _generate_impl enforces the deadline (the Ollama provider does, with
        # aiohttp), so one stalled request could hold a turn for 10 minutes,
        # 3 SDK attempts per base retry. The SDK now stops at the configured
        # deadline and leaves retrying to generate()'s loop.
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            timeout=config.timeout_seconds,
            max_retries=0,
        )

    def get_provider_type(self) -> LLMProvider:
        """Get provider type."""
        return LLMProvider.OPENAI

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """Generate text using OpenAI GPT API.

        Args:
            request: LLM request

        Returns:
            LLM response

        Raises:
            RuntimeError: If API call fails

        """
        start_time = time.perf_counter()

        try:
            # Build API request
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": [{"role": "user", "content": request.prompt}],
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "top_p": request.top_p,
            }

            if request.stop_sequences:
                kwargs["stop"] = request.stop_sequences

            # Make API call
            completion = await self.client.chat.completions.create(**kwargs)

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract response
            choice = completion.choices[0]
            text = choice.message.content or ""
            finish_reason = choice.finish_reason or "stop"

            # Extract token counts
            usage = completion.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0

            return LLMResponse(
                text=text,
                provider=LLMProvider.OPENAI,
                latency_ms=latency_ms,
                tokens_generated=completion_tokens,
                finish_reason=finish_reason,
                metadata={
                    "model": self.model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "finish_reason": finish_reason,
                },
            )

        # Every openai exception is translated to RuntimeError, which is what
        # this method's own docstring promises and what BaseLLMProvider and
        # the failover router are written against. Only RateLimitError was
        # translated before, so a refused connection or an HTTP 500 escaped as
        # a raw openai.* exception that no caller was catching.
        except RateLimitError as e:
            msg = f"OpenAI rate limit exceeded: {e}"
            raise RuntimeError(msg) from e
        except APITimeoutError as e:
            # A timeout surfaces as the BUILTIN TimeoutError, not RuntimeError.
            # OpenAI's APITimeoutError is NOT a subclass of it (verified),
            # so BaseLLMProvider.generate()'s retry loop -- written as
            # `except TimeoutError` -- never saw provider timeouts at all.
            # Translating here makes the semantic type available to
            # timeout-aware callers and to that loop.
            msg = f"OpenAI request timeout: {e}"
            raise TimeoutError(msg) from e
        except APIConnectionError as e:
            msg = f"OpenAI connection error: {e}"
            raise RuntimeError(msg) from e
        except APIStatusError as e:
            msg = f"OpenAI status error ({e.status_code}): {e}"
            raise RuntimeError(msg) from e
        except APIError as e:
            msg = f"OpenAI API error: {e}"
            raise RuntimeError(msg) from e
