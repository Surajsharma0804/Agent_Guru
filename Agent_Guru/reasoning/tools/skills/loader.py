"""
Skill loader for loading and registering third-party skills.

Handles skill discovery, validation, and registration with the tool registry.
"""

import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from Agent_Guru.reasoning.tools.base import Tool
from Agent_Guru.reasoning.tools.registry import get_registry
from Agent_Guru.reasoning.tools.skills.manifest import (
    SkillManifest,
    SkillManifestParser,
    SkillManifestValidator,
)


class SkillLoadError(Exception):
    """Exception raised when skill loading fails."""

    pass


class SkillLoader:
    """Loader for third-party skills."""

    def __init__(self, plugins_dir: Path):
        """Initialize skill loader.

        Args:
            plugins_dir: Directory containing skill plugins
        """
        self.plugins_dir = Path(plugins_dir)
        self.loaded_skills: Dict[str, SkillManifest] = {}
        self.registry = get_registry()

    async def load_skill(self, skill_dir: Path) -> SkillManifest:
        """Load a skill from a directory.

        Args:
            skill_dir: Directory containing skill

        Returns:
            Loaded skill manifest

        Raises:
            SkillLoadError: If loading fails
        """
        # Find manifest file
        manifest_path = skill_dir / "skill.yaml"
        if not manifest_path.exists():
            manifest_path = skill_dir / "skill.yml"
            if not manifest_path.exists():
                raise SkillLoadError(f"No manifest file found in {skill_dir}")

        # Parse manifest
        try:
            manifest = SkillManifestParser.parse_yaml(manifest_path)
        except ValueError as e:
            raise SkillLoadError(f"Failed to parse manifest: {str(e)}")

        # Validate manifest
        errors = SkillManifestValidator.validate(manifest)
        if errors:
            raise SkillLoadError(f"Manifest validation failed: {', '.join(errors)}")

        # Check if already loaded
        if manifest.skill_id in self.loaded_skills:
            raise SkillLoadError(f"Skill '{manifest.skill_id}' already loaded")

        # Load skill module
        try:
            module = self._load_module(skill_dir, manifest.entry_point)
        except Exception as e:
            raise SkillLoadError(f"Failed to load skill module: {str(e)}")

        # Register tools
        try:
            await self._register_tools(module, manifest)
        except Exception as e:
            raise SkillLoadError(f"Failed to register tools: {str(e)}")

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
            raise ImportError(f"Module file not found: {module_path}")

        # Load module
        spec = importlib.util.spec_from_file_location(entry_point, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Failed to create module spec for {module_path}")

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

    async def load_all_skills(self) -> List[SkillManifest]:
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
            except SkillLoadError as e:
                # Log error but continue loading other skills
                print(f"Failed to load skill from {skill_dir}: {str(e)}")

        return loaded

    def get_loaded_skills(self) -> List[SkillManifest]:
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
