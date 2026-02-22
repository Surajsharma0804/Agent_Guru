"""
Simplified unit tests for TemplateGenerator focusing on core functionality.
"""


from Agent_Guru.reasoning.models.intent import Intent, IntentType
from Agent_Guru.reasoning.models.result import ExecutionResult, Response, ResponseModality
from Agent_Guru.reasoning.response.template_generator import (
    ResponseTemplate,
    TemplateGenerator,
    TemplateType,
)


class TestTemplateGeneratorCore:
    """Core functionality tests for TemplateGenerator."""

    def test_initialization(self, generator: TemplateGenerator):
        """Test generator initializes with default templates."""
        assert len(generator.list_templates()) > 0
        assert "generic_success" in generator.list_templates()
        assert "generic_error" in generator.list_templates()

    def test_generate_success_response(
        self, generator: TemplateGenerator, success_result: ExecutionResult, timer_intent: Intent
    ):
        """Test generating success response."""
        response = generator.generate(
            result=success_result, intent=timer_intent, modality=ResponseModality.TEXT
        )

        assert isinstance(response, Response)
        assert response.text
        assert "5 minutes" in response.text
        assert response.modality == ResponseModality.TEXT
        assert response.metadata["generation_method"] == "template"
        assert response.metadata["latency_ms"] < 100  # Latency requirement

    def test_generate_error_response(
        self, generator: TemplateGenerator, error_result: ExecutionResult, timer_intent: Intent
    ):
        """Test generating error response."""
        response = generator.generate(
            result=error_result, intent=timer_intent, modality=ResponseModality.TEXT
        )

        assert isinstance(response, Response)
        assert response.text
        assert "timed out" in response.text.lower() or "too long" in response.text.lower()
        assert response.metadata["generation_method"] == "template"

    def test_voice_modality_uses_concise_template(
        self, generator: TemplateGenerator, success_result: ExecutionResult, timer_intent: Intent
    ):
        """Test voice modality uses more concise templates."""
        text_response = generator.generate(
            result=success_result, intent=timer_intent, modality=ResponseModality.TEXT
        )

        voice_response = generator.generate(
            result=success_result, intent=timer_intent, modality=ResponseModality.VOICE
        )

        # Voice responses should be shorter or equal
        assert len(voice_response.text) <= len(text_response.text)

    def test_personalization_concise(
        self, generator: TemplateGenerator, success_result: ExecutionResult, timer_intent: Intent
    ):
        """Test concise personalization removes filler words."""
        response = generator.generate(
            result=success_result,
            intent=timer_intent,
            modality=ResponseModality.TEXT,
            user_preferences={"verbosity": "concise"},
        )

        # Concise responses should not have filler phrases
        assert "I've successfully" not in response.text
        assert "for you" not in response.text

    def test_suggestions_included(
        self, generator: TemplateGenerator, success_result: ExecutionResult, timer_intent: Intent
    ):
        """Test suggestions are included in response."""
        response = generator.generate(
            result=success_result, intent=timer_intent, modality=ResponseModality.TEXT
        )

        assert response.suggestions
        assert len(response.suggestions) <= 3  # Max 3 suggestions

    def test_template_selection_intent_specific(
        self, generator: TemplateGenerator, success_result: ExecutionResult, timer_intent: Intent
    ):
        """Test intent-specific template is selected."""
        response = generator.generate(
            result=success_result, intent=timer_intent, modality=ResponseModality.TEXT
        )

        assert response.metadata["template_id"] == "set_timer_success"

    def test_template_selection_generic_fallback(
        self, generator: TemplateGenerator, success_result: ExecutionResult
    ):
        """Test generic template is used as fallback."""
        unknown_intent = Intent(
            intent_type=IntentType.UNKNOWN,
            entities={},
            confidence=0.5,
            requires_reasoning=False,
            original_input="do something",
        )

        response = generator.generate(
            result=success_result, intent=unknown_intent, modality=ResponseModality.TEXT
        )

        assert response.metadata["template_id"] == "generic_success"

    def test_add_custom_template(self, generator: TemplateGenerator):
        """Test adding custom template."""
        custom_template = ResponseTemplate(
            template_id="custom_test",
            template_type=TemplateType.SUCCESS,
            text_template="Custom response: {value}",
            voice_template="Custom: {value}",
            variables=["value"],
        )

        generator.add_template(custom_template)

        assert "custom_test" in generator.list_templates()
        assert generator.get_template("custom_test") == custom_template

    def test_get_template(self, generator: TemplateGenerator):
        """Test getting template by ID."""
        template = generator.get_template("generic_success")

        assert template is not None
        assert template.template_id == "generic_success"
        assert template.template_type == TemplateType.SUCCESS

    def test_get_nonexistent_template(self, generator: TemplateGenerator):
        """Test getting nonexistent template returns None."""
        template = generator.get_template("nonexistent_template")

        assert template is None

    def test_list_templates(self, generator: TemplateGenerator):
        """Test listing all templates."""
        templates = generator.list_templates()

        assert isinstance(templates, list)
        assert len(templates) > 0
        assert "generic_success" in templates
        assert "generic_error" in templates

    def test_latency_requirement(
        self, generator: TemplateGenerator, success_result: ExecutionResult, timer_intent: Intent
    ):
        """Test response generation meets <100ms latency requirement."""
        import time

        start = time.perf_counter()
        response = generator.generate(
            result=success_result, intent=timer_intent, modality=ResponseModality.TEXT
        )
        latency_ms = (time.perf_counter() - start) * 1000

        # Should be well under 100ms
        assert latency_ms < 100
        assert response.metadata["latency_ms"] < 100

    def test_metadata_includes_template_info(
        self, generator: TemplateGenerator, success_result: ExecutionResult, timer_intent: Intent
    ):
        """Test response metadata includes template information."""
        response = generator.generate(
            result=success_result, intent=timer_intent, modality=ResponseModality.TEXT
        )

        assert "template_id" in response.metadata
        assert "template_type" in response.metadata
        assert "generation_method" in response.metadata
        assert "latency_ms" in response.metadata
        assert response.metadata["generation_method"] == "template"

    def test_both_modality(
        self, generator: TemplateGenerator, success_result: ExecutionResult, timer_intent: Intent
    ):
        """Test BOTH modality uses text template."""
        response = generator.generate(
            result=success_result, intent=timer_intent, modality=ResponseModality.BOTH
        )

        assert response.text
        assert response.modality == ResponseModality.BOTH


class TestResponseTemplate:
    """Unit tests for ResponseTemplate dataclass."""

    def test_create_template(self):
        """Test creating response template."""
        template = ResponseTemplate(
            template_id="test",
            template_type=TemplateType.SUCCESS,
            text_template="Test {value}",
            voice_template="Test",
            variables=["value"],
        )

        assert template.template_id == "test"
        assert template.template_type == TemplateType.SUCCESS
        assert template.text_template == "Test {value}"
        assert template.voice_template == "Test"
        assert template.variables == ["value"]
        assert template.suggestions is None

    def test_template_with_suggestions(self):
        """Test template with suggestions."""
        template = ResponseTemplate(
            template_id="test",
            template_type=TemplateType.SUCCESS,
            text_template="Done",
            voice_template="Done",
            variables=[],
            suggestions=["Try again", "Cancel"],
        )

        assert template.suggestions == ["Try again", "Cancel"]


class TestTemplateType:
    """Unit tests for TemplateType enum."""

    def test_template_types(self):
        """Test all template types are defined."""
        assert TemplateType.SUCCESS == "success"
        assert TemplateType.ERROR == "error"
        assert TemplateType.CONFIRMATION == "confirmation"
        assert TemplateType.CLARIFICATION == "clarification"
        assert TemplateType.PARTIAL_SUCCESS == "partial_success"
        assert TemplateType.PROGRESS == "progress"
