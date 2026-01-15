"""
Property-Based Tests for Wake Word Stripping

Tests the wake word stripping functionality to ensure wake words are
properly removed from transcribed text before passing to downstream systems.

Requirements: 30.1, 30.2, 30.3, 30.4
Properties: 79, 80, 81, 82
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, MagicMock

# Import the VoiceInterface class
from gui.voice_interface import VoiceInterface, VoiceState


# Test data generators
@st.composite
def wake_word_text(draw):
    """Generate text that contains a wake word."""
    wake_words = ["hey guru", "hello guru", "hi guru", "hey guro", "hello guro", "hi guro"]
    wake_word = draw(st.sampled_from(wake_words))
    
    # Generate command text
    commands = [
        "open notepad",
        "type hello world",
        "send message to john",
        "search for python tutorial",
        "close chrome",
        "write a letter",
        "what is the weather"
    ]
    command = draw(st.sampled_from(commands))
    
    # Combine wake word and command
    position = draw(st.sampled_from(["start", "middle", "end"]))
    
    if position == "start":
        return f"{wake_word} {command}"
    elif position == "middle":
        words = command.split()
        mid = len(words) // 2
        return f"{' '.join(words[:mid])} {wake_word} {' '.join(words[mid:])}"
    else:  # end
        return f"{command} {wake_word}"


@st.composite
def command_without_wake_word(draw):
    """Generate command text without wake word."""
    commands = [
        "open notepad",
        "type hello world",
        "send message to john",
        "search for python tutorial",
        "close chrome",
        "write a letter",
        "what is the weather",
        "show me the files",
        "delete this document"
    ]
    return draw(st.sampled_from(commands))


@st.composite
def case_variant_wake_word_text(draw):
    """Generate text with wake word in various cases."""
    wake_words = ["hey guru", "hello guru", "hi guru"]
    wake_word = draw(st.sampled_from(wake_words))
    
    # Apply case transformation
    case_type = draw(st.sampled_from(["lower", "upper", "title", "mixed"]))
    if case_type == "lower":
        wake_word = wake_word.lower()
    elif case_type == "upper":
        wake_word = wake_word.upper()
    elif case_type == "title":
        wake_word = wake_word.title()
    else:  # mixed
        wake_word = "".join(
            c.upper() if draw(st.booleans()) else c.lower()
            for c in wake_word
        )
    
    command = draw(command_without_wake_word())
    return f"{wake_word} {command}"


# Helper function to create mock VoiceInterface
def create_mock_voice_interface():
    """Create a VoiceInterface with mocked dependencies."""
    mock_speech_input = Mock()
    mock_speech_input.get_capabilities.return_value = {"wake_word": True, "continuous": True}
    mock_speech_input.calibrate_microphone.return_value = 300.0
    
    mock_speech_output = Mock()
    
    voice_interface = VoiceInterface(
        speech_input=mock_speech_input,
        speech_output=mock_speech_output,
        wake_word="hey guru"
    )
    
    return voice_interface


# Property 79: Wake Word Removal in Active State
@settings(max_examples=100, deadline=None)
@given(text=wake_word_text())
def test_property_79_wake_word_removal_in_active_state(text):
    """
    Property 79: Wake Word Removal in Active State
    
    For any transcribed text containing a wake word, when the Voice_Interface
    is in ACTIVE state, the wake word SHALL be stripped before passing to
    downstream systems.
    
    Validates: Requirements 30.1, 30.2, 30.5
    """
    # Create voice interface
    voice_interface = create_mock_voice_interface()
    
    # Set to active state
    voice_interface.is_active = True
    
    # Strip wake word
    stripped_text = voice_interface.strip_wake_word(text)
    
    # Verify wake word is removed
    stripped_lower = stripped_text.lower()
    wake_word_variations = voice_interface.wake_word_variations
    
    for wake_word in wake_word_variations:
        assert wake_word not in stripped_lower, \
            f"Wake word '{wake_word}' still present in stripped text: '{stripped_text}'"
    
    # Verify some text remains (not completely empty unless input was only wake word)
    if text.lower().strip() not in wake_word_variations:
        assert len(stripped_text.strip()) > 0, \
            f"Stripped text is empty when input had content: '{text}'"


# Property 80: Intent Pre-Filter Never Sees Wake Word
@settings(max_examples=100, deadline=None)
@given(text=wake_word_text())
def test_property_80_intent_pre_filter_never_sees_wake_word(text):
    """
    Property 80: Intent Pre-Filter Never Sees Wake Word
    
    For any command text, the Intent_Pre_Filter SHALL never receive text
    containing the wake word. The wake word must be stripped by the
    Voice_Interface before passing to Intent_Pre_Filter.
    
    Validates: Requirements 30.2
    """
    # Create voice interface
    voice_interface = create_mock_voice_interface()
    voice_interface.is_active = True
    
    # Strip wake word (simulating what happens before Intent_Pre_Filter)
    stripped_text = voice_interface.strip_wake_word(text)
    
    # Verify no wake word variations are present
    stripped_lower = stripped_text.lower()
    for wake_word in voice_interface.wake_word_variations:
        assert wake_word not in stripped_lower, \
            f"Intent_Pre_Filter would receive wake word '{wake_word}' in text: '{stripped_text}'"


# Property 81: Command Executor Never Sees Wake Word
@settings(max_examples=100, deadline=None)
@given(text=wake_word_text())
def test_property_81_command_executor_never_sees_wake_word(text):
    """
    Property 81: Command Executor Never Sees Wake Word
    
    For any command text, the Command_Executor SHALL never receive text
    containing the wake word. The wake word must be stripped by the
    Voice_Interface before passing to Command_Executor.
    
    Validates: Requirements 30.3
    """
    # Create voice interface
    voice_interface = create_mock_voice_interface()
    voice_interface.is_active = True
    
    # Strip wake word (simulating what happens before Command_Executor)
    stripped_text = voice_interface.strip_wake_word(text)
    
    # Verify no wake word variations are present
    stripped_lower = stripped_text.lower()
    for wake_word in voice_interface.wake_word_variations:
        assert wake_word not in stripped_lower, \
            f"Command_Executor would receive wake word '{wake_word}' in text: '{stripped_text}'"


# Property 82: LLM Never Sees Wake Word
@settings(max_examples=100, deadline=None)
@given(text=wake_word_text())
def test_property_82_llm_never_sees_wake_word(text):
    """
    Property 82: LLM Never Sees Wake Word
    
    For any command text, the LLM_Adapter SHALL never receive text
    containing the wake word. The wake word must be stripped by the
    Voice_Interface before passing to LLM_Adapter.
    
    Validates: Requirements 30.4
    """
    # Create voice interface
    voice_interface = create_mock_voice_interface()
    voice_interface.is_active = True
    
    # Strip wake word (simulating what happens before LLM_Adapter)
    stripped_text = voice_interface.strip_wake_word(text)
    
    # Verify no wake word variations are present
    stripped_lower = stripped_text.lower()
    for wake_word in voice_interface.wake_word_variations:
        assert wake_word not in stripped_lower, \
            f"LLM_Adapter would receive wake word '{wake_word}' in text: '{stripped_text}'"


# Additional property: Case-insensitive wake word stripping
@settings(max_examples=100, deadline=None)
@given(text=case_variant_wake_word_text())
def test_property_case_insensitive_wake_word_stripping(text):
    """
    Property: Case-Insensitive Wake Word Stripping
    
    For any wake word in any case variation (upper, lower, title, mixed),
    the wake word SHALL be stripped correctly.
    
    Validates: Requirements 30.6
    """
    # Create voice interface
    voice_interface = create_mock_voice_interface()
    voice_interface.is_active = True
    
    # Strip wake word
    stripped_text = voice_interface.strip_wake_word(text)
    
    # Verify wake word is removed (case-insensitive check)
    stripped_lower = stripped_text.lower()
    for wake_word in voice_interface.wake_word_variations:
        assert wake_word not in stripped_lower, \
            f"Wake word '{wake_word}' still present after case-insensitive stripping: '{stripped_text}'"


# Additional property: Text without wake word remains unchanged
@settings(max_examples=100, deadline=None)
@given(text=command_without_wake_word())
def test_property_text_without_wake_word_unchanged(text):
    """
    Property: Text Without Wake Word Remains Unchanged
    
    For any text that does not contain a wake word, the strip_wake_word
    function SHALL return the text unchanged (except for whitespace normalization).
    
    Validates: Requirements 30.1
    """
    # Create voice interface
    voice_interface = create_mock_voice_interface()
    voice_interface.is_active = True
    
    # Strip wake word
    stripped_text = voice_interface.strip_wake_word(text)
    
    # Verify text is essentially unchanged (allowing for whitespace normalization)
    assert stripped_text.strip() == text.strip(), \
        f"Text without wake word was modified: '{text}' -> '{stripped_text}'"


# Additional property: Wake word at different positions
@settings(max_examples=100, deadline=None)
@given(
    wake_word=st.sampled_from(["hey guru", "hello guru", "hi guru"]),
    command=command_without_wake_word(),
    position=st.sampled_from(["start", "middle", "end"])
)
def test_property_wake_word_position_handling(wake_word, command, position):
    """
    Property: Wake Word Position Handling
    
    For any wake word at any position (start, middle, end) in the text,
    the wake word SHALL be stripped correctly, leaving the command intact.
    
    Validates: Requirements 30.1, 30.5
    """
    # Create voice interface
    voice_interface = create_mock_voice_interface()
    voice_interface.is_active = True
    
    # Construct text with wake word at specified position
    if position == "start":
        text = f"{wake_word} {command}"
    elif position == "middle":
        words = command.split()
        mid = len(words) // 2
        text = f"{' '.join(words[:mid])} {wake_word} {' '.join(words[mid:])}"
    else:  # end
        text = f"{command} {wake_word}"
    
    # Strip wake word
    stripped_text = voice_interface.strip_wake_word(text)
    
    # Verify wake word is removed
    stripped_lower = stripped_text.lower()
    assert wake_word.lower() not in stripped_lower, \
        f"Wake word '{wake_word}' at position '{position}' not stripped: '{stripped_text}'"
    
    # Verify command words are still present
    command_words = command.lower().split()
    for word in command_words:
        if len(word) > 2:  # Skip very short words
            assert word in stripped_lower, \
                f"Command word '{word}' lost after stripping wake word at position '{position}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
