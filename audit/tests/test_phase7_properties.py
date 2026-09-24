"""Property-based tests for Phase 7: Code quality - layer violations.

Task 10.9 - Property 19.

Property 19: Layer Violation Detection
    Any import in llm/, memory/, or reasoning/ referencing platform/ or
    deployment/ produces a finding.
    Imports that do not cross this boundary produce no finding.

    One exception, stated here and enforced by detect_layer_violations
    rather than left to per-line markers: a FUNCTION-SCOPED import of
    Agent_Guru.platform from a module under reasoning/tools/ is allowed.
    See TOOL_ADAPTER_PREFIX for why.

Subsystem: audit/tests
Requirements: 7.11
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Layer violation detector. This file is the rule's only implementation;
# nothing under audit/phases/ carries a copy of it.
# ---------------------------------------------------------------------------

# Modules that must NOT import from the platform or deployment layers
RESTRICTED_IMPORTERS = {"llm", "memory", "reasoning"}

# Layers that are off-limits for the restricted importer modules
FORBIDDEN_TARGETS = {"platform", "deployment"}

# reasoning/tools/ holds the tools the LLM agent calls to act on the machine:
# open an app, send a message, search the web. Their execute() methods exist
# to delegate to the one real implementation of that action in platform/.
# Every such delegation that the rule flagged was once a placeholder that
# returned success without doing anything, and was fixed by delegating
# instead of writing a second implementation, which this project forbids.
#
# The rule protects two things, and neither is at stake for these imports:
#   - Import-time isolation. The imports are function-scoped, so importing
#     any reasoning module, tools included, loads no Agent_Guru.platform
#     module. That is verified, not assumed; see
#     test_importing_tool_adapters_loads_no_platform_module.
#   - Dependency direction. platform/ imports nothing from reasoning/, so
#     there is no cycle to break.
# A reasoning-owned interface would not remove the dependency, only move who
# supplies it. Tools are constructed with no arguments and looked up through a
# global registry, so there is no composition root to inject an
# implementation from; each entry point would have to register one, and one
# that forgot would get tools that fail at runtime, the failure these
# delegations were written to end.
#
# So the exception is narrow and checked: platform only (a tool has no
# business with deployment/), function scope only (a module-level import in
# reasoning/tools/ is still a violation), and reasoning/tools/ only (the
# reasoning core, llm/ and memory/ stay under the full rule). Before this was
# stated here, the same imports needed a "# layer-exempt" comment on the line,
# which the detector trusts without checking that the import is lazy, and four
# of them lacked one, so the codebase audit failed on correct code.
TOOL_ADAPTER_PREFIX = "Agent_Guru/reasoning/tools/"


def _module_layer(file_path: str) -> str | None:
    """Return the top-level layer name for a module path.

    Strips the 'Agent_Guru/' prefix and returns the first path component.

    Examples:
        'Agent_Guru/llm/runtime.py'  → 'llm'
        'Agent_Guru/memory/store.py' → 'memory'
        'Agent_Guru/platform/os.py'  → 'platform'
    """
    normalized = file_path.replace("\\", "/")
    # Strip leading Agent_Guru/ prefix
    if normalized.startswith("Agent_Guru/"):
        normalized = normalized[len("Agent_Guru/"):]
    parts = normalized.split("/")
    return parts[0] if parts else None


def _is_lazy_import_line(node: ast.AST, source_lines: list[str]) -> bool:
    """Return True if this import has a # layer-exempt or # noqa: PLC0415 marker.

    Lazy imports that are intentionally inside functions to avoid module-level
    layer crossing are annotated with:
        # layer-exempt: <reason>
    or (for backwards compatibility):
        # noqa: PLC0415

    These are accepted architectural patterns for optional dependencies and
    cross-layer utilities that are only needed at runtime.
    """
    lineno = getattr(node, "lineno", None)
    if lineno is None or lineno > len(source_lines):
        return False
    line = source_lines[lineno - 1]  # lineno is 1-indexed
    return "layer-exempt" in line or "PLC0415" in line


def detect_layer_violations(
    source_file: str,
    source_code: str,
) -> list[str]:
    """Return list of layer violation descriptions found in source_code.

    A violation occurs when a module in RESTRICTED_IMPORTERS imports
    anything from Agent_Guru.platform or Agent_Guru.deployment (the internal
    layers), not from the stdlib 'platform' module.

    Args:
        source_file: Relative file path (used to determine source layer).
        source_code: Python source code to analyse.

    Returns:
        List of violation strings, empty if no violations.
    """
    source_layer = _module_layer(source_file)
    if source_layer not in RESTRICTED_IMPORTERS:
        return []  # Not a restricted layer - no check needed

    violations: list[str] = []
    try:
        tree = ast.parse(textwrap.dedent(source_code))
    except SyntaxError:
        return []

    source_lines = source_code.splitlines()
    is_tool_adapter = source_file.replace("\\", "/").startswith(TOOL_ADAPTER_PREFIX)
    function_scoped = {
        id(inner)
        for fn in ast.walk(tree)
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
        for inner in ast.walk(fn)
        if isinstance(inner, (ast.Import, ast.ImportFrom))
    }

    def allowed(node: ast.AST, module_name: str) -> bool:
        if _is_lazy_import_line(node, source_lines):
            return True
        return (
            is_tool_adapter
            and id(node) in function_scoped
            and _target_layer(module_name) == "platform"
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_internal_layer_import(alias.name) and not allowed(node, alias.name):
                    violations.append(
                        f"{source_file}: 'import {alias.name}' crosses "
                        f"layer boundary ({source_layer} → {_target_layer(alias.name)})"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module and _is_internal_layer_import(node.module) and not allowed(node, node.module):
                violations.append(
                    f"{source_file}: 'from {node.module} import ...' crosses "
                    f"layer boundary ({source_layer} → {_target_layer(node.module)})"
                )

    return violations


def _target_layer(module_name: str) -> str:
    """Return the internal layer a forbidden import targets.

    The report used to name the first dotted component, which for every
    Agent_Guru.platform import is "Agent_Guru", so each finding read
    "reasoning → Agent_Guru" and did not say which boundary was crossed.
    """
    if module_name.startswith("Agent_Guru."):
        return _first_component(module_name[len("Agent_Guru."):])
    return _first_component(module_name)


def _is_internal_layer_import(module_name: str) -> bool:
    """Return True if module_name refers to an internal Agent_Guru forbidden layer.

    We flag imports that start with 'Agent_Guru.platform', 'Agent_Guru.deployment',
    or that are bare 'deployment' (not stdlib) - but NOT the stdlib 'platform' module.
    """
    first = _first_component(module_name)
    # 'platform' alone is the Python stdlib module - never a layer violation
    if module_name == "platform":
        return False
    # Agent_Guru.platform.* or Agent_Guru.deployment.* are forbidden targets
    if module_name.startswith("Agent_Guru."):
        inner = module_name[len("Agent_Guru."):]
        return _first_component(inner) in FORBIDDEN_TARGETS
    # Bare 'deployment' (not 'platform' which is stdlib) is also a violation
    return first == "deployment"


def _first_component(dotted_name: str) -> str:
    """Return the first component of a dotted module name.

    Examples:
        'platform.os_controller' → 'platform'
        'Agent_Guru.deployment' → 'Agent_Guru'  (outer package)
        'deployment'            → 'deployment'
    """
    return dotted_name.split(".")[0]


# ===========================================================================
# Property 19: Layer Violation Detection
# ===========================================================================


class TestLayerViolationDetectionProperty19:
    """Property 19 - cross-boundary imports produce a finding; valid imports do not."""

    # ── Positive cases: violations should be detected ──────────────────────

    def test_llm_importing_agent_guru_platform_is_violation(self) -> None:
        source = "from Agent_Guru.platform import controller"
        violations = detect_layer_violations("Agent_Guru/llm/runtime.py", source)
        assert len(violations) >= 1

    def test_memory_importing_agent_guru_deployment_is_violation(self) -> None:
        source = "from Agent_Guru.deployment import installer"
        violations = detect_layer_violations("Agent_Guru/memory/store.py", source)
        assert len(violations) >= 1

    def test_reasoning_importing_bare_deployment_is_violation(self) -> None:
        source = "import deployment"
        violations = detect_layer_violations("Agent_Guru/reasoning/engine.py", source)
        assert len(violations) >= 1

    def test_llm_importing_agent_guru_deployment_dotted_is_violation(self) -> None:
        source = "import Agent_Guru.deployment.installer_builder"
        violations = detect_layer_violations("Agent_Guru/llm/runtime.py", source)
        assert len(violations) >= 1

    def test_stdlib_platform_not_a_violation(self) -> None:
        """The Python stdlib 'platform' module is not a layer violation."""
        source = "import platform\nx = platform.system()"
        violations = detect_layer_violations("Agent_Guru/llm/runtime.py", source)
        assert violations == [], "stdlib 'platform' must not be flagged"

    # ── Negative cases: non-violations should not produce findings ─────────

    def test_llm_importing_asyncio_no_violation(self) -> None:
        source = "import asyncio"
        violations = detect_layer_violations("Agent_Guru/llm/runtime.py", source)
        assert violations == []

    def test_llm_importing_memory_no_violation(self) -> None:
        # memory → llm would be a violation, but llm → memory is allowed
        source = "from memory.store import ConversationStore"
        violations = detect_layer_violations("Agent_Guru/llm/runtime.py", source)
        assert violations == []

    def test_speech_importing_platform_no_violation(self) -> None:
        # speech is not a restricted layer
        source = "import platform"
        violations = detect_layer_violations("Agent_Guru/speech/tts.py", source)
        assert violations == []

    def test_platform_importing_platform_no_violation(self) -> None:
        # platform layer importing itself is OK
        source = "from platform.base import BaseController"
        violations = detect_layer_violations("Agent_Guru/platform/windows.py", source)
        assert violations == []

    def test_clean_llm_file_no_violation(self) -> None:
        source = """
        import asyncio
        from pathlib import Path
        from typing import Optional
        from llm.router import ModelRouter
        from memory.cache import ResponseCache
        class LLMRuntime:
            async def generate(self, prompt: str) -> str:
                return "response"
        """
        violations = detect_layer_violations("Agent_Guru/llm/runtime.py", source)
        assert violations == []

    def test_syntax_error_returns_empty(self) -> None:
        violations = detect_layer_violations(
            "Agent_Guru/llm/runtime.py", "def broken(:"
        )
        assert violations == []

    def test_non_restricted_layer_never_violations(self) -> None:
        source = "import platform\nimport deployment"
        for layer in ["speech", "vision", "avatar", "agents", "core"]:
            violations = detect_layer_violations(
                f"Agent_Guru/{layer}/module.py", source
            )
            assert violations == [], f"{layer} should not be checked for layer violations"

    # ── The reasoning/tools/ adapter exception, and its limits ────────────

    _LAZY_PLATFORM = """
        async def execute(self):
            from Agent_Guru.platform.features.web_search import search_web
            return await search_web("q")
        """

    def test_tool_adapter_function_scoped_platform_import_allowed(self) -> None:
        violations = detect_layer_violations(
            "Agent_Guru/reasoning/tools/knowledge/web_search.py", self._LAZY_PLATFORM
        )
        assert violations == []

    def test_tool_adapter_module_level_platform_import_still_flagged(self) -> None:
        source = "from Agent_Guru.platform.features.web_search import search_web"
        violations = detect_layer_violations(
            "Agent_Guru/reasoning/tools/knowledge/web_search.py", source
        )
        assert len(violations) == 1
        assert "reasoning → platform" in violations[0]

    def test_tool_adapter_function_scoped_deployment_import_still_flagged(self) -> None:
        source = """
        def execute(self):
            from Agent_Guru.deployment import installer
        """
        violations = detect_layer_violations(
            "Agent_Guru/reasoning/tools/system/app_control.py", source
        )
        assert len(violations) == 1

    def test_reasoning_core_function_scoped_platform_import_still_flagged(self) -> None:
        # The exception is for the tool adapters, not for the reasoning core.
        violations = detect_layer_violations(
            "Agent_Guru/reasoning/engine.py", self._LAZY_PLATFORM
        )
        assert len(violations) == 1

    @given(
        source_file=st.sampled_from([
            "Agent_Guru/reasoning/engine.py",
            "Agent_Guru/reasoning/intent/engine.py",
            "Agent_Guru/reasoning/tools/external/messaging.py",
            "Agent_Guru/reasoning/tools/knowledge/information.py",
            "Agent_Guru/llm/runtime.py",
            "Agent_Guru/memory/store.py",
        ]),
        target_module=st.sampled_from([
            "Agent_Guru.platform",
            "Agent_Guru.platform.os_controller",
            "Agent_Guru.platform.controllers.messaging_controller",
            "Agent_Guru.deployment.installer",
        ]),
        lazy=st.booleans(),
    )
    @settings(max_examples=100)
    def test_property_19_exception_is_exactly_lazy_platform_from_tools(
        self, source_file: str, target_module: str, lazy: bool
    ) -> None:
        """Only a function-scoped platform import from reasoning/tools/ escapes."""
        statement = f"import {target_module}"
        source = f"def run():\n    {statement}\n" if lazy else statement
        violations = detect_layer_violations(source_file, source)
        exempt = (
            lazy
            and source_file.startswith(TOOL_ADAPTER_PREFIX)
            and target_module.startswith("Agent_Guru.platform")
        )
        assert (violations == []) == exempt, (source_file, target_module, lazy, violations)

    # ── Property 19: Hypothesis property ──────────────────────────────────

    @given(
        source_layer=st.sampled_from(sorted(RESTRICTED_IMPORTERS)),
        target_module=st.sampled_from([
            "Agent_Guru.platform",
            "Agent_Guru.deployment",
            "Agent_Guru.platform.os_controller",
            "Agent_Guru.deployment.installer",
            "deployment",   # bare deployment (not stdlib)
        ]),
    )
    @settings(max_examples=100)
    def test_property_19_restricted_importing_forbidden_always_flagged(
        self, source_layer: str, target_module: str
    ) -> None:
        """Property 19: any restricted→forbidden import produces a violation."""
        source = f"import {target_module}"
        violations = detect_layer_violations(
            f"Agent_Guru/{source_layer}/module.py", source
        )
        assert len(violations) >= 1, (
            f"{source_layer} importing {target_module} should be flagged"
        )

    @given(
        source_layer=st.sampled_from(sorted(RESTRICTED_IMPORTERS)),
        safe_module=st.sampled_from(["asyncio", "pathlib", "json", "typing",
                                     "collections", "hashlib", "structlog"]),
    )
    @settings(max_examples=100)
    def test_property_19_stdlib_imports_never_flagged(
        self, source_layer: str, safe_module: str
    ) -> None:
        """Standard library imports are never a layer violation."""
        source = f"import {safe_module}"
        violations = detect_layer_violations(
            f"Agent_Guru/{source_layer}/module.py", source
        )
        assert violations == []


# ---------------------------------------------------------------------------
# Task 10.9 also covers verifying the actual codebase has no violations.
# This is run as a slow integration-style test.
# ---------------------------------------------------------------------------


class TestActualCodebaseLayerViolations:
    """Scan the real Agent_Guru/ directory for layer violations."""

    def test_no_layer_violations_in_codebase(self, repo_root: Path) -> None:
        """All llm/, memory/, reasoning/ files must not import Agent_Guru.platform or deployment."""
        package_root = repo_root / "Agent_Guru"
        if not package_root.exists():
            return  # Skip in isolated test environments

        violations: list[str] = []

        for py_file in package_root.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            try:
                rel_path = py_file.relative_to(repo_root)
                # Normalize to forward slashes for cross-platform consistency
                rel_path_str = str(rel_path).replace("\\", "/")
                source = py_file.read_text(encoding="utf-8", errors="replace")
                file_violations = detect_layer_violations(rel_path_str, source)
                violations.extend(file_violations)
            except (OSError, ValueError):
                continue

        assert violations == [], (
            f"Found {len(violations)} layer violations:\n"
            + "\n".join(f"  - {v}" for v in violations[:20])
        )

    def test_importing_tool_adapters_loads_no_platform_module(self, repo_root: Path) -> None:
        """The adapter exception rests on this: lazy means platform stays unloaded.

        The adapter modules are discovered, not listed, so a new tool that
        leans on the exception is covered by this check automatically.
        """
        import subprocess
        import sys

        tools_root = repo_root / TOOL_ADAPTER_PREFIX
        adapters = []
        for py_file in sorted(tools_root.rglob("*.py")):
            if "tests" in py_file.parts or "__pycache__" in py_file.parts:
                continue
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            if any(
                isinstance(node, ast.ImportFrom)
                and (node.module or "").startswith("Agent_Guru.platform")
                for node in ast.walk(tree)
            ):
                rel = py_file.relative_to(repo_root).with_suffix("")
                adapters.append(".".join(rel.parts))
        assert adapters, "no reasoning/tools/ module imports platform; drop the exception"

        script = (
            "import importlib, sys\n"
            f"for name in {adapters!r}:\n"
            "    importlib.import_module(name)\n"
            "loaded = sorted(m for m in sys.modules if m.startswith('Agent_Guru.platform'))\n"
            "print(loaded)\n"
            "sys.exit(1 if loaded else 0)\n"
        )
        result = subprocess.run(  # noqa: S603  # nosec B603
            [sys.executable, "-c", script],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
        assert result.returncode == 0, (
            f"importing {adapters} loaded platform modules: {result.stdout}{result.stderr}"
        )
