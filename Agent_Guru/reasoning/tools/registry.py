"""Tool registry for managing and discovering tools.

This module provides a centralized registry for all tools with automatic discovery
and capability-based matching.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from Agent_Guru.reasoning.tools.base import Tool, ToolMetadata, ToolSensitivity

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Registry for managing tools with plugin architecture.

    Provides automatic tool discovery, registration, and capability-based matching.
    Thread-safe for concurrent access.
    """

    def __init__(self) -> None:
        """Initialize the tool registry."""
        self._tools: dict[str, Tool] = {}
        self._metadata: dict[str, ToolMetadata] = {}
        self._capability_index: dict[str, set[str]] = {}  # capability -> tool_ids
        self._lock = asyncio.Lock()

    async def register(self, tool: Tool, metadata: ToolMetadata) -> None:
        """Register a tool with the registry.

        Args:
            tool: Tool instance to register
            metadata: Tool metadata

        Raises:
            ValueError: If tool_id already registered

        """
        async with self._lock:
            if metadata.tool_id in self._tools:
                msg = f"Tool '{metadata.tool_id}' already registered"
                raise ValueError(msg)

            # Set metadata on tool
            tool._metadata = metadata

            # Register tool
            self._tools[metadata.tool_id] = tool
            self._metadata[metadata.tool_id] = metadata

            # Build capability index
            for capability in metadata.capabilities:
                if capability not in self._capability_index:
                    self._capability_index[capability] = set()
                self._capability_index[capability].add(metadata.tool_id)

    async def unregister(self, tool_id: str) -> None:
        """Unregister a tool from the registry.

        Args:
            tool_id: Tool ID to unregister

        """
        async with self._lock:
            if tool_id not in self._tools:
                return

            metadata = self._metadata[tool_id]

            # Remove from capability index
            for capability in metadata.capabilities:
                if capability in self._capability_index:
                    self._capability_index[capability].discard(tool_id)
                    if not self._capability_index[capability]:
                        del self._capability_index[capability]

            # Remove tool
            del self._tools[tool_id]
            del self._metadata[tool_id]

    def get_tool(self, tool_id: str) -> Tool | None:
        """Get a tool by ID.

        Args:
            tool_id: Tool ID to retrieve

        Returns:
            Tool instance or None if not found

        """
        return self._tools.get(tool_id)

    def get_metadata(self, tool_id: str) -> ToolMetadata | None:
        """Get tool metadata by ID.

        Args:
            tool_id: Tool ID to retrieve metadata for

        Returns:
            Tool metadata or None if not found

        """
        return self._metadata.get(tool_id)

    def list_tools(self) -> list[ToolMetadata]:
        """List all registered tools.

        Returns:
            List of tool metadata for all registered tools

        """
        return list(self._metadata.values())

    def find_by_capability(self, capability: str) -> list[ToolMetadata]:
        """Find tools by capability.

        Args:
            capability: Capability to search for

        Returns:
            List of tool metadata matching the capability

        """
        tool_ids = self._capability_index.get(capability, set())
        return [self._metadata[tool_id] for tool_id in tool_ids if tool_id in self._metadata]

    def find_by_capabilities(self, capabilities: list[str]) -> list[ToolMetadata]:
        """Find tools matching any of the given capabilities.

        Args:
            capabilities: List of capabilities to search for

        Returns:
            List of tool metadata matching any capability, sorted by match count

        """
        # Count matches per tool
        match_counts: dict[str, int] = {}
        for capability in capabilities:
            tool_ids = self._capability_index.get(capability, set())
            for tool_id in tool_ids:
                match_counts[tool_id] = match_counts.get(tool_id, 0) + 1

        # Sort by match count (descending)
        sorted_tool_ids = sorted(match_counts.keys(), key=lambda x: match_counts[x], reverse=True)

        return [self._metadata[tool_id] for tool_id in sorted_tool_ids if tool_id in self._metadata]

    async def execute(
        self,
        tool_id: str,
        timeout_ms: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a tool with given parameters.

        Args:
            tool_id: Tool ID to execute
            timeout_ms: Optional timeout in milliseconds
            **kwargs: Tool parameters

        Returns:
            Execution result dictionary

        Raises:
            ValueError: If tool not found or parameters invalid
            asyncio.TimeoutError: If execution exceeds timeout

        """
        tool = self.get_tool(tool_id)
        if tool is None:
            msg = f"Tool '{tool_id}' not found"
            raise ValueError(msg)

        # Validate parameters
        tool.validate_parameters(**kwargs)

        # Execute with timeout
        start_time = time.perf_counter()
        try:
            if timeout_ms is not None:
                result = await asyncio.wait_for(tool.execute(**kwargs), timeout=timeout_ms / 1000.0)
            else:
                result = await tool.execute(**kwargs)

            execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            result["execution_time_ms"] = execution_time_ms
            return result

        except TimeoutError:
            execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            return {
                "success": False,
                "error": f"Tool execution timed out after {timeout_ms}ms",
                "execution_time_ms": execution_time_ms,
            }

        except Exception as exc:
            # BUG FIX: only the timeout path was handled, so ANY exception a
            # tool raised propagated straight out of the registry. Tools are
            # the least trustworthy code in the system - third-party
            # integrations, subprocesses, network calls - and this is the
            # boundary that is supposed to contain them: every caller above
            # consumes the {"success": ..., "error": ...} dict this method
            # documents, so one misbehaving tool could take down a whole
            # reasoning turn instead of returning a failed tool result the
            # planner can react to.
            #
            # asyncio.CancelledError derives from BaseException, so genuine
            # cancellation still propagates rather than being reported as a
            # tool failure.
            execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            logger.exception("Tool '%s' raised during execution", tool_id)
            return {
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
                "execution_time_ms": execution_time_ms,
            }

# Global registry instance
_global_registry = ToolRegistry()

def get_registry() -> ToolRegistry:
    """Get the global tool registry instance.

    Returns:
        Global ToolRegistry instance

    """
    return _global_registry

def tool(
    tool_id: str,
    name: str,
    description: str,
    parameters: list[Any] | None = None,
    sensitivity: ToolSensitivity = ToolSensitivity.SAFE,
    estimated_latency_ms: int = 1000,
    capabilities: list[str] | None = None,
    examples: list[str] | None = None,
) -> Callable[[type[Tool]], type[Tool]]:
    """Decorator for automatic tool registration.

    Args:
        tool_id: Unique tool identifier
        name: Human-readable tool name
        description: Tool description
        parameters: List of ToolParameter instances
        sensitivity: Tool sensitivity level
        estimated_latency_ms: Estimated execution latency
        capabilities: List of capabilities
        examples: List of example usage scenarios

    Returns:
        Decorator function

    Example:
        @tool(
            tool_id="timer.set",
            name="Set Timer",
            description="Set a timer for a specified duration",
            parameters=[
                ToolParameter(
                    name="duration_seconds",
                    type=ToolParameterType.INTEGER,
                    description="Timer duration in seconds",
                    required=True
                )
            ],
            capabilities=["timer", "time_management"]
        )
        class SetTimerTool(Tool):
            async def execute(self, **kwargs):
                # Implementation
                pass

    """

    def decorator(cls: type[Tool]) -> type[Tool]:
        # Create metadata
        metadata = ToolMetadata(
            tool_id=tool_id,
            name=name,
            description=description,
            parameters=parameters or [],
            sensitivity=sensitivity,
            estimated_latency_ms=estimated_latency_ms,
            capabilities=capabilities or [],
            examples=examples or [],
        )

        # Store metadata on class
        cls._tool_metadata = metadata  # type: ignore[attr-defined]

        # Register tool instance on first instantiation
        original_init = cls.__init__

        @wraps(original_init)
        def new_init(self: Tool, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            # Store metadata on instance
            self._metadata = metadata
            # Mark for lazy registration (will be registered when needed)
            self._registered = False  # type: ignore[attr-defined]

        cls.__init__ = new_init  # type: ignore

        # Add method to ensure registration
        async def ensure_registered(self: Tool) -> None:
            """Ensure tool is registered with global registry."""
            if not self._registered:  # type: ignore[attr-defined]
                await _global_registry.register(self, metadata)
                self._registered = True  # type: ignore[attr-defined]

        cls.ensure_registered = ensure_registered  # type: ignore

        return cls

    return decorator
