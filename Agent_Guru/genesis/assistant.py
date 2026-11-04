"""The running assistant, seen from outside it: is it up, where is its window, ask it to stop.

The installer used to know about the assistant only at the moment it started
one. With the assistant starting at sign-in, the shortcut, the installer and
the uninstaller all meet one that is already running: the shortcut started a
second assistant on the same microphone, and an uninstall tried to delete
files the running one held open. Standard library only: the frozen launcher
imports this.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from Agent_Guru.genesis.layout import Layout

#: How long a started assistant may take to open its window before another may
#: be started. The real run took 14.2 s; a machine at sign-in is slower.
START_GRACE_S = 180.0


def workspace_file(layout: Layout) -> Path:
    return layout.runtime_root / "workspace.json"


def pid_file(layout: Layout) -> Path:
    return layout.runtime_root / "assistant.pid"


def _process_alive(pid: int) -> bool:
    if sys.platform == "win32":
        # os.kill(pid, 0) is not a query on Windows: signal 0 is CTRL_C_EVENT.
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel.CloseHandle(handle)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _record(layout: Layout) -> dict[str, str]:
    try:
        data = json.loads(workspace_file(layout).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _origin(url: str) -> str:
    return url.split("/workspace.html", 1)[0].split("/#", 1)[0]


def window_url(layout: Layout) -> str:
    """The running assistant's window address, or "" when nothing answers at it.

    Asked of the server, because the file survives a crash and a dead address
    would open a blank window.
    """
    url = str(_record(layout).get("url") or "")
    if not url.startswith("http://127.0.0.1:"):
        return ""
    try:
        with urllib.request.urlopen(_origin(url) + "/ui/tokens.css", timeout=2):  # noqa: S310  # nosec B310 - loopback only
            return url
    except OSError:
        return ""


def starting(layout: Layout) -> bool:
    """True while an assistant started moments ago is still loading and has no window yet."""
    path = pid_file(layout)
    try:
        return time.time() - path.stat().st_mtime < START_GRACE_S and _process_alive(int(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return False


def remember(layout: Layout, pid: int | None) -> None:
    if pid:
        pid_file(layout).write_text(str(pid), encoding="utf-8")


def request_quit(layout: Layout, wait_s: float = 35.0) -> bool:
    """Ask the running assistant to shut down the way Ctrl+C does; True when it was asked and has gone."""
    url = window_url(layout)
    token = url.rsplit("#t=", 1)[-1] if "#t=" in url else ""
    if not token:
        return False
    origin = _origin(url)
    request = urllib.request.Request(origin + "/api/quit", data=b"{}", method="POST",  # noqa: S310
                                     headers={"Content-Type": "application/json", "X-Genesis-Token": token, "Origin": origin})
    try:
        with urllib.request.urlopen(request, timeout=5):  # noqa: S310  # nosec B310 - loopback only
            pass
    except (urllib.error.URLError, OSError):
        return False
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        if not window_url(layout):
            return True
        time.sleep(0.25)
    return False
