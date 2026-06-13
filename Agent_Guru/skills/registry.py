"""Skill registry for discovery, installation, and conflict resolution."""

from __future__ import annotations

import logging

from Agent_Guru.skills.manifest import (
    InstallResult,
    SkillManifest,
    ValidationError,
)

logger = logging.getLogger(__name__)

_PRIORITY = {"user_installed": 2, "verified": 1, "unverified": 0}


def _skill_priority(manifest: SkillManifest) -> int:
    if manifest.user_installed:
        return _PRIORITY["user_installed"]
    if manifest.verified:
        return _PRIORITY["verified"]
    return _PRIORITY["unverified"]


class SkillRegistry:
    """Registry for managing skills: discover, install, validate, conflict resolution."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillManifest] = {}

    async def discover(self, source: str = "marketplace") -> list[SkillManifest]:
        """Discover available skills from a source."""
        return list(self._skills.values())

    def validate(self, manifest: SkillManifest) -> list[ValidationError]:
        """Validate a skill manifest. Returns list of errors (empty = valid)."""
        errors: list[ValidationError] = []
        if not manifest.skill_id:
            errors.append(ValidationError("skill_id", "skill_id is required"))
        if not manifest.name:
            errors.append(ValidationError("name", "name is required"))
        if not manifest.version:
            errors.append(ValidationError("version", "version is required"))
        if not manifest.entry_point:
            errors.append(ValidationError("entry_point", "entry_point is required"))
        if manifest.resource_limits.cpu_percent <= 0:
            errors.append(ValidationError("resource_limits.cpu_percent", "must be > 0"))
        if manifest.resource_limits.memory_mb <= 0:
            errors.append(ValidationError("resource_limits.memory_mb", "must be > 0"))
        if manifest.resource_limits.timeout_ms <= 0:
            errors.append(ValidationError("resource_limits.timeout_ms", "must be > 0"))
        return errors

    async def install(self, manifest: SkillManifest) -> InstallResult:
        """Install a skill after validation."""
        errors = self.validate(manifest)
        if errors:
            return InstallResult(
                success=False,
                skill_id=manifest.skill_id,
                error="; ".join(f"{e.field}: {e.message}" for e in errors),
            )
        existing = self._skills.get(manifest.skill_id)
        if existing is not None:
            resolved = self.resolve_conflict(existing, manifest)
            self._skills[manifest.skill_id] = resolved
        else:
            self._skills[manifest.skill_id] = manifest
        logger.info("Installed skill %s v%s", manifest.skill_id, manifest.version)
        return InstallResult(success=True, skill_id=manifest.skill_id, manifest=manifest)

    def resolve_conflict(self, a: SkillManifest, b: SkillManifest) -> SkillManifest:
        """Resolve conflict between two skills with same ID using priority."""
        if _skill_priority(b) >= _skill_priority(a):
            return b
        return a

    async def uninstall(self, skill_id: str) -> bool:
        """Uninstall a skill by ID."""
        if skill_id in self._skills:
            del self._skills[skill_id]
            logger.info("Uninstalled skill %s", skill_id)
            return True
        return False

    def get(self, skill_id: str) -> SkillManifest | None:
        return self._skills.get(skill_id)

    def list_skills(self) -> list[SkillManifest]:
        return list(self._skills.values())
