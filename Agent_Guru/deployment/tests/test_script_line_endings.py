"""Every tracked shell script checks out with LF line endings, even on Windows.

With only `* text=auto` in .gitattributes, a Windows clone with
core.autocrlf=true wrote every line of the wake-word runner's three scripts
with CRLF, and Linux bash refused them ("syntax error near unexpected token
$'do\\r'"). Those scripts reach the cluster copied from a Windows checkout, so
the line endings git writes on checkout are what has to hold. git cat-file
--filters produces exactly the bytes a checkout would write for that path,
with the attributes and the config given here.
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 - runs the local git binary on fixed arguments
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or not (REPO / ".git").exists(),
    reason="needs git and a git checkout of the repository",
)


def _git(*args: str) -> bytes:
    return subprocess.run(  # nosec B603 B607 - git from PATH, fixed arguments
        ["git", "-c", f"safe.directory={REPO.as_posix()}", *args],
        cwd=REPO, capture_output=True, check=True,
    ).stdout


def _tracked_scripts() -> list[str]:
    return [p for p in _git("ls-files", "-z", "--", "*.sh").decode().split("\0") if p]


def test_there_are_scripts_to_check() -> None:
    # Guards the parametrized test below against passing vacuously on an empty list.
    assert "wakeword_training/runner/submit_chain.sh" in _tracked_scripts()  # nosec B101


@pytest.mark.parametrize("script", _tracked_scripts() if shutil.which("git") and (REPO / ".git").exists() else [])
def test_windows_checkout_writes_lf(script: str) -> None:
    checked_out = _git("-c", "core.autocrlf=true", "cat-file", "--filters", f"HEAD:{script}")
    assert b"\r\n" not in checked_out, f"{script} would be checked out with CRLF line endings"  # nosec B101
