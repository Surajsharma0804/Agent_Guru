"""
Property-Based Tests for Exact Text Dictation

Tests universal properties for exact text dictation including:
- Exact text preservation (no interpretation)
- Intent Pre-Filter bypass in dictation mode
- LLM bypass in dictation mode
- Integration with DICTATION_MODE state

Uses Hypothesis for property-based testing with 100+ iterations per property.

Validates: Requirements 2.5, 14, 21.6, 29.3, 29.4
"""

import pytest
from hypothesis import given, settings, strategies as st, assume
from unittest.mock import Mock, MagicMock, patch, call
import time
from typing import Optional

# Import command executor components
from src.execution.command_executor import (
    CommandExecutor,
    ExecutionStatus,
    ExecutionResult
)

# Import PAL interfaces for mocking
from src.pal.interfaces import (
    ApplicationController,
    InputAutomation,
    AutomationTarget,
    PlatformCapabilityError
)


# ============================================================================
# Test Data Generators
# ============================================================================

@st.composite
def exact_text(draw):
    """
    Generate text that should be typed exactly as-is.
    
    Includes:
    - Regular sentences
    - Text with punctuation
    - Text with numbers
    - Text with special characters
    - Text with mixed case
    - Text with whitespace variations
    """
    templates = [
        # Regular sentences
        "Hello, how are you today?",
        "The quick brown fox jumps over the lazy dog.",
        "I need to finish this report by 5 PM.",
        
        # Text with numbers
        "My phone number is 555-1234.",
        "The meeting is at 3:30 PM on March 15th.",
        "Please send $100 to account #12345.",
        
        # Text with special characters
        "Email me at user@example.com!",
        "Check out https://www.example.com for more info.",
        "Use code: ABC-123-XYZ (expires 12/31/2024)",
        
        # Text with mixed case
        "iPhone 15 Pro Max",
        "JavaScript and TypeScript",
        "NASA and SpaceX",
        
        # Text with whitespace variations
        "Line 1\nLine 2\nLine 3",
        "Tab\tseparated\tvalues",
        "Multiple    spaces    between    words",
        
        # Text that might be misinterpreted
        "open notepad",  # Looks like command but should be typed literally
        "search for python tutorial",  # Looks like command
        "write hello world",  # Looks like command
        
        # Text with grammar errors (should NOT be corrected)
        "i dont have no time",  # Double negative
        "Me and him went to store",  # Grammar error
        "Their going too the park",  # Wrong their/there/they're
    ]
    
    return draw(st.sampled_from(templates))


@st.composite
def text_with_variations(draw):
    """Generate text with various formatting variations."""
    base_texts = [
        "Hello World",
        "Test 123",
        "Special!@#$%",
        "Mixed CaSe TeXt",
    ]
    
    base = draw(st.sampled_from(base_texts))
    
    # Add variations
    variations = [
        base,
        base.lower(),
        base.upper(),
        base + "\n",
        "\n" + base,
        base + "  ",  # trailing spaces
        "  " + base,  # leading spaces
        base.replace(" ", "\t"),  # tabs instead of spaces
    ]
    
    return draw(st.sampled_from(variations))


@st.composite
def target_application(draw):
    """Generate target application names."""
    apps = [
        "notepad",
        "word",
        "excel",
        "chrome",
        "vscode",
        None,  # No specific target (use focused app)
    ]
    
    return draw(st.sampled_from(apps))


# ============================================================================
# Mock PAL Interfaces
# ============================================================================

def create_mock_app_controller() -> Mock:
    """Create mock ApplicationController."""
    mock = Mock(spec=ApplicationController)
    mock.open_app.return_value = True
    mock.close_app.return_value = True
    mock.is_running.return_value = True
    mock.get_capabilities.return_value = {
        "can_open_apps": True,
        "can_close_apps": True,
        "can_discover_apps": True
    }
    return mock


def create_mock_input_automation(can_type: bool = True) -> Mock:
    """Create mock InputAutomation."""
    mock = Mock(spec=InputAutomation)
    mock.type_text.return_value = can_type
    mock.focus_app.return_value = True
    mock.get_capabilities.return_value = {
        "can_type_text": can_type,
        "can_click": True,
        "can_focus_apps": True
    }
    return mock


# ============================================================================
# Property 9: Exact Text Dictation
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    text=exact_text(),
    target_app=target_application()
)
def test_property_9_exact_text_dictation(text, target_app):
    """
    Property 9: Exact Text Dictation
    
    For any text string, when executing dictation, the system SHALL type the
    text EXACTLY as provided without any interpretation, grammar correction,
    rephrasing, or modification.
    
    This ensures dictation preserves user intent precisely.
    
    Validates: Requirements 2.5, 14, 21.6
    
    Feature: guru-complete-system, Property 9: Exact Text Dictation
    """
    # Create mocks
    app_controller = create_mock_app_controller()
    input_automation = create_mock_input_automation(can_type=True)
    
    # Create command executor
    executor = CommandExecutor(app_controller, input_automation)
    
    # Execute dictation
    result = executor.execute_dictation(text, target_app)
    
    # Verify execution succeeded
    assert result.status == ExecutionStatus.SUCCESS, \
        f"Dictation should succeed, but got status: {result.status}"
    
    # Verify type_text was called with EXACT text (no modification)
    input_automation.type_text.assert_called_once()
    
    # Get the actual text that was typed
    call_args = input_automation.type_text.call_args
    if call_args[0]:  # positional args
        typed_text = call_args[0][0]
    else:  # keyword args
        typed_text = call_args[1].get('text')
    
    # CRITICAL: Text must be EXACTLY the same (no modification)
    assert typed_text == text, \
        f"Text should be typed EXACTLY as provided.\nExpected: '{text}'\nActual: '{typed_text}'"
    
    # Verify no grammar correction
    assert typed_text.lower() == text.lower() or typed_text == text, \
        "Text should not be case-corrected"
    
    # Verify no rephrasing
    assert len(typed_text) == len(text), \
        f"Text length should be preserved. Expected {len(text)}, got {len(typed_text)}"


# ============================================================================
# Property 74: Intent Pre-Filter Bypass in Dictation
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    text=exact_text()
)
def test_property_74_intent_pre_filter_bypass_in_dictation(text):
    """
    Property 74: Intent Pre-Filter Bypass in Dictation
    
    For any text in dictation mode, the Intent_Pre_Filter SHALL be bypassed
    completely. The text should go directly to text automation without any
    pattern matching or intent recognition.
    
    This ensures commands like "open notepad" are typed literally, not executed.
    
    Validates: Requirements 29.3
    
    Feature: guru-complete-system, Property 74: Intent Pre-Filter Bypass in Dictation
    """
    # Create mocks
    app_controller = create_mock_app_controller()
    input_automation = create_mock_input_automation(can_type=True)
    
    # Create command executor
    executor = CommandExecutor(app_controller, input_automation)
    
    # Execute dictation (bypasses intent recognition)
    result = executor.execute_dictation(text)
    
    # Verify execution succeeded
    assert result.status == ExecutionStatus.SUCCESS, \
        f"Dictation should succeed, but got status: {result.status}"
    
    # Verify text was typed (not executed as command)
    input_automation.type_text.assert_called_once()
    
    # Verify NO application was opened (even if text looks like "open notepad")
    # The execute_dictation method should NOT call app_controller.open_app
    app_controller.open_app.assert_not_called()
    
    # Verify the text was typed exactly as-is
    call_args = input_automation.type_text.call_args
    if call_args[0]:
        typed_text = call_args[0][0]
    else:
        typed_text = call_args[1].get('text')
    
    assert typed_text == text, \
        f"Text should be typed exactly, not interpreted as command"


# ============================================================================
# Property 75: LLM Bypass in Dictation
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    text=exact_text()
)
def test_property_75_llm_bypass_in_dictation(text):
    """
    Property 75: LLM Bypass in Dictation
    
    For any text in dictation mode, the LLM_Adapter SHALL be bypassed completely.
    No LLM processing, no grammar correction, no rephrasing should occur.
    
    This ensures dictation is fast and preserves exact user input.
    
    Validates: Requirements 29.4
    
    Feature: guru-complete-system, Property 75: LLM Bypass in Dictation
    """
    # Create mocks
    app_controller = create_mock_app_controller()
    input_automation = create_mock_input_automation(can_type=True)
    
    # Create command executor
    executor = CommandExecutor(app_controller, input_automation)
    
    # Mock LLM adapter to verify it's not called
    with patch('src.llm.adapter.LLMAdapter') as mock_llm:
        # Execute dictation
        result = executor.execute_dictation(text)
        
        # Verify execution succeeded
        assert result.status == ExecutionStatus.SUCCESS, \
            f"Dictation should succeed, but got status: {result.status}"
        
        # Verify LLM was NOT called
        mock_llm.assert_not_called()
        
        # Verify text was typed exactly
        input_automation.type_text.assert_called_once()
        
        call_args = input_automation.type_text.call_args
        if call_args[0]:
            typed_text = call_args[0][0]
        else:
            typed_text = call_args[1].get('text')
        
        # Text should be EXACTLY the same (no LLM processing)
        assert typed_text == text, \
            f"Text should not be processed by LLM.\nExpected: '{text}'\nActual: '{typed_text}'"


# ============================================================================
# Additional Property: Dictation Preserves Whitespace
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    text=text_with_variations()
)
def test_property_dictation_preserves_whitespace(text):
    """
    Property: Dictation Preserves Whitespace
    
    For any text with whitespace variations (spaces, tabs, newlines), dictation
    SHALL preserve the exact whitespace formatting without normalization.
    
    Feature: guru-complete-system, Property: Dictation Preserves Whitespace
    """
    # Create mocks
    app_controller = create_mock_app_controller()
    input_automation = create_mock_input_automation(can_type=True)
    
    # Create command executor
    executor = CommandExecutor(app_controller, input_automation)
    
    # Execute dictation
    result = executor.execute_dictation(text)
    
    # Verify execution succeeded
    assert result.status == ExecutionStatus.SUCCESS, \
        f"Dictation should succeed, but got status: {result.status}"
    
    # Get typed text
    call_args = input_automation.type_text.call_args
    if call_args[0]:
        typed_text = call_args[0][0]
    else:
        typed_text = call_args[1].get('text')
    
    # Verify whitespace is preserved EXACTLY
    assert typed_text == text, \
        f"Whitespace should be preserved exactly.\nExpected: {repr(text)}\nActual: {repr(typed_text)}"
    
    # Verify leading whitespace preserved
    if text.startswith(' ') or text.startswith('\t') or text.startswith('\n'):
        assert typed_text[0] == text[0], \
            "Leading whitespace should be preserved"
    
    # Verify trailing whitespace preserved
    if text.endswith(' ') or text.endswith('\t') or text.endswith('\n'):
        assert typed_text[-1] == text[-1], \
            "Trailing whitespace should be preserved"


# ============================================================================
# Additional Property: Dictation Platform Capability Check
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    text=exact_text(),
    can_type=st.booleans()
)
def test_property_dictation_platform_capability_check(text, can_type):
    """
    Property: Dictation Platform Capability Check
    
    For any platform capability configuration, dictation SHALL check if text
    automation is supported before attempting to type.
    
    If not supported, it should return appropriate error status.
    
    Feature: guru-complete-system, Property: Dictation Platform Capability Check
    """
    # Create mocks with specific capability
    app_controller = create_mock_app_controller()
    input_automation = create_mock_input_automation(can_type=can_type)
    
    # Create command executor
    executor = CommandExecutor(app_controller, input_automation)
    
    # Execute dictation
    result = executor.execute_dictation(text)
    
    if can_type:
        # Should succeed
        assert result.status == ExecutionStatus.SUCCESS, \
            f"Dictation should succeed when platform supports typing, but got: {result.status}"
        
        # Verify text was typed
        input_automation.type_text.assert_called_once()
    else:
        # Should fail with appropriate error
        assert result.status == ExecutionStatus.FAILED, \
            f"Dictation should fail when platform doesn't support typing, but got: {result.status}"
        
        # Error message should indicate platform limitation
        assert "platform" in result.message.lower() or "not support" in result.message.lower(), \
            f"Error message should indicate platform limitation: {result.message}"
        
        # Should NOT attempt to type
        input_automation.type_text.assert_not_called()


# ============================================================================
# Additional Property: Dictation Target App Focus
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    text=exact_text(),
    target_app=target_application()
)
def test_property_dictation_target_app_focus(text, target_app):
    """
    Property: Dictation Target App Focus
    
    For any target application specified, dictation SHALL attempt to focus
    that application before typing text.
    
    If no target specified, it should type into currently focused app.
    
    Feature: guru-complete-system, Property: Dictation Target App Focus
    """
    # Create mocks
    app_controller = create_mock_app_controller()
    input_automation = create_mock_input_automation(can_type=True)
    
    # Create command executor
    executor = CommandExecutor(app_controller, input_automation)
    
    # Execute dictation with target app
    result = executor.execute_dictation(text, target_app)
    
    # Verify execution succeeded
    assert result.status == ExecutionStatus.SUCCESS, \
        f"Dictation should succeed, but got status: {result.status}"
    
    if target_app is not None:
        # Should attempt to focus target app
        input_automation.focus_app.assert_called_once_with(target_app)
    else:
        # Should NOT attempt to focus (use currently focused app)
        # focus_app might still be called, but not with a specific app
        pass
    
    # Should type text regardless
    input_automation.type_text.assert_called_once()


# ============================================================================
# Additional Property: Dictation Execution Time Tracking
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    text=exact_text()
)
def test_property_dictation_execution_time_tracking(text):
    """
    Property: Dictation Execution Time Tracking
    
    For any dictation operation, the system SHALL track and report execution
    time in the ExecutionResult.
    
    Execution time should be >= 0 and reasonable (< 10 seconds for normal text).
    
    Note: When using mocks, execution time may be 0.0 (instant execution).
    In production, execution time will be > 0 due to actual I/O operations.
    
    Feature: guru-complete-system, Property: Dictation Execution Time Tracking
    """
    # Create mocks
    app_controller = create_mock_app_controller()
    input_automation = create_mock_input_automation(can_type=True)
    
    # Create command executor
    executor = CommandExecutor(app_controller, input_automation)
    
    # Execute dictation
    result = executor.execute_dictation(text)
    
    # Verify execution time is tracked (>= 0, including 0.0 for mocks)
    assert result.execution_time >= 0, \
        f"Execution time should be >= 0, but got {result.execution_time}"
    
    # Verify execution time is reasonable (< 10 seconds)
    assert result.execution_time < 10.0, \
        f"Execution time should be < 10s for normal text, but got {result.execution_time:.2f}s"


# ============================================================================
# Additional Property: Dictation Brief Confirmation
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    text=exact_text()
)
def test_property_dictation_brief_confirmation(text):
    """
    Property: Dictation Brief Confirmation
    
    For any successful dictation, the system SHALL provide a brief confirmation
    message following the Human Co-Worker Speech Contract (≤ 5 words).
    
    Typical confirmation: "Typed"
    
    Feature: guru-complete-system, Property: Dictation Brief Confirmation
    """
    # Create mocks
    app_controller = create_mock_app_controller()
    input_automation = create_mock_input_automation(can_type=True)
    
    # Create command executor
    executor = CommandExecutor(app_controller, input_automation)
    
    # Execute dictation
    result = executor.execute_dictation(text)
    
    # Verify execution succeeded
    assert result.status == ExecutionStatus.SUCCESS, \
        f"Dictation should succeed, but got status: {result.status}"
    
    # Verify message is brief (≤ 5 words)
    message_words = result.message.split()
    assert len(message_words) <= 5, \
        f"Confirmation message should be ≤ 5 words, but got {len(message_words)} words: '{result.message}'"
    
    # Verify message is appropriate
    assert result.message.lower() in ["typed", "done", "sent"], \
        f"Confirmation should be brief action phrase, but got: '{result.message}'"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
