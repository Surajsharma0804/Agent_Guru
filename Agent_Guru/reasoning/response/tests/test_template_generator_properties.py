"""
Property-based tests for TemplateGenerator.

Tests invariants using Hypothesis for:
- Response generation always produces valid Response objects
- Latency requirements are always met (<100ms)
- Template selection is deterministic
"""

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from Agent_Guru.reasoning.models.intent import Entity, Intent, IntentType
from Agent_Guru.reasoning.models.result import ExecutionResult, Response, ResponseModality
from Agent_Guru.reasoning.response.template_generator import TemplateGenerator

# Strategies
intent_types = st.sampled_from(
    [
        IntentType.SET_TIMER,
        IntentType.QUERY_WEATHER,
        IntentType.SEND_MESSAGE,
        IntentType.PLAY_MUSIC,
        IntentType.UNKNOWN,
    ]
)

modalities = st.sampled_from([ResponseModality.VOICE, ResponseModality.TEXT, ResponseModality.BOTH])


class TestTemplateGeneratorProperties:
    """Property-based tests for TemplateGenerator."""

    @given(intent_type=intent_types, modality=modalities)
    @settings(max_examples=100)
    def test_property_success_response_always_valid(
        self, intent_type: IntentType, modality: ResponseModality
    ):
        """
        Property: For any successful execution result and intent,
        generate() always produces a valid Response object.

        Validates: Requirements 8.1
        """
        generator = TemplateGenerator()

        result = ExecutionResult(
            success=True,
            result_data={"value": "test"},
            execution_time=0.1,
            action_id="test",
            tool_id="test_tool",
            timestamp=datetime.now(tz=timezone.utc),
        )

        intent = Intent(
            intent_type=intent_type,
            entities={
                "value": Entity(entity_type="test", value="test", raw_text="test", confidence=0.95)
            },
            confidence=0.95,
            requires_reasoning=False,
            original_input="test input",
        )

        response = generator.generate(result=result, intent=intent, modality=modality)

        assert isinstance(response, Response)  # nosec B101
        assert isinstance(response.text, str)  # nosec B101
        assert len(response.text) > 0  # nosec B101
        assert response.modality == modality  # nosec B101
        assert response.metadata["generation_method"] == "template"  # nosec B101

    @given(intent_type=intent_types, modality=modalities)
    @settings(max_examples=100)
    def test_property_latency_always_under_100ms(
        self, intent_type: IntentType, modality: ResponseModality
    ):
        """
        Property: For any input, response generation completes in <100ms.

        Validates: Requirements 8.5 (latency requirement)
        """
        import time

        generator = TemplateGenerator()

        result = ExecutionResult(
            success=True,
            result_data={"value": "test"},
            execution_time=0.1,
            action_id="test",
            tool_id="test_tool",
            timestamp=datetime.now(tz=timezone.utc),
        )

        intent = Intent(
            intent_type=intent_type,
            entities={},
            confidence=0.95,
            requires_reasoning=False,
            original_input="test input",
        )

        start = time.perf_counter()
        response = generator.generate(result=result, intent=intent, modality=modality)
        latency_ms = (time.perf_counter() - start) * 1000

        assert latency_ms < 100  # nosec B101
        assert response.metadata["latency_ms"] < 100  # nosec B101

    @given(intent_type=intent_types, modality=modalities)
    @settings(max_examples=100)
    def test_property_template_selection_deterministic(
        self, intent_type: IntentType, modality: ResponseModality
    ):
        """
        Property: Same input always selects same template.

        Validates: Requirements 8.1 (deterministic behavior)
        """
        generator = TemplateGenerator()

        result = ExecutionResult(
            success=True,
            result_data={"value": "test"},
            execution_time=0.1,
            action_id="test",
            tool_id="test_tool",
            timestamp=datetime.now(tz=timezone.utc),
        )

        intent = Intent(
            intent_type=intent_type,
            entities={},
            confidence=0.95,
            requires_reasoning=False,
            original_input="test input",
        )

        response1 = generator.generate(result=result, intent=intent, modality=modality)

        response2 = generator.generate(result=result, intent=intent, modality=modality)

        assert response1.metadata["template_id"] == response2.metadata["template_id"]  # nosec B101

    @given(intent_type=intent_types, modality=modalities)
    @settings(max_examples=100)
    def test_property_suggestions_limited(
        self, intent_type: IntentType, modality: ResponseModality
    ):
        """
        Property: Suggestions are always limited to 3 or fewer.

        Validates: Requirements 8.1 (suggestions)
        """
        generator = TemplateGenerator()

        result = ExecutionResult(
            success=True,
            result_data={"value": "test"},
            execution_time=0.1,
            action_id="test",
            tool_id="test_tool",
            timestamp=datetime.now(tz=timezone.utc),
        )

        intent = Intent(
            intent_type=intent_type,
            entities={},
            confidence=0.95,
            requires_reasoning=False,
            original_input="test input",
        )

        response = generator.generate(result=result, intent=intent, modality=modality)

        assert len(response.suggestions) <= 3  # nosec B101

    @given(intent_type=intent_types, modality=modalities)
    @settings(max_examples=100)
    def test_property_metadata_always_complete(
        self, intent_type: IntentType, modality: ResponseModality
    ):
        """
        Property: Response metadata always contains required fields.

        Validates: Requirements 8.1 (metadata completeness)
        """
        generator = TemplateGenerator()

        result = ExecutionResult(
            success=True,
            result_data={"value": "test"},
            execution_time=0.1,
            action_id="test",
            tool_id="test_tool",
            timestamp=datetime.now(tz=timezone.utc),
        )

        intent = Intent(
            intent_type=intent_type,
            entities={},
            confidence=0.95,
            requires_reasoning=False,
            original_input="test input",
        )

        response = generator.generate(result=result, intent=intent, modality=modality)

        assert "template_id" in response.metadata  # nosec B101
        assert "template_type" in response.metadata  # nosec B101
        assert "generation_method" in response.metadata  # nosec B101
        assert "latency_ms" in response.metadata  # nosec B101
        assert response.metadata["generation_method"] == "template"  # nosec B101
        assert response.metadata["latency_ms"] >= 0  # nosec B101
