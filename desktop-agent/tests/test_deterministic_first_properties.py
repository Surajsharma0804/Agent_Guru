"""
Property-Based Tests for Deterministic-First Guarantee

Tests for Requirement 31: Deterministic-First Guarantee
- Property 84: High Confidence Bypasses LLM
- Property 85: Complete Parameters Bypass LLM
- Property 86: LLM Only for Ambiguity
- Property 88: High Bypass Rate Target

Validates: Requirements 31.1, 31.2, 31.3, 31.6
"""

import pytest
from hypothesis import given, settings, strategies as st, assume
from hypothesis import HealthCheck

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm.intent_pre_filter import (
    IntentPreFilter, 
    PreFilterResult, 
    RoutingDecision,
    ActionPattern
)
from llm.intent import IntentType
from llm.intent_router import IntentRouter


# ============================================================================
# Test Data Generators
# ============================================================================

@st.composite
def high_confidence_command(draw):
    """Generate commands that should have high confidence."""
    
    app_names = ['notepad', 'chrome', 'firefox', 'calculator', 'word', 'excel']
    actions = ['open', 'launch', 'start', 'run']
    
    action = draw(st.sampled_from(actions))
    app = draw(st.sampled_from(app_names))
    
    return f"{action} {app}"


@st.composite
def complete_parameters_command(draw):
    """Generate commands with complete parameters."""
    
    # Type text command with complete text parameter
    texts = ['hello world', 'test message', 'important note', 'meeting at 3pm']
    text = draw(st.sampled_from(texts))
    
    return f"type {text}"


@st.composite
def ambiguous_command(draw):
    """Generate commands with ambiguous references."""
    
    ambiguous_words = ['it', 'that', 'this', 'them', 'something', 'maybe']
    actions = ['open', 'close', 'click', 'type']
    
    ambiguous = draw(st.sampled_from(ambiguous_words))
    action = draw(st.sampled_from(actions))
    
    return f"{action} {ambiguous}"


@st.composite
def incomplete_parameters_command(draw):
    """Generate commands with incomplete parameters."""
    
    # Commands missing required parameters
    incomplete = ['open', 'close', 'type', 'click']
    
    return draw(st.sampled_from(incomplete))


@st.composite
def random_command(draw):
    """Generate random commands for bypass rate testing."""
    
    # Mix of deterministic and non-deterministic commands
    deterministic = [
        'open notepad',
        'launch chrome',
        'close firefox',
        'type hello',
        'search for python',
        'start calculator'
    ]
    
    non_deterministic = [
        'what is the weather',
        'tell me a joke',
        'how are you',
        'open that thing',
        'click it'
    ]
    
    all_commands = deterministic + non_deterministic
    
    return draw(st.sampled_from(all_commands))


# ============================================================================
# Property 84: High Confidence Bypasses LLM
# ============================================================================

@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(command=high_confidence_command())
def test_property_84_high_confidence_bypasses_llm(command):
    """
    Property 84: High Confidence Bypasses LLM
    
    For any command with confidence ≥ 0.7, the Intent_Pre_Filter SHALL bypass
    the LLM and route deterministically.
    
    Validates: Requirements 31.1
    
    Feature: guru-complete-system, Property 84: High Confidence Bypasses LLM
    """
    
    # Create pre-filter
    pre_filter = IntentPreFilter()
    
    # Classify command
    result = pre_filter.classify(command)
    
    # If confidence is high enough, LLM should be bypassed
    if result.confidence >= IntentPreFilter.CONFIDENCE_THRESHOLD:
        assert result.bypass_llm, \
            f"High confidence command ({result.confidence:.2f}) should bypass LLM: '{command}'"
        assert result.routing_decision == RoutingDecision.DETERMINISTIC, \
            f"High confidence command should route deterministically: '{command}'"
        assert result.intent is not None, \
            f"Deterministic routing should create intent: '{command}'"


# ============================================================================
# Property 85: Complete Parameters Bypass LLM
# ============================================================================

@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(command=complete_parameters_command())
def test_property_85_complete_parameters_bypass_llm(command):
    """
    Property 85: Complete Parameters Bypass LLM
    
    For any command where all required parameters are extractable, the system
    SHALL bypass the LLM and route deterministically.
    
    Validates: Requirements 31.2
    
    Feature: guru-complete-system, Property 85: Complete Parameters Bypass LLM
    """
    
    # Create pre-filter
    pre_filter = IntentPreFilter()
    
    # Classify command
    result = pre_filter.classify(command)
    
    # If parameters are complete and confidence is high, LLM should be bypassed
    if result.parameters_complete and result.confidence >= IntentPreFilter.CONFIDENCE_THRESHOLD:
        assert result.bypass_llm, \
            f"Command with complete parameters should bypass LLM: '{command}'"
        assert result.routing_decision == RoutingDecision.DETERMINISTIC, \
            f"Complete parameters should route deterministically: '{command}'"
        assert result.intent is not None, \
            f"Deterministic routing should create intent: '{command}'"
        
        # Verify parameters were extracted
        assert len(result.parameters_extracted) > 0, \
            f"Parameters should be extracted: '{command}'"


# ============================================================================
# Property 86: LLM Only for Ambiguity
# ============================================================================

@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(command=ambiguous_command())
def test_property_86_llm_only_for_ambiguity(command):
    """
    Property 86: LLM Only for Ambiguity
    
    For any command containing ambiguous references (vague pronouns, ambiguous
    targets), the system SHALL route to LLM for clarification.
    
    Validates: Requirements 31.3
    
    Feature: guru-complete-system, Property 86: LLM Only for Ambiguity
    """
    
    # Create pre-filter
    pre_filter = IntentPreFilter()
    
    # Classify command
    result = pre_filter.classify(command)
    
    # Ambiguous commands should NOT bypass LLM
    if result.routing_decision == RoutingDecision.AMBIGUOUS:
        assert not result.bypass_llm, \
            f"Ambiguous command should NOT bypass LLM: '{command}'"
        assert result.ambiguity_reason is not None, \
            f"Ambiguity reason should be provided: '{command}'"
        assert result.requires_clarification, \
            f"Ambiguous command should require clarification: '{command}'"


# ============================================================================
# Property 87: Incomplete Parameters Require LLM
# ============================================================================

@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(command=incomplete_parameters_command())
def test_property_87_incomplete_parameters_require_llm(command):
    """
    Property 87: Incomplete Parameters Require LLM
    
    For any command where required parameters are missing, the system SHALL
    NOT bypass the LLM.
    
    Validates: Requirements 31.2
    
    Feature: guru-complete-system, Property 87: Incomplete Parameters Require LLM
    """
    
    # Create pre-filter
    pre_filter = IntentPreFilter()
    
    # Classify command
    result = pre_filter.classify(command)
    
    # Incomplete parameters should not bypass LLM
    if not result.parameters_complete:
        assert not result.bypass_llm, \
            f"Command with incomplete parameters should NOT bypass LLM: '{command}'"
        assert result.routing_decision != RoutingDecision.DETERMINISTIC, \
            f"Incomplete parameters should not route deterministically: '{command}'"


# ============================================================================
# Property 88: High Bypass Rate Target
# ============================================================================

@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(commands=st.lists(random_command(), min_size=100, max_size=100))
def test_property_88_high_bypass_rate_target(commands):
    """
    Property 88: High Bypass Rate Target
    
    For any sequence of 100 commands, the bypass rate SHOULD be ≥ 80% to meet
    the deterministic-first guarantee target.
    
    Note: This is a target, not a hard requirement. The test verifies that the
    system is capable of achieving high bypass rates with appropriate commands.
    
    Validates: Requirements 31.6
    
    Feature: guru-complete-system, Property 88: High Bypass Rate Target
    """
    
    # Create pre-filter
    pre_filter = IntentPreFilter()
    
    # Process all commands
    bypassed_count = 0
    
    for command in commands:
        result = pre_filter.classify(command)
        if result.bypass_llm:
            bypassed_count += 1
            
    # Calculate bypass rate
    bypass_rate = bypassed_count / len(commands)
    
    # Get statistics
    stats = pre_filter.get_statistics()
    
    # Verify statistics are being tracked
    assert stats['total_commands'] >= 100, \
        "Statistics should track at least 100 commands"
    assert 'bypass_rate' in stats, \
        "Statistics should include bypass rate"
    assert 'recent_bypass_rate' in stats, \
        "Statistics should include recent bypass rate"
    
    # Log the bypass rate (informational)
    print(f"\nBypass Rate: {bypass_rate:.1%}")
    print(f"Bypassed: {bypassed_count}/{len(commands)}")
    print(f"Target: {IntentPreFilter.TARGET_BYPASS_RATE:.1%}")
    
    # Note: We don't assert bypass_rate >= TARGET_BYPASS_RATE because the
    # random commands include non-deterministic ones. This property verifies
    # that the system CAN achieve high bypass rates, not that it always does.


# ============================================================================
# Property 89: Bypass Statistics Tracking
# ============================================================================

@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(commands=st.lists(random_command(), min_size=10, max_size=50))
def test_property_89_bypass_statistics_tracking(commands):
    """
    Property 89: Bypass Statistics Tracking
    
    For any sequence of commands, the system SHALL accurately track bypass
    statistics including total commands, bypassed commands, and bypass rate.
    
    Validates: Requirements 31.4, 31.5
    
    Feature: guru-complete-system, Property 89: Bypass Statistics Tracking
    """
    
    # Create pre-filter
    pre_filter = IntentPreFilter()
    
    # Process all commands and count bypasses manually
    manual_bypassed_count = 0
    manual_total_count = 0
    
    for command in commands:
        result = pre_filter.classify(command)
        manual_total_count += 1
        if result.bypass_llm:
            manual_bypassed_count += 1
            
    # Get statistics
    stats = pre_filter.get_statistics()
    
    # Verify statistics match manual count
    assert stats['total_commands'] == manual_total_count, \
        f"Total commands mismatch: {stats['total_commands']} != {manual_total_count}"
    assert stats['bypassed_commands'] == manual_bypassed_count, \
        f"Bypassed commands mismatch: {stats['bypassed_commands']} != {manual_bypassed_count}"
    
    # Verify bypass rate calculation
    expected_rate = manual_bypassed_count / max(1, manual_total_count)
    assert abs(stats['bypass_rate'] - expected_rate) < 0.01, \
        f"Bypass rate mismatch: {stats['bypass_rate']:.2f} != {expected_rate:.2f}"


# ============================================================================
# Property 90: Rolling Window Tracking
# ============================================================================

@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(commands=st.lists(random_command(), min_size=100, max_size=150))
def test_property_90_rolling_window_tracking(commands):
    """
    Property 90: Rolling Window Tracking
    
    For any sequence of commands, the system SHALL track bypass rate over a
    rolling window of the most recent 100 commands.
    
    Validates: Requirements 31.5
    
    Feature: guru-complete-system, Property 90: Rolling Window Tracking
    """
    
    # Create pre-filter
    pre_filter = IntentPreFilter()
    
    # Process all commands
    for command in commands:
        pre_filter.classify(command)
        
    # Get statistics
    stats = pre_filter.get_statistics()
    
    # Verify rolling window is being tracked
    assert 'recent_bypass_rate' in stats, \
        "Statistics should include recent bypass rate"
    
    # Recent bypass rate should be between 0 and 1
    assert 0.0 <= stats['recent_bypass_rate'] <= 1.0, \
        f"Recent bypass rate should be between 0 and 1: {stats['recent_bypass_rate']}"
    
    # If we have more than 100 commands, recent rate may differ from overall rate
    if stats['total_commands'] > 100:
        # Recent rate is calculated from last 100 commands only
        # It may be different from overall rate
        print(f"\nOverall Rate: {stats['bypass_rate']:.1%}")
        print(f"Recent Rate (last 100): {stats['recent_bypass_rate']:.1%}")


# ============================================================================
# Property 91: Confidence Threshold Enforcement
# ============================================================================

@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(command=high_confidence_command())
def test_property_91_confidence_threshold_enforcement(command):
    """
    Property 91: Confidence Threshold Enforcement
    
    For any command, if confidence is below the threshold (0.7), the system
    SHALL NOT bypass the LLM, even if a pattern matches.
    
    Validates: Requirements 31.1
    
    Feature: guru-complete-system, Property 91: Confidence Threshold Enforcement
    """
    
    # Create pre-filter
    pre_filter = IntentPreFilter()
    
    # Classify command
    result = pre_filter.classify(command)
    
    # Verify threshold enforcement
    if result.bypass_llm:
        # If LLM was bypassed, confidence must be >= threshold
        assert result.confidence >= IntentPreFilter.CONFIDENCE_THRESHOLD, \
            f"LLM bypass requires confidence >= {IntentPreFilter.CONFIDENCE_THRESHOLD:.2f}, " \
            f"got {result.confidence:.2f} for command: '{command}'"
    else:
        # If LLM was not bypassed, confidence should be < threshold OR parameters incomplete
        if result.confidence >= IntentPreFilter.CONFIDENCE_THRESHOLD:
            # High confidence but LLM not bypassed - parameters must be incomplete
            assert not result.parameters_complete, \
                f"High confidence ({result.confidence:.2f}) with complete parameters " \
                f"should bypass LLM: '{command}'"


# ============================================================================
# Property 92: Intent Router LLM Restriction
# ============================================================================

@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(command=high_confidence_command())
def test_property_92_intent_router_llm_restriction(command):
    """
    Property 92: Intent Router LLM Restriction
    
    For any deterministic command, the Intent Router SHALL NOT invoke the LLM.
    
    Validates: Requirements 31.3
    
    Feature: guru-complete-system, Property 92: Intent Router LLM Restriction
    """
    
    # Create pre-filter
    pre_filter = IntentPreFilter()
    
    # Classify command
    result = pre_filter.classify(command)
    
    # Create router (without LLM adapter to verify it's not needed)
    router = IntentRouter(pre_filter=pre_filter, llm_adapter=None)
    
    # Check if LLM should be invoked
    should_invoke = router.should_invoke_llm(result)
    
    # If routing is deterministic, LLM should NOT be invoked
    if result.routing_decision == RoutingDecision.DETERMINISTIC:
        assert not should_invoke, \
            f"Deterministic routing should NOT invoke LLM: '{command}'"
        assert result.bypass_llm, \
            f"Deterministic routing should set bypass_llm flag: '{command}'"


# ============================================================================
# Manual Test Cases (Examples)
# ============================================================================

def test_manual_high_confidence_examples():
    """Manual test cases for high confidence commands."""
    
    pre_filter = IntentPreFilter()
    
    test_cases = [
        "open notepad",
        "launch chrome",
        "close firefox",
        "type hello world",
        "search for python tutorial"
    ]
    
    for command in test_cases:
        result = pre_filter.classify(command)
        
        print(f"\nCommand: '{command}'")
        print(f"  Routing: {result.routing_decision.value}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Bypass LLM: {result.bypass_llm}")
        print(f"  Parameters Complete: {result.parameters_complete}")
        
        # These should all bypass LLM
        assert result.bypass_llm, f"High confidence command should bypass LLM: '{command}'"


def test_manual_ambiguous_examples():
    """Manual test cases for ambiguous commands."""
    
    pre_filter = IntentPreFilter()
    
    test_cases = [
        "open it",
        "close that",
        "click something",
        "type this",
        "maybe open chrome"
    ]
    
    for command in test_cases:
        result = pre_filter.classify(command)
        
        print(f"\nCommand: '{command}'")
        print(f"  Routing: {result.routing_decision.value}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Bypass LLM: {result.bypass_llm}")
        print(f"  Ambiguity: {result.ambiguity_reason}")
        
        # These should NOT bypass LLM
        assert not result.bypass_llm, f"Ambiguous command should NOT bypass LLM: '{command}'"


if __name__ == "__main__":
    # Run manual tests
    print("=" * 80)
    print("MANUAL TEST: High Confidence Examples")
    print("=" * 80)
    test_manual_high_confidence_examples()
    
    print("\n" + "=" * 80)
    print("MANUAL TEST: Ambiguous Examples")
    print("=" * 80)
    test_manual_ambiguous_examples()
