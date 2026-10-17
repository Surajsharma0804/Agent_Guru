"""Run model-written Python inside WSL, behind a boundary that was attacked before it was trusted.

SkillSandbox's process mode is no boundary on Windows: code it runs can
read the owner's documents and keys, write anywhere the owner can, open
network connections (Ollama on localhost included) and start any
program. Windows 11 Home has no Windows Sandbox; an AppContainer launcher
was tried and CreateProcessW failed with error 203, so it never ran.

Here each run is a transient systemd service in a WSL2 distribution
(default "Ubuntu", AGENT_GURU_SANDBOX_DISTRO) that has drive automount and
Windows interop switched off in /etc/wsl.conf. The service runs as the
unprivileged user agsandbox with:

* no network: no address family but AF_UNIX, in a private network namespace;
* no files of anyone's: /home, /root, /mnt, /run, /var, /opt, /srv and the
  Windows driver share hidden, /etc and /usr read-only, its own empty /tmp
  that is gone after the run, /init (WSL's own init) inaccessible, /sys
  closed except the cgroup view;
* no processes but its own (private PID namespace) and no devices but
  null, zero, random, urandom and a tty;
* no privileges: no capabilities, no new privileges (sudo refuses), no
  setuid, no new namespaces, no mount, ptrace or module system calls;
* limits: memory (no swap), 32 tasks, one CPU, files up to 64 MB, a wall
  clock after which it is killed with SIGKILL (Python is PID 1 in its
  namespace and would ignore SIGTERM, which made a 5 s limit take 96 s).

Each property was checked by trying to break it from inside (see
tests/test_wsl_sandbox_boundary.py). What it cannot stop: reading files
any local user may read in the distribution's own /etc and /usr, and
using its CPU and memory share for as long as the run is allowed.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
import shutil
import subprocess  # nosec B404 - fixed wsl.exe arguments, no shell
import time
import uuid
from dataclasses import dataclass

from Agent_Guru.reasoning.tools.skills.sandbox import _kill_and_wait, _read_stream_capped

SANDBOX_USER = "agsandbox"
DISTRO_ENV = "AGENT_GURU_SANDBOX_DISTRO"
DEFAULT_DISTRO = "Ubuntu"
MAX_CODE_CHARS = 50_000
MAX_OUTPUT_BYTES = 256 * 1024
#: Starting WSL when its VM is stopped takes several seconds before the run begins.
_START_GRACE_S = 20.0

_RESULT = re.compile(r"^\s*Finished with result: ([a-z-]+)\s*$", re.MULTILINE)
_STATUS = re.compile(r"^Main processes terminated with: code=(\w+), status=(\d+)", re.MULTILINE)
_UNIT_LINE = re.compile(r"\ARunning as unit: [^\n]*\n")

# Hidden from the service. /init is WSL's init, a way back to the host;
# /usr/lib/wsl holds the Windows driver share; the rest hold other users'
# files or host state.
_HIDDEN_DIRS = "/mnt:ro /run:ro /usr/lib/wsl:ro /srv:ro /media:ro /opt:ro /var:ro /boot:ro"
_INACCESSIBLE = (
    "/init /sys/firmware /sys/devices /sys/class /sys/bus /sys/block /sys/dev /sys/module /sys/power /sys/kernel"
)
_DENIED_CALLS = "~@privileged @resources @mount @debug @module @reboot @swap @obsolete @cpu-emulation @clock @raw-io"


@dataclass(slots=True)
class SandboxRun:
    """How one run ended. *result* is systemd's word: success, exit-code, timeout, oom-kill, signal...

    "unavailable" means nothing ran; "output-limit" that the run printed
    more than MAX_OUTPUT_BYTES and was ended.
    """

    result: str
    exit_code: int | None
    stdout: str
    stderr: str
    seconds: float

    @property
    def ok(self) -> bool:
        return self.result == "success"


def distro() -> str:
    return os.environ.get(DISTRO_ENV, "").strip() or DEFAULT_DISTRO


def service_properties(seconds: int, memory_mb: int) -> list[str]:
    """The systemd-run -p arguments that make the boundary."""
    props = [
        f"User={SANDBOX_USER}", f"Group={SANDBOX_USER}",
        "WorkingDirectory=/tmp", "Environment=HOME=/tmp", "Environment=LANG=C.UTF-8",
        "PrivateNetwork=yes", "PrivateDevices=yes", "PrivateTmp=yes", "PrivateIPC=yes", "PrivatePIDs=yes",
        "ProtectHome=tmpfs", "ProtectSystem=strict", "ProtectHostname=private:sandbox", "ProtectClock=yes",
        "ProtectKernelTunables=yes", "ProtectKernelModules=yes", "ProtectKernelLogs=yes",
        "ProtectControlGroups=yes", "ProtectProc=invisible", "ProcSubset=pid",
        f"TemporaryFileSystem={_HIDDEN_DIRS}", f"InaccessiblePaths={_INACCESSIBLE}",
        "RestrictNamespaces=yes", "NoNewPrivileges=yes", "CapabilityBoundingSet=", "AmbientCapabilities=",
        "RestrictSUIDSGID=yes", "LockPersonality=yes", "RestrictRealtime=yes", "RemoveIPC=yes",
        "RestrictAddressFamilies=AF_UNIX",
        "SystemCallFilter=@system-service", f"SystemCallFilter={_DENIED_CALLS}",
        # A denied call fails with EPERM instead of killing the process,
        # which lost everything it had printed so far.
        "SystemCallArchitectures=native", "SystemCallErrorNumber=EPERM", "UMask=0077",
        f"MemoryMax={memory_mb}M", "MemorySwapMax=0", "TasksMax=32", "CPUQuota=100%",
        f"RuntimeMaxSec={seconds}", "KillSignal=SIGKILL", "TimeoutStopSec=1",
        "LimitFSIZE=64M", "LimitNOFILE=256", "LimitCORE=0",
    ]
    out: list[str] = []
    for prop in props:
        out += ["-p", prop]
    return out


def run_command(seconds: int, memory_mb: int, wsl: str = "wsl.exe", unit: str = "agent-guru-sandbox") -> list[str]:
    """The wsl.exe argv for one run; the code goes on stdin. --exec: no shell anywhere."""
    return [
        wsl, "-d", distro(), "-u", "root", "--exec",
        "systemd-run", f"--unit={unit}", "--pipe", "--wait", "--collect", "--service-type=exec",
        *service_properties(seconds, memory_mb),
        "/usr/bin/python3", "-I", "-u", "-",
    ]


def parse_result(stderr: str) -> tuple[str, int | None, str]:
    """(result, exit code, the program's own stderr) from systemd-run's stderr.

    systemd prints its summary after the program has ended, so the last
    "Finished with result" is systemd's even if the program printed one.
    """
    results = _RESULT.findall(stderr)
    if not results:
        return "unknown", None, stderr
    statuses = _STATUS.findall(stderr)
    code = int(statuses[-1][1]) if statuses and statuses[-1][0] == "exited" else None
    last = list(_RESULT.finditer(stderr))[-1].start()
    own = _UNIT_LINE.sub("", stderr[:last], count=1)
    return results[-1], code, own.rstrip("\n")


async def run_python(code: str, *, seconds: int = 10, memory_mb: int = 256) -> SandboxRun:
    """Run *code* in the boundary and return how it ended; never raises for a failed run."""
    started = time.monotonic()
    if len(code) > MAX_CODE_CHARS:
        return SandboxRun("unavailable", None, "", f"code longer than {MAX_CODE_CHARS} characters", 0.0)
    wsl = shutil.which("wsl.exe") or shutil.which("wsl")
    if wsl is None:
        return SandboxRun("unavailable", None, "", "WSL is not installed", 0.0)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    unit = f"agent-guru-sandbox-{uuid.uuid4().hex[:16]}"
    process = await asyncio.create_subprocess_exec(
        *run_command(seconds, memory_mb, wsl, unit),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        creationflags=flags,
    )
    assert process.stdin is not None  # nosec B101 - created with PIPE above
    process.stdin.write(code.encode("utf-8"))
    process.stdin.close()
    # Each stream on its own, woken by whichever ends first: waiting for both
    # together left a capped stdout waiting on a stderr that could not close
    # while the program kept writing, and a flood ended as a timeout.
    out_task = asyncio.ensure_future(_read_stream_capped(process.stdout, MAX_OUTPUT_BYTES))
    err_task = asyncio.ensure_future(_read_stream_capped(process.stderr, MAX_OUTPUT_BYTES))
    pending: set[asyncio.Future] = {out_task, err_task}
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds + _START_GRACE_S
    while pending:
        done, pending = await asyncio.wait(pending, timeout=max(0.0, deadline - loop.time()),
                                           return_when=asyncio.FIRST_COMPLETED)
        cut = any(task.result()[1] for task in done)
        if not done or cut:
            for task in pending:
                task.cancel()
            await _stop(wsl, process, unit)
            if cut:
                out = out_task.result()[0] if out_task.done() and not out_task.cancelled() else b""
                return SandboxRun("output-limit", None, out.decode("utf-8", "replace"), "", time.monotonic() - started)
            # systemd ends the service at RuntimeMaxSec; this covers a WSL that never answered.
            return SandboxRun("timeout", None, "", "WSL did not finish the run", time.monotonic() - started)
    out, err = out_task.result()[0], err_task.result()[0]
    await _kill_and_wait(process)
    result, code_, own = parse_result(err.decode("utf-8", "replace"))
    if result == "unknown":
        # systemd-run itself failed (no such user, no systemd, distribution missing).
        return SandboxRun("unavailable", process.returncode, "", own.strip()[-500:], time.monotonic() - started)
    return SandboxRun(result, code_, out.decode("utf-8", "replace"), own, time.monotonic() - started)


async def _stop(wsl: str, process: asyncio.subprocess.Process, unit: str) -> None:
    """End a run early: the service inside WSL as well, which outlives a killed wsl.exe until its time limit."""
    with contextlib.suppress(ProcessLookupError):
        process.kill()
    await _kill_and_wait(process)
    killer = await asyncio.create_subprocess_exec(
        wsl, "-d", distro(), "-u", "root", "--exec", "systemctl", "kill", "--signal=SIGKILL", f"{unit}.service",
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        await asyncio.wait_for(killer.wait(), timeout=15)
    except TimeoutError:
        killer.kill()
        await _kill_and_wait(killer)


#: The boundary's preconditions, checked as root in the distribution. Prints one problem per line.
_CHECK_SCRIPT = f"""
id -u {SANDBOX_USER} >/dev/null 2>&1 || echo "no user {SANDBOX_USER}: run 'python -m Agent_Guru sandbox setup'"
[ "$(ps -p 1 -o comm=)" = systemd ] || echo "systemd is not running: set [boot] systemd=true in /etc/wsl.conf"
ls /proc/sys/fs/binfmt_misc/ 2>/dev/null | grep -qi wslinterop && echo "Windows interop is on: set [interop] enabled=false in /etc/wsl.conf"
grep -qs ' /mnt/[a-z] ' /proc/mounts && echo "Windows drives are mounted: set [automount] enabled=false in /etc/wsl.conf"
command -v python3 >/dev/null || echo "python3 is not installed in the distribution"
true
"""

_checked_ok = False


def check(timeout: float = 60.0) -> list[str]:
    """Problems that stop the boundary from being trusted on this machine; [] when it can be used."""
    global _checked_ok
    if _checked_ok:
        return []
    wsl = shutil.which("wsl.exe") or shutil.which("wsl")
    if wsl is None:
        return ["WSL is not installed"]
    try:
        done = subprocess.run(  # nosec B603 - fixed script, no shell on this side
            [wsl, "-d", distro(), "-u", "root", "--exec", "/bin/sh", "-c", _CHECK_SCRIPT],
            capture_output=True, timeout=timeout, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [f"WSL did not answer: {exc}"]
    if done.returncode != 0:
        # wsl.exe writes its own errors (an unknown distribution) in UTF-16.
        text = done.stdout.replace(b"\0", b"") + done.stderr.replace(b"\0", b"")
        return [f"WSL distribution {distro()!r} could not run: {text.decode('utf-8', 'replace').strip()[:300]}"]
    problems = [line for line in done.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
    _checked_ok = not problems
    return problems


def setup(timeout: float = 120.0) -> list[str]:
    """Create the sandbox user if it is missing, then check; returns the problems left."""
    wsl = shutil.which("wsl.exe") or shutil.which("wsl")
    if wsl is None:
        return ["WSL is not installed"]
    script = (
        f"id -u {SANDBOX_USER} >/dev/null 2>&1 || "
        f"useradd --system --no-create-home --shell /usr/sbin/nologin {SANDBOX_USER}"
    )
    subprocess.run(  # nosec B603 - fixed script
        [wsl, "-d", distro(), "-u", "root", "--exec", "/bin/sh", "-c", script],
        capture_output=True, timeout=timeout, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return check()
