"""Run the assistant in the background, stop it cleanly, and start it when the owner logs in.

The assistant only ran in a console window: closing the window or
logging off ended it, and nothing started it again. `python -m
Agent_Guru service start` runs it detached with no window; `stop` asks it
to shut down the way Ctrl+C does; `status` says whether it runs;
`autostart on` starts it at log-in.

Stopping is a request, not a kill. On Windows another process cannot
deliver SIGTERM (os.kill is TerminateProcess) and a windowless process
gets no Ctrl+Break, so the assistant would end without stopping its
MCP servers, its scheduler lock or the speech engine. Instead the
running assistant records its process id at start (announce()) and
watches for a stop file (watch_for_stop()); `stop` writes that file and
waits. Only if the assistant has not ended after 30 s is it terminated,
and the command says so.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess  # nosec B404 - starts this interpreter with fixed arguments
import sys
import time
from pathlib import Path
from typing import Any

_STATE = "service.json"
# With a suffix: app_data_dir() creates a name without one as a folder,
# which "existed" at once and stopped the assistant as it started.
_STOP = "stop-request.txt"
STOP_WAIT_S = 30.0
_POLL_S = 1.0
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _data(name: str) -> Path:
    from Agent_Guru.utils.path_utils import app_data_dir

    return app_data_dir(name)


def _alive(pid: int) -> bool:
    """Whether *pid* is a running Agent Guru (a reused process id is not taken for it)."""
    try:
        import psutil

        process = psutil.Process(pid)
        return process.is_running() and any("Agent_Guru" in part or "main.py" in part for part in process.cmdline())
    except Exception:
        return False


def _started_by(pid: int, launched: int) -> bool:
    """Whether *pid* is the launched process or one it started.

    A venv's python.exe on Windows is a launcher that runs the real
    interpreter as its child, so the process that announces itself is not
    the one Popen returned; start() reported "not reported in yet" for an
    assistant that was running.
    """
    try:
        import psutil

        process: Any = psutil.Process(pid)
        for _ in range(4):
            if process is None:
                return False
            if process.pid == launched:
                return True
            process = process.parent()
    except Exception:
        return False
    return False


def state() -> dict[str, Any] | None:
    """The running assistant's record, or None when none runs."""
    try:
        recorded = json.loads(_data(_STATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return recorded if isinstance(recorded, dict) and _alive(int(recorded.get("pid", 0))) else None


def announce() -> None:
    """Called by the assistant at start: record this process, and drop a stop request left from before."""
    with contextlib.suppress(OSError):
        _data(_STOP).unlink()
    _data(_STATE).write_text(json.dumps({"pid": os.getpid(), "started": time.time(),
                                         "command": sys.argv}), encoding="utf-8")


def withdraw() -> None:
    """Called by the assistant at a clean exit."""
    for name in (_STATE, _STOP):
        with contextlib.suppress(OSError):
            path = _data(name)
            if name == _STOP or json.loads(path.read_text(encoding="utf-8")).get("pid") == os.getpid():
                path.unlink()


async def watch_for_stop(stop: asyncio.Event) -> None:
    """Set *stop* once a stop request appears; the assistant then shuts down as on Ctrl+C."""
    path = _data(_STOP)
    while not stop.is_set():
        if path.exists():
            stop.set()
            return
        await asyncio.sleep(_POLL_S)


def _interpreter() -> str:
    """pythonw on Windows, so no console window opens; the same interpreter otherwise."""
    exe = Path(sys.executable)
    windowless = exe.with_name("pythonw.exe")
    return str(windowless) if sys.platform == "win32" and windowless.exists() else str(exe)


def start(command: list[str] | None = None, wait_s: float = 20.0) -> tuple[bool, str]:
    """Start the assistant in the background unless it runs; (started, what happened)."""
    running = state()
    if running:
        return False, f"Agent Guru is already running (process {running['pid']})."
    with contextlib.suppress(OSError):
        _data(_STOP).unlink()
    argv = command or [_interpreter(), "-m", "Agent_Guru"]
    log = _data("service.log").open("ab")
    kwargs: dict[str, Any] = {"cwd": str(_PROJECT_ROOT), "stdin": subprocess.DEVNULL, "stdout": log, "stderr": log}
    if sys.platform == "win32":
        kwargs["creationflags"] = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                                   | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        kwargs["start_new_session"] = True
    child = subprocess.Popen(argv, **kwargs)  # nosec B603 - fixed interpreter and arguments
    log.close()
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        if child.poll() is not None:
            return False, f"Agent Guru exited at start (code {child.returncode}); see {_data('service.log')}"
        running = state()
        if running and _started_by(int(running["pid"]), child.pid):
            return True, f"Agent Guru is running in the background (process {running['pid']})."
        time.sleep(0.25)
    return True, f"Agent Guru was started (process {child.pid}) but has not reported in yet; see {_data('service.log')}"


def stop(wait_s: float = STOP_WAIT_S) -> tuple[bool, str]:
    """Ask the running assistant to shut down; (stopped, what happened)."""
    running = state()
    if not running:
        return False, "Agent Guru is not running."
    pid = int(running["pid"])
    _data(_STOP).write_text(str(time.time()), encoding="utf-8")
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True, "Agent Guru stopped."
        time.sleep(0.25)
    import psutil

    with contextlib.suppress(psutil.Error):
        psutil.Process(pid).terminate()
    return True, f"Agent Guru did not stop within {wait_s:.0f} s and was ended; its last state may not be saved."


# --- Start at log-in -------------------------------------------------------

def _startup_entry() -> Path:
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Agent Guru.lnk"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "LaunchAgents" / "com.agentguru.assistant.plist"
    return Path.home() / ".config" / "systemd" / "user" / "agent-guru.service"


def startup_file_text(python: str, project: str) -> str:
    """The launchd or systemd file that starts the assistant at log-in (Windows uses a shortcut)."""
    if sys.platform == "darwin":
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.agentguru.assistant</string>
  <key>ProgramArguments</key><array><string>{python}</string><string>-m</string><string>Agent_Guru</string></array>
  <key>WorkingDirectory</key><string>{project}</string>
  <key>RunAtLoad</key><true/>
</dict></plist>
"""
    return f"""[Unit]
Description=Agent Guru assistant

[Service]
WorkingDirectory={project}
ExecStart={python} -m Agent_Guru
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


def autostart(on: bool) -> str:
    entry = _startup_entry()
    if not on:
        if entry.exists():
            entry.unlink()
            return f"Agent Guru will no longer start at log-in ({entry} removed)."
        return "Agent Guru was not set to start at log-in."
    entry.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        import win32com.client  # type: ignore[import-untyped]

        link = win32com.client.Dispatch("WScript.Shell").CreateShortcut(str(entry))
        link.TargetPath = _interpreter()
        link.Arguments = "-m Agent_Guru service start"
        link.WorkingDirectory = str(_PROJECT_ROOT)
        link.Description = "Start Agent Guru in the background"
        link.Save()
    else:
        entry.write_text(startup_file_text(sys.executable, str(_PROJECT_ROOT)), encoding="utf-8")
    how = "" if sys.platform == "win32" else (
        " Load it with: launchctl load " + str(entry) if sys.platform == "darwin"
        else " Enable it with: systemctl --user enable --now agent-guru")
    return f"Agent Guru will start at log-in ({entry}).{how}"


def run(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m Agent_Guru service",
                                     description="Run Agent Guru in the background and start it at log-in.")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("start", help="start it in the background, with no window")
    sub.add_parser("stop", help="ask it to shut down, as Ctrl+C does")
    sub.add_parser("status", help="whether it is running")
    auto = sub.add_parser("autostart", help="start it when you log in, or stop doing so")
    auto.add_argument("switch", choices=["on", "off"])
    args = parser.parse_args(argv)
    if args.action == "status":
        running = state()
        if running:
            since = time.strftime("%Y-%m-%d %H:%M", time.localtime(running.get("started", 0)))
            print(f"Agent Guru is running (process {running['pid']}, since {since}).")  # noqa: T201
        else:
            print("Agent Guru is not running.")  # noqa: T201
        print(f"Starts at log-in: {'yes' if _startup_entry().exists() else 'no'}")  # noqa: T201
        return 0 if running else 1
    if args.action == "autostart":
        print(autostart(args.switch == "on"))  # noqa: T201
        return 0
    ok, said = start() if args.action == "start" else stop()
    print(said)  # noqa: T201
    return 0 if ok else 1
