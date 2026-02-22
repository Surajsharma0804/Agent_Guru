"""
Skill discovery for finding and listing available skills.

Provides functionality to discover skills in the plugins directory.
"""

from pathlib import Path
from typing import List, Optional

from Agent_Guru.reasoning.tools.skills.manifest import (
    SkillManifest,
    SkillManifestParser,
)


class SkillDiscovery:
    """Discovery service for finding available skills."""

    def __init__(self, plugins_dir: Path):
        """Initialize skill discovery.

        Args:
            plugins_dir: Directory containing skill plugins
        """
        self.plugins_dir = Path(plugins_dir)

    def discover_skills(self) -> List[Path]:
        """Discover all skill directories.

        Returns:
            List of paths to skill directories
        """
        if not self.plugins_dir.exists():
            return []

        skill_dirs = []
        for item in self.plugins_dir.iterdir():
            if not item.is_dir():
                continue

            # Check if directory contains a manifest file
            if (item / "skill.yaml").exists() or (item / "skill.yml").exists():
                skill_dirs.append(item)

        return skill_dirs

    def get_skill_manifest(self, skill_dir: Path) -> Optional[SkillManifest]:
        """Get manifest for a skill directory.

        Args:
            skill_dir: Path to skill directory

        Returns:
            Skill manifest or None if not found/invalid
        """
        manifest_path = skill_dir / "skill.yaml"
        if not manifest_path.exists():
            manifest_path = skill_dir / "skill.yml"
            if not manifest_path.exists():
                return None

        try:
            return SkillManifestParser.parse_yaml(manifest_path)
        except Exception:
            return None

    def list_available_skills(self) -> List[SkillManifest]:
        """List all available skills with valid manifests.

        Returns:
            List of skill manifests
        """
        skill_dirs = self.discover_skills()
        manifests = []

        for skill_dir in skill_dirs:
            manifest = self.get_skill_manifest(skill_dir)
            if manifest:
                manifests.append(manifest)

        return manifests

    def find_skill_by_id(self, skill_id: str) -> Optional[Path]:
        """Find skill directory by skill ID.

        Args:
            skill_id: Skill ID to find

        Returns:
            Path to skill directory or None if not found
        """
        skill_dirs = self.discover_skills()

        for skill_dir in skill_dirs:
            manifest = self.get_skill_manifest(skill_dir)
            if manifest and manifest.skill_id == skill_id:
                return skill_dir

        return None
