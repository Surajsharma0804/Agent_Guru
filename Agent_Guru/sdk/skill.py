"""Base Skill class and decorators for skill development.

Provides the foundation for creating Agent Guru skills with
capability decorators and parameter validation.
"""

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, get_type_hints


class SkillMetadata:
    """Metadata for a skill capability."""

    def __init__(
        self,
        capability: str,
        description: str,
        parameters: list[dict[str, Any]],
    ) -> None:
        """Initialize skill metadata.

        Args:
            capability: Capability identifier
            description: Capability description
            parameters: List of parameter definitions

        """
        self.capability = capability
        self.description = description
        self.parameters = parameters


class Skill:
    """Base class for Agent Guru skills.

    All skills must inherit from this class and use the @skill_capability
    decorator to define their capabilities.

    Example:
        class MySkill(Skill):
            @skill_capability("my_capability")
            async def my_method(self, param1: str, param2: int) -> dict:
                return {"result": "success"}

    """

    def __init__(self) -> None:
        """Initialize skill."""
        self._capabilities: dict[str, SkillMetadata] = {}
        self._discover_capabilities()

    def _discover_capabilities(self) -> None:
        """Discover capabilities defined with @skill_capability decorator."""
        for name in dir(self):
            if name.startswith("_"):
                continue

            attr = getattr(self, name)
            if hasattr(attr, "_skill_capability"):
                metadata = attr._skill_capability
                self._capabilities[metadata.capability] = metadata

    def get_capabilities(self) -> list[str]:
        """Get list of capability identifiers.

        Returns:
            List of capability identifiers

        """
        return list(self._capabilities.keys())

    def get_capability_metadata(self, capability: str) -> SkillMetadata | None:
        """Get metadata for a capability.

        Args:
            capability: Capability identifier

        Returns:
            Capability metadata or None if not found

        """
        return self._capabilities.get(capability)

    async def execute_capability(self, capability: str, **kwargs: Any) -> Any:  # noqa: ANN401
        """Execute a capability with given parameters.

        Args:
            capability: Capability to execute
            **kwargs: Parameters for capability

        Returns:
            Capability result

        Raises:
            ValueError: If capability not found

        """
        metadata = self.get_capability_metadata(capability)
        if metadata is None:
            msg = f"Capability '{capability}' not found"
            raise ValueError(msg)

        # Find method
        for name in dir(self):
            attr = getattr(self, name)
            if (
                hasattr(attr, "_skill_capability")
                and attr._skill_capability.capability == capability
            ):
                # Execute method
                if inspect.iscoroutinefunction(attr):
                    return await attr(**kwargs)
                return attr(**kwargs)

        msg = f"Capability '{capability}' not found"
        raise ValueError(msg)


def skill_capability(capability: str, description: str | None = None) -> Callable:
    """Decorator to mark a method as a skill capability.

    Args:
        capability: Capability identifier
        description: Capability description (optional)

    Returns:
        Decorated function

    Example:
        @skill_capability("weather_query", "Get weather for a location")
        async def get_weather(self, location: str) -> dict:
            return {"temperature": 72}

    """

    def decorator(func: Callable) -> Callable:
        # Get function signature
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        # Extract parameters (skip 'self')
        parameters = []
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            param_type = type_hints.get(param_name, Any)
            param_required = param.default == inspect.Parameter.empty

            parameters.append(
                {
                    "name": param_name,
                    "type": _type_to_string(param_type),
                    "required": param_required,
                    "default": (None if param_required else param.default),
                },
            )

        # Create metadata
        metadata = SkillMetadata(
            capability=capability,
            description=description or func.__doc__ or "",
            parameters=parameters,
        )

        # Attach metadata to function
        func._skill_capability = metadata  # type: ignore[attr-defined]

        @wraps(func)
        async def wrapper(*args, **kwargs):
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        wrapper._skill_capability = metadata  # type: ignore[attr-defined]
        return wrapper

    return decorator


def skill_parameter(
    name: str,
    param_type: str,
    description: str,
    required: bool = True,
    default: Any = None,  # noqa: ANN401
) -> dict[str, Any]:
    """Define a skill parameter.

    This is a helper function for manually defining parameters
    when automatic extraction is not sufficient.

    Args:
        name: Parameter name
        param_type: Parameter type (string, integer, float, boolean, array, object)
        description: Parameter description
        required: Whether parameter is required
        default: Default value if not required

    Returns:
        Parameter definition dictionary

    """
    return {
        "name": name,
        "type": param_type,
        "description": description,
        "required": required,
        "default": default,
    }


def _type_to_string(type_hint: Any) -> str:  # noqa: ANN401
    """Convert Python type hint to string representation.

    Args:
        type_hint: Type hint

    Returns:
        String representation

    """
    if type_hint is str:
        return "string"
    if type_hint is int:
        return "integer"
    if type_hint is float:
        return "float"
    if type_hint is bool:
        return "boolean"
    if type_hint is list or str(type_hint).startswith("typing.List"):
        return "array"
    if type_hint is dict or str(type_hint).startswith("typing.Dict"):
        return "object"
    return "string"  # Default to string
