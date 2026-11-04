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

import json
import os
import re
import shutil
import subprocess  # nosec B404 - argument lists to the managed runtime's own programs, never a shell
import sys
import time
import urllib.request
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from Agent_Guru.genesis.layout import Layout
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
    proc = subprocess.Popen(args, cwd=str(cwd) if cwd else None, env=env, stdout=subprocess.PIPE,  # nosec B603
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
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


def _pins(component: dict[str, Any]) -> list[tuple[vf.PinnedFile, str]]:
    return [(vf.PinnedFile(f["name"], int(f["size"]), f["sha256"]), f["url"]) for f in component.get("files", [])]


def _fetch(ctx: ActionContext, pin: vf.PinnedFile, url: str, dest: Path) -> bool:
    """Put the pinned file at *dest* through the download cache; True when nothing was downloaded."""
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
            try:
                ctx.download(url, cached, pin, resume=True, should_stop=ctx.should_stop,
                             progress=lambda name, done, total: throttle(done, total))
            except vf.DownloadCancelled as exc:
                raise Cancelled(str(exc)) from exc
            except (vf.DownloadError, vf.VerificationError, OSError) as exc:
                raise ActionError(str(exc)) from exc
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
    exe = target / "python.exe"
    if exe.is_file() and _python_version(ctx, exe):
        return Outcome(reused=True, detail={"python": str(exe), "version": _python_version(ctx, exe)})
    if sys.platform != "win32":
        msg = "no Python 3.11 to 3.13 was found; install one from your system's packages and run again"
        raise ActionError(msg)
    (pin, url), = _pins(component)
    archive = ctx.layout.cache_dir / "files" / pin.digest[:16] / pin.name
    _fetch(ctx, pin, url, archive)
    ctx.check()
    staging = target.with_name("python.unpacking")
    shutil.rmtree(staging, ignore_errors=True)
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename
            if not name.startswith("tools/") or name.endswith("/"):
                continue
            rel = Path(name[len("tools/"):])
            # anchor catches "tools//x" and "tools/C:/x" as well, which
            # is_absolute() misses on Windows for a rooted path without a drive.
            if rel.anchor or ".." in rel.parts:
                msg = f"{pin.name} holds an unsafe path {name!r}; nothing was unpacked"
                raise ActionError(msg)
            out = staging / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    shutil.rmtree(target, ignore_errors=True)
    os.replace(staging, target)
    version = _python_version(ctx, exe)
    if not version:
        msg = f"the private Python in {target} did not start"
        raise ActionError(msg)
    return Outcome(detail={"python": str(exe), "version": version})


def _base_python(ctx: ActionContext) -> str:
    return ctx.python or str(ctx.layout.private_python_dir / "python.exe")


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
    packages = component["packages"]
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
    args = [str(ctx.layout.venv_python), "-I", "-m", "pip", "install", "--no-input", "--progress-bar", "raw",
            "--cache-dir", str(ctx.layout.cache_dir / "pip"), "--report", str(report),
            "-r", str(reqs), "-c", str(ctx.layout.lock_file)]
    if ctx.offline_dir is not None:
        args += ["--no-index", "--find-links", str(ctx.offline_dir / "wheels")]
    else:
        for index in component.get("extra_index", []):
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
    for pin, url in _pins(component):
        ctx.check()
        reused = _fetch(ctx, pin, url, dest_dir / pin.name) and reused
    return Outcome(reused=reused, detail={"dest": str(dest_dir)})


def act_remove_files(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    """Delete exactly the pinned files this component placed; never the folder or anything else in it."""
    dest_dir = resolve_dest(component["dest"], ctx.layout)
    removed = []
    for pin, _ in _pins(component):
        path = dest_dir / pin.name
        if path.is_file():
            path.unlink()
            removed.append(pin.name)
    return Outcome(detail={"removed": removed})


def act_ollama_present(ctx: ActionContext, component: dict[str, Any]) -> Outcome:
    """Ollama is its own application: reused when it answers, otherwise the person is told how to get it."""
    try:
        with urllib.request.urlopen(ctx.ollama_host + "/api/version", timeout=3) as response:  # noqa: S310  # nosec B310
            version = json.loads(response.read()).get("version", "")
    except (OSError, ValueError) as exc:
        msg = ("Ollama is not running. Install it from https://ollama.com/download, start it, then choose Retry. "
               f"({type(exc).__name__})")
        raise ActionError(msg) from exc
    return Outcome(reused=True, detail={"version": version})


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
    code, out = ctx.run([str(ctx.layout.venv_python), "-I", "-m", "Agent_Guru.genesis.runtime_tasks", task, *args],
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
    "ollama.present": act_ollama_present,
    "ollama.pull": act_ollama_pull,
    "runtime.task": act_runtime_task,
    "data.folder": act_data_folder,
    "nothing": act_nothing_to_install,
}

#: The rollback written in the manifest when a step cannot be undone.
NOT_REVERSIBLE = "not reversible"
