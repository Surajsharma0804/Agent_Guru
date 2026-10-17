"""Instruction skills: written know-how (a SKILL.md) the model can look up and follow.

Agent Guru's skills were code with a manifest; the public skill catalogs
(NousResearch's hermes-agent, the OpenClaw skills repository, any git
repository of SKILL.md folders) are instructions: a YAML front matter
with a name and a description, then how to do the task. Nothing could
read them.

    python -m Agent_Guru skills catalog hermes|openclaw|<git URL|folder>   list a catalog's skills
    python -m Agent_Guru skills learn <source> <name> [--yes]              install one

A catalog is fetched with the importer's quarantine (a shallow clone with
hooks off, no submodules). Only the skill's Markdown files are installed
(SKILL.md and the .md files beside it), under the data folder; scripts and
other files are named in the report and never copied, so nothing from a
catalog runs. Installed skills are offered to the model through the
read-only use_skill tool: its description lists them, and a call returns
the instructions, which pass the toolbox's guard as outside text.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from Agent_Guru.integration.mcp_tools import ServerConfig, ToolRisk, ToolRule

CATALOGS = {
    "hermes": "https://github.com/NousResearch/hermes-agent.git",
    # The skills live in the main repository: openclaw/skills, where the
    # reference project looked, answered "Repository not found" (2026-10-18).
    "openclaw": "https://github.com/openclaw/openclaw.git",
}
SERVER_NAME = "skills"
MAX_SKILL_CHARS = 20000
_MAX_LISTED = 15
_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


@dataclass(slots=True)
class SkillInfo:
    name: str
    description: str
    path: Path


def front_matter(text: str) -> tuple[dict[str, Any], str]:
    """(the YAML front matter, the body) of a SKILL.md; ({}, text) when it has none or it is not valid."""
    import yaml

    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", text, re.DOTALL)
    if not match:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}, text
    return (meta if isinstance(meta, dict) else {}), match.group(2)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")[:64]


def find_skills(root: Path) -> list[SkillInfo]:
    """Every SKILL.md under *root* with a name and a description."""
    found = []
    for path in sorted(root.rglob("SKILL.md")) + sorted(root.rglob("skill.md")):
        try:
            meta, _ = front_matter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        name, description = _slug(str(meta.get("name") or path.parent.name)), str(meta.get("description") or "").strip()
        if name and description and not any(s.name == name for s in found):
            found.append(SkillInfo(name, " ".join(description.split())[:300], path))
    return found


def _fetch(source: str, into: Path) -> Path:
    """The catalog's Markdown files in *into*, nothing else fetched or run.

    The importer's full clone failed on both public catalogs (git exit
    128): hermes-agent alone is 20,211 files, past its 120 s limit and,
    under the quarantine folder, past Windows' 260-character paths. Only
    *.md is needed, so this is a shallow, blob-less clone with a sparse
    checkout of Markdown, long paths on, hooks off and no submodules.
    """
    import subprocess  # nosec B404 - git with fixed arguments, the URL is one argument

    url = CATALOGS.get(source.lower(), source)
    if not re.match(r"^(https?|git)://|^git@", url):
        from Agent_Guru.reasoning.tools.skills.importer import _fetch as fetch

        return fetch(url, into)
    git = shutil.which("git")
    if git is None:
        msg = "git is not installed"
        raise ValueError(msg)
    target = into / "c"
    base = [git, "-c", "core.hooksPath=/dev/null", "-c", "protocol.file.allow=never", "-c", "core.longpaths=true"]
    steps = [
        [*base, "clone", "--depth", "1", "--filter=blob:none", "--no-checkout", "--no-recurse-submodules", "--", url, str(target)],
        [*base, "-C", str(target), "sparse-checkout", "set", "--no-cone", "*.md"],
        [*base, "-C", str(target), "checkout"],
    ]
    for step in steps:
        done = subprocess.run(step, capture_output=True, text=True, timeout=600, check=False,  # nosec B603
                              stdin=subprocess.DEVNULL)
        if done.returncode != 0:
            msg = f"git {step[len(base)] if step[len(base)] != '-C' else step[len(base) + 2]} failed: {done.stderr.strip()[-300:]}"
            raise ValueError(msg)
    shutil.rmtree(target / ".git", ignore_errors=True)
    return target


def catalog(source: str) -> list[SkillInfo]:
    """The skills in a catalog (hermes, openclaw, a git URL or a folder), fetched into a throwaway folder."""
    with tempfile.TemporaryDirectory(prefix="agent_guru_catalog_") as quarantine:
        skills = find_skills(_fetch(source, Path(quarantine)))
        # The files are gone with the folder; only the names and descriptions are kept.
        return [SkillInfo(s.name, s.description, Path(s.path.parent.name)) for s in skills]


def store() -> Path:
    from Agent_Guru.utils.path_utils import app_data_dir

    return app_data_dir("instruction_skills", create=True)


def learn(source: str, name: str, *, install: bool, into: Path | None = None) -> tuple[bool, list[str]]:
    """Install the skill *name* from *source* (only its .md files); (installed, report lines)."""
    from Agent_Guru.reasoning.tools.skills.importer import scan

    with tempfile.TemporaryDirectory(prefix="agent_guru_skill_") as quarantine:
        skills = {s.name: s for s in find_skills(_fetch(source, Path(quarantine)))}
        skill = skills.get(_slug(name))
        if skill is None:
            return False, [f"no skill named {name!r} in {source}; `skills catalog {source}` lists them"]
        folder = skill.path.parent
        markdown = sorted(p for p in folder.rglob("*.md") if p.is_file())
        others = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() and p.suffix.lower() != ".md")
        report = [f"{skill.name}: {skill.description}",
                  f"instructions: {', '.join(p.relative_to(folder).as_posix() for p in markdown)}"]
        if others:
            report.append(f"not copied (never run): {', '.join(others[:20])}")
        report += [f"note: {f}" for f in scan(folder) if any(f.startswith(m.relative_to(folder).as_posix()) for m in markdown)]
        if sum(len(p.read_text(encoding="utf-8", errors="replace")) for p in markdown) > MAX_SKILL_CHARS * 3:
            return False, [*report, "BLOCKED: the instructions are longer than 60,000 characters"]
        if not install:
            return False, [*report, "Not installed. Run again with --yes to install it."]
        target = (into or store()) / skill.name
        if target.exists():
            shutil.rmtree(target)
        for path in markdown:
            out = target / path.relative_to(folder)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        return True, [*report, f"Installed in {target}."]


def installed(root: Path | None = None) -> list[SkillInfo]:
    return find_skills(root or store())


def skills_server() -> ServerConfig:
    return ServerConfig(name=SERVER_NAME, command="(in process)", timeout=10.0,
                        tools={"use_skill": ToolRule(allow=True, risk=ToolRisk.READ_ONLY)})


class SkillTools:
    """use_skill: the instructions of one installed skill."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root

    def tool_list(self) -> list[dict[str, Any]]:
        skills = installed(self._root)
        if not skills:
            return []
        listed = "; ".join(f"{s.name}: {s.description[:100]}" for s in skills[:_MAX_LISTED])
        return [{"name": "use_skill", "description": "Read the instructions of an installed skill before doing that "
                 f"kind of task, then follow them. Installed: {listed}",
                 "annotations": {"readOnlyHint": True},
                 "inputSchema": {"type": "object", "properties": {"name": {"type": "string", "enum": [s.name for s in skills]}},
                                 "required": ["name"], "additionalProperties": False}}]

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool, bool]:
        if name != "use_skill":
            return f"unknown tool {name}", True, False
        skill = next((s for s in installed(self._root) if s.name == arguments.get("name")), None)
        if skill is None:
            return "No such skill is installed.", True, False
        _, body = front_matter(skill.path.read_text(encoding="utf-8"))
        extra = [p for p in sorted(skill.path.parent.rglob("*.md")) if p != skill.path]
        text = body.strip() + "".join(f"\n\n[{p.relative_to(skill.path.parent).as_posix()}]\n{p.read_text(encoding='utf-8')}"
                                      for p in extra)
        return text[:MAX_SKILL_CHARS], False, False
