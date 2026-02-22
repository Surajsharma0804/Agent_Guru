"""
Manifest generation helpers for skills.

Provides utilities to generate skill manifests from Skill classes.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from Agent_Guru.sdk.skill import Skill


class ManifestGenerator:
    """Generator for skill manifests."""

    @staticmethod
    def generate_from_skill(
        skill_class: Type[Skill],
        skill_id: str,
        version: str,
        name: str,
        description: str,
        author: str,
        required_permissions: Optional[List[str]] = None,
        max_latency: int = 5000,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate manifest from a Skill class.

        Args:
            skill_class: Skill class
            skill_id: Unique skill identifier
            version: Skill version
            name: Skill name
            description: Skill description
            author: Skill author
            required_permissions: Required permissions
            max_latency: Maximum latency in milliseconds
            dependencies: Python dependencies
            metadata: Additional metadata

        Returns:
            Manifest dictionary
        """
        # Create skill instance to discover capabilities
        skill_instance = skill_class()

        # Extract capabilities
        capabilities = []
        entry_points = {}

        for capability in skill_instance.get_capabilities():
            capabilities.append(capability)

            # Create entry point (Python code to execute capability)
            entry_points[capability] = (
                f"from {skill_class.__module__} import {skill_class.__name__}; "
                f"import asyncio; "
                f"import json; "
                f"import os; "
                f"skill = {skill_class.__name__}(); "
                f"params = json.loads(os.environ.get('SKILL_PARAMETERS', '{{}}')); "
                f"result = asyncio.run(skill.execute_capability('{capability}', **params)); "
                f"print(json.dumps(result))"
            )

        # Build manifest
        manifest = {
            "skill_id": skill_id,
            "version": version,
            "name": name,
            "description": description,
            "author": author,
            "capabilities": capabilities,
            "required_permissions": required_permissions or [],
            "entry_points": entry_points,
            "max_latency": max_latency,
            "dependencies": dependencies or [],
            "metadata": metadata or {},
        }

        return manifest

    @staticmethod
    def save_manifest(manifest: Dict[str, Any], output_path: Path) -> None:
        """Save manifest to file.

        Args:
            manifest: Manifest dictionary
            output_path: Output file path
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    @staticmethod
    def generate_and_save(
        skill_class: Type[Skill],
        output_path: Path,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate manifest from skill class and save to file.

        Args:
            skill_class: Skill class
            output_path: Output file path
            **kwargs: Arguments for generate_from_skill

        Returns:
            Generated manifest
        """
        manifest = ManifestGenerator.generate_from_skill(
            skill_class, **kwargs
        )
        ManifestGenerator.save_manifest(manifest, output_path)
        return manifest
