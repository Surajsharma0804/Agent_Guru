"""Verification: each component's probe, run for real, with one of six results.

PASS            the probe ran and the component did its job.
WARNING         it works, degraded, and the detail says how (the wake-word
                fallback that wakes on any loud sound).
NOT INSTALLED   its packages or files are not there.
NOT CONFIGURED  installed, but something it needs is not set (no model chosen,
                no Edge or Chrome for the browser tools).
FAILED          the probe ran and the component did not work.
NOT APPLICABLE  this component does not apply to this machine (the GPU add-on
                without an NVIDIA GPU).

A component that was not probed has no result at all; it is never PASS.
Checks that need a person (hearing the voice, speaking the wake phrase) are
marked needs_person and stay UNVERIFIED until the person confirms on screen.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from Agent_Guru.genesis import autostart
from Agent_Guru.genesis import actions as act
from Agent_Guru.utils import verified_files as vf

LABELS = ("PASS", "WARNING", "NOT INSTALLED", "NOT CONFIGURED", "FAILED", "NOT APPLICABLE")


@dataclass
class Result:
    label: str
    detail: str
    data: dict[str, Any] = field(default_factory=dict)
    needs_person: str = ""

    def __post_init__(self) -> None:
        if self.label not in LABELS:
            msg = f"unknown verification result {self.label!r}"
            raise ValueError(msg)

    @property
    def counts_as_installed(self) -> bool:
        return self.label in ("PASS", "WARNING")


def _task(task: str, *args_from: str, needs_person: str = "") -> Callable[[act.ActionContext, dict[str, Any]], Result]:
    def probe(ctx: act.ActionContext, component: dict[str, Any]) -> Result:
        args = [(component.get("model") or ctx.model) if a == "model" else str(component.get(a, "")) for a in args_from]
        out = act.run_runtime_task(ctx, task, [a for a in args if a], timeout=900)
        label = out.pop("result", "FAILED")
        detail = out.pop("detail", "")
        return Result(label if label in LABELS else "FAILED", detail, out, needs_person if label == "PASS" else "")
    return probe


def probe_python(ctx: act.ActionContext, component: dict[str, Any]) -> Result:
    exe = ctx.python or str(act.private_python(ctx))
    version = act._python_version(ctx, exe)
    return Result("PASS", f"Python {version}", {"python": exe}) if version else \
        Result("NOT INSTALLED", f"no working Python 3.11 to 3.13 at {exe}")


def probe_venv(ctx: act.ActionContext, component: dict[str, Any]) -> Result:
    version = act._python_version(ctx, ctx.layout.venv_python) if ctx.layout.venv_python.is_file() else ""
    return Result("PASS", f"private environment on Python {version}") if version else \
        Result("NOT INSTALLED", f"no private environment at {ctx.layout.venv_dir}")


def probe_ollama(ctx: act.ActionContext, component: dict[str, Any]) -> Result:
    try:
        with urllib.request.urlopen(ctx.ollama_host + "/api/version", timeout=3) as response:  # noqa: S310  # nosec B310
            version = json.loads(response.read()).get("version", "")
    except (OSError, ValueError) as exc:
        return Result("NOT INSTALLED", f"Ollama does not answer ({type(exc).__name__})")
    return Result("PASS", f"Ollama {version} is running")


def probe_app(ctx: act.ActionContext, component: dict[str, Any]) -> Result:
    needed = [ctx.layout.lock_file, ctx.layout.app_root / "Agent_Guru" / "__init__.py", ctx.layout.app_root / "main.py"]
    missing = [p.name for p in needed if not p.is_file()]
    return Result("NOT INSTALLED", f"missing from {ctx.layout.app_root}: {', '.join(missing)}") if missing else \
        Result("PASS", f"the application source is in {ctx.layout.app_root}")


def probe_files(ctx: act.ActionContext, component: dict[str, Any]) -> Result:
    dest = act.resolve_dest(component["dest"], ctx.layout)
    pins = [p for p, _ in act._pins(component, ctx)]
    found = vf.verify(dest, pins)
    if not found:
        return Result("PASS", f"{len(pins)} pinned files match their SHA-256 in {dest}")
    missing = all(not (dest / p.name).exists() for p in pins)
    return Result("NOT INSTALLED" if missing else "FAILED", "; ".join(found))


def probe_data_folder(ctx: act.ActionContext, component: dict[str, Any]) -> Result:
    folder = ctx.layout.data_dir
    if not folder.is_dir():
        return Result("NOT INSTALLED", f"{folder} does not exist")
    marker = folder / ".genesis-write-check"
    try:
        marker.write_text("ok", encoding="utf-8")
        marker.unlink()
    except OSError as exc:
        return Result("FAILED", f"{folder} is not writable: {exc}")
    return Result("PASS", f"{folder} exists and is writable")


def probe_gpu_addon(ctx: act.ActionContext, component: dict[str, Any]) -> Result:
    out = act.run_runtime_task(ctx, "core.import", [])
    if out.get("result") == "NOT INSTALLED":
        return Result("NOT INSTALLED", out.get("detail", ""))
    code, text = ctx.run([str(ctx.layout.venv_python), "-I", "-c",
                          "import ctranslate2; print(ctranslate2.get_cuda_device_count())"], timeout=120)
    count = text.strip().splitlines()[-1] if text.strip() else ""
    if code != 0 or not count.isdigit():
        return Result("FAILED", f"CTranslate2 did not report its CUDA devices: {text.strip()[-200:]}")
    return Result("PASS", f"CTranslate2 sees {count} CUDA device(s)") if int(count) > 0 else \
        Result("FAILED", "CTranslate2 sees no CUDA device with the GPU libraries installed")


def probe_autostart(ctx: act.ActionContext, component: dict[str, Any]) -> Result:
    entry = autostart.entry_path(ctx.platform)
    return Result("PASS", str(entry)) if entry.is_file() else Result("NOT INSTALLED", "the assistant does not start at sign-in")


PROBES: dict[str, Callable[[act.ActionContext, dict[str, Any]], Result]] = {
    "autostart.present": probe_autostart,
    "python.ok": probe_python,
    "venv.ok": probe_venv,
    "ollama.running": probe_ollama,
    "files.pinned": probe_files,
    "app.present": probe_app,
    "data.folder": probe_data_folder,
    "gpu.cuda": probe_gpu_addon,
    "core.import": _task("core.import"),
    "db.readwrite": _task("db.readwrite"),
    "memory.persist": _task("memory.persist"),
    "embed.sentence": _task("embed.sentence"),
    "llm.reply": _task("llm.reply", "model"),
    "tts.synthesize": _task("tts.synthesize", needs_person="Play the test sentence and confirm you hear a voice."),
    "stt.transcribe": _task("stt.transcribe", "whisper_size"),
    "wake.load": _task("wake.load", needs_person="Say the wake phrase and confirm the assistant wakes."),
    "vision.check": _task("vision.check"),
    "browser.check": _task("browser.check"),
    "coding.check": _task("coding.check"),
    "research.reach": _task("research.reach"),
    "vault.check": _task("vault.check"),
    "voice.import": _task("voice.import"),
}


def run(probe_id: str, ctx: act.ActionContext, component: dict[str, Any]) -> Result:
    probe = PROBES.get(probe_id)
    if probe is None:
        return Result("FAILED", f"no probe called {probe_id!r}")
    try:
        return probe(ctx, component)
    except act.Cancelled:
        raise
    except Exception as exc:  # a broken probe is a FAILED result, never a crash or a pass
        return Result("FAILED", f"the probe {probe_id} raised {type(exc).__name__}: {exc}")
