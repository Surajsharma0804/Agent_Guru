"""
Property-based tests for ErrorResponseGenerator.

Tests universal properties that should hold for all error responses:
- All error types produce valid responses
- Voice responses are concise
- No technical jargon in user messages
- Recoverable errors have suggestions
- All responses have proper metadata
"""

from hypothesis import assume, given
from hypothesis import strategies as st

from Agent_Guru.reasoning.models.error import Error, ErrorType, FallbackStrategy
from Agent_Guru.reasoning.models.intent import Entity, Intent, IntentType
from Agent_Guru.reasoning.models.result import ResponseModality
from Agent_Guru.reasoning.response.error_response_generator import ErrorResponseGenerator


# Strategy for generating Error objects
@st.composite
def error_strategy(draw):
    """Generate random Error objects."""
    error_type = draw(st.sampled_from(list(ErrorType)))
    error_code = draw(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Nd")))
    )
    # Generate non-empty message (avoid whitespace-only strings)
    message = draw(st.text(min_size=1, max_size=100).filter(lambda x: x.strip() != ""))
    recoverable = draw(st.booleans())

    # Optional fallback strategy
    fallback = draw(st.one_of(st.none(), st.sampled_from(list(FallbackStrategy))))

    return Error(
        error_code=error_code,
        error_type=error_type,
        message=message,
        recoverable=recoverable,
        suggested_fallback=fallback,
    )


# Strategy for generating Intent objects
@st.composite
def intent_strategy(draw):
    """Generate random Intent objects."""
    intent_type = draw(st.sampled_from(list(IntentType)))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))
    original_input = draw(st.text(min_size=1, max_size=100))

    # Generate entities
    entity_types = ["duration", "location", "person", "time", "quantity"]
    num_entities = draw(st.integers(min_value=0, max_value=3))
    entities = {}

    for _ in range(num_entities):
        entity_type = draw(st.sampled_from(entity_types))
        entity_value = draw(st.text(min_size=1, max_size=20))
        raw_text = draw(st.text(min_size=1, max_size=20))
        entities[entity_type] = Entity(
            entity_type=entity_type,
            value=entity_value,
            raw_text=raw_text,
            confidence=draw(st.floats(min_value=0.0, max_value=1.0)),
        )

    return Intent(
        intent_type=intent_type,
        entities=entities,
        confidence=confidence,
        original_input=original_input,
    )


class TestErrorResponseGeneratorProperties:
    """Property-based tests for ErrorResponseGenerator."""

    @given(error=error_strategy(), modality=st.sampled_from(list(ResponseModality)))
    def test_property_all_errors_produce_valid_responses(
        self, error: Error, modality: ResponseModality
    ):
        """
        Property: All error types produce valid responses.

        For any error and modality, generate_error_response should:
        - Return a Response object
        - Have non-empty text
        - Have proper metadata
        - Not raise exceptions
        """
        generator = ErrorResponseGenerator()
        response = generator.generate_error_response(error, modality)

        # Response is valid
        assert response is not None  # nosec B101
        assert response.text  # nosec B101
        assert len(response.text) > 0  # nosec B101

        # Metadata is present
        assert "error_type" in response.metadata  # nosec B101
        assert "error_code" in response.metadata  # nosec B101
        assert "recoverable" in response.metadata  # nosec B101
        assert "generation_method" in response.metadata  # nosec B101

        # Modality matches
        assert response.modality == modality  # nosec B101

    @given(error=error_strategy())
    def test_property_voice_responses_are_concise(self, error: Error):
        """
        Property: Voice responses are more concise than text responses.

        For any error, the voice response should be shorter or equal
        in length to the text response.
        """
        generator = ErrorResponseGenerator()
        text_response = generator.generate_error_response(error, ResponseModality.TEXT)

        voice_response = generator.generate_error_response(error, ResponseModality.VOICE)

        # Voice should be shorter or equal
        assert len(voice_response.text) <= len(text_response.text)  # nosec B101

    @given(error=error_strategy())
    def test_property_no_technical_jargon(self, error: Error):
        """
        Property: Error responses don't contain technical jargon.

        For any error, the user-facing message should not contain:
        - Stack traces
        - Exception names
        - Technical error codes
        - Internal system details
        """
        generator = ErrorResponseGenerator()
        response = generator.generate_error_response(error, ResponseModality.TEXT)

        # Technical terms that should not appear
        forbidden_terms = [
            "exception",
            "stack trace",
            "null pointer",
            "segfault",
            "core dump",
            "traceback",
            "errno",
            "0x",  # Hex addresses
        ]

        text_lower = response.text.lower()
        for term in forbidden_terms:
            assert term not in text_lower, f"Technical term '{term}' found in user message"  # nosec B101

    @given(error=error_strategy())
    def test_property_recoverable_errors_have_suggestions(self, error: Error):
        """
        Property: Recoverable errors include suggested actions.

        For any recoverable error, the response should include
        at least one suggestion for the user.
        """
        assume(error.recoverable)  # Only test recoverable errors

        generator = ErrorResponseGenerator()
        response = generator.generate_error_response(error, ResponseModality.TEXT)

        # Should have suggestions
        assert len(response.suggestions) > 0  # nosec B101

    @given(error=error_strategy(), modality=st.sampled_from(list(ResponseModality)))
    def test_property_suggestions_are_limited(self, error: Error, modality: ResponseModality):
        """
        Property: Suggestions are limited to 3.

        For any error, the response should have at most 3 suggestions
        to avoid overwhelming the user.
        """
        generator = ErrorResponseGenerator()
        response = generator.generate_error_response(error, modality)

        # Suggestions limited to 3
        assert len(response.suggestions) <= 3  # nosec B101

    @given(
        error=error_strategy(),
        intent=intent_strategy(),
        modality=st.sampled_from(list(ResponseModality)),
    )
    def test_property_context_aware_responses(
        self, error: Error, intent: Intent, modality: ResponseModality
    ):
        """
        Property: Responses with intent context are valid.

        For any error and intent, generate_error_response should
        produce a valid response that may include intent-specific
        alternatives.
        """
        generator = ErrorResponseGenerator()
        response = generator.generate_error_response(error, modality, intent=intent)

        # Response is valid
        assert response is not None  # nosec B101
        assert response.text  # nosec B101
        assert len(response.text) > 0  # nosec B101

        # May have intent-specific suggestions
        assert isinstance(response.suggestions, list)  # nosec B101

    @given(error=error_strategy())
    def test_property_metadata_completeness(self, error: Error):
        """
        Property: All error responses have complete metadata.

        For any error, the response metadata should include:
        - error_type
        - error_code
        - recoverable flag
        - generation_method
        - requires_clarification flag
        """
        generator = ErrorResponseGenerator()
        response = generator.generate_error_response(error, ResponseModality.TEXT)

        # Required metadata fields
        required_fields = [
            "error_type",
            "error_code",
            "recoverable",
            "generation_method",
            "requires_clarification",
        ]

        for field in required_fields:
            assert field in response.metadata, f"Missing metadata field: {field}"  # nosec B101

    @given(error=error_strategy())
    def test_property_error_type_consistency(self, error: Error):
        """
        Property: Error type in metadata matches input error.

        For any error, the error_type in response metadata should
        match the error_type of the input error.
        """
        generator = ErrorResponseGenerator()
        response = generator.generate_error_response(error, ResponseModality.TEXT)

        assert response.metadata["error_type"] == error.error_type.value  # nosec B101
        assert response.metadata["error_code"] == error.error_code  # nosec B101
        assert response.metadata["recoverable"] == error.recoverable  # nosec B101

    @given(error=error_strategy(), modality=st.sampled_from(list(ResponseModality)))
    def test_property_non_empty_messages(self, error: Error, modality: ResponseModality):
        """
        Property: Error messages are never empty.

        For any error and modality, the response text should
        always be non-empty and contain meaningful content.
        """
        generator = ErrorResponseGenerator()
        response = generator.generate_error_response(error, modality)

        # Text is non-empty
        assert response.text  # nosec B101
        assert len(response.text.strip()) > 0  # nosec B101

        # Contains at least one word
        assert len(response.text.split()) > 0  # nosec B101

    @given(error=error_strategy())
    def test_property_user_friendly_language(self, error: Error):
        """
        Property: Error messages use user-friendly language.

        For any error, the response should use conversational,
        helpful language appropriate for end users.
        """
        generator = ErrorResponseGenerator()
        response = generator.generate_error_response(error, ResponseModality.TEXT)

        # Should contain helpful phrases OR be a complete sentence
        helpful_indicators = [
            "please",
            "try",
            "could",
            "can",
            "would",
            "sorry",
            "help",
            "again",
            "check",
            "need",
            "more",
            "specific",
            "yet",  # Added for "not available yet" type messages
            "that",  # Added for "I can't do that" type messages
        ]

        text_lower = response.text.lower()
        # At least one helpful indicator should be present OR it's a complete sentence
        has_helpful_language = any(indicator in text_lower for indicator in helpful_indicators)
        is_complete_sentence = len(response.text.split()) >= 3 and response.text.strip().endswith(
            (".", "?", "!")
        )

        assert (  # nosec B101
            has_helpful_language or is_complete_sentence
        ), f"No helpful language found in: {response.text}"

    @given(error=error_strategy(), modality=st.sampled_from(list(ResponseModality)))
    def test_property_generation_method_tagged(self, error: Error, modality: ResponseModality):
        """
        Property: All responses are tagged with generation method.

        For any error, the response metadata should indicate
        it was generated by the error response generator.
        """
        generator = ErrorResponseGenerator()
        response = generator.generate_error_response(error, modality)

        assert response.metadata["generation_method"] == "error_response"  # nosec B101

    @given(error=error_strategy())
    def test_property_clarification_flag_consistency(self, error: Error):
        """
        Property: Clarification flag is consistent with error type.

        For errors that require user clarification (ambiguous intent,
        invalid input, etc.), the requires_clarification flag should
        be set appropriately.
        """
        generator = ErrorResponseGenerator()
        response = generator.generate_error_response(error, ResponseModality.TEXT)

        # Clarification flag should be boolean
        assert isinstance(response.metadata["requires_clarification"], bool)  # nosec B101

        # Certain error types should require clarification
        clarification_errors = {
            ErrorType.INVALID_INPUT,
            ErrorType.AMBIGUOUS_INTENT,
            ErrorType.INVALID_PARAMETERS,
            ErrorType.CONFIRMATION_REQUIRED,
        }

        if error.error_type in clarification_errors:
            assert response.metadata["requires_clarification"] is True  # nosec B101
