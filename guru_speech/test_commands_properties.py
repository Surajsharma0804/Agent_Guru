"""
Property-based tests for CommandInterpreter module.

This module contains property tests that verify universal correctness properties
of the command interpretation functionality.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

from .commands import CommandInterpreter
from .models import CommandResult


# Strategy for generating valid action IDs
action_ids = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
    min_size=1,
    max_size=20
).filter(lambda x: x and not x.isspace())

# Strategy for generating valid command patterns
# Patterns should be reasonable text strings that could be spoken
patterns = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"), whitelist_characters="*"),
    min_size=1,
    max_size=50
).filter(lambda x: x.strip() and len(x.strip()) > 0)

# Strategy for generating language codes
language_codes = st.sampled_from(["en", "hi", "pa"])


@settings(max_examples=100, deadline=None)
@given(
    pattern=patterns,
    action_id=action_ids,
    language=language_codes
)
def test_command_pattern_matching_and_mapping(pattern, action_id, language):
    """
    Feature: guru-speech-engine, Property 3: Command Pattern Matching and Mapping
    
    For any registered command pattern and any text that matches that pattern, 
    the Command_Interpreter should return a CommandResult with the correct 
    action_id associated with that pattern.
    
    **Validates: Requirements 4.1, 4.2**
    
    This property verifies that:
    1. When a command is registered with a pattern and action_id
    2. And text matching that pattern is interpreted
    3. Then the returned CommandResult contains the correct action_id
    4. And is_command is True
    5. And the language is preserved
    """
    # Assume pattern doesn't conflict with default commands
    # to avoid interference from pre-registered patterns
    pattern_lower = pattern.lower().strip()
    assume(pattern_lower not in ["open youtube", "youtube kholo", "youtube ਖੋਲ੍ਹੋ"])
    assume(pattern_lower not in ["play music", "music chalao", "music ਚਲਾਓ"])
    assume("search for" not in pattern_lower)
    assume("dhundo" not in pattern_lower)
    assume("ਲੱਭੋ" not in pattern_lower)
    
    # Create a fresh interpreter
    interpreter = CommandInterpreter()
    
    # Register the command with the generated pattern and action_id
    interpreter.register_command(
        patterns=[pattern],
        action_id=action_id,
        languages=[language]
    )
    
    # Interpret text that exactly matches the pattern
    result = interpreter.interpret(pattern, language=language)
    
    # Property assertions
    
    # 1. Result must be a CommandResult instance
    assert isinstance(result, CommandResult), \
        "interpret() must return a CommandResult instance"
    
    # 2. The action_id must match the registered action_id
    assert result.action_id == action_id, \
        f"Expected action_id '{action_id}', but got '{result.action_id}'"
    
    # 3. is_command must be True since we matched a registered pattern
    assert result.is_command is True, \
        "is_command must be True when a pattern matches"
    
    # 4. The language must be preserved
    assert result.language == language, \
        f"Expected language '{language}', but got '{result.language}'"
    
    # 5. The raw_text must be preserved
    assert result.raw_text == pattern, \
        f"Expected raw_text '{pattern}', but got '{result.raw_text}'"
    
    # 6. Confidence should be positive (1.0 for exact match)
    assert result.confidence > 0.0, \
        "Confidence must be positive for matched commands"
    
    # 7. Parameters should be a dictionary (may be empty)
    assert isinstance(result.parameters, dict), \
        "Parameters must be a dictionary"


@settings(max_examples=100, deadline=None)
@given(
    pattern=patterns,
    action_id=action_ids,
    wrong_language=language_codes,
    correct_language=language_codes
)
def test_command_language_specificity(pattern, action_id, wrong_language, correct_language):
    """
    Feature: guru-speech-engine, Property 3: Command Pattern Matching and Mapping (Language)
    
    For any registered command pattern with a specific language, text in a 
    different language should not match that pattern.
    
    **Validates: Requirements 4.1, 4.2**
    """
    # Ensure languages are different
    assume(wrong_language != correct_language)
    
    # Assume pattern doesn't conflict with default commands
    pattern_lower = pattern.lower().strip()
    assume(pattern_lower not in ["open youtube", "youtube kholo", "youtube ਖੋਲ੍ਹੋ"])
    assume(pattern_lower not in ["play music", "music chalao", "music ਚਲਾਓ"])
    assume("search for" not in pattern_lower)
    assume("dhundo" not in pattern_lower)
    assume("ਲੱਭੋ" not in pattern_lower)
    
    # Create interpreter
    interpreter = CommandInterpreter()
    
    # Register command for specific language only
    interpreter.register_command(
        patterns=[pattern],
        action_id=action_id,
        languages=[correct_language]
    )
    
    # Try to interpret with wrong language
    result = interpreter.interpret(pattern, language=wrong_language)
    
    # Property assertion: should not match because language doesn't match
    # (unless it matches a default command in that language)
    if result.is_command and result.action_id == action_id:
        # This should not happen - the command should not match
        pytest.fail(
            f"Command matched with wrong language. "
            f"Pattern '{pattern}' registered for '{correct_language}' "
            f"but matched with '{wrong_language}'"
        )


@settings(max_examples=100, deadline=None)
@given(
    patterns=st.lists(patterns, min_size=2, max_size=5, unique=True),
    action_id=action_ids,
    language=language_codes,
    data=st.data()
)
def test_multiple_patterns_same_action(patterns, action_id, language, data):
    """
    Feature: guru-speech-engine, Property 3: Command Pattern Matching and Mapping (Multiple Patterns)
    
    For any command registered with multiple patterns, all patterns should map 
    to the same action_id.
    
    **Validates: Requirements 4.1, 4.2**
    """
    # Filter out patterns that conflict with defaults
    filtered_patterns = []
    for pattern in patterns:
        pattern_lower = pattern.lower().strip()
        if (pattern_lower not in ["open youtube", "youtube kholo", "youtube ਖੋਲ੍ਹੋ"] and
            pattern_lower not in ["play music", "music chalao", "music ਚਲਾਓ"] and
            "search for" not in pattern_lower and
            "dhundo" not in pattern_lower and
            "ਲੱਭੋ" not in pattern_lower):
            filtered_patterns.append(pattern)
    
    assume(len(filtered_patterns) >= 2)
    
    # Create interpreter
    interpreter = CommandInterpreter()
    
    # Register command with multiple patterns
    interpreter.register_command(
        patterns=filtered_patterns,
        action_id=action_id,
        languages=[language]
    )
    
    # Pick a random pattern from the list
    chosen_pattern = data.draw(st.sampled_from(filtered_patterns))
    
    # Interpret the chosen pattern
    result = interpreter.interpret(chosen_pattern, language=language)
    
    # Property assertions
    assert result.is_command is True, \
        f"Pattern '{chosen_pattern}' should be recognized as a command"
    
    assert result.action_id == action_id, \
        f"All patterns should map to action_id '{action_id}', but got '{result.action_id}'"


@settings(max_examples=100, deadline=None)
@given(
    pattern=patterns,
    action_id=action_ids,
    language=language_codes
)
def test_command_registration_retrieval(pattern, action_id, language):
    """
    Feature: guru-speech-engine, Property 3: Command Pattern Matching and Mapping (Registration)
    
    For any registered command, it should be retrievable from the command registry.
    
    **Validates: Requirements 4.1, 4.2**
    """
    # Assume pattern doesn't conflict with default commands
    pattern_lower = pattern.lower().strip()
    assume(pattern_lower not in ["open youtube", "youtube kholo", "youtube ਖੋਲ੍ਹੋ"])
    assume(pattern_lower not in ["play music", "music chalao", "music ਚਲਾਓ"])
    assume("search for" not in pattern_lower)
    assume("dhundo" not in pattern_lower)
    assume("ਲੱਭੋ" not in pattern_lower)
    
    # Create interpreter
    interpreter = CommandInterpreter()
    
    # Get initial command count (includes defaults)
    initial_commands = interpreter.get_registered_commands()
    initial_count = len(initial_commands)
    
    # Register new command
    interpreter.register_command(
        patterns=[pattern],
        action_id=action_id,
        languages=[language]
    )
    
    # Get updated commands
    updated_commands = interpreter.get_registered_commands()
    
    # Property assertions
    
    # 1. Command count should increase by 1
    assert len(updated_commands) == initial_count + 1, \
        f"Expected {initial_count + 1} commands, but got {len(updated_commands)}"
    
    # 2. The new command should be in the registry
    action_ids = [cmd["action_id"] for cmd in updated_commands]
    assert action_id in action_ids, \
        f"Registered action_id '{action_id}' not found in registry"
    
    # 3. Find the registered command and verify its properties
    registered_cmd = next((cmd for cmd in updated_commands if cmd["action_id"] == action_id), None)
    assert registered_cmd is not None, \
        f"Could not find registered command with action_id '{action_id}'"
    
    assert pattern in registered_cmd["patterns"], \
        f"Pattern '{pattern}' not found in registered command patterns"
    
    assert language in registered_cmd["languages"], \
        f"Language '{language}' not found in registered command languages"


@settings(max_examples=100, deadline=None)
@given(
    text=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po")),
        min_size=1,
        max_size=100
    ).filter(lambda x: x.strip() and len(x.strip()) > 0),
    language=language_codes
)
def test_unrecognized_text_passthrough(text, language):
    """
    Feature: guru-speech-engine, Property 4: Unrecognized Text Passthrough
    
    For any text that does not match any registered command pattern, 
    the Command_Interpreter should return a CommandResult with is_command=False 
    and raw_text equal to the input text.
    
    **Validates: Requirements 4.4**
    
    This property verifies that:
    1. When text does not match any registered command pattern
    2. Then the returned CommandResult has is_command=False
    3. And raw_text equals the input text
    4. And action_id is None
    5. And the language is preserved
    """
    # Filter out text that matches default commands
    text_lower = text.lower().strip()
    
    # Skip if text matches any default command patterns
    default_patterns = [
        "open youtube", "youtube kholo", "youtube ਖੋਲ੍ਹੋ",
        "play music", "music chalao", "music ਚਲਾਓ"
    ]
    
    # Skip if exact match with default patterns
    assume(text_lower not in default_patterns)
    
    # Skip if matches search patterns (contains these keywords)
    assume("search for" not in text_lower)
    assume("dhundo" not in text_lower)
    assume("ਲੱਭੋ" not in text_lower)
    
    # Skip if fuzzy match is too close to default patterns (similarity >= 0.8)
    from difflib import SequenceMatcher
    for pattern in default_patterns:
        similarity = SequenceMatcher(None, text_lower, pattern).ratio()
        assume(similarity < 0.8)
    
    # Create interpreter with only default commands
    interpreter = CommandInterpreter()
    
    # Interpret the text
    result = interpreter.interpret(text, language=language)
    
    # Property assertions
    
    # 1. Result must be a CommandResult instance
    assert isinstance(result, CommandResult), \
        "interpret() must return a CommandResult instance"
    
    # 2. is_command must be False since no pattern matched
    assert result.is_command is False, \
        f"is_command must be False for unrecognized text, but got True for '{text}'"
    
    # 3. action_id must be None
    assert result.action_id is None, \
        f"action_id must be None for unrecognized text, but got '{result.action_id}'"
    
    # 4. raw_text must equal the input text
    assert result.raw_text == text, \
        f"Expected raw_text '{text}', but got '{result.raw_text}'"
    
    # 5. The language must be preserved
    assert result.language == language, \
        f"Expected language '{language}', but got '{result.language}'"
    
    # 6. Confidence should be 0.0 for unrecognized text
    assert result.confidence == 0.0, \
        f"Confidence must be 0.0 for unrecognized text, but got {result.confidence}"
    
    # 7. Parameters should be an empty dictionary
    assert result.parameters == {}, \
        f"Parameters must be empty for unrecognized text, but got {result.parameters}"



@settings(max_examples=100, deadline=None)
@given(
    pattern=patterns,
    action_id=action_ids,
    language=language_codes
)
def test_command_result_structure_completeness(pattern, action_id, language):
    """
    Feature: guru-speech-engine, Property 7: Command Result Structure Completeness
    
    For any command interpretation result where is_command=True, the CommandResult 
    should contain a non-null action_id, a parameters dictionary, the raw_text, 
    a confidence score between 0.0 and 1.0, and a valid language code.
    
    **Validates: Requirements 12.1, 12.3**
    
    This property verifies that:
    1. When a command is detected (is_command=True)
    2. Then action_id is not None
    3. And parameters is a dictionary
    4. And raw_text is present and matches input
    5. And confidence is between 0.0 and 1.0
    6. And language is a valid language code
    7. And all required fields are properly populated
    """
    # Assume pattern doesn't conflict with default commands
    pattern_lower = pattern.lower().strip()
    assume(pattern_lower not in ["open youtube", "youtube kholo", "youtube ਖੋਲ੍ਹੋ"])
    assume(pattern_lower not in ["play music", "music chalao", "music ਚਲਾਓ"])
    assume("search for" not in pattern_lower)
    assume("dhundo" not in pattern_lower)
    assume("ਲੱਭੋ" not in pattern_lower)
    
    # Create interpreter and register command
    interpreter = CommandInterpreter()
    interpreter.register_command(
        patterns=[pattern],
        action_id=action_id,
        languages=[language]
    )
    
    # Interpret text that matches the pattern
    result = interpreter.interpret(pattern, language=language)
    
    # Property assertions for command result structure
    
    # 1. Result must be a CommandResult instance
    assert isinstance(result, CommandResult), \
        "interpret() must return a CommandResult instance"
    
    # 2. When is_command is True, verify complete structure
    if result.is_command:
        # 2a. action_id must not be None
        assert result.action_id is not None, \
            "action_id must not be None when is_command=True"
        
        # 2b. action_id must be a non-empty string
        assert isinstance(result.action_id, str), \
            f"action_id must be a string, but got {type(result.action_id)}"
        assert len(result.action_id) > 0, \
            "action_id must not be empty when is_command=True"
        
        # 2c. parameters must be a dictionary
        assert isinstance(result.parameters, dict), \
            f"parameters must be a dict, but got {type(result.parameters)}"
        
        # 2d. raw_text must be present and match input
        assert result.raw_text is not None, \
            "raw_text must not be None"
        assert isinstance(result.raw_text, str), \
            f"raw_text must be a string, but got {type(result.raw_text)}"
        assert result.raw_text == pattern, \
            f"raw_text must match input text. Expected '{pattern}', got '{result.raw_text}'"
        
        # 2e. confidence must be between 0.0 and 1.0
        assert isinstance(result.confidence, (int, float)), \
            f"confidence must be numeric, but got {type(result.confidence)}"
        assert 0.0 <= result.confidence <= 1.0, \
            f"confidence must be between 0.0 and 1.0, but got {result.confidence}"
        
        # 2f. confidence should be positive for detected commands
        assert result.confidence > 0.0, \
            f"confidence must be positive when is_command=True, but got {result.confidence}"
        
        # 2g. language must be a valid language code
        assert result.language is not None, \
            "language must not be None"
        assert isinstance(result.language, str), \
            f"language must be a string, but got {type(result.language)}"
        assert len(result.language) > 0, \
            "language must not be empty"
        assert result.language in ["en", "hi", "pa"], \
            f"language must be a valid code (en, hi, pa), but got '{result.language}'"
        
        # 2h. is_command must be True (already checked, but verify consistency)
        assert result.is_command is True, \
            "is_command must be True when command is detected"
        
        # 2i. Verify the action_id matches what was registered
        assert result.action_id == action_id, \
            f"action_id must match registered value. Expected '{action_id}', got '{result.action_id}'"
