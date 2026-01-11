"""
LLM Adapter Module for GURU Personal Assistant

This module provides a multi-provider LLM abstraction layer that enforces
the critical security invariant: LLMs are advisory only, never authoritative.

All LLM outputs are structured intents that must pass through:
- AuthorityState verification
- SignedCommandVerifier validation  
- Skill sandbox policy enforcement

Key Security Principles:
- LLMs cannot directly execute any system functions
- All outputs are validated and sanitized
- LLM isolation breach triggers immediate authority revocation
- Fail-safe defaults with comprehensive audit logging
"""

from .adapter import LLMAdapter
from .providers import (
    LLMProvider,
    GeminiProvider,
    LocalProvider,
    ProviderCapabilities,
    ProviderStatus
)
from .intent import (
    IntentType,
    IntentValidator,
    StructuredIntent
)
from .safety import (
    LLMSafetyEngine,
    ContentSafetyFilter,
    ResponseSanitizer,
    SafeResponse
)
from .exceptions import (
    LLMAdapterError,
    ProviderError,
    SafetyViolationError,
    IntentValidationError,
    IsolationBreachError
)

__all__ = [
    'LLMAdapter',
    'LLMProvider',
    'GeminiProvider', 
    'LocalProvider',
    'ProviderCapabilities',
    'ProviderStatus',
    'IntentType',
    'IntentValidator',
    'StructuredIntent',
    'LLMSafetyEngine',
    'ContentSafetyFilter',
    'ResponseSanitizer',
    'SafeResponse',
    'LLMAdapterError',
    'ProviderError',
    'SafetyViolationError',
    'IntentValidationError',
    'IsolationBreachError'
]