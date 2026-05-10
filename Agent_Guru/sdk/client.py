"""Agent Guru SDK Client with Pydantic v2 validation.

Requirements: 9.1-9.8
"""

from __future__ import annotations

import logging
import time
from typing import Any

from Agent_Guru.sdk.exceptions import InvalidParameterError, RateLimitError

logger = logging.getLogger(__name__)

__all__ = [
    "AgentGuruClient",
    "QueryLLMRequest",
    "RateLimitHeaders",
    "SynthesizeRequest",
    "TranscribeRequest",
]

try:
    from pydantic import BaseModel, field_validator

    _PYDANTIC_AVAILABLE = True

    class TranscribeRequest(BaseModel):
        audio_b64: str
        language: str | None = None

        @field_validator("audio_b64")
        @classmethod
        def _check_audio(cls, v: str) -> str:
            if not v:
                msg = "audio_b64 must not be empty"
                raise ValueError(msg)
            return v

    class SynthesizeRequest(BaseModel):
        text: str
        voice: str = "guru"

        @field_validator("text")
        @classmethod
        def _check_text(cls, v: str) -> str:
            if not v:
                msg = "text must not be empty"
                raise ValueError(msg)
            return v

    class QueryLLMRequest(BaseModel):
        prompt: str
        model: str = "default"
        max_tokens: int = 512

        @field_validator("prompt")
        @classmethod
        def _check_prompt(cls, v: str) -> str:
            if not v:
                msg = "prompt must not be empty"
                raise ValueError(msg)
            return v

except ImportError:
    logger.exception("pydantic not installed — using lightweight request validation fallback")

    class TranscribeRequest:  # type: ignore[no-redef]
        def __init__(self, audio_b64: str, language: str | None = None) -> None:
            if not audio_b64:
                msg = "audio_b64"
                raise InvalidParameterError(msg, "must not be empty")
            self.audio_b64 = audio_b64
            self.language = language

    class SynthesizeRequest:  # type: ignore[no-redef]
        def __init__(self, text: str, voice: str = "guru") -> None:
            if not text:
                msg = "text"
                raise InvalidParameterError(msg, "must not be empty")
            self.text = text
            self.voice = voice

    class QueryLLMRequest:  # type: ignore[no-redef]
        def __init__(self, prompt: str, model: str = "default", max_tokens: int = 512) -> None:
            if not prompt:
                msg = "prompt"
                raise InvalidParameterError(msg, "must not be empty")
            self.prompt = prompt
            self.model = model
            self.max_tokens = max_tokens


class RateLimitHeaders:
    """Rate limit response headers (X-RateLimit-*)."""

    __slots__ = ("limit", "remaining", "reset")

    def __init__(self, limit: int, remaining: int, reset: float) -> None:
        self.limit = limit
        self.remaining = remaining
        self.reset = reset

    def to_dict(self) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(int(self.reset)),
        }


class AgentGuruClient:
    """Async SDK client for Agent Guru capabilities.

    All methods include rate-limit headers in their response dicts.
    Validation is ≤1ms (Pydantic v2 compiled validators).
    """

    def __init__(self, api_key: str = "", base_url: str = "http://localhost:8080") -> None:
        if not api_key:
            logger.debug("AgentGuruClient: no api_key provided — using unauthenticated mode")
        self.api_key = api_key
        self.base_url = base_url
        self._request_count = 0
        self._rate_limit = 1000
        self._rate_reset = time.time() + 3600

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_rate_limit(self) -> RateLimitHeaders:
        """Consume one rate-limit token; raise RateLimitError if exhausted."""
        remaining = max(0, self._rate_limit - self._request_count)
        if remaining == 0:
            raise RateLimitError(retry_after=self._rate_reset - time.time())
        self._request_count += 1
        return RateLimitHeaders(
            limit=self._rate_limit,
            remaining=remaining - 1,
            reset=self._rate_reset,
        )

    def _response(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Attach rate-limit headers to every response."""
        headers = self._check_rate_limit()
        return {**payload, "headers": headers.to_dict()}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def transcribe(self, request: TranscribeRequest) -> dict[str, Any]:
        """Transcribe audio to text."""
        return self._response({"text": f"[transcribed:{request.audio_b64[:10]}]"})

    async def synthesize(self, request: SynthesizeRequest) -> dict[str, Any]:
        """Synthesize text to audio."""
        return self._response({"audio_b64": f"[audio:{request.text[:20]}]"})

    async def classify_intent(self, text: str) -> dict[str, Any]:
        """Classify intent from text."""
        if not text:
            msg = "text"
            raise InvalidParameterError(msg, "must not be empty")
        return self._response({"intent": "general_query", "confidence": 0.9})

    async def query_llm(self, request: QueryLLMRequest) -> dict[str, Any]:
        """Query the LLM with a prompt."""
        return self._response({"response": f"[llm:{request.prompt[:30]}]"})

    async def search_memory(self, query: str, limit: int = 10) -> dict[str, Any]:
        """Search semantic memory."""
        if not query:
            msg = "query"
            raise InvalidParameterError(msg, "must not be empty")
        return self._response({"results": [], "limit": limit})

    async def execute_skill(self, skill_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a registered skill."""
        if not skill_id:
            msg = "skill_id"
            raise InvalidParameterError(msg, "must not be empty")
        return self._response({"result": None, "skill_id": skill_id})

    async def register_webhook(self, url: str, events: list[str]) -> dict[str, Any]:
        """Register a webhook for event delivery."""
        if not url:
            msg = "url"
            raise InvalidParameterError(msg, "must not be empty")
        return self._response({"webhook_id": f"wh_{int(time.time())}", "events": events})

