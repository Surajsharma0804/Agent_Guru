"""Install folder, runtime and user data stay apart; a source checkout never installs into itself."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from Agent_Guru.genesis import layout as lay


def test_the_runtime_and_the_download_cache_live_inside_the_install_folder(tmp_path):
    root = tmp_path / "Agent Guru"
    layout = lay.default_layout(root)
    for path in (layout.runtime_root, layout.venv_python, layout.cache_dir, layout.journal_path, layout.lock_path):
        assert root.resolve() in path.parents  # nosec B101  removed with the app on uninstall


def test_user_data_is_not_inside_the_install_folder(tmp_path):
    layout = lay.default_layout(tmp_path / "Agent Guru")
    assert layout.install_root not in layout.data_dir.parents  # nosec B101  uninstall keeps it
    assert layout.settings_path.parent == layout.data_dir  # nosec B101


def test_a_source_checkout_must_name_its_install_folder(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    with pytest.raises(ValueError, match="--root"):
        lay.default_layout()


def test_a_frozen_launcher_installs_next_to_itself(monkeypatch, tmp_path):
    exe = tmp_path / "Agent Guru" / "AgentGuru.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    layout = lay.default_layout()
    assert layout.install_root == exe.parent.resolve() and layout.app_root == exe.parent.resolve() / "app"  # nosec B101
    assert layout.lock_file == layout.app_root / "requirements-lock.txt"  # nosec B101


def test_the_source_root_is_the_checkout():
    assert (lay.source_root() / "Agent_Guru" / "genesis" / "layout.py").is_file()  # nosec B101
    assert isinstance(lay.source_root(), Path)  # nosec B101
