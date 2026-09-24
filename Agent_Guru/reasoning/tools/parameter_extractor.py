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


def _missing_parameter_error(
    param: Any,
    metadata: Any,
    technical_message: str,
    error: Any,
) -> ValueError:
    """Build the exception raised when a required tool parameter is absent.

    str() is the technical message so logs and tracebacks are diagnosable.
    ``user_message`` is what a caller renders to the person: a request for the
    one missing detail, not a claim that the request was not understood -
    the intent was matched to a tool, so "Could you rephrase?" is both
    unhelpful and inaccurate.
    """
    described = getattr(param, "description", None) or param.name
    exc = ValueError(technical_message)
    exc.user_message = (
        f"I need one more detail before I can do that: {described}."
    )
    exc.technical_message = technical_message
    exc.error = error
    exc.missing_parameter = param.name
    exc.tool_id = metadata.tool_id
    return exc


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
                    technical_message = (
                        f"Required parameter '{param.name}' not found in intent"
                    )
                    error = error_manager.create_error(
                        error_type=ErrorType.INVALID_INPUT,
                        message=technical_message,
                        context=context,
                    )
                    # The technical detail used to be built, handed to the
                    # ErrorManager, and then DISCARDED: only
                    # error.user_message was raised, so every missing-parameter
                    # failure surfaced - in logs, in tracebacks, to every
                    # caller - as the generic "I didn't understand that. Could
                    # you rephrase?", with no way to tell WHICH parameter of
                    # WHICH tool was missing.
                    #
                    # str(exc) now carries the diagnosable message; the
                    # user-facing sentence stays available on the exception for
                    # anything that renders to the person, and it now names the
                    # missing detail instead of claiming incomprehension - the
                    # intent WAS understood, one value is simply absent.
                    raise _missing_parameter_error(param, metadata, technical_message, error)
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
                technical_message = f"Parameter '{param.name}' validation failed: {e!s}"
                error = error_manager.create_error(
                    error_type=ErrorType.INVALID_INPUT,
                    message=technical_message,
                    context=context,
                )
                # Same reasoning as above: keep the diagnosable text in str().
                exc = ValueError(technical_message)
                exc.user_message = error.user_message
                exc.error = error
                raise exc from e

            parameters[param.name] = value

        return parameters

    def _extract_parameter(self, param: ToolParameter, intent: Intent) -> Any | None:
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

    def _convert_and_validate(self, value: Any, param: ToolParameter) -> Any:
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
