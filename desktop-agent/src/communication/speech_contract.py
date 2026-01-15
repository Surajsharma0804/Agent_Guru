"""
Speech Contract Validator

Production-grade speech contract enforcement for Human Co-Worker Speech Policy.
Ensures GURU speaks like a professional co-worker, not a chatbot.

CRITICAL RULES:
1. During action execution: Verb-first phrases ≤ 5 words only
2. During action execution: NO questions
3. NEVER use chatbot greeting phrases ("How can I help you?")
4. NEVER use chatbot confirmation phrases ("Sure, I can...", "Let me know if...")
5. During action execution: ONLY approved action phrases

Approved Action Phrases:
- "Opening [app]"
- "Done"
- "Typed"
- "Sent"
- "Failed: [reason]"
- "Searching"
- "Closing"
- "Starting"
- "Stopping"
- "Creating"
- "Deleting"
- "Saving"
- "Loading"

Forbidden Phrases (ALWAYS):
- "How can I help you?"
- "Sure, I can..."
- "Let me know if..."
- "Is there anything else?"
- "I'd be happy to..."
- "I'll be glad to..."
- "Feel free to..."
- "Don't hesitate to..."

Validates: Requirements 32.1, 32.2, 32.4, 32.5, 32.6, 32.7
"""

import re
from typing import Tuple, Optional
from enum import Enum
from dataclasses import dataclass


class SpeechContext(Enum):
    """Context in which speech is being produced"""
    ACTION_EXECUTION = "action_execution"  # During command execution
    CONVERSATION = "conversation"  # During idle conversation
    ERROR = "error"  # During error reporting


@dataclass
class ValidationResult:
    """Result of speech contract validation"""
    is_valid: bool
    reason: Optional[str] = None
    suggested_alternative: Optional[str] = None


class SpeechContractValidator:
    """
    Validates speech output against Human Co-Worker Speech Contract.
    
    Enforces professional, concise speech patterns that make GURU feel like
    a competent co-worker rather than a chatbot.
    
    Properties:
    - Property 89: Action Speech Brevity
    - Property 90: No Questions During Actions
    - Property 91: No Chatbot Greeting Phrases
    - Property 92: No Chatbot Confirmation Phrases
    - Property 93: Approved Action Phrases Only
    """
    
    # Approved action verbs (verb-first phrases)
    APPROVED_ACTION_VERBS = {
        "opening", "opened", "open",
        "closing", "closed", "close",
        "starting", "started", "start",
        "stopping", "stopped", "stop",
        "creating", "created", "create",
        "deleting", "deleted", "delete",
        "saving", "saved", "save",
        "loading", "loaded", "load",
        "typing", "typed", "type",
        "sending", "sent", "send",
        "searching", "searched", "search",
        "done", "failed", "error",
        "launching", "launched", "launch",
        "running", "ran", "run",
        "executing", "executed", "execute",
        "processing", "processed", "process",
        "copying", "copied", "copy",
        "moving", "moved", "move",
        "renaming", "renamed", "rename",
        "installing", "installed", "install",
        "uninstalling", "uninstalled", "uninstall",
        "updating", "updated", "update",
        "downloading", "downloaded", "download",
        "uploading", "uploaded", "upload"
    }
    
    # Forbidden chatbot phrases (ALWAYS forbidden, regardless of context)
    FORBIDDEN_PHRASES = {
        # Greeting phrases
        "how can i help you",
        "how may i help you",
        "how can i assist you",
        "how may i assist you",
        "what can i do for you",
        "what can i help you with",
        
        # Confirmation phrases
        "sure, i can",
        "sure i can",
        "of course, i can",
        "of course i can",
        "i'd be happy to",
        "i'd be glad to",
        "i'll be happy to",
        "i'll be glad to",
        
        # Follow-up phrases
        "let me know if",
        "let me know when",
        "feel free to",
        "don't hesitate to",
        "is there anything else",
        "anything else i can",
        "would you like me to",
        
        # Chatbot personality phrases
        "i'm here to help",
        "i'm here to assist",
        "i'm your assistant",
        "as your assistant",
        "as an ai",
        "as an assistant"
    }
    
    # Question patterns (forbidden during action execution)
    QUESTION_PATTERNS = [
        r'\?$',  # Ends with question mark
        r'^(what|where|when|why|how|who|which|can|could|would|should|do|does|did|is|are|was|were)\b',  # Starts with question word
    ]
    
    def __init__(self):
        """Initialize speech contract validator"""
        # Compile question patterns for efficiency
        self.question_regexes = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.QUESTION_PATTERNS
        ]
    
    def validate(
        self,
        text: str,
        context: SpeechContext = SpeechContext.CONVERSATION
    ) -> ValidationResult:
        """
        Validate speech text against contract.
        
        Args:
            text: Speech text to validate
            context: Context in which speech is being produced
        
        Returns:
            ValidationResult with validation status and reason
        
        Validates: Requirements 32.1, 32.2, 32.4, 32.5, 32.6, 32.7
        """
        if not text or not text.strip():
            return ValidationResult(
                is_valid=False,
                reason="Empty text"
            )
        
        text = text.strip()
        text_lower = text.lower()
        
        # Rule 1: ALWAYS check for forbidden chatbot phrases
        # Validates: Requirements 32.4, 32.5, 32.6
        for forbidden in self.FORBIDDEN_PHRASES:
            if forbidden in text_lower:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Contains forbidden chatbot phrase: '{forbidden}'",
                    suggested_alternative="Use concise, professional language"
                )
        
        # Context-specific validation
        if context == SpeechContext.ACTION_EXECUTION:
            return self._validate_action_speech(text, text_lower)
        elif context == SpeechContext.CONVERSATION:
            return self._validate_conversation_speech(text, text_lower)
        elif context == SpeechContext.ERROR:
            return self._validate_error_speech(text, text_lower)
        
        # Default: allow
        return ValidationResult(is_valid=True)
    
    def _validate_action_speech(self, text: str, text_lower: str) -> ValidationResult:
        """
        Validate speech during action execution.
        
        Rules:
        1. Must NOT contain questions (checked first)
        2. Must start with approved action verb
        3. Must be verb-first phrase
        4. Must be ≤ 5 words
        
        Args:
            text: Original text
            text_lower: Lowercase text
        
        Returns:
            ValidationResult
        
        Validates: Requirements 32.1, 32.2, 32.7
        """
        words = text.split()
        
        # Rule 1: Must NOT contain questions (check FIRST)
        # Validates: Requirements 32.2
        for regex in self.question_regexes:
            if regex.search(text):
                return ValidationResult(
                    is_valid=False,
                    reason="Questions not allowed during action execution",
                    suggested_alternative="Use declarative statement"
                )
        
        # Rule 2: Must start with approved action verb
        # Validates: Requirements 32.7
        first_word = words[0].lower() if words else ""
        
        # Check if starts with approved verb
        is_approved = False
        for verb in self.APPROVED_ACTION_VERBS:
            if first_word.startswith(verb) or first_word == verb:
                is_approved = True
                break
        
        if not is_approved:
            return ValidationResult(
                is_valid=False,
                reason=f"Action speech must start with approved verb, got: '{first_word}'",
                suggested_alternative="Use approved action verbs: Opening, Done, Typed, Sent, Failed, etc."
            )
        
        # Rule 3: Check word count (≤ 5 words)
        # Validates: Requirements 32.1
        if len(words) > 5:
            return ValidationResult(
                is_valid=False,
                reason=f"Action speech exceeds 5 words ({len(words)} words)",
                suggested_alternative=f"Use first 5 words: '{' '.join(words[:5])}'"
            )
        
        # All checks passed
        return ValidationResult(is_valid=True)
    
    def _validate_conversation_speech(self, text: str, text_lower: str) -> ValidationResult:
        """
        Validate speech during conversation.
        
        Rules:
        1. Must NOT contain forbidden chatbot phrases (already checked)
        2. Should be natural but professional
        3. No excessive verbosity
        
        Args:
            text: Original text
            text_lower: Lowercase text
        
        Returns:
            ValidationResult
        """
        # Conversational speech is more flexible
        # Main constraint is no chatbot phrases (already checked)
        
        # Optional: Check for excessive length (soft limit)
        words = text.split()
        if len(words) > 50:
            return ValidationResult(
                is_valid=False,
                reason=f"Conversational speech too verbose ({len(words)} words)",
                suggested_alternative="Keep responses concise and focused"
            )
        
        return ValidationResult(is_valid=True)
    
    def _validate_error_speech(self, text: str, text_lower: str) -> ValidationResult:
        """
        Validate speech during error reporting.
        
        Rules:
        1. Must be concise
        2. Must explain what failed
        3. Should start with "Failed:" or "Error:"
        
        Args:
            text: Original text
            text_lower: Lowercase text
        
        Returns:
            ValidationResult
        """
        # Error speech should be brief and informative
        words = text.split()
        
        # Check if starts with error indicator
        if not (text_lower.startswith("failed") or text_lower.startswith("error")):
            return ValidationResult(
                is_valid=False,
                reason="Error speech should start with 'Failed:' or 'Error:'",
                suggested_alternative=f"Failed: {text}"
            )
        
        # Check length (should be concise)
        if len(words) > 10:
            return ValidationResult(
                is_valid=False,
                reason=f"Error speech too verbose ({len(words)} words)",
                suggested_alternative="Keep error messages concise"
            )
        
        return ValidationResult(is_valid=True)
    
    def is_action_phrase(self, text: str) -> bool:
        """
        Check if text is a valid action phrase.
        
        Args:
            text: Text to check
        
        Returns:
            True if valid action phrase, False otherwise
        
        Validates: Requirements 32.7
        """
        result = self.validate(text, SpeechContext.ACTION_EXECUTION)
        return result.is_valid
    
    def is_question(self, text: str) -> bool:
        """
        Check if text contains a question.
        
        Args:
            text: Text to check
        
        Returns:
            True if contains question, False otherwise
        
        Validates: Requirements 32.2
        """
        for regex in self.question_regexes:
            if regex.search(text):
                return True
        return False
    
    def contains_forbidden_phrase(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if text contains forbidden chatbot phrase.
        
        Args:
            text: Text to check
        
        Returns:
            Tuple of (contains_forbidden, forbidden_phrase)
        
        Validates: Requirements 32.4, 32.5, 32.6
        """
        text_lower = text.lower()
        
        for forbidden in self.FORBIDDEN_PHRASES:
            if forbidden in text_lower:
                return (True, forbidden)
        
        return (False, None)
    
    def get_word_count(self, text: str) -> int:
        """
        Get word count of text.
        
        Args:
            text: Text to count
        
        Returns:
            Number of words
        """
        return len(text.split())
    
    def truncate_to_word_limit(self, text: str, max_words: int = 5) -> str:
        """
        Truncate text to word limit.
        
        Args:
            text: Text to truncate
            max_words: Maximum number of words
        
        Returns:
            Truncated text
        
        Validates: Requirements 32.1
        """
        words = text.split()
        if len(words) <= max_words:
            return text
        
        return ' '.join(words[:max_words])


# Global validator instance
_validator: Optional[SpeechContractValidator] = None


def get_speech_contract_validator() -> SpeechContractValidator:
    """
    Get global speech contract validator instance.
    
    Returns:
        SpeechContractValidator singleton
    """
    global _validator
    
    if _validator is None:
        _validator = SpeechContractValidator()
    
    return _validator


__all__ = [
    'SpeechContractValidator',
    'SpeechContext',
    'ValidationResult',
    'get_speech_contract_validator'
]
