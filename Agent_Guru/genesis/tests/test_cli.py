"""`agent-guru genesis` from a terminal: the plan, the exit codes, and a redacted report."""

from __future__ import annotations

import getpass
import io
import json
from pathlib import Path

import pytest

from Agent_Guru.genesis import cli
from Agent_Guru.genesis import executor as ex
from Agent_Guru.genesis.layout import default_layout
from Agent_Guru.genesis.tests.test_planner import machine


@pytest.fixture
def fake_scan(monkeypatch):
    state = {"machine": machine()}
    monkeypatch.setattr(cli.probes, "scan", lambda *a, **k: state["machine"])
    return state


def test_plan_json_prints_the_plan_and_creates_nothing(tmp_path, fake_scan, capsys):
    root = tmp_path / "Agent Guru"
    assert cli.run(["--root", str(root), "--plan", "--json"]) == cli.EXIT_OK  # nosec B101
    plan = json.loads(capsys.readouterr().out)
    assert {r["id"] for r in plan["components"]} >= {"core-packages", "llm-model"}  # nosec B101
    assert not root.exists()  # nosec B101


def test_plan_text_names_the_model_the_sizes_and_what_changes_outside(tmp_path, fake_scan, capsys):
    cli.run(["--root", str(tmp_path / "AG"), "--plan"])
    text = capsys.readouterr().out
    assert "Model: qwen2.5:1.5b" in text and "Download " in text and "Outside the install folder" in text  # nosec B101
    assert "Nothing is added to startup, PATH or the firewall." in text  # nosec B101


def test_a_wrong_command_line_exits_2(tmp_path, capsys):
    assert cli.run(["--no-such-flag"]) == cli.EXIT_USAGE  # nosec B101
    assert cli.run(["--plan"]) == cli.EXIT_USAGE  # nosec B101  no --root from a source checkout
    assert "--root" in capsys.readouterr().err  # nosec B101


def test_a_plan_that_does_not_fit_exits_3_and_changes_nothing(tmp_path, fake_scan):
    fake_scan["machine"] = machine(free_mb=100)
    root = tmp_path / "AG"
    assert cli.run(["--root", str(root), "--plan"]) == cli.EXIT_CANNOT  # nosec B101
    assert cli.run(["--root", str(root), "--yes"]) == cli.EXIT_CANNOT  # nosec B101
    assert not root.exists()  # nosec B101


def test_without_yes_and_without_a_terminal_nothing_is_installed(tmp_path, fake_scan, monkeypatch):
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO(""))
    ran = []
    monkeypatch.setattr(ex.Executor, "run", lambda self, run_id=None: ran.append(1))
    assert cli.run(["--root", str(tmp_path / "AG")]) == cli.EXIT_NOT_APPROVED and ran == []  # nosec B101


def test_another_installer_running_exits_5(tmp_path, fake_scan):
    root = tmp_path / "AG"
    with ex.InstallLock(default_layout(root)):
        assert cli.run(["--root", str(root), "--yes"]) == cli.EXIT_BUSY  # nosec B101


@pytest.mark.parametrize(("summary", "code"), [
    (ex.Summary("r", verified=["core-packages"]), cli.EXIT_OK),
    (ex.Summary("r", failed={"voice-packages": "no network"}), cli.EXIT_FAILED),
    (ex.Summary("r", cancelled=["voice-packages"]), cli.EXIT_CANCELLED),
    (ex.Summary("r", refused="not enough disk"), cli.EXIT_CANNOT),
])
def test_the_exit_code_follows_the_runs_outcome(tmp_path, fake_scan, monkeypatch, summary, code):
    monkeypatch.setattr(ex.Executor, "run", lambda self, run_id=None: summary)
    assert cli.run(["--root", str(tmp_path / "AG"), "--yes"]) == code  # nosec B101


def test_a_second_run_says_it_had_nothing_to_do(tmp_path, fake_scan, monkeypatch, capsys):
    monkeypatch.setattr(ex.Executor, "run", lambda self, run_id=None: ex.Summary("r", reused=["core-packages"]))
    assert cli.run(["--root", str(tmp_path / "AG"), "--yes"]) == cli.EXIT_OK  # nosec B101
    assert "Nothing to do" in capsys.readouterr().out  # nosec B101


def test_the_report_has_no_user_name_or_home_folder(tmp_path, monkeypatch, capsys):
    home = str(Path.home())
    user = getpass.getuser()
    # A python entry of its own: the default one is shared by every fake machine.
    fake = machine(pythons=[{"version": "3.13.15", "path": home + "\\AppData\\Local\\Python\\python.exe"}])
    fake.probes["disk"].value["target"] = home + "\\Agent Guru"
    # The name outside the home folder too: a second drive, a share.
    fake.probes["disk"].value["measured_at"] = f"D:\\builds\\{user}-tools"
    monkeypatch.setattr(cli.probes, "scan", lambda *a, **k: fake)
    assert cli.run(["--root", str(tmp_path / "AG"), "--report"]) == cli.EXIT_OK  # nosec B101
    out = capsys.readouterr().out
    assert home not in out and home.replace("\\", "\\\\") not in out and user.lower() not in out.lower()  # nosec B101
    assert "<home>" in out  # nosec B101


def test_verify_with_nothing_installed_says_so(tmp_path, capsys):
    assert cli.run(["--root", str(tmp_path / "AG"), "--verify"]) == cli.EXIT_OK  # nosec B101
    assert "nothing is installed here yet" in capsys.readouterr().out  # nosec B101
