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
    ModelCallMetadata,
)

# Legacy compatibility imports (avoiding circular import)
# from .adapter import LLMAdapter  # Circular import - removed
from .providers import LLMProvider, ProviderCapabilities, ProviderStatus

# Export the production implementation
__all__ = [
    "LanguageModelAdapter",
    "get_production_adapter", 
    "RuntimeConfiguration",
    "TaskConfiguration",
    "ProviderConfiguration",
    "TaskType",
    "ProviderType",
    "SecurityMode",
    "ModelCallMetadata",
    # "LLMAdapter",  # Legacy compatibility - removed to avoid circular import
    "LLMProvider",
    "ProviderCapabilities", 
    "ProviderStatus",
]
