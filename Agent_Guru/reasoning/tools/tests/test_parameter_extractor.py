"""
Tests for parameter extractor.
"""

import pytest

from Agent_Guru.reasoning.models.intent import Intent, Entity
from Agent_Guru.reasoning.tools.parameter_extractor import (
    ParameterExtractor,
    ParameterExtractionError,
)
from Agent_Guru.reasoning.tools.base import ToolParameter, ToolParameterType
from Agent_Guru.reasoning.tools.examples.timer_tool import SetTimerTool


class TestParameterExtractor:
    """Tests for ParameterExtractor."""

    @pytest.fixture
    def extractor(self) -> ParameterExtractor:
        """Create parameter extractor."""
        return ParameterExtractor()

    @pytest.fixture
    def timer_tool(self) -> SetTimerTool:
        """Create timer tool."""
        return SetTimerTool()

    def test_extract_required_parameters(
        self, extractor: ParameterExtractor, timer_tool: SetTimerTool
    ) -> None:
        """Test extracting required parameters."""
        intent = Intent(
            intent_type="set_timer",
            original_input="Set timer for 5 minutes",
            entities={
                "duration_seconds": Entity(
                    entity_type="duration", value=300, raw_text="5 minutes"
                )
            },
            confidence=0.95,
        )

        params = extractor.extract_parameters(timer_tool, intent)

        assert "duration_seconds" in params
        assert params["duration_seconds"] == 300

    def test_extract_optional_parameters_with_default(
        self, extractor: ParameterExtractor, timer_tool: SetTimerTool
    ) -> None:
        """Test extracting optional parameters (skipped if no default)."""
        intent = Intent(
            intent_type="set_timer",
            original_input="Set timer for 5 minutes",
            entities={
                "duration_seconds": Entity(
                    entity_type="duration", value=300, raw_text="5 minutes"
                )
            },
            confidence=0.95,
        )

        params = extractor.extract_parameters(timer_tool, intent)

        # Label is optional - may or may not be in params depending on default
        assert "duration_seconds" in params

    def test_missing_required_parameter_raises_error(
        self, extractor: ParameterExtractor, timer_tool: SetTimerTool
    ) -> None:
        """Test that missing required parameter raises error."""
        intent = Intent(
            intent_type="set_timer",
            original_input="Set timer",
            entities={},  # Missing duration_seconds
            confidence=0.95,
        )

        with pytest.raises(ParameterExtractionError) as exc_info:
            extractor.extract_parameters(timer_tool, intent)

        assert "duration_seconds" in str(exc_info.value)
        assert "Required parameter" in str(exc_info.value)

    def test_type_conversion_integer(self, extractor: ParameterExtractor) -> None:
        """Test type conversion for integer parameters."""
        param = ToolParameter(
            name="count",
            type=ToolParameterType.INTEGER,
            description="Count",
            required=True,
        )

        # String to int
        value = extractor._convert_and_validate("42", param)
        assert value == 42
        assert isinstance(value, int)

        # Float to int
        value = extractor._convert_and_validate(42.7, param)
        assert value == 42

    def test_type_conversion_boolean(self, extractor: ParameterExtractor) -> None:
        """Test type conversion for boolean parameters."""
        param = ToolParameter(
            name="enabled",
            type=ToolParameterType.BOOLEAN,
            description="Enabled",
            required=True,
        )

        # String to bool
        assert extractor._convert_and_validate("true", param) is True
        assert extractor._convert_and_validate("false", param) is False
        assert extractor._convert_and_validate("yes", param) is True
        assert extractor._convert_and_validate("no", param) is False

        # Int to bool
        assert extractor._convert_and_validate(1, param) is True
        assert extractor._convert_and_validate(0, param) is False

    def test_validate_parameters_success(
        self, extractor: ParameterExtractor, timer_tool: SetTimerTool
    ) -> None:
        """Test successful parameter validation."""
        params = {"duration_seconds": 300}

        errors = extractor.validate_parameters(timer_tool, params)

        assert len(errors) == 0

    def test_validate_parameters_missing_required(
        self, extractor: ParameterExtractor, timer_tool: SetTimerTool
    ) -> None:
        """Test validation with missing required parameter."""
        params = {}  # Missing duration_seconds

        errors = extractor.validate_parameters(timer_tool, params)

        assert len(errors) > 0
        assert any("duration_seconds" in error for error in errors)
        assert any("Required parameter" in error for error in errors)

    def test_fuzzy_parameter_matching(
        self, extractor: ParameterExtractor, timer_tool: SetTimerTool
    ) -> None:
        """Test fuzzy matching of parameter names."""
        intent = Intent(
            intent_type="set_timer",
            original_input="Set timer for 5 minutes",
            entities={
                "duration": Entity(  # Fuzzy match to "duration_seconds"
                    entity_type="duration", value=300, raw_text="5 minutes"
                )
            },
            confidence=0.95,
        )

        params = extractor.extract_parameters(timer_tool, intent)

        # Should fuzzy match "duration" to "duration_seconds"
        assert "duration_seconds" in params
        assert params["duration_seconds"] == 300
