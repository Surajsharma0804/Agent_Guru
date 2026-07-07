"""
Tests for tool base classes.
"""

import pytest
from typing import Any, Dict

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolMetadata,
    ToolSensitivity,
)


class TestToolParameter:
    """Tests for ToolParameter model."""

    def test_required_parameter(self) -> None:
        """Test creating a required parameter."""
        param = ToolParameter(
            name="duration",
            type=ToolParameterType.INTEGER,
            description="Duration in seconds",
            required=True,
        )

        assert param.name == "duration"  # nosec B101
        assert param.type == ToolParameterType.INTEGER  # nosec B101
        assert param.required is True  # nosec B101
        assert param.default is None  # nosec B101

    def test_optional_parameter_with_default(self) -> None:
        """Test creating an optional parameter with default value."""
        param = ToolParameter(
            name="repeat",
            type=ToolParameterType.BOOLEAN,
            description="Whether to repeat",
            required=False,
            default=False,
        )

        assert param.required is False  # nosec B101
        assert param.default is False  # nosec B101

    def test_required_parameter_cannot_have_default(self) -> None:
        """Test that required parameters cannot have default values."""
        with pytest.raises(ValueError, match="Default value can only be set"):
            ToolParameter(
                name="duration",
                type=ToolParameterType.INTEGER,
                description="Duration",
                required=True,
                default=60,
            )


class TestToolMetadata:
    """Tests for ToolMetadata model."""

    def test_minimal_metadata(self) -> None:
        """Test creating minimal tool metadata."""
        metadata = ToolMetadata(
            tool_id="test.tool", name="Test Tool", description="A test tool"
        )

        assert metadata.tool_id == "test.tool"  # nosec B101
        assert metadata.name == "Test Tool"  # nosec B101
        assert metadata.sensitivity == ToolSensitivity.SAFE  # nosec B101
        assert metadata.estimated_latency_ms == 1000  # nosec B101
        assert metadata.parameters == []  # nosec B101
        assert metadata.capabilities == []  # nosec B101

    def test_full_metadata(self) -> None:
        """Test creating full tool metadata."""
        params = [
            ToolParameter(
                name="input", type=ToolParameterType.STRING, description="Input text", required=True
            )
        ]

        metadata = ToolMetadata(
            tool_id="test.tool",
            name="Test Tool",
            description="A test tool",
            parameters=params,
            sensitivity=ToolSensitivity.SENSITIVE,
            estimated_latency_ms=500,
            capabilities=["text_processing"],
            examples=["Process text input"],
        )

        assert len(metadata.parameters) == 1  # nosec B101
        assert metadata.sensitivity == ToolSensitivity.SENSITIVE  # nosec B101
        assert metadata.estimated_latency_ms == 500  # nosec B101
        assert "text_processing" in metadata.capabilities  # nosec B101

    def test_negative_latency_rejected(self) -> None:
        """Test that negative latency is rejected."""
        with pytest.raises(ValueError, match="Estimated latency must be positive"):
            ToolMetadata(
                tool_id="test.tool",
                name="Test Tool",
                description="A test tool",
                estimated_latency_ms=-100,
            )


class TestTool:
    """Tests for Tool base class."""

    def test_tool_requires_metadata(self) -> None:
        """Test that tool requires metadata to be set."""

        class TestTool(Tool):
            async def execute(self, **kwargs: Any) -> Dict[str, Any]:
                return {"success": True}

        tool = TestTool()
        with pytest.raises(ValueError, match="Tool metadata not set"):
            _ = tool.metadata

    def test_validate_parameters_success(self) -> None:
        """Test successful parameter validation."""

        class TestTool(Tool):
            async def execute(self, **kwargs: Any) -> Dict[str, Any]:
                return {"success": True}

        tool = TestTool()
        tool._metadata = ToolMetadata(
            tool_id="test.tool",
            name="Test",
            description="Test",
            parameters=[
                ToolParameter(
                    name="text", type=ToolParameterType.STRING, description="Text", required=True
                ),
                ToolParameter(
                    name="count",
                    type=ToolParameterType.INTEGER,
                    description="Count",
                    required=False,
                    default=1,
                ),
            ],
        )

        # Should not raise
        tool.validate_parameters(text="hello")
        tool.validate_parameters(text="hello", count=5)

    def test_validate_parameters_missing_required(self) -> None:
        """Test validation fails for missing required parameters."""

        class TestTool(Tool):
            async def execute(self, **kwargs: Any) -> Dict[str, Any]:
                return {"success": True}

        tool = TestTool()
        tool._metadata = ToolMetadata(
            tool_id="test.tool",
            name="Test",
            description="Test",
            parameters=[
                ToolParameter(
                    name="text", type=ToolParameterType.STRING, description="Text", required=True
                )
            ],
        )

        with pytest.raises(ValueError, match="Missing required parameters: text"):
            tool.validate_parameters()

    def test_validate_parameters_unknown_parameter(self) -> None:
        """Test validation fails for unknown parameters."""

        class TestTool(Tool):
            async def execute(self, **kwargs: Any) -> Dict[str, Any]:
                return {"success": True}

        tool = TestTool()
        tool._metadata = ToolMetadata(
            tool_id="test.tool", name="Test", description="Test", parameters=[]
        )

        with pytest.raises(ValueError, match="Unknown parameter: unknown"):
            tool.validate_parameters(unknown="value")

    def test_validate_parameters_wrong_type(self) -> None:
        """Test validation fails for wrong parameter types."""

        class TestTool(Tool):
            async def execute(self, **kwargs: Any) -> Dict[str, Any]:
                return {"success": True}

        tool = TestTool()
        tool._metadata = ToolMetadata(
            tool_id="test.tool",
            name="Test",
            description="Test",
            parameters=[
                ToolParameter(
                    name="count",
                    type=ToolParameterType.INTEGER,
                    description="Count",
                    required=True,
                )
            ],
        )

        with pytest.raises(ValueError, match="has invalid type"):
            tool.validate_parameters(count="not_an_integer")

    def test_validate_type_string(self) -> None:
        """Test type validation for strings."""

        class TestTool(Tool):
            async def execute(self, **kwargs: Any) -> Dict[str, Any]:
                return {"success": True}

        tool = TestTool()

        assert tool._validate_type("hello", ToolParameterType.STRING) is True  # nosec B101
        assert tool._validate_type(123, ToolParameterType.STRING) is False  # nosec B101

    def test_validate_type_integer(self) -> None:
        """Test type validation for integers."""

        class TestTool(Tool):
            async def execute(self, **kwargs: Any) -> Dict[str, Any]:
                return {"success": True}

        tool = TestTool()

        assert tool._validate_type(123, ToolParameterType.INTEGER) is True  # nosec B101
        assert tool._validate_type(123.45, ToolParameterType.INTEGER) is False  # nosec B101
        assert tool._validate_type(True, ToolParameterType.INTEGER) is False  # bool is not int  # nosec B101

    def test_validate_type_float(self) -> None:
        """Test type validation for floats."""

        class TestTool(Tool):
            async def execute(self, **kwargs: Any) -> Dict[str, Any]:
                return {"success": True}

        tool = TestTool()

        assert tool._validate_type(123.45, ToolParameterType.FLOAT) is True  # nosec B101
        assert tool._validate_type(123, ToolParameterType.FLOAT) is True  # int is acceptable  # nosec B101
        assert tool._validate_type(True, ToolParameterType.FLOAT) is False  # nosec B101

    def test_validate_type_boolean(self) -> None:
        """Test type validation for booleans."""

        class TestTool(Tool):
            async def execute(self, **kwargs: Any) -> Dict[str, Any]:
                return {"success": True}

        tool = TestTool()

        assert tool._validate_type(True, ToolParameterType.BOOLEAN) is True  # nosec B101
        assert tool._validate_type(False, ToolParameterType.BOOLEAN) is True  # nosec B101
        assert tool._validate_type(1, ToolParameterType.BOOLEAN) is False  # nosec B101

    def test_validate_type_array(self) -> None:
        """Test type validation for arrays."""

        class TestTool(Tool):
            async def execute(self, **kwargs: Any) -> Dict[str, Any]:
                return {"success": True}

        tool = TestTool()

        assert tool._validate_type([1, 2, 3], ToolParameterType.ARRAY) is True  # nosec B101
        assert tool._validate_type([], ToolParameterType.ARRAY) is True  # nosec B101
        assert tool._validate_type((1, 2, 3), ToolParameterType.ARRAY) is False  # nosec B101

    def test_validate_type_object(self) -> None:
        """Test type validation for objects."""

        class TestTool(Tool):
            async def execute(self, **kwargs: Any) -> Dict[str, Any]:
                return {"success": True}

        tool = TestTool()

        assert tool._validate_type({"key": "value"}, ToolParameterType.OBJECT) is True  # nosec B101
        assert tool._validate_type({}, ToolParameterType.OBJECT) is True  # nosec B101
        assert tool._validate_type([1, 2], ToolParameterType.OBJECT) is False  # nosec B101
