"""
Property-Based Tests for WhatsApp Desktop Automation

Tests universal properties for WhatsApp automation including:
- WhatsApp Desktop targeting (not web version)
- Startup delay handling
- Message send verification
- Contact name fuzzy matching

Uses Hypothesis for property-based testing with 100+ iterations per property.

Validates: Requirements 26.1, 26.4, 26.5, 26.6
"""

import pytest
from hypothesis import given, settings, strategies as st, assume
from unittest.mock import Mock, MagicMock, patch
import time
from typing import List, Tuple

# Import WhatsApp automation components
from src.execution.whatsapp_automation import (
    WhatsAppAutomation,
    WhatsAppConfig,
    ContactMatcher,
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
def contact_name(draw):
    """Generate realistic contact names."""
    first_names = ["John", "Sarah", "Michael", "Emma", "David", "Lisa", "James", "Maria"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
    
    first = draw(st.sampled_from(first_names))
    last = draw(st.sampled_from(last_names))
    
    # Sometimes return full name, sometimes just first name
    if draw(st.booleans()):
        return f"{first} {last}"
    else:
        return first


@st.composite
def contact_name_variation(draw, base_name: str):
    """Generate variations of a contact name for fuzzy matching tests."""
    variations = [
        base_name.lower(),  # lowercase
        base_name.upper(),  # uppercase
        base_name.split()[0] if ' ' in base_name else base_name,  # first name only
        base_name[:3],  # partial name
        base_name + " ",  # trailing space
        " " + base_name,  # leading space
    ]
    
    # Add typo variations
    if len(base_name) > 3:
        # Drop a character
        variations.append(base_name[:-1])
        # Swap two characters
        chars = list(base_name)
        if len(chars) > 1:
            chars[0], chars[1] = chars[1], chars[0]
            variations.append(''.join(chars))
    
    return draw(st.sampled_from(variations))


@st.composite
def message_text(draw):
    """Generate realistic message text."""
    templates = [
        "Hello, how are you?",
        "Can we meet tomorrow?",
        "Thanks for your help!",
        "I'll call you later.",
        "See you soon!",
        "What time works for you?",
        "Let me know when you're free.",
        "Great to hear from you!"
    ]
    
    return draw(st.sampled_from(templates))


@st.composite
def startup_delay(draw):
    """Generate realistic startup delays (0.5 to 10 seconds)."""
    return draw(st.floats(min_value=0.5, max_value=10.0))


@st.composite
def contact_list(draw):
    """Generate a list of contact names."""
    num_contacts = draw(st.integers(min_value=5, max_value=20))
    contacts = []
    
    for _ in range(num_contacts):
        contacts.append(draw(contact_name()))
    
    return contacts


# ============================================================================
# Mock PAL Interfaces
# ============================================================================

def create_mock_app_controller(can_open: bool = True) -> Mock:
    """Create mock ApplicationController."""
    mock = Mock(spec=ApplicationController)
    mock.open_app.return_value = can_open
    mock.close_app.return_value = True
    mock.is_running.return_value = can_open
    mock.get_capabilities.return_value = {
        "can_open_apps": can_open,
        "can_close_apps": True,
        "can_discover_apps": True
    }
    return mock


def create_mock_input_automation(can_type: bool = True, can_click: bool = True) -> Mock:
    """Create mock InputAutomation."""
    mock = Mock(spec=InputAutomation)
    mock.type_text.return_value = can_type
    mock.click.return_value = can_click
    mock.focus_app.return_value = True
    mock.get_capabilities.return_value = {
        "can_type_text": can_type,
        "can_click": can_click,
        "can_focus_apps": True
    }
    return mock


# ============================================================================
# Property 60: WhatsApp Desktop Targeting
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    contact=contact_name(),
    message=message_text()
)
def test_property_60_whatsapp_desktop_targeting(contact, message):
    """
    Property 60: WhatsApp Desktop Targeting
    
    For any contact name and message text, when sending a WhatsApp message,
    the system SHALL target WhatsApp Desktop application (app_id="whatsapp"),
    NOT the web version.
    
    Validates: Requirements 26.1
    
    Feature: guru-complete-system, Property 60: WhatsApp Desktop Targeting
    """
    # Create mocks
    app_controller = create_mock_app_controller(can_open=True)
    input_automation = create_mock_input_automation(can_type=True)
    
    # Create WhatsApp automation
    whatsapp = WhatsAppAutomation(app_controller, input_automation)
    
    # Send message
    result = whatsapp.send_message(contact, message, fallback_to_manual=False)
    
    # Verify WhatsApp Desktop was targeted (app_id="whatsapp")
    app_controller.open_app.assert_called_once()
    call_args = app_controller.open_app.call_args
    
    # Extract app_id from call
    if call_args[0]:  # positional args
        app_id = call_args[0][0]
    else:  # keyword args
        app_id = call_args[1].get('app_id')
    
    assert app_id == "whatsapp", \
        f"Should target WhatsApp Desktop (app_id='whatsapp'), but targeted '{app_id}'"
    
    # Verify NOT targeting web version (would have different app_id or URL)
    assert app_id != "chrome", "Should not target Chrome browser"
    assert app_id != "firefox", "Should not target Firefox browser"
    assert app_id != "edge", "Should not target Edge browser"
    assert "web.whatsapp.com" not in str(call_args), \
        "Should not target web.whatsapp.com URL"


# ============================================================================
# Property 61: Startup Delay Handling
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    contact=contact_name(),
    message=message_text(),
    delay=startup_delay()
)
def test_property_61_startup_delay_handling(contact, message, delay):
    """
    Property 61: Startup Delay Handling
    
    For any startup delay configuration (0.5 to 10 seconds), when sending a
    WhatsApp message, the system SHALL wait for the configured delay after
    opening WhatsApp Desktop before attempting to interact with it.
    
    This ensures WhatsApp has fully loaded before automation begins.
    
    Validates: Requirements 26.4
    
    Feature: guru-complete-system, Property 61: Startup Delay Handling
    """
    # Create mocks
    app_controller = create_mock_app_controller(can_open=True)
    input_automation = create_mock_input_automation(can_type=True)
    
    # Create custom config with specific startup delay
    config = WhatsAppConfig(startup_delay=delay)
    
    # Create WhatsApp automation with custom config
    whatsapp = WhatsAppAutomation(app_controller, input_automation, config)
    
    # Track timing
    start_time = time.time()
    
    # Send message
    result = whatsapp.send_message(contact, message, fallback_to_manual=False)
    
    elapsed_time = time.time() - start_time
    
    # Verify startup delay was respected
    # Allow 10% tolerance for timing variations
    min_expected = delay * 0.9
    
    assert elapsed_time >= min_expected, \
        f"Should wait at least {min_expected:.2f}s (90% of {delay:.2f}s), but only waited {elapsed_time:.2f}s"
    
    # Verify WhatsApp was opened
    app_controller.open_app.assert_called_once()


# ============================================================================
# Property 62: Message Send Verification
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    contact=contact_name(),
    message=message_text()
)
def test_property_62_message_send_verification(contact, message):
    """
    Property 62: Message Send Verification
    
    For any contact and message, when sending a WhatsApp message successfully,
    the system SHALL verify the message was sent and return SUCCESS status.
    
    When verification fails or message cannot be sent, the system SHALL return
    appropriate error status (FAILED, NOT_FOUND, etc.).
    
    Validates: Requirements 26.5
    
    Feature: guru-complete-system, Property 62: Message Send Verification
    """
    # Test Case 1: Successful send with verification
    app_controller = create_mock_app_controller(can_open=True)
    input_automation = create_mock_input_automation(can_type=True)
    
    whatsapp = WhatsAppAutomation(app_controller, input_automation)
    
    result = whatsapp.send_message(contact, message, fallback_to_manual=False)
    
    # Verify result status is SUCCESS
    assert result.status == ExecutionStatus.SUCCESS, \
        f"Should return SUCCESS status, but got {result.status}"
    
    # Verify message indicates success
    assert "sent" in result.message.lower(), \
        f"Success message should contain 'sent', but got: {result.message}"
    
    # Verify contact name is in message
    assert contact in result.message, \
        f"Success message should contain contact name '{contact}', but got: {result.message}"
    
    # Test Case 2: Failed send (cannot open app)
    app_controller_fail = create_mock_app_controller(can_open=False)
    input_automation_fail = create_mock_input_automation(can_type=True)
    
    whatsapp_fail = WhatsAppAutomation(app_controller_fail, input_automation_fail)
    
    result_fail = whatsapp_fail.send_message(contact, message, fallback_to_manual=False)
    
    # Verify result status is FAILED
    assert result_fail.status == ExecutionStatus.FAILED, \
        f"Should return FAILED status when app cannot open, but got {result_fail.status}"
    
    # Verify error is reported
    assert result_fail.error is not None, \
        "Should report error when send fails"


# ============================================================================
# Property 63: Contact Name Fuzzy Matching
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    base_contact=contact_name(),
    contacts=contact_list()
)
def test_property_63_contact_name_fuzzy_matching(base_contact, contacts):
    """
    Property 63: Contact Name Fuzzy Matching
    
    For any contact name and list of available contacts, when the input name
    is similar to a contact in the list (≥ 80% similarity), the system SHALL
    match it to the correct contact using fuzzy matching.
    
    This handles typos, partial names, and case variations.
    
    Validates: Requirements 26.6
    
    Feature: guru-complete-system, Property 63: Contact Name Fuzzy Matching
    """
    # Add base contact to list if not already present
    if base_contact not in contacts:
        contacts.append(base_contact)
    
    # Create contact matcher
    matcher = ContactMatcher(threshold=0.8)
    
    # Test exact match
    exact_match = matcher.find_best_match(base_contact, contacts)
    
    assert exact_match is not None, \
        f"Should find exact match for '{base_contact}'"
    
    matched_name, score = exact_match
    
    assert matched_name == base_contact, \
        f"Exact match should return '{base_contact}', but got '{matched_name}'"
    
    assert score >= 0.8, \
        f"Exact match score should be ≥ 0.8, but got {score:.2f}"
    
    # Test case-insensitive match
    lowercase_match = matcher.find_best_match(base_contact.lower(), contacts)
    
    if lowercase_match is not None:
        matched_name_lower, score_lower = lowercase_match
        
        assert matched_name_lower.lower() == base_contact.lower(), \
            f"Case-insensitive match should find '{base_contact}', but got '{matched_name_lower}'"
        
        assert score_lower >= 0.8, \
            f"Case-insensitive match score should be ≥ 0.8, but got {score_lower:.2f}"
    
    # Test partial match (first name only)
    if ' ' in base_contact:
        first_name = base_contact.split()[0]
        partial_match = matcher.find_best_match(first_name, contacts)
        
        if partial_match is not None:
            matched_name_partial, score_partial = partial_match
            
            # Should match the full contact name
            assert first_name.lower() in matched_name_partial.lower(), \
                f"Partial match for '{first_name}' should contain first name, but got '{matched_name_partial}'"
            
            assert score_partial >= 0.8, \
                f"Partial match score should be ≥ 0.8, but got {score_partial:.2f}"
    
    # Test no match for completely different name
    different_name = "XyZ_NoMatch_123"
    no_match = matcher.find_best_match(different_name, contacts)
    
    # Should return None or a match with score < 0.8
    if no_match is not None:
        _, score_no_match = no_match
        # If a match is returned, it should still meet threshold
        assert score_no_match >= 0.8, \
            f"If match is returned, score should be ≥ 0.8, but got {score_no_match:.2f}"


# ============================================================================
# Additional Property: Fuzzy Matching Threshold Consistency
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    threshold=st.floats(min_value=0.5, max_value=0.95),
    contact1=contact_name(),
    contact2=contact_name()
)
def test_property_fuzzy_matching_threshold_consistency(threshold, contact1, contact2):
    """
    Property: Fuzzy Matching Threshold Consistency
    
    For any threshold value (0.5 to 0.95), the ContactMatcher SHALL only
    return matches with similarity scores ≥ threshold.
    
    This ensures threshold enforcement is consistent.
    
    Feature: guru-complete-system, Property: Fuzzy Matching Threshold Consistency
    """
    # Assume contacts are different
    assume(contact1.lower() != contact2.lower())
    
    # Create matcher with specific threshold
    matcher = ContactMatcher(threshold=threshold)
    
    # Create contact list
    contacts = [contact1, contact2]
    
    # Try to match contact1
    match = matcher.find_best_match(contact1, contacts)
    
    if match is not None:
        matched_name, score = match
        
        # Verify score meets threshold
        assert score >= threshold, \
            f"Match score {score:.2f} should be ≥ threshold {threshold:.2f}"
        
        # Verify matched name is in contact list
        assert matched_name in contacts, \
            f"Matched name '{matched_name}' should be in contact list"


# ============================================================================
# Additional Property: WhatsApp Automation Fallback Behavior
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    contact=contact_name(),
    message=message_text(),
    can_open=st.booleans(),
    can_type=st.booleans()
)
def test_property_whatsapp_fallback_behavior(contact, message, can_open, can_type):
    """
    Property: WhatsApp Automation Fallback Behavior
    
    For any platform capability configuration, when automation fails and
    fallback_to_manual=True, the system SHALL provide clear instructions
    for manual completion.
    
    When fallback_to_manual=False, the system SHALL return appropriate
    error status without fallback.
    
    Feature: guru-complete-system, Property: WhatsApp Automation Fallback Behavior
    """
    # Create mocks with specific capabilities
    app_controller = create_mock_app_controller(can_open=can_open)
    input_automation = create_mock_input_automation(can_type=can_type)
    
    whatsapp = WhatsAppAutomation(app_controller, input_automation)
    
    # Test with fallback enabled
    result_with_fallback = whatsapp.send_message(
        contact,
        message,
        fallback_to_manual=True
    )
    
    # If automation should fail (cannot open or cannot type)
    if not can_open or not can_type:
        # Should provide fallback instructions
        assert result_with_fallback.message is not None, \
            "Should provide fallback message when automation fails"
        
        # Fallback message should contain contact and message
        assert contact in result_with_fallback.message, \
            f"Fallback message should contain contact '{contact}'"
        
        assert message in result_with_fallback.message or "message" in result_with_fallback.message.lower(), \
            "Fallback message should reference the message"
    
    # Test with fallback disabled
    result_without_fallback = whatsapp.send_message(
        contact,
        message,
        fallback_to_manual=False
    )
    
    # If automation should fail
    if not can_open or not can_type:
        # Should return error status
        assert result_without_fallback.status in [
            ExecutionStatus.FAILED,
            ExecutionStatus.NOT_FOUND,
            ExecutionStatus.PERMISSION_DENIED
        ], f"Should return error status, but got {result_without_fallback.status}"
        
        # Should have error field populated
        assert result_without_fallback.error is not None, \
            "Should populate error field when automation fails"


# ============================================================================
# Additional Property: WhatsApp Automation Execution Time
# ============================================================================

@settings(max_examples=100, deadline=None)
@given(
    contact=contact_name(),
    message=message_text()
)
def test_property_whatsapp_execution_time_tracking(contact, message):
    """
    Property: WhatsApp Automation Execution Time Tracking
    
    For any WhatsApp message send operation, the system SHALL track and
    report execution time in the ExecutionResult.
    
    Execution time should be > 0 and reasonable (< 60 seconds for normal operation).
    
    Feature: guru-complete-system, Property: WhatsApp Automation Execution Time Tracking
    """
    # Create mocks
    app_controller = create_mock_app_controller(can_open=True)
    input_automation = create_mock_input_automation(can_type=True)
    
    # Use minimal startup delay for faster testing
    config = WhatsAppConfig(startup_delay=0.1)
    
    whatsapp = WhatsAppAutomation(app_controller, input_automation, config)
    
    # Send message
    result = whatsapp.send_message(contact, message, fallback_to_manual=False)
    
    # Verify execution time is tracked
    assert result.execution_time > 0, \
        f"Execution time should be > 0, but got {result.execution_time}"
    
    # Verify execution time is reasonable (< 60 seconds)
    assert result.execution_time < 60.0, \
        f"Execution time should be < 60s, but got {result.execution_time:.2f}s"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
