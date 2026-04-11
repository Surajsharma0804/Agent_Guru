import logging
_logger = logging.getLogger(__name__)
"""
Skill installer for managing skill installation, updates, and uninstallation.

Provides functionality to:
- Install skills from local files or marketplace
- Check for updates and notify users
- Uninstall skills with cleanup
- Track skill usage statistics
"""

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from Agent_Guru.reasoning.models.skill import (
    InstalledSkill,
    SkillStatus,
)
from Agent_Guru.reasoning.tools.skills.manifest import (
    SkillManifest,
    SkillManifestParser,
    SkillManifestValidator,
)
from Agent_Guru.reasoning.tools.skills.permissions import get_permission_manager
from Agent_Guru.reasoning.tools.skills.registry import get_skill_registry


@dataclass
class InstallResult:
    """Result of skill installation."""

    success: bool
    skill_id: Optional[str] = None
    error: Optional[str] = None
    warnings: list[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class UpdateInfo:
    """Information about available skill update."""

    skill_id: str
    current_version: str
    latest_version: str
    release_notes: str
    update_url: str


class SkillInstaller:
    """Manager for skill installation and updates."""

    def __init__(self, skills_dir: Optional[Path] = None):
        """Initialize skill installer.

        Args:
            skills_dir: Directory to install skills to
        """
        self.skills_dir = skills_dir or Path.home() / ".agent_guru" / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        self.registry = get_skill_registry()
        self.permission_manager = get_permission_manager()

        self._usage_stats: dict[str, dict] = {}
        self._load_usage_stats()

    async def install_skill(
        self,
        source: Path,
        user_id: str,
        auto_approve_permissions: bool = False,
    ) -> InstallResult:
        """Install a skill from local file or directory.

        Args:
            source: Path to skill manifest or skill directory
            user_id: User ID installing the skill
            auto_approve_permissions: Auto-approve all permissions

        Returns:
            Installation result
        """
        try:
            # Step 1: Load and validate manifest
            manifest = await self._load_manifest(source)
            if manifest is None:
                return InstallResult(
                    success=False,
                    error="Failed to load skill manifest",
                )

            # Validate manifest
            errors = SkillManifestValidator.validate(manifest)
            if errors:
                return InstallResult(
                    success=False,
                    error=f"Manifest validation failed: {', '.join(errors)}",
                )

            # Step 2: Check if already installed
            existing = self.registry.get_skill(manifest.skill_id)
            if existing:
                return InstallResult(
                    success=False,
                    error=f"Skill '{manifest.skill_id}' is already installed",
                    warnings=["Use update_skill() to update existing skill"],
                )

            # Step 3: Request permissions
            if not auto_approve_permissions:
                for permission in getattr(manifest, "required_permissions", []):
                    granted = await self.permission_manager.request_permission(
                        skill_id=manifest.skill_id,
                        permission=permission,
                        reason=f"Required by {manifest.name}",
                        auto_grant=False,
                    )

                    if not granted:
                        return InstallResult(
                            success=False,
                            error=f"Permission {permission.value} denied by user",
                        )

            # Step 4: Copy skill files to installation directory
            skill_install_dir = self.skills_dir / manifest.skill_id
            if source.is_dir():
                shutil.copytree(source, skill_install_dir, dirs_exist_ok=True)
            else:
                # Just copy manifest if source is a file
                skill_install_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy(source, skill_install_dir / "manifest.json")

            # Step 5: Register skill
            await self.registry.register_skill(manifest)

            # Step 6: Initialize usage stats
            self._usage_stats[manifest.skill_id] = {
                "install_date": datetime.now(tz=timezone.utc).isoformat(),
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "last_used": None,
            }
            await self._save_usage_stats()

            return InstallResult(
                success=True,
                skill_id=manifest.skill_id,
            )

        except Exception as e:
            return InstallResult(
                success=False,
                error=f"Installation failed: {str(e)}",
            )

    async def uninstall_skill(
        self, skill_id: str, cleanup_data: bool = True
    ) -> InstallResult:
        """Uninstall a skill.

        Args:
            skill_id: Skill ID to uninstall
            cleanup_data: Whether to cleanup skill data

        Returns:
            Uninstallation result
        """
        try:
            # Step 1: Check if skill exists
            skill = self.registry.get_skill(skill_id)
            if skill is None:
                return InstallResult(
                    success=False,
                    error=f"Skill '{skill_id}' not found",
                )

            # Step 2: Unregister skill
            await self.registry.unregister_skill(skill_id)

            # Step 3: Revoke all permissions
            granted_permissions = self.permission_manager.get_granted_permissions(
                skill_id
            )
            for permission in granted_permissions:
                await self.permission_manager.revoke_permission(skill_id, permission)

            # Step 4: Cleanup files
            skill_install_dir = self.skills_dir / skill_id
            if skill_install_dir.exists():
                shutil.rmtree(skill_install_dir)

            # Step 5: Cleanup usage stats
            if cleanup_data and skill_id in self._usage_stats:
                del self._usage_stats[skill_id]
                await self._save_usage_stats()

            return InstallResult(
                success=True,
                skill_id=skill_id,
            )

        except Exception as e:
            return InstallResult(
                success=False,
                error=f"Uninstallation failed: {str(e)}",
            )

    async def check_for_updates(
        self, skill_id: Optional[str] = None
    ) -> list[UpdateInfo]:
        """Check for available skill updates.

        Args:
            skill_id: Check specific skill (None = check all)

        Returns:
            List of available updates
        """
        updates: list[InstalledSkill] = []

        # Get skills to check
        if skill_id:
            skills = [self.registry.get_skill(skill_id)]
            if skills[0] is None:
                return []
        else:
            skills = self.registry.list_skills(status=SkillStatus.ACTIVE)

        # Check each skill for updates
        for _skill in skills:
            # In a real implementation, this would query a marketplace API
            # For now, return empty list (no updates available)
            pass

        return updates

    async def update_skill(
        self, skill_id: str, source: Optional[Path] = None
    ) -> InstallResult:
        """Update an installed skill.

        Args:
            skill_id: Skill ID to update
            source: Path to new version (None = download from marketplace)

        Returns:
            Update result
        """
        try:
            # Step 1: Check if skill exists
            existing = self.registry.get_skill(skill_id)
            if existing is None:
                return InstallResult(
                    success=False,
                    error=f"Skill '{skill_id}' not found",
                )

            # Step 2: Load new manifest
            if source is None:
                return InstallResult(
                    success=False,
                    error="Marketplace updates not yet implemented",
                    warnings=["Provide source path for manual update"],
                )

            manifest = await self._load_manifest(source)
            if manifest is None:
                return InstallResult(
                    success=False,
                    error="Failed to load new manifest",
                )

            # Step 3: Validate version is newer
            if manifest.version <= existing.manifest.version:
                return InstallResult(
                    success=False,
                    error=f"New version {manifest.version} is not newer than current {existing.manifest.version}",
                )

            # Step 4: Backup current version
            backup_dir = self.skills_dir / f"{skill_id}.backup"
            current_dir = self.skills_dir / skill_id
            if current_dir.exists():
                shutil.copytree(current_dir, backup_dir, dirs_exist_ok=True)

            try:
                # Step 5: Copy new files
                if source.is_dir():
                    shutil.copytree(source, current_dir, dirs_exist_ok=True)
                else:
                    shutil.copy(source, current_dir / "manifest.json")

                # Step 6: Update registry
                await self.registry.unregister_skill(skill_id)
                await self.registry.register_skill(manifest)

                # Step 7: Cleanup backup
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)

                return InstallResult(
                    success=True,
                    skill_id=skill_id,
                )

            except Exception as e:
                # Rollback on failure
                if backup_dir.exists():
                    if current_dir.exists():
                        shutil.rmtree(current_dir)
                    shutil.copytree(backup_dir, current_dir)
                    shutil.rmtree(backup_dir)

                raise e

        except Exception as e:
            return InstallResult(
                success=False,
                error=f"Update failed: {str(e)}",
            )

    async def record_execution(
        self, skill_id: str, success: bool
    ) -> None:
        """Record skill execution for usage statistics.

        Args:
            skill_id: Skill ID
            success: Whether execution succeeded
        """
        if skill_id not in self._usage_stats:
            self._usage_stats[skill_id] = {
                "install_date": datetime.now(tz=timezone.utc).isoformat(),
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "last_used": None,
            }

        stats = self._usage_stats[skill_id]
        stats["total_executions"] += 1
        stats["last_used"] = datetime.now(tz=timezone.utc).isoformat()

        if success:
            stats["successful_executions"] += 1
        else:
            stats["failed_executions"] += 1

        await self._save_usage_stats()

    def get_usage_stats(self, skill_id: str) -> Optional[dict]:
        """Get usage statistics for a skill.

        Args:
            skill_id: Skill ID

        Returns:
            Usage statistics or None if not found
        """
        return self._usage_stats.get(skill_id)

    async def _load_manifest(self, source: Path) -> Optional[SkillManifest]:
        """Load skill manifest from source.

        Args:
            source: Path to manifest file or skill directory

        Returns:
            Parsed manifest or None if failed
        """
        try:
            # Find manifest file
            if source.is_dir():
                manifest_path = source / "manifest.json"
            else:
                manifest_path = source

            if not manifest_path.exists():
                return None

            # Parse manifest
            with open(manifest_path, encoding="utf-8") as f:
                json.load(f)

            return SkillManifestParser().parse  # type: ignore[attr-defined](manifest_data)

        except Exception as e:
            _logger.warning("Failed to load manifest: %s", e)
            return None

    async def _save_usage_stats(self) -> None:
        """Save usage statistics to disk."""
        stats_path = self.skills_dir / "usage_stats.json"
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(self._usage_stats, f, indent=2)

    def _load_usage_stats(self) -> None:
        """Load usage statistics from disk."""
        stats_path = self.skills_dir / "usage_stats.json"
        if stats_path.exists():
            try:
                with open(stats_path, encoding="utf-8") as f:
                    self._usage_stats = json.load(f)
            except Exception as e:
                _logger.warning("Failed to load usage stats: %s", e)
                self._usage_stats = {}
        else:
            self._usage_stats = {}


# Global installer instance
_global_installer: Optional[SkillInstaller] = None


def get_skill_installer() -> SkillInstaller:
    """Get the global skill installer instance.

    Returns:
        Global SkillInstaller instance
    """
    global _global_installer
    if _global_installer is None:
        _global_installer = SkillInstaller()
    return _global_installer
