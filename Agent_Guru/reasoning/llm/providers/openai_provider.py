"""
OpenAI LLM Provider

Implements OpenAI GPT-4 Turbo integration with:
- API key management from environment variables
- Rate limiting (60 RPM, 90K TPM default)
- Circuit breaker for failure handling
- Retry logic with exponential backoff

Performance Target: <400ms for 512 tokens
"""

import os
import time
from typing import Optional

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.providers.base import BaseLLMProvider, ProviderConfig


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI GPT-4 Turbo provider.

    Uses OpenAI API with async client for optimal performance.

    Example:
        >>> config = ProviderConfig(api_key=os.getenv("OPENAI_API_KEY"))
        >>> provider = OpenAIProvider(config)
        >>> request = LLMRequest(prompt="Hello, world!")
        >>> response = await provider.generate(request)
        >>> print(response.text)
    """

    def __init__(
        self,
        config: Optional[ProviderConfig] = None,
        model: str = "gpt-4-turbo-preview",
    ):
        """Initialize OpenAI provider.

        Args:
            config: Provider configuration (if None, loads from env)
            model: OpenAI model to use

        Raises:
            ValueError: If API key not found
        """
        if config is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY environment variable not set. "
                    "Set it with: export OPENAI_API_KEY=your-key-here"
                )
            config = ProviderConfig(
                api_key=api_key,
                rate_limit_rpm=60,  # OpenAI default
                rate_limit_tpm=90000,  # OpenAI default
            )

        super().__init__(config)
        self.model = model
        self.client = AsyncOpenAI(api_key=config.api_key)

    def get_provider_type(self) -> LLMProvider:
        """Get provider type."""
        return LLMProvider.OPENAI

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text using OpenAI API.

        Args:
            request: LLM request

        Returns:
            LLM response

        Raises:
            APIError: On OpenAI API errors
            RateLimitError: On rate limit exceeded
            APIConnectionError: On connection errors
            Timeout: On request timeout
        """
        start_time = time.perf_counter()

        try:
            # Make API call
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": request.prompt}],
                temperature=request.temperature,
                top_p=request.top_p,
                max_tokens=request.max_tokens,
                stop=request.stop_sequences if request.stop_sequences else None,
                stream=False,  # Streaming not supported in this version
            )

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract response
            choice = completion.choices[0]
            text = choice.message.content or ""
            finish_reason = choice.finish_reason or "stop"

            # Map OpenAI finish reasons to our format
            if finish_reason == "length":
                finish_reason = "length"
            elif finish_reason in ["stop", "end_turn"]:
                finish_reason = "stop"
            else:
                finish_reason = "error"

            return LLMResponse(
                text=text,
                provider=LLMProvider.OPENAI,
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
            raise RuntimeError(f"OpenAI rate limit exceeded: {e}") from e

        except APITimeoutError as e:
            # Timeout - will be retried by base class (must be before APIConnectionError)
            raise TimeoutError(f"OpenAI request timeout: {e}") from e

        except APIConnectionError as e:
            # Connection error - will be retried by base class
            raise RuntimeError(f"OpenAI connection error: {e}") from e

        except APIError as e:
            # API error - will be retried by base class
            raise RuntimeError(f"OpenAI API error: {e}") from e

        except Exception as e:
            # Unexpected error
            raise RuntimeError(f"OpenAI unexpected error: {e}") from e
