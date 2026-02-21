"""
Unified LLM Client

Provides a unified interface for local and cloud LLM providers.
Handles routing, fallback, and error recovery.
"""

from typing import Optional

from Agent_Guru.reasoning.llm.local_server import LocalLLMServer
from Agent_Guru.reasoning.llm.models import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
)


class LLMClient:
    """
    Unified client for local and cloud LLM providers.

    Provides a single interface for inference with automatic fallback.

    Example:
        >>> client = LLMClient(local_server=server)
        >>> request = LLMRequest(prompt="Hello, world!")
        >>> response = await client.generate(request)
        >>> print(response.text)
    """

    def __init__(
        self,
        local_server: Optional[LocalLLMServer] = None,
        prefer_local: bool = True,
    ):
        """Initialize LLM client.

        Args:
            local_server: Local llama.cpp server instance
            prefer_local: Whether to prefer local over cloud
        """
        self.local_server = local_server
        self.prefer_local = prefer_local

    async def generate(
        self, request: LLMRequest, provider: Optional[LLMProvider] = None
    ) -> LLMResponse:
        """Generate text using specified or preferred provider.

        Args:
            request: LLM request
            provider: Specific provider to use (None = auto-select)

        Returns:
            LLM response

        Raises:
            RuntimeError: If all providers fail
        """
        # Use specified provider if given
        if provider == LLMProvider.LOCAL:
            return await self._generate_local(request)

        # Auto-select based on preference
        if self.prefer_local and self.local_server:
            try:
                return await self._generate_local(request)
            except Exception:
                # Fallback to cloud would go here
                raise

        raise RuntimeError("No LLM provider available")

    async def _generate_local(self, request: LLMRequest) -> LLMResponse:
        """Generate using local server."""
        if not self.local_server:
            raise RuntimeError("Local server not configured")

        return await self.local_server.generate(request)
