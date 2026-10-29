"""Closing the console window stops the assistant the way Ctrl+C does.

It ended the process at once: the shutdown in run() never ran, so the microphone was not released
and the stores were not closed. The child here is run under conhost, whose window takes WM_CLOSE
as clicking X does, and sends the real CTRL_CLOSE_EVENT; it waits on the same stop event as run()
and records its shutdown in SQLite before it ends.
"""

from __future__ import annotations

import sqlite3
import subprocess  # nosec B404 - this interpreter on fixed scripts
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="console control events are Windows only")

ROOT = Path(__file__).resolve().parents[3]

_CHILD = """
import asyncio, sqlite3, sys
sys.path.insert(0, {root!r})
import main

async def run():
    stop_event = asyncio.Event()
    registered = main._on_console_close(asyncio.get_running_loop(), stop_event)
    db = sqlite3.connect({db!r})
    db.execute("create table if not exists log (what text)")
    db.execute("insert into log values (?)", ("ready" if registered else "not registered",))
    db.commit()
    await stop_event.wait()
    db.execute("insert into log values ('shut down cleanly')")
    db.commit()
    db.close()
    main._end_without_native_teardown()

asyncio.run(run())
"""

_CLOSE = """
import ctypes, sys
k, u = ctypes.windll.kernel32, ctypes.windll.user32
k.FreeConsole()
if not k.AttachConsole(int(sys.argv[1])):
    sys.exit(1)
hwnd = k.GetConsoleWindow()
k.FreeConsole()
sys.exit(0 if u.PostMessageW(hwnd, 0x0010, 0, 0) else 2)  # WM_CLOSE, as clicking X
"""


def _log(db: Path) -> list[str]:
    if not db.exists():
        return []
    with sqlite3.connect(db) as conn:
        try:
            return [r[0] for r in conn.execute("select what from log")]
        except sqlite3.OperationalError:
            return []


def test_closing_the_console_runs_the_clean_shutdown(tmp_path):
    db = tmp_path / "state.db"
    script = tmp_path / "child.py"
    script.write_text(_CHILD.format(root=str(ROOT), db=str(db)), encoding="utf-8")
    console = subprocess.Popen(["conhost.exe", sys.executable, str(script)], cwd=ROOT)  # noqa: S603  # nosec B603 B607
    try:
        deadline = time.monotonic() + 60
        while "ready" not in _log(db) and time.monotonic() < deadline:
            time.sleep(0.2)
        assert _log(db) == ["ready"], _log(db)  # nosec B101
        child = _child_pid(script)
        closer = subprocess.run([sys.executable, "-c", _CLOSE, str(child)], check=False, timeout=30)  # noqa: S603  # nosec B603
        assert closer.returncode == 0  # nosec B101
        started = time.monotonic()
        console.wait(timeout=15)
        assert _log(db) == ["ready", "shut down cleanly"]  # nosec B101
        assert time.monotonic() - started < 5  # nosec B101  inside the time Windows gives
    finally:
        if console.poll() is None:
            console.kill()


def _child_pid(script: Path) -> int:
    """The interpreter running *script*, found by its command line."""
    out = subprocess.run(  # noqa: S603  # nosec B603 B607
        ["powershell", "-NoProfile", "-Command",
         f"(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {{ $_.CommandLine -like '*{script.name}*' "
         f"-and $_.CommandLine -like '*{script.parent.name}*' }}).ProcessId"],
        capture_output=True, text=True, check=False, timeout=60,
    ).stdout.split()
    assert out, "the child interpreter was not found"  # nosec B101
    return int(out[-1])
