"""
Property-Based Tests for Speech Contract

Tests the Human Co-Worker Speech Contract enforcement using property-based testing.
Validates that GURU speaks like a professional co-worker, not a chatbot.

Properties Tested:
- Property 89: Action Speech Brevity
- Property 90: No Questions During Actions
- Property 91: No Chatbot Greeting Phrases
- Property 92: No Chatbot Confirmation Phrases
- Property 93: Approved Action Phrases Only

Validates: Requirements 32.1, 32.2, 32.4, 32.5, 32.6, 32.7

Feature: guru-complete-system
"""

import os

# Import speech contract components
import sys

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from communication.speech_contract import (
    SpeechContext,
    SpeechContractValidator,
    ValidationResult,
    get_speech_contract_validator,
)

# Test data generators

@st.composite
def action_verb(draw):
    """Generate approved action verbs"""
    verbs = [
        "opening", "opened", "open",
        "closing", "closed", "close",
        "starting", "started", "start",
        "stopping", "stopped", "stop",
        "typing", "typed", "type",
        "sending", "sent", "send",
        "done", "failed"
    ]
    return draw(st.sampled_from(verbs))


@st.composite
def valid_action_phrase(draw):
    """Generate valid action phrases (verb-first, ≤ 5 words)"""
    verb = draw(action_verb())
    
    # Generate 0-4 additional words
    num_words = draw(st.integers(min_value=0, max_value=4))
    
    if num_words == 0:
        return verb.capitalize()
    
    # Generate additional words (app names, objects, etc.)
    words = [verb.capitalize()]
    for _ in range(num_words):
        word = draw(st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll')),
            min_size=3,
            max_size=10
        ))
        words.append(word)
    
    return ' '.join(words)


@st.composite
def invalid_action_phrase_too_long(draw):
    """Generate action phrases that are too long (> 5 words)"""
    verb = draw(action_verb())
    
    # Generate 6-10 words total
    num_words = draw(st.integers(min_value=6, max_value=10))
    
    words = [verb.capitalize()]
    for _ in range(num_words - 1):
        word = draw(st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll')),
            min_size=3,
            max_size=10
        ))
        words.append(word)
    
    return ' '.join(words)


@st.composite
def question_phrase(draw):
    """Generate question phrases"""
    question_starters = [
        "What", "Where", "When", "Why", "How", "Who", "Which",
        "Can", "Could", "Would", "Should", "Do", "Does", "Did",
        "Is", "Are", "Was", "Were"
    ]
    
    starter = draw(st.sampled_from(question_starters))
    
    # Generate rest of question
    words = [starter]
    num_words = draw(st.integers(min_value=2, max_value=8))
    
    for _ in range(num_words - 1):
        word = draw(st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll')),
            min_size=3,
            max_size=10
        ))
        words.append(word)
    
    return ' '.join(words) + '?'


@st.composite
def forbidden_chatbot_phrase(draw):
    """Generate text containing forbidden chatbot phrases"""
    forbidden = [
        "How can I help you?",
        "Sure, I can do that",
        "Let me know if you need anything",
        "I'd be happy to help",
        "Feel free to ask",
        "Is there anything else?",
        "I'm here to assist you"
    ]
    
    return draw(st.sampled_from(forbidden))


@st.composite
def conversational_text(draw):
    """Generate conversational text (no forbidden phrases)"""
    # Generate 5-30 words of conversational text
    num_words = draw(st.integers(min_value=5, max_value=30))
    
    words = []
    for _ in range(num_words):
        word = draw(st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll')),
            min_size=3,
            max_size=10
        ))
        words.append(word)
    
    text = ' '.join(words)
    
    # Ensure it doesn't accidentally contain forbidden phrases
    validator = get_speech_contract_validator()
    contains_forbidden, _ = validator.contains_forbidden_phrase(text)
    assume(not contains_forbidden)
    
    return text


# Property Tests

@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(phrase=valid_action_phrase())
def test_property_89_action_speech_brevity(phrase):
    """
    Property 89: Action Speech Brevity
    
    For any action execution, TTS output should be verb-first and ≤ 5 words.
    
    Validates: Requirements 32.1
    
    Feature: guru-complete-system, Property 89: Action Speech Brevity
    """
    validator = get_speech_contract_validator()
    
    # Validate as action speech
    result = validator.validate(phrase, SpeechContext.ACTION_EXECUTION)
    
    # Should be valid (verb-first, ≤ 5 words)
    assert result.is_valid, f"Valid action phrase rejected: '{phrase}' - {result.reason}"
    
    # Verify word count
    word_count = validator.get_word_count(phrase)
    assert word_count <= 5, f"Action phrase exceeds 5 words: {word_count}"


@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(phrase=invalid_action_phrase_too_long())
def test_property_89_action_speech_brevity_violation(phrase):
    """
    Property 89: Action Speech Brevity (Violation)
    
    For any action phrase > 5 words, validation should fail.
    
    Validates: Requirements 32.1
    
    Feature: guru-complete-system, Property 89: Action Speech Brevity
    """
    validator = get_speech_contract_validator()
    
    # Validate as action speech
    result = validator.validate(phrase, SpeechContext.ACTION_EXECUTION)
    
    # Should be invalid (too long)
    assert not result.is_valid, f"Long action phrase accepted: '{phrase}'"
    assert "exceeds 5 words" in result.reason.lower() or "5 words" in result.reason.lower()


@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(question=question_phrase())
def test_property_90_no_questions_during_actions(question):
    """
    Property 90: No Questions During Actions
    
    For any action execution, TTS output should never contain questions.
    
    Validates: Requirements 32.2
    
    Feature: guru-complete-system, Property 90: No Questions During Actions
    """
    validator = get_speech_contract_validator()
    
    # Validate as action speech
    result = validator.validate(question, SpeechContext.ACTION_EXECUTION)
    
    # Should be invalid (contains question)
    assert not result.is_valid, f"Question accepted during action: '{question}'"
    assert "question" in result.reason.lower()
    
    # Verify is_question method
    assert validator.is_question(question), f"Question not detected: '{question}'"


@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(text=st.text(min_size=1, max_size=100))
def test_property_91_no_chatbot_greeting_phrases(text):
    """
    Property 91: No Chatbot Greeting Phrases
    
    For any TTS output, it should never contain "How can I help you?".
    
    Validates: Requirements 32.4
    
    Feature: guru-complete-system, Property 91: No Chatbot Greeting Phrases
    """
    validator = get_speech_contract_validator()
    
    # Check if text contains "how can i help you"
    text_lower = text.lower()
    contains_greeting = "how can i help you" in text_lower or "how may i help you" in text_lower
    
    # Validate in any context
    result_action = validator.validate(text, SpeechContext.ACTION_EXECUTION)
    result_conversation = validator.validate(text, SpeechContext.CONVERSATION)
    
    if contains_greeting:
        # Should be rejected in all contexts
        assert not result_action.is_valid, f"Greeting phrase accepted in action context: '{text}'"
        assert not result_conversation.is_valid, f"Greeting phrase accepted in conversation context: '{text}'"
        assert "forbidden" in result_action.reason.lower()
    else:
        # May be valid or invalid for other reasons, but not due to greeting phrase
        if not result_action.is_valid:
            assert "how can i help" not in result_action.reason.lower()
        if not result_conversation.is_valid:
            assert "how can i help" not in result_conversation.reason.lower()


@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(text=st.text(min_size=1, max_size=100))
def test_property_92_no_chatbot_confirmation_phrases(text):
    """
    Property 92: No Chatbot Confirmation Phrases
    
    For any TTS output, it should never contain "Sure, I can..." or "Let me know if...".
    
    Validates: Requirements 32.5, 32.6
    
    Feature: guru-complete-system, Property 92: No Chatbot Confirmation Phrases
    """
    validator = get_speech_contract_validator()
    
    # Check if text contains forbidden confirmation phrases
    text_lower = text.lower()
    contains_confirmation = (
        "sure, i can" in text_lower or
        "sure i can" in text_lower or
        "let me know if" in text_lower or
        "i'd be happy to" in text_lower or
        "i'll be glad to" in text_lower
    )
    
    # Validate in any context
    result_action = validator.validate(text, SpeechContext.ACTION_EXECUTION)
    result_conversation = validator.validate(text, SpeechContext.CONVERSATION)
    
    if contains_confirmation:
        # Should be rejected in all contexts
        assert not result_action.is_valid, f"Confirmation phrase accepted in action context: '{text}'"
        assert not result_conversation.is_valid, f"Confirmation phrase accepted in conversation context: '{text}'"
        assert "forbidden" in result_action.reason.lower()
    else:
        # May be valid or invalid for other reasons, but not due to confirmation phrase
        if not result_action.is_valid:
            assert "sure" not in result_action.reason.lower() or "let me know" not in result_action.reason.lower()


@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(phrase=valid_action_phrase())
def test_property_93_approved_action_phrases_only(phrase):
    """
    Property 93: Approved Action Phrases Only
    
    For any action execution, TTS output should use only approved phrases:
    "Opening [app]", "Done", "Typed", "Sent", "Failed: [reason]".
    
    Validates: Requirements 32.7
    
    Feature: guru-complete-system, Property 93: Approved Action Phrases Only
    """
    validator = get_speech_contract_validator()
    
    # Validate as action speech
    result = validator.validate(phrase, SpeechContext.ACTION_EXECUTION)
    
    # Should be valid (approved action phrase)
    assert result.is_valid, f"Approved action phrase rejected: '{phrase}' - {result.reason}"
    
    # Verify is_action_phrase method
    assert validator.is_action_phrase(phrase), f"Action phrase not recognized: '{phrase}'"


@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(text=conversational_text())
def test_property_93_non_action_phrases_rejected_in_action_context(text):
    """
    Property 93: Approved Action Phrases Only (Rejection)
    
    For any non-action phrase, validation should fail in action context.
    
    Validates: Requirements 32.7
    
    Feature: guru-complete-system, Property 93: Approved Action Phrases Only
    """
    validator = get_speech_contract_validator()
    
    # Assume text doesn't start with approved action verb
    first_word = text.split()[0].lower() if text.split() else ""
    approved_verbs = validator.APPROVED_ACTION_VERBS
    
    starts_with_approved = any(
        first_word.startswith(verb) or first_word == verb
        for verb in approved_verbs
    )
    
    assume(not starts_with_approved)
    
    # Validate as action speech
    result = validator.validate(text, SpeechContext.ACTION_EXECUTION)
    
    # Should be invalid (not an approved action phrase)
    assert not result.is_valid, f"Non-action phrase accepted in action context: '{text}'"


# Integration Tests

def test_speech_contract_validator_initialization():
    """Test that speech contract validator initializes correctly"""
    validator = SpeechContractValidator()
    
    assert validator is not None
    assert len(validator.APPROVED_ACTION_VERBS) > 0
    assert len(validator.FORBIDDEN_PHRASES) > 0
    assert len(validator.question_regexes) > 0


def test_forbidden_phrases_always_rejected():
    """Test that all forbidden phrases are rejected in all contexts"""
    validator = get_speech_contract_validator()
    
    forbidden_phrases = [
        "How can I help you?",
        "Sure, I can do that",
        "Let me know if you need anything",
        "I'd be happy to help",
        "Feel free to ask"
    ]
    
    for phrase in forbidden_phrases:
        # Test in all contexts
        result_action = validator.validate(phrase, SpeechContext.ACTION_EXECUTION)
        result_conversation = validator.validate(phrase, SpeechContext.CONVERSATION)
        result_error = validator.validate(phrase, SpeechContext.ERROR)
        
        assert not result_action.is_valid, f"Forbidden phrase accepted in action: '{phrase}'"
        assert not result_conversation.is_valid, f"Forbidden phrase accepted in conversation: '{phrase}'"
        assert not result_error.is_valid, f"Forbidden phrase accepted in error: '{phrase}'"


def test_approved_action_phrases_accepted():
    """Test that approved action phrases are accepted in action context"""
    validator = get_speech_contract_validator()
    
    approved_phrases = [
        "Opening Chrome",
        "Done",
        "Typed message",
        "Sent email",
        "Failed: Network error",
        "Searching Google",
        "Closing window"
    ]
    
    for phrase in approved_phrases:
        result = validator.validate(phrase, SpeechContext.ACTION_EXECUTION)
        assert result.is_valid, f"Approved phrase rejected: '{phrase}' - {result.reason}"


def test_word_count_enforcement():
    """Test that word count is enforced correctly"""
    validator = get_speech_contract_validator()
    
    # Valid: ≤ 5 words
    valid_phrases = [
        "Opening Chrome",
        "Done",
        "Typed message successfully",
        "Sent email to John"
    ]
    
    for phrase in valid_phrases:
        result = validator.validate(phrase, SpeechContext.ACTION_EXECUTION)
        assert result.is_valid, f"Valid phrase rejected: '{phrase}'"
    
    # Invalid: > 5 words
    invalid_phrases = [
        "Opening Chrome browser window for you now",
        "Typed message successfully and sent it to recipient"
    ]
    
    for phrase in invalid_phrases:
        result = validator.validate(phrase, SpeechContext.ACTION_EXECUTION)
        assert not result.is_valid, f"Long phrase accepted: '{phrase}'"


def test_question_detection():
    """Test that questions are detected correctly"""
    validator = get_speech_contract_validator()
    
    questions = [
        "What should I do?",
        "Where is the file?",
        "Can I help you?",
        "Would you like me to continue?"
    ]
    
    for question in questions:
        assert validator.is_question(question), f"Question not detected: '{question}'"
        
        # Should be rejected in action context
        result = validator.validate(question, SpeechContext.ACTION_EXECUTION)
        assert not result.is_valid, f"Question accepted in action: '{question}'"


def test_truncate_to_word_limit():
    """Test word limit truncation"""
    validator = get_speech_contract_validator()
    
    text = "Opening Chrome browser window for you now"
    truncated = validator.truncate_to_word_limit(text, 5)
    
    assert truncated == "Opening Chrome browser window for"
    assert validator.get_word_count(truncated) == 5


def test_singleton_pattern():
    """Test that get_speech_contract_validator returns singleton"""
    validator1 = get_speech_contract_validator()
    validator2 = get_speech_contract_validator()
    
    assert validator1 is validator2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
