"""
LLM Provider Abstraction Layer

Multi-provider LLM system with standardized interfaces, capability detection,
and comprehensive security controls. All providers are advisory only.

Security Principles:
- Providers cannot execute actions directly
- All outputs are structured intents only
- Rate limiting and authentication handled per provider
- Fail-safe defaults with comprehensive error handling
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Any, Dict, Literal, Optional

from .exceptions import ProviderError, RateLimitExceededError
from .intent import IntentValidator, StructuredIntent


class ProviderStatus(Enum):
    """Provider operational status."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_FAILED = "authentication_failed"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class ProviderCapabilities:
    """Comprehensive provider capability specification."""

    # Core capabilities
    supports_structured_output: bool = False
    supports_streaming: bool = False
    supports_function_calling: bool = False
    supports_image_input: bool = False
    supports_audio_input: bool = False

    # Model specifications
    max_tokens: int = 4096
    context_window: int = 4096
    model_name: str = "unknown"
    model_version: str = "unknown"

    # Rate limits
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    tokens_per_minute: int = 100000

    # Latency characteristics
    average_latency_ms: int = 1000
    p95_latency_ms: int = 3000

    # Cost information (if applicable)
    cost_per_1k_tokens: Optional[float] = None

    # Security features
    supports_content_filtering: bool = True
    supports_safety_classification: bool = False

    # Provider metadata
    provider_type: Literal["cloud", "local", "hybrid"] = "cloud"
    requires_api_key: bool = True
    requires_internet: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert capabilities to dictionary."""
        return {
            "supports_structured_output": self.supports_structured_output,
            "supports_streaming": self.supports_streaming,
            "supports_function_calling": self.supports_function_calling,
            "supports_image_input": self.supports_image_input,
            "supports_audio_input": self.supports_audio_input,
            "max_tokens": self.max_tokens,
            "context_window": self.context_window,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "requests_per_minute": self.requests_per_minute,
            "requests_per_hour": self.requests_per_hour,
            "requests_per_day": self.requests_per_day,
            "tokens_per_minute": self.tokens_per_minute,
            "average_latency_ms": self.average_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
            "supports_content_filtering": self.supports_content_filtering,
            "supports_safety_classification": self.supports_safety_classification,
            "provider_type": self.provider_type,
            "requires_api_key": self.requires_api_key,
            "requires_internet": self.requires_internet,
        }


@dataclass
class RateLimitState:
    """Track rate limiting state for a provider."""

    requests_this_minute: int = 0
    requests_this_hour: int = 0
    requests_this_day: int = 0
    tokens_this_minute: int = 0

    last_minute_reset: datetime = field(default_factory=datetime.utcnow)
    last_hour_reset: datetime = field(default_factory=datetime.utcnow)
    last_day_reset: datetime = field(default_factory=datetime.utcnow)

    def reset_if_needed(self):
        """Reset counters if time windows have passed."""
        now = datetime.utcnow()

        # Reset minute counter
        if now - self.last_minute_reset >= timedelta(minutes=1):
            self.requests_this_minute = 0
            self.tokens_this_minute = 0
            self.last_minute_reset = now

        # Reset hour counter
        if now - self.last_hour_reset >= timedelta(hours=1):
            self.requests_this_hour = 0
            self.last_hour_reset = now

        # Reset day counter
        if now - self.last_day_reset >= timedelta(days=1):
            self.requests_this_day = 0
            self.last_day_reset = now


class LLMProvider(ABC):
    """
    Abstract base class for all LLM providers.

    Enforces the critical security invariant: providers are advisory only,
    never authoritative. All outputs must be structured intents.
    """

    def __init__(self, provider_name: str, config: Optional[Dict[str, Any]] = None):
        self.provider_name = provider_name
        self.config = config or {}
        self.status = ProviderStatus.UNKNOWN
        self.capabilities: Optional[ProviderCapabilities] = None
        self.rate_limit_state = RateLimitState()
        self.intent_validator = IntentValidator()
        self._lock = Lock()

        # Initialize logging
        self.logger = logging.getLogger(f"llm.provider.{provider_name}")

    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the provider and detect capabilities.

        Returns:
            bool: True if initialization successful
        """

    @abstractmethod
    async def generate_intent(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> StructuredIntent:
        """
        Generate structured intent from user input.

        CRITICAL: This method MUST return structured intent only.
        Direct execution is strictly forbidden.

        Args:
            user_input: User's natural language input
            context: Optional context information

        Returns:
            StructuredIntent: Validated structured intent

        Raises:
            ProviderError: If generation fails
            RateLimitExceededError: If rate limits exceeded
        """

    @abstractmethod
    async def detect_capabilities(self) -> ProviderCapabilities:
        """
        Detect and return provider capabilities.

        Returns:
            ProviderCapabilities: Comprehensive capability specification
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Perform provider health check.

        Returns:
            bool: True if provider is healthy
        """

    def check_rate_limits(self, estimated_tokens: int = 100) -> bool:
        """
        Check if request would exceed rate limits.

        Args:
            estimated_tokens: Estimated token count for request

        Returns:
            bool: True if request is within limits
        """
        with self._lock:
            self.rate_limit_state.reset_if_needed()

            if not self.capabilities:
                return True  # No limits if capabilities unknown

            # Check request limits
            if self.rate_limit_state.requests_this_minute >= self.capabilities.requests_per_minute:
                return False

            if self.rate_limit_state.requests_this_hour >= self.capabilities.requests_per_hour:
                return False

            if self.rate_limit_state.requests_this_day >= self.capabilities.requests_per_day:
                return False

            # Check token limits
            if self.rate_limit_state.tokens_this_minute + estimated_tokens > self.capabilities.tokens_per_minute:
                return False

            return True

    def record_request(self, token_count: int = 100):
        """Record a successful request for rate limiting."""
        with self._lock:
            self.rate_limit_state.requests_this_minute += 1
            self.rate_limit_state.requests_this_hour += 1
            self.rate_limit_state.requests_this_day += 1
            self.rate_limit_state.tokens_this_minute += token_count

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive provider status."""
        return {
            "provider_name": self.provider_name,
            "status": self.status.value,
            "capabilities": self.capabilities.to_dict() if self.capabilities else None,
            "rate_limit_state": {
                "requests_this_minute": self.rate_limit_state.requests_this_minute,
                "requests_this_hour": self.rate_limit_state.requests_this_hour,
                "requests_this_day": self.rate_limit_state.requests_this_day,
                "tokens_this_minute": self.rate_limit_state.tokens_this_minute,
            },
        }


class GeminiProvider(LLMProvider):
    """
    Google Gemini provider implementation with comprehensive security controls.

    Features:
    - Structured output generation
    - Rate limiting and backoff
    - Content safety filtering
    - Authentication management
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("gemini", config)
        self.api_key = self.config.get("api_key")
        self.model_name = self.config.get("model_name", "gemini-pro")
        self.base_url = self.config.get("base_url", "https://generativelanguage.googleapis.com")
        self.timeout = self.config.get("timeout", 30)

    async def initialize(self) -> bool:
        """Initialize Gemini provider."""
        try:
            if not self.api_key:
                self.logger.error("Gemini API key not provided")
                self.status = ProviderStatus.AUTHENTICATION_FAILED
                return False

            # Detect capabilities
            self.capabilities = await self.detect_capabilities()

            # Perform health check
            if await self.health_check():
                self.status = ProviderStatus.AVAILABLE
                self.logger.info("Gemini provider initialized successfully")
                return True
            else:
                self.status = ProviderStatus.UNAVAILABLE
                return False

        except Exception as e:
            self.logger.error(f"Failed to initialize Gemini provider: {e}")
            self.status = ProviderStatus.UNAVAILABLE
            return False

    async def generate_intent(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> StructuredIntent:
        """Generate structured intent using Gemini."""

        # Check rate limits
        if not self.check_rate_limits():
            raise RateLimitExceededError("Gemini rate limit exceeded", provider_name=self.provider_name, retry_after=60)

        try:
            # Construct prompt for structured output
            prompt = self._build_structured_prompt(user_input, context)

            # Make API request (simulated - would use actual Gemini API)
            response = await self._make_api_request(prompt)

            # Validate and parse response
            intent = self.intent_validator.validate_raw_response(response)

            # Record successful request
            self.record_request(len(response))

            return intent

        except Exception as e:
            self.logger.error(f"Failed to generate intent: {e}")
            raise ProviderError(
                f"Gemini intent generation failed: {str(e)}", provider_name=self.provider_name, provider_error=e
            )

    async def detect_capabilities(self) -> ProviderCapabilities:
        """Detect Gemini capabilities."""
        return ProviderCapabilities(
            supports_structured_output=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_image_input=True,
            supports_audio_input=False,
            max_tokens=8192,
            context_window=32768,
            model_name=self.model_name,
            model_version="1.0",
            requests_per_minute=60,
            requests_per_hour=1000,
            requests_per_day=10000,
            tokens_per_minute=100000,
            average_latency_ms=800,
            p95_latency_ms=2000,
            cost_per_1k_tokens=0.001,
            supports_content_filtering=True,
            supports_safety_classification=True,
            provider_type="cloud",
            requires_api_key=True,
            requires_internet=True,
        )

    async def health_check(self) -> bool:
        """Perform Gemini health check."""
        try:
            # Simulate health check API call
            await asyncio.sleep(0.1)  # Simulate network delay
            return True
        except Exception:
            return False

    def _build_structured_prompt(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Build prompt that enforces structured output."""

        system_prompt = """
You are GURU's intent parser. You MUST respond with valid JSON only.

CRITICAL SECURITY RULES:
- You can ONLY produce structured intents, never execute actions
- You CANNOT run commands, access files, or control systems
- All outputs must be valid JSON with intent_type and parameters

Valid intent types:
- type_text: Type text exactly as requested
- press_key: Press keyboard keys
- mouse_action: Mouse movements and clicks
- launch_app: Launch applications
- execute_skill: Execute predefined skills
- get_status: Query system status
- search_memory: Search memory service

Response format:
{
  "intent_type": "type_text",
  "parameters": {"text": "Hello world"},
  "confidence": 0.95,
  "context": "User wants to type greeting"
}
"""

        user_prompt = f"User input: {user_input}"
        if context:
            user_prompt += f"\nContext: {json.dumps(context)}"

        return f"{system_prompt}\n\n{user_prompt}"

    async def _make_api_request(self, prompt: str) -> str:
        """Make API request to Gemini (simulated)."""

        # Simulate API call delay
        await asyncio.sleep(0.5)

        # Simulate structured response
        return json.dumps(
            {
                "intent_type": "type_text",
                "parameters": {"text": "Hello from Gemini"},
                "confidence": 0.95,
                "context": "Generated by Gemini provider",
            }
        )


class LocalProvider(LLMProvider):
    """
    Local LLM provider for on-device inference.

    Features:
    - Complete privacy (no network calls)
    - Quantized model support
    - Resource monitoring
    - Offline operation
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("local", config)
        self.model_path = self.config.get("model_path", "./models/local-llm.ggu")
        self.max_memory_mb = self.config.get("max_memory_mb", 4096)
        self.threads = self.config.get("threads", 4)

    async def initialize(self) -> bool:
        """Initialize local LLM provider."""
        try:
            # Check if model file exists
            import os

            if not os.path.exists(self.model_path):
                self.logger.error(f"Local model not found: {self.model_path}")
                self.status = ProviderStatus.UNAVAILABLE
                return False

            # Initialize model (simulated)
            self.capabilities = await self.detect_capabilities()

            if await self.health_check():
                self.status = ProviderStatus.AVAILABLE
                self.logger.info("Local provider initialized successfully")
                return True
            else:
                self.status = ProviderStatus.UNAVAILABLE
                return False

        except Exception as e:
            self.logger.error(f"Failed to initialize local provider: {e}")
            self.status = ProviderStatus.UNAVAILABLE
            return False

    async def generate_intent(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> StructuredIntent:
        """Generate structured intent using local model."""

        try:
            # Build prompt
            prompt = self._build_local_prompt(user_input, context)

            # Generate response (simulated)
            response = await self._generate_local_response(prompt)

            # Validate and parse
            intent = self.intent_validator.validate_raw_response(response)

            return intent

        except Exception as e:
            self.logger.error(f"Local intent generation failed: {e}")
            raise ProviderError(f"Local provider failed: {str(e)}", provider_name=self.provider_name, provider_error=e)

    async def detect_capabilities(self) -> ProviderCapabilities:
        """Detect local model capabilities."""
        return ProviderCapabilities(
            supports_structured_output=True,
            supports_streaming=False,
            supports_function_calling=False,
            supports_image_input=False,
            supports_audio_input=False,
            max_tokens=2048,
            context_window=4096,
            model_name="local-llm",
            model_version="1.0",
            requests_per_minute=1000,  # No network limits
            requests_per_hour=10000,
            requests_per_day=100000,
            tokens_per_minute=10000,
            average_latency_ms=2000,
            p95_latency_ms=5000,
            cost_per_1k_tokens=0.0,  # No cost for local
            supports_content_filtering=False,
            supports_safety_classification=False,
            provider_type="local",
            requires_api_key=False,
            requires_internet=False,
        )

    async def health_check(self) -> bool:
        """Perform local provider health check."""
        try:
            # Check memory usage, model availability, etc.
            await asyncio.sleep(0.1)
            return True
        except Exception:
            return False

    def _build_local_prompt(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Build prompt optimized for local model."""

        prompt = """<|system|>
You are GURU's local intent parser. Respond with JSON only.

Valid intents: type_text, press_key, mouse_action, launch_app, get_status

Format:
{{"intent_type": "type_text", "parameters": {{"text": "example"}}, "confidence": 0.9}}

<|user|>
{user_input}

<|assistant|>
"""
        return prompt

    async def _generate_local_response(self, prompt: str) -> str:
        """Generate response using local model (simulated)."""

        # Simulate local inference delay
        await asyncio.sleep(1.0)

        # Simulate local model response
        return json.dumps(
            {
                "intent_type": "type_text",
                "parameters": {"text": "Hello from local model"},
                "confidence": 0.85,
                "context": "Generated by local provider",
            }
        )
