"""
DeepSeek LLM Provider

Implements DeepSeek integration with:
- API key management from environment variables
- Rate limiting (60 RPM, 90K TPM default)
- Circuit breaker for failure handling
- Retry logic with exponential backoff
- OpenAI-compatible API

Performance Target: <400ms for 512 tokens
"""

import os
import time
from typing import Optional

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.providers.base import BaseLLMProvider, ProviderConfig


class DeepSeekProvider(BaseLLMProvider):
    """
    DeepSeek provider using OpenAI-compatible API.

    Uses OpenAI SDK with custom base URL for DeepSeek API.

    Example:
        >>> config = ProviderConfig(api_key=os.getenv("DEEPSEEK_API_KEY"))
        >>> provider = DeepSeekProvider(config)
        >>> request = LLMRequest(prompt="Hello, world!")
        >>> response = await provider.generate(request)
        >>> print(response.text)
    """

    def __init__(
        self,
        config: Optional[ProviderConfig] = None,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com/v1",  # Added /v1 endpoint
    ):
        """Initialize DeepSeek provider.

        Args:
            config: Provider configuration (if None, loads from env)
            model: DeepSeek model to use
            base_url: DeepSeek API base URL

        Raises:
            ValueError: If API key not found
        """
        if config is None:
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                raise ValueError(
                    "DEEPSEEK_API_KEY environment variable not set. "
                    "Set it with: export DEEPSEEK_API_KEY=your-key-here"
                )
            config = ProviderConfig(
                api_key=api_key,
                rate_limit_rpm=60,  # DeepSeek default
                rate_limit_tpm=90000,  # DeepSeek default
            )

        super().__init__(config)
        self.model = model
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=base_url,
        )

    def get_provider_type(self) -> LLMProvider:
        """Get provider type."""
        return LLMProvider.DEEPSEEK

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text using DeepSeek API.

        Args:
            request: LLM request

        Returns:
            LLM response

        Raises:
            APIError: On DeepSeek API errors
            RateLimitError: On rate limit exceeded
            APIConnectionError: On connection errors
            APITimeoutError: On request timeout
        """
        start_time = time.perf_counter()

        try:
            # Make API call (OpenAI-compatible)
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": request.prompt}],
                temperature=request.temperature,
                top_p=request.top_p,
                max_tokens=request.max_tokens,
                stop=request.stop_sequences if request.stop_sequences else None,
                stream=False,
            )

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract response
            choice = completion.choices[0]
            text = choice.message.content or ""
            finish_reason = choice.finish_reason or "stop"

            # Map finish reasons to our format
            if finish_reason == "length":
                finish_reason = "length"
            elif finish_reason in ["stop", "end_turn"]:
                finish_reason = "stop"
            else:
                finish_reason = "error"

            return LLMResponse(
                text=text,
                provider=LLMProvider.DEEPSEEK,
                latency_ms=latency_ms,
                tokens_generated=completion.usage.completion_tokens
                if completion.usage
                else len(text.split()),
                finish_reason=finish_reason,
                metadata={
                    "model": self.model,
                    "prompt_tokens": completion.usage.prompt_tokens if completion.usage else 0,
                    "total_tokens": completion.usage.total_tokens if completion.usage else 0,
                },
            )

        except RateLimitError as e:
            # Rate limit exceeded - will be retried by base class
            raise RuntimeError(f"DeepSeek rate limit exceeded: {e}") from e

        except APITimeoutError as e:
            # Timeout - will be retried by base class (must be before APIConnectionError)
            raise TimeoutError(f"DeepSeek request timeout: {e}") from e

        except APIConnectionError as e:
            # Connection error - will be retried by base class
            raise RuntimeError(f"DeepSeek connection error: {e}") from e

        except APIError as e:
            # API error - will be retried by base class
            raise RuntimeError(f"DeepSeek API error: {e}") from e

        except Exception as e:
            # Unexpected error
            raise RuntimeError(f"DeepSeek unexpected error: {e}") from e
