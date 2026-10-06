"""Closing an application asks its own windows to close; nothing is killed.

close_application() ended the chosen process with terminate_process(),
which on Windows is TerminateProcess even with force=False. Measured: an
editor holding unsaved text was gone 0.03 s later and never asked whether
to save. Now the windows of exactly that instance get WM_CLOSE, the same
request clicking their X makes, and the application decides.

Window handles here are fakes and no message is posted: the controller's
three win32 calls are replaced.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from Agent_Guru.platform.controllers.application_control import ApplicationController


class Integration:
    def __init__(self, processes):
        self.procs = [SimpleNamespace(pid=pid, name=name) for pid, name in processes]
        self.terminated = []

    def get_process_list(self, **kw):
        return self.procs

    def terminate_process(self, pid, force=False):
        self.terminated.append((pid, force))
        return True


def _controller(processes, windows, owners=None, disabled=(), platform="win32"):
    """windows: (hwnd, pid, title); owners: {hwnd: owner hwnd}; disabled: hwnds not enabled."""
    c = ApplicationController.__new__(ApplicationController)
    c.platform = platform
    c._platform_integration = Integration(processes)
    wins = [SimpleNamespace(handle=h, pid=pid, title=t) for h, pid, t in windows]
    c.list_windows = lambda: wins
    owners = owners or {}
    c.posted = []
    c._window_owner = lambda h: owners.get(h, 0)
    c._window_enabled = lambda h: h not in disabled
    c._post_close = c.posted.append
    return c


DESKTOP = (1, 4, "Program Manager")


def test_the_request_goes_to_the_instances_own_window_and_nothing_is_killed():
    c = _controller([(4, "explorer.exe"), (30, "notepad.exe"), (31, "notepad.exe")],
                    [DESKTOP, (300, 31, "Untitled - Notepad")])
    assert c.close_application("notepad") is True  # nosec B101
    assert c.posted == [300] and c._platform_integration.terminated == []  # nosec B101  terminated before


def test_every_window_of_that_instance_is_asked():
    c = _controller([(30, "notepad.exe")], [DESKTOP, (300, 30, "a.txt - Notepad"), (301, 30, "b.txt - Notepad")])
    c.close_application("notepad")
    assert c.posted == [300, 301]  # nosec B101


def test_only_one_instance_is_asked_to_close():
    # Closing has always meant one instance; it does not become "all of them".
    c = _controller([(30, "notepad.exe"), (31, "notepad.exe")],
                    [DESKTOP, (300, 30, "a.txt - Notepad"), (310, 31, "b.txt - Notepad")])
    c.close_application("notepad")
    assert c.posted == [300]  # nosec B101


def test_unrelated_windows_are_never_asked_even_with_the_name_in_their_title():
    c = _controller([(30, "notepad.exe"), (40, "chrome.exe"), (50, "notepad_helper.exe")],
                    [DESKTOP, (400, 40, "notepad - Google Search"), (500, 50, "Notepad"), (300, 30, "Untitled - Notepad")])
    c.close_application("notepad")
    assert c.posted == [300]  # nosec B101


def test_only_an_exact_executable_is_the_application():
    c = _controller([(50, "notepad_helper.exe"), (51, "mynotepad.exe")],
                    [DESKTOP, (500, 50, "Notepad"), (510, 51, "Notepad")])
    # No notepad.exe: taskkill /IM notepad.exe (exact) is the existing fallback; no window is asked.
    c._taskkill_by_name = lambda name, force=False: False
    assert c.close_application("notepad") is False and c.posted == []  # nosec B101


def test_an_open_dialog_is_not_closed_for_the_user():
    # WM_CLOSE to "Save changes?" would answer it with Cancel.
    c = _controller([(30, "notepad.exe")], [DESKTOP, (300, 30, "*a.txt - Notepad"), (301, 30, "Notepad")],
                    owners={301: 300}, disabled={300})
    c.close_application("notepad")
    assert c.posted == [300]  # nosec B101


def test_a_process_without_a_window_is_left_running():
    c = _controller([(30, "notepad.exe")], [DESKTOP])
    assert c.close_application("notepad") is False  # nosec B101
    assert c.posted == [] and c._platform_integration.terminated == []  # nosec B101


def test_a_request_that_cannot_be_posted_is_an_error():
    c = _controller([(30, "notepad.exe")], [DESKTOP, (300, 30, "Untitled - Notepad")])

    def broken(hwnd):
        raise OSError("PostMessage failed")

    c._post_close = broken
    with pytest.raises(OSError):
        c.close_application("notepad")
    assert c._platform_integration.terminated == []  # nosec B101


def test_a_protected_process_is_still_refused():
    c = _controller([(4, "explorer.exe")], [DESKTOP])
    with pytest.raises(ValueError, match="protected"):
        c.close_application("file explorer")
    assert c.posted == []  # nosec B101


def test_force_is_still_an_explicit_kill():
    c = _controller([(30, "notepad.exe")], [DESKTOP, (300, 30, "Untitled - Notepad")])
    c.close_application("notepad", force=True)
    assert c._platform_integration.terminated == [(30, True)] and c.posted == []  # nosec B101


def test_a_save_question_is_seen_as_waiting_for_the_user():
    c = _controller([(30, "notepad.exe")], [DESKTOP, (300, 30, "*a.txt - Notepad"), (301, 30, "Notepad")],
                    owners={301: 300}, disabled={300})
    assert c.app_awaiting_user("notepad") is True  # nosec B101


def test_a_tool_window_is_not_a_question():
    # Owned, but its owner stays usable: a find box or palette, not modal.
    c = _controller([(30, "notepad.exe")], [DESKTOP, (300, 30, "a.txt - Notepad"), (301, 30, "Find")],
                    owners={301: 300})
    assert c.app_awaiting_user("notepad") is False  # nosec B101


def test_another_applications_dialog_is_not_this_ones():
    c = _controller([(30, "notepad.exe"), (40, "chrome.exe")],
                    [DESKTOP, (300, 30, "a.txt - Notepad"), (400, 40, "Chrome"), (401, 40, "Leave site?")],
                    owners={401: 400}, disabled={400})
    assert c.app_awaiting_user("notepad") is False  # nosec B101


def test_waiting_cannot_be_told_off_windows_or_when_reading_fails():
    assert _controller([(30, "notepad.exe")], [DESKTOP], platform="linux").app_awaiting_user("notepad") is None  # nosec B101
    c = _controller([(30, "notepad.exe")], [DESKTOP, (300, 30, "Notepad")])

    def broken(h):
        raise OSError("gone")

    c._window_owner = broken
    assert c.app_awaiting_user("notepad") is None  # nosec B101
