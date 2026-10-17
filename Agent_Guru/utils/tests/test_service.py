"""The background assistant starts detached, stops through its own shutdown, and is ended only as a last resort.

A stand-in child runs the same announce / watch_for_stop / withdraw
calls main.py makes, in a data folder of its own, so no real assistant
(microphone, models, Ollama) starts.
"""

from __future__ import annotations

import os
import sys
import time

import pytest

from Agent_Guru.utils import service

pytestmark = pytest.mark.timeout(90)

_CHILD = """
import asyncio, pathlib, sys
from Agent_Guru.utils import service
async def main():
    service.announce()
    stop = asyncio.Event()
    if {obey}:
        await service.watch_for_stop(stop)
    else:
        await asyncio.sleep(120)
    pathlib.Path(sys.argv[1]).write_text("clean shutdown")
    service.withdraw()
asyncio.run(main())
"""


@pytest.fixture
def data(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA" if os.name == "nt" else "XDG_DATA_HOME", str(tmp_path))
    yield tmp_path
    running = service.state()
    if running:
        import psutil

        psutil.Process(running["pid"]).kill()


def _child(tmp_path, obey=True):
    return [sys.executable, "-c", _CHILD.format(obey=obey), str(tmp_path / "marker.txt")]


def test_start_status_and_a_clean_stop(data):
    started, said = service.start(_child(data))
    assert started and "running in the background" in said, said  # nosec B101
    pid = service.state()["pid"]
    assert service.start(_child(data))[0] is False  # nosec B101  a second copy is refused
    began = time.monotonic()
    stopped, said = service.stop()
    assert stopped and said == "Agent Guru stopped."  # nosec B101
    assert time.monotonic() - began < 10  # nosec B101
    # It ran its own shutdown (the line after the wait) rather than being killed.
    assert (data / "marker.txt").read_text() == "clean shutdown"  # nosec B101
    assert service.state() is None and not service._alive(pid)  # nosec B101


def test_one_that_ignores_the_request_is_ended_and_told(data):
    service.start(_child(data, obey=False))
    stopped, said = service.stop(wait_s=1.0)
    assert stopped and "was ended" in said  # nosec B101
    assert not (data / "marker.txt").exists()  # nosec B101


def test_a_dead_process_is_not_reported_as_running(data):
    (data / "agent_guru").mkdir(exist_ok=True)
    service.announce()
    # This test process is not an Agent Guru command line, and a stale
    # record of a reused id must not count either.
    record = service._data("service.json")
    record.write_text(record.read_text().replace(str(os.getpid()), "999999"))
    assert service.state() is None and service.stop() == (False, "Agent Guru is not running.")  # nosec B101


@pytest.mark.skipif(sys.platform != "win32", reason="a Windows shortcut")
def test_autostart_makes_and_removes_a_startup_shortcut(monkeypatch, tmp_path):
    entry = tmp_path / "Startup" / "Agent Guru.lnk"
    monkeypatch.setattr(service, "_startup_entry", lambda: entry)
    assert "will start at log-in" in service.autostart(True) and entry.exists()  # nosec B101
    import win32com.client

    link = win32com.client.Dispatch("WScript.Shell").CreateShortcut(str(entry))
    assert link.Arguments == "-m Agent_Guru service start" and link.TargetPath.lower().endswith(".exe")  # nosec B101
    assert "no longer" in service.autostart(False) and not entry.exists()  # nosec B101


def test_the_login_file_runs_the_assistant_from_the_project(monkeypatch):
    text = service.startup_file_text("/usr/bin/python3", "/home/me/Agent_Guru")
    assert "-m" in text and "Agent_Guru" in text and "/home/me/Agent_Guru" in text  # nosec B101
