"""Tool parameter extraction with validation and type conversion.

This module provides parameter extraction from intent entities with:
- Required parameter validation
- Optional parameter defaults
- Type conversion and validation
"""

from typing import Any

from Agent_Guru.reasoning.error.error_manager import (
    ErrorContext,
    ErrorType,
    get_error_manager,
)
from Agent_Guru.reasoning.models.intent import Entity, Intent
from Agent_Guru.reasoning.tools.base import Tool, ToolParameter, ToolParameterType


class ParameterExtractor:
    """Extracts and validates tool parameters from intent entities."""

    def extract_parameters(self, tool: Tool, intent: Intent) -> dict[str, Any]:
        """Extract parameters from intent entities with validation.

        Args:
            tool: Tool to extract parameters for
            intent: Intent containing entities

        Returns:
            Dictionary of parameter name → value

        Raises:
            ValueError: If required parameters missing or validation fails (with user-friendly message)

        """
        error_manager = get_error_manager()
        metadata = tool.metadata
        parameters: dict[str, Any] = {}

        # Extract each parameter
        for param in metadata.parameters:
            value = self._extract_parameter(param, intent)

            if value is None:
                if param.required:
                    context = ErrorContext(
                        tool_id=metadata.tool_id,
                        additional_data={
                            "parameter": param.name,
                            "intent_type": intent.intent_type.value,
                        },
                    )
                    error = error_manager.create_error(
                        error_type=ErrorType.INVALID_INPUT,
                        message=f"Required parameter '{param.name}' not found in intent",
                        context=context,
                    )
                    raise ValueError(error.user_message)
                # Apply default value for optional parameters
                if hasattr(param, "default_value") and param.default_value is not None:
                    value = param.default_value
                else:
                    continue  # Skip optional parameters without defaults

            # Type conversion and validation
            try:
                value = self._convert_and_validate(value, param)
            except (ValueError, TypeError) as e:
                context = ErrorContext(
                    tool_id=metadata.tool_id,
                    additional_data={
                        "parameter": param.name,
                        "value": str(value),
                        "expected_type": param.type.value,
                    },
                )
                error = error_manager.create_error(
                    error_type=ErrorType.INVALID_INPUT,
                    message=f"Parameter '{param.name}' validation failed: {e!s}",
                    context=context,
                )
                raise ValueError(error.user_message) from e

            parameters[param.name] = value

        return parameters

    def _extract_parameter(self, param: ToolParameter, intent: Intent) -> Any | None:  # noqa: ANN401
        """Extract single parameter from intent entities.

        Args:
            param: Parameter definition
            intent: Intent containing entities

        Returns:
            Parameter value or None if not found

        """
        # Try exact match first
        if param.name in intent.entities:
            entity = intent.entities[param.name]
            return entity.value if isinstance(entity, Entity) else entity

        # Try fuzzy match (e.g., "duration" matches "duration_seconds")
        for entity_name, entity_value in intent.entities.items():
            if param.name.startswith(entity_name) or entity_name.startswith(param.name):
                return entity_value.value if isinstance(entity_value, Entity) else entity_value

        return None

    def _convert_and_validate(self, value: Any, param: ToolParameter) -> Any:  # noqa: ANN401
        """Convert value to correct type and validate.

        Args:
            value: Raw value to convert
            param: Parameter definition

        Returns:
            Converted and validated value

        Raises:
            ValueError: If conversion or validation fails

        """
        # Type conversion
        if param.type == ToolParameterType.STRING:
            value = str(value)
        elif param.type == ToolParameterType.INTEGER:
            value = int(value)
        elif param.type == ToolParameterType.FLOAT:
            value = float(value)
        elif param.type == ToolParameterType.BOOLEAN:
            if isinstance(value, str):
                value = value.lower() in ("true", "yes", "1", "on")
            else:
                value = bool(value)
        elif param.type == ToolParameterType.ARRAY:
            if not isinstance(value, list):
                value = [value]
        elif param.type == ToolParameterType.OBJECT and not isinstance(value, dict):
            msg = f"Expected dict, got {type(value)}"
            raise ValueError(msg)

        # Validation
        if hasattr(param, "min_value") and param.min_value is not None and value < param.min_value:
            msg = f"Value {value} below minimum {param.min_value}"
            raise ValueError(msg)

        if hasattr(param, "max_value") and param.max_value is not None and value > param.max_value:
            msg = f"Value {value} above maximum {param.max_value}"
            raise ValueError(msg)

        if (
            hasattr(param, "allowed_values")
            and param.allowed_values
            and value not in param.allowed_values
        ):
            msg = f"Value {value} not in allowed values {param.allowed_values}"
            raise ValueError(msg)

        return value

    def validate_parameters(self, tool: Tool, parameters: dict[str, Any]) -> list[str]:
        """Validate extracted parameters.

        Args:
            tool: Tool to validate parameters for
            parameters: Extracted parameters

        Returns:
            List of validation errors (empty if valid)

        """
        errors: list[str] = []
        metadata = tool.metadata

        # Check required parameters
        for param in metadata.parameters:
            if param.required and param.name not in parameters:
                errors.append(f"Required parameter '{param.name}' missing")

        # Check parameter types and constraints
        for param in metadata.parameters:
            if param.name not in parameters:
                continue

            value = parameters[param.name]

            # Type validation
            try:
                self._convert_and_validate(value, param)
            except (ValueError, TypeError) as e:
                errors.append(f"Parameter '{param.name}': {e!s}")

        return errors
