"""
LLM System - Multi-Provider AI Runtime with Security-First Design

Production-grade LLM system for YuktOS GURU with:
- Multiple local models (Ollama)
- Cloud API providers (OpenAI, Gemini)
- Runtime provider switching
- Task-based routing
- Comprehensive security controls
- Audit logging integration

CRITICAL SECURITY INVARIANTS:
- NO MODEL may directly control keyboard, mouse, filesystem, or OS
- NO LLM may execute actions
- ALL execution passes through Authority State Machine
- ALL failures MUST fail closed (LOCKED_LISTEN_ONLY)
- NO silent fallbacks without explicit configuration

Models are replaceable. Authority is sacred. Execution is earned.
"""

# Legacy adapter (for backward compatibility) - removed due to circular import
# from .adapter import LLMAdapter

# Configuration management
from .config_manager import LLMConfigManager, LLMConfigPaths, get_llm_config_manager

# Exceptions
from .exceptions import (
    AuthenticationError,
    CapabilityDetectionError,
    ConfigurationError,
    IntentValidationError,
    IsolationBreachError,
    LLMAdapterError,
    LLMException,
    ModelNotFoundError,
    ModelRouterError,
    NetworkError,
    ProviderError,
    ProviderRegistrationError,
    RateLimitExceededError,
    TaskRoutingError,
)
from .gemini_provider import GeminiProvider

# Integration layer
from .integration import LLMSystemIntegration, get_llm_integration, initialize_llm_system

# Intent processing
from .intent import IntentType, IntentValidator, StructuredIntent

# Core model router components
from .model_router import (
    ModelRouter,
    ProviderConfiguration,
    ProviderType,
    RouterConfiguration,
    TaskConfiguration,
    TaskType,
    get_model_router,
)

# Provider implementations
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from .providers import GeminiProvider as LegacyGeminiProvider
from .providers import LLMProvider, LocalProvider, ProviderCapabilities, ProviderStatus

# Safety
from .safety import ContentSafetyFilter, LLMSafetyEngine, ResponseSanitizer, SafeResponse

__all__ = [
    # Core model router
    "ModelRouter",
    "RouterConfiguration",
    "TaskType",
    "ProviderType",
    "TaskConfiguration",
    "ProviderConfiguration",
    "get_model_router",
    # Integration
    "LLMSystemIntegration",
    "get_llm_integration",
    "initialize_llm_system",
    # Configuration
    "LLMConfigManager",
    "LLMConfigPaths",
    "get_llm_config_manager",
    # Provider implementations
    "OllamaProvider",
    "OpenAIProvider",
    "GeminiProvider",
    # Legacy adapter (backward compatibility) - removed due to circular import
    # "LLMAdapter",
    "LLMProvider",
    "LegacyGeminiProvider",
    "LocalProvider",
    "ProviderCapabilities",
    "ProviderStatus",
    # Intent processing
    "IntentType",
    "IntentValidator",
    "StructuredIntent",
    # Safety
    "LLMSafetyEngine",
    "ContentSafetyFilter",
    "ResponseSanitizer",
    "SafeResponse",
    # Exceptions
    "LLMException",
    "ModelRouterError",
    "ProviderError",
    "ProviderRegistrationError",
    "AuthenticationError",
    "RateLimitExceededError",
    "NetworkError",
    "ModelNotFoundError",
    "CapabilityDetectionError",
    "ConfigurationError",
    "TaskRoutingError",
    "IntentValidationError",
    "IsolationBreachError",
    "LLMAdapterError",
]

__version__ = "1.0.0"
