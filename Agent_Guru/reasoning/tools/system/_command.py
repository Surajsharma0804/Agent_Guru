"""Shared async subprocess execution for the system tool modules.

Consolidates the ``asyncio.create_subprocess_exec`` pattern that
``process_control.py`` already established in this package, and adds the
bounded timeout and reliable child termination that every call site in this
package was missing.

Why this module exists
----------------------
``system_control.py`` and ``app_control.py`` previously called
``subprocess.run()`` **synchronously from inside ``async def`` methods**,
blocking the entire asyncio event loop for the full duration of the child
process -- measured as total starvation of a 50ms heartbeat across a 0.6s
command -- which freezes speech capture, TTS playback, UI and every other
concurrent task.

``process_control.py`` was already structurally correct
(``create_subprocess_exec``), but *no* call site anywhere in the package
passed a timeout, so a wedged child (a hung ``netsh``/``nmcli``, or an
unanswered UAC/polkit elevation prompt) waited forever.

Fixing this at the root here, rather than repeating the same correction at
nineteen call sites, keeps one implementation to reason about.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import sys

logger = logging.getLogger(__name__)

# Generous relative to the tools' own declared `estimated_latency_ms`
# (200-500ms) while still bounding the worst case: PowerShell cold start alone
# can be 1-3s, and `netsh interface set interface` can take 5-10s on Windows.
DEFAULT_COMMAND_TIMEOUT_S = 20.0

# Cap on post-kill reaping, so cleanup can never become a new source of hangs.
_REAP_TIMEOUT_S = 5.0

_IS_WINDOWS = sys.platform == "win32"


async def _terminate_tree(proc: asyncio.subprocess.Process) -> None:
    """Kill a timed-out child **and every process it spawned**.

    Killing only the direct child is not sufficient and was measured failing:
    a child that has spawned its own helpers leaves those grandchildren alive
    still holding the inherited stdout/stderr pipes open, so the pipes never
    reach EOF, the read never completes, and the "cleanup" itself stalls until
    its own cap while leaking an orphaned process. Real commands used by this
    package do exactly this -- `powershell`, `nmcli` and `networksetup` all
    spawn helpers.
    """
    if proc.returncode is not None:
        return

    if _IS_WINDOWS:
        # Windows has no process groups in the POSIX sense; taskkill /T is the
        # supported way to terminate a whole tree. Spawned asynchronously so
        # cleanup does not reintroduce event-loop blocking.
        with contextlib.suppress(Exception):
            killer = await asyncio.create_subprocess_exec(
                "taskkill",
                "/F",
                "/T",
                "/PID",
                str(proc.pid),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait({asyncio.ensure_future(killer.wait())}, timeout=_REAP_TIMEOUT_S)
        return

    # POSIX: the child was started in its own session/process group (see
    # run_cmd_async), so one signal reaches the entire tree.
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        return
    with contextlib.suppress(ProcessLookupError):
        proc.kill()


async def run_cmd_async(
    args: list[str],
    *,
    timeout: float = DEFAULT_COMMAND_TIMEOUT_S,
) -> tuple[int, str, str]:
    """Run a command without blocking the event loop, bounded by a timeout.

    Args:
        args: Command and arguments to execute.
        timeout: Maximum seconds to wait before killing the child process tree.

    Returns:
        Tuple of (returncode, stdout, stderr).

    Raises:
        TimeoutError: If the command exceeds ``timeout``. The child and all of
            its descendants are killed and reaped first, so nothing is leaked.
        FileNotFoundError: If the executable does not exist.

    """
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        # Own process group, so a timeout can take down helper processes the
        # command spawned rather than orphaning them.
        **({} if _IS_WINDOWS else {"start_new_session": True}),
    )

    # communicate() runs as its own task awaited via asyncio.wait(), which
    # reports a timeout WITHOUT cancelling it. That distinction matters:
    # cancelling communicate() mid-flight (what asyncio.wait_for does) tears
    # down the transport's pipe readers half-way, after which the child may
    # never be reaped. Leaving the task alive means that once the tree is
    # killed below, the pipes reach EOF and this same task finishes the reap.
    comm = asyncio.ensure_future(proc.communicate())
    done, _pending = await asyncio.wait({comm}, timeout=timeout)

    if comm not in done:
        await _terminate_tree(proc)
        with contextlib.suppress(Exception):
            await asyncio.wait({comm}, timeout=_REAP_TIMEOUT_S)
        if not comm.done():
            comm.cancel()
        # Only the executable name is included: the remaining argv can carry
        # user-supplied values (application names, paths), which do not belong
        # in an error string that propagates outward.
        logger.warning("Command timed out after %.1fs: %s", timeout, args[0])
        msg = f"Command timed out after {timeout:.1f}s: {args[0]}"
        raise TimeoutError(msg) from None

    stdout_bytes, stderr_bytes = comm.result()
    return (
        proc.returncode or 0,
        stdout_bytes.decode("utf-8", errors="replace"),
        stderr_bytes.decode("utf-8", errors="replace"),
    )
