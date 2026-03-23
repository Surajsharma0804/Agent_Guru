"""
Skill data models for the skill ecosystem.

Defines data structures for skills, permissions, and installed skills.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class Permission(str, Enum):
    """Permission types for skills."""

    NETWORK_ACCESS = "network_access"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    LOCATION_ACCESS = "location_access"
    CALENDAR_ACCESS = "calendar_access"
    CONTACTS_ACCESS = "contacts_access"
    SYSTEM_CONTROL = "system_control"


class TrustLevel(str, Enum):
    """Trust levels for skills."""

    TRUSTED = "trusted"  # Fully trusted, minimal restrictions
    RESTRICTED = "restricted"  # Limited trust, requires confirmations
    BLOCKED = "blocked"  # Not trusted, execution blocked


class SkillStatus(str, Enum):
    """Status of an installed skill."""

    ACTIVE = "active"  # Skill is active and can be used
    DISABLED = "disabled"  # Skill is disabled by user
    FAILED = "failed"  # Skill failed to load or execute
    UPDATING = "updating"  # Skill is being updated


class SkillManifestModel(BaseModel):
    """Skill manifest data model (extended from manifest.py)."""

    skill_id: str = Field(..., description="Unique skill identifier")
    version: str = Field(..., description="Skill version (semver)")
    name: str = Field(..., description="Human-readable skill name")
    description: str = Field(..., description="Skill description")
    author: str = Field(..., description="Skill author")
    capabilities: list[str] = Field(
        default_factory=list, description="Skill capabilities"
    )
    required_permissions: list[Permission] = Field(
        default_factory=list, description="Required permissions"
    )
    entry_points: dict[str, str] = Field(
        default_factory=dict, description="Entry points for tools"
    )
    max_latency: int = Field(
        default=5000, description="Maximum execution latency in ms"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="Required dependencies"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format (semver)."""
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError("Version must be in semver format (x.y.z)")
        if not all(part.isdigit() for part in parts):
            raise ValueError("Version parts must be numeric")
        return v

    @field_validator("max_latency")
    @classmethod
    def validate_max_latency(cls, v: int) -> int:
        """Validate max latency."""
        if v <= 0:
            raise ValueError("Max latency must be positive")
        if v > 60000:
            raise ValueError("Max latency cannot exceed 60 seconds")
        return v


class InstalledSkill(BaseModel):
    """Installed skill data model."""

    manifest: SkillManifestModel = Field(..., description="Skill manifest")
    status: SkillStatus = Field(
        default=SkillStatus.ACTIVE, description="Skill status"
    )
    trust_level: TrustLevel = Field(
        default=TrustLevel.RESTRICTED, description="Trust level"
    )
    granted_permissions: list[Permission] = Field(
        default_factory=list, description="Granted permissions"
    )
    install_date: datetime = Field(
        default_factory=datetime.now, description="Installation date"
    )
    last_used: Optional[datetime] = Field(
        None, description="Last usage timestamp"
    )
    usage_count: int = Field(default=0, description="Total usage count")
    success_rate: float = Field(default=1.0, description="Success rate (0.0-1.0)")

    @field_validator("success_rate")
    @classmethod
    def validate_success_rate(cls, v: float) -> float:
        """Validate success rate."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Success rate must be between 0.0 and 1.0")
        return v

    def has_permission(self, permission: Permission) -> bool:
        """Check if skill has a permission.

        Args:
            permission: Permission to check

        Returns:
            True if permission is granted
        """
        return permission in self.granted_permissions

    def grant_permission(self, permission: Permission) -> None:
        """Grant a permission to the skill.

        Args:
            permission: Permission to grant
        """
        if permission not in self.granted_permissions:
            self.granted_permissions.append(permission)

    def revoke_permission(self, permission: Permission) -> None:
        """Revoke a permission from the skill.

        Args:
            permission: Permission to revoke
        """
        if permission in self.granted_permissions:
            self.granted_permissions.remove(permission)

    def update_usage(self, success: bool) -> None:
        """Update usage statistics.

        Args:
            success: Whether the execution was successful
        """
        self.usage_count += 1
        self.last_used = datetime.now()

        # Update success rate with exponential moving average
        alpha = 0.1  # Smoothing factor
        new_value = 1.0 if success else 0.0
        self.success_rate = alpha * new_value + (1 - alpha) * self.success_rate
