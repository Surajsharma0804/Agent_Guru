"""The assistant starts at sign-in with no window, and one assistant serves every way of opening it."""

from __future__ import annotations

import json
import os
import plistlib
import shlex
import subprocess
import sys
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from Agent_Guru.genesis import actions as act
from Agent_Guru.genesis import app as ga
from Agent_Guru.genesis import assistant, autostart, cli, launcher
from Agent_Guru.genesis import journal as jr
from Agent_Guru.genesis import manifest as mf
from Agent_Guru.genesis import planner, verify
from Agent_Guru.genesis.layout import Layout
from Agent_Guru.genesis.server import HEARTBEAT_TIMEOUT, GenesisServer
from Agent_Guru.genesis.tests.test_planner import machine

MANIFEST = mf.load()


@pytest.fixture
def layout(tmp_path):
    out = Layout(tmp_path / "My Install", tmp_path / "data")
    out.runtime_root.mkdir(parents=True)
    return out


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    return tmp_path


def finished(layout):
    j = jr.Journal(layout.journal_path)
    j.append("r", "first-start", "Awakening", "started")
    j.append("r", "first-start", "Awakening", "verified", {"result": "PASS"})


def test_the_linux_entry_runs_the_command_with_a_quoted_path(layout, home):
    entry = autostart.write("linux", ["/opt/My Apps/AgentGuru.AppImage", "--background"], Path("/opt"))
    assert entry == home / "config" / "autostart" / "agent-guru.desktop"  # nosec B101
    lines = dict(line.split("=", 1) for line in entry.read_text(encoding="utf-8").splitlines() if "=" in line)
    assert shlex.split(lines["Exec"]) == ["/opt/My Apps/AgentGuru.AppImage", "--background"]  # nosec B101
    assert lines["Terminal"] == "false" and lines["Type"] == "Application"  # nosec B101


def test_the_macos_entry_is_a_valid_launch_agent(layout, home):
    entry = autostart.write("darwin", ["/Applications/Agent Guru.app/Contents/MacOS/AgentGuru", "--root", "a&b", "--background"], Path("/tmp"))  # nosec B108
    plist = plistlib.loads(entry.read_bytes())
    assert plist["ProgramArguments"][2] == "a&b" and plist["RunAtLoad"] is True  # nosec B101
    assert entry.name == autostart.LABEL + ".plist"  # nosec B101


@pytest.mark.skipif(sys.platform != "win32", reason="a Windows shortcut")
def test_the_windows_entry_is_a_real_shortcut_in_the_startup_folder(layout, home):
    entry = autostart.write("windows", ["C:\\Program Files\\A Guru\\AgentGuru.exe", "--root", "D:\\My Install", "--background"], Path("C:\\Windows"))
    assert entry.parent.name == "Startup" and entry.suffix == ".lnk"  # nosec B101
    import win32com.client

    link = win32com.client.Dispatch("WScript.Shell").CreateShortcut(str(entry))
    assert link.TargetPath.endswith("AgentGuru.exe") and link.Arguments == '--root "D:\\My Install" --background'  # nosec B101
    assert link.WindowStyle == 7  # nosec B101  minimised, so nothing flashes at sign-in


def test_a_frozen_build_starts_itself_and_never_the_console_build(layout, monkeypatch, tmp_path):
    # A native path so PosixPath on Linux can parse the directory and
    # filename components. The hardcoded "C:\\AG\\..." was one PosixPath
    # name component on Linux, so .name never started with "agentgurucli"
    # and the rename to the windowed build was skipped.
    cli_exe = tmp_path / "AG" / "AgentGuruCli.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(cli_exe))
    monkeypatch.delenv("APPIMAGE", raising=False)
    command, _ = autostart.launcher_command(layout)
    assert Path(command[0]).name == "AgentGuru.exe"  # nosec B101
    assert command[-1] == "--background"  # nosec B101


def test_an_appimage_is_started_from_the_file_not_its_mount(layout, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/tmp/.mount_AgXyz/AgentGuru")  # nosec B108
    monkeypatch.setenv("APPIMAGE", "/home/me/AgentGuru.AppImage")
    assert Path(autostart.launcher_command(layout)[0][0]) == Path("/home/me/AgentGuru.AppImage")  # nosec B101


def test_the_part_installs_verifies_and_removes(layout, home, monkeypatch):
    monkeypatch.setattr(autostart, "launcher_command", lambda _l: (["/bin/ag", "--background"], Path("/bin")))
    ctx = act.ActionContext(layout, lambda k, d: None, platform="linux")
    component = MANIFEST.by_id["autostart"]
    assert verify.run("autostart.present", ctx, component).label == "NOT INSTALLED"  # nosec B101
    act.ACTIONS[component["install"]](ctx, component)
    assert verify.run("autostart.present", ctx, component).label == "PASS"  # nosec B101
    assert act.ACTIONS[component["rollback"]](ctx, component).detail == {"removed": True}  # nosec B101
    assert verify.run("autostart.present", ctx, component).label == "NOT INSTALLED"  # nosec B101


def test_it_is_on_by_default_shown_on_the_plan_and_optional():
    plan = planner.plan(machine(), MANIFEST, planner.Choices())
    assert plan["tiers"]["startup"] is True  # nosec B101
    assert next(r for r in plan["components"] if r["id"] == "autostart")["action"] == "install"  # nosec B101
    assert MANIFEST.by_id["autostart"]["required"] is False  # nosec B101  so Control Center can remove it
    off = planner.plan(machine(), MANIFEST, planner.Choices(tiers=dict(planner.DEFAULT_TIERS, startup=False)))
    assert next(r for r in off["components"] if r["id"] == "autostart")["action"] == "skip"  # nosec B101


class Launches:
    def __init__(self):
        self.calls = []

    def __call__(self, args, cwd):
        self.calls.append(args)
        return SimpleNamespace(pid=None)


@pytest.fixture
def no_ollama(monkeypatch):
    monkeypatch.setattr(act, "private_ollama", lambda *a: None)


def test_background_on_a_finished_install_starts_the_assistant_and_opens_no_window(layout, monkeypatch, no_ollama):
    finished(layout)
    starts = Launches()
    monkeypatch.setattr(launcher, "GenesisApp", lambda lay, replay_journal=None: ga.GenesisApp(lay, MANIFEST, launcher=starts))
    monkeypatch.setattr(launcher, "_show", lambda *a: pytest.fail("a window opened at sign-in"))
    monkeypatch.setattr(launcher, "webbrowser", SimpleNamespace(open=lambda *a: pytest.fail("a browser opened at sign-in")))
    assert launcher.main(["--root", str(layout.install_root), "--background"]) == 0  # nosec B101
    assert len(starts.calls) == 1  # nosec B101


def test_background_before_setup_finished_does_nothing(layout, monkeypatch, no_ollama):
    starts = Launches()
    monkeypatch.setattr(launcher, "GenesisApp", lambda lay, replay_journal=None: ga.GenesisApp(lay, MANIFEST, launcher=starts))
    assert launcher.main(["--root", str(layout.install_root), "--background"]) == 0  # nosec B101
    assert starts.calls == []  # nosec B101


def serving(layout):
    """A real server with the assistant's address on file, as workspace.start leaves it."""
    server = GenesisServer({("POST", "/api/quit"): lambda b: (server.stop() or 200, {"stopping": True})}, outlives_window=True)
    url = server.start().replace("/#t=", "/workspace.html#t=")
    assistant.workspace_file(layout).write_text(json.dumps({"url": url}), encoding="utf-8")
    return server, url


def test_opening_the_app_again_reaches_the_running_assistant(layout, monkeypatch, no_ollama):
    """The shortcut started a second assistant, on the same microphone, every time."""
    finished(layout)
    server, url = serving(layout)
    starts, shown = Launches(), []
    monkeypatch.setattr(launcher, "GenesisApp", lambda lay, replay_journal=None: ga.GenesisApp(lay, MANIFEST, launcher=starts))
    monkeypatch.setattr(launcher, "_show", lambda u, b: shown.append(u))
    try:
        assert launcher.main(["--root", str(layout.install_root)]) == 0  # nosec B101
    finally:
        server.stop()
    assert shown == [url] and starts.calls == []  # nosec B101


def test_an_address_left_by_a_crash_is_not_opened(layout):
    assistant.workspace_file(layout).write_text(json.dumps({"url": "http://127.0.0.1:9/workspace.html#t=x"}), encoding="utf-8")
    assert assistant.window_url(layout) == ""  # nosec B101


def test_an_assistant_still_loading_is_not_started_twice(layout, no_ollama):
    starts = Launches()
    app = ga.GenesisApp(layout, MANIFEST, launcher=starts)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])  # nosec B603
    try:
        assistant.remember(layout, child.pid)
        assert app.start_assistant() == {"started": False, "running": True} and starts.calls == []  # nosec B101
    finally:
        child.kill()
        child.wait(10)
    assert assistant.starting(layout) is False  # nosec B101
    assert app.start_assistant()["started"] is True and len(starts.calls) == 1  # nosec B101


def test_an_old_process_number_is_not_taken_for_one_loading_now(layout):
    """A number on file from days ago may belong to anything now, so being alive proves nothing."""
    assistant.remember(layout, os.getpid())
    assert assistant.starting(layout) is True  # nosec B101
    os.utime(assistant.pid_file(layout), (0, 0))
    assert assistant.starting(layout) is False  # nosec B101


def test_the_assistants_server_outlives_its_window():
    """It stopped 60 s after the last page, so the assistant ran on with no way back to it."""
    now = [0.0]
    server = GenesisServer({}, clock=lambda: now[0], outlives_window=True)
    server.start()
    now[0] = HEARTBEAT_TIMEOUT * 10
    try:
        assert server.heartbeat_lapsed() and not server.stopped.wait(2.5)  # nosec B101
    finally:
        server.stop()


def test_setups_server_still_ends_with_its_window():
    now = [0.0]
    server = GenesisServer({}, clock=lambda: now[0])
    server.start()
    now[0] = HEARTBEAT_TIMEOUT * 10
    assert server.stopped.wait(5)  # nosec B101


def test_stop_asks_the_running_assistant(layout):
    server, _ = serving(layout)
    assert assistant.request_quit(layout, wait_s=5) is True  # nosec B101
    assert server.stopped.is_set()  # nosec B101


def test_stop_with_nothing_running_is_not_an_error(layout):
    assert launcher.main(["--root", str(layout.install_root), "--stop"]) == 0  # nosec B101


def test_uninstall_stops_it_and_removes_the_sign_in_entry(layout, home, monkeypatch):
    calls = []
    monkeypatch.setattr(assistant, "request_quit", lambda lay: calls.append("quit") or True)
    monkeypatch.setattr(autostart, "remove", lambda plat: calls.append("entry") or True)
    assert "removed" in cli.uninstall(layout, remove_data=False)  # nosec B101
    assert calls == ["quit", "entry"]  # nosec B101


def test_the_assistant_gets_no_console(layout, monkeypatch):
    seen = {}

    def popen(args, **k):
        seen.update(k)
        return SimpleNamespace(pid=None)

    monkeypatch.setattr(ga.subprocess, "Popen", popen)
    ga.GenesisApp(layout, MANIFEST)._start_detached(["x"], layout.runtime_root)
    assert seen["start_new_session"] is True and seen["stdin"] == subprocess.DEVNULL  # nosec B101
    if sys.platform == "win32":
        assert seen["creationflags"] & subprocess.CREATE_NO_WINDOW  # nosec B101
    assert (layout.runtime_root / "assistant.log").exists()  # nosec B101


def test_every_address_read_is_loopback(layout):
    assistant.workspace_file(layout).write_text(json.dumps({"url": "http://example.test/workspace.html#t=x"}), encoding="utf-8")
    calls = []
    original = urllib.request.urlopen
    urllib.request.urlopen = lambda *a, **k: calls.append(a) or original(*a, **k)
    try:
        assert assistant.window_url(layout) == "" and calls == []  # nosec B101
    finally:
        urllib.request.urlopen = original
