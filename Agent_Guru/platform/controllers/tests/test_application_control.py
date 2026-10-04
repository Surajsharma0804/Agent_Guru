"""ApplicationController's process lookups ask only for what they use.

Finding an app to close by name, re-checking a pid against the protected set
before terminating it, and listing running applications read only pid and
name. They used to call get_process_list() with its default full read of
status, CPU and memory for every process; on Windows the two lookups of one
"close app" command took 12.83 s that way and 0.02 s without it. This module
had no tests before.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from Agent_Guru.platform.controllers.application_control import ApplicationController


class RecordingIntegration:
    """Stands in for the platform integration and records every list request."""

    def __init__(self, processes: list[tuple[int, str]]) -> None:
        self.processes = [SimpleNamespace(pid=p, name=n) for p, n in processes]
        self.calls: list[dict] = []

    def get_process_list(self, **kwargs):
        self.calls.append(kwargs)
        return self.processes


@pytest.fixture
def controller():
    c = ApplicationController.__new__(ApplicationController)
    c.platform = "win32"
    c._platform_integration = RecordingIntegration(
        [(4, "System"), (1200, "notepad.exe"), (3400, "Code.exe")],
    )
    return c


def test_find_by_name_reads_no_usage(controller):
    assert controller._find_process_by_name("notepad") == 1200  # nosec B101
    assert controller._platform_integration.calls == [{"include_usage": False}]  # nosec B101


def test_pid_recheck_reads_no_usage(controller):
    assert controller._get_process_name(3400) == "Code.exe"  # nosec B101
    assert controller._platform_integration.calls == [{"include_usage": False}]  # nosec B101


def test_unknown_name_and_pid(controller):
    assert controller._find_process_by_name("no-such-app") is None  # nosec B101
    assert controller._get_process_name(99999) is None  # nosec B101


def test_listing_applications_reads_no_usage(controller):
    controller.list_windows = lambda: []
    apps = controller.list_running_applications()
    assert {a.pid for a in apps} == {4, 1200, 3400}  # nosec B101
    assert controller._platform_integration.calls == [{"include_usage": False}]  # nosec B101
