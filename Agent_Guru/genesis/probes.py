"""Read-only facts about this machine, for the scan screen and the planner.

Every probe returns a Probe: a value, or "unknown" with the reason, or
"unsupported" on a platform it cannot read. None of them guesses: a number
that could not be read is unknown, never a default. None of them writes
anything, changes a setting or installs anything. The registry is only read
(winreg, read access) and only for WebView2's version.

Hardware facts never leave the machine. The only network traffic is to the
local Ollama (its version and model list) and a TCP connect, with nothing
sent, to each host a plan downloads from, so the plan can say which are
reachable.

Every outside call goes through Seams, so the tests run fake machines (no
GPU, a 4 GB GPU, no Python, offline) without touching this one.
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import re
import shutil
import socket
import subprocess  # nosec B404 - fixed argument lists to known programs, never a shell
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

OK, UNKNOWN, UNSUPPORTED = "ok", "unknown", "unsupported"

#: The Python versions a managed runtime may be built from. pyproject.toml
#: requires >=3.11,<3.14: kokoro-onnx has no release for 3.14.
COMPATIBLE_PYTHON = ((3, 11), (3, 12), (3, 13))

_WEBVIEW2_CLIENT = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


@dataclass
class Probe:
    id: str
    label: str
    status: str
    value: Any = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ok(id_: str, label: str, value: Any) -> Probe:
    return Probe(id_, label, OK, value)


def unknown(id_: str, label: str, reason: str) -> Probe:
    return Probe(id_, label, UNKNOWN, None, reason)


def unsupported(id_: str, label: str, reason: str) -> Probe:
    return Probe(id_, label, UNSUPPORTED, None, reason)


def _run(args: list[str], timeout: float = 10.0) -> tuple[int, str]:
    """Run a fixed program with an argument list (never a shell); (exit code, stdout)."""
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False,  # nosec B603
                              encoding="utf-8", errors="replace",
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, f"{type(exc).__name__}: {exc}"
    return done.returncode, done.stdout


def _http_json(url: str, timeout: float = 3.0, body: dict | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310  # nosec B310 - local Ollama only
        return json.loads(response.read().decode("utf-8"))


def _tcp(host: str, port: int, timeout: float = 3.0) -> str:
    """"" when a TCP connection opens; otherwise why not. Nothing is sent."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return ""
    except OSError as exc:
        return f"{type(exc).__name__}: {exc}"


@dataclass
class Seams:
    """Everything a probe asks the outside world, replaceable in tests."""

    run: Callable[[list[str], float], tuple[int, str]] = _run
    http_json: Callable[..., Any] = _http_json
    tcp: Callable[[str, int, float], str] = _tcp
    which: Callable[[str], str | None] = shutil.which
    system: Callable[[], str] = platform.system
    env: Callable[[str], str | None] = os.environ.get
    disk_free: Callable[[Path], int] = lambda p: shutil.disk_usage(p).free
    memory: Callable[[], tuple[int, int] | None] = lambda: _memory()
    exists: Callable[[Path], bool] = lambda p: p.exists()
    webview2_version: Callable[[], str | None] = lambda: _webview2_version()
    audio_counts: Callable[[], tuple[int, int] | None] = lambda: _audio_counts()


# --- Windows-only readers (ctypes and winreg, read access only) -------------


def _memory() -> tuple[int, int] | None:
    """(total, available) bytes of RAM, or None where this cannot be read."""
    system = platform.system()
    if system == "Windows":
        class _MemStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        status = _MemStatus()
        status.dwLength = ctypes.sizeof(_MemStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return None
        return int(status.ullTotalPhys), int(status.ullAvailPhys)
    if system == "Linux":
        try:
            info = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines() if ":" in line)
            return int(info["MemTotal"].split()[0]) * 1024, int(info["MemAvailable"].split()[0]) * 1024
        except (OSError, KeyError, ValueError):
            return None
    return None


def _webview2_version() -> str | None:
    """The installed WebView2 runtime's version, from the registry keys Microsoft documents, or None."""
    if platform.system() != "Windows":
        return None
    import winreg

    places = [(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\" + _WEBVIEW2_CLIENT),
              (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\" + _WEBVIEW2_CLIENT),
              (winreg.HKEY_CURRENT_USER, "Software\\" + _WEBVIEW2_CLIENT)]
    for hive, key in places:
        try:
            with winreg.OpenKey(hive, key, 0, winreg.KEY_READ) as handle:
                version, _ = winreg.QueryValueEx(handle, "pv")
        except OSError:
            continue
        # "0.0.0.0" is the version the updater leaves behind after an
        # uninstall, not an address; it means WebView2 is not installed.
        if version and version != "0.0.0.0":  # nosec B104
            return str(version)
    return None


def _audio_counts() -> tuple[int, int] | None:
    """(input devices, output devices) from winmm, or None off Windows."""
    if platform.system() != "Windows":
        return None
    winmm = ctypes.windll.winmm  # type: ignore[attr-defined]
    return int(winmm.waveInGetNumDevs()), int(winmm.waveOutGetNumDevs())


# --- the probes --------------------------------------------------------------


def probe_os(s: Seams) -> Probe:
    return ok("os", "Operating system", f"{s.system()} {platform.release()} ({platform.version()}, {platform.machine()})")


def probe_cpu(s: Seams) -> Probe:
    logical = os.cpu_count()
    name = platform.processor() or ""
    physical: int | None = None
    if s.system() == "Windows":
        code, out = s.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                           "(Get-CimInstance Win32_Processor | Measure-Object NumberOfCores -Sum).Sum; "
                           "(Get-CimInstance Win32_Processor | Select-Object -First 1).Name"], 15.0)
        lines = [line.strip() for line in out.splitlines() if line.strip()] if code == 0 else []
        if lines and lines[0].isdigit():
            physical = int(lines[0])
            name = lines[1] if len(lines) > 1 else name
    elif s.system() == "Darwin":
        code, out = s.run(["sysctl", "-n", "hw.physicalcpu"], 5.0)
        physical = int(out.strip()) if code == 0 and out.strip().isdigit() else None
    if logical is None:
        return unknown("cpu", "Processor", "os.cpu_count() returned nothing")
    return ok("cpu", "Processor", {"name": name or "unknown", "logical": logical, "physical": physical})


def probe_ram(s: Seams) -> Probe:
    mem = s.memory()
    if mem is None:
        return unknown("ram", "Memory", f"no reader for {s.system()}")
    total, avail = mem
    return ok("ram", "Memory", {"total_mb": total // 2**20, "available_mb": avail // 2**20})


def probe_gpu(s: Seams) -> Probe:
    """NVIDIA through nvidia-smi; other vendors by name only, from the OS."""
    smi = s.which("nvidia-smi")
    if smi:
        code, out = s.run([smi, "--query-gpu=name,memory.total,memory.used,driver_version,pstate",
                           "--format=csv,noheader,nounits"], 10.0)
        if code == 0 and out.strip():
            first = [p.strip() for p in out.strip().splitlines()[0].split(",")]
            if len(first) == 5:
                name, total, used, driver, pstate = first
                try:
                    return ok("gpu", "Graphics", {"vendor": "NVIDIA", "name": name, "vram_total_mb": int(float(total)),
                                                  "vram_used_mb": int(float(used)), "driver": driver, "pstate": pstate})
                except ValueError:
                    pass
        return unknown("gpu", "Graphics", f"nvidia-smi is installed but did not answer (exit {code})")
    if s.system() == "Windows":
        code, out = s.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                           "(Get-CimInstance Win32_VideoController).Name"], 15.0)
        names = [n.strip() for n in out.splitlines() if n.strip()] if code == 0 else []
        if names:
            vendor = next((v for v in ("AMD", "Intel", "NVIDIA", "Microsoft") if any(v in n for n in names)), "other")
            return ok("gpu", "Graphics", {"vendor": vendor, "name": "; ".join(names), "vram_total_mb": None,
                                          "vram_used_mb": None, "driver": None, "pstate": None,
                                          "note": "memory not readable without the vendor's tools"})
        return unknown("gpu", "Graphics", "Windows reported no display adapter")
    if s.system() == "Darwin":
        return ok("gpu", "Graphics", {"vendor": "Apple", "name": platform.machine(), "vram_total_mb": None,
                                      "vram_used_mb": None, "driver": None, "pstate": None,
                                      "note": "Apple GPUs share system memory"})
    return unknown("gpu", "Graphics", "no NVIDIA tools found and no reader for this platform")


def probe_disk(s: Seams, target: Path) -> Probe:
    probe_at = target
    while not s.exists(probe_at) and probe_at.parent != probe_at:
        probe_at = probe_at.parent
    try:
        free = s.disk_free(probe_at)
    except OSError as exc:
        return unknown("disk", "Free disk", f"{probe_at}: {exc}")
    return ok("disk", "Free disk", {"target": str(target), "measured_at": str(probe_at), "free_mb": free // 2**20})


def probe_python(s: Seams) -> Probe:
    """Compatible Pythons already installed. Each is asked for its own version; none is assumed."""
    candidates: list[str] = []
    if s.system() == "Windows":
        code, out = s.run(["py", "-0p"], 10.0)
        if code == 0:
            # Lines look like " -V:3.13 *        C:\Program Files\Python313\python.exe": the
            # path starts at its drive letter and may contain spaces.
            candidates += [m.group(1).strip()
                           for m in re.finditer(r"\s([A-Za-z]:\\.*?pythonw?\.exe)\s*$", out, re.M | re.I)]
    for name in ("python3.13", "python3.12", "python3.11", "python3", "python"):
        found = s.which(name)
        if found:
            candidates.append(found)
    if not getattr(sys, "frozen", False):
        candidates.append(sys.executable)
    found_ok: list[dict[str, str]] = []
    seen: set[str] = set()
    for exe in candidates:
        key = os.path.normcase(exe)
        if key in seen or "\\.venv\\" in key or "/.venv/" in key:
            continue
        seen.add(key)
        code, out = s.run([exe, "-I", "-c", "import sys, venv, ensurepip; print('%d.%d.%d' % sys.version_info[:3])"], 15.0)
        version = out.strip()
        if code == 0 and re.fullmatch(r"\d+\.\d+\.\d+", version):
            major_minor = tuple(int(x) for x in version.split(".")[:2])
            if major_minor in COMPATIBLE_PYTHON:
                found_ok.append({"version": version, "path": exe})
    if found_ok:
        return ok("python", "Python 3.11 to 3.13", found_ok)
    return ok("python", "Python 3.11 to 3.13", [])


def probe_git(s: Seams) -> Probe:
    git = s.which("git")
    if not git:
        return ok("git", "Git", None)
    code, out = s.run([git, "--version"], 10.0)
    return ok("git", "Git", out.strip() if code == 0 else None)


def ollama_host(s: Seams) -> tuple[str, bool]:
    """(host, custom): custom is True when OLLAMA_HOST is set. Its value is not shown anywhere."""
    raw = (s.env("OLLAMA_HOST") or "").strip()
    if not raw:
        return "http://127.0.0.1:11434", False
    return (raw if "://" in raw else "http://" + raw).rstrip("/"), True


def probe_ollama(s: Seams) -> Probe:
    host, custom = ollama_host(s)
    where = "the host OLLAMA_HOST names" if custom else "127.0.0.1:11434"
    installed = bool(s.which("ollama"))
    try:
        version = s.http_json(host + "/api/version").get("version", "")
        tags = s.http_json(host + "/api/tags").get("models") or []
    except (OSError, ValueError) as exc:
        return ok("ollama", "Ollama", {"running": False, "installed": installed, "where": where,
                                       "reason": f"no answer from {where}: {type(exc).__name__}"})
    models = []
    for tag in tags:
        name = tag.get("name") or tag.get("model") or ""
        caps: list[str] = []
        try:
            caps = list(s.http_json(host + "/api/show", body={"model": name}).get("capabilities") or [])
        except (OSError, ValueError):
            caps = []
        models.append({"name": name, "size_mb": round((tag.get("size") or 0) / 2**20, 1), "capabilities": caps,
                       "parameters": (tag.get("details") or {}).get("parameter_size", "")})
    return ok("ollama", "Ollama", {"running": True, "installed": True, "where": where,
                                   "version": version, "models": models})


def probe_audio(s: Seams) -> Probe:
    counts = s.audio_counts()
    if counts is None:
        if s.system() == "Linux" and s.exists(Path("/proc/asound/cards")):
            return ok("audio", "Audio devices", {"inputs": None, "outputs": None, "note": "ALSA present"})
        return unsupported("audio", "Audio devices", f"no device reader for {s.system()} in the installer")
    inputs, outputs = counts
    return ok("audio", "Audio devices", {"inputs": inputs, "outputs": outputs})


def probe_network(s: Seams, hosts: list[str]) -> Probe:
    result = {host: (s.tcp(host, 443, 3.0) or "reachable") for host in hosts}
    return ok("network", "Download hosts", result)


def probe_webview2(s: Seams) -> Probe:
    if s.system() != "Windows":
        return unsupported("webview2", "WebView2", "Windows only; other systems use their own web view or a browser")
    version = s.webview2_version()
    return ok("webview2", "WebView2", version)


def probe_existing(s: Seams, layout: Any) -> Probe:
    from Agent_Guru.genesis import journal

    events, bad = journal.read(layout.journal_path)
    return ok("existing", "Existing install", {
        "runtime": s.exists(layout.venv_python),
        "installed_components": sorted(journal.installed_components(events)),
        "journal_events": len(events), "journal_unreadable_lines": bad,
        "settings": s.exists(layout.settings_path), "data_folder": s.exists(layout.data_dir),
    })


@dataclass
class Machine:
    """All probe results, by id; the planner reads only this."""

    probes: dict[str, Probe] = field(default_factory=dict)

    def value(self, probe_id: str) -> Any:
        p = self.probes.get(probe_id)
        return p.value if p and p.status == OK else None

    def to_dict(self) -> dict[str, Any]:
        return {k: v.to_dict() for k, v in self.probes.items()}


def scan(layout: Any, hosts: list[str], seams: Seams | None = None,
         on_result: Callable[[Probe], None] | None = None, *, network: bool = True) -> Machine:
    """Run every probe in screen order, calling *on_result* as each one returns."""
    s = seams or Seams()
    machine = Machine()
    steps: list[tuple[str, str, Callable[[], Probe]]] = [
        ("os", "Operating system", lambda: probe_os(s)), ("cpu", "Processor", lambda: probe_cpu(s)),
        ("ram", "Memory", lambda: probe_ram(s)), ("gpu", "Graphics", lambda: probe_gpu(s)),
        ("disk", "Free disk", lambda: probe_disk(s, layout.install_root)),
        ("python", "Python 3.11 to 3.13", lambda: probe_python(s)), ("git", "Git", lambda: probe_git(s)),
        ("ollama", "Ollama", lambda: probe_ollama(s)), ("audio", "Audio devices", lambda: probe_audio(s)),
        ("webview2", "WebView2", lambda: probe_webview2(s)),
        ("existing", "Existing install", lambda: probe_existing(s, layout)),
        ("network", "Download hosts", (lambda: probe_network(s, hosts)) if network else
         (lambda: unknown("network", "Download hosts", "not checked: offline install"))),
    ]
    for probe_id, label, step in steps:
        try:
            result = step()
        except Exception as exc:  # a probe that breaks is unknown, never a crash of the scan
            result = unknown(probe_id, label, f"{type(exc).__name__}: {exc}")
        machine.probes[result.id] = result
        if on_result:
            on_result(result)
    return machine
