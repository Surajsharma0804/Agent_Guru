"""
Unified LLM Runtime Interface.

The main entry point for all LLM operations across providers.
Orchestrates context management, token counting, error handling,
and performance monitoring.

Performance:
    Overhead: <500ms (95th percentile) on top of provider latency
    Concurrent requests: 100+ req/s

Author: Agent Guru Team
Date: 2026-03-18
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Optional, Union

from Agent_Guru.llm.context_manager import ContextManager
from Agent_Guru.llm.error_handler import ErrorHandler
from Agent_Guru.llm.models import (
    CompletionRequest,
    CompletionResponse,
    ContextWindowExceededError,
    Message,
    ModelProvider,
    RuntimeConfig,
    StreamChunk,
)
from Agent_Guru.llm.performance_monitor import PerformanceMonitor
from Agent_Guru.llm.providers.anthropic_adapter import AnthropicAdapter
from Agent_Guru.llm.providers.base import ProviderAdapter
from Agent_Guru.llm.providers.google_adapter import GoogleAdapter
from Agent_Guru.llm.providers.ollama_adapter import OllamaAdapter
from Agent_Guru.llm.providers.openai_adapter import OpenAIAdapter
from Agent_Guru.llm.token_counter import TokenCounter

logger = logging.getLogger(__name__)

# BUG-031: _CONTEXT_LIMITS was duplicated here AND in context_manager.py.
# Canonical definition lives in context_manager.py; imported here to remove duplication.
from Agent_Guru.llm.context_manager import CONTEXT_LIMITS as _CONTEXT_LIMITS

# Pricing per 1K tokens for cost estimation
_PRICING: dict[str, float] = {
    "gpt-4": 0.03,
    "gpt-3.5-turbo": 0.002,
    "claude-3-opus": 0.015,
    "claude-3-sonnet": 0.003,
}


class LLMRuntime:
    """
    Unified interface for all LLM operations.

    Provides a single API for Ollama, OpenAI, Anthropic, and Google models
    with streaming, function calling, context management, and performance
    monitoring built in.

    Example:
        >>> config = RuntimeConfig(
        ...     openai_config=OpenAIConfig(api_key="sk-..."),
        ... )
        >>> runtime = LLMRuntime.from_config(config)
        >>> response = await runtime.complete(
        ...     CompletionRequest(
        ...         model="gpt-3.5-turbo",
        ...         messages=[Message(role="user", content="Hello!")],
        ...     )
        ... )
        >>> print(response.content)
    """

    def __init__(
        self,
        config: RuntimeConfig,
        context_manager: ContextManager,
        token_counter: TokenCounter,
        performance_monitor: PerformanceMonitor,
        error_handler: ErrorHandler,
    ) -> None:
        self.config = config
        self.context_manager = context_manager
        self.token_counter = token_counter
        self.performance_monitor = performance_monitor
        self.error_handler = error_handler

        self.adapters: dict[ModelProvider, ProviderAdapter] = {
            ModelProvider.OLLAMA: OllamaAdapter(config.ollama_config),
            ModelProvider.OPENAI: OpenAIAdapter(config.openai_config),
            ModelProvider.ANTHROPIC: AnthropicAdapter(config.anthropic_config),
            ModelProvider.GOOGLE: GoogleAdapter(config.google_config),
        }

    @classmethod
    def from_config(cls, config: RuntimeConfig) -> "LLMRuntime":
        """Convenience factory that wires all components together."""
        token_counter = TokenCounter()
        return cls(
            config=config,
            context_manager=ContextManager(
                token_counter=token_counter,
                compression_threshold=config.compression_threshold,
                max_history_messages=config.max_history_messages,
            ),
            token_counter=token_counter,
            performance_monitor=PerformanceMonitor(
                slow_threshold_ms=config.slow_threshold_ms,
                failure_threshold=config.failure_threshold,
            ),
            error_handler=ErrorHandler(
                max_retries=config.max_retries,
                initial_backoff_ms=config.initial_backoff_ms,
                max_backoff_ms=config.max_backoff_ms,
                circuit_breaker_threshold=config.circuit_breaker_threshold,
                circuit_breaker_timeout_s=config.circuit_breaker_timeout_s,
            ),
        )

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """
        Execute a non-streaming completion request.

        Injects session context, validates token budget, executes with
        retry logic, updates context, and records metrics.

        Args:
            request: Completion request in unified format.

        Returns:
            CompletionResponse with full response.

        Raises:
            ContextWindowExceededError: If request exceeds context limit.
            CircuitBreakerOpenError: If provider circuit is open.
        """
        # BUG-003: use timezone-aware UTC timestamp to avoid DST/NTP corruption
        start_time = datetime.now(tz=timezone.utc)
        provider = self._get_provider(request.model)
        adapter = self.adapters[provider]

        # Inject session context
        if request.session_id:
            request.messages = self.context_manager.inject_context(
                request.session_id, request.messages
            )

        # Validate token budget
        estimated_tokens = self.token_counter.count_messages(
            request.messages, request.model
        )
        if request.max_tokens:
            estimated_tokens += request.max_tokens

        context_limit = self._get_context_limit(request.model)
        if estimated_tokens > context_limit:
            raise ContextWindowExceededError(
                f"Estimated {estimated_tokens} tokens exceeds context limit "
                f"{context_limit} for model '{request.model}'."
            )

        # Resolve per-request timeout (config.timeout → 30s default)
        timeout: float = getattr(self.config, "timeout", None) or 30.0

        # Execute with retry, enforcing timeout on each adapter call
        response = await self.error_handler.execute_with_retry(
            lambda: asyncio.wait_for(adapter.complete(request), timeout=timeout),
            provider=provider.value,
        )

        # Update context
        if request.session_id and request.messages:
            await self.context_manager.update_context(
                request.session_id,
                request.messages[-1],
                Message(role="assistant", content=response.content),
            )

        # Record metrics
        # BUG-003: compute latency from two UTC-aware datetimes
        latency_ms = (datetime.now(tz=timezone.utc) - start_time).total_seconds() * 1000
        response.latency_ms = latency_ms

        await self.performance_monitor.record_request(
            model=request.model,
            provider=provider,
            latency_ms=latency_ms,
            tokens=response.usage.total_tokens,
            cost=response.usage.estimated_cost,
            success=True,
        )

        return response

    async def stream(
        self, request: CompletionRequest
    ) -> AsyncIterator[StreamChunk]:
        """
        Execute a streaming completion request.

        Yields StreamChunk objects incrementally. Updates context and
        records metrics after the stream completes.

        Args:
            request: Completion request (stream=True recommended).

        Yields:
            StreamChunk for each token/chunk.

        Raises:
            ContextWindowExceededError: If request exceeds context limit.
        """
        # BUG-003: use timezone-aware UTC timestamp
        start_time = datetime.now(tz=timezone.utc)
        provider = self._get_provider(request.model)
        adapter = self.adapters[provider]

        # Inject session context
        if request.session_id:
            request.messages = self.context_manager.inject_context(
                request.session_id, request.messages
            )

        # Validate token budget
        estimated_tokens = self.token_counter.count_messages(
            request.messages, request.model
        )
        context_limit = self._get_context_limit(request.model)
        if estimated_tokens > context_limit:
            raise ContextWindowExceededError(
                f"Estimated {estimated_tokens} tokens exceeds context limit "
                f"{context_limit} for model '{request.model}'."
            )

        full_content = ""
        error_msg: Optional[str] = None

        try:
            async for chunk in adapter.stream(request):
                full_content += chunk.content
                yield chunk
        except Exception as exc:
            error_msg = str(exc)
            latency_ms = (datetime.now(tz=timezone.utc) - start_time).total_seconds() * 1000
            await self.performance_monitor.record_request(
                model=request.model,
                provider=provider,
                latency_ms=latency_ms,
                tokens=self.token_counter.count_text(full_content, request.model),
                cost=0.0,
                success=False,
                error=error_msg,
            )
            raise

        # Update context with full response
        if request.session_id and request.messages:
            await self.context_manager.update_context(
                request.session_id,
                request.messages[-1],
                Message(role="assistant", content=full_content),
            )

        # Record metrics
        latency_ms = (datetime.now(tz=timezone.utc) - start_time).total_seconds() * 1000
        tokens = self.token_counter.count_text(full_content, request.model)

        await self.performance_monitor.record_request(
            model=request.model,
            provider=provider,
            latency_ms=latency_ms,
            tokens=tokens,
            cost=self._estimate_cost(tokens, request.model),
            success=True,
        )

    async def embed(
        self, text: Union[str, list[str]], model: str
    ) -> list[list[float]]:
        """
        Generate embeddings for text.

        Args:
            text: Single string or list of strings.
            model: Embedding model name.

        Returns:
            List of embedding vectors.
        """
        provider = self._get_provider(model)
        adapter = self.adapters[provider]

        return await self.error_handler.execute_with_retry(
            lambda: adapter.embed(text, model),
            provider=provider.value,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_provider(model: str) -> ModelProvider:
        """Determine provider from model name prefix."""
        if model.startswith(("gpt-", "text-embedding", "o1-", "o3-")):
            return ModelProvider.OPENAI
        if model.startswith("claude-"):
            return ModelProvider.ANTHROPIC
        if model.startswith("gemini-"):
            return ModelProvider.GOOGLE
        return ModelProvider.OLLAMA

    @staticmethod
    def _get_context_limit(model: str) -> int:
        """Return context window limit for a model."""
        for prefix, limit in _CONTEXT_LIMITS.items():
            if model.startswith(prefix):
                return limit
        return 4096

    @staticmethod
    def _estimate_cost(tokens: int, model: str) -> float:
        """Estimate cost for token usage."""
        for prefix, price_per_1k in _PRICING.items():
            if model.startswith(prefix):
                return (tokens / 1000) * price_per_1k
        return 0.0  # Local models are free
