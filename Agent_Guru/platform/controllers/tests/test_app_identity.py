"""Which running processes are an application, for closing it and for checking open and close.

_find_process_by_name() fell back to substring matching, also for known names
whose real executable was not running: "close word" with WordPad open matched
wordpad.exe, and an unknown short name matched any process containing it. It
also took the first match, which for Windows 11 Notepad (two notepad.exe
processes) was the one without the window: the window stayed open and the
close was reported done. app_instances() is the read-only view the assistant
checks an open or a close against.
"""

from __future__ import annotations

from types import SimpleNamespace

from Agent_Guru.platform.controllers.application_control import ApplicationController


def _controller(processes, windows=(), platform="win32"):
    c = ApplicationController.__new__(ApplicationController)
    c.platform = platform
    procs = [SimpleNamespace(pid=pid, name=name) for pid, name in processes]
    c._platform_integration = SimpleNamespace(get_process_list=lambda **kw: procs)
    wins = [SimpleNamespace(pid=pid, title=title) for pid, title in windows]
    c.list_windows = lambda: wins
    return c


DESKTOP = [(1, "Program Manager")]  # a session always has some window


def test_a_known_name_matches_only_its_own_executables():
    c = _controller([(10, "wordpad.exe"), (11, "WINWORD.EXE")], DESKTOP)
    assert c._find_process_by_name("word") == 11  # nosec B101
    c = _controller([(10, "wordpad.exe")], DESKTOP)
    assert c._find_process_by_name("word") is None  # nosec B101  wordpad.exe matched before


def test_an_unknown_name_matches_only_that_executable():
    c = _controller([(20, "buzz.exe"), (21, "zzz.exe")], DESKTOP)
    assert c._find_process_by_name("zz") is None  # nosec B101  both matched before
    assert c._find_process_by_name("zzz") == 21  # nosec B101


def test_the_instance_with_the_window_is_closed_first():
    # Windows 11 Notepad: two notepad.exe, only the second owns the window.
    c = _controller([(30, "Notepad.exe"), (31, "Notepad.exe")], [*DESKTOP, (31, "Untitled - Notepad")])
    assert c._find_process_by_name("notepad") == 31  # nosec B101


def test_instances_are_the_application_and_say_which_show_a_window():
    c = _controller(
        [(40, "CalculatorApp.exe"), (41, "ApplicationFrameHost.exe"), (42, "calculatorhelper.exe")],
        [*DESKTOP, (41, "Calculator")],
    )
    # The frame host and a similarly named helper are not the application.
    assert c.app_instances("calculator") == {40: False}  # nosec B101


def test_a_launcher_alone_is_not_the_application():
    c = _controller([(50, "cmd.exe"), (51, "paintlauncher.exe")], DESKTOP)
    assert c.app_instances("paint") == {}  # nosec B101


def test_instances_report_their_windows():
    c = _controller([(60, "notepad.exe"), (61, "notepad.exe")], [*DESKTOP, (61, "Untitled - Notepad")])
    assert c.app_instances("notepad") == {60: False, 61: True}  # nosec B101


def test_unreadable_state_is_none_not_a_guess():
    # Processes but no window at all on the desktop: the window list failed.
    c = _controller([(70, "notepad.exe")], windows=())
    assert c.app_instances("notepad") is None  # nosec B101
    assert _controller([(70, "notepad.exe")], DESKTOP, platform="linux").app_instances("notepad") is None  # nosec B101

    def broken(**kw):
        raise OSError("snapshot failed")

    c = _controller([], DESKTOP)
    c._platform_integration = SimpleNamespace(get_process_list=broken)
    assert c.app_instances("notepad") is None  # nosec B101


def test_nothing_running_is_an_empty_answer():
    assert _controller([(80, "explorer.exe")], DESKTOP).app_instances("notepad") == {}  # nosec B101
