"""The only things the installer can do: a fixed table of action ids.

The manifest names an action id for each component's install and rollback;
the executor looks the id up in ACTIONS and nowhere else. Nothing from a
manifest, a model, a download or a web page is ever run as a command: an id
that is not in the table is an error, and every argument an action passes to
a program is built here from the layout and from fields the manifest's
validator has already checked (package names, pinned file names, a model
name matching MODEL_NAME). Programs run from argument lists, never a shell.

Each action takes an ActionContext (the layout, the journal emitter, the
seams for programs, downloads and HTTP, and the cancel flag) and a
component's manifest entry, and returns an Outcome. It either finishes,
raises ActionError with a message for the person, or raises Cancelled.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform as _platform
import re
import shutil
import subprocess  # nosec B404 - argument lists to the managed runtime's own programs, never a shell
import sys
import tarfile
import time
import urllib.request
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from Agent_Guru.genesis.layout import Layout
from Agent_Guru.genesis.manifest import files_for, packages_for
from Agent_Guru.utils import verified_files as vf
from Agent_Guru.utils.path_utils import app_data_dir

#: Ollama model names: lowercase letters, digits and . _ - : /, as ollama.com
#: lists them. Anything else is refused before it reaches the pull API.
MODEL_NAME = re.compile(r"^[a-z0-9][a-z0-9._\-/]*(:[a-z0-9._\-]+)?$")
#: A requirement line the installer will hand to pip: a bare distribution
#: name. Versions come from the lock (-c), never from the manifest.
PACKAGE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*$")
#: Hosts an extra package index may come from.
ALLOWED_INDEXES = ("https://download.pytorch.org/whl/cpu",)


class ActionError(RuntimeError):
    """An action failed. The message is shown to the person as it is."""


class Cancelled(RuntimeError):  # noqa: N818 - a request, not a failure
    """The person cancelled; the step stopped at a safe point."""


@dataclass
class Outcome:
    reused: bool = False
    detail: dict[str, Any] = field(default_factory=dict)


def _run(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None,
         on_line: Callable[[str], None] | None = None, should_stop: Callable[[], bool] | None = None,
         timeout: float = 3600.0) -> tuple[int, str]:
    """Run a program from an argument list, streaming its output lines; (exit code, last 4000 chars)."""
    try:
        proc = subprocess.Popen(args, cwd=str(cwd) if cwd else None, env=env, stdout=subprocess.PIPE,  # nosec B603
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as exc:
        # The bare FileNotFoundError said "[WinError 2] The system cannot find
        # the file specified" without saying which file.
        msg = f"could not start {args[0]}: {exc.strerror or exc}"
        raise ActionError(msg) from exc
    tail: list[str] = []
    start = time.monotonic()
    assert proc.stdout is not None  # nosec B101 - PIPE was requested
    for line in proc.stdout:
        tail.append(line)
        del tail[:-60]
        if on_line:
            on_line(line.rstrip("\n"))
        if (should_stop and should_stop()) or time.monotonic() - start > timeout:
            proc.kill()
            proc.wait()
            if should_stop and should_stop():
                raise Cancelled("stopped while " + Path(args[0]).name + " was running")
            return -9, "".join(tail)[-4000:] + "\n(timed out)"
    return proc.wait(), "".join(tail)[-4000:]


def current_platform() -> str:
    return {"win32": "windows", "darwin": "darwin"}.get(sys.platform, "linux")


def _spawn(args: list[str]) -> None:
    """Start a long-running program and leave it running after this process ends."""
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,  # nosec B603
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _http_lines(url: str, body: dict[str, Any], timeout: float = 60.0) -> Iterator[dict[str, Any]]:
    """POST JSON and yield each JSON line of a streamed reply (Ollama's pull API)."""
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310  # nosec B310 - local Ollama only
        for raw in response:
            if raw.strip():
                yield json.loads(raw)


@dataclass
class ActionContext:
    layout: Layout
    emit: Callable[[str, dict[str, Any]], None]
    """emit(kind, data) for "progress" and "log" events of the current component."""
    run: Callable[..., tuple[int, str]] = _run
    download: Callable[..., None] = vf.download
    http_lines: Callable[..., Iterator[dict[str, Any]]] = _http_lines
    should_stop: Callable[[], bool] = lambda: False
    offline_dir: Path | None = None
    ollama_host: str = "http://127.0.0.1:11434"
    #: The Python the plan chose: a compatible one already installed, or "" for the private runtime.
    python: str = ""
    model: str = ""
    platform: str = field(default_factory=current_platform)
    arch: str = field(default_factory=_platform.machine)
    spawn: Callable[[list[str]], None] = _spawn
    which: Callable[[str], str | None] = shutil.which
    sleep: Callable[[float], None] = time.sleep

    def check(self) -> None:
        if self.should_stop():
            raise Cancelled("cancelled before the next step")


# --- helpers ---------------------------------------------------------------


class _Throttle:
    """Progress events at most every 0.5 s and at the end: each one is an fsync."""

    def __init__(self, ctx: ActionContext, label: str) -> None:
        self.ctx, self.label, self.last = ctx, label, 0.0

    def __call__(self, done: int, total: int | None) -> None:
        now = time.monotonic()
        if total is not None and done >= total or now - self.last >= 0.5:
            self.last = now
            self.ctx.emit("progress", {"done": done, "total": total if total else None, "item": self.label})


def _venv_env(layout: Layout) -> dict[str, str]:
    """The managed runtime's environment: the app's source on the path, nothing from the user's Python."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "PIP_", "VIRTUAL_ENV", "CONDA"))}
    env["PYTHONPATH"] = str(layout.app_root)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


def _python_version(ctx: ActionContext, exe: Path | str) -> str:
    code, out = ctx.run([str(exe), "-I", "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"], timeout=60)
    version = out.strip().splitlines()[-1] if out.strip() else ""
    return version if code == 0 and re.fullmatch(r"3\.1[123]\.\d+", version) else ""


def resolve_dest(token: str, layout: Layout) -> Path:
    """A manifest destination: "data:<relative>" under the user's data folder, "home:<relative>" under home."""
    kind, _, rel = token.partition(":")
    # anchor, not is_absolute(): on Windows "/etc" has no drive, so
    # is_absolute() says False, yet it resolves to the root of the drive.
    if not rel or ".." in Path(rel).parts or Path(rel).anchor:
        msg = f"destination {token!r} must be relative and must not climb out of its folder"
        raise ActionError(msg)
    if kind == "data":
        return app_data_dir(create=False) / rel
    if kind == "home":
        return Path.home() / rel
    if kind == "runtime":
        return layout.runtime_root / rel
    msg = f"unknown destination kind {kind!r} in {token!r}"
    raise ActionError(msg)


def _pins(component: dict[str, Any], ctx: ActionContext) -> list[tuple[vf.PinnedFile, list[str]]]:
    """Each pinned file for this machine with its URLs: the source first, then mirrors of the same bytes."""
    return [(vf.PinnedFile(f["name"], int(f["size"]), f["sha256"]), [f["url"], *f.get("mirrors", [])])
            for f in files_for(component, ctx.platform, ctx.arch)]


def private_python(ctx: ActionContext) -> Path:
    """The private runtime's interpreter: the NuGet layout on Windows, the standalone build elsewhere."""
    folder = ctx.layout.private_python_dir
    return folder / "python.exe" if ctx.platform == "windows" else folder / "bin" / "python3"


def _safe_rel(name: str, prefix: str, archive: str) -> Path | None:
    """*name* relative to *prefix*, or None outside it; refuses a path that would escape.

    anchor catches "tools//x" and "tools/C:/x" as well, which is_absolute()
    misses on Windows for a rooted path without a drive.
    """
    if not name.startswith(prefix) or name.endswith("/"):
        return None
    rel = Path(name[len(prefix):])
    if rel.anchor or ".." in rel.parts:
        msg = f"{archive} holds an unsafe path {name!r}; nothing was unpacked"
        raise ActionError(msg)
    return rel


def _fetch(ctx: ActionContext, pin: vf.PinnedFile, urls: list[str], dest: Path) -> bool:
    """Put the pinned file at *dest* through the download cache; True when nothing was downloaded.

    A mirror is tried when a source cannot be reached. It cannot change what
    is installed: every source is checked against the same pinned size and
    hash. This exists because a network filter can block one host outright: on
    2026-11-04 a Sophos device here re-signed GitHub's release host, so the
    voice could not be fetched from GitHub with certificate checks on, and
    turning those off is never the answer. A hash mismatch is not retried on
    another source: wrong bytes mean something is wrong, not that a host is down.
    """
    if dest.is_file() and not vf.problems(dest, pin):
        return True
    cached = ctx.layout.cache_dir / "files" / pin.digest[:16] / pin.name
    if not (cached.is_file() and not vf.problems(cached, pin)):
        if ctx.offline_dir is not None:
            source = ctx.offline_dir / "files" / pin.name
            if not source.is_file():
                msg = f"offline install: {pin.name} is not in {source.parent}"
                raise ActionError(msg)
            vf.copy_in(source, cached, pin)
        else:
            throttle = _Throttle(ctx, pin.name)
            errors: list[str] = []
            for url in urls:
                try:
                    ctx.download(url, cached, pin, resume=True, should_stop=ctx.should_stop,
                                 progress=lambda name, done, total: throttle(done, total))
                    errors = []
                    break
                except vf.DownloadCancelled as exc:
                    raise Cancelled(str(exc)) from exc
                except vf.VerificationError as exc:
                    raise ActionError(str(exc)) from exc
                except OSError as exc:
                    errors.append(str(exc))
                    if len(urls) > 1:
                        ctx.emit("log", {"line": f"{pin.name}: {exc}; trying the next source"})
            if errors:
                raise ActionError("; ".join(errors))
    vf.copy_in(cached, dest, pin)
    return False


# --- the actions -------------------------------------------------------------


def act_runtime_python(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    """Reuse a compatible Python, or unpack the pinned private runtime into the install folder."""
    if ctx.python:
        version = _python_version(ctx, ctx.python)
        if not version:
            msg = f"the Python the plan chose ({ctx.python}) did not report a version from 3.11 to 3.13"
            raise ActionError(msg)
        return Outcome(reused=True, detail={"python": ctx.python, "version": version})
    target = ctx.layout.private_python_dir
    exe = private_python(ctx)
    if exe.is_file() and _python_version(ctx, exe):
        return Outcome(reused=True, detail={"python": str(exe), "version": _python_version(ctx, exe)})
    pins = _pins(component, ctx)
    if not pins:
        msg = f"no private Python is pinned for {ctx.platform} {ctx.arch}; install Python 3.11 to 3.13 and run again"
        raise ActionError(msg)
    (pin, urls), = pins
    archive = ctx.layout.cache_dir / "files" / pin.digest[:16] / pin.name
    _fetch(ctx, pin, urls, archive)
    ctx.check()
    staging = target.with_name("python.unpacking")
    shutil.rmtree(staging, ignore_errors=True)
    if pin.name.endswith(".nupkg"):
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                rel = _safe_rel(info.filename, "tools/", pin.name)
                if rel is None:
                    continue
                out = staging / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, out.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    else:
        # python-build-standalone: one top folder "python". filter="data"
        # refuses links and paths that leave the folder.
        with tarfile.open(archive) as tf:
            tf.extractall(staging.parent / "python.unpacked", filter="data")  # nosec B202
        shutil.rmtree(staging, ignore_errors=True)
        os.replace(staging.parent / "python.unpacked" / "python", staging)
        shutil.rmtree(staging.parent / "python.unpacked", ignore_errors=True)
    shutil.rmtree(target, ignore_errors=True)
    os.replace(staging, target)
    version = _python_version(ctx, exe)
    if not version:
        msg = f"the private Python in {target} did not start"
        raise ActionError(msg)
    return Outcome(detail={"python": str(exe), "version": version})


def _base_python(ctx: ActionContext) -> str:
    return ctx.python or str(private_python(ctx))


def act_runtime_venv(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    venv_py = ctx.layout.venv_python
    if venv_py.is_file() and _python_version(ctx, venv_py):
        return Outcome(reused=True, detail={"venv": str(ctx.layout.venv_dir)})
    code, out = ctx.run([_base_python(ctx), "-I", "-m", "venv", str(ctx.layout.venv_dir)], timeout=600)
    if code != 0 or not venv_py.is_file():
        msg = f"creating the private environment failed (exit {code}): {out.strip()[-400:]}"
        raise ActionError(msg)
    return Outcome(detail={"venv": str(ctx.layout.venv_dir), "version": _python_version(ctx, venv_py)})


_PIP_PROGRESS = re.compile(r"Progress (\d+) of (\d+)")


def act_pip_tier(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    """pip install the component's packages, versions from the lock, into the private environment."""
    packages = packages_for(component, ctx.platform)
    bad = [p for p in packages if not PACKAGE_NAME.match(p)]
    if bad:
        msg = f"refusing package names {bad}: only bare names are installed, versions come from the lock"
        raise ActionError(msg)
    if not ctx.layout.lock_file.is_file():
        msg = f"the lock file is missing: {ctx.layout.lock_file}"
        raise ActionError(msg)
    work = ctx.layout.cache_dir / "tiers"
    work.mkdir(parents=True, exist_ok=True)
    reqs = work / f"{component['id']}.txt"
    reqs.write_text("\n".join(packages) + "\n", encoding="utf-8")
    report = work / f"{component['id']}.report.json"
    constraints = ctx.layout.lock_file
    if ctx.platform == "darwin":
        # The lock pins PyTorch's +cpu builds, which that index does not
        # publish for macOS: there the same versions come from PyPI, and they
        # are CPU builds already.
        constraints = work / "constraints-darwin.txt"
        constraints.write_text(ctx.layout.lock_file.read_text(encoding="utf-8").replace("+cpu", ""), encoding="utf-8")
    args = [str(ctx.layout.venv_python), "-I", "-m", "pip", "install", "--no-input", "--progress-bar", "raw",
            "--cache-dir", str(ctx.layout.cache_dir / "pip"), "--report", str(report),
            "-r", str(reqs), "-c", str(constraints)]
    if ctx.offline_dir is not None:
        args += ["--no-index", "--find-links", str(ctx.offline_dir / "wheels")]
    else:
        for index in [] if ctx.platform == "darwin" else component.get("extra_index", []):
            if index not in ALLOWED_INDEXES:
                msg = f"package index {index!r} is not on the allowed list"
                raise ActionError(msg)
            args += ["--extra-index-url", index]
    throttle = _Throttle(ctx, component["id"])

    def line(text: str) -> None:
        m = _PIP_PROGRESS.search(text)
        if m:
            throttle(int(m.group(1)), int(m.group(2)))
        elif text.startswith(("Collecting", "Downloading", "Installing", "Successfully", "ERROR")):
            ctx.emit("log", {"line": text[:300]})

    code, out = ctx.run(args, cwd=ctx.layout.runtime_root, env=_venv_env(ctx.layout), on_line=line,
                        should_stop=ctx.should_stop)
    if code != 0:
        msg = f"pip could not install {component['id']} (exit {code}): {out.strip()[-600:]}"
        raise ActionError(msg)
    installed: list[str] = []
    try:
        installed = [i["metadata"]["name"] for i in json.loads(report.read_text(encoding="utf-8")).get("install", [])]
    except (OSError, ValueError, KeyError):
        pass
    return Outcome(reused=not installed, detail={"installed": installed})


def act_pip_uninstall_tier(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    """Remove what this tier's install added, minus anything another installed tier also added."""
    work = ctx.layout.cache_dir / "tiers"
    try:
        mine = [i["metadata"]["name"] for i in
                json.loads((work / f"{component['id']}.report.json").read_text(encoding="utf-8"))["install"]]
    except (OSError, ValueError, KeyError) as exc:
        msg = f"no record of what {component['id']} installed, so nothing is removed ({exc})"
        raise ActionError(msg) from exc
    others: set[str] = set()
    for report in work.glob("*.report.json"):
        if report.name != f"{component['id']}.report.json":
            try:
                others |= {i["metadata"]["name"] for i in json.loads(report.read_text(encoding="utf-8"))["install"]}
            except (OSError, ValueError, KeyError):
                continue
    remove = [p for p in mine if p not in others and PACKAGE_NAME.match(p)]
    if remove:
        code, out = ctx.run([str(ctx.layout.venv_python), "-I", "-m", "pip", "uninstall", "-y", *remove],
                            env=_venv_env(ctx.layout))
        if code != 0:
            msg = f"pip could not remove {component['id']} (exit {code}): {out.strip()[-400:]}"
            raise ActionError(msg)
    (work / f"{component['id']}.report.json").unlink(missing_ok=True)
    return Outcome(detail={"removed": remove})


def act_download_files(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    dest_dir = resolve_dest(component["dest"], ctx.layout)
    reused = True
    for pin, urls in _pins(component, ctx):
        ctx.check()
        reused = _fetch(ctx, pin, urls, dest_dir / pin.name) and reused
    return Outcome(reused=reused, detail={"dest": str(dest_dir)})


def act_remove_files(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    """Delete exactly the pinned files this component placed; never the folder or anything else in it."""
    dest_dir = resolve_dest(component["dest"], ctx.layout)
    removed = []
    for pin, _ in _pins(component, ctx):
        path = dest_dir / pin.name
        if path.is_file():
            path.unlink()
            removed.append(pin.name)
    return Outcome(detail={"removed": removed})


def ollama_version(host: str) -> str:
    """The running Ollama's version, or "" when nothing answers."""
    try:
        with urllib.request.urlopen(host + "/api/version", timeout=3) as response:  # noqa: S310  # nosec B310
            return str(json.loads(response.read()).get("version", "")) or "unknown"
    except (OSError, ValueError):
        return ""


def private_ollama(layout: Layout, platform: str) -> Path | None:
    """The Ollama this installer unpacked on Linux or macOS, if there is one."""
    folder = layout.runtime_root / "ollama"
    for exe in (folder / "bin" / "ollama", folder / "ollama"):
        if platform != "windows" and exe.is_file():
            return exe
    return None


def _start_ollama(ctx: ActionContext, exe: str) -> None:
    if not ollama_version(ctx.ollama_host):
        ctx.spawn([exe, "serve"])
    for _ in range(120):
        if ollama_version(ctx.ollama_host):
            return
        ctx.check()
        ctx.sleep(1.0)
    msg = f"Ollama was installed but did not start answering at {exe}"
    raise ActionError(msg)


def act_ollama_install(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    """Reuse a running Ollama; otherwise install the pinned release and start it.

    Ollama's own script for Linux pipes curl into a root shell, which this
    installer will not do. Here it is a pinned file, checked against the hash
    Ollama publishes, and on Linux and macOS it is unpacked into the private
    runtime with no root and started as a plain process.
    """
    version = ollama_version(ctx.ollama_host)
    if version:
        return Outcome(reused=True, detail={"version": version})
    # Installed but stopped: start it. Reinstalling would fetch 1.7 GB for nothing.
    installed = ctx.which("ollama") or private_ollama(ctx.layout, ctx.platform)
    if installed:
        _start_ollama(ctx, str(installed))
        return Outcome(reused=True, detail={"version": ollama_version(ctx.ollama_host)})
    pins = _pins(component, ctx)
    if not pins:
        msg = f"no Ollama build is pinned for {ctx.platform} {ctx.arch}"
        raise ActionError(msg)
    (pin, urls), = pins
    archive = ctx.layout.cache_dir / "files" / pin.digest[:16] / pin.name
    _fetch(ctx, pin, urls, archive)
    ctx.check()
    if ctx.platform == "windows":
        code, out = ctx.run([str(archive), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"], timeout=1800)
        if code != 0:
            msg = f"the Ollama installer stopped with exit {code}: {out.strip()[-300:]}"
            raise ActionError(msg)
        exe = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Programs" / "Ollama" / "ollama.exe"
    else:
        folder = ctx.layout.runtime_root / "ollama"
        folder.mkdir(parents=True, exist_ok=True)
        if pin.name.endswith(".zst"):
            # Python 3.13's tarfile cannot read zstd.
            code, out = ctx.run(["tar", "--zstd", "-xf", str(archive), "-C", str(folder)], timeout=1800)
            if code != 0:
                msg = f"unpacking Ollama needs tar with zstd support (install zstd): {out.strip()[-300:]}"
                raise ActionError(msg)
        else:
            with tarfile.open(archive) as tf:
                tf.extractall(folder, filter="data")  # nosec B202
        exe = private_ollama(ctx.layout, ctx.platform) or folder / "ollama"
    _start_ollama(ctx, str(exe))
    return Outcome(detail={"version": ollama_version(ctx.ollama_host)})


def _tree_id(folder: Path) -> str:
    """Names and sizes of every file: enough to tell one build of the app from another, without hashing it."""
    entries = sorted(f"{p.relative_to(folder).as_posix()}:{p.stat().st_size}" for p in folder.rglob("*")
                     if p.is_file() and p.name != ".genesis-build")
    return hashlib.sha256("\n".join(entries).encode()).hexdigest()


def act_app_files(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    """Copy the application out of a frozen bundle, which is read-only or goes away when the launcher exits.

    Where nothing is bundled (the Windows installer places the source
    itself, and a checkout is its own source) there is nothing to copy.
    """
    bundled = ctx.layout.bundled_app
    target = ctx.layout.app_root
    if bundled is None:
        return Outcome(reused=True, detail={"app": str(target)})
    if not bundled.is_dir():
        msg = f"this build carries no application source at {bundled}"
        raise ActionError(msg)
    build = _tree_id(bundled)
    marker = target / ".genesis-build"
    if marker.is_file() and marker.read_text(encoding="utf-8") == build:
        return Outcome(reused=True, detail={"app": str(target)})
    staging = target.with_name("app.copying")
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(bundled, staging)
    (staging / ".genesis-build").write_text(build, encoding="utf-8")
    shutil.rmtree(target, ignore_errors=True)
    os.replace(staging, target)
    return Outcome(detail={"app": str(target)})


def act_ollama_pull(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    """Pull a model through Ollama's own API, which verifies every layer it downloads.

    The chat model is the one the plan chose (ctx.model); a component that
    names its own model (the vision model) pulls that one instead.
    """
    model = component.get("model") or ctx.model
    if not MODEL_NAME.match(model or ""):
        msg = f"refusing model name {model!r}"
        raise ActionError(msg)
    layers: dict[str, tuple[int, int]] = {}
    throttle = _Throttle(ctx, model)
    status = ""
    try:
        for msg_ in ctx.http_lines(ctx.ollama_host + "/api/pull", {"model": model, "stream": True}, timeout=600):
            ctx.check()
            if "error" in msg_:
                msg = f"Ollama could not pull {model}: {msg_['error']}"
                raise ActionError(msg)
            status = msg_.get("status", status)
            digest, total = msg_.get("digest"), msg_.get("total")
            if digest and isinstance(total, int) and total > 0:
                layers[digest] = (int(msg_.get("completed") or 0), total)
                throttle(sum(c for c, _ in layers.values()), sum(t for _, t in layers.values()))
    except OSError as exc:
        msg = f"127.0.0.1 (Ollama): pulling {model} stopped: {type(exc).__name__}: {exc}"
        raise ActionError(msg) from exc
    if status != "success":
        msg = f"Ollama did not finish pulling {model} (last status {status!r})"
        raise ActionError(msg)
    return Outcome(detail={"model": model, "bytes": sum(t for _, t in layers.values())})


def act_runtime_task(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    """Run one allow-listed task inside the managed runtime (runtime_tasks.TASKS), e.g. fetching the voice."""
    task = component["task"]
    result = run_runtime_task(ctx, task, component.get("task_args", []))
    if result.get("result") != "PASS":
        msg = f"{task}: {result.get('detail', 'no detail')}"
        raise ActionError(msg)
    return Outcome(reused=bool(result.get("reused")), detail=result)


def run_runtime_task(ctx: ActionContext, task: str, args: list[str], timeout: float = 1800.0) -> dict[str, Any]:
    from Agent_Guru.genesis.runtime_tasks import TASKS

    if task not in TASKS:
        msg = f"unknown runtime task {task!r}"
        raise ActionError(msg)
    if not ctx.layout.venv_python.is_file():
        return {"result": "NOT INSTALLED", "detail": "the private environment does not exist yet"}
    # -s, not -I: isolated mode also ignores PYTHONPATH and the current
    # folder, so the first real install's checks all failed with "No module
    # named 'Agent_Guru'". -s keeps the user's own site-packages out, and the
    # environment is built by _venv_env, which drops every other PYTHON*.
    code, out = ctx.run([str(ctx.layout.venv_python), "-s", "-m", "Agent_Guru.genesis.runtime_tasks", task, *args],
                        cwd=ctx.layout.app_root, env=_venv_env(ctx.layout), should_stop=ctx.should_stop,
                        timeout=timeout)
    lines = [ln for ln in out.splitlines() if ln.startswith("{") and '"result"' in ln]
    if not lines:
        return {"result": "FAILED", "detail": f"exit {code}: {out.strip()[-500:]}"}
    return json.loads(lines[-1])


def act_data_folder(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    """The user's data folder. Created if missing; never removed by the installer."""
    folder = app_data_dir(create=False)
    existed = folder.is_dir()
    folder.mkdir(parents=True, exist_ok=True)
    return Outcome(reused=existed, detail={"folder": str(folder)})


def act_nothing_to_install(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    """For a component with nothing to fetch (research uses packages the core has): only its probe decides."""
    return Outcome(reused=True)


def act_remove_venv(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    """Delete the private environment. It holds packages only, never user data."""
    venv = ctx.layout.venv_dir
    if venv.exists():
        if ctx.layout.runtime_root not in venv.parents:
            msg = f"refusing to delete {venv}: it is not inside {ctx.layout.runtime_root}"
            raise ActionError(msg)
        shutil.rmtree(venv)
    return Outcome(detail={"removed": str(venv)})


def act_remove_private_python(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    target = ctx.layout.private_python_dir
    if target.exists() and ctx.layout.runtime_root in target.parents:
        shutil.rmtree(target)
    return Outcome(detail={"removed": str(target)})


ACTIONS: dict[str, Callable[[ActionContext, dict[str, Any]], Outcome]] = {
    "runtime.python": act_runtime_python,
    "runtime.remove_python": act_remove_private_python,
    "runtime.venv": act_runtime_venv,
    "runtime.remove_venv": act_remove_venv,
    "pip.tier": act_pip_tier,
    "pip.uninstall_tier": act_pip_uninstall_tier,
    "files.download": act_download_files,
    "files.remove": act_remove_files,
    "ollama.install": act_ollama_install,
    "app.files": act_app_files,
    "ollama.pull": act_ollama_pull,
    "runtime.task": act_runtime_task,
    "data.folder": act_data_folder,
    "nothing": act_nothing_to_install,
}

#: The rollback written in the manifest when a step cannot be undone.
NOT_REVERSIBLE = "not reversible"
