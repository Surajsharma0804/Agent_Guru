"""Third-party skill plugin architecture.

This module provides infrastructure for loading, validating, and managing
third-party skills with manifest-based configuration.
"""

from Agent_Guru.reasoning.tools.skills.discovery import SkillDiscovery
from Agent_Guru.reasoning.tools.skills.loader import SkillLoader
from Agent_Guru.reasoning.tools.skills.manifest import (
    SkillManifest,
    SkillManifestParser,
    SkillManifestValidator,
)
from Agent_Guru.reasoning.tools.skills.metrics import SkillMetrics

__all__ = [
    "SkillDiscovery",
    "SkillLoader",
    "SkillManifest",
    "SkillManifestParser",
    "SkillManifestValidator",
    "SkillMetrics",
]
