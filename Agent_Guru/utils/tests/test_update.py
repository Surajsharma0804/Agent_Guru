"""`update` only fast-forwards: it never merges, rebases or touches the owner's changes.

Runs real git on a throwaway upstream and clone.
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 - git with fixed arguments

import pytest

from Agent_Guru.utils import update

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="UNVERIFIED on this host: git is not installed")


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)  # nosec B603 B607


def _commit(repo, name, text):
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", f"change {name}")


@pytest.fixture
def repos(tmp_path):
    upstream, work, other = tmp_path / "upstream.git", tmp_path / "work", tmp_path / "other"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(upstream))
    _git(tmp_path, "clone", "-q", str(upstream), str(work))
    _commit(work, "a.txt", "1")
    _git(work, "push", "-q", "-u", "origin", "main")
    _git(tmp_path, "clone", "-q", str(upstream), str(other))
    return work, other


def _publish(other, name, text):
    _commit(other, name, text)
    _git(other, "push", "-q", "origin", "main")


def test_it_fast_forwards_and_says_what_arrived(repos, monkeypatch):
    work, other = repos
    monkeypatch.setattr("Agent_Guru.utils.service.state", lambda: None)
    _publish(other, "b.txt", "2")
    _publish(other, "requirements.txt", "httpx\n")
    state = update.inspect(work)
    assert (state.behind, state.ahead, state.dependencies_changed) == (2, 0, True)  # nosec B101
    assert any("requirements.txt" in line for line in state.incoming)  # nosec B101
    updated, said = update.update(work)
    assert updated and "2 new commits" in said and "Dependencies changed" in said  # nosec B101
    assert (work / "b.txt").read_text() == "2"  # nosec B101
    assert update.update(work) == (False, "Already up to date.")  # nosec B101


def test_changes_to_tracked_files_are_never_overwritten(repos):
    work, other = repos
    _publish(other, "a.txt", "theirs")
    (work / "a.txt").write_text("mine, not committed", encoding="utf-8")
    updated, said = update.update(work)
    assert not updated and "Commit or stash" in said  # nosec B101
    assert (work / "a.txt").read_text() == "mine, not committed"  # nosec B101


def test_diverged_history_is_left_for_the_owner(repos):
    work, other = repos
    _publish(other, "b.txt", "theirs")
    _commit(work, "c.txt", "mine")
    head = _git(work, "rev-parse", "HEAD").stdout
    updated, said = update.update(work)
    assert not updated and "Merge or rebase them yourself" in said  # nosec B101
    assert _git(work, "rev-parse", "HEAD").stdout == head  # nosec B101


def test_a_folder_that_is_not_a_checkout_is_said(tmp_path):
    assert "not a git checkout" in update.inspect(tmp_path, fetch=False).problem  # nosec B101
