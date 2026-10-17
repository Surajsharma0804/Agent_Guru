"""Apply a unified diff to files held in memory, all or nothing.

The coding tools (integration/coding_tools.py) let the model propose a
change as a unified diff: tried first on a copy in the sandbox, written
to the owner's files only after a yes. Both need the same answer to
"what would these files be after this diff?", without git or patch
installed and without touching disk, so it is computed here.

Strict on purpose: every context and removed line must match the file
(trailing whitespace aside); a hunk may sit up to 50 lines from where
its header says, since models count lines badly, but nowhere else. A
diff that does not fit raises PatchError naming the file and hunk, and
nothing is changed, so a half-applied edit never reaches a file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_SEARCH = 50


class PatchError(ValueError):
    """The diff does not apply; nothing was changed."""


@dataclass(slots=True)
class FilePatch:
    old: str | None  # None: the file is created
    new: str | None  # None: the file is deleted
    hunks: list[tuple[int, list[str]]] = field(default_factory=list)


def _name(header: str) -> str | None:
    path = header.split("\t", 1)[0].strip()
    if path == "/dev/null":
        return None
    return re.sub(r"^[ab]/", "", path)


def parse(diff: str) -> list[FilePatch]:
    """The files and hunks in *diff*; raises PatchError for a diff with none."""
    lines = diff.replace("\r\n", "\n").split("\n")
    patches: list[FilePatch] = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            patch = FilePatch(_name(lines[i][4:]), _name(lines[i + 1][4:]))
            if patch.old is None and patch.new is None:
                msg = "a file goes from nothing to nothing"
                raise PatchError(msg)
            patches.append(patch)
            i += 2
            continue
        match = _HUNK.match(lines[i])
        if match and patches:
            body: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith(("@@ ", "--- ", "diff ")):
                line = lines[i]
                if line.startswith(("+", "-", " ")) or line == "":
                    body.append(line if line else " ")
                elif line.startswith("\\"):
                    pass  # "\ No newline at end of file"
                else:
                    break
                i += 1
            while body and body[-1] == " ":
                body.pop()  # the blank line after a diff is not context
            patches[-1].hunks.append((int(match.group(1)), body))
            continue
        i += 1
    if not patches or not any(p.hunks for p in patches):
        msg = "no file changes found: send a unified diff with ---/+++ headers and @@ hunks"
        raise PatchError(msg)
    return patches


def _apply_hunks(name: str, text: str, hunks: list[tuple[int, list[str]]]) -> str:
    lines = text.split("\n")
    trailing_newline = text.endswith("\n")
    if trailing_newline:
        lines = lines[:-1]
    offset = 0
    for number, (start, body) in enumerate(hunks, 1):
        before = [ln[1:] for ln in body if ln[:1] in (" ", "-")]
        after = [ln[1:] for ln in body if ln[:1] in (" ", "+")]
        want = max(0, start - 1 + offset) if before else max(0, start + offset)
        found = None
        for distance in range(_SEARCH + 1):
            for at in {want - distance, want + distance}:
                if 0 <= at <= len(lines) - len(before) and all(
                    a.rstrip() == b.rstrip() for a, b in zip(lines[at:at + len(before)], before, strict=True)
                ):
                    found = at
                    break
            if found is not None:
                break
        if found is None:
            msg = f"{name}: hunk {number} does not match the file near line {start}"
            raise PatchError(msg)
        lines[found:found + len(before)] = after
        offset += len(after) - len(before) + (found - want)
    return "\n".join(lines) + ("\n" if trailing_newline or not lines else "")


def apply(files: dict[str, str], diff: str) -> dict[str, str | None]:
    """The changed files after *diff* (None for a deleted one); *files* is not modified.

    Raises PatchError, changing nothing, when any part does not apply.
    """
    changed: dict[str, str | None] = {}
    for patch in parse(diff):
        name = patch.new or patch.old or ""
        if ".." in name.replace("\\", "/").split("/") or name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name):
            msg = f"{name}: only paths inside the project can be changed"
            raise PatchError(msg)
        if patch.old is None:
            if name in files:
                msg = f"{name}: the diff creates a file that already exists"
                raise PatchError(msg)
            changed[name] = _apply_hunks(name, "", patch.hunks)
            continue
        current = changed.get(patch.old, files.get(patch.old))
        if current is None:
            msg = f"{patch.old}: no such file in the project"
            raise PatchError(msg)
        if patch.new is None:
            changed[patch.old] = None
            continue
        changed[name] = _apply_hunks(name, current, patch.hunks)
        if patch.new != patch.old:
            changed[patch.old] = None
    return changed
