"""The tray icon: what shows that the microphone is open when no window does."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from Agent_Guru.utils import tray


class Pystray:
    class MenuItem:
        def __init__(self, text, action, default=False, checked=None, enabled=True):
            self.text, self.action, self.checked, self.enabled = text, action, checked, enabled

    @staticmethod
    def Menu(*items):  # noqa: N802 - pystray's name
        return {i.text: i for i in items}


class Workspace:
    def __init__(self, microphone="on"):
        self.microphone = microphone
        self.asked = []

    def state(self, body):
        return 200, {"microphone": self.microphone}

    def set_mic(self, body):
        self.asked.append(body)
        self.microphone = "muted" if body["muted"] else "on"
        return 200, body


def menu(workspace, stopped=None):
    return tray.menu_items(workspace, "http://127.0.0.1:1/workspace.html#t=x", Pystray, lambda: None if stopped is None else stopped.append(True))


def test_mute_goes_through_the_workspace_and_shows_the_real_state():
    workspace = Workspace()
    item = menu(workspace)["Mute microphone"]
    assert item.checked(None) is False  # nosec B101
    item.action(None, None)
    assert workspace.asked == [{"muted": True}] and item.checked(None) is True  # nosec B101
    item.action(None, None)
    assert workspace.asked[-1] == {"muted": False} and item.checked(None) is False  # nosec B101


def test_mute_is_off_when_nothing_is_listening():
    assert menu(Workspace("none"))["Mute microphone"].enabled(None) is False  # nosec B101


def test_quit_asks_the_assistant_and_removes_the_icon():
    stopped, gone = [], []
    menu(Workspace(), stopped)["Quit Agent Guru"].action(SimpleNamespace(stop=lambda: gone.append(True)), None)
    assert stopped == [True] and gone == [True]  # nosec B101


def test_open_uses_the_installed_launcher(monkeypatch):
    started = []
    monkeypatch.setenv("AGENT_GURU_LAUNCHER", "C:\\AG\\AgentGuru.exe")
    monkeypatch.setenv("AGENT_GURU_INSTALL_ROOT", "C:\\AG")
    monkeypatch.setattr(tray.subprocess, "Popen", lambda args: started.append(args))
    tray.open_window("http://x")
    assert started == [["C:\\AG\\AgentGuru.exe", "--root", "C:\\AG"]]  # nosec B101


def test_open_from_a_checkout_uses_the_browser(monkeypatch):
    opened = []
    monkeypatch.delenv("AGENT_GURU_LAUNCHER", raising=False)
    monkeypatch.setattr(tray.webbrowser, "open", opened.append)
    tray.open_window("http://x")
    assert opened == ["http://x"]  # nosec B101


def test_no_tray_library_leaves_the_assistant_running(monkeypatch):
    monkeypatch.setitem(sys.modules, "pystray", None)
    monkeypatch.setattr(tray.sys, "platform", "linux")
    assert tray.start(Workspace(), "http://x") is None  # nosec B101


def test_macos_starts_no_tray_thread(monkeypatch):
    monkeypatch.setattr(tray.sys, "platform", "darwin")
    assert tray.start(Workspace(), "http://x") is None  # nosec B101
