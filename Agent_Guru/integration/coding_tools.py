"""Work on a code project in the owner's folders: read it, try a change in the sandbox, apply it after a yes.

The assistant could run a snippet in the sandbox but not work on a
project: "fix the failing test in my budget app" had nowhere to start.
These tools give it the loop a coding agent needs, with the owner in it:

    project_files   list a project's files, or read one                    read-only
    project_git     git status, diff or log of the project                 read-only
    project_try     apply a unified diff to a COPY of the project inside
                    the WSL sandbox and run a command there (tests)        the owner says yes first
    project_apply   apply the same diff to the real files, keeping a
                    backup of every file it changes                        the owner says yes first

The real files change only through project_apply, after the owner hears
which files will change. A change is all or nothing (utils/patching.py):
a diff that does not fit changes no file. Tried changes run only in the
sandbox, so a test suite or a build step cannot reach anything else.
Projects must lie under FILES_ROOTS; .git, virtual environments, caches
and files the sensitive-file policy names are never read or copied.
Off unless AGENT_GURU_CODING_TOOLS is on; project_try also needs the
sandbox (python -m Agent_Guru sandbox setup).
"""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404 - git with fixed arguments
import time
from pathlib import Path
from typing import Any

from Agent_Guru.integration.mcp_tools import ServerConfig, ToolRisk, ToolRule
from Agent_Guru.utils.patching import PatchError, apply as apply_patch

SERVER_NAME = "code_project"
ENABLE_ENV = "AGENT_GURU_CODING_TOOLS"
_SKIP_DIRS = frozenset({".git", ".hg", ".venv", "venv", "env", "node_modules", "__pycache__", ".mypy_cache",
                        ".pytest_cache", ".ruff_cache", "dist", "build", ".tox", ".idea", ".vscode"})
MAX_FILE_BYTES = 512 * 1024
MAX_FILES = 2000
MAX_READ_CHARS = 12000
MAX_OUTPUT_CHARS = 4000


def enabled() -> bool:
    return os.environ.get(ENABLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def coding_server() -> ServerConfig:
    rules = {"project_files": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
             "project_git": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
             "project_try": ToolRule(allow=True, risk=ToolRisk.LOW_RISK_WRITE),
             "project_apply": ToolRule(allow=True, risk=ToolRisk.LOW_RISK_WRITE)}
    return ServerConfig(name=SERVER_NAME, command="(in process)", timeout=240.0, tools=rules)


def project_root(path_text: str) -> tuple[Path | None, str]:
    """(the project folder, "") when the assistant may work in *path_text*, else (None, why not)."""
    from Agent_Guru.connectors.tools import _roots
    from Agent_Guru.security.file_policy import sensitive_reason

    path = Path(os.path.expandvars(os.path.expanduser(path_text.strip().strip('"')))).resolve()
    if reason := sensitive_reason(path):
        return None, f"that folder is off limits ({reason})"
    if not any(path.is_relative_to(r.resolve()) for r in _roots()):
        return None, "only projects under the owner's folders (FILES_ROOTS) can be worked on"
    if not path.is_dir():
        return None, "no such folder"
    return path, ""


def project_files(root: Path) -> dict[str, Path]:
    """Relative name to path for every file the tools may see in *root*."""
    from Agent_Guru.security.file_policy import sensitive_reason

    found: dict[str, Path] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".tox"))
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if sensitive_reason(path) or path.stat().st_size > MAX_FILE_BYTES:
                continue
            found[path.relative_to(root).as_posix()] = path
            if len(found) >= MAX_FILES:
                return found
    return found


def _texts(files: dict[str, Path]) -> dict[str, str]:
    out = {}
    for name, path in files.items():
        try:
            out[name] = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary files are copied as they are, never patched
    return out


def _cut(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    text = text.strip()
    return text if len(text) <= limit else f"{text[:limit // 4]}\n[...]\n{text[-(limit * 3 // 4):]}"


class CodingTools:
    """The project tools (see the module docstring)."""

    def __init__(self, backups: Path | None = None) -> None:
        self._backups = backups

    def tool_list(self) -> list[dict[str, Any]]:
        if not enabled():
            return []
        path = {"type": "string", "minLength": 3, "maxLength": 500}
        diff = {"type": "string", "minLength": 10, "maxLength": 60000}
        tools = [
            {"name": "project_files", "description": "List the files of a code project in the owner's folders, or read one "
             "file (give file).", "annotations": {"readOnlyHint": True},
             "inputSchema": {"type": "object", "properties": {"path": path, "file": {"type": "string", "maxLength": 300}},
                             "required": ["path"], "additionalProperties": False}},
            {"name": "project_git", "description": "git status, diff or log of a project.", "annotations": {"readOnlyHint": True},
             "inputSchema": {"type": "object", "properties": {"path": path, "command": {"type": "string",
                             "enum": ["status", "diff", "log"]}}, "required": ["path", "command"], "additionalProperties": False}},
            {"name": "project_apply", "description": "Apply a unified diff (--- a/file, +++ b/file, @@ hunks) to the "
             "project's real files. Try it with project_try first. The owner confirms first.",
             "annotations": {"readOnlyHint": False}, "inputSchema": {"type": "object", "properties": {
                 "path": path, "patch": diff}, "required": ["path", "patch"], "additionalProperties": False}},
        ]
        from Agent_Guru.reasoning.tools.skills import wsl_sandbox

        if not wsl_sandbox.check():
            tools.insert(2, {"name": "project_try", "description": "Apply a unified diff to a copy of the project in an "
                             "isolated sandbox (no internet) and run a command there, for example "
                             "'python3 -m pytest -q'. The patch may be empty to run the command as it is. "
                             "The owner confirms first.",
                             "annotations": {"readOnlyHint": False, "openWorldHint": False},
                             "inputSchema": {"type": "object", "properties": {
                                 "path": path, "patch": {"type": "string", "maxLength": 60000},
                                 "command": {"type": "string", "minLength": 1, "maxLength": 500}},
                                 "required": ["path", "command"], "additionalProperties": False}})
        return tools

    def describe(self, tool: str, arguments: dict[str, Any]) -> str | None:
        root, _ = project_root(str(arguments.get("path", "")))
        where = root.name if root else "the project"
        if tool == "project_try":
            change = " with the proposed change" if str(arguments.get("patch", "")).strip() else ""
            return f"run '{str(arguments.get('command', ''))[:120]}' on a sandbox copy of {where}{change}"
        if tool == "project_apply" and root is not None:
            try:
                changed = apply_patch(_texts(project_files(root)), str(arguments.get("patch", "")))
            except PatchError:
                return None
            names = ", ".join(sorted(changed)[:6]) + (f" and {len(changed) - 6} more" if len(changed) > 6 else "")
            return f"change {len(changed)} file(s) in {where}: {names}"
        return None

    async def precheck(self, tool: str, arguments: dict[str, Any]) -> list[str]:
        root, why = project_root(str(arguments.get("path", "")))
        if root is None:
            return [why]
        if tool in ("project_try", "project_apply") and str(arguments.get("patch", "")).strip():
            try:
                apply_patch(_texts(project_files(root)), str(arguments["patch"]))
            except PatchError as exc:
                return [str(exc)]
        return []

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool, bool]:
        root, why = project_root(str(arguments.get("path", "")))
        if root is None:
            return f"Cannot work there: {why}.", True, False
        if name == "project_files":
            return self._files(root, str(arguments.get("file", "") or ""))
        if name == "project_git":
            return self._git(root, str(arguments.get("command", "")))
        if name == "project_try":
            return await self._try(root, str(arguments.get("patch", "") or ""), str(arguments.get("command", "")))
        if name == "project_apply":
            return self._apply(root, str(arguments.get("patch", "")))
        return f"unknown tool {name}", True, False

    @staticmethod
    def _files(root: Path, file: str) -> tuple[str, bool, bool]:
        files = project_files(root)
        if not file:
            listing = "\n".join(f"{n} ({p.stat().st_size} bytes)" for n, p in list(files.items())[:300])
            return f"{len(files)} files in {root.name}:\n{listing}", False, False
        path = files.get(file.replace("\\", "/").lstrip("./"))
        if path is None:
            return f"{file} is not a readable file of the project.", True, False
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"{file} is not a text file.", True, False
        return text[:MAX_READ_CHARS] + ("\n[cut]" if len(text) > MAX_READ_CHARS else ""), False, False

    @staticmethod
    def _git(root: Path, command: str) -> tuple[str, bool, bool]:
        git = shutil.which("git")
        if git is None:
            return "git is not installed.", True, False
        args = {"status": ["status", "--short", "--branch"], "diff": ["diff", "--stat", "--patch"],
                "log": ["log", "--oneline", "-20"]}.get(command)
        if args is None:
            return "Only status, diff and log.", True, False
        done = subprocess.run([git, "-C", str(root), *args], capture_output=True, text=True, timeout=30,  # nosec B603
                              check=False, stdin=subprocess.DEVNULL)
        if done.returncode != 0:
            return _cut(done.stderr) or "git failed", True, False
        return _cut(done.stdout) or "(nothing)", False, False

    async def _try(self, root: Path, patch: str, command: str) -> tuple[str, bool, bool]:
        from Agent_Guru.reasoning.tools.skills import wsl_sandbox

        files = project_files(root)
        texts = _texts(files)
        try:
            changed = apply_patch(texts, patch) if patch.strip() else {}
        except PatchError as exc:
            return f"The change does not apply: {exc}. Nothing was run.", True, False
        payload: dict[str, bytes] = {n: p.read_bytes() for n, p in files.items()}
        for name, text in changed.items():
            if text is None:
                payload.pop(name, None)
            else:
                payload[name] = text.encode("utf-8")
        run = await wsl_sandbox.run_project(payload, command)
        verdict = {"success": "passed (exit 0)", "exit-code": f"failed (exit {run.exit_code})",
                   "timeout": "was stopped at its time limit", "oom-kill": "ran out of memory",
                   "output-limit": "printed too much and was stopped"}.get(run.result, run.result)
        head = f"On a sandbox copy{' with the change' if changed else ''}, '{command}' {verdict} in {run.seconds:.1f} s."
        return f"{head}\n{_cut(run.stdout + chr(10) + run.stderr)}", run.result != "success", run.result != "unavailable"

    def _apply(self, root: Path, patch: str) -> tuple[str, bool, bool]:
        from Agent_Guru.utils.path_utils import app_data_dir

        files = project_files(root)
        try:
            changed = apply_patch(_texts(files), patch)
        except PatchError as exc:
            return f"The change does not apply: {exc}. No file was changed.", True, False
        backup = (self._backups or app_data_dir("project-backups", create=True)) / f"{root.name}-{time.strftime('%Y%m%d-%H%M%S')}"
        for name in changed:
            if name in files:
                target = backup / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(files[name], target)
        for name, text in changed.items():
            path = root / name
            if text is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
        # Read back: every file is what the diff said it would be.
        verified = all((not (root / n).exists()) if t is None else (root / n).read_text(encoding="utf-8") == t
                       for n, t in changed.items())
        return (f"Changed {len(changed)} file(s) in {root.name}: {', '.join(sorted(changed))}. "
                f"The old versions are in {backup}."), not verified, verified
