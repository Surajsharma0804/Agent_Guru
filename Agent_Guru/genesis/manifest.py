"""The component manifest: what an install can contain, and the rules it must follow.

components.json lists every component with its tier, its dependencies, its
measured size, where it comes from, how it is installed (an action id from
actions.ACTIONS), how it is checked (a probe id from verify.PROBES) and how it
is undone (an action id, or "not reversible"). validate() refuses a manifest
with a dangling id, a dependency cycle, a required component without a probe,
a package the lock does not pin, or a downloaded file without a real hash.
Sizes and hashes in the file were computed from the real artifacts; a size
nobody measured is null with an UNVERIFIED note, never a guess.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANIFEST_PATH = Path(__file__).resolve().parent / "components.json"

#: The eight stage nodes of the install screen, in order.
STAGES = ("Foundation", "Memory", "Intelligence", "Voice", "Awareness", "Capabilities", "Protection", "Awakening")
TIERS = ("core", "voice", "vision", "research", "browser", "coding")
PLATFORMS = ("windows", "linux", "darwin")
NOT_REVERSIBLE = "not reversible"
REQUIRED_FIELDS = ("id", "title", "stage", "tier", "required", "platforms", "depends_on", "size", "source",
                   "license", "probe", "install", "rollback", "reason")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._\-]*)==([^\s;#]+)")


@dataclass(frozen=True)
class Manifest:
    components: tuple[dict[str, Any], ...]

    @property
    def by_id(self) -> dict[str, dict[str, Any]]:
        return {c["id"]: c for c in self.components}

    def ids(self) -> list[str]:
        return [c["id"] for c in self.components]


def platform_key(platform: str, arch: str = "") -> str:
    """The key of a files_by_platform table: one build per chip on Linux and macOS."""
    chip = "arm64" if arch.lower() in ("arm64", "aarch64") else "x86_64" if arch.lower() in ("x86_64", "amd64") else arch.lower()
    return platform if platform == "windows" else f"{platform}-{chip}"


def files_for(component: dict[str, Any], platform: str, arch: str = "") -> list[dict[str, Any]]:
    """The pinned files this component takes on this machine."""
    table = component.get("files_by_platform")
    if table is not None:
        return list(table.get(platform_key(platform, arch), []))
    return list(component.get("files", []))


def packages_for(component: dict[str, Any], platform: str) -> list[str]:
    """The packages this component installs here: pywin32 and pycaw have no Linux or macOS wheels."""
    return [*component.get("packages", []), *component.get("platform_packages", {}).get(platform, [])]


def load(path: Path = MANIFEST_PATH) -> Manifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Manifest(tuple(raw["components"]))


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def lock_pins(lock_file: Path) -> dict[str, str]:
    """{normalised name: version} for every "name==version" line of the lock."""
    pins: dict[str, str] = {}
    for line in lock_file.read_text(encoding="utf-8").splitlines():
        m = _PIN.match(line.strip())
        if m:
            pins[normalise(m.group(1))] = m.group(2)
    return pins


def _cycle(components: dict[str, dict[str, Any]]) -> list[str]:
    """One dependency cycle as a list of ids, or [] when there is none."""
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(cid: str) -> list[str]:
        state[cid] = 1
        stack.append(cid)
        for dep in components[cid].get("depends_on", []):
            if dep not in components:
                continue
            if state.get(dep) == 1:
                return stack[stack.index(dep):] + [dep]
            if state.get(dep) is None:
                found = visit(dep)
                if found:
                    return found
        stack.pop()
        state[cid] = 2
        return []

    for cid in components:
        if state.get(cid) is None:
            found = visit(cid)
            if found:
                return found
    return []


def validate(manifest: Manifest, probe_ids: Iterable[str], action_ids: Iterable[str],
             pins: dict[str, str] | None = None) -> list[str]:
    """Every problem with the manifest; empty when it can be installed from."""
    probes, actions = set(probe_ids), set(action_ids)
    problems: list[str] = []
    seen: set[str] = set()
    by_id = manifest.by_id
    for c in manifest.components:
        cid = c.get("id", "?")
        missing = [f for f in REQUIRED_FIELDS if f not in c]
        if missing:
            problems.append(f"{cid}: missing {', '.join(missing)}")
            continue
        if cid in seen:
            problems.append(f"{cid}: listed twice")
        seen.add(cid)
        if c["stage"] not in STAGES:
            problems.append(f"{cid}: unknown stage {c['stage']!r}")
        if c["tier"] not in TIERS:
            problems.append(f"{cid}: unknown tier {c['tier']!r}")
        if not set(c["platforms"]) <= set(PLATFORMS) or not c["platforms"]:
            problems.append(f"{cid}: platforms must be some of {PLATFORMS}")
        if not c["probe"]:
            problems.append(f"{cid}: no verify probe" + (" on a required component" if c["required"] else ""))
        elif c["probe"] not in probes:
            problems.append(f"{cid}: probe {c['probe']!r} does not exist")
        if c["install"] not in actions:
            problems.append(f"{cid}: install action {c['install']!r} does not exist")
        if c["rollback"] != NOT_REVERSIBLE and c["rollback"] not in actions:
            problems.append(f"{cid}: rollback action {c['rollback']!r} does not exist")
        for dep in c["depends_on"]:
            if dep not in by_id:
                problems.append(f"{cid}: depends on {dep!r}, which is not in the manifest")
            elif c["required"] and not by_id[dep].get("required"):
                problems.append(f"{cid}: a required component depends on the optional {dep!r}")
        size = c["size"]
        for key in ("download_bytes", "disk_bytes"):
            value = size.get(key)
            if value is None and "UNVERIFIED" not in str(size.get("measured", "")):
                problems.append(f"{cid}: {key} is unknown but not marked UNVERIFIED")
            if value is not None and (not isinstance(value, int) or value < 0):
                problems.append(f"{cid}: {key} must be a byte count")
        everyone = [f for files in c.get("files_by_platform", {}).values() for f in files]
        for f in [*c.get("files", []), *everyone]:
            if not _SHA256.match(str(f.get("sha256", ""))):
                problems.append(f"{cid}: {f.get('name')} has no real SHA-256")
            if not isinstance(f.get("size"), int) or f["size"] <= 0:
                problems.append(f"{cid}: {f.get('name')} has no size")
            if not all(str(u).startswith("https://") for u in [f.get("url", ""), *f.get("mirrors", [])]):
                problems.append(f"{cid}: {f.get('name')} is not fetched over https")
        if c["install"] == "files.download" and not c.get("files"):
            problems.append(f"{cid}: a download component lists no files")
        if c["install"] == "pip.tier":
            if not c.get("packages"):
                problems.append(f"{cid}: a package component lists no packages")
            extras = [p for group in c.get("platform_packages", {}).values() for p in group]
            for pkg in [*c.get("packages", []), *extras]:
                if pins is not None and normalise(pkg) not in pins:
                    problems.append(f"{cid}: {pkg} is not pinned in requirements-lock.txt")
    cycle = _cycle({c["id"]: c for c in manifest.components if "id" in c})
    if cycle:
        problems.append("dependency cycle: " + " -> ".join(cycle))
    return problems


def order(manifest: Manifest, wanted: Iterable[str]) -> list[str]:
    """*wanted* plus everything they depend on, dependencies first, in manifest order otherwise."""
    by_id = manifest.by_id
    out: list[str] = []
    visiting: set[str] = set()

    def add(cid: str) -> None:
        if cid in out:
            return
        if cid in visiting:
            msg = f"dependency cycle through {cid}"
            raise ValueError(msg)
        visiting.add(cid)
        for dep in by_id[cid]["depends_on"]:
            add(dep)
        visiting.discard(cid)
        out.append(cid)

    wanted_set = set(wanted)
    for cid in manifest.ids():
        if cid in wanted_set:
            add(cid)
    return out
