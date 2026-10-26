"""An application name never reaches cmd.exe as commands of its own.

DesktopApplicationController falls back to `cmd /c start "" <name>` when
os.startfile cannot open a name. cmd reads that line again, so "notepad>x"
(an app name the intent engine passes on for "open notepad>x.txt")
redirected into a file and "notepad&whoami" ran whoami. Nothing is launched
here: os.startfile fails on purpose and the cmd launch is recorded instead.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from Agent_Guru.platform.controllers import desktop_app_controller
from Agent_Guru.platform.controllers.desktop_app_controller import DesktopApplicationController


@pytest.fixture
def launches(monkeypatch):
    made: list[tuple[str, ...]] = []

    def no_startfile(name):
        raise OSError(f"not found: {name}")

    class Done:
        returncode = 0

        async def wait(self):
            return 0

    async def record(*argv, **kwargs):
        made.append(argv)
        return Done()

    monkeypatch.setattr(os, "startfile", no_startfile, raising=False)
    monkeypatch.setattr(desktop_app_controller.asyncio, "create_subprocess_exec", record)
    return made


@pytest.mark.parametrize("name", ["notepad>x", "notepad&whoami", "notepad^&whoami", "%COMSPEC%", 'x"&whoami&"',
                                  "notepad|whoami", "notepad<x", "notepad\r\nwhoami"])
def test_a_name_cmd_would_act_on_is_not_given_to_cmd(launches, name):
    controller = DesktopApplicationController()
    opened = asyncio.run(controller._open_windows(name))
    assert opened is False and launches == []  # nosec B101


@pytest.mark.parametrize("name", ["notepad", "visual studio code", "Microsoft Edge"])
def test_an_ordinary_name_still_falls_back_to_start(launches, name):
    controller = DesktopApplicationController()
    assert asyncio.run(controller._open_windows(name)) is True  # nosec B101
    assert launches == [("cmd", "/c", "start", "", name)]  # nosec B101
