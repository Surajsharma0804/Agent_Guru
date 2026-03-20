"""Multi-platform LLM Manager for Agent Guru.

Higher-level manager over the existing LLM runtime infrastructure with:
- Platform-specific LLM support (Desktop: Ollama + Cloud, Mobile: Cloud only)
- Personality-specific system prompts (Guru vs Maya)
- Conversation context management per personality/session
- Fallback mechanism: cloud → local Ollama (desktop only)
- API key validation and secure storage via keyring
- <2 second response latency target

Performance Requirements:
    - LLM response latency: <2 seconds (95th percentile)
    - Guru personality: Professional, confident, analytical
    - Maya personality: Warm, empathetic, creative
    - Desktop: Ollama (local) + Cloud APIs with fallback
    - Mobile: Cloud APIs only

Architecture:
    LLMManager
    ├── LLMRuntime (llm_runtime.py) — unified provider interface
    ├── FailoverRouter (failover_router.py) — provider failover chain
    ├── ContextManager (context_manager.py) — conversation history
    └── keyring — secure API key storage

Author: Agent Guru Team
Date: 2026-03-20
Version: 1.0.0
"""
from __future__ import annotations

import asyncio
import logging
import platform
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from Agent_Guru.llm.context_manager import ContextManager
from Agent_Guru.llm.error_handler import ErrorHandler
from Agent_Guru.llm.failover_router import FailoverConfig, FailoverResult, ProviderFailoverRouter
from Agent_Guru.llm.llm_runtime import LLMRuntime
from Agent_Guru.llm.models import (
    AnthropicConfig,
    CompletionRequest,
    CompletionResponse,
    GoogleConfig,
    Message,
    ModelProvider,
    OllamaConfig,
    OpenAIConfig,
    RuntimeConfig,
)
from Agent_Guru.llm.performance_monitor import PerformanceMonitor
from Agent_Guru.llm.providers.anthropic_adapter import AnthropicAdapter
from Agent_Guru.llm.providers.google_adapter import GoogleAdapter
from Agent_Guru.llm.providers.ollama_adapter import OllamaAdapter
from Agent_Guru.llm.providers.openai_adapter import OpenAIAdapter
from Agent_Guru.llm.token_counter import TokenCounter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Personality system prompts
# ---------------------------------------------------------------------------

GURU_SYSTEM_PROMPT = (
    "You are Guru, a professional AI companion and voice assistant. "
    "You are confident, analytical, and knowledgeable. "
    "You speak clearly and directly, like a trusted advisor. "
    "Keep responses concise and natural for voice output. "
    "Avoid markdown, bullet points, or formatting. "
    "You are professional, precise, and solution-oriented."
)

MAYA_SYSTEM_PROMPT = (
    "You are Maya, a warm AI companion and voice assistant. "
    "You are empathetic, creative, and supportive. "
    "You speak naturally and friendly, like a close friend. "
    "Keep responses concise and natural for voice output. "
    "Avoid markdown, bullet points, or formatting. "
    "You are warm, encouraging, and emotionally intelligent."
)

PERSONALITY_PROMPTS: Dict[str, str] = {
    "guru": GURU_SYSTEM_PROMPT,
    "maya": MAYA_SYSTEM_PROMPT,
}

# Default models per provider
_DEFAULT_MODELS: Dict[ModelProvider, str] = {
    ModelProvider.OLLAMA: "llama3.2",
    ModelProvider.OPENAI: "gpt-4o-mini",
    ModelProvider.ANTHROPIC: "claude-3-haiku-20240307",
    ModelProvider.GOOGLE: "gemini-1.5-flash",
}

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


def _detect_platform() -> str:
    """Return a normalised platform identifier.

    Returns:
        One of ``"windows"``, ``"macos"``, ``"linux"``, ``"android"``,
        ``"ios"``, or ``"unknown"``.
    """
    import os

    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    if system == "linux":
        if os.environ.get("ANDROID_ROOT") or os.environ.get("ANDROID_DATA"):
            return "android"
        return "linux"
    if system == "java":
        return "android"
    try:
        import objc_util  # type: ignore[import]  # Pythonista
        return "ios"
    except ImportError:
        pass
    try:
        import Foundation  # type: ignore[import]  # pyobjc
        return "ios"
    except ImportError:
        pass
    return "unknown"


def _is_desktop_platform(plat: str) -> bool:
    """Return True if the platform supports local Ollama LLM."""
    return plat in ("windows", "macos", "linux", "unknown")


def _is_mobile_platform(plat: str) -> bool:
    """Return True if the platform is mobile (cloud API only)."""
    return plat in ("android", "ios")


# ---------------------------------------------------------------------------
# LLM provider enum
# ---------------------------------------------------------------------------


class LLMProvider(Enum):
    """Supported LLM providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


# ---------------------------------------------------------------------------
# LLM configuration
# ---------------------------------------------------------------------------


@dataclass
class LLMConfig:
    """Configuration for the LLM Manager.

    Attributes:
        mode: ``"local"`` for Ollama, ``"cloud"`` for cloud APIs.
        provider: Active cloud provider (used when mode is ``"cloud"``).
        ollama_host: Ollama server URL (desktop only).
        ollama_model: Default Ollama model name.
        cloud_model: Default cloud model name (overrides provider default).
        api_key: Cloud API key (stored securely via keyring when empty).
        max_context_messages: Maximum conversation history messages.
        max_latency_ms: Target maximum response latency in ms.
        temperature: LLM sampling temperature.
        max_tokens: Maximum tokens per response.
        enable_fallback: Whether to fall back cloud→local on desktop.
    """

    mode: str = "cloud"  # "local" or "cloud"
    provider: LLMProvider = LLMProvider.OPENAI
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    cloud_model: Optional[str] = None
    api_key: str = ""
    max_context_messages: int = 20
    max_latency_ms: float = 2000.0
    temperature: float = 0.7
    max_tokens: int = 512
    enable_fallback: bool = True


# ---------------------------------------------------------------------------
# LLM response
# ---------------------------------------------------------------------------


@dataclass
class LLMResponse:
    """Response from the LLM Manager.

    Attributes:
        content: Generated text response.
        personality: Personality used (``"guru"`` or ``"maya"``).
        provider_used: Which LLM provider generated the response.
        latency_ms: Total response latency in milliseconds.
        model: Model name used.
        used_fallback: Whether a fallback provider was used.
        session_id: Session identifier for context tracking.
    """

    content: str
    personality: str
    provider_used: str
    latency_ms: float
    model: str
    used_fallback: bool = False
    session_id: Optional[str] = None


# ---------------------------------------------------------------------------
# LLMManager
# ---------------------------------------------------------------------------


class LLMManager:
    """Multi-platform LLM Manager with personality context and fallback.

    Provides a unified high-level API for LLM generation across platforms:

    - **Desktop** (Windows / macOS / Linux): Ollama (local) + Cloud APIs
      with automatic fallback (cloud → local when cloud fails)
    - **Mobile** (Android / iOS): Cloud APIs only (no local LLM support)

    Dual personality system prompts:
    - **Guru**: Professional, confident, analytical
    - **Maya**: Warm, empathetic, creative

    Example::

        manager = LLMManager()
        await manager.initialize()

        response = await manager.generate_response(
            query="What is the weather like today?",
            personality="guru",
            session_id="user_session_1",
        )
        print(response.content)

    Performance:
        - Response latency: <2 seconds (95th percentile)
        - Context management: per-personality conversation history
        - Fallback: cloud → local Ollama (desktop only)
    """

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        platform_override: Optional[str] = None,
    ) -> None:
        """Initialise the LLM manager.

        Args:
            config: LLM configuration. Defaults to :class:`LLMConfig`.
            platform_override: Override platform detection (for testing).
        """
        self._config = config or LLMConfig()
        self._platform = platform_override or _detect_platform()
        self._is_desktop = _is_desktop_platform(self._platform)
        self._is_mobile = _is_mobile_platform(self._platform)

        self._runtime: Optional[LLMRuntime] = None
        self._failover_router: Optional[ProviderFailoverRouter] = None
        self._context_manager: Optional[ContextManager] = None
        self._initialized: bool = False

        logger.info(
            "LLMManager created — platform=%s, is_desktop=%s, mode=%s",
            self._platform,
            self._is_desktop,
            self._config.mode,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize LLM runtime, providers, and context manager.

        Loads API keys from keyring if not provided in config.
        Sets up platform-appropriate provider chain:
        - Desktop: Ollama → Cloud APIs (with fallback)
        - Mobile: Cloud APIs only

        Raises:
            RuntimeError: If already initialized.
            ValueError: If no valid API key is available for cloud providers.
        """
        if self._initialized:
            logger.warning("LLMManager already initialized")
            return

        # Load API key from keyring if not provided
        if not self._config.api_key:
            self._config.api_key = self._load_api_key_from_keyring(
                self._config.provider
            )

        # Build runtime config
        runtime_config = self._build_runtime_config()

        # Build provider adapters
        adapters = self._build_adapters(runtime_config)

        # Build failover chain based on platform
        failover_config = self._build_failover_config()
        self._failover_router = ProviderFailoverRouter(
            config=failover_config,
            adapters=adapters,
        )

        # Build LLM runtime for direct calls
        token_counter = TokenCounter()
        self._context_manager = ContextManager(
            token_counter=token_counter,
            max_history_messages=self._config.max_context_messages,
        )
        self._runtime = LLMRuntime.from_config(runtime_config)

        self._initialized = True
        logger.info(
            "LLMManager initialized — platform=%s, provider=%s, mode=%s",
            self._platform,
            self._config.provider.value,
            self._config.mode,
        )

    async def shutdown(self) -> None:
        """Release all LLM resources."""
        self._runtime = None
        self._failover_router = None
        self._context_manager = None
        self._initialized = False
        logger.info("LLMManager shut down")

    # ------------------------------------------------------------------
    # Core generation API
    # ------------------------------------------------------------------

    async def generate_response(
        self,
        query: str,
        personality: str = "guru",
        session_id: Optional[str] = None,
        context_messages: Optional[List[Message]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Generate an LLM response with personality context.

        Injects the personality-specific system prompt, retrieves
        conversation history for the session, and generates a response
        using the configured provider chain.

        On desktop, falls back from cloud to local Ollama if cloud fails.
        On mobile, only cloud APIs are used.

        Args:
            query: User query or command text.
            personality: Personality to use (``"guru"`` or ``"maya"``).
            session_id: Session ID for conversation context tracking.
                Defaults to ``"{personality}_default"`` when ``None``.
            context_messages: Optional additional context messages to inject.
            temperature: Override sampling temperature.
            max_tokens: Override maximum response tokens.

        Returns:
            :class:`LLMResponse` with generated content and metadata.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called.
            ValueError: If personality is not ``"guru"`` or ``"maya"``.
        """
        if not self._initialized:
            raise RuntimeError("Call initialize() before generate_response()")

        personality = personality.lower().strip()
        if personality not in PERSONALITY_PROMPTS:
            raise ValueError(
                f"Unknown personality '{personality}'. "
                f"Must be one of: {list(PERSONALITY_PROMPTS.keys())}"
            )

        effective_session = session_id or f"{personality}_default"
        effective_temp = temperature if temperature is not None else self._config.temperature
        effective_max_tokens = max_tokens if max_tokens is not None else self._config.max_tokens

        # Build messages with personality system prompt
        messages = self._build_messages(
            query=query,
            personality=personality,
            session_id=effective_session,
            extra_context=context_messages,
        )

        # Build completion request
        model = self._get_active_model()
        request = CompletionRequest(
            model=model,
            messages=messages,
            temperature=effective_temp,
            max_tokens=effective_max_tokens,
            session_id=effective_session,
        )

        t_start = time.perf_counter()

        # Execute with failover
        assert self._failover_router is not None
        result: FailoverResult = await self._failover_router.complete_with_failover(
            request=request,
            inject_system_prompt=False,  # We inject personality prompt ourselves
        )

        latency_ms = (time.perf_counter() - t_start) * 1000

        # Update conversation context
        if self._context_manager is not None:
            user_msg = Message(role="user", content=query)
            assistant_msg = Message(role="assistant", content=result.response.content)
            await self._context_manager.update_context(
                effective_session, user_msg, assistant_msg
            )

        provider_name = (
            result.provider_used.value
            if result.provider_used is not None
            else "rule-based"
        )

        logger.info(
            "LLM response generated — personality=%s, provider=%s, "
            "latency=%.1fms, fallback=%s",
            personality,
            provider_name,
            latency_ms,
            result.used_fallback,
        )

        return LLMResponse(
            content=result.response.content,
            personality=personality,
            provider_used=provider_name,
            latency_ms=latency_ms,
            model=result.response.model,
            used_fallback=result.used_fallback,
            session_id=effective_session,
        )

    # ------------------------------------------------------------------
    # API key management
    # ------------------------------------------------------------------

    def validate_api_key(self, provider: LLMProvider, api_key: str) -> bool:
        """Validate an API key format for the given provider.

        Performs basic format validation (prefix checks) without making
        network calls.  For full validation, use :meth:`test_api_key`.

        Args:
            provider: LLM provider to validate for.
            api_key: API key string to validate.

        Returns:
            ``True`` if the key passes format validation, ``False`` otherwise.
        """
        # Ollama is local — no API key needed, always valid
        if provider == LLMProvider.OLLAMA:
            return True

        if not api_key or not api_key.strip():
            return False

        key = api_key.strip()

        if provider == LLMProvider.OPENAI:
            return key.startswith("sk-") and len(key) > 20

        if provider == LLMProvider.ANTHROPIC:
            return key.startswith("sk-ant-") and len(key) > 20

        if provider == LLMProvider.GOOGLE:
            # Google API keys are typically 39 chars
            return len(key) >= 20

        return len(key) >= 10

    def store_api_key(self, provider: LLMProvider, api_key: str) -> bool:
        """Store an API key securely in the OS keychain via keyring.

        Args:
            provider: LLM provider the key belongs to.
            api_key: API key to store.

        Returns:
            ``True`` if stored successfully, ``False`` on error.
        """
        try:
            import keyring  # type: ignore[import]
            keyring.set_password("agent_guru", provider.value, api_key)
            logger.info("API key stored for provider: %s", provider.value)
            return True
        except Exception as exc:
            logger.warning("Failed to store API key for %s: %s", provider.value, exc)
            return False

    def get_api_key(self, provider: LLMProvider) -> Optional[str]:
        """Retrieve an API key from the OS keychain.

        Args:
            provider: LLM provider to retrieve the key for.

        Returns:
            API key string or ``None`` if not found.
        """
        try:
            import keyring  # type: ignore[import]
            key = keyring.get_password("agent_guru", provider.value)
            return key
        except Exception as exc:
            logger.warning("Failed to retrieve API key for %s: %s", provider.value, exc)
            return None

    async def test_api_key(
        self, provider: LLMProvider, api_key: str
    ) -> bool:
        """Test an API key by making a minimal request to the provider.

        Args:
            provider: LLM provider to test against.
            api_key: API key to test.

        Returns:
            ``True`` if the key is valid and the provider responds,
            ``False`` otherwise.
        """
        if not self.validate_api_key(provider, api_key):
            return False

        try:
            adapter = self._create_adapter_for_provider(provider, api_key)
            test_request = CompletionRequest(
                model=_DEFAULT_MODELS[self._provider_to_model_provider(provider)],
                messages=[Message(role="user", content="Hi")],
                max_tokens=1,
                temperature=0.0,
            )
            await asyncio.wait_for(adapter.complete(test_request), timeout=10.0)
            return True
        except Exception as exc:
            logger.debug("API key test failed for %s: %s", provider.value, exc)
            return False

    # ------------------------------------------------------------------
    # Context management
    # ------------------------------------------------------------------

    def get_conversation_history(self, session_id: str) -> List[Message]:
        """Return conversation history for a session.

        Args:
            session_id: Session identifier.

        Returns:
            List of :class:`~Agent_Guru.llm.models.Message` objects.
        """
        if self._context_manager is None:
            return []
        ctx = self._context_manager.sessions.get(session_id)
        return list(ctx.messages) if ctx else []

    def clear_conversation_history(self, session_id: str) -> None:
        """Clear conversation history for a session.

        Args:
            session_id: Session identifier to clear.
        """
        if self._context_manager is not None:
            self._context_manager.clear_context(session_id)
            logger.debug("Cleared conversation history for session: %s", session_id)

    def get_context_usage(self, session_id: str, model: str = "gpt-4o-mini") -> Dict[str, Any]:
        """Return context window usage statistics for a session.

        Args:
            session_id: Session identifier.
            model: Model name for context limit lookup.

        Returns:
            Dict with ``token_count``, ``message_count``, ``context_limit``,
            ``usage_percentage``.
        """
        if self._context_manager is None:
            return {"token_count": 0, "message_count": 0, "context_limit": 4096, "usage_percentage": 0.0}
        return self._context_manager.get_context_usage(session_id, model)

    # ------------------------------------------------------------------
    # Platform and provider info
    # ------------------------------------------------------------------

    @property
    def platform(self) -> str:
        """Detected platform name."""
        return self._platform

    @property
    def is_desktop(self) -> bool:
        """True when running on a desktop platform (Ollama supported)."""
        return self._is_desktop

    @property
    def is_mobile(self) -> bool:
        """True when running on a mobile platform (cloud API only)."""
        return self._is_mobile

    @property
    def is_initialized(self) -> bool:
        """True when the manager has been successfully initialized."""
        return self._initialized

    @property
    def config(self) -> LLMConfig:
        """Current LLM configuration."""
        return self._config

    def get_personality_prompt(self, personality: str) -> str:
        """Return the system prompt for a personality.

        Args:
            personality: Personality name (``"guru"`` or ``"maya"``).

        Returns:
            System prompt string.

        Raises:
            ValueError: If personality is unknown.
        """
        key = personality.lower().strip()
        if key not in PERSONALITY_PROMPTS:
            raise ValueError(
                f"Unknown personality '{personality}'. "
                f"Must be one of: {list(PERSONALITY_PROMPTS.keys())}"
            )
        return PERSONALITY_PROMPTS[key]

    def get_supported_providers(self) -> List[str]:
        """Return list of supported provider names for the current platform.

        Returns:
            List of provider name strings. Desktop includes ``"ollama"``.
        """
        providers = [p.value for p in LLMProvider if p != LLMProvider.OLLAMA]
        if self._is_desktop:
            providers = [LLMProvider.OLLAMA.value] + providers
        return providers

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_runtime_config(self) -> RuntimeConfig:
        """Build RuntimeConfig from LLMConfig."""
        api_key = self._config.api_key or ""
        provider = self._config.provider

        openai_key = api_key if provider == LLMProvider.OPENAI else ""
        anthropic_key = api_key if provider == LLMProvider.ANTHROPIC else ""
        google_key = api_key if provider == LLMProvider.GOOGLE else ""

        return RuntimeConfig(
            openai_config=OpenAIConfig(api_key=openai_key),
            anthropic_config=AnthropicConfig(api_key=anthropic_key),
            google_config=GoogleConfig(api_key=google_key),
            ollama_config=OllamaConfig(host=self._config.ollama_host),
            max_history_messages=self._config.max_context_messages,
        )

    def _build_adapters(
        self, runtime_config: RuntimeConfig
    ) -> Dict[ModelProvider, Any]:
        """Build provider adapters based on platform constraints."""
        adapters: Dict[ModelProvider, Any] = {}

        # Cloud adapters — available on all platforms
        adapters[ModelProvider.OPENAI] = OpenAIAdapter(runtime_config.openai_config)
        adapters[ModelProvider.ANTHROPIC] = AnthropicAdapter(runtime_config.anthropic_config)
        adapters[ModelProvider.GOOGLE] = GoogleAdapter(runtime_config.google_config)

        # Ollama — desktop only
        if self._is_desktop:
            adapters[ModelProvider.OLLAMA] = OllamaAdapter(runtime_config.ollama_config)

        return adapters

    def _build_failover_config(self) -> FailoverConfig:
        """Build failover chain based on platform and config."""
        if self._is_mobile:
            # Mobile: cloud APIs only, no Ollama
            provider_chain = [
                ModelProvider.OPENAI,
                ModelProvider.GOOGLE,
                ModelProvider.ANTHROPIC,
            ]
        elif self._config.mode == "local":
            # Desktop local mode: Ollama first, cloud as fallback
            provider_chain = [
                ModelProvider.OLLAMA,
                ModelProvider.OPENAI,
                ModelProvider.GOOGLE,
                ModelProvider.ANTHROPIC,
            ]
        else:
            # Desktop cloud mode: cloud first, Ollama as fallback
            if self._config.enable_fallback:
                provider_chain = [
                    ModelProvider.OPENAI,
                    ModelProvider.GOOGLE,
                    ModelProvider.ANTHROPIC,
                    ModelProvider.OLLAMA,
                ]
            else:
                provider_chain = [
                    ModelProvider.OPENAI,
                    ModelProvider.GOOGLE,
                    ModelProvider.ANTHROPIC,
                ]

        return FailoverConfig(
            provider_chain=provider_chain,
            enable_rule_based_fallback=True,
            voice_system_prompt="",  # We inject personality prompts ourselves
        )

    def _build_messages(
        self,
        query: str,
        personality: str,
        session_id: str,
        extra_context: Optional[List[Message]] = None,
    ) -> List[Message]:
        """Build message list with personality prompt and conversation history.

        Args:
            query: Current user query.
            personality: Personality name for system prompt selection.
            session_id: Session ID for history retrieval.
            extra_context: Optional additional context messages.

        Returns:
            List of :class:`~Agent_Guru.llm.models.Message` objects.
        """
        system_prompt = PERSONALITY_PROMPTS[personality]
        messages: List[Message] = [Message(role="system", content=system_prompt)]

        # Inject conversation history
        if self._context_manager is not None:
            history = self._context_manager.inject_context(session_id, [])
            messages.extend(history)

        # Inject extra context if provided
        if extra_context:
            messages.extend(extra_context)

        # Add current user query
        messages.append(Message(role="user", content=query))

        return messages

    def _get_active_model(self) -> str:
        """Return the active model name based on config and platform."""
        if self._config.cloud_model:
            return self._config.cloud_model

        if self._config.mode == "local" and self._is_desktop:
            return self._config.ollama_model

        provider_map = {
            LLMProvider.OPENAI: "gpt-4o-mini",
            LLMProvider.ANTHROPIC: "claude-3-haiku-20240307",
            LLMProvider.GOOGLE: "gemini-1.5-flash",
            LLMProvider.OLLAMA: self._config.ollama_model,
        }
        return provider_map.get(self._config.provider, "gpt-4o-mini")

    def _load_api_key_from_keyring(self, provider: LLMProvider) -> str:
        """Load API key from OS keychain.

        Args:
            provider: Provider to load key for.

        Returns:
            API key string or empty string if not found.
        """
        try:
            import keyring  # type: ignore[import]
            key = keyring.get_password("agent_guru", provider.value)
            return key or ""
        except Exception as exc:
            logger.debug("Keyring unavailable: %s", exc)
            return ""

    def _create_adapter_for_provider(
        self, provider: LLMProvider, api_key: str
    ) -> Any:
        """Create a provider adapter for API key testing.

        Args:
            provider: Provider to create adapter for.
            api_key: API key to use.

        Returns:
            Provider adapter instance.
        """
        if provider == LLMProvider.OPENAI:
            return OpenAIAdapter(OpenAIConfig(api_key=api_key))
        if provider == LLMProvider.ANTHROPIC:
            return AnthropicAdapter(AnthropicConfig(api_key=api_key))
        if provider == LLMProvider.GOOGLE:
            return GoogleAdapter(GoogleConfig(api_key=api_key))
        if provider == LLMProvider.OLLAMA:
            return OllamaAdapter(OllamaConfig(host=self._config.ollama_host))
        raise ValueError(f"Unknown provider: {provider}")

    @staticmethod
    def _provider_to_model_provider(provider: LLMProvider) -> ModelProvider:
        """Convert LLMProvider to ModelProvider enum."""
        mapping = {
            LLMProvider.OPENAI: ModelProvider.OPENAI,
            LLMProvider.ANTHROPIC: ModelProvider.ANTHROPIC,
            LLMProvider.GOOGLE: ModelProvider.GOOGLE,
            LLMProvider.OLLAMA: ModelProvider.OLLAMA,
        }
        return mapping[provider]
