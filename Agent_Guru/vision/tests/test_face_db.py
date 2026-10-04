"""Regression tests for FaceDatabase persistence paths.

These cover one specific defect and the constructor argument that replaced the
workaround people reached for instead.

The defect: FaceDatabase persists to a JSON file, but two callers passed
db_path=":memory:" because that is what you pass SQLite to get a database that
never touches disk. Nothing validated it. The constructor treated ":memory:"
as an ordinary relative path, so every run wrote a real file with that literal
name into whatever directory the process started in, and that file held the
base64-encoded face biometric templates of everyone the database had seen. On
Windows ":" is not a legal filename character, so the Win32 layer substituted
U+F03A and the file became invisible to ordinary tooling: git did not match it,
cleanup scripts did not match it, and it sat in the working tree.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import numpy as np
import pytest

from Agent_Guru.vision.database.face_db import FaceDatabase

if TYPE_CHECKING:
    from pathlib import Path


def _unit_vector(index: int = 0) -> np.ndarray:
    """Build a normalised 512-dim embedding pointing along one axis."""
    vector = np.zeros(512, dtype=np.float32)
    vector[index] = 1.0
    return vector


@pytest.mark.parametrize("token", [":memory:", "memory", "  :memory:  "])
def test_sqlite_memory_token_is_rejected(token: str) -> None:
    """The SQLite in-memory token raises instead of becoming a file name.

    Both spellings are checked because Windows rewrites the colon to U+F03A,
    and surrounding whitespace is checked because a stripped value is still the
    same mistake.
    """
    with pytest.raises(ValueError, match="not SQLite"):
        FaceDatabase(db_path=token)


def test_rejected_token_leaves_no_file_behind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is created on disk when the token is rejected.

    This is the part that actually mattered: the old code produced a file of
    biometric templates in the process working directory as a side effect of a
    constructor call that the caller believed did no I/O at all.
    """
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="not SQLite"):
        FaceDatabase(db_path=":memory:")

    assert list(tmp_path.iterdir()) == []  # nosec B101


def test_none_path_keeps_identities_out_of_the_filesystem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """db_path=None gives a working database that writes nothing.

    This is the supported replacement for what the ":memory:" callers wanted.
    Without it the next person needing a throwaway database has the same reason
    to invent one, so the guard above would only move the bug.
    """
    monkeypatch.chdir(tmp_path)

    db = FaceDatabase(db_path=None)
    assert db.add_identity("Alice", [_unit_vector()], permission_level="user")  # nosec B101

    match = db.search(_unit_vector())
    assert match.identity == "Alice"  # nosec B101
    assert list(tmp_path.iterdir()) == []  # nosec B101


def test_real_path_still_persists(tmp_path: Path) -> None:
    """A normal path behaves exactly as before, so the guard changed nothing else."""
    db_path = tmp_path / "identities.json"

    db = FaceDatabase(db_path=str(db_path))
    assert db.add_identity("Alice", [_unit_vector()], permission_level="user")  # nosec B101

    assert db_path.exists()  # nosec B101
    stored = json.loads(db_path.read_text(encoding="utf-8"))
    assert [entry["name"] for entry in stored["identities"]] == ["Alice"]  # nosec B101

    reloaded = FaceDatabase(db_path=str(db_path))
    assert reloaded.search(_unit_vector()).identity == "Alice"  # nosec B101


def _windows_trustee_sids(path: Path) -> set[str]:
    import win32security

    sd = win32security.GetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION)
    dacl = sd.GetSecurityDescriptorDacl()
    return {
        win32security.ConvertSidToStringSid(dacl.GetAce(i)[2])
        for i in range(dacl.GetAceCount())
    }


# Everyone, Authenticated Users, BUILTIN\Users: every local account.
_BROAD_SIDS = {"S-1-1-0", "S-1-5-11", "S-1-5-32-545"}


def test_persisted_file_is_owner_only(tmp_path: Path) -> None:
    """The database file is readable by its owner only, since it holds biometric templates.

    On Windows this used to check st_mode == 0o600, which Windows cannot
    express: every file reports 666, so the test failed on every Windows run
    while the real protection, an ACL set with icacls, was in place. It now
    checks that ACL. The folder first grants BUILTIN\\Users read access to new
    files, as an ordinary folder on a data drive does (Authenticated Users and
    Users), and a plain file written beside the database must show it, so the
    test cannot pass just because the temporary folder was already private.
    """
    import os

    if os.name == "nt":
        import subprocess

        subprocess.run(  # nosec B603 B607
            ["icacls", str(tmp_path), "/grant", "*S-1-5-32-545:(OI)(CI)(RX)"],
            capture_output=True, check=True, timeout=10,
        )
        control = tmp_path / "plain.txt"
        control.write_text("x", encoding="utf-8")
        assert _windows_trustee_sids(control) & _BROAD_SIDS  # nosec B101

    db_path = tmp_path / "identities.json"
    db = FaceDatabase(db_path=str(db_path))
    db.add_identity("Alice", [_unit_vector()], permission_level="user")

    if os.name == "nt":
        broad = _windows_trustee_sids(db_path) & _BROAD_SIDS
        assert not broad, f"face database readable by {sorted(broad)}"  # nosec B101
    else:
        mode = db_path.stat().st_mode & 0o777
        assert mode == 0o600, f"expected 0600, got {mode:o}"  # nosec B101
