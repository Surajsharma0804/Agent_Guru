"""LLM Manager for Agent Guru.

This is the high-level wrapper over the LLM runtime. It handles:
- Personality-specific system prompts (Guru = professional, Maya = warm)
- Conversation context per session
- Provider selection with graceful fallback to Ollama

Cloud providers (OpenAI, Anthropic, Google) are supported if their adapter
files exist and an API key is configured. If not, we fall back to Ollama
without crashing. The assistant should always work out of the box.

Currently active: gemma3:4b via Ollama (best for 4GB VRAM).
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from Agent_Guru.llm.failover_router import FailoverConfig, FailoverResult, ProviderFailoverRouter
from Agent_Guru.llm.llm_runtime import LLMRuntime
from Agent_Guru.llm.models import (
    CompletionRequest,
    Message,
    ModelProvider,
    OllamaConfig,
    RuntimeConfig,
)
from Agent_Guru.llm.providers.ollama_adapter import OllamaAdapter

# Cloud adapters are optional — only available if the adapter files exist.
# We import them lazily so a missing file doesn't crash the whole module.
try:
    from Agent_Guru.llm.providers.openai_adapter import (
        OpenAIAdapter as _OpenAIAdapter,  # type: ignore[import]
    )

    _HAS_OPENAI = True
except ImportError:
    _OpenAIAdapter = None  # type: ignore[assignment,misc]
    _HAS_OPENAI = False

try:
    from Agent_Guru.llm.providers.anthropic_adapter import (
        AnthropicAdapter as _AnthropicAdapter,  # type: ignore[import]
    )

    _HAS_ANTHROPIC = True
except ImportError:
    _AnthropicAdapter = None  # type: ignore[assignment,misc]
    _HAS_ANTHROPIC = False

try:
    from Agent_Guru.llm.providers.google_adapter import (
        GoogleAdapter as _GoogleAdapter,  # type: ignore[import]
    )

    _HAS_GOOGLE = True
except ImportError:
    _GoogleAdapter = None  # type: ignore[assignment,misc]
    _HAS_GOOGLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Personality system prompts
# ---------------------------------------------------------------------------

GURU_SYSTEM_PROMPT = (
    "You are Guru, a professional AI voice assistant. "
    "You are confident, analytical, and knowledgeable. "
    "Speak clearly and directly, like a trusted advisor. "
    "Keep responses concise and natural for voice output. "
    "No markdown, no bullet points, no formatting."
)

MAYA_SYSTEM_PROMPT = (
    "You are Maya, a warm AI voice assistant. "
    "You are empathetic, creative, and supportive. "
    "Speak naturally and friendly, like a close friend. "
    "Keep responses concise and natural for voice output. "
    "No markdown, no bullet points, no formatting."
)

PERSONALITY_PROMPTS: dict[str, str] = {
    "guru": GURU_SYSTEM_PROMPT,
    "maya": MAYA_SYSTEM_PROMPT,
}

# Default model names per provider (used for API key testing)
_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-haiku-20240307",
    "google": "gemini-1.5-flash",
    "ollama": "gemma3:4b",
}


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


def _detect_platform() -> str:
    """Return a normalised platform identifier."""
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
        import objc_util  # type: ignore[import]  # noqa: F401

        return "ios"
    except ImportError:
        pass
    return "unknown"


def _is_desktop_platform(plat: str) -> bool:
    """Return True if the platform supports local Ollama."""
    return plat in ("windows", "macos", "linux", "unknown")


def _is_mobile_platform(plat: str) -> bool:
    """Return True if the platform is mobile (cloud API only)."""
    return plat in ("android", "ios")


# ---------------------------------------------------------------------------
# Enums and dataclasses
# ---------------------------------------------------------------------------


class LLMProvider(Enum):
    """Supported LLM providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


@dataclass
class LLMConfig:
    """Configuration for the LLM Manager."""

    mode: str = "local"  # "local" or "cloud"
    provider: LLMProvider = LLMProvider.OLLAMA
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    cloud_model: str | None = None
    api_key: str = ""
    max_context_messages: int = 20
    max_latency_ms: float = 2000.0
    temperature: float = 0.7
    max_tokens: int = 512
    enable_fallback: bool = True


@dataclass
class LLMResponse:
    """Response from the LLM Manager."""

    content: str
    personality: str
    provider_used: str
    latency_ms: float
    model: str
    used_fallback: bool = False
    session_id: str | None = None


# ---------------------------------------------------------------------------
# LLMManager
# ---------------------------------------------------------------------------


class LLMManager:
    """High-level LLM manager with personality context and provider fallback.

    Desktop: Ollama (local) is the primary provider. Cloud APIs are used
    if an API key is set and the adapter is installed.

    Mobile: Cloud APIs only (no local LLM support).

    Example::

        manager = LLMManager()
        await manager.initialize()
        response = await manager.generate_response(
            query="What is the weather like today?",
            personality="guru",
        )
        print(response.content)
    """

    def __init__(
        self,
        config: LLMConfig | None = None,
        platform_override: str | None = None,
    ) -> None:
        self._config = config or LLMConfig()
        self._platform = platform_override or _detect_platform()
        self._is_desktop = _is_desktop_platform(self._platform)
        self._is_mobile = _is_mobile_platform(self._platform)

        # Pick up OLLAMA_MODEL / OLLAMA_HOST from env if not explicitly set
        env_model = os.environ.get("OLLAMA_MODEL", "").strip()
        if env_model:
            self._config.ollama_model = env_model
        env_host = os.environ.get("OLLAMA_HOST", "").strip()
        if env_host:
            self._config.ollama_host = env_host

        self._runtime: LLMRuntime | None = None
        self._failover_router: ProviderFailoverRouter | None = None
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
        """Initialize LLM runtime and provider chain.

        Auto-detects available providers. If no cloud API key is found
        and we're on desktop, silently switches to local Ollama mode.
        """
        if self._initialized:
            logger.warning("LLMManager already initialized")
            return

        # Load API key from keyring if not provided
        if not self._config.api_key:
            self._config.api_key = self._load_api_key_from_keyring(self._config.provider)

        # Auto-detect: if no cloud key is set anywhere, use local Ollama.
        if self._is_desktop and self._config.mode == "cloud":
            has_any_cloud_key = any(
                [
                    os.environ.get("OPENAI_API_KEY", "").strip(),
                    os.environ.get("ANTHROPIC_API_KEY", "").strip(),
                    os.environ.get("GOOGLE_API_KEY", "").strip(),
                    os.environ.get("GEMINI_API_KEY", "").strip(),
                    os.environ.get("DEEPSEEK_API_KEY", "").strip(),
                    (self._config.api_key and self._config.provider != LLMProvider.OLLAMA),
                ],
            )
            if not has_any_cloud_key:
                logger.info(
                    "No cloud API key found — switching to local Ollama mode (model: %s at %s)",
                    self._config.ollama_model,
                    self._config.ollama_host,
                )
                self._config.mode = "local"
                self._config.provider = LLMProvider.OLLAMA

        # Build runtime config (Ollama only — cloud configs added if adapters exist)
        runtime_config = self._build_runtime_config()

        # Build provider adapters
        adapters = self._build_adapters()

        # Build failover chain
        failover_config = self._build_failover_config()
        self._failover_router = ProviderFailoverRouter(
            config=failover_config,
            adapters=adapters,
        )

        # Build LLM runtime for direct calls
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
        self._initialized = False
        logger.info("LLMManager shut down")

    # ------------------------------------------------------------------
    # Core generation API
    # ------------------------------------------------------------------

    async def generate_response(
        self,
        query: str,
        personality: str = "guru",
        session_id: str | None = None,
        context_messages: list[Message] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate an LLM response with personality context.

        Args:
            query: User query or command text.
            personality: "guru" or "maya".
            session_id: Session ID for conversation context tracking.
            context_messages: Optional additional context messages.
            temperature: Override sampling temperature.
            max_tokens: Override maximum response tokens.

        Returns:
            LLMResponse with generated content and metadata.

        """
        if not self._initialized:
            msg = "Call initialize() before generate_response()"
            raise RuntimeError(msg)

        personality = personality.lower().strip()
        if personality not in PERSONALITY_PROMPTS:
            msg = (
                f"Unknown personality '{personality}'. "
                f"Must be one of: {list(PERSONALITY_PROMPTS.keys())}"
            )
            raise ValueError(
                msg,
            )

        effective_session = session_id or f"{personality}_default"
        effective_temp = temperature if temperature is not None else self._config.temperature
        effective_max_tokens = max_tokens if max_tokens is not None else self._config.max_tokens

        messages = self._build_messages(
            query=query,
            personality=personality,
            session_id=effective_session,
            extra_context=context_messages,
        )

        model = self._get_active_model()
        request = CompletionRequest(
            model=model,
            messages=messages,
            temperature=effective_temp,
            max_tokens=effective_max_tokens,
            session_id=effective_session,
        )

        t_start = time.perf_counter()

        if self._failover_router is None:
            msg = "LLMManager not initialized — call initialize() first"
            raise RuntimeError(msg)

        result: FailoverResult = await self._failover_router.complete_with_failover(
            request=request,
            inject_system_prompt=False,
        )

        latency_ms = (time.perf_counter() - t_start) * 1000

        # Update conversation context
        if self._runtime is not None and self._runtime.context_manager is not None:
            user_msg = Message(role="user", content=query)
            assistant_msg = Message(role="assistant", content=result.response.content)
            await self._runtime.context_manager.update_context(
                effective_session,
                user_msg,
                assistant_msg,
            )

        provider_name = (
            result.provider_used.value if result.provider_used is not None else "rule-based"
        )

        logger.info(
            "LLM response — personality=%s, provider=%s, latency=%.1fms, fallback=%s",
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
        """Validate an API key format for the given provider (no network call)."""
        if provider == LLMProvider.OLLAMA:
            return True  # Ollama is local — no key needed
        if not api_key or not api_key.strip():
            return False
        key = api_key.strip()
        if provider == LLMProvider.OPENAI:
            return key.startswith("sk-") and len(key) > 20  # noqa: PLR2004 - Threshold

        if provider == LLMProvider.ANTHROPIC:
            return key.startswith("sk-ant-") and len(key) > 20  # noqa: PLR2004 - Threshold

        if provider == LLMProvider.GOOGLE:
            return len(key) >= 20  # noqa: PLR2004 - Threshold

        return len(key) >= 10  # noqa: PLR2004 - Threshold


    def store_api_key(self, provider: LLMProvider, api_key: str) -> bool:
        """Store an API key securely in the OS keychain."""
        try:
            import keyring  # type: ignore[import]

            keyring.set_password("agent_guru", provider.value, api_key)
            logger.info("API key stored for provider: %s", provider.value)
            return True
        except Exception:
            logger.exception("Failed to store API key for %s", provider.value)
            return False

    def get_api_key(self, provider: LLMProvider) -> str | None:
        """Retrieve an API key from the OS keychain."""
        try:
            import keyring  # type: ignore[import]

            return keyring.get_password("agent_guru", provider.value)
        except Exception:
            logger.exception("Failed to retrieve API key for %s", provider.value)
            return None

    async def test_api_key(self, provider: LLMProvider, api_key: str) -> bool:
        """Test an API key by making a minimal request to the provider."""
        if not self.validate_api_key(provider, api_key):
            return False
        try:
            adapter = self._create_adapter_for_provider(provider, api_key)
            test_request = CompletionRequest(
                model=_DEFAULT_MODELS.get(provider.value, "gpt-4o-mini"),
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

    def get_conversation_history(self, session_id: str) -> list[Message]:
        """Return conversation history for a session."""
        if self._runtime is None or self._runtime.context_manager is None:
            return []
        ctx = self._runtime.context_manager.sessions.get(session_id)
        return list(ctx.messages) if ctx else []

    def clear_conversation_history(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        if self._runtime is not None and self._runtime.context_manager is not None:
            self._runtime.context_manager.clear_context(session_id)
            logger.debug("Cleared conversation history for session: %s", session_id)

    def get_context_usage(self, session_id: str, model: str = "gpt-4o-mini") -> dict[str, Any]:
        """Return context window usage statistics for a session."""
        if self._runtime is None or self._runtime.context_manager is None:
            return {
                "token_count": 0,
                "message_count": 0,
                "context_limit": 4096,
                "usage_percentage": 0.0,
            }
        return self._runtime.context_manager.get_context_usage(session_id, model)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def platform(self) -> str:
        return self._platform

    @property
    def is_desktop(self) -> bool:
        return self._is_desktop

    @property
    def is_mobile(self) -> bool:
        return self._is_mobile

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def config(self) -> LLMConfig:
        return self._config

    def get_personality_prompt(self, personality: str) -> str:
        """Return the system prompt for a personality."""
        key = personality.lower().strip()
        if key not in PERSONALITY_PROMPTS:
            msg = f"Unknown personality '{personality}'."
            raise ValueError(msg)
        return PERSONALITY_PROMPTS[key]

    def get_supported_providers(self) -> list[str]:
        """Return list of supported provider names for the current platform."""
        providers = [p.value for p in LLMProvider if p != LLMProvider.OLLAMA]
        if self._is_desktop:
            providers = [LLMProvider.OLLAMA.value, *providers]
        return providers

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_runtime_config(self) -> RuntimeConfig:
        """Build RuntimeConfig — only Ollama config needed right now."""
        return RuntimeConfig(
            ollama_config=OllamaConfig(host=self._config.ollama_host),
            max_history_messages=self._config.max_context_messages,
        )

    def _build_adapters(self) -> dict[ModelProvider, Any]:
        """Build provider adapters based on what's actually installed."""
        adapters: dict[ModelProvider, Any] = {}

        # Ollama is always available on desktop
        if self._is_desktop:
            adapters[ModelProvider.OLLAMA] = OllamaAdapter(
                OllamaConfig(host=self._config.ollama_host),
            )

        # Cloud adapters — only add if the adapter file exists
        if _HAS_OPENAI and _OpenAIAdapter is not None:
            try:
                adapters[ModelProvider.OPENAI] = _OpenAIAdapter(
                    type("OpenAIConfig", (), {"api_key": os.environ.get("OPENAI_API_KEY", "")})(),
                )
            except Exception as exc:
                logger.debug("OpenAI adapter skipped: %s", exc)

        if _HAS_ANTHROPIC and _AnthropicAdapter is not None:
            try:
                adapters[ModelProvider.ANTHROPIC] = _AnthropicAdapter(
                    type(
                        "AnthropicConfig",
                        (),
                        {"api_key": os.environ.get("ANTHROPIC_API_KEY", "")},
                    )(),
                )
            except Exception as exc:
                logger.debug("Anthropic adapter skipped: %s", exc)

        if _HAS_GOOGLE and _GoogleAdapter is not None:
            try:
                adapters[ModelProvider.GOOGLE] = _GoogleAdapter(
                    type(
                        "GoogleConfig",
                        (),
                        {
                            "api_key": os.environ.get(
                                "GOOGLE_API_KEY",
                                os.environ.get("GEMINI_API_KEY", ""),
                            ),
                        },
                    )(),
                )
            except Exception as exc:
                logger.debug("Google adapter skipped: %s", exc)

        return adapters

    def _build_failover_config(self) -> FailoverConfig:
        """Build failover chain based on platform and config."""
        if self._is_mobile:
            provider_chain = [ModelProvider.OPENAI, ModelProvider.GOOGLE, ModelProvider.ANTHROPIC]
        elif self._config.mode == "local":
            provider_chain = [
                ModelProvider.OLLAMA,
                ModelProvider.OPENAI,
                ModelProvider.GOOGLE,
                ModelProvider.ANTHROPIC,
            ]
        elif self._config.enable_fallback:
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
            voice_system_prompt="",
        )

    def _build_messages(
        self,
        query: str,
        personality: str,
        session_id: str,
        extra_context: list[Message] | None = None,
    ) -> list[Message]:
        """Build message list with personality prompt and conversation history."""
        system_prompt = PERSONALITY_PROMPTS[personality]
        messages: list[Message] = [Message(role="system", content=system_prompt)]

        if self._runtime is not None and self._runtime.context_manager is not None:
            history = self._runtime.context_manager.inject_context(session_id, [])
            messages.extend(history)

        if extra_context:
            messages.extend(extra_context)

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
        return provider_map.get(self._config.provider, self._config.ollama_model)

    def _load_api_key_from_keyring(self, provider: LLMProvider) -> str:
        """Load API key from OS keychain."""
        try:
            import keyring  # type: ignore[import]

            return keyring.get_password("agent_guru", provider.value) or ""
        except Exception as exc:
            logger.debug("Keyring unavailable: %s", exc)
            return ""

    def _create_adapter_for_provider(self, provider: LLMProvider, api_key: str) -> Any:  # noqa: ANN401
        """Create a provider adapter for API key testing."""
        if provider == LLMProvider.OPENAI:
            if not _HAS_OPENAI or _OpenAIAdapter is None:
                msg = "OpenAI adapter not installed"
                raise ValueError(msg)
            return _OpenAIAdapter(type("OpenAIConfig", (), {"api_key": api_key})())
        if provider == LLMProvider.ANTHROPIC:
            if not _HAS_ANTHROPIC or _AnthropicAdapter is None:
                msg = "Anthropic adapter not installed"
                raise ValueError(msg)
            return _AnthropicAdapter(type("AnthropicConfig", (), {"api_key": api_key})())
        if provider == LLMProvider.GOOGLE:
            if not _HAS_GOOGLE or _GoogleAdapter is None:
                msg = "Google adapter not installed"
                raise ValueError(msg)
            return _GoogleAdapter(type("GoogleConfig", (), {"api_key": api_key})())
        if provider == LLMProvider.OLLAMA:
            return OllamaAdapter(OllamaConfig(host=self._config.ollama_host))
        msg = f"Unknown provider: {provider}"
        raise ValueError(msg)

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
