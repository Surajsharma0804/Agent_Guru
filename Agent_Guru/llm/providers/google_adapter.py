"""
Google Gemini provider adapter.

Translates between the unified LLM Runtime API and the Google Generative AI API,
supporting chat completions, streaming, and embeddings.

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
    GoogleConfig,
    ModelProvider,
    StreamChunk,
    TokenUsage,
)
from Agent_Guru.llm.providers.base import ProviderAdapter


class GoogleAdapter(ProviderAdapter):
    """
    Adapter for the Google Gemini API.

    Supports:
    - Chat completions (non-streaming and streaming)
    - Embeddings

    Example:
        >>> config = GoogleConfig(api_key="AIza...")
        >>> adapter = GoogleAdapter(config)
        >>> response = await adapter.complete(request)
    """

    def __init__(self, config: GoogleConfig) -> None:
        self.config = config
        self._genai: Optional[Any] = None

    def _get_genai(self) -> Any:
        """Lazy-initialize the google-generativeai module."""
        if self._genai is None:
            import google.generativeai as genai  # type: ignore[import]

            genai.configure(api_key=self.config.api_key)
            self._genai = genai
        return self._genai

    # ------------------------------------------------------------------
    # Message format helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_gemini_history(messages: list) -> tuple[Optional[str], list]:
        """
        Convert unified messages to Gemini chat history format.

        Returns (system_instruction, history_list).
        Gemini uses 'user' and 'model' roles.
        """
        system_instruction: Optional[str] = None
        history: list = []

        for m in messages:
            if m.role == "system":
                system_instruction = m.content
            elif m.role == "assistant":
                history.append({"role": "model", "parts": [m.content]})
            else:
                history.append({"role": "user", "parts": [m.content]})

        return system_instruction, history

    # ------------------------------------------------------------------
    # ProviderAdapter interface
    # ------------------------------------------------------------------

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a non-streaming chat completion via Gemini."""
        genai = self._get_genai()
        system_instruction, history = self._to_gemini_history(request.messages)

        model_kwargs: Dict[str, Any] = {}
        if system_instruction:
            model_kwargs["system_instruction"] = system_instruction

        model = genai.GenerativeModel(request.model, **model_kwargs)

        generation_config = genai.types.GenerationConfig(
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
        )

        # Use the last user message as the prompt; prior turns as history
        if history and history[-1]["role"] == "user":
            prompt = history[-1]["parts"][0]
            chat_history = history[:-1]
        else:
            prompt = ""
            chat_history = history

        chat = model.start_chat(history=chat_history)
        response = await chat.send_message_async(
            prompt, generation_config=generation_config
        )

        content = response.text or ""

        # Approximate token usage (Gemini doesn't always return exact counts)
        prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        completion_tokens = (
            getattr(response.usage_metadata, "candidates_token_count", 0) or 0
        )

        return CompletionResponse(
            content=content,
            model=request.model,
            provider=ModelProvider.GOOGLE,
            finish_reason="stop",
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                estimated_cost=0.0,  # Gemini pricing varies; set to 0 for now
            ),
            function_call=None,
            latency_ms=0.0,
            timestamp=datetime.now(),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Execute a streaming chat completion via Gemini."""
        genai = self._get_genai()
        system_instruction, history = self._to_gemini_history(request.messages)

        model_kwargs: Dict[str, Any] = {}
        if system_instruction:
            model_kwargs["system_instruction"] = system_instruction

        model = genai.GenerativeModel(request.model, **model_kwargs)

        generation_config = genai.types.GenerationConfig(
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
        )

        if history and history[-1]["role"] == "user":
            prompt = history[-1]["parts"][0]
            chat_history = history[:-1]
        else:
            prompt = ""
            chat_history = history

        chat = model.start_chat(history=chat_history)
        response = await chat.send_message_async(
            prompt, generation_config=generation_config, stream=True
        )

        async for chunk in response:
            text = chunk.text or ""
            if text:
                yield StreamChunk(content=text, finish_reason=None)

        yield StreamChunk(content="", finish_reason="stop")

    async def embed(
        self, text: Union[str, List[str]], model: str
    ) -> List[List[float]]:
        """Generate embeddings using Google's embedding models."""
        genai = self._get_genai()

        if isinstance(text, str):
            text = [text]

        embeddings: List[List[float]] = []
        for t in text:
            result = genai.embed_content(model=model, content=t)
            embeddings.append(result["embedding"])

        return embeddings
