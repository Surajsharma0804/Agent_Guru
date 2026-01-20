"""
GURU AI Runtime System - Absolute Integration & Model-Routing Master

Production-grade multi-provider LLM routing system with zero-compromise security.
Enables runtime switching between local models (Ollama) and cloud APIs (Gemini/OpenAI).

CRITICAL SECURITY INVARIANTS (NON-NEGOTIABLE):
- NO MODEL may directly control keyboard, mouse, filesystem, or OS
- NO LLM may execute actions
- ALL execution passes through Authority State Machine
- ALL failures MUST fail closed (LOCKED_LISTEN_ONLY)
- NO AI-style naming, comments, or structure
- NO demo logic, mocks, placeholders, or TODOs
- NO silent fallbacks without explicit configuration

MANDATORY SYSTEM ARCHITECTURE:
Audio Input → Speech-to-Text (Local) → Language Detection (Local, Deterministic) →
Intent Extraction (LLM – Local or API) → Intent Structuring (LLM – Local or API) →
Rule Validator (NO LLM) → Authority State Machine → Execution Engine → Audit Logger

ZERO TOLERANCE PRINCIPLES:
- Models are replaceable. Authority is sacred. Execution is earned.
- API keys NEVER logged, NEVER stored in code
- Switching to API requires manual confirmation + Authority ARMED state
- Every model call MUST be audited (metadata only, no content)
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional, Union

from .exceptions import ModelRouterError, ProviderError
from .intent import StructuredIntent
from .safety import SafeResponse


@dataclass
class AdapterConfiguration:
    """Base configuration for LLM adapters with security controls."""
    
    # Provider settings
    default_provider: str = "ollama"
    fallback_provider: Optional[str] = None
    
    # Timeout and retry settings
    default_timeout_seconds: float = 30.0
    max_retries: int = 2
    
    # Security settings
    require_authority_for_api: bool = True
    log_all_requests: bool = True
    
    # Performance settings
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600


@dataclass
class ModelCallMetadata:
    """Metadata for LLM calls (for audit logging)."""
    
    provider: str
    model: str
    task_type: str
    timestamp: datetime
    duration_ms: int
    success: bool
    error_type: Optional[str] = None
    token_count: Optional[int] = None


class LLMAdapter(ABC):
    """
    Abstract base class for LLM adapters with security enforcement.
    
    Enforces security boundaries and provides common functionality
    for all LLM adapter implementations.
    """
    
    def __init__(self, config: Optional[AdapterConfiguration] = None):
        """Initialize LLM adapter with security configuration."""
        self.config = config or AdapterConfiguration()
        self._lock = Lock()
        self._call_history: List[ModelCallMetadata] = []
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        
    @abstractmethod
    async def process_intent(
        self, 
        text: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> StructuredIntent:
        """
        Process user input and extract structured intent.
        
        Args:
            text: User input text
            context: Optional context information
            
        Returns:
            StructuredIntent with extracted information
            
        Raises:
            ProviderError: If LLM provider fails
            ModelRouterError: If routing fails
        """
        pass
    
    @abstractmethod
    async def structure_response(
        self, 
        intent: StructuredIntent,
        context: Optional[Dict[str, Any]] = None
    ) -> SafeResponse:
        """
        Structure a response for the given intent.
        
        Args:
            intent: Structured intent to respond to
            context: Optional context information
            
        Returns:
            SafeResponse with structured output
            
        Raises:
            ProviderError: If LLM provider fails
            ModelRouterError: If routing fails
        """
        pass
    
    def get_call_history(self, limit: Optional[int] = None) -> List[ModelCallMetadata]:
        """Get history of LLM calls for audit purposes."""
        with self._lock:
            history = list(reversed(self._call_history))
            if limit:
                history = history[:limit]
            return history
    
    def clear_cache(self) -> None:
        """Clear the response cache."""
        with self._lock:
            self._cache.clear()
            self._cache_timestamps.clear()
    
    def _log_call(self, metadata: ModelCallMetadata) -> None:
        """Log an LLM call for audit purposes."""
        with self._lock:
            self._call_history.append(metadata)
            # Keep only last 1000 calls
            if len(self._call_history) > 1000:
                self._call_history = self._call_history[-1000:]
    
    def _get_cached_response(self, cache_key: str) -> Optional[Any]:
        """Get cached response if still valid."""
        with self._lock:
            if cache_key not in self._cache:
                return None
            
            timestamp = self._cache_timestamps.get(cache_key)
            if not timestamp:
                return None
            
            # Check if cache entry is still valid
            age_seconds = (datetime.utcnow() - timestamp).total_seconds()
            if age_seconds > self.config.cache_ttl_seconds:
                # Remove expired entry
                del self._cache[cache_key]
                del self._cache_timestamps[cache_key]
                return None
            
            return self._cache[cache_key]
    
    def _cache_response(self, cache_key: str, response: Any) -> None:
        """Cache a response."""
        if not self.config.enable_caching:
            return
            
        with self._lock:
            self._cache[cache_key] = response
            self._cache_timestamps[cache_key] = datetime.utcnow()
            
            # Limit cache size
            if len(self._cache) > 1000:
                # Remove oldest entries
                oldest_keys = sorted(
                    self._cache_timestamps.keys(),
                    key=lambda k: self._cache_timestamps[k]
                )[:100]
                for key in oldest_keys:
                    del self._cache[key]
                    del self._cache_timestamps[key]


# Import the production adapter as the main implementation
from .production_adapter import (
    ProductionLanguageModelAdapter as LanguageModelAdapter,
    get_production_adapter,
    RuntimeConfiguration,
    TaskConfiguration,
    ProviderConfiguration,
    TaskType,
    ProviderType,
    SecurityMode,
)

# Legacy compatibility imports (avoiding circular import)
from .providers import LLMProvider, ProviderCapabilities, ProviderStatus

# Export the production implementation and base classes
__all__ = [
    # Base classes
    "LLMAdapter",
    "AdapterConfiguration", 
    "ModelCallMetadata",
    
    # Production implementation
    "LanguageModelAdapter",
    "get_production_adapter", 
    "RuntimeConfiguration",
    "TaskConfiguration",
    "ProviderConfiguration",
    "TaskType",
    "ProviderType",
    "SecurityMode",
    
    # Provider interfaces
    "LLMProvider",
    "ProviderCapabilities", 
    "ProviderStatus",
]
