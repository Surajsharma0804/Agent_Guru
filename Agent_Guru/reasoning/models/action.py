"""Action and tool data models."""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ActionSensitivity(str, Enum):
    """Enumeration of action sensitivity levels."""

    SAFE = "safe"  # No confirmation needed
    SENSITIVE = "sensitive"  # Confirmation required
    DANGEROUS = "dangerous"  # Requires explicit permission


class Parameter(BaseModel):
    """Represents a tool parameter definition."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "duration",
            "param_type": "int",
            "required": True,
            "description": "Timer duration in seconds",
            "validation_rules": {"min": 1, "max": 86400},
        }
    })

    name: str = Field(..., description="Parameter name")
    param_type: str = Field(..., description="Parameter type (str, int, float, bool, etc.)")
    required: bool = Field(default=True, description="Whether parameter is required")
    default: Optional[Any] = Field(default=None, description="Default value if not required")
    description: str = Field(default="", description="Parameter description")
    validation_rules: dict[str, Any] = Field(
        default_factory=dict,
        description="Validation rules (min, max, pattern, etc.)",
    )

    @field_validator("param_type")
    @classmethod
    def validate_param_type(cls, v: str) -> str:
        """Validate parameter type is recognized."""
        valid_types = {
            "str", "int", "float", "bool", "list", "dict",
            "datetime", "duration", "any"
        }
        if v not in valid_types:
            raise ValueError(f"Parameter type must be one of {valid_types}, got {v}")
        return v

    def __eq__(self, other: object) -> bool:
        """Check equality based on name and type."""
        if not isinstance(other, Parameter):
            return False
        return self.name == other.name and self.param_type == other.param_type

    def __hash__(self) -> int:
        """Generate hash for parameter."""
        return hash((self.name, self.param_type))


class Tool(BaseModel):
    """Represents an executable tool."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "tool_id": "set_timer",
            "name": "Set Timer",
            "description": "Set a countdown timer",
            "parameters": [
                {
                    "name": "duration",
                    "param_type": "int",
                    "required": True,
                    "description": "Duration in seconds",
                }
            ],
            "sensitivity": "safe",
            "estimated_latency": 0.05,
            "requires_permission": False,
            "tags": ["time", "scheduling"],
        }
    })

    tool_id: str = Field(..., description="Unique tool identifier")
    name: str = Field(..., description="Human-readable tool name")
    description: str = Field(..., description="Tool description")
    parameters: list[Parameter] = Field(
        default_factory=list,
        description="Tool parameters",
    )
    sensitivity: ActionSensitivity = Field(
        default=ActionSensitivity.SAFE,
        description="Tool sensitivity level",
    )
    estimated_latency: float = Field(
        default=0.1,
        description="Estimated execution latency in seconds",
    )
    requires_permission: bool = Field(
        default=False,
        description="Whether tool requires explicit permission",
    )
    permission_scope: Optional[str] = Field(
        default=None,
        description="Permission scope required (e.g., 'messaging', 'smart_home')",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tool tags for categorization",
    )

    @field_validator("tool_id")
    @classmethod
    def validate_tool_id(cls, v: str) -> str:
        """Validate tool ID format."""
        if not v or not v.replace("_", "").replace("-", "").replace(".", "").isalnum():
            raise ValueError("Tool ID must be alphanumeric with underscores, hyphens, or dots")
        return v

    @field_validator("estimated_latency")
    @classmethod
    def validate_latency(cls, v: float) -> float:
        """Validate latency is non-negative."""
        if v < 0:
            raise ValueError("Estimated latency must be non-negative")
        return v

    def get_required_parameters(self) -> list[Parameter]:
        """
        Get list of required parameters.

        Returns:
            List of required parameters
        """
        return [p for p in self.parameters if p.required]

    def get_optional_parameters(self) -> list[Parameter]:
        """
        Get list of optional parameters.

        Returns:
            List of optional parameters
        """
        return [p for p in self.parameters if not p.required]

    def validate_parameters(self, provided: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate provided parameters against tool definition.

        Args:
            provided: Dictionary of provided parameter values

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check required parameters
        for param in self.get_required_parameters():
            if param.name not in provided:
                errors.append(f"Missing required parameter: {param.name}")

        # Check parameter types (basic validation)
        for name, value in provided.items():
            param = next((p for p in self.parameters if p.name == name), None)
            if param is None:
                errors.append(f"Unknown parameter: {name}")
            elif param.param_type == "int" and not isinstance(value, int):
                errors.append(f"Parameter {name} must be int, got {type(value).__name__}")
            elif param.param_type == "str" and not isinstance(value, str):
                errors.append(f"Parameter {name} must be str, got {type(value).__name__}")
            elif param.param_type == "bool" and not isinstance(value, bool):
                errors.append(f"Parameter {name} must be bool, got {type(value).__name__}")

        return len(errors) == 0, errors

    def __eq__(self, other: object) -> bool:
        """Check equality based on tool ID."""
        if not isinstance(other, Tool):
            return False
        return self.tool_id == other.tool_id

    def __hash__(self) -> int:
        """Generate hash for tool."""
        return hash(self.tool_id)


class Action(BaseModel):
    """Represents an action to be executed."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "action_id": "action_123",
            "tool_id": "set_timer",
            "parameters": {"duration": 300},
            "is_sensitive": False,
            "estimated_duration": 0.05,
            "requires_confirmation": False,
        }
    })

    action_id: str = Field(..., description="Unique action identifier")
    tool_id: str = Field(..., description="ID of tool to execute")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Action parameters",
    )
    is_sensitive: bool = Field(
        default=False,
        description="Whether action is sensitive",
    )
    estimated_duration: float = Field(
        default=0.1,
        description="Estimated execution duration in seconds",
    )
    requires_confirmation: bool = Field(
        default=False,
        description="Whether action requires user confirmation",
    )
    confirmation_message: Optional[str] = Field(
        default=None,
        description="Message to show for confirmation",
    )

    @field_validator("action_id")
    @classmethod
    def validate_action_id(cls, v: str) -> str:
        """Validate action ID is not empty."""
        if not v:
            raise ValueError("Action ID cannot be empty")
        return v

    @field_validator("tool_id")
    @classmethod
    def validate_tool_id(cls, v: str) -> str:
        """Validate tool ID is not empty."""
        if not v:
            raise ValueError("Tool ID cannot be empty")
        return v

    @field_validator("estimated_duration")
    @classmethod
    def validate_duration(cls, v: float) -> float:
        """Validate duration is non-negative."""
        if v < 0:
            raise ValueError("Estimated duration must be non-negative")
        return v

    def __eq__(self, other: object) -> bool:
        """Check equality based on action ID."""
        if not isinstance(other, Action):
            return False
        return self.action_id == other.action_id

    def __hash__(self) -> int:
        """Generate hash for action."""
        return hash(self.action_id)
