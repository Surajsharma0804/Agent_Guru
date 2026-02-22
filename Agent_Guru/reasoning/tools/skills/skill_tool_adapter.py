"""
Adapter to integrate skills with the tool selection system.

Wraps skills as Tool instances so they can be selected and executed
alongside core tools.
"""

import time
from typing import Any, Dict, Optional

from Agent_Guru.reasoning.models.skill import InstalledSkill, SkillStatus
from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolMetadata,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.skills.sandbox_executor import (
    get_sandbox_executor,
)


class SkillToolAdapter(Tool):
    """Adapter that wraps a skill as a Tool."""

    def __init__(self, skill: InstalledSkill, entry_point: str):
        """Initialize skill tool adapter.

        Args:
            skill: Installed skill
            entry_point: Entry point to execute
        """
        super().__init__()
        self.skill = skill
        self.entry_point = entry_point
        self.executor = get_sandbox_executor()

        # Create tool metadata from skill manifest
        self._metadata = self._create_metadata()

    def _create_metadata(self) -> ToolMetadata:
        """Create tool metadata from skill manifest.

        Returns:
            Tool metadata
        """
        # Map skill capabilities to tool capabilities
        capabilities = self.skill.manifest.capabilities

        # Determine sensitivity based on required permissions
        sensitivity = self._determine_sensitivity()

        # Create parameters (skills typically accept generic parameters)
        parameters = [
            ToolParameter(
                name="parameters",
                type=ToolParameterType.OBJECT,
                description="Skill parameters",
                required=False,
                default={},
            )
        ]

        return ToolMetadata(
            tool_id=f"skill.{self.skill.manifest.skill_id}.{self.entry_point}",
            name=f"{self.skill.manifest.name} - {self.entry_point}",
            description=self.skill.manifest.description,
            parameters=parameters,
            sensitivity=sensitivity,
            estimated_latency_ms=self.skill.manifest.max_latency,
            capabilities=capabilities,
            examples=[],
        )

    def _determine_sensitivity(self) -> ToolSensitivity:
        """Determine tool sensitivity based on required permissions.

        Returns:
            Tool sensitivity level
        """
        from Agent_Guru.reasoning.models.skill import Permission

        # Dangerous permissions require explicit confirmation
        dangerous_permissions = {
            Permission.FILE_WRITE,
            Permission.SYSTEM_CONTROL,
        }

        # Sensitive permissions require confirmation
        sensitive_permissions = {
            Permission.LOCATION_ACCESS,
            Permission.CALENDAR_ACCESS,
            Permission.CONTACTS_ACCESS,
        }

        required = set(self.skill.manifest.required_permissions)

        if required & dangerous_permissions:
            return ToolSensitivity.DANGEROUS
        elif required & sensitive_permissions:
            return ToolSensitivity.SENSITIVE
        else:
            return ToolSensitivity.SAFE

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute the skill.

        Args:
            **kwargs: Tool parameters

        Returns:
            Execution result dictionary
        """
        start_time = time.perf_counter()

        # Validate parameters
        self.validate_parameters(**kwargs)

        # Extract parameters
        parameters = kwargs.get("parameters", {})

        # Get user_id from context (default to "default" for now)
        user_id = kwargs.get("user_id", "default")

        # Execute skill through sandbox executor
        result = await self.executor.execute_skill(
            skill=self.skill,
            entry_point=self.entry_point,
            parameters=parameters,
            user_id=user_id,
        )

        # Calculate execution time
        execution_time_ms = int((time.perf_counter() - start_time) * 1000)

        # Return standardized result
        return {
            "success": result.success,
            "result": result.result if result.success else None,
            "error": result.error if not result.success else None,
            "execution_time_ms": execution_time_ms,
            "resource_usage": result.resource_usage,
        }


class SkillToolRegistry:
    """Registry for skill-based tools."""

    def __init__(self):
        """Initialize skill tool registry."""
        self._skill_tools: Dict[str, SkillToolAdapter] = {}

    def register_skill(self, skill: InstalledSkill) -> None:
        """Register a skill and create tool adapters for its entry points.

        Args:
            skill: Skill to register
        """
        # Only register active skills
        if skill.status != SkillStatus.ACTIVE:
            return

        # Create tool adapter for each entry point
        for entry_point in skill.manifest.entry_points.keys():
            tool = SkillToolAdapter(skill, entry_point)
            tool_id = tool.metadata.tool_id
            self._skill_tools[tool_id] = tool

    def unregister_skill(self, skill_id: str) -> None:
        """Unregister a skill and remove its tool adapters.

        Args:
            skill_id: Skill ID to unregister
        """
        # Remove all tools for this skill
        to_remove = [
            tool_id
            for tool_id in self._skill_tools.keys()
            if tool_id.startswith(f"skill.{skill_id}.")
        ]

        for tool_id in to_remove:
            del self._skill_tools[tool_id]

    def get_skill_tool(self, tool_id: str) -> Optional[SkillToolAdapter]:
        """Get a skill tool by ID.

        Args:
            tool_id: Tool ID

        Returns:
            Skill tool or None if not found
        """
        return self._skill_tools.get(tool_id)

    def list_skill_tools(self) -> list[SkillToolAdapter]:
        """List all registered skill tools.

        Returns:
            List of skill tools
        """
        return list(self._skill_tools.values())

    def find_by_capability(self, capability: str) -> list[SkillToolAdapter]:
        """Find skill tools by capability.

        Args:
            capability: Capability to search for

        Returns:
            List of matching skill tools
        """
        return [
            tool
            for tool in self._skill_tools.values()
            if capability in tool.metadata.capabilities
        ]


# Global skill tool registry
_global_skill_tool_registry: Optional[SkillToolRegistry] = None


def get_skill_tool_registry() -> SkillToolRegistry:
    """Get the global skill tool registry instance.

    Returns:
        Global SkillToolRegistry instance
    """
    global _global_skill_tool_registry
    if _global_skill_tool_registry is None:
        _global_skill_tool_registry = SkillToolRegistry()
    return _global_skill_tool_registry
