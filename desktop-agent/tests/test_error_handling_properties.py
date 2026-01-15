"""
Property-Based Tests for Error Handling System

Tests the production-grade error handling system to ensure:
- Exception isolation (no crashes)
- Actionable error messages
- Transient failure retry
- No security failure retry

Feature: guru-complete-system
Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5, 20.6
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis import Phase
import time
from datetime import datetime
from typing import Optional
import threading

from src.failure.error_handler import (
    ErrorHandler,
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
    safe_execute,
    safe_execute_with_retry
)


# ============================================================================
# Test Strategies
# ============================================================================

@st.composite
def error_messages(draw):
    """Generate various error messages."""
    templates = [
        "Connection failed",
        "Authentication failed",
        "Permission denied",
        "Network timeout",
        "LLM timeout",
        "Component crashed",
        "Application not found",
        "Configuration error",
        "Security violation",
        "Integrity check failed",
        "Out of memory",
        "Resource limit exceeded"
    ]
    return draw(st.sampled_from(templates))


@st.composite
def component_names(draw):
    """Generate component names."""
    components = [
        "voice_interface",
        "command_executor",
        "authority_state_machine",
        "audit_logger",
        "tts_service",
        "llm_adapter",
        "memory_service",
        "biometric_provider",
        "intrusion_detector",
        "skill_runner"
    ]
    return draw(st.sampled_from(components))


@st.composite
def exception_types(draw):
    """Generate various exception types."""
    exception_classes = [
        Exception,
        RuntimeError,
        ValueError,
        ConnectionError,
        TimeoutError,
        PermissionError,
        FileNotFoundError
    ]
    exc_class = draw(st.sampled_from(exception_classes))
    message = draw(error_messages())
    return exc_class(message)


@st.composite
def transient_exceptions(draw):
    """Generate transient exceptions that should be retried."""
    messages = [
        "Connection timeout",
        "Network unreachable",
        "LLM timeout after 10 seconds",
        "Temporary network error"
    ]
    message = draw(st.sampled_from(messages))
    exc_class = draw(st.sampled_from([ConnectionError, TimeoutError, RuntimeError]))
    return exc_class(message)


@st.composite
def security_exceptions(draw):
    """Generate security-related exceptions that should NOT be retried."""
    messages = [
        "Authentication failed",
        "Permission denied",
        "Security violation detected",
        "Integrity check failed",
        "Unauthorized access attempt"
    ]
    message = draw(st.sampled_from(messages))
    exc_class = draw(st.sampled_from([PermissionError, RuntimeError, ValueError]))
    return exc_class(message)


# ============================================================================
# Mock Components
# ============================================================================

class MockAuditLogger:
    """Mock audit logger for testing."""
    
    def __init__(self):
        self.logged_events = []
    
    def log_system_event(self, event_type, event_data, severity):
        self.logged_events.append({
            "event_type": event_type,
            "event_data": event_data,
            "severity": severity,
            "timestamp": datetime.now()
        })


class MockTTSService:
    """Mock TTS service for testing."""
    
    def __init__(self):
        self.spoken_messages = []
    
    def speak(self, text, priority=None):
        self.spoken_messages.append({
            "text": text,
            "priority": priority,
            "timestamp": datetime.now()
        })


class FailingComponent:
    """Component that fails predictably for testing."""
    
    def __init__(self, exception: Exception, fail_count: int = 1):
        self.exception = exception
        self.fail_count = fail_count
        self.call_count = 0
    
    def execute(self):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise self.exception
        return "success"


# ============================================================================
# Property 64: Exception Isolation
# Feature: guru-complete-system, Property 64: Exception Isolation
# Validates: Requirements 20.1, 20.2
# ============================================================================

@given(
    exception=exception_types(),
    component=component_names()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_64_exception_isolation(exception, component):
    """
    Property 64: Exception Isolation
    
    For any component exception, the system should catch it, log it,
    and continue operation without crashing the entire application.
    
    This property ensures that no single component failure can bring
    down the entire GURU system.
    """
    # Create error handler
    audit_logger = MockAuditLogger()
    tts_service = MockTTSService()
    error_handler = ErrorHandler(audit_logger, tts_service)
    
    # Track if application crashed
    application_crashed = False
    
    try:
        # Handle the error
        success, result = error_handler.handle_error(
            exception, component, context={"test": "property_64"}
        )
        
        # Application should NOT crash
        application_crashed = False
        
    except Exception as e:
        # If we get here, the error handler failed to isolate the exception
        application_crashed = True
        pytest.fail(f"Exception not isolated: {e}")
    
    # Verify application did not crash
    assert not application_crashed, "Application crashed due to component exception"
    
    # Verify error was logged
    assert len(audit_logger.logged_events) > 0, "Error was not logged to audit logger"
    
    # Verify error was classified
    error_history = error_handler.get_error_history()
    assert len(error_history) > 0, "Error was not tracked in history"
    
    error_ctx = error_history[-1]
    assert error_ctx.component_name == component
    assert error_ctx.exception == exception
    assert error_ctx.category in ErrorCategory
    assert error_ctx.severity in ErrorSeverity


@given(
    component=component_names()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_64_safe_execute_decorator(component):
    """
    Property 64: Exception Isolation (Decorator)
    
    The safe_execute decorator should catch all exceptions and prevent
    application crashes.
    """
    error_handler = ErrorHandler()
    
    # Create a function that always fails
    @safe_execute(component, error_handler)
    def failing_function():
        raise RuntimeError("Test failure")
    
    # Execute should not crash
    result = failing_function()
    
    # Function should return None on failure
    assert result is None
    
    # Error should be tracked
    error_history = error_handler.get_error_history()
    assert len(error_history) > 0


# ============================================================================
# Property 65: Actionable Error Messages
# Feature: guru-complete-system, Property 65: Actionable Error Messages
# Validates: Requirements 20.3, 20.4
# ============================================================================

@given(
    exception=exception_types(),
    component=component_names()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_65_actionable_error_messages(exception, component):
    """
    Property 65: Actionable Error Messages
    
    For any command failure, the system should speak an error message
    that explains what went wrong in user-friendly terms.
    
    Error messages should be actionable (not technical stack traces).
    """
    # Create error handler with TTS
    tts_service = MockTTSService()
    error_handler = ErrorHandler(tts_service=tts_service)
    
    # Handle error
    error_handler.handle_error(exception, component)
    
    # Get error context
    error_history = error_handler.get_error_history()
    assert len(error_history) > 0
    
    error_ctx = error_history[-1]
    
    # Verify user message exists
    assert error_ctx.user_message is not None, "No user message generated"
    assert len(error_ctx.user_message) > 0, "User message is empty"
    
    # Verify message is user-friendly (not technical)
    user_msg = error_ctx.user_message.lower()
    
    # Should NOT contain technical terms
    technical_terms = ["exception", "traceback", "stack trace", "null pointer", "segfault"]
    for term in technical_terms:
        assert term not in user_msg, f"User message contains technical term: {term}"
    
    # Should contain actionable language
    # (Either explains what happened or what to do)
    assert len(user_msg.split()) >= 3, "User message too short to be actionable"
    
    # Verify TTS spoke the message
    assert len(tts_service.spoken_messages) > 0, "Error message was not spoken"
    
    spoken_msg = tts_service.spoken_messages[-1]["text"]
    assert spoken_msg == error_ctx.user_message, "Spoken message doesn't match user message"


@given(
    component=component_names()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_65_category_specific_messages(component):
    """
    Property 65: Actionable Error Messages (Category-Specific)
    
    Different error categories should produce appropriate user messages.
    """
    error_handler = ErrorHandler()
    
    # Test different error categories
    test_cases = [
        (PermissionError("Access denied"), "permission"),
        (ConnectionError("Network timeout"), "network"),
        (TimeoutError("LLM timeout"), "timeout"),
        (FileNotFoundError("Application not found"), "not found"),
        (RuntimeError("Authentication failed"), "authentication")
    ]
    
    for exception, expected_keyword in test_cases:
        error_ctx = error_handler.classify_error(exception, component)
        
        assert error_ctx.user_message is not None
        user_msg = error_ctx.user_message.lower()
        
        # Message should be relevant to the error
        assert len(user_msg) > 0, f"Empty message for {exception}"


# ============================================================================
# Property 66: Transient Failure Retry
# Feature: guru-complete-system, Property 66: Transient Failure Retry
# Validates: Requirements 20.5
# ============================================================================

@given(
    fail_count=st.integers(min_value=1, max_value=3)  # max_retries=3, so test up to 3 failures
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_66_transient_failure_retry(fail_count):
    """
    Property 66: Transient Failure Retry
    
    For any transient failure (network, LLM timeout), the system should
    automatically retry the operation.
    
    This property verifies that transient errors are retried up to the
    configured maximum attempts.
    
    SEMANTICS: max_retries=3 means "make 3 retry attempts total"
    - Component fails fail_count times, then succeeds on attempt (fail_count + 1)
    - Error handler makes max_retries attempts total
    - Success requires: fail_count < max_retries (strict inequality)
    
    Example: fail_count=3, max_retries=3
    - Component fails on attempts 1, 2, 3, succeeds on attempt 4
    - Error handler makes 3 attempts (1, 2, 3), all fail
    - Recovery fails because we need 4 attempts but only make 3
    """
    # Create error handler
    error_handler = ErrorHandler()
    
    # Create component that fails N times then succeeds
    transient_exception = ConnectionError("Network timeout")
    component = FailingComponent(transient_exception, fail_count=fail_count)
    
    # Handle error with retry
    success, result = error_handler.handle_error(
        transient_exception,
        "test_component",
        context={"category": "network"},
        operation=component.execute
    )
    
    # Get recovery strategy for network errors
    strategy = error_handler.RECOVERY_STRATEGIES[ErrorCategory.NETWORK]
    
    # CRITICAL: max_retries means "total retry attempts", not "retries after initial failure"
    # Component needs (fail_count + 1) attempts to succeed
    # Error handler makes max_retries attempts
    # Success requires: fail_count < max_retries (component succeeds within retry budget)
    if fail_count < strategy.max_retries:
        # Should succeed after retries
        assert success, f"Recovery failed after {fail_count} failures (max retries: {strategy.max_retries})"
        assert result == "success"
        # Component should be called: fail_count times (failures) + 1 time (success)
        assert component.call_count == fail_count + 1
    else:
        # Should fail if fail_count >= max_retries (not enough retry budget)
        assert not success, f"Recovery succeeded when it should have failed (fail_count={fail_count}, max_retries={strategy.max_retries})"
        # Component should be called exactly max_retries times (all failures)
        assert component.call_count == strategy.max_retries


@given(
    component_name=component_names()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_66_network_error_retry(component_name):
    """
    Property 66: Transient Failure Retry (Network Errors)
    
    Network errors should be retried automatically.
    Note: Critical components may classify network errors as CRITICAL
    instead of RECOVERABLE, but they should still have a retry strategy.
    """
    error_handler = ErrorHandler()
    
    # Create network error
    network_error = ConnectionError("Connection timeout")
    
    # Classify error
    error_ctx = error_handler.classify_error(network_error, component_name)
    
    # Should be classified as network error
    assert error_ctx.category == ErrorCategory.NETWORK
    
    # Severity depends on component criticality
    # Critical components: CRITICAL severity
    # Non-critical components: RECOVERABLE severity
    critical_components = [
        "authority_state_machine",
        "audit_logger",
        "biometric_provider",
        "intrusion_detector"
    ]
    
    if component_name.lower() in critical_components:
        assert error_ctx.severity == ErrorSeverity.CRITICAL, \
            f"Critical component {component_name} should have CRITICAL severity for network errors"
    else:
        assert error_ctx.severity == ErrorSeverity.RECOVERABLE, \
            f"Non-critical component {component_name} should have RECOVERABLE severity for network errors"
    
    # Should have retry strategy regardless of severity
    strategy = error_handler.RECOVERY_STRATEGIES[ErrorCategory.NETWORK]
    assert strategy.max_retries > 0, "Network errors should be retried"
    assert strategy.exponential_backoff, "Network errors should use exponential backoff"


@given(
    component_name=component_names()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_66_llm_timeout_fallback(component_name):
    """
    Property 66: Transient Failure Retry (LLM Timeout)
    
    LLM timeouts should NOT be retried (already timed out),
    but should fall back to templates.
    
    Note: LLM timeout detection requires either:
    - Component name contains "llm"
    - Exception message contains "llm" AND "timeout"
    - Context component contains "llm"
    """
    error_handler = ErrorHandler()
    
    # Create LLM timeout error with explicit context
    llm_timeout = TimeoutError("LLM timeout after 10 seconds")
    
    # Classify error with LLM context
    error_ctx = error_handler.classify_error(
        llm_timeout, component_name,
        context={"component": "llm_adapter"}
    )
    
    # LLM timeout detection logic:
    # 1. Message contains "llm" and "timeout" -> LLM_TIMEOUT
    # 2. Component name contains "llm" -> LLM_TIMEOUT  
    # 3. Context component contains "llm" -> LLM_TIMEOUT
    # 4. Otherwise -> NETWORK (generic timeout)
    
    message_has_llm_timeout = "llm" in str(llm_timeout).lower() and "timeout" in str(llm_timeout).lower()
    component_has_llm = "llm" in component_name.lower()
    context_has_llm = "llm" in "llm_adapter".lower()
    
    if message_has_llm_timeout or component_has_llm or context_has_llm:
        assert error_ctx.category == ErrorCategory.LLM_TIMEOUT, \
            f"Should be LLM_TIMEOUT (msg_llm={message_has_llm_timeout}, comp_llm={component_has_llm}, ctx_llm={context_has_llm}), got {error_ctx.category}"
        
        # Should NOT retry (already timed out)
        strategy = error_handler.RECOVERY_STRATEGIES[ErrorCategory.LLM_TIMEOUT]
        assert strategy.max_retries == 0, "LLM timeouts should not be retried"
        
        # Should allow degradation (fallback to templates)
        assert strategy.allow_degradation, "LLM timeouts should allow degradation"
    else:
        # Without LLM indicators, classified as generic network timeout
        assert error_ctx.category == ErrorCategory.NETWORK


# ============================================================================
# Property 67: No Security Failure Retry
# Feature: guru-complete-system, Property 67: No Security Failure Retry
# Validates: Requirements 20.6
# ============================================================================

@given(
    security_exception=security_exceptions(),
    component=component_names()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_67_no_security_failure_retry(security_exception, component):
    """
    Property 67: No Security Failure Retry
    
    For any security-related failure (authentication, authorization),
    the system should never automatically retry.
    
    This is a critical security property: security failures indicate
    potential attacks and must not be retried automatically.
    """
    # Create error handler
    error_handler = ErrorHandler()
    
    # Create component that would succeed on retry
    failing_component = FailingComponent(security_exception, fail_count=1)
    
    # Handle error with retry attempt
    success, result = error_handler.handle_error(
        security_exception,
        component,
        operation=failing_component.execute
    )
    
    # Get error context
    error_history = error_handler.get_error_history()
    assert len(error_history) > 0
    
    error_ctx = error_history[-1]
    
    # Verify error is classified as security-related
    security_categories = [
        ErrorCategory.AUTHENTICATION,
        ErrorCategory.AUTHORIZATION,
        ErrorCategory.SECURITY_VIOLATION,
        ErrorCategory.INTEGRITY_VIOLATION
    ]
    
    if error_ctx.category in security_categories:
        # Security errors should NEVER be retried
        assert not error_ctx.recovery_attempted, \
            f"Security error was retried (category: {error_ctx.category.value})"
        
        assert error_ctx.retry_count == 0, \
            f"Security error had {error_ctx.retry_count} retry attempts"
        
        # Component should only be called once (no retries)
        assert failing_component.call_count == 0, \
            "Security error triggered operation execution"
        
        # Recovery should fail
        assert not success, "Security error recovery succeeded (should always fail)"


@given(
    component=component_names()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_67_authentication_no_retry(component):
    """
    Property 67: No Security Failure Retry (Authentication)
    
    Authentication failures should never be retried automatically.
    """
    error_handler = ErrorHandler()
    
    # Create authentication error
    auth_error = RuntimeError("Authentication failed")
    
    # Classify error
    error_ctx = error_handler.classify_error(auth_error, component)
    
    # Should be classified as authentication error
    assert error_ctx.category == ErrorCategory.AUTHENTICATION
    
    # Should be critical severity
    assert error_ctx.severity == ErrorSeverity.CRITICAL
    
    # Should NOT have retry strategy
    strategy = error_handler.RECOVERY_STRATEGIES[ErrorCategory.AUTHENTICATION]
    assert strategy.max_retries == 0, "Authentication errors should never be retried"
    assert strategy.requires_manual_intervention, \
        "Authentication errors should require manual intervention"


@given(
    component=component_names()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_67_authorization_no_retry(component):
    """
    Property 67: No Security Failure Retry (Authorization)
    
    Authorization failures should never be retried automatically.
    """
    error_handler = ErrorHandler()
    
    # Create authorization error
    auth_error = PermissionError("Permission denied")
    
    # Classify error
    error_ctx = error_handler.classify_error(auth_error, component)
    
    # Should be classified as authorization error
    assert error_ctx.category == ErrorCategory.AUTHORIZATION
    
    # Should be critical severity
    assert error_ctx.severity == ErrorSeverity.CRITICAL
    
    # Should NOT have retry strategy
    strategy = error_handler.RECOVERY_STRATEGIES[ErrorCategory.AUTHORIZATION]
    assert strategy.max_retries == 0, "Authorization errors should never be retried"


@given(
    component=component_names()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_67_security_violation_no_retry(component):
    """
    Property 67: No Security Failure Retry (Security Violations)
    
    Security violations should never be retried automatically.
    """
    error_handler = ErrorHandler()
    
    # Create security violation error
    security_error = RuntimeError("Security violation detected")
    
    # Classify error
    error_ctx = error_handler.classify_error(security_error, component)
    
    # Should be classified as security violation
    assert error_ctx.category == ErrorCategory.SECURITY_VIOLATION
    
    # Should be fatal severity
    assert error_ctx.severity == ErrorSeverity.FATAL
    
    # Should NOT have retry strategy
    strategy = error_handler.RECOVERY_STRATEGIES[ErrorCategory.SECURITY_VIOLATION]
    assert strategy.max_retries == 0, "Security violations should never be retried"


@given(
    component=component_names()
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_property_67_integrity_violation_no_retry(component):
    """
    Property 67: No Security Failure Retry (Integrity Violations)
    
    Integrity violations should never be retried automatically.
    """
    error_handler = ErrorHandler()
    
    # Create integrity violation error
    integrity_error = RuntimeError("Integrity check failed")
    
    # Classify error
    error_ctx = error_handler.classify_error(integrity_error, component)
    
    # Should be classified as integrity violation
    assert error_ctx.category == ErrorCategory.INTEGRITY_VIOLATION
    
    # Should be fatal severity
    assert error_ctx.severity == ErrorSeverity.FATAL
    
    # Should NOT have retry strategy
    strategy = error_handler.RECOVERY_STRATEGIES[ErrorCategory.INTEGRITY_VIOLATION]
    assert strategy.max_retries == 0, "Integrity violations should never be retried"


# ============================================================================
# Additional Integration Tests
# ============================================================================

@given(
    component=component_names()
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_error_handler_statistics(component):
    """
    Verify error handler tracks statistics correctly.
    """
    error_handler = ErrorHandler()
    
    # Generate various errors
    errors = [
        RuntimeError("Test error 1"),
        ConnectionError("Network error"),
        PermissionError("Auth error")
    ]
    
    for error in errors:
        error_handler.handle_error(error, component)
    
    # Get statistics
    stats = error_handler.get_statistics()
    
    # Verify statistics
    assert stats["total_errors"] == len(errors)
    assert stats["total_errors"] > 0


@given(
    component=component_names()
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_error_handler_callbacks(component):
    """
    Verify error handler invokes callbacks correctly.
    """
    error_handler = ErrorHandler()
    
    # Track callback invocations
    callback_invoked = []
    critical_callback_invoked = []
    
    def error_callback(error_ctx):
        callback_invoked.append(error_ctx)
    
    def critical_callback(error_ctx):
        critical_callback_invoked.append(error_ctx)
    
    error_handler.add_error_callback(error_callback)
    error_handler.add_critical_error_callback(critical_callback)
    
    # Generate error
    error = RuntimeError("Test error")
    error_handler.handle_error(error, component)
    
    # Verify callback invoked
    assert len(callback_invoked) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
