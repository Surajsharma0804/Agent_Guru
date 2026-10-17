"""Bring this checkout up to date with its upstream, safely.

There was no way to update Agent Guru short of running git by hand.
`python -m Agent_Guru update --check` fetches and says how far behind
the checkout is and what would arrive; `update` fast-forwards to the
upstream branch.

It never merges, rebases or discards: it refuses while tracked files
have changes, and when the checkout and the upstream have both moved,
because either would mean deciding about the owner's work for them.
Dependencies are not installed by it; when requirements or
pyproject.toml change in the update it says so, and when the assistant
is running it says to restart it.
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 - git with fixed arguments
from dataclasses import dataclass, field
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEPENDENCY_FILES = ("pyproject.toml", "requirements.txt", "requirements-lock.txt")


@dataclass(slots=True)
class UpdateState:
    behind: int = 0
    ahead: int = 0
    incoming: list[str] = field(default_factory=list)
    dependencies_changed: bool = False
    problem: str = ""


def _git(root: Path, *args: str, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    git = shutil.which("git")
    if git is None:
        msg = "git is not installed"
        raise OSError(msg)
    return subprocess.run(  # nosec B603 - git with fixed arguments
        [git, "-C", str(root), *args], capture_output=True, text=True, timeout=timeout, check=False,
        stdin=subprocess.DEVNULL,
    )


def inspect(root: Path = _PROJECT_ROOT, *, fetch: bool = True) -> UpdateState:
    """How the checkout at *root* stands against its upstream, after fetching it."""
    state = UpdateState()
    try:
        if _git(root, "rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
            state.problem = f"{root} is not a git checkout"
            return state
        if _git(root, "rev-parse", "--abbrev-ref", "@{u}").returncode != 0:
            state.problem = "this branch has no upstream to update from"
            return state
        if fetch:
            fetched = _git(root, "fetch", "--quiet")
            if fetched.returncode != 0:
                state.problem = f"could not fetch: {fetched.stderr.strip()[:200]}"
                return state
        counts = _git(root, "rev-list", "--left-right", "--count", "HEAD...@{u}").stdout.split()
        state.ahead, state.behind = int(counts[0]), int(counts[1])
        if state.behind:
            state.incoming = _git(root, "log", "--format=%h %s", "HEAD..@{u}").stdout.splitlines()
            changed = _git(root, "diff", "--name-only", "HEAD", "@{u}").stdout.split()
            state.dependencies_changed = any(name in _DEPENDENCY_FILES for name in changed)
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError) as exc:
        state.problem = f"{type(exc).__name__}: {exc}"[:200]
    return state


def update(root: Path = _PROJECT_ROOT) -> tuple[bool, str]:
    """Fast-forward the checkout to its upstream; (updated, what happened)."""
    state = inspect(root)
    if state.problem:
        return False, f"Not updated: {state.problem}."
    if not state.behind:
        return False, "Already up to date."
    if state.ahead:
        return False, (f"Not updated: this checkout has {state.ahead} commits the upstream does not, and the upstream "
                       f"{state.behind} this checkout does not. Merge or rebase them yourself.")
    if _git(root, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        return False, "Not updated: tracked files have changes. Commit or stash them first."
    merged = _git(root, "merge", "--ff-only", "@{u}")
    if merged.returncode != 0:
        return False, f"Not updated: {merged.stderr.strip()[:200]}"
    notes = [f"Updated: {state.behind} new commits."]
    if state.dependencies_changed:
        notes.append("Dependencies changed: run  pip install -r requirements.txt  before the next start.")
    from Agent_Guru.utils import service

    if service.state():
        notes.append("Agent Guru is running the old code: python -m Agent_Guru service stop, then service start.")
    return True, " ".join(notes)


def run(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m Agent_Guru update",
                                     description="Fast-forward this checkout to its upstream, never merging.")
    parser.add_argument("--check", action="store_true", help="only say what an update would bring")
    args = parser.parse_args(argv)
    if args.check:
        state = inspect()
        if state.problem:
            print(f"Cannot check: {state.problem}.")  # noqa: T201  the command's output
            return 1
        print(f"Behind the upstream by {state.behind} commits, ahead by {state.ahead}.")  # noqa: T201
        for line in state.incoming[:20]:
            print(f"  {line}")  # noqa: T201
        if state.dependencies_changed:
            print("The update changes dependencies.")  # noqa: T201
        return 0
    updated, said = update()
    print(said)  # noqa: T201
    return 0 if updated or said == "Already up to date." else 1
