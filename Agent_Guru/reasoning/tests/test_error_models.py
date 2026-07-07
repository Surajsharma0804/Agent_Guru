"""Comprehensive unit tests for error models - 100% coverage."""

import pytest

from Agent_Guru.reasoning.models.error import (
    Error,
    ErrorType,
    FallbackStrategy,
)


class TestError:
    """Test Error model."""
    
    def test_error_creation_valid(self):
        """Test creating a valid error."""
        error = Error(
            error_code="ERR_INTENT_001",
            error_type=ErrorType.INTENT_DETECTION_FAILED,
            message="Failed to detect intent from input",
            details={"input": "mumble mumble", "confidence": 0.12},
            recoverable=True,
            suggested_fallback=FallbackStrategy.USER_NOTIFICATION,
            user_message="I didn't understand that. Could you rephrase?",
        )
        
        assert error.error_code == "ERR_INTENT_001"  # nosec B101
        assert error.error_type == ErrorType.INTENT_DETECTION_FAILED  # nosec B101
        assert error.message == "Failed to detect intent from input"  # nosec B101
        assert error.details == {"input": "mumble mumble", "confidence": 0.12}  # nosec B101
        assert error.recoverable  # nosec B101
        assert error.suggested_fallback == FallbackStrategy.USER_NOTIFICATION  # nosec B101
        assert error.user_message == "I didn't understand that. Could you rephrase?"  # nosec B101
    
    def test_error_code_validation_invalid_empty(self):
        """Test error code validation fails for empty code."""
        with pytest.raises(ValueError, match="Error code cannot be empty"):
            Error(
                error_code="",
                error_type=ErrorType.SYSTEM_ERROR,
                message="Test",
            )
    
    def test_error_code_validation_invalid_whitespace(self):
        """Test error code validation fails for whitespace-only code."""
        with pytest.raises(ValueError, match="Error code cannot be empty"):
            Error(
                error_code="   ",
                error_type=ErrorType.SYSTEM_ERROR,
                message="Test",
            )
    
    def test_error_message_validation_invalid_empty(self):
        """Test error message validation fails for empty message."""
        with pytest.raises(ValueError, match="Error message cannot be empty"):
            Error(
                error_code="ERR_001",
                error_type=ErrorType.SYSTEM_ERROR,
                message="",
            )
    
    def test_error_message_validation_invalid_whitespace(self):
        """Test error message validation fails for whitespace-only message."""
        with pytest.raises(ValueError, match="Error message cannot be empty"):
            Error(
                error_code="ERR_001",
                error_type=ErrorType.SYSTEM_ERROR,
                message="  ",
            )
    
    def test_is_timeout_error_reasoning_timeout(self):
        """Test is_timeout_error for reasoning timeout."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.REASONING_TIMEOUT,
            message="Reasoning timed out",
        )
        assert error.is_timeout_error()  # nosec B101
    
    def test_is_timeout_error_execution_timeout(self):
        """Test is_timeout_error for execution timeout."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.EXECUTION_TIMEOUT,
            message="Execution timed out",
        )
        assert error.is_timeout_error()  # nosec B101
    
    def test_is_timeout_error_llm_timeout(self):
        """Test is_timeout_error for LLM timeout."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.LLM_TIMEOUT,
            message="LLM timed out",
        )
        assert error.is_timeout_error()  # nosec B101
    
    def test_is_timeout_error_false(self):
        """Test is_timeout_error returns False for non-timeout errors."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.INVALID_INPUT,
            message="Invalid input",
        )
        assert not error.is_timeout_error()  # nosec B101
    
    def test_is_llm_error_unavailable(self):
        """Test is_llm_error for LLM unavailable."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.LLM_UNAVAILABLE,
            message="LLM unavailable",
        )
        assert error.is_llm_error()  # nosec B101
    
    def test_is_llm_error_timeout(self):
        """Test is_llm_error for LLM timeout."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.LLM_TIMEOUT,
            message="LLM timeout",
        )
        assert error.is_llm_error()  # nosec B101
    
    def test_is_llm_error_rate_limit(self):
        """Test is_llm_error for LLM rate limit."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.LLM_RATE_LIMIT,
            message="LLM rate limit",
        )
        assert error.is_llm_error()  # nosec B101
    
    def test_is_llm_error_invalid_response(self):
        """Test is_llm_error for LLM invalid response."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.LLM_INVALID_RESPONSE,
            message="LLM invalid response",
        )
        assert error.is_llm_error()  # nosec B101
    
    def test_is_llm_error_false(self):
        """Test is_llm_error returns False for non-LLM errors."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.INVALID_INPUT,
            message="Invalid input",
        )
        assert not error.is_llm_error()  # nosec B101
    
    def test_is_safety_error_permission_denied(self):
        """Test is_safety_error for permission denied."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.PERMISSION_DENIED,
            message="Permission denied",
        )
        assert error.is_safety_error()  # nosec B101
    
    def test_is_safety_error_sensitive_action_blocked(self):
        """Test is_safety_error for sensitive action blocked."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.SENSITIVE_ACTION_BLOCKED,
            message="Sensitive action blocked",
        )
        assert error.is_safety_error()  # nosec B101
    
    def test_is_safety_error_confirmation_required(self):
        """Test is_safety_error for confirmation required."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.CONFIRMATION_REQUIRED,
            message="Confirmation required",
        )
        assert error.is_safety_error()  # nosec B101
    
    def test_is_safety_error_false(self):
        """Test is_safety_error returns False for non-safety errors."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.INVALID_INPUT,
            message="Invalid input",
        )
        assert not error.is_safety_error()  # nosec B101
    
    def test_should_retry_llm_timeout(self):
        """Test should_retry for LLM timeout."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.LLM_TIMEOUT,
            message="LLM timeout",
            recoverable=True,
        )
        assert error.should_retry()  # nosec B101
    
    def test_should_retry_execution_timeout(self):
        """Test should_retry for execution timeout."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.EXECUTION_TIMEOUT,
            message="Execution timeout",
            recoverable=True,
        )
        assert error.should_retry()  # nosec B101
    
    def test_should_retry_network_error(self):
        """Test should_retry for network error."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.NETWORK_ERROR,
            message="Network error",
            recoverable=True,
        )
        assert error.should_retry()  # nosec B101
    
    def test_should_retry_service_unavailable(self):
        """Test should_retry for service unavailable."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.SERVICE_UNAVAILABLE,
            message="Service unavailable",
            recoverable=True,
        )
        assert error.should_retry()  # nosec B101
    
    def test_should_retry_rate_limit(self):
        """Test should_retry for rate limit."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.LLM_RATE_LIMIT,
            message="Rate limit",
            recoverable=True,
        )
        assert error.should_retry()  # nosec B101
    
    def test_should_retry_false_not_recoverable(self):
        """Test should_retry returns False for non-recoverable errors."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.LLM_TIMEOUT,
            message="LLM timeout",
            recoverable=False,
        )
        assert not error.should_retry()  # nosec B101
    
    def test_should_retry_false_wrong_type(self):
        """Test should_retry returns False for non-retryable error types."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.INVALID_INPUT,
            message="Invalid input",
            recoverable=True,
        )
        assert not error.should_retry()  # nosec B101
    
    def test_get_user_friendly_message_custom(self):
        """Test get_user_friendly_message returns custom message."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.INVALID_INPUT,
            message="Technical error",
            user_message="Custom user message",
        )
        assert error.get_user_friendly_message() == "Custom user message"  # nosec B101
    
    def test_get_user_friendly_message_invalid_input(self):
        """Test get_user_friendly_message for invalid input."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.INVALID_INPUT,
            message="Technical error",
        )
        assert "didn't understand" in error.get_user_friendly_message()  # nosec B101
    
    def test_get_user_friendly_message_ambiguous_intent(self):
        """Test get_user_friendly_message for ambiguous intent."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.AMBIGUOUS_INTENT,
            message="Technical error",
        )
        assert "not sure what you mean" in error.get_user_friendly_message()  # nosec B101
    
    def test_get_user_friendly_message_unknown_intent(self):
        """Test get_user_friendly_message for unknown intent."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.UNKNOWN_INTENT,
            message="Technical error",
        )
        assert "not sure how to help" in error.get_user_friendly_message()  # nosec B101
    
    def test_get_user_friendly_message_no_tool_found(self):
        """Test get_user_friendly_message for no tool found."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.NO_TOOL_FOUND,
            message="Technical error",
        )
        assert "don't have the capability" in error.get_user_friendly_message()  # nosec B101
    
    def test_get_user_friendly_message_permission_denied(self):
        """Test get_user_friendly_message for permission denied."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.PERMISSION_DENIED,
            message="Technical error",
        )
        assert "don't have permission" in error.get_user_friendly_message()  # nosec B101
    
    def test_get_user_friendly_message_execution_timeout(self):
        """Test get_user_friendly_message for execution timeout."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.EXECUTION_TIMEOUT,
            message="Technical error",
        )
        assert "taking longer than expected" in error.get_user_friendly_message()  # nosec B101
    
    def test_get_user_friendly_message_llm_unavailable(self):
        """Test get_user_friendly_message for LLM unavailable."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.LLM_UNAVAILABLE,
            message="Technical error",
        )
        assert "having trouble thinking" in error.get_user_friendly_message()  # nosec B101
    
    def test_get_user_friendly_message_system_error(self):
        """Test get_user_friendly_message for system error."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.SYSTEM_ERROR,
            message="Technical error",
        )
        assert "Something went wrong" in error.get_user_friendly_message()  # nosec B101
    
    def test_get_user_friendly_message_default(self):
        """Test get_user_friendly_message for unmapped error type."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.CONFIGURATION_ERROR,
            message="Technical error",
        )
        assert "encountered an error" in error.get_user_friendly_message()  # nosec B101
    
    def test_error_equality(self):
        """Test error equality comparison."""
        error1 = Error(
            error_code="ERR_001",
            error_type=ErrorType.INVALID_INPUT,
            message="Test",
        )
        error2 = Error(
            error_code="ERR_001",
            error_type=ErrorType.INVALID_INPUT,
            message="Test",
        )
        error3 = Error(
            error_code="ERR_002",
            error_type=ErrorType.INVALID_INPUT,
            message="Test",
        )
        
        assert error1 == error2  # nosec B101
        assert error1 != error3  # nosec B101
        assert error1 != "not an error"  # nosec B101
    
    def test_error_hash(self):
        """Test error hashing."""
        error1 = Error(
            error_code="ERR_001",
            error_type=ErrorType.INVALID_INPUT,
            message="Test",
        )
        error2 = Error(
            error_code="ERR_001",
            error_type=ErrorType.INVALID_INPUT,
            message="Test",
        )
        
        assert hash(error1) == hash(error2)  # nosec B101
    
    def test_error_type_enum(self):
        """Test error type enum values."""
        assert ErrorType.INVALID_INPUT == "invalid_input"  # nosec B101
        assert ErrorType.INTENT_DETECTION_FAILED == "intent_detection_failed"  # nosec B101
        assert ErrorType.PERMISSION_DENIED == "permission_denied"  # nosec B101
        assert ErrorType.LLM_UNAVAILABLE == "llm_unavailable"  # nosec B101
    
    def test_fallback_strategy_enum(self):
        """Test fallback strategy enum values."""
        assert FallbackStrategy.CLOUD_TO_LOCAL_LLM == "cloud_to_local_llm"  # nosec B101
        assert FallbackStrategy.ALTERNATIVE_TOOL == "alternative_tool"  # nosec B101
        assert FallbackStrategy.RETRY_WITH_BACKOFF == "retry_with_backoff"  # nosec B101
        assert FallbackStrategy.NONE == "none"  # nosec B101
