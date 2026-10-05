"""Anthropic LLM Provider.

Provides Claude API integration with circuit breaker, rate limiting, and retry logic.

Performance Targets:
- Inference latency: <2s for 512 tokens (95th percentile)
- Rate limits: 60 RPM, 90,000 TPM (configurable)
- Circuit breaker: Opens after 5 consecutive failures

Implementation Notes:
- Uses anthropic SDK (async native)
- Supports Claude 3.5 Sonnet (default), Claude 3 Opus, Claude 3 Haiku
- Handles rate limiting, connection errors, and API errors
- Circuit breaker prevents cascading failures
"""

import os
import time
from typing import Any

from anthropic import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    RateLimitError,
)

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.providers.base import BaseLLMProvider, ProviderConfig


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude LLM provider.

    Default model: claude-opus-5-5. The previous default,
    claude-3-5-sonnet-20241022, has been retired.

    Example:
        >>> config = ProviderConfig(api_key="sk-ant-...")
        >>> provider = AnthropicProvider(config)
        >>> request = LLMRequest(prompt="What is the time?")
        >>> response = await provider.generate(request)

    """

    def __init__(
        self,
        config: ProviderConfig | None = None,
        model: str = "claude-opus-5-5",
    ) -> None:
        """Initialize Anthropic provider.

        Args:
            config: Provider configuration. If None, loads from ANTHROPIC_API_KEY env var.
            model: Claude model to use.

        Raises:
            ValueError: If no API key is provided and ANTHROPIC_API_KEY is not set.

        """
        if config is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                msg = "ANTHROPIC_API_KEY environment variable not set"
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
        self.client = AsyncAnthropic(
            api_key=config.api_key,
            timeout=config.timeout_seconds,
            max_retries=0,
        )

    def get_provider_type(self) -> LLMProvider:
        """Get provider type."""
        return LLMProvider.ANTHROPIC

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """Generate text using Anthropic Claude API.

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
                "max_tokens": request.max_tokens,
                "messages": [{"role": "user", "content": request.prompt}],
            }
            # temperature and top_p are not sent. The installed SDK (anthropic
            # 1.x) no longer accepts them and current Claude models reject
            # sampling parameters, so passing them made every request raise
            # TypeError before reaching the network: the provider could not
            # complete a single call, and the retries hid why.

            if request.stop_sequences:
                kwargs["stop_sequences"] = request.stop_sequences

            # Make API call
            message = await self.client.messages.create(**kwargs)

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract text from content blocks
            text_parts = []
            for content_block in message.content:
                if content_block.type == "text":
                    text_parts.append(content_block.text)
            text = "".join(text_parts)

            # Map stop reason
            finish_reason = "stop"
            if message.stop_reason == "max_tokens":
                finish_reason = "length"
            elif message.stop_reason == "stop_sequence":
                finish_reason = "stop"
            elif message.stop_reason == "refusal":
                # A declined request has no text; without this it read as an
                # ordinary empty answer.
                finish_reason = "refusal"

            # Extract token counts
            prompt_tokens = message.usage.input_tokens
            completion_tokens = message.usage.output_tokens
            total_tokens = prompt_tokens + completion_tokens

            return LLMResponse(
                text=text,
                provider=LLMProvider.ANTHROPIC,
                latency_ms=latency_ms,
                tokens_generated=completion_tokens,
                finish_reason=finish_reason,
                metadata={
                    "model": self.model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "stop_reason": message.stop_reason,
                },
            )

        # See the matching note in openai_provider.py: only RateLimitError
        # was translated, so every other anthropic exception escaped as a raw
        # provider type that no caller catches, against a docstring promising
        # RuntimeError.
        except RateLimitError as e:
            msg = f"Anthropic rate limit exceeded: {e}"
            raise RuntimeError(msg) from e
        except APITimeoutError as e:
            # A timeout surfaces as the BUILTIN TimeoutError, not RuntimeError.
            # Anthropic's APITimeoutError is NOT a subclass of it (verified),
            # so BaseLLMProvider.generate()'s retry loop -- written as
            # `except TimeoutError` -- never saw provider timeouts at all.
            # Translating here makes the semantic type available to
            # timeout-aware callers and to that loop.
            msg = f"Anthropic request timeout: {e}"
            raise TimeoutError(msg) from e
        except APIConnectionError as e:
            msg = f"Anthropic connection error: {e}"
            raise RuntimeError(msg) from e
        except APIStatusError as e:
            msg = f"Anthropic status error ({e.status_code}): {e}"
            raise RuntimeError(msg) from e
        except APIError as e:
            msg = f"Anthropic API error: {e}"
            raise RuntimeError(msg) from e
