"""
OpenAI provider adapter.

Translates between the unified LLM Runtime API and the OpenAI API,
supporting chat completions, streaming, function calling, and embeddings.

Author: Agent Guru Team
Date: 2026-03-18
Version: 1.0.0
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from Agent_Guru.llm.models import (
    CompletionRequest,
    CompletionResponse,
    ModelProvider,
    OpenAIConfig,
    StreamChunk,
    TokenUsage,
)
from Agent_Guru.llm.providers.base import ProviderAdapter
from Agent_Guru.security.embedding_auth import RETRIEVAL_THRESHOLD, verify_embedding

# Pricing per 1K tokens (prompt / completion)
_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-32k": {"prompt": 0.06, "completion": 0.12},
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
    "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
    "text-embedding-ada-002": {"prompt": 0.0001, "completion": 0.0},
}


class OpenAIAdapter(ProviderAdapter):
    """
    Adapter for the OpenAI API.

    Supports:
    - Chat completions (non-streaming and streaming)
    - Function / tool calling
    - Embeddings

    Example:
        >>> config = OpenAIConfig(api_key="sk-...")
        >>> adapter = OpenAIAdapter(config)
        >>> response = await adapter.complete(request)
    """

    def __init__(self, config: OpenAIConfig) -> None:
        self.config = config
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        """Lazy-initialize the AsyncOpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI  # type: ignore[import]

            kwargs: Dict[str, Any] = {"api_key": self.config.api_key}
            if self.config.base_url:
                kwargs["base_url"] = self.config.base_url
            if self.config.organization:
                kwargs["organization"] = self.config.organization
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a non-streaming chat completion."""
        client = self._get_client()

        openai_messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
        ]

        kwargs: Dict[str, Any] = {}
        if request.functions:
            kwargs["functions"] = [
                {"name": f.name, "description": f.description, "parameters": f.parameters}
                for f in request.functions
            ]
            if request.function_call is not None:
                kwargs["function_call"] = request.function_call

        response = await client.chat.completions.create(
            model=request.model,
            messages=openai_messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            **kwargs,
        )

        choice = response.choices[0]

        function_call: Optional[Dict[str, Any]] = None
        if choice.message.function_call:
            function_call = {
                "name": choice.message.function_call.name,
                "arguments": choice.message.function_call.arguments,
            }

        usage = response.usage
        cost = self._calculate_cost(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            model=request.model,
        )

        return CompletionResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=ModelProvider.OPENAI,
            finish_reason=choice.finish_reason or "stop",
            usage=TokenUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                estimated_cost=cost,
            ),
            function_call=function_call,
            latency_ms=0.0,  # Set by LLMRuntime
            timestamp=datetime.now(),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Execute a streaming chat completion."""
        client = self._get_client()

        openai_messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
        ]

        kwargs: Dict[str, Any] = {}
        if request.functions:
            kwargs["functions"] = [
                {"name": f.name, "description": f.description, "parameters": f.parameters}
                for f in request.functions
            ]

        stream = await client.chat.completions.create(
            model=request.model,
            messages=openai_messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True,
            **kwargs,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            function_call: Optional[Dict[str, Any]] = None
            if delta.function_call:
                function_call = {
                    "name": delta.function_call.name,
                    "arguments": delta.function_call.arguments,
                }

            yield StreamChunk(
                content=delta.content or "",
                finish_reason=choice.finish_reason,
                function_call=function_call,
            )

    async def embed(
        self, text: Union[str, List[str]], model: str
    ) -> List[List[float]]:
        """Generate embeddings using OpenAI's embedding models."""
        client = self._get_client()

        if isinstance(text, str):
            text = [text]

        response = await client.embeddings.create(model=model, input=text)
        return [item.embedding for item in response.data]

    def find_similar(
        self,
        query_embedding: List[float],
        candidate_embeddings: List[List[float]],
        threshold: float = RETRIEVAL_THRESHOLD,
    ) -> List[int]:
        """Return indices of *candidate_embeddings* that are similar to *query_embedding*.

        Uses :func:`~Agent_Guru.security.embedding_auth.verify_embedding` to
        enforce the retrieval threshold (CWE-200/284/20 fix).

        Args:
            query_embedding: Query embedding vector.
            candidate_embeddings: List of candidate embedding vectors.
            threshold: Minimum cosine similarity for a match.
                Defaults to :data:`~Agent_Guru.security.embedding_auth.RETRIEVAL_THRESHOLD` (0.85).

        Returns:
            List of indices (into *candidate_embeddings*) that meet the threshold.
        """
        import numpy as np

        q = np.array(query_embedding, dtype=np.float32)
        return [
            i
            for i, cand in enumerate(candidate_embeddings)
            if verify_embedding(q, np.array(cand, dtype=np.float32), threshold)
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _calculate_cost(
        self, prompt_tokens: int, completion_tokens: int, model: str
    ) -> float:
        """Calculate estimated cost based on published pricing."""
        for prefix, prices in _PRICING.items():
            if model.startswith(prefix):
                return (prompt_tokens / 1000) * prices["prompt"] + (
                    completion_tokens / 1000
                ) * prices["completion"]
        return 0.0
