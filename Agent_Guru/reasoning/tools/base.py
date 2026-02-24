"""
Base classes for tools in the Agent_Guru reasoning engine.

This module defines the abstract base class for all tools and related data structures.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ToolParameterType(str, Enum):
    """Parameter types for tool inputs."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class ToolSensitivity(str, Enum):
    """Sensitivity levels for tools."""

    SAFE = "safe"  # No confirmation needed
    SENSITIVE = "sensitive"  # Confirmation required
    DANGEROUS = "dangerous"  # Explicit confirmation with details required


class ToolParameter(BaseModel):
    """Definition of a tool parameter."""

    name: str = Field(..., description="Parameter name")
    type: ToolParameterType = Field(..., description="Parameter type")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(default=True, description="Whether parameter is required")
    default: Optional[Any] = Field(default=None, description="Default value if not required")

    @field_validator("default")
    @classmethod
    def validate_default(cls, v: Any, info: Any) -> Any:
        """Validate that default is only set for optional parameters."""
        if v is not None and info.data.get("required", True):
            raise ValueError("Default value can only be set for optional parameters")
        return v


class ToolMetadata(BaseModel):
    """Metadata about a tool."""

    tool_id: str = Field(..., description="Unique tool identifier")
    name: str = Field(..., description="Human-readable tool name")
    description: str = Field(..., description="Tool description")
    parameters: List[ToolParameter] = Field(default_factory=list, description="Tool parameters")
    sensitivity: ToolSensitivity = Field(
        default=ToolSensitivity.SAFE, description="Tool sensitivity level"
    )
    estimated_latency_ms: int = Field(
        default=1000, description="Estimated execution latency in milliseconds"
    )
    capabilities: List[str] = Field(
        default_factory=list, description="Tool capabilities for matching"
    )
    examples: List[str] = Field(default_factory=list, description="Example usage scenarios")

    @field_validator("estimated_latency_ms")
    @classmethod
    def validate_latency(cls, v: int) -> int:
        """Validate latency is positive."""
        if v <= 0:
            raise ValueError("Estimated latency must be positive")
        return v


class Tool(ABC):
    """Abstract base class for all tools.

    All tools must inherit from this class and implement the execute method.
    Tools are automatically registered when decorated with @tool.
    """

    def __init__(self) -> None:
        """Initialize the tool."""
        self._metadata: Optional[ToolMetadata] = None

    @property
    def metadata(self) -> ToolMetadata:
        """Get tool metadata."""
        if self._metadata is None:
            raise ValueError("Tool metadata not set. Use @tool decorator.")
        return self._metadata

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute the tool with given parameters.

        Args:
            **kwargs: Tool parameters as keyword arguments

        Returns:
            Dictionary containing execution results with keys:
            - success: bool indicating if execution succeeded
            - result: Any result data if successful
            - error: str error message if failed
            - execution_time_ms: int execution time in milliseconds

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        pass

    def validate_parameters(self, **kwargs: Any) -> None:
        """Validate that all required parameters are present and valid.

        Args:
            **kwargs: Parameters to validate

        Raises:
            ValueError: If validation fails
        """
        required_params = {p.name for p in self.metadata.parameters if p.required}
        provided_params = set(kwargs.keys())

        missing = required_params - provided_params
        if missing:
            raise ValueError(f"Missing required parameters: {', '.join(missing)}")

        # Validate parameter types
        param_map = {p.name: p for p in self.metadata.parameters}
        for name, value in kwargs.items():
            if name not in param_map:
                raise ValueError(f"Unknown parameter: {name}")

            param = param_map[name]
            if not self._validate_type(value, param.type):
                raise ValueError(
                    f"Parameter '{name}' has invalid type. "
                    f"Expected {param.type.value}, got {type(value).__name__}"
                )

    def _validate_type(self, value: Any, expected_type: ToolParameterType) -> bool:
        """Validate that value matches expected type."""
        if expected_type == ToolParameterType.STRING:
            return isinstance(value, str)
        elif expected_type == ToolParameterType.INTEGER:
            return isinstance(value, int) and not isinstance(value, bool)
        elif expected_type == ToolParameterType.FLOAT:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        elif expected_type == ToolParameterType.BOOLEAN:
            return isinstance(value, bool)
        elif expected_type == ToolParameterType.ARRAY:
            return isinstance(value, list)
        elif expected_type == ToolParameterType.OBJECT:
            return isinstance(value, dict)
