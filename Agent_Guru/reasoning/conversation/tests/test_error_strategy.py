"""
Tests for error response strategies.
"""

import pytest

from Agent_Guru.reasoning.conversation.error_strategy import (
    ErrorCategory,
    ErrorClassifier,
    ErrorResponse,
    ErrorResponseStrategy,
)
from Agent_Guru.reasoning.models.error import Error, ErrorType


class TestErrorClassifier:
    """Test error classifier."""

    def test_classify_user_error(self):
        """Test classifying user error."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.INVALID_PARAMETERS,
            message="Invalid parameter: duration must be positive",
            details={},
        )

        category = ErrorClassifier.classify_error(error)

        assert category == ErrorCategory.USER_ERROR  # nosec B101

    def test_classify_system_error(self):
        """Test classifying system error."""
        error = Error(
            error_code="ERR_002",
            error_type=ErrorType.SYSTEM_ERROR,
            message="Internal server error: database connection failed",
            details={},
        )

        category = ErrorClassifier.classify_error(error)

        assert category == ErrorCategory.SYSTEM_ERROR  # nosec B101

    def test_classify_external_error(self):
        """Test classifying external error."""
        error = Error(
            error_code="ERR_003",
            error_type=ErrorType.NETWORK_ERROR,
            message="API error: weather service unavailable",
            details={},
        )

        category = ErrorClassifier.classify_error(error)

        assert category == ErrorCategory.EXTERNAL_ERROR  # nosec B101

    def test_classify_timeout(self):
        """Test classifying timeout error."""
        error = Error(
            error_code="ERR_004",
            error_type=ErrorType.EXECUTION_TIMEOUT,
            message="Request timeout after 30 seconds",
            details={},
        )

        category = ErrorClassifier.classify_error(error)

        assert category == ErrorCategory.EXTERNAL_ERROR  # nosec B101

    def test_is_recoverable_invalid_params(self):
        """Test checking if error is recoverable."""
        error = Error(
            error_code="ERR_005",
            error_type=ErrorType.INVALID_PARAMETERS,
            message="Invalid parameters",
            details={},
        )

        is_recoverable = ErrorClassifier.is_recoverable(error)

        assert is_recoverable is True  # nosec B101

    def test_is_not_recoverable_system_error(self):
        """Test checking if system error is not recoverable."""
        error = Error(
            error_code="ERR_006",
            error_type=ErrorType.SYSTEM_ERROR,
            message="System error",
            details={},
            recoverable=False,
        )

        is_recoverable = ErrorClassifier.is_recoverable(error)

        assert is_recoverable is False  # nosec B101

    def test_get_empathy_level_user_error(self):
        """Test empathy level for user error."""
        empathy = ErrorClassifier.get_empathy_level(ErrorCategory.USER_ERROR)

        assert empathy == 0.8  # nosec B101

    def test_get_empathy_level_system_error(self):
        """Test empathy level for system error."""
        empathy = ErrorClassifier.get_empathy_level(ErrorCategory.SYSTEM_ERROR)

        assert empathy == 0.4  # nosec B101


class TestErrorResponseStrategy:
    """Test error response strategy."""

    def test_generate_response_user_error(self):
        """Test generating response for user error."""
        strategy = ErrorResponseStrategy()

        error = Error(
            error_code="ERR_007",
            error_type=ErrorType.INVALID_PARAMETERS,
            message="Invalid parameter: duration must be positive",
            details={},
        )

        response = strategy.generate_error_response(error)

        assert response is not None  # nosec B101
        assert response.category == ErrorCategory.USER_ERROR  # nosec B101
        assert len(response.message) > 0  # nosec B101
        assert response.is_recoverable is True  # nosec B101
        assert response.empathy_level == 0.8  # nosec B101

    def test_generate_response_system_error(self):
        """Test generating response for system error."""
        strategy = ErrorResponseStrategy()

        error = Error(
            error_code="ERR_008",
            error_type=ErrorType.SYSTEM_ERROR,
            message="Internal error: database connection failed",
            details={},
            recoverable=False,
        )

        response = strategy.generate_error_response(error)

        assert response is not None  # nosec B101
        assert response.category == ErrorCategory.SYSTEM_ERROR  # nosec B101
        assert len(response.message) > 0  # nosec B101
        assert response.is_recoverable is False  # nosec B101
        assert "sorry" in response.message.lower() or "error" in response.message.lower()  # nosec B101

    def test_generate_response_with_suggestions(self):
        """Test generating response with suggestions."""
        strategy = ErrorResponseStrategy()

        error = Error(
            error_code="ERR_009",
            error_type=ErrorType.INVALID_INPUT,
            message="Invalid input format",
            details={},
        )

        response = strategy.generate_error_response(error)

        assert response is not None  # nosec B101
        assert len(response.suggestions) > 0  # nosec B101
        assert response.is_recoverable is True  # nosec B101

    def test_adapt_for_tone_high_empathy(self):
        """Test adapting response for high empathy."""
        strategy = ErrorResponseStrategy()

        original_response = ErrorResponse(
            message="An error occurred.",
            suggestions=["Try again"],
            is_recoverable=True,
            category=ErrorCategory.USER_ERROR,
            empathy_level=0.5,
        )

        adapted = strategy.adapt_for_tone(original_response, empathy_multiplier=1.5)

        assert adapted.empathy_level > original_response.empathy_level  # nosec B101
        assert "sorry" in adapted.message.lower() or "apologize" in adapted.message.lower()  # nosec B101

    def test_adapt_for_tone_low_empathy(self):
        """Test adapting response for low empathy."""
        strategy = ErrorResponseStrategy()

        original_response = ErrorResponse(
            message="Sorry, an error occurred.",
            suggestions=["Try again"],
            is_recoverable=True,
            category=ErrorCategory.SYSTEM_ERROR,
            empathy_level=0.8,
        )

        adapted = strategy.adapt_for_tone(original_response, empathy_multiplier=0.3)

        assert adapted.empathy_level < original_response.empathy_level  # nosec B101
        assert "sorry" not in adapted.message.lower()  # nosec B101


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
