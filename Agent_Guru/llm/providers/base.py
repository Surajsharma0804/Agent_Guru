"""
Abstract base class for LLM provider adapters.

All provider adapters must implement this interface to ensure
cross-provider compatibility.

Author: Agent Guru Team
Date: 2026-03-18
Version: 1.0.0
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Union

from Agent_Guru.llm.models import CompletionRequest, CompletionResponse, StreamChunk


class ProviderAdapter(ABC):
    """Abstract base class for all LLM provider adapters."""

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """
        Execute a non-streaming completion request.

        Args:
            request: Completion request in unified format.

        Returns:
            CompletionResponse in unified format.
        """
        ...

    @abstractmethod
    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """
        Execute a streaming completion request.

        Args:
            request: Completion request in unified format.

        Yields:
            StreamChunk for each token/chunk received.
        """
        ...

    @abstractmethod
    async def embed(
        self, text: Union[str, List[str]], model: str
    ) -> List[List[float]]:
        """
        Generate embeddings for text.

        Args:
            text: Single string or list of strings to embed.
            model: Embedding model name.

        Returns:
            List of embedding vectors (one per input string).
        """
        ...
