"""
Conversation Strategy Engine for Agent_Guru.

This module handles conversation strategies including:
- Clarification rules and templates
- Confirmation logic for sensitive actions
- Tone and personality adaptation
- Error response strategies
- Proactive suggestion generation
"""

from Agent_Guru.reasoning.conversation.clarification import (
    ClarificationGenerator,
    ClarificationRules,
    ClarificationTemplate,
)
from Agent_Guru.reasoning.conversation.confirmation import (
    ConfirmationGenerator,
    ConfirmationParser,
    ConfirmationRules,
)
from Agent_Guru.reasoning.conversation.error_strategy import (
    ErrorClassifier,
    ErrorResponseStrategy,
)
from Agent_Guru.reasoning.conversation.strategy_engine import (
    ConversationStrategyEngine,
)
from Agent_Guru.reasoning.conversation.suggestions import (
    ProactiveSuggestionGenerator,
)
from Agent_Guru.reasoning.conversation.tone import (
    PersonalityDimension,
    ToneAdapter,
)

__all__ = [
    "ClarificationRules",
    "ClarificationTemplate",
    "ClarificationGenerator",
    "ConfirmationRules",
    "ConfirmationGenerator",
    "ConfirmationParser",
    "ToneAdapter",
    "PersonalityDimension",
    "ErrorResponseStrategy",
    "ErrorClassifier",
    "ProactiveSuggestionGenerator",
    "ConversationStrategyEngine",
]
