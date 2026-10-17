"""`init` recommends a model but never replaces one the owner chose."""

from __future__ import annotations

import pytest

from Agent_Guru.llm import model_catalog
from Agent_Guru.llm.model_catalog import ModelEntry
from Agent_Guru.utils import commands


@pytest.fixture
def machine(monkeypatch, tmp_path):
    written = []
    monkeypatch.setattr(commands, "_settings_file", lambda: tmp_path / "settings.toml")
    monkeypatch.setattr(commands, "config", lambda argv: written.append(argv) or 0)
    monkeypatch.setattr(model_catalog, "_gpu_memory_mb", lambda: (4096.0, 100.0))
    monkeypatch.setattr(model_catalog, "installed", lambda: [
        ModelEntry("chat:4b", 2600, capabilities=["completion", "tools"], gpu_fit="fits", needs_mb=3620)])
    monkeypatch.setattr("shutil.which", lambda _name: None)
    return written


def test_a_recommendation_is_only_printed_without_yes(machine, monkeypatch, capsys):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    assert commands.init([]) == 0  # nosec B101
    assert machine == [] and "chat:4b is recommended" in capsys.readouterr().out  # nosec B101


def test_yes_saves_it_when_no_model_is_chosen(machine, monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    commands.init(["--yes"])
    assert machine == [["set", "OLLAMA_MODEL", "chat:4b"]]  # nosec B101


def test_a_chosen_model_is_kept_even_with_yes(machine, monkeypatch, capsys):
    monkeypatch.setenv("OLLAMA_MODEL", "gemma4")
    commands.init(["--yes"])
    assert machine == [] and "gemma4 is chosen and kept" in capsys.readouterr().out  # nosec B101


def test_ollama_not_running_is_said_not_raised(machine, monkeypatch, capsys):
    def down():
        raise OSError("refused")

    monkeypatch.setattr(model_catalog, "installed", down)
    assert commands.init([]) == 0 and "Ollama: not answering" in capsys.readouterr().out  # nosec B101
