"""Module: Agent_Guru.llm.failover_router
Purpose: Provider failover chain with automatic fallback and rule-based responses.

Implements the failover chain: Ollama → OpenAI → Gemini → Rule-based
with availability checking, context preservation across switches, and
a rule-based fallback for when all providers are unavailable.

Performance:
    - Time Complexity: O(k) where k = number of providers in chain
    - Space Complexity: O(1)
    - Failover latency: <100ms per provider check

Author: Agent Guru Team
Date: 2026-03-19
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from Agent_Guru.llm.models import (
    CompletionRequest,
    CompletionResponse,
    Message,
    ModelProvider,
    TokenUsage,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider availability status
# ---------------------------------------------------------------------------


class ProviderStatus(Enum):
    """Provider availability status."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass
class ProviderHealth:
    """Health state for a single provider."""

    provider: ModelProvider
    status: ProviderStatus = ProviderStatus.UNKNOWN
    last_check_ts: float = 0.0
    consecutive_failures: int = 0
    last_error: str | None = None

    def is_healthy(self, ttl_seconds: float = 30.0) -> bool:
        """Return True if the provider is available OR its TTL has expired
        (meaning it is eligible for a retry check).

        BUG-010 fix: the old method returned True for UNAVAILABLE providers
        after TTL — which could be read as "OK to use" but is really "OK to
        retry". The semantics are preserved; the name and docstring now correctly
        reflect the intent so future readers don't misread it.
        """
        if self.status == ProviderStatus.UNAVAILABLE:
            # Still within the blackout window — do NOT retry yet
            if (time.time() - self.last_check_ts) <= ttl_seconds:
                return False
            # TTL expired — allow a retry attempt
            return True
        return self.status != ProviderStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# Rule-based fallback responses
# ---------------------------------------------------------------------------

_RULE_BASED_RESPONSES: dict[str, str] = {
    "hello": "Hello! I'm Guru. How can I help you today?",
    "hi": "Hi there! I'm Guru. What can I do for you?",
    "help": "I can help you with tasks, answer questions, and control your computer. Just ask!",
    "what can you do": "I can open apps, type text, search the web, answer questions, and much more!",
    "goodbye": "Goodbye! Have a great day!",
    "bye": "Bye! Talk to you soon!",
    "thank you": "You're welcome! Is there anything else I can help with?",
    "thanks": "Happy to help! Anything else?",
    "what time is it": "I don't have access to real-time data right now, but you can check your system clock.",
    "what's the weather": "I can't check the weather right now, but you can ask me to open a weather website.",
}

_DEFAULT_FALLBACK = (
    "I'm having trouble connecting to my AI services right now. "
    "Please check your internet connection or try again in a moment. "
    "I can still help with basic commands like opening apps and typing text."
)


def _rule_based_response(user_message: str) -> str:
    """Generate a rule-based response for common queries.

    Args:
        user_message: User's message text

    Returns:
        Rule-based response string

    """
    normalized = user_message.lower().strip().rstrip("?!.,")
    for pattern, response in _RULE_BASED_RESPONSES.items():
        if pattern in normalized:
            return response
    return _DEFAULT_FALLBACK


# ---------------------------------------------------------------------------
# Failover router
# ---------------------------------------------------------------------------


@dataclass
class FailoverConfig:
    """Configuration for the failover router.

    Attributes:
        provider_chain: Ordered list of providers to try
        health_check_ttl_seconds: How long to cache health status
        max_failures_before_skip: Consecutive failures before skipping provider
        enable_rule_based_fallback: Whether to use rule-based fallback
        voice_system_prompt: System prompt for voice interaction personality

    """

    provider_chain: list[ModelProvider] = field(
        default_factory=lambda: [
            ModelProvider.OLLAMA,
            ModelProvider.OPENAI,
            ModelProvider.GOOGLE,
            ModelProvider.ANTHROPIC,
        ],
    )
    health_check_ttl_seconds: float = 30.0
    max_failures_before_skip: int = 3
    enable_rule_based_fallback: bool = True
    voice_system_prompt: str = (
        "You are Guru, a helpful AI voice assistant. "
        "Keep responses concise and natural for voice output. "
        "Avoid markdown, bullet points, or formatting. "
        "Speak in a friendly, conversational tone."
    )


@dataclass
class FailoverResult:
    """Result from a failover router completion.

    Attributes:
        response: The completion response
        provider_used: Which provider was used
        providers_tried: All providers that were attempted
        used_fallback: Whether rule-based fallback was used
        latency_ms: Total latency including failover attempts

    """

    response: CompletionResponse
    provider_used: ModelProvider | None
    providers_tried: list[ModelProvider]
    used_fallback: bool
    latency_ms: float


class ProviderFailoverRouter:
    """Intelligent provider failover router.

    Tries providers in order (Ollama → OpenAI → Gemini → Anthropic),
    falling back to rule-based responses if all providers fail.

    Features:
    - Automatic availability checking with TTL caching
    - Context preservation across provider switches
    - Rule-based fallback for offline operation
    - Voice-optimized system prompt injection

    Example:
        >>> router = ProviderFailoverRouter(config, adapters)
        >>> result = await router.complete_with_failover(request)
        >>> print(result.response.content)
        >>> print(f"Used: {result.provider_used}")

    """

    def __init__(
        self,
        config: FailoverConfig,
        adapters: dict[ModelProvider, Any],
    ) -> None:
        """Initialize the failover router.

        Args:
            config: Failover configuration
            adapters: Dict mapping ModelProvider → ProviderAdapter

        """
        self._config = config
        self._adapters = adapters
        self._health: dict[ModelProvider, ProviderHealth] = {
            p: ProviderHealth(provider=p) for p in config.provider_chain
        }
        self._lock = asyncio.Lock()

    async def complete_with_failover(
        self,
        request: CompletionRequest,
        inject_system_prompt: bool = True,
    ) -> FailoverResult:
        """Execute completion with automatic provider failover.

        Tries each provider in the chain. If a provider fails, moves to
        the next. If all fail, returns a rule-based response.

        Time Complexity: O(k) where k = len(provider_chain)

        Args:
            request: Completion request
            inject_system_prompt: Whether to inject voice system prompt

        Returns:
            FailoverResult with response and metadata

        """
        start = time.perf_counter()
        providers_tried: list[ModelProvider] = []

        # Inject voice system prompt if not already present
        if inject_system_prompt and self._config.voice_system_prompt:
            request = self._inject_system_prompt(request)

        for provider in self._config.provider_chain:
            if provider not in self._adapters:
                continue

            health = self._health[provider]

            # Skip providers with too many consecutive failures
            if health.consecutive_failures >= self._config.max_failures_before_skip:
                # Check if TTL has expired (time to retry)
                if not health.is_healthy(self._config.health_check_ttl_seconds):
                    logger.debug("Skipping %s: too many failures", provider.value)
                    continue

            providers_tried.append(provider)

            try:
                # Adapt request model to provider's default if needed
                adapted_request = self._adapt_request(request, provider)
                adapter = self._adapters[provider]
                response = await adapter.complete(adapted_request)

                # Mark provider as healthy
                async with self._lock:
                    health.status = ProviderStatus.AVAILABLE
                    health.consecutive_failures = 0
                    health.last_check_ts = time.time()

                latency_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "Failover router: used %s (tried: %s, latency: %.1fms)",
                    provider.value,
                    [p.value for p in providers_tried],
                    latency_ms,
                )

                return FailoverResult(
                    response=response,
                    provider_used=provider,
                    providers_tried=providers_tried,
                    used_fallback=False,
                    latency_ms=latency_ms,
                )

            except Exception as e:
                logger.exception("Provider %s failed. Trying next provider...", provider.value)
                async with self._lock:
                    health.status = ProviderStatus.UNAVAILABLE
                    health.consecutive_failures += 1
                    health.last_check_ts = time.time()
                    health.last_error = str(e)
                continue

        # All providers failed — use rule-based fallback
        latency_ms = (time.perf_counter() - start) * 1000
        # BUG-013: replaced f-string logger call with %s lazy-format
        logger.warning(
            "All providers failed. Using rule-based fallback. Tried: %s",
            [p.value for p in providers_tried],
        )

        if self._config.enable_rule_based_fallback:
            user_text = self._extract_last_user_message(request)
            fallback_text = _rule_based_response(user_text)
        else:
            fallback_text = _DEFAULT_FALLBACK

        fallback_response = CompletionResponse(
            content=fallback_text,
            model="rule-based",
            # BUG-033: was ModelProvider.OLLAMA as a wrong placeholder; None
            # signals "no real LLM provider" so cost/routing callers behave correctly.
            # BUG-004: was __import__("datetime").datetime.now() — fragile and naive;
            # replaced with proper import + UTC-aware timestamp.
            provider=None,  # type: ignore[arg-type]
            finish_reason="stop",
            usage=TokenUsage(
                prompt_tokens=0,
                completion_tokens=len(fallback_text.split()),
                total_tokens=len(fallback_text.split()),
                estimated_cost=0.0,
            ),
            latency_ms=latency_ms,
            timestamp=datetime.now(tz=UTC),
        )

        return FailoverResult(
            response=fallback_response,
            provider_used=None,
            providers_tried=providers_tried,
            used_fallback=True,
            latency_ms=latency_ms,
        )

    async def check_provider_availability(self, provider: ModelProvider) -> ProviderStatus:
        """Check if a provider is available by making a minimal test request.

        Args:
            provider: Provider to check

        Returns:
            ProviderStatus

        """
        if provider not in self._adapters:
            return ProviderStatus.UNAVAILABLE

        try:
            adapter = self._adapters[provider]
            test_request = CompletionRequest(
                model=self._get_default_model(provider),
                messages=[Message(role="user", content="ping")],
                max_tokens=1,
                temperature=0.0,
            )
            await asyncio.wait_for(adapter.complete(test_request), timeout=5.0)
            async with self._lock:
                self._health[provider].status = ProviderStatus.AVAILABLE
                self._health[provider].last_check_ts = time.time()
            return ProviderStatus.AVAILABLE

        except Exception as e:
            async with self._lock:
                self._health[provider].status = ProviderStatus.UNAVAILABLE
                self._health[provider].last_check_ts = time.time()
                self._health[provider].last_error = str(e)
            return ProviderStatus.UNAVAILABLE

    def get_health_status(self) -> dict[str, Any]:
        """Return health status for all providers."""
        return {
            p.value: {
                "status": h.status.value,
                "consecutive_failures": h.consecutive_failures,
                "last_error": h.last_error,
                "last_check_ts": h.last_check_ts,
            }
            for p, h in self._health.items()
        }

    def reset_provider_health(self, provider: ModelProvider) -> None:
        """Reset health state for a provider (e.g. after config change)."""
        if provider in self._health:
            self._health[provider] = ProviderHealth(provider=provider)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _inject_system_prompt(self, request: CompletionRequest) -> CompletionRequest:
        """Inject voice system prompt if not already present."""
        has_system = any(m.role == "system" for m in request.messages)
        if has_system:
            return request

        system_msg = Message(role="system", content=self._config.voice_system_prompt)
        new_messages = [system_msg, *list(request.messages)]

        # Return a shallow copy with updated messages
        import dataclasses

        return dataclasses.replace(request, messages=new_messages)

    def _adapt_request(
        self,
        request: CompletionRequest,
        provider: ModelProvider,
    ) -> CompletionRequest:
        """Adapt request model name for the target provider."""
        import dataclasses

        default_model = self._get_default_model(provider)
        # Only override model if it doesn't match the provider's prefix
        if not self._model_matches_provider(request.model, provider):
            return dataclasses.replace(request, model=default_model)
        return request

    @staticmethod
    def _model_matches_provider(model: str, provider: ModelProvider) -> bool:
        """Check if a model name belongs to a provider."""
        prefixes = {
            ModelProvider.OPENAI: ("gpt-", "text-embedding", "o1-", "o3-"),
            ModelProvider.ANTHROPIC: ("claude-",),
            ModelProvider.GOOGLE: ("gemini-",),
            ModelProvider.OLLAMA: (),  # Ollama accepts any model name
        }
        provider_prefixes = prefixes.get(provider, ())
        if not provider_prefixes:
            return True  # Ollama accepts anything
        return any(model.startswith(p) for p in provider_prefixes)

    @staticmethod
    def _get_default_model(provider: ModelProvider) -> str:
        """Return the default model for a provider."""
        defaults = {
            ModelProvider.OLLAMA: "llama3.2",
            ModelProvider.OPENAI: "gpt-4o-mini",
            ModelProvider.ANTHROPIC: "claude-3-haiku-20240307",
            ModelProvider.GOOGLE: "gemini-2.0-flash",
        }
        return defaults.get(provider, "gpt-4o-mini")

    @staticmethod
    def _extract_last_user_message(request: CompletionRequest) -> str:
        """Extract the last user message from a request."""
        for msg in reversed(request.messages):
            if msg.role == "user":
                return msg.content
        return ""
