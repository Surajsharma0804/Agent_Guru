"""Ollama provider adapter for local LLM inference.

Supports GPU-accelerated local models via the Ollama runtime.
Function calling is not natively supported and raises an error.

GPU Performance:
    - Local LLM: <400ms for 512 tokens with GPU acceleration
    - Requires Ollama with CUDA support

Author: Agent Guru Team
Date: 2026-03-18
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from Agent_Guru.llm.models import (
    CompletionRequest,
    CompletionResponse,
    ModelProvider,
    OllamaConfig,
    ProviderNotSupportedError,
    StreamChunk,
    TokenUsage,
)
from Agent_Guru.llm.providers.base import ProviderAdapter
from Agent_Guru.reasoning.llm.generation import OLLAMA_THINK, context_fits, ollama_options

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class OllamaAdapter(ProviderAdapter):
    """Adapter for Ollama local models.

    Supports:
    - Chat completions (non-streaming and streaming)
    - Embeddings
    - GPU acceleration via Ollama's CUDA support

    Does NOT support:
    - Function calling (raises ProviderNotSupportedError)

    Example:
        >>> config = OllamaConfig(host="http://localhost:11434")
        >>> adapter = OllamaAdapter(config)
        >>> response = await adapter.complete(request)

    """

    def __init__(self, config: OllamaConfig) -> None:
        self.config = config
        self._client: Any | None = None
        self._logger = logging.getLogger(__name__)

        # P2-61/62/63: Production Ollama optimization via env vars.
        # KEEP_ALIVE=-1 pins model in VRAM permanently - eliminates cold-start.
        # FLASH_ATTENTION=1 enables fused attention kernels on supported GPUs.
        # NUM_PARALLEL controls concurrent request handling based on VRAM.
        os.environ.setdefault("OLLAMA_KEEP_ALIVE", "-1")
        os.environ.setdefault("OLLAMA_FLASH_ATTENTION", "1")
        os.environ.setdefault("OLLAMA_NUM_PARALLEL", "1")

    @staticmethod
    def _options(request: CompletionRequest) -> dict[str, Any]:
        """Ollama options for this request, from the shared generation policy."""
        return ollama_options(num_predict=request.max_tokens, temperature=request.temperature)

    def _get_client(self) -> Any:
        """Lazy-initialize the Ollama async client."""
        if self._client is None:
            import ollama  # type: ignore[import]

            self._client = ollama.AsyncClient(host=self.config.host)
        return self._client

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a non-streaming chat completion via Ollama."""
        if request.functions:
            msg = (
                "Function calling is not supported for Ollama models. "
                "Use OpenAI or Anthropic for function calling."
            )
            raise ProviderNotSupportedError(
                msg,
            )

        client = self._get_client()
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        # Options come from the shared generation policy, the same ones every
        # other Ollama client sends. This adapter had its own copy: num_ctx
        # 1024, which cannot hold even the 1619-token first voice prompt (it
        # only worked because Ollama silently raises anything under 2048 to
        # 2048), and which differed from the intent fallback's, so Ollama
        # reloaded the model between the two calls on every voice turn.
        # num_thread=8 is gone: it bought nothing with every layer on the GPU
        # (2.66 s vs 2.60 s measured), and it would oversubscribe a CPU with
        # fewer cores.
        options = self._options(request)

        # BUG FIX: latency_ms was previously hardcoded to 0.0 below instead of
        # being measured, so every CompletionResponse this adapter produced
        # silently reported zero latency. ProviderFailoverRouter.complete_
        # with_failover() computes its own accurate round-trip latency but
        # only stores it on FailoverResult.latency_ms - it never propagates
        # that back into response.latency_ms - and LLMManager.generate_
        # response()'s telemetry call (record_request(latency_ms=result.
        # response.latency_ms, ...)) reads the per-provider field on the
        # response, by design, so that a slow/failed earlier provider in the
        # failover chain doesn't inflate the latency attributed to the
        # provider that actually succeeded. Since Ollama is the only adapter
        # currently wired into this repo's on-device provider chain, this
        # was silently zeroing out 100% of the LLM performance telemetry
        # this codebase records in practice. Fixed by measuring the actual
        # client.chat() call duration here, matching how CompletionResponse
        # is documented to be used everywhere else.
        # BUG FIX: OllamaConfig.timeout_s was declared (llm/models.py) but
        # never read anywhere in this adapter, and ProviderFailoverRouter
        # (the production caller - llm/failover_router.py) awaits
        # adapter.complete() directly with no timeout of its own either. A
        # stalled Ollama server (model still loading, GPU driver wedged, a
        # dropped local socket that never errors) would previously hang this
        # call forever: no exception is raised, so the failover chain never
        # gets a chance to try the next provider or fall back to a rule-
        # based response, and the whole request pipeline freezes. Wrapping
        # the call in asyncio.wait_for(timeout_s) turns that into a bounded
        # TimeoutError that ProviderFailoverRouter's except-and-continue
        # loop already handles correctly.
        # think: without it a thinking model such as gemma4 spent the whole
        # reply budget reasoning and returned empty content, so the voice
        # pipeline had nothing to say. See OLLAMA_THINK for the measurements.
        call_start = time.perf_counter()
        response = await asyncio.wait_for(
            client.chat(
                model=request.model,
                messages=messages,
                options=options,
                think=OLLAMA_THINK,
                keep_alive=-1,  # P2-61: keep model loaded permanently
            ),
            timeout=self.config.timeout_s,
        )
        latency_ms = (time.perf_counter() - call_start) * 1000
        prompt_tokens = response.get("prompt_eval_count", 0)
        completion_tokens = response.get("eval_count", 0)
        context_fits(prompt_tokens, request.max_tokens, source="OllamaAdapter")

        return CompletionResponse(
            content=response["message"]["content"],
            model=request.model,
            provider=ModelProvider.OLLAMA,
            # Was hard-coded "stop", so a reply cut off by num_predict looked
            # finished and the voice pipeline spoke it mid-sentence. Ollama
            # reports "length" when the cap ended it.
            finish_reason=response.get("done_reason") or "stop",
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                estimated_cost=0.0,  # Local models are free
            ),
            function_call=None,
            latency_ms=latency_ms,
            timestamp=datetime.now(tz=UTC),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Execute a streaming chat completion via Ollama."""
        if request.functions:
            msg = "Function calling is not supported for Ollama models."
            raise ProviderNotSupportedError(msg)

        client = self._get_client()
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        options = self._options(request)

        # BUG FIX: same unbounded-hang risk as complete() above - guard the
        # initial call that opens the stream with the configured timeout.
        # (Not currently reached in production: only LLMRuntime.complete()
        # calls adapter.stream(), and production goes through LLMManager /
        # ProviderFailoverRouter instead - see llm_manager.py. Fixed here
        # too so this adapter is safe regardless of which caller reaches it,
        # and so it doesn't silently regress if streaming is wired in later.
        # A stall *mid-stream*, after this call returns, would need a
        # per-chunk timeout around the iteration below to fully close off;
        # that's a larger change than closing the connect-time hang this
        # fixes, and is left as a follow-up since it isn't on the current
        # production path.)
        stream = await asyncio.wait_for(
            client.chat(
                model=request.model,
                messages=messages,
                stream=True,
                options=options,
                think=OLLAMA_THINK,
            ),
            timeout=self.config.timeout_s,
        )

        async for chunk in stream:
            if "message" in chunk:
                yield StreamChunk(
                    content=chunk["message"].get("content", ""),
                    finish_reason="stop" if chunk.get("done") else None,
                )

    async def embed(self, text: str | list[str], model: str) -> list[list[float]]:
        """Generate embeddings using an Ollama embedding model."""
        client = self._get_client()

        if isinstance(text, str):
            text = [text]

        embeddings: list[list[float]] = []
        for t in text:
            response = await client.embeddings(model=model, prompt=t)
            embeddings.append(response["embedding"])

        return embeddings
