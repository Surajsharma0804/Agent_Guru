"""Skill manifest schema and validation.

Defines the structure and validation rules for skill manifests.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

class SkillManifest(BaseModel):
    """Skill manifest data model."""

    skill_id: str = Field(..., description="Unique skill identifier")
    name: str = Field(..., description="Human-readable skill name")
    version: str = Field(..., description="Skill version (semver)")
    author: str = Field(..., description="Skill author")
    description: str = Field(..., description="Skill description")
    permissions: list[str] = Field(default_factory=list, description="Required permissions")
    tools: list[dict[str, Any]] = Field(default_factory=list, description="Tool definitions")
    entry_point: str = Field(..., description="Entry point module path")
    runtime: str = Field(default="python", description="Runtime environment")
    dependencies: list[str] = Field(default_factory=list, description="Required dependencies")
    min_agent_version: str | None = Field(None, description="Minimum Agent_Guru version")
    max_agent_version: str | None = Field(None, description="Maximum Agent_Guru version")
    homepage: str | None = Field(None, description="Skill homepage URL")
    repository: str | None = Field(None, description="Source repository URL")
    license: str | None = Field(None, description="License identifier")
    tags: list[str] = Field(default_factory=list, description="Skill tags")

    @field_validator("skill_id")
    @classmethod
    def validate_skill_id(cls, v: str) -> str:
        """Validate skill ID format."""
        if not v or not v.strip():
            msg = "Skill ID cannot be empty"
            raise ValueError(msg)
        if not v.replace("_", "").replace("-", "").isalnum():
            msg = "Skill ID must be alphanumeric with _ or -"
            raise ValueError(msg)
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format (semver)."""
        parts = v.split(".")
        if len(parts) != 3:
            msg = "Version must be in semver format (x.y.z)"
            raise ValueError(msg)
        if not all(part.isdigit() for part in parts):
            msg = "Version parts must be numeric"
            raise ValueError(msg)
        return v

    @field_validator("runtime")
    @classmethod
    def validate_runtime(cls, v: str) -> str:
        """Validate runtime."""
        valid_runtimes = ["python", "nodejs", "docker"]
        if v not in valid_runtimes:
            msg = f"Runtime must be one of: {', '.join(valid_runtimes)}"
            raise ValueError(msg)
        return v

class SkillManifestParser:
    """Parser for skill manifest files."""

    @staticmethod
    def parse_yaml(file_path: Path) -> SkillManifest:
        """Parse skill manifest from YAML file.

        Args:
            file_path: Path to manifest file

        Returns:
            Parsed SkillManifest

        Raises:
            ValueError: If parsing fails

        """
        try:
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                msg = "Manifest file is empty"
                raise ValueError(msg)

            return SkillManifest(**data)

        except yaml.YAMLError as e:
            msg = f"Invalid YAML format: {e!s}"
            raise ValueError(msg) from e

    @staticmethod
    def parse_dict(data: dict[str, Any]) -> SkillManifest:
        """Parse skill manifest from dictionary.

        Args:
            data: Manifest data

        Returns:
            Parsed SkillManifest

        Raises:
            ValueError: If parsing fails

        """
        try:
            return SkillManifest(**data)
        except Exception as e:
            msg = f"Failed to parse manifest: {e!s}"
            raise ValueError(msg) from e

class SkillManifestValidator:
    """Validator for skill manifests."""

    @staticmethod
    def validate(manifest: SkillManifest) -> list[str]:
        """Validate skill manifest.

        Args:
            manifest: Manifest to validate

        Returns:
            List of validation errors (empty if valid)

        """
        errors = []

        # Validate required fields
        if not manifest.skill_id:
            errors.append("skill_id is required")
        if not manifest.name:
            errors.append("name is required")
        if not manifest.version:
            errors.append("version is required")
        if not manifest.author:
            errors.append("author is required")
        if not manifest.description:
            errors.append("description is required")
        if not manifest.entry_point:
            errors.append("entry_point is required")

        # Validate tools
        if not manifest.tools:
            errors.append("At least one tool must be defined")
        else:
            for i, tool in enumerate(manifest.tools):
                if "tool_id" not in tool:
                    errors.append(f"Tool {i}: tool_id is required")
                if "name" not in tool:
                    errors.append(f"Tool {i}: name is required")
                if "description" not in tool:
                    errors.append(f"Tool {i}: description is required")

        # Validate permissions
        valid_permissions = [
            "network_access",
            "file_read",
            "file_write",
            "system_control",
            "location_access",
            "calendar_access",
            "contacts_access",
        ]
        for permission in manifest.permissions:
            if permission not in valid_permissions:
                errors.append(
                    f"Invalid permission '{permission}'. "
                    f"Must be one of: {', '.join(valid_permissions)}",
                )

        return errors

    @staticmethod
    def validate_file(file_path: Path) -> list[str]:
        """Validate skill manifest file.

        Args:
            file_path: Path to manifest file

        Returns:
            List of validation errors (empty if valid)

        """
        try:
            manifest = SkillManifestParser.parse_yaml(file_path)
            return SkillManifestValidator.validate(manifest)
        except ValueError as e:
            return [str(e)]
