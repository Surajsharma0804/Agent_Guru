"""
Anthropic Claude provider adapter.

Translates between the unified LLM Runtime API and the Anthropic Messages API,
supporting chat completions, streaming, and function/tool calling.

Author: Agent Guru Team
Date: 2026-03-18
Version: 1.0.0
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, Optional, Union

from Agent_Guru.llm.models import (
    AnthropicConfig,
    CompletionRequest,
    CompletionResponse,
    ModelProvider,
    StreamChunk,
    TokenUsage,
)
from Agent_Guru.llm.providers.base import ProviderAdapter

# Pricing per 1K tokens (input / output)
_PRICING: dict[str, dict[str, float]] = {
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "claude-2": {"input": 0.008, "output": 0.024},
}


class AnthropicAdapter(ProviderAdapter):
    """
    Adapter for the Anthropic Claude API.

    Supports:
    - Chat completions (non-streaming and streaming)
    - Tool / function calling (translated to Anthropic tool format)

    Does NOT support:
    - Embeddings (Anthropic does not provide an embeddings API)

    Example:
        >>> config = AnthropicConfig(api_key="sk-ant-...")
        >>> adapter = AnthropicAdapter(config)
        >>> response = await adapter.complete(request)
    """

    def __init__(self, config: AnthropicConfig) -> None:
        self.config = config
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        """Lazy-initialize the Anthropic async client."""
        if self._client is None:
            import anthropic  # type: ignore[import]

            self._client = anthropic.AsyncAnthropic(api_key=self.config.api_key)
        return self._client

    # ------------------------------------------------------------------
    # Message format helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_anthropic_messages(
        messages: list,
    ) -> tuple[Optional[str], list]:
        """
        Split messages into system prompt + user/assistant turns.

        Anthropic requires the system prompt as a separate parameter.
        Returns (system_prompt, anthropic_messages).
        """
        system_prompt: Optional[str] = None
        anthropic_messages: list = []

        for m in messages:
            if m.role == "system":
                system_prompt = m.content
            else:
                anthropic_messages.append({"role": m.role, "content": m.content})

        return system_prompt, anthropic_messages

    @staticmethod
    def _to_anthropic_tools(functions: list) -> list:
        """Translate FunctionDefinition list to Anthropic tool format."""
        return [
            {
                "name": f.name,
                "description": f.description,
                "input_schema": f.parameters,
            }
            for f in functions
        ]

    # ------------------------------------------------------------------
    # ProviderAdapter interface
    # ------------------------------------------------------------------

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a non-streaming chat completion via Anthropic."""
        client = self._get_client()
        system_prompt, anthropic_messages = self._to_anthropic_messages(request.messages)

        # Build prompt in Anthropic v0.8 format (HUMAN_PROMPT / AI_PROMPT)
        import anthropic as _anthropic  # type: ignore[import]
        prompt_parts: list[str] = []
        if system_prompt:
            prompt_parts.append(system_prompt)
        for m in anthropic_messages:
            if m["role"] == "user":
                prompt_parts.append(f"{_anthropic.HUMAN_PROMPT} {m['content']}")
            else:
                prompt_parts.append(f"{_anthropic.AI_PROMPT} {m['content']}")
        prompt_parts.append(_anthropic.AI_PROMPT)
        full_prompt = "\n".join(prompt_parts)

        response = await client.completions.acreate(
            model=request.model,
            prompt=full_prompt,
            max_tokens_to_sample=request.max_tokens or 1024,
        )

        content = response.completion or ""

        return CompletionResponse(
            content=content,
            model=request.model,
            provider=ModelProvider.ANTHROPIC,
            finish_reason=response.stop_reason or "stop",
            usage=TokenUsage(
                prompt_tokens=0,
                completion_tokens=len(content.split()),
                total_tokens=len(content.split()),
                estimated_cost=0.0,
            ),
            function_call=None,
            latency_ms=0.0,
            timestamp=datetime.now(tz=timezone.utc),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Execute a streaming chat completion via Anthropic."""
        client = self._get_client()
        system_prompt, anthropic_messages = self._to_anthropic_messages(request.messages)

        kwargs: dict[str, Any] = {}
        if system_prompt:
            kwargs["system"] = system_prompt
        if request.functions:
            kwargs["tools"] = self._to_anthropic_tools(request.functions)

        async with client.messages.stream(
            model=request.model,
            messages=anthropic_messages,
            max_tokens=request.max_tokens or 1024,
            temperature=request.temperature,
            **kwargs,
        ) as stream:
            async for text in stream.text_stream:
                yield StreamChunk(content=text, finish_reason=None)

        # Final chunk with stop reason
        yield StreamChunk(content="", finish_reason="stop")

    async def embed(
        self, text: Union[str, list[str]], model: str
    ) -> list[list[float]]:
        """Anthropic does not provide an embeddings API."""
        raise NotImplementedError(
            "Anthropic does not provide an embeddings API. "
            "Use OpenAI or Ollama for embeddings."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _calculate_cost(
        self, input_tokens: int, output_tokens: int, model: str
    ) -> float:
        """Calculate estimated cost based on published pricing."""
        for prefix, prices in _PRICING.items():
            if model.startswith(prefix):
                return (input_tokens / 1000) * prices["input"] + (
                    output_tokens / 1000
                ) * prices["output"]
        return 0.0
