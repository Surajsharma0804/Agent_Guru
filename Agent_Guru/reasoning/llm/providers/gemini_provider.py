"""
Google Gemini LLM Provider

Implements Google Gemini Pro integration with:
- API key management from environment variables
- Rate limiting (60 RPM, 90K TPM default)
- Circuit breaker for failure handling
- Retry logic with exponential backoff

Performance Target: <400ms for 512 tokens
"""

import os
import time
from typing import Any, Optional

try:
    import google.generativeai as genai  # type: ignore[import]
    from google.api_core import exceptions as google_exceptions  # type: ignore[import]
    _GENAI_AVAILABLE = True
except ImportError:
    genai = None  # type: ignore[assignment]
    google_exceptions = None  # type: ignore[assignment]
    _GENAI_AVAILABLE = False

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.providers.base import BaseLLMProvider, ProviderConfig


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini Pro provider.

    Uses Google Generative AI SDK with async support for optimal performance.

    Example:
        >>> config = ProviderConfig(api_key=os.getenv("GEMINI_API_KEY"))
        >>> provider = GeminiProvider(config)
        >>> request = LLMRequest(prompt="Hello, world!")
        >>> response = await provider.generate(request)
        >>> print(response.text)
    """

    def __init__(
        self,
        config: Optional[ProviderConfig] = None,
        model: str = "gemini-2.5-flash",  # Gemini 2.5 Flash (250K tokens available)
    ):
        """Initialize Gemini provider.

        Args:
            config: Provider configuration (if None, loads from env)
            model: Gemini model to use

        Raises:
            ValueError: If API key not found
        """
        if config is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError(
                    "GEMINI_API_KEY environment variable not set. "
                    "Set it with: export GEMINI_API_KEY=your-key-here"
                )
            config = ProviderConfig(
                api_key=api_key,
                rate_limit_rpm=60,  # Gemini default
                rate_limit_tpm=90000,  # Gemini default
            )

        super().__init__(config)
        self.model_name = model

        # Configure Gemini API
        genai.configure(api_key=config.api_key)
        self.model = genai.GenerativeModel(model)

    def get_provider_type(self) -> LLMProvider:
        """Get provider type."""
        return LLMProvider.GEMINI

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text using Gemini API.

        Args:
            request: LLM request

        Returns:
            LLM response

        Raises:
            google_exceptions.GoogleAPIError: On Gemini API errors
            google_exceptions.ResourceExhausted: On rate limit exceeded
        """
        start_time = time.perf_counter()

        try:
            # Configure generation parameters
            generation_config = genai.types.GenerationConfig(
                temperature=request.temperature,
                top_p=request.top_p,
                max_output_tokens=request.max_tokens,
                stop_sequences=request.stop_sequences if request.stop_sequences else None,
            )

            # Make API call (async)
            response = await self.model.generate_content_async(
                request.prompt,
                generation_config=generation_config,
            )

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract response text
            text = response.text if response.text else ""

            # Determine finish reason
            finish_reason = "stop"
            if hasattr(response, "prompt_feedback") and response.prompt_feedback:
                if response.prompt_feedback.block_reason:
                    finish_reason = "error"

            # Estimate tokens (Gemini doesn't always provide token counts)
            tokens_generated = len(text.split())  # Rough estimate
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                tokens_generated = response.usage_metadata.candidates_token_count

            return LLMResponse(
                text=text,
                provider=LLMProvider.GEMINI,
                latency_ms=latency_ms,
                tokens_generated=tokens_generated,
                finish_reason=finish_reason,
                metadata={
                    "model": self.model_name,
                    "prompt_tokens": response.usage_metadata.prompt_token_count
                    if hasattr(response, "usage_metadata") and response.usage_metadata
                    else len(request.prompt.split()),
                    "total_tokens": response.usage_metadata.total_token_count
                    if hasattr(response, "usage_metadata") and response.usage_metadata
                    else len(request.prompt.split()) + tokens_generated,
                },
            )

        except google_exceptions.ResourceExhausted as e:
            # Rate limit exceeded - will be retried by base class
            raise RuntimeError(f"Gemini rate limit exceeded: {e}") from e

        except google_exceptions.DeadlineExceeded as e:
            # Timeout - will be retried by base class
            raise TimeoutError(f"Gemini request timeout: {e}") from e

        except google_exceptions.ServiceUnavailable as e:
            # Service unavailable - will be retried by base class
            raise RuntimeError(f"Gemini service unavailable: {e}") from e

        except google_exceptions.GoogleAPIError as e:
            # API error - will be retried by base class
            raise RuntimeError(f"Gemini API error: {e}") from e

        except Exception as e:
            # Unexpected error
            raise RuntimeError(f"Gemini unexpected error: {e}") from e
