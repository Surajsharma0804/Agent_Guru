"""
Anthropic LLM Provider

Implements Anthropic Claude 3.5 Sonnet integration with:
- API key management from environment variables
- Rate limiting (60 RPM, 90K TPM default)
- Circuit breaker for failure handling
- Retry logic with exponential backoff

Performance Target: <400ms for 512 tokens
"""

import os
import time
from typing import Optional

from anthropic import (
    APIConnectionError,
    APIError,
    APIStatusError,
    AsyncAnthropic,
    RateLimitError,
)

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.providers.base import BaseLLMProvider, ProviderConfig


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude 3.5 Sonnet provider.

    Uses Anthropic API with async client for optimal performance.

    Example:
        >>> config = ProviderConfig(api_key=os.getenv("ANTHROPIC_API_KEY"))
        >>> provider = AnthropicProvider(config)
        >>> request = LLMRequest(prompt="Hello, world!")
        >>> response = await provider.generate(request)
        >>> print(response.text)
    """

    def __init__(
        self,
        config: Optional[ProviderConfig] = None,
        model: str = "claude-3-5-sonnet-20241022",
    ):
        """Initialize Anthropic provider.

        Args:
            config: Provider configuration (if None, loads from env)
            model: Anthropic model to use

        Raises:
            ValueError: If API key not found
        """
        if config is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY environment variable not set. "
                    "Set it with: export ANTHROPIC_API_KEY=your-key-here"
                )
            config = ProviderConfig(
                api_key=api_key,
                rate_limit_rpm=60,  # Anthropic default
                rate_limit_tpm=90000,  # Anthropic default
            )

        super().__init__(config)
        self.model = model
        self.client = AsyncAnthropic(api_key=config.api_key)

    def get_provider_type(self) -> LLMProvider:
        """Get provider type."""
        return LLMProvider.ANTHROPIC

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text using Anthropic API.

        Args:
            request: LLM request

        Returns:
            LLM response

        Raises:
            APIError: On Anthropic API errors
            RateLimitError: On rate limit exceeded
            APIConnectionError: On connection errors
            APIStatusError: On HTTP status errors
        """
        start_time = time.perf_counter()

        try:
            # Make API call
            message = await self.client.messages.create(  # type: ignore[attr-defined]
                model=self.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                messages=[{"role": "user", "content": request.prompt}],
                stop_sequences=request.stop_sequences if request.stop_sequences else None,
            )

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract response text
            text = ""
            for content_block in message.content:
                if content_block.type == "text":
                    text += content_block.text

            # Map Anthropic stop reasons to our format
            finish_reason = "stop"
            if message.stop_reason == "max_tokens":
                finish_reason = "length"
            elif message.stop_reason in ["end_turn", "stop_sequence"]:
                finish_reason = "stop"
            else:
                finish_reason = "error"

            return LLMResponse(
                text=text,
                provider=LLMProvider.ANTHROPIC,
                latency_ms=latency_ms,
                tokens_generated=message.usage.output_tokens,
                finish_reason=finish_reason,
                metadata={
                    "model": self.model,
                    "prompt_tokens": message.usage.input_tokens,
                    "total_tokens": message.usage.input_tokens + message.usage.output_tokens,
                    "stop_reason": message.stop_reason,
                },
            )

        except RateLimitError as e:
            # Rate limit exceeded - will be retried by base class
            raise RuntimeError(f"Anthropic rate limit exceeded: {e}") from e

        except APIConnectionError as e:
            # Connection error - will be retried by base class
            raise RuntimeError(f"Anthropic connection error: {e}") from e

        except APIStatusError as e:
            # HTTP status error - will be retried by base class
            raise RuntimeError(f"Anthropic status error: {e}") from e

        except APIError as e:
            # API error - will be retried by base class
            raise RuntimeError(f"Anthropic API error: {e}") from e

        except Exception as e:
            # Unexpected error
            raise RuntimeError(f"Anthropic unexpected error: {e}") from e
