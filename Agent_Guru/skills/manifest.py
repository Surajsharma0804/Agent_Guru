"""Skill manifest dataclasses and validation."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ResourceLimits:
    """Resource limits for skill execution."""
    cpu_percent: float = 10.0
    memory_mb: int = 128
    timeout_ms: int = 5000


@dataclass
class SkillManifest:
    """Manifest describing a skill's metadata and requirements."""
    skill_id: str
    name: str
    version: str
    intents: List[str]
    permissions: List[str]
    resource_limits: ResourceLimits
    entry_point: str
    description: str = ""
    author: str = ""
    verified: bool = False
    user_installed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "version": self.version,
            "intents": self.intents,
            "permissions": self.permissions,
            "resource_limits": {
                "cpu_percent": self.resource_limits.cpu_percent,
                "memory_mb": self.resource_limits.memory_mb,
                "timeout_ms": self.resource_limits.timeout_ms,
            },
            "entry_point": self.entry_point,
            "description": self.description,
            "author": self.author,
            "verified": self.verified,
            "user_installed": self.user_installed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SkillManifest:
        rl = data.get("resource_limits", {})
        return cls(
            skill_id=data["skill_id"],
            name=data["name"],
            version=data["version"],
            intents=data.get("intents", []),
            permissions=data.get("permissions", []),
            resource_limits=ResourceLimits(
                cpu_percent=rl.get("cpu_percent", 10.0),
                memory_mb=rl.get("memory_mb", 128),
                timeout_ms=rl.get("timeout_ms", 5000),
            ),
            entry_point=data["entry_point"],
            description=data.get("description", ""),
            author=data.get("author", ""),
            verified=data.get("verified", False),
            user_installed=data.get("user_installed", False),
        )

    def checksum(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()


@dataclass
class InstallResult:
    """Result of a skill installation."""
    success: bool
    skill_id: str
    error: Optional[str] = None
    manifest: Optional[SkillManifest] = None


@dataclass
class ValidationError:
    """Skill manifest validation error."""
    field: str
    message: str


@dataclass
class ResourceUsage:
    """Actual resource usage during skill execution."""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    wall_time_ms: float = 0.0


@dataclass
class SkillResult:
    """Result of skill execution."""
    success: bool
    skill_id: str
    output: Any = None
    error: Optional[str] = None
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)
