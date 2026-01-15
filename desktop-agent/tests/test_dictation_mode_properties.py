"""
Property-Based Tests for Dictation Mode

Tests the dictation mode functionality to ensure proper state transitions,
exit conditions, and integration with the voice interface state machine.

Requirements: 29.1, 29.2, 29.6, 29.7
Properties: 73, 77, 78
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, MagicMock
import time

# Import the VoiceInterface class
from gui.voice_interface import VoiceInterface, VoiceState


# Test data generators
@st.composite
def dictation_trigger_command(draw):
    """Generate commands that should trigger dictation mode."""
    triggers = ["write", "type", "dictate"]
    trigger = draw(st.sampled_from(triggers))
    
    # Generate text to be typed
    text_samples = [
        "hello world",
        "this is a test",
        "the quick brown fox",
        "meeting notes for today",
        "dear john comma",
        "python code example"
    ]
    text = draw(st.sampled_from(text_samples))
    
    # Combine trigger and text
    templates = [
        f"{trigger} {text}",
        f"open notepad and {trigger} {text}",
        f"please {trigger} {text}",
        f"{trigger} the following {text}"
    ]
    
    return draw(st.sampled_from(templates))


@st.composite
def non_dictation_command(draw):
    """Generate commands that should NOT trigger dictation mode."""
    commands = [
        "open notepad",
        "close chrome",
        "search for python",
        "send message to john",
        "what is the weather",
        "show me the files",
        "delete this document",
        "launch calculator"
    ]
    return draw(st.sampled_from(commands))


@st.composite
def dictation_exit_command(draw):
    """Generate commands that should exit dictation mode."""
    exit_commands = [
        "done",
        "stop writing",
        "stop typing",
        "finish",
        "that's all done",
        "okay done",
        "stop writing now"
    ]
    return draw(st.sampled_from(exit_commands))


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


# Property 73: Dictation Mode Entry
@settings(max_examples=100, deadline=None)
@given(command=dictation_trigger_command())
def test_property_73_dictation_mode_entry(command):
    """
    Property 73: Dictation Mode Entry
    
    For any command containing "write", "type", or "dictate", when the
    Voice_Interface is in ACTIVE state, the system SHALL enter DICTATION_MODE.
    
    Validates: Requirements 29.2
    """
    # Create voice interface
    voice_interface = create_mock_voice_interface()
    
    # Set to active state (wake word detected)
    voice_interface.is_active = True
    voice_interface._set_state(VoiceState.COMMAND_MODE)
    
    # Check if command should trigger dictation mode
    should_enter = voice_interface.should_enter_dictation_mode(command)
    
    # Verify dictation mode is triggered
    assert should_enter, \
        f"Command '{command}' should trigger dictation mode but didn't"
    
    # Enter dictation mode
    voice_interface.enter_dictation_mode()
    
    # Verify state is DICTATION_MODE
    assert voice_interface.current_state == VoiceState.DICTATION_MODE, \
        f"State should be DICTATION_MODE but is {voice_interface.current_state}"
    
    # Verify dictation_mode flag is set
    assert voice_interface.is_dictation_mode(), \
        "is_dictation_mode() should return True"


# Property 77: Dictation Mode Exit on Silence
@settings(max_examples=100, deadline=None)
@given(silence_duration=st.floats(min_value=2.0, max_value=5.0))
def test_property_77_dictation_mode_exit_on_silence(silence_duration):
    """
    Property 77: Dictation Mode Exit on Silence
    
    For any silence duration >= 2 seconds while in DICTATION_MODE, the
    Voice_Interface SHALL exit DICTATION_MODE and return to COMMAND_MODE.
    
    Validates: Requirements 29.6
    """
    # Create voice interface
    voice_interface = create_mock_voice_interface()
    
    # Enter dictation mode
    voice_interface.is_active = True
    voice_interface.enter_dictation_mode()
    
    # Verify we're in dictation mode
    assert voice_interface.is_dictation_mode()
    
    # Simulate silence by setting silence_start_time
    current_time = time.time()
    voice_interface.silence_start_time = current_time - silence_duration
    
    # Check exit conditions with no speech
    should_exit = voice_interface.check_dictation_exit_conditions(
        text="",
        has_speech=False
    )
    
    # Verify exit is triggered for >= 2 seconds
    if silence_duration >= 2.0:
        assert should_exit, \
            f"Dictation mode should exit after {silence_duration}s of silence"
    
    # Exit dictation mode
    if should_exit:
        voice_interface.exit_dictation_mode()
        
        # Verify state is COMMAND_MODE
        assert voice_interface.current_state == VoiceState.COMMAND_MODE, \
            f"State should be COMMAND_MODE after exit but is {voice_interface.current_state}"
        
        # Verify dictation_mode flag is cleared
        assert not voice_interface.is_dictation_mode(), \
            "is_dictation_mode() should return False after exit"


# Property 78: Dictation Mode Exit on Command
@settings(max_examples=100, deadline=None)
@given(exit_command=dictation_exit_command())
def test_property_78_dictation_mode_exit_on_command(exit_command):
    """
    Property 78: Dictation Mode Exit on Command
    
    For any exit command ("done", "stop writing", etc.) while in DICTATION_MODE,
    the Voice_Interface SHALL exit DICTATION_MODE and return to COMMAND_MODE.
    
    Validates: Requirements 29.7
    """
    # Create voice interface
    voice_interface = create_mock_voice_interface()
    
    # Enter dictation mode
    voice_interface.is_active = True
    voice_interface.enter_dictation_mode()
    
    # Verify we're in dictation mode
    assert voice_interface.is_dictation_mode()
    
    # Check exit conditions with exit command
    should_exit = voice_interface.check_dictation_exit_conditions(
        text=exit_command,
        has_speech=True
    )
    
    # Verify exit is triggered
    assert should_exit, \
        f"Dictation mode should exit on command '{exit_command}'"
    
    # Exit dictation mode
    voice_interface.exit_dictation_mode()
    
    # Verify state is COMMAND_MODE
    assert voice_interface.current_state == VoiceState.COMMAND_MODE, \
        f"State should be COMMAND_MODE after exit but is {voice_interface.current_state}"
    
    # Verify dictation_mode flag is cleared
    assert not voice_interface.is_dictation_mode(), \
        "is_dictation_mode() should return False after exit"


# Additional property: Non-dictation commands don't trigger dictation mode
@settings(max_examples=100, deadline=None)
@given(command=non_dictation_command())
def test_property_non_dictation_commands_dont_trigger(command):
    """
    Property: Non-Dictation Commands Don't Trigger Dictation Mode
    
    For any command that does not contain "write", "type", or "dictate",
    the Voice_Interface SHALL NOT enter DICTATION_MODE.
    
    Validates: Requirements 29.2
    """
    # Create voice interface
    voice_interface = create_mock_voice_interface()
    
    # Set to active state
    voice_interface.is_active = True
    voice_interface._set_state(VoiceState.COMMAND_MODE)
    
    # Check if command should trigger dictation mode
    should_enter = voice_interface.should_enter_dictation_mode(command)
    
    # Verify dictation mode is NOT triggered
    assert not should_enter, \
        f"Command '{command}' should NOT trigger dictation mode but did"


# Additional property: Silence timer resets on speech
@settings(max_examples=100, deadline=None)
@given(
    initial_silence=st.floats(min_value=0.5, max_value=1.5),
    speech_detected=st.booleans()
)
def test_property_silence_timer_resets_on_speech(initial_silence, speech_detected):
    """
    Property: Silence Timer Resets on Speech
    
    For any silence duration < 2 seconds, when speech is detected, the
    silence timer SHALL be reset and dictation mode SHALL NOT exit.
    
    Validates: Requirements 29.6
    """
    # Create voice interface
    voice_interface = create_mock_voice_interface()
    
    # Enter dictation mode
    voice_interface.is_active = True
    voice_interface.enter_dictation_mode()
    
    # Set initial silence
    current_time = time.time()
    voice_interface.silence_start_time = current_time - initial_silence
    
    # Check exit conditions
    should_exit = voice_interface.check_dictation_exit_conditions(
        text="some text" if speech_detected else "",
        has_speech=speech_detected
    )
    
    # Verify behavior
    if speech_detected:
        # Silence timer should be reset, no exit
        assert not should_exit, \
            "Dictation mode should NOT exit when speech is detected"
        # Note: In actual implementation, silence_start_time would be reset to None
    else:
        # No speech, but silence < 2s, should not exit yet
        if initial_silence < 2.0:
            assert not should_exit, \
                f"Dictation mode should NOT exit after only {initial_silence}s of silence"


# Additional property: Dictation mode state consistency
@settings(max_examples=100, deadline=None)
@given(
    enter_count=st.integers(min_value=1, max_value=5),
    exit_count=st.integers(min_value=1, max_value=5)
)
def test_property_dictation_mode_state_consistency(enter_count, exit_count):
    """
    Property: Dictation Mode State Consistency
    
    For any sequence of enter/exit operations, the dictation mode state
    SHALL remain consistent with the is_dictation_mode() flag and the
    current_state value.
    
    Validates: Requirements 29.1, 29.2, 29.6, 29.7
    """
    # Create voice interface
    voice_interface = create_mock_voice_interface()
    voice_interface.is_active = True
    
    # Perform enter/exit operations
    for i in range(max(enter_count, exit_count)):
        if i < enter_count:
            voice_interface.enter_dictation_mode()
            
            # Verify consistency
            assert voice_interface.is_dictation_mode(), \
                f"After enter #{i+1}, is_dictation_mode() should be True"
            assert voice_interface.current_state == VoiceState.DICTATION_MODE, \
                f"After enter #{i+1}, state should be DICTATION_MODE"
        
        if i < exit_count:
            voice_interface.exit_dictation_mode()
            
            # Verify consistency
            assert not voice_interface.is_dictation_mode(), \
                f"After exit #{i+1}, is_dictation_mode() should be False"
            assert voice_interface.current_state == VoiceState.COMMAND_MODE, \
                f"After exit #{i+1}, state should be COMMAND_MODE"


# Additional property: Case-insensitive exit command detection
@settings(max_examples=100, deadline=None)
@given(
    base_command=st.sampled_from(["done", "stop writing", "finish"]),
    case_transform=st.sampled_from(["lower", "upper", "title", "mixed"])
)
def test_property_case_insensitive_exit_commands(base_command, case_transform):
    """
    Property: Case-Insensitive Exit Command Detection
    
    For any exit command in any case variation, the Voice_Interface SHALL
    correctly detect it and exit DICTATION_MODE.
    
    Validates: Requirements 29.7
    """
    # Create voice interface
    voice_interface = create_mock_voice_interface()
    
    # Enter dictation mode
    voice_interface.is_active = True
    voice_interface.enter_dictation_mode()
    
    # Transform command case
    if case_transform == "lower":
        command = base_command.lower()
    elif case_transform == "upper":
        command = base_command.upper()
    elif case_transform == "title":
        command = base_command.title()
    else:  # mixed
        command = "".join(
            c.upper() if i % 2 == 0 else c.lower()
            for i, c in enumerate(base_command)
        )
    
    # Check exit conditions
    should_exit = voice_interface.check_dictation_exit_conditions(
        text=command,
        has_speech=True
    )
    
    # Verify exit is triggered regardless of case
    assert should_exit, \
        f"Exit command '{command}' (from '{base_command}') should trigger exit"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
