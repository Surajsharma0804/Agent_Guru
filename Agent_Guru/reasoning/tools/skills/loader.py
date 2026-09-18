"""Skill loader for loading and registering third-party skills.

Handles skill discovery, validation, and registration with the tool registry.
"""

import logging

_logger = logging.getLogger(__name__)

import importlib.util  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

from Agent_Guru.reasoning.error.error_manager import (  # noqa: E402
    ErrorContext,
    ErrorType,
    get_error_manager,
)
from Agent_Guru.reasoning.models.skill import TrustLevel  # noqa: E402
from Agent_Guru.reasoning.tools.base import Tool  # noqa: E402
from Agent_Guru.reasoning.tools.registry import get_registry  # noqa: E402
from Agent_Guru.reasoning.tools.skills.manifest import (  # noqa: E402
    SkillManifest,
    SkillManifestParser,
    SkillManifestValidator,
)
from Agent_Guru.reasoning.tools.skills.permissions import get_permission_manager  # noqa: E402
from Agent_Guru.reasoning.tools.skills.registry import get_skill_registry  # noqa: E402


class SkillLoader:
    """Loader for third-party skills."""

    def __init__(self, plugins_dir: Path) -> None:
        """Initialize skill loader.

        Args:
            plugins_dir: Directory containing skill plugins

        """
        self.plugins_dir = Path(plugins_dir)
        self.loaded_skills: dict[str, SkillManifest] = {}
        self.registry = get_registry()

    async def load_skill(self, skill_dir: Path) -> SkillManifest:
        """Load a skill from a directory.

        Args:
            skill_dir: Directory containing skill

        Returns:
            Loaded skill manifest

        Raises:
            ValueError: If loading fails (with user-friendly message)

        """
        error_manager = get_error_manager()

        # Find manifest file
        manifest_path = skill_dir / "skill.yaml"
        if not manifest_path.exists():
            manifest_path = skill_dir / "skill.yml"
            if not manifest_path.exists():
                context = ErrorContext(additional_data={"skill_dir": str(skill_dir)})
                error = error_manager.create_error(
                    error_type=ErrorType.TOOL_UNAVAILABLE,
                    message=f"No manifest file found in {skill_dir}",
                    context=context,
                )
                raise ValueError(error.user_message)

        # Parse manifest
        try:
            manifest = SkillManifestParser.parse_yaml(manifest_path)
        except ValueError as e:
            context = ErrorContext(additional_data={"manifest_path": str(manifest_path)})
            error = error_manager.create_error(
                error_type=ErrorType.MALFORMED_INPUT,
                message=f"Failed to parse manifest: {e!s}",
                context=context,
            )
            raise ValueError(error.user_message) from e

        # Validate manifest
        errors = SkillManifestValidator.validate(manifest)
        if errors:
            context = ErrorContext(additional_data={"validation_errors": errors})
            error = error_manager.create_error(
                error_type=ErrorType.PLAN_VALIDATION_FAILED,
                message=f"Manifest validation failed: {', '.join(errors)}",
                context=context,
            )
            raise ValueError(error.user_message)

        # Check if already loaded
        if manifest.skill_id in self.loaded_skills:
            context = ErrorContext(
                tool_id=manifest.skill_id,
            )
            error = error_manager.create_error(
                error_type=ErrorType.TOOL_UNAVAILABLE,
                message=f"Skill '{manifest.skill_id}' already loaded",
                context=context,
            )
            raise ValueError(error.user_message)

        # SECURITY FIX (Round 14): previously this method proceeded straight
        # from schema validation to importing and exec'ing the skill's
        # entry-point module in-process, with no reference anywhere to
        # SkillRegistry or PermissionManager -- the exact
        # install-time-consent and trust-level infrastructure this codebase
        # built specifically to gate third-party code execution. A bare
        # directory dropped into plugins_dir with nothing more than a
        # syntactically valid skill.yaml would have its Python entry point
        # imported and any Tool subclass silently registered into the live,
        # global tool registry -- no install step, no permission request,
        # no trust level ever consulted. A full-repository search confirmed
        # nothing in the live app calls this method today, but
        # reasoning/tools/selector.py already wires the sandboxed skill-tool
        # path (get_skill_tool_registry()) into live tool selection, so
        # this method is clearly meant to be connected the same way -- and
        # doing so without this gate would immediately reopen unauthenticated
        # arbitrary code execution. Require the skill to already be
        # registered (i.e. it went through SkillInstaller's manifest
        # validation + permission-request flow) and not BLOCKED at the
        # trust level before importing a single line of its code.
        if get_skill_registry().get_skill(manifest.skill_id) is None:
            context = ErrorContext(tool_id=manifest.skill_id)
            error = error_manager.create_error(
                error_type=ErrorType.PERMISSION_DENIED,
                message=(
                    f"Skill '{manifest.skill_id}' is not installed/registered -- "
                    "refusing to import unvetted third-party code"
                ),
                context=context,
            )
            raise ValueError(error.user_message)

        trust_level = get_permission_manager().get_trust_level(manifest.skill_id)
        if trust_level == TrustLevel.BLOCKED:
            context = ErrorContext(tool_id=manifest.skill_id)
            error = error_manager.create_error(
                error_type=ErrorType.PERMISSION_DENIED,
                message=f"Skill '{manifest.skill_id}' is blocked -- refusing to load",
                context=context,
            )
            raise ValueError(error.user_message)

        # Load skill module
        try:
            module = self._load_module(skill_dir, manifest.entry_point)
        except Exception as e:
            context = ErrorContext(
                tool_id=manifest.skill_id,
                additional_data={"entry_point": manifest.entry_point},
            )
            error = error_manager.create_error(
                error_type=ErrorType.TOOL_UNAVAILABLE,
                message=f"Failed to load skill module: {e!s}",
                context=context,
            )
            raise ValueError(error.user_message) from e

        # Register tools
        try:
            await self._register_tools(module, manifest)
        except Exception as e:
            context = ErrorContext(
                tool_id=manifest.skill_id,
            )
            error = error_manager.create_error(
                error_type=ErrorType.TOOL_UNAVAILABLE,
                message=f"Failed to register tools: {e!s}",
                context=context,
            )
            raise ValueError(error.user_message) from e

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
        # SECURITY FIX (Round 14): entry_point is untrusted data taken
        # straight from the skill's own manifest file. The old code built
        # `skill_dir / entry_point.replace(".", "/")` with plain path
        # arithmetic and no containment check -- only "." was neutralized,
        # so a manifest entry_point of e.g. "../../../etc/passwd" (or any
        # absolute path, which Path.__truediv__ happily accepts and
        # discards the left side of) would resolve module_path OUTSIDE
        # skill_dir entirely, and this method would still exec_module()
        # whatever Python file it found there. Fixed by resolving the
        # untrusted component through safe_path(), the same containment
        # helper already used for untrusted path input elsewhere in this
        # codebase (avatar/config.py, deployment/onboarding.py,
        # personality/engine.py).
        from Agent_Guru.utils.path_utils import safe_path

        module_path = safe_path(skill_dir, entry_point.replace(".", "/"))
        if module_path.is_dir():
            # module_path was already validated to be inside skill_dir;
            # appending a fixed, non-attacker-controlled filename cannot
            # escape it.
            module_path = module_path / "__init__.py"
        elif not module_path.suffix:
            module_path = module_path.with_suffix(".py")

        if not module_path.exists():
            msg = f"Module file not found: {module_path}"
            raise ImportError(msg)

        # Load module
        spec = importlib.util.spec_from_file_location(entry_point, module_path)
        if spec is None or spec.loader is None:
            msg = f"Failed to create module spec for {module_path}"
            raise ImportError(msg)

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

    async def load_all_skills(self) -> list[SkillManifest]:
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
            except ValueError as e:
                # Log error but continue loading other skills
                _logger.warning("Failed to load skill from %s: %s", skill_dir, str(e))

        return loaded

    def get_loaded_skills(self) -> list[SkillManifest]:
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
