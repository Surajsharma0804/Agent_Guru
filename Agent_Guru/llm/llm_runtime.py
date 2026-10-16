"""Unified LLM Runtime Interface.

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
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from Agent_Guru.llm.context_manager import CONTEXT_LIMITS as _CONTEXT_LIMITS
from Agent_Guru.llm.context_manager import ContextManager
from Agent_Guru.llm.error_handler import ErrorHandler
from Agent_Guru.llm.models import (
    CompletionRequest,
    CompletionResponse,
    ContextWindowExceededError,
    Message,
    ModelProvider,
    ProviderNotSupportedError,
    RuntimeConfig,
    StreamChunk,
)
from Agent_Guru.llm.performance_monitor import PerformanceMonitor
from Agent_Guru.llm.providers.ollama_adapter import OllamaAdapter
from Agent_Guru.llm.token_counter import TokenCounter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from Agent_Guru.llm.providers.base import ProviderAdapter

logger = logging.getLogger(__name__)

# BUG-031: _CONTEXT_LIMITS was duplicated here AND in context_manager.py.
# Canonical definition lives in context_manager.py; imported here to remove duplication.

# Pricing per 1K tokens for cost estimation (local Ollama models are free)
_PRICING: dict[str, float] = {}


class LLMRuntime:
    """Unified interface for all LLM operations.

    Provides a single API for Ollama models with streaming, function calling,
    context management, and performance monitoring built in.

    Example:
        >>> config = RuntimeConfig(
        ...     ollama_config=OllamaConfig(host="http://localhost:11434"),
        ... )
        >>> runtime = LLMRuntime.from_config(config)
        >>> response = await runtime.complete(
        ...     CompletionRequest(
        ...         model="llama3",
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

        from Agent_Guru.llm.providers.openai_compatible import OpenAICompatibleAdapter

        self.adapters: dict[ModelProvider, ProviderAdapter] = {
            ModelProvider.OLLAMA: OllamaAdapter(config.ollama_config),
            ModelProvider.OPENAI_COMPATIBLE: OpenAICompatibleAdapter(),
        }

    @classmethod
    def from_config(cls, config: RuntimeConfig) -> LLMRuntime:
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

    def _fallback_for(self, request: CompletionRequest) -> CompletionRequest | None:
        """The same request for AGENT_GURU_FALLBACK_MODEL, or None when there is none to try.

        Answers went to one engine: with Ollama stopped or its model failing,
        every turn ended in an error although a second engine (another local
        one, or a cloud model the owner allowed) could have answered. One
        retry on the fallback, never a chain, and never for a request the
        context window refused, which the fallback would refuse as well.
        """
        import dataclasses
        import os

        fallback = os.environ.get("AGENT_GURU_FALLBACK_MODEL", "").strip()
        if not fallback or fallback == request.model or request.metadata.get("fallback_of"):
            return None
        try:
            self._get_provider(fallback)
        except ProviderNotSupportedError:
            return None
        return dataclasses.replace(request, model=fallback, metadata={**request.metadata, "fallback_of": request.model})

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """A completion from request.model, or from AGENT_GURU_FALLBACK_MODEL when that fails."""
        try:
            return await self._complete(request)
        except ContextWindowExceededError:
            raise
        except Exception as exc:
            other = self._fallback_for(request)
            if other is None:
                raise
            logger.warning("%s failed (%s); answering with %s", request.model, type(exc).__name__, other.model)
            return await self._complete(other)

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Chunks from request.model; from AGENT_GURU_FALLBACK_MODEL only when the first failed before any chunk.

        Once text has been sent it has been heard, so a stream that fails
        part-way is not restarted on another model.
        """
        sent = False
        try:
            async for chunk in self._stream(request):
                sent = True
                yield chunk
        except ContextWindowExceededError:
            raise
        except Exception as exc:
            other = None if sent else self._fallback_for(request)
            if other is None:
                raise
            logger.warning("%s failed (%s); answering with %s", request.model, type(exc).__name__, other.model)
            async for chunk in self._stream(other):
                yield chunk

    async def _complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a non-streaming completion request.

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
        start_time = datetime.now(tz=UTC)
        provider = self._get_provider(request.model)
        adapter = self.adapters[provider]

        # Inject session context
        if request.session_id:
            request.messages = self.context_manager.inject_context(
                request.session_id,
                request.messages,
            )

        # Validate token budget
        estimated_tokens = self.token_counter.count_messages(request.messages, request.model)
        if request.max_tokens:
            estimated_tokens += request.max_tokens

        context_limit = self._get_context_limit(request.model)
        if estimated_tokens > context_limit:
            msg = (
                f"Estimated {estimated_tokens} tokens exceeds context limit "
                f"{context_limit} for model '{request.model}'."
            )
            raise ContextWindowExceededError(
                msg,
            )

        # Resolve per-request timeout.
        # mistral:7b on RTX 2050 (4GB VRAM, model barely fits) runs at ~6-8 tok/s.
        # A 150-token response takes ~20-25s. Use 120s to cover worst case.
        timeout: float = getattr(self.config, "timeout", None) or 120.0
        if self._get_provider(request.model) == ModelProvider.OLLAMA:
            timeout = min(timeout, 120.0)  # 120s for local Ollama

        # Execute with retry, enforcing timeout on each adapter call.
        #
        # BUG FIX (Round 26): unlike stream() just below (which wraps its
        # equivalent call in try/except and calls
        # performance_monitor.record_request(success=False, ...) on failure),
        # this call had no such handling - if every retry attempt raised
        # (or a permanent/non-retryable error occurred), the exception from
        # execute_with_retry() propagated straight out of complete() and
        # performance_monitor.record_request() below was simply never
        # reached for that request. Because ErrorHandler's circuit breaker
        # tracks failures independently (via its own internal state, not
        # through PerformanceMonitor), the app still recovered correctly -
        # but PerformanceMonitor, whose failure counter is what
        # _emit_reliability_warning() and report_to_self_improvement()'s
        # success_rate are actually computed from, never saw a single
        # failed request on this - the primary, non-streaming - call path.
        # A model/provider that was failing constantly would have reported
        # a misleading 100% success_rate to the Self-Improvement Engine,
        # since only successes were ever recorded. Wrapping this the same
        # way stream() already does closes that gap.
        try:
            response = await self.error_handler.execute_with_retry(
                lambda: asyncio.wait_for(adapter.complete(request), timeout=timeout),
                provider=provider.value,
            )
        except Exception as exc:
            latency_ms = (datetime.now(tz=UTC) - start_time).total_seconds() * 1000
            await self.performance_monitor.record_request(
                model=request.model,
                provider=provider,
                latency_ms=latency_ms,
                tokens=estimated_tokens,
                cost=0.0,
                success=False,
                error=str(exc),
            )
            raise

        # Update context
        if request.session_id and request.messages:
            await self.context_manager.update_context(
                request.session_id,
                request.messages[-1],
                Message(role="assistant", content=response.content),
            )

        # Record metrics
        # BUG-003: compute latency from two UTC-aware datetimes
        latency_ms = (datetime.now(tz=UTC) - start_time).total_seconds() * 1000
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

    async def _stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Execute a streaming completion request.

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
        start_time = datetime.now(tz=UTC)
        provider = self._get_provider(request.model)
        adapter = self.adapters[provider]

        # Inject session context
        if request.session_id:
            request.messages = self.context_manager.inject_context(
                request.session_id,
                request.messages,
            )

        # Validate token budget
        estimated_tokens = self.token_counter.count_messages(request.messages, request.model)
        context_limit = self._get_context_limit(request.model)
        if estimated_tokens > context_limit:
            msg = (
                f"Estimated {estimated_tokens} tokens exceeds context limit "
                f"{context_limit} for model '{request.model}'."
            )
            raise ContextWindowExceededError(
                msg,
            )

        full_content = ""
        error_msg: str | None = None

        try:
            async for chunk in adapter.stream(request):
                full_content += chunk.content
                yield chunk
        except Exception as exc:
            error_msg = str(exc)
            latency_ms = (datetime.now(tz=UTC) - start_time).total_seconds() * 1000
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
        latency_ms = (datetime.now(tz=UTC) - start_time).total_seconds() * 1000
        tokens = self.token_counter.count_text(full_content, request.model)

        await self.performance_monitor.record_request(
            model=request.model,
            provider=provider,
            latency_ms=latency_ms,
            tokens=tokens,
            cost=self._estimate_cost(tokens, request.model),
            success=True,
        )

    async def supports_tool_calling(self, model: str) -> bool:
        """Whether *model*'s provider takes tools for it and answers with structured calls."""
        try:
            return await self.adapters[self._get_provider(model)].supports_tool_calling(model)
        except Exception:
            return False

    async def embed(self, text: str | list[str], model: str) -> list[list[float]]:
        """Generate embeddings for text.

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
        """Determine provider from model name.

        Ollama unless the model is "engine:<name>" (the owner's local engine
        at AGENT_GURU_ENGINE_URL) or a cloud model the owner allowed
        (AGENT_GURU_ALLOW_CLOUD and the provider's key): those go to the
        OpenAI-compatible adapter. Other cloud names are refused, as before.
        """
        from Agent_Guru.llm.providers.openai_compatible import endpoint_for

        if endpoint_for(model) is not None:
            return ModelProvider.OPENAI_COMPATIBLE
        if model.startswith("engine:"):
            msg = f"Model '{model}' needs AGENT_GURU_ENGINE_URL, the address of the engine that serves it."
            raise ProviderNotSupportedError(msg)
        if model.startswith(("gpt-", "text-embedding", "o1-", "o3-")):
            msg = (
                f"Model '{model}' is an OpenAI cloud model; it is used only with "
                "AGENT_GURU_ALLOW_CLOUD set and its API key. Use a local Ollama model instead."
            )
            raise ProviderNotSupportedError(
                msg,
            )
        if model.startswith("claude-"):
            msg = (
                f"Model '{model}' is an Anthropic cloud model; it is used only with "
                "AGENT_GURU_ALLOW_CLOUD set and its API key. Use a local Ollama model instead."
            )
            raise ProviderNotSupportedError(
                msg,
            )
        if model.startswith("gemini-"):
            msg = (
                f"Model '{model}' is a Google cloud model; it is used only with "
                "AGENT_GURU_ALLOW_CLOUD set and its API key. Use a local Ollama model instead."
            )
            raise ProviderNotSupportedError(
                msg,
            )
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
