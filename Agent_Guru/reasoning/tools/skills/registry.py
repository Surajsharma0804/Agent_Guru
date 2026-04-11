"""
Skill registry for managing installed skills.

Provides registration, discovery, and management of skills.
"""

import asyncio
from pathlib import Path
from typing import Optional

from Agent_Guru.reasoning.models.skill import (
    InstalledSkill,
    SkillManifestModel,
    SkillStatus,
)
from Agent_Guru.reasoning.tools.skills.manifest import (
    SkillManifest,
    SkillManifestValidator,
)


class SkillRegistry:
    """Registry for managing installed skills."""

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize skill registry.

        Args:
            storage_path: Path to persist registry data
        """
        self.storage_path = storage_path
        self.skills: dict[str, InstalledSkill] = {}
        self._lock = asyncio.Lock()

    async def register_skill(
        self, manifest: SkillManifest
    ) -> InstalledSkill:
        """Register a new skill.

        Args:
            manifest: Skill manifest

        Returns:
            Installed skill

        Raises:
            ValueError: If validation fails or skill already registered
        """
        async with self._lock:
            # Validate manifest
            errors = SkillManifestValidator.validate(manifest)
            if errors:
                raise ValueError(f"Manifest validation failed: {', '.join(errors)}")

            # Check if already registered
            if manifest.skill_id in self.skills:
                raise ValueError(f"Skill '{manifest.skill_id}' already registered")

            # Convert to model
            manifest_model = SkillManifestModel(
                skill_id=manifest.skill_id,
                version=manifest.version,
                name=manifest.name,
                description=manifest.description,
                author=manifest.author,
                capabilities=[],
                required_permissions=[],
                entry_points={},
                dependencies=manifest.dependencies,
            )

            # Create installed skill
            installed = InstalledSkill(last_used=datetime.now(tz=timezone.utc), manifest=manifest_model)
            self.skills[manifest.skill_id] = installed

            # Persist if storage path set
            if self.storage_path:
                await self._persist()

            return installed

    async def unregister_skill(self, skill_id: str) -> None:
        """Unregister a skill.

        Args:
            skill_id: Skill ID to unregister
        """
        async with self._lock:
            if skill_id in self.skills:
                del self.skills[skill_id]

                # Persist if storage path set
                if self.storage_path:
                    await self._persist()

    def get_skill(self, skill_id: str) -> Optional[InstalledSkill]:
        """Get an installed skill.

        Args:
            skill_id: Skill ID

        Returns:
            Installed skill or None if not found
        """
        return self.skills.get(skill_id)

    def list_skills(
        self, status: Optional[SkillStatus] = None
    ) -> list[InstalledSkill]:
        """List installed skills.

        Args:
            status: Filter by status (optional)

        Returns:
            List of installed skills
        """
        skills = list(self.skills.values())
        if status:
            skills = [s for s in skills if s.status == status]
        return skills

    def find_skills_by_capability(self, capability: str) -> list[InstalledSkill]:
        """Find skills by capability.

        Args:
            capability: Capability to search for

        Returns:
            List of matching skills
        """
        return [
            skill
            for skill in self.skills.values()
            if capability in skill.manifest.capabilities
            and skill.status == SkillStatus.ACTIVE
        ]

    async def update_skill(
        self, skill_id: str, status: Optional[SkillStatus] = None
    ) -> None:
        """Update skill properties.

        Args:
            skill_id: Skill ID
            status: New status (optional)
        """
        async with self._lock:
            skill = self.skills.get(skill_id)
            if not skill:
                raise ValueError(f"Skill '{skill_id}' not found")

            if status:
                skill.status = status

            # Persist if storage path set
            if self.storage_path:
                await self._persist()

    def validate_manifest(self, manifest: SkillManifest) -> list[str]:
        """Validate a skill manifest.

        Args:
            manifest: Manifest to validate

        Returns:
            List of validation errors (empty if valid)
        """
        return SkillManifestValidator.validate(manifest)

    async def _persist(self) -> None:
        """Persist registry to storage."""
        # Note: In a real implementation, this would save to database

    async def _load(self) -> None:
        """Load registry from storage."""
        # Note: In a real implementation, this would load from database


# Global registry instance
_global_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry instance.

    Returns:
        Global SkillRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry
