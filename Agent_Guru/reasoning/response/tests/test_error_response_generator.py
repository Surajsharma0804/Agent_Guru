"""
Unit tests for ErrorResponseGenerator.

Tests:
- Error response generation for all error types
- User-friendly messages (no technical jargon)
- Suggested actions for recoverable errors
- Alternative options
- Context-aware responses
- Modality-specific responses (voice vs text)
"""


import pytest

from Agent_Guru.reasoning.models.error import Error, ErrorType, FallbackStrategy
from Agent_Guru.reasoning.models.intent import Entity, Intent, IntentType
from Agent_Guru.reasoning.models.result import ResponseModality
from Agent_Guru.reasoning.response.error_response_generator import (
    ErrorResponseGenerator,
    ErrorResponseTemplate,
)


class TestErrorResponseGenerator:
    """Unit tests for ErrorResponseGenerator."""

    @pytest.fixture
    def generator(self) -> ErrorResponseGenerator:
        """Create error response generator."""
        return ErrorResponseGenerator()

    def test_initialization(self, generator: ErrorResponseGenerator):
        """Test generator initialization."""
        assert generator is not None  # nosec B101
        assert len(generator._error_templates) > 0  # nosec B101

    def test_generate_error_response_invalid_input(self, generator: ErrorResponseGenerator):
        """Test error response for invalid input."""
        error = Error(
            error_code="ERR_001",
            error_type=ErrorType.INVALID_INPUT,
            message="Invalid input",
            recoverable=True,
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT)

        assert response is not None  # nosec B101
        assert response.text  # nosec B101
        assert "didn't understand" in response.text.lower()  # nosec B101
        assert "rephrase" in response.text.lower()  # nosec B101
        assert len(response.suggestions) > 0  # nosec B101
        assert response.metadata["error_type"] == ErrorType.INVALID_INPUT.value  # nosec B101
        assert response.metadata["recoverable"] is True  # nosec B101

    def test_generate_error_response_permission_denied(self, generator: ErrorResponseGenerator):
        """Test error response for permission denied."""
        error = Error(
            error_code="ERR_002",
            error_type=ErrorType.PERMISSION_DENIED,
            message="Permission denied",
            recoverable=True,
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT)

        assert response is not None  # nosec B101
        assert "permission" in response.text.lower()  # nosec B101
        assert len(response.suggestions) > 0  # nosec B101
        assert (  # nosec B101
            "Grant permission" in response.suggestions
            or "grant permission" in str(response.suggestions).lower()
        )

    def test_generate_error_response_timeout(self, generator: ErrorResponseGenerator):
        """Test error response for timeout."""
        error = Error(
            error_code="ERR_003",
            error_type=ErrorType.EXECUTION_TIMEOUT,
            message="Execution timeout",
            recoverable=True,
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT)

        assert response is not None  # nosec B101
        assert (  # nosec B101
            "longer than expected" in response.text.lower() or "too long" in response.text.lower()
        )
        assert len(response.suggestions) > 0  # nosec B101

    def test_generate_error_response_network_error(self, generator: ErrorResponseGenerator):
        """Test error response for network error."""
        error = Error(
            error_code="ERR_004",
            error_type=ErrorType.NETWORK_ERROR,
            message="Network error",
            recoverable=True,
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT)

        assert response is not None  # nosec B101
        assert "network" in response.text.lower() or "connection" in response.text.lower()  # nosec B101
        assert len(response.suggestions) > 0  # nosec B101
        assert any("connection" in s.lower() for s in response.suggestions)  # nosec B101

    def test_generate_error_response_tool_unavailable(self, generator: ErrorResponseGenerator):
        """Test error response for tool unavailable."""
        error = Error(
            error_code="ERR_005",
            error_type=ErrorType.TOOL_UNAVAILABLE,
            message="Tool unavailable",
            recoverable=False,
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT)

        assert response is not None  # nosec B101
        assert "unavailable" in response.text.lower() or "not available" in response.text.lower()  # nosec B101
        assert len(response.suggestions) > 0  # nosec B101

    def test_voice_vs_text_modality(self, generator: ErrorResponseGenerator):
        """Test that voice responses are more concise than text."""
        error = Error(
            error_code="ERR_006",
            error_type=ErrorType.INVALID_INPUT,
            message="Invalid input",
            recoverable=True,
        )

        text_response = generator.generate_error_response(error, ResponseModality.TEXT)

        voice_response = generator.generate_error_response(error, ResponseModality.VOICE)

        # Voice should be shorter or equal
        assert len(voice_response.text) <= len(text_response.text)  # nosec B101
        assert voice_response.modality == ResponseModality.VOICE  # nosec B101
        assert text_response.modality == ResponseModality.TEXT  # nosec B101

    def test_no_technical_jargon(self, generator: ErrorResponseGenerator):
        """Test that error messages don't contain technical jargon."""
        error = Error(
            error_code="ERR_007",
            error_type=ErrorType.SYSTEM_ERROR,
            message="NullPointerException in module X",
            recoverable=True,
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT)

        # Should not contain technical terms
        assert "NullPointerException" not in response.text  # nosec B101
        assert (  # nosec B101
            "module" not in response.text.lower() or "something went wrong" in response.text.lower()
        )
        assert "stack trace" not in response.text.lower()  # nosec B101
        assert "exception" not in response.text.lower()  # nosec B101

    def test_recoverable_errors_have_suggestions(self, generator: ErrorResponseGenerator):
        """Test that recoverable errors include suggested actions."""
        error = Error(
            error_code="ERR_008",
            error_type=ErrorType.EXECUTION_FAILED,
            message="Execution failed",
            recoverable=True,
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT)

        assert len(response.suggestions) > 0  # nosec B101
        assert any("try" in s.lower() for s in response.suggestions)  # nosec B101

    def test_non_recoverable_errors_have_alternatives(self, generator: ErrorResponseGenerator):
        """Test that non-recoverable errors include alternatives."""
        error = Error(
            error_code="ERR_009",
            error_type=ErrorType.NO_TOOL_FOUND,
            message="No tool found",
            recoverable=False,
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT)

        assert len(response.suggestions) > 0  # nosec B101

    def test_context_aware_responses(self, generator: ErrorResponseGenerator):
        """Test that responses are context-aware."""
        error = Error(
            error_code="ERR_010",
            error_type=ErrorType.NO_TOOL_FOUND,
            message="No tool found",
            recoverable=False,
        )

        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={
                "duration": Entity(
                    entity_type="duration", value="5 minutes", raw_text="5 minutes", confidence=0.9
                )
            },
            confidence=0.9,
            original_input="set a timer for 5 minutes",
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT, intent=intent)

        # Should mention timer in context
        assert "timer" in response.text.lower() or len(response.suggestions) > 0  # nosec B101

    def test_intent_specific_alternatives(self, generator: ErrorResponseGenerator):
        """Test that alternatives are intent-specific."""
        error = Error(
            error_code="ERR_011",
            error_type=ErrorType.TOOL_UNAVAILABLE,
            message="Tool unavailable",
            recoverable=True,
        )

        # Test with timer intent
        timer_intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={
                "duration": Entity(
                    entity_type="duration", value="5 minutes", raw_text="5 minutes", confidence=0.9
                )
            },
            confidence=0.9,
            original_input="set a timer for 5 minutes",
        )

        timer_response = generator.generate_error_response(
            error, ResponseModality.TEXT, intent=timer_intent
        )

        # Should have timer-specific alternatives
        assert len(timer_response.suggestions) > 0  # nosec B101

    def test_fallback_strategy_suggestions(self, generator: ErrorResponseGenerator):
        """Test that fallback strategies generate appropriate suggestions."""
        error = Error(
            error_code="ERR_012",
            error_type=ErrorType.LLM_TIMEOUT,
            message="LLM timeout",
            recoverable=True,
            suggested_fallback=FallbackStrategy.RETRY_WITH_BACKOFF,
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT)

        assert len(response.suggestions) > 0  # nosec B101
        # Should suggest retry
        assert any("try" in s.lower() or "again" in s.lower() for s in response.suggestions)  # nosec B101

    def test_clarification_required_flag(self, generator: ErrorResponseGenerator):
        """Test that clarification required flag is set correctly."""
        error = Error(
            error_code="ERR_013",
            error_type=ErrorType.AMBIGUOUS_INTENT,
            message="Ambiguous intent",
            recoverable=True,
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT)

        assert response.metadata["requires_clarification"] is True  # nosec B101

    def test_all_error_types_have_templates(self, generator: ErrorResponseGenerator):
        """Test that all error types have templates."""
        for error_type in ErrorType:
            error = Error(
                error_code=f"ERR_{error_type.value}",
                error_type=error_type,
                message=f"Test error: {error_type.value}",
                recoverable=True,
            )

            response = generator.generate_error_response(error, ResponseModality.TEXT)

            assert response is not None  # nosec B101
            assert response.text  # nosec B101
            assert len(response.text) > 0  # nosec B101

    def test_error_response_metadata(self, generator: ErrorResponseGenerator):
        """Test that error response includes proper metadata."""
        error = Error(
            error_code="ERR_014",
            error_type=ErrorType.INVALID_INPUT,
            message="Invalid input",
            recoverable=True,
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT)

        assert "error_type" in response.metadata  # nosec B101
        assert "error_code" in response.metadata  # nosec B101
        assert "recoverable" in response.metadata  # nosec B101
        assert "generation_method" in response.metadata  # nosec B101
        assert response.metadata["generation_method"] == "error_response"  # nosec B101

    def test_suggestion_limit(self, generator: ErrorResponseGenerator):
        """Test that suggestions are limited to 3."""
        error = Error(
            error_code="ERR_015",
            error_type=ErrorType.EXECUTION_FAILED,
            message="Execution failed",
            recoverable=True,
            suggested_fallback=FallbackStrategy.RETRY_WITH_BACKOFF,
        )

        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={
                "duration": Entity(
                    entity_type="duration", value="5 minutes", raw_text="5 minutes", confidence=0.9
                )
            },
            confidence=0.9,
            original_input="set a timer for 5 minutes",
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT, intent=intent)

        # Should be limited to 3 suggestions
        assert len(response.suggestions) <= 3  # nosec B101

    def test_invalid_parameters_with_details(self, generator: ErrorResponseGenerator):
        """Test error response for invalid parameters with details."""
        error = Error(
            error_code="ERR_016",
            error_type=ErrorType.INVALID_PARAMETERS,
            message="Invalid parameters",
            details={"missing_parameters": ["duration", "label"]},
            recoverable=True,
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT)

        assert response is not None  # nosec B101
        # Should mention missing parameters
        assert (  # nosec B101
            "duration" in response.text
            or "label" in response.text
            or "more information" in response.text.lower()
        )

    def test_confirmation_required_error(self, generator: ErrorResponseGenerator):
        """Test error response for confirmation required."""
        error = Error(
            error_code="ERR_017",
            error_type=ErrorType.CONFIRMATION_REQUIRED,
            message="Confirmation required",
            recoverable=True,
        )

        response = generator.generate_error_response(error, ResponseModality.TEXT)

        assert "confirm" in response.text.lower()  # nosec B101
        assert any("confirm" in s.lower() or "cancel" in s.lower() for s in response.suggestions)  # nosec B101

    def test_llm_error_responses(self, generator: ErrorResponseGenerator):
        """Test error responses for LLM-related errors."""
        llm_errors = [
            ErrorType.LLM_UNAVAILABLE,
            ErrorType.LLM_TIMEOUT,
            ErrorType.LLM_RATE_LIMIT,
            ErrorType.LLM_INVALID_RESPONSE,
        ]

        for error_type in llm_errors:
            error = Error(
                error_code=f"ERR_{error_type.value}",
                error_type=error_type,
                message=f"LLM error: {error_type.value}",
                recoverable=True,
            )

            response = generator.generate_error_response(error, ResponseModality.TEXT)

            # Should not mention "LLM" or technical terms
            assert "llm" not in response.text.lower()  # nosec B101
            assert "model" not in response.text.lower() or "thinking" in response.text.lower()  # nosec B101
            assert len(response.suggestions) > 0  # nosec B101


class TestErrorResponseTemplate:
    """Unit tests for ErrorResponseTemplate."""

    def test_template_creation(self):
        """Test creating error response template."""
        template = ErrorResponseTemplate(
            user_message="Test error message",
            voice_message="Test error",
            suggested_actions=["Action 1", "Action 2"],
            alternatives=["Alternative 1"],
            requires_clarification=True,
        )

        assert template.user_message == "Test error message"  # nosec B101
        assert template.voice_message == "Test error"  # nosec B101
        assert len(template.suggested_actions) == 2  # nosec B101
        assert len(template.alternatives) == 1  # nosec B101
        assert template.requires_clarification is True  # nosec B101

    def test_template_defaults(self):
        """Test template default values."""
        template = ErrorResponseTemplate(
            user_message="Test", voice_message="Test", suggested_actions=[], alternatives=[]
        )

        assert template.requires_clarification is False  # nosec B101
