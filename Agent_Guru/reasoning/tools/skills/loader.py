"""Skill loader for loading and registering third-party skills.

Handles skill discovery, validation, and registration with the tool registry.
"""

import logging

_logger = logging.getLogger(__name__)

import importlib.util  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

from Agent_Guru.reasoning.error.error_manager import (  # noqa: E402
    ErrorContext,
    ErrorType,
    get_error_manager,
)
from Agent_Guru.reasoning.tools.base import Tool  # noqa: E402
from Agent_Guru.reasoning.tools.registry import get_registry  # noqa: E402
from Agent_Guru.reasoning.tools.skills.manifest import (  # noqa: E402
    SkillManifest,
    SkillManifestParser,
    SkillManifestValidator,
)


class SkillLoader:
    """Loader for third-party skills."""

    def __init__(self, plugins_dir: Path) -> None:
        """Initialize skill loader.

        Args:
            plugins_dir: Directory containing skill plugins

        """
        self.plugins_dir = Path(plugins_dir)
        self.loaded_skills: dict[str, SkillManifest] = {}
        self.registry = get_registry()

    async def load_skill(self, skill_dir: Path) -> SkillManifest:
        """Load a skill from a directory.

        Args:
            skill_dir: Directory containing skill

        Returns:
            Loaded skill manifest

        Raises:
            ValueError: If loading fails (with user-friendly message)

        """
        error_manager = get_error_manager()

        # Find manifest file
        manifest_path = skill_dir / "skill.yaml"
        if not manifest_path.exists():
            manifest_path = skill_dir / "skill.yml"
            if not manifest_path.exists():
                context = ErrorContext(additional_data={"skill_dir": str(skill_dir)})
                error = error_manager.create_error(
                    error_type=ErrorType.TOOL_UNAVAILABLE,
                    message=f"No manifest file found in {skill_dir}",
                    context=context,
                )
                raise ValueError(error.user_message)

        # Parse manifest
        try:
            manifest = SkillManifestParser.parse_yaml(manifest_path)
        except ValueError as e:
            context = ErrorContext(additional_data={"manifest_path": str(manifest_path)})
            error = error_manager.create_error(
                error_type=ErrorType.MALFORMED_INPUT,
                message=f"Failed to parse manifest: {e!s}",
                context=context,
            )
            raise ValueError(error.user_message) from e

        # Validate manifest
        errors = SkillManifestValidator.validate(manifest)
        if errors:
            context = ErrorContext(additional_data={"validation_errors": errors})
            error = error_manager.create_error(
                error_type=ErrorType.PLAN_VALIDATION_FAILED,
                message=f"Manifest validation failed: {', '.join(errors)}",
                context=context,
            )
            raise ValueError(error.user_message)

        # Check if already loaded
        if manifest.skill_id in self.loaded_skills:
            context = ErrorContext(
                tool_id=manifest.skill_id,
            )
            error = error_manager.create_error(
                error_type=ErrorType.TOOL_UNAVAILABLE,
                message=f"Skill '{manifest.skill_id}' already loaded",
                context=context,
            )
            raise ValueError(error.user_message)

        # Load skill module
        try:
            module = self._load_module(skill_dir, manifest.entry_point)
        except Exception as e:
            context = ErrorContext(
                tool_id=manifest.skill_id,
                additional_data={"entry_point": manifest.entry_point},
            )
            error = error_manager.create_error(
                error_type=ErrorType.TOOL_UNAVAILABLE,
                message=f"Failed to load skill module: {e!s}",
                context=context,
            )
            raise ValueError(error.user_message) from e

        # Register tools
        try:
            await self._register_tools(module, manifest)
        except Exception as e:
            context = ErrorContext(
                tool_id=manifest.skill_id,
            )
            error = error_manager.create_error(
                error_type=ErrorType.TOOL_UNAVAILABLE,
                message=f"Failed to register tools: {e!s}",
                context=context,
            )
            raise ValueError(error.user_message) from e

        # Mark as loaded
        self.loaded_skills[manifest.skill_id] = manifest

        return manifest

    def _load_module(self, skill_dir: Path, entry_point: str) -> Any:
        """Load skill module.

        Args:
            skill_dir: Skill directory
            entry_point: Entry point module path

        Returns:
            Loaded module

        Raises:
            ImportError: If module loading fails

        """
        # Convert entry point to file path
        module_path = skill_dir / entry_point.replace(".", "/")
        if module_path.is_dir():
            module_path = module_path / "__init__.py"
        elif not module_path.suffix:
            module_path = module_path.with_suffix(".py")

        if not module_path.exists():
            msg = f"Module file not found: {module_path}"
            raise ImportError(msg)

        # Load module
        spec = importlib.util.spec_from_file_location(entry_point, module_path)
        if spec is None or spec.loader is None:
            msg = f"Failed to create module spec for {module_path}"
            raise ImportError(msg)

        module = importlib.util.module_from_spec(spec)
        sys.modules[entry_point] = module
        spec.loader.exec_module(module)

        return module

    async def _register_tools(self, module: Any, manifest: SkillManifest) -> None:
        """Register tools from skill module.

        Args:
            module: Loaded skill module
            manifest: Skill manifest

        Raises:
            ValueError: If tool registration fails

        """
        # Find tool classes in module
        for name in dir(module):
            obj = getattr(module, name)

            # Check if it's a Tool subclass
            if (
                isinstance(obj, type)
                and issubclass(obj, Tool)
                and obj is not Tool
                and hasattr(obj, "_tool_metadata")
            ):
                # Create tool instance
                tool_instance = obj()

                # Ensure tool is registered
                await tool_instance.ensure_registered()

    async def load_all_skills(self) -> list[SkillManifest]:
        """Load all skills from plugins directory.

        Returns:
            List of loaded skill manifests

        """
        if not self.plugins_dir.exists():
            return []

        loaded = []
        for skill_dir in self.plugins_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            try:
                manifest = await self.load_skill(skill_dir)
                loaded.append(manifest)
            except ValueError as e:
                # Log error but continue loading other skills
                _logger.warning("Failed to load skill from %s: %s", skill_dir, str(e))

        return loaded

    def get_loaded_skills(self) -> list[SkillManifest]:
        """Get list of loaded skills.

        Returns:
            List of loaded skill manifests

        """
        return list(self.loaded_skills.values())

    def is_skill_loaded(self, skill_id: str) -> bool:
        """Check if a skill is loaded.

        Args:
            skill_id: Skill ID to check

        Returns:
            True if skill is loaded

        """
        return skill_id in self.loaded_skills
