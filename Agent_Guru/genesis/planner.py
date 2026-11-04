"""From probe results to a plan: what is reused, what is downloaded, and what it costs.

plan() is a pure function of the machine's probe results, the manifest and the
person's choices. It makes no network call and writes nothing (a test holds
it to that); the probes did the looking. The plan says:

- for each component, reuse, install or skip, and why;
- the bytes to download and to keep on disk, the free space, and whether it
  fits with the margin below;
- every change outside the install folder;
- which tiers are on, and which features are unavailable on this machine
  and why;
- which model will answer, whether it fits the GPU next to speech, and
  when it will run partly on the CPU.

It never chooses a model whose weights do not fit in RAM, nor one whose
download does not fit on the disk. It prefers a model already installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from Agent_Guru.genesis.manifest import NOT_REVERSIBLE, Manifest
from Agent_Guru.genesis.probes import Machine
from Agent_Guru.utils.model_fit import gpu_fit, needs_mb

#: GPU memory Whisper takes when speech runs on the GPU: the base model in
#: int8, "~300MB VRAM" by speech/config.py's note on it. It is reserved before
#: the chat model's fit is judged, because both stay loaded during a turn.
WHISPER_GPU_MB = 300
#: Disk margin over installed size plus the download cache. pip unpacks
#: wheels next to their final place while installing, and a filesystem
#: reports free space in its own allocation units.
DISK_MARGIN = 0.10
#: Below this a spoken answer of 50 tokens takes more than 10 s, and the
#: plan offers a smaller model (it never switches by itself).
POOR_TOKENS_PER_SECOND = 5.0
#: Windows' path limit without LongPathsEnabled, and the longest path the
#: installer creates below the install folder: "\runtime\venv\" (14) plus the
#: deepest file pip writes in any tier (143 characters, measured 2026-11-04,
#: an onnxruntime .pyc). A longer install folder would fail halfway through pip.
WINDOWS_MAX_PATH = 259
DEEPEST_BELOW_ROOT = 14 + 143


def path_problem(disk: dict[str, Any], platform: str) -> str:
    """Why the install folder's path is too long for this machine, or ""."""
    chars = disk.get("target_chars")
    if platform != "windows" or not isinstance(chars, int) or disk.get("long_paths"):
        return ""
    if chars + DEEPEST_BELOW_ROOT <= WINDOWS_MAX_PATH:
        return ""
    return (f"the install folder's path is {chars} characters; with long paths off in Windows it can be at most "
            f"{WINDOWS_MAX_PATH - DEEPEST_BELOW_ROOT}, because pip writes files {DEEPEST_BELOW_ROOT} characters "
            "below it. Choose a shorter folder.")

#: Every tier is on unless the person turns it off: the owner's rule is a
#: small download and a complete install, with no limit on installed size.
#: Voice is still planned without a microphone (typed chat works and a
#: microphone can be added later); the GPU add-on still needs an NVIDIA GPU.
DEFAULT_TIERS = {"core": True, "voice": True, "vision": True, "research": True, "browser": True, "coding": True}


@dataclass
class Choices:
    tiers: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_TIERS))
    model: str = ""
    gpu_speech: bool | None = None  # None: on when an NVIDIA GPU is found and voice is on
    offline: bool = False


def _platform(machine: Machine) -> str:
    os_value = str(machine.value("os") or "")
    return "windows" if os_value.startswith("Windows") else "darwin" if os_value.startswith("Darwin") else "linux"


def _usable(model: dict[str, Any]) -> bool:
    caps = model.get("capabilities") or []
    return "tools" in caps and "completion" in caps


def choose_model(machine: Machine, candidates: list[dict[str, Any]], choices: Choices, speech_on_gpu: bool,
                 free_disk_mb: float | None) -> dict[str, Any]:
    """The model that will answer, with the reason and the GPU fit. Never one that does not fit RAM or disk."""
    ollama = machine.value("ollama") or {}
    installed = [m for m in ollama.get("models", []) if _usable(m)]
    gpu = machine.value("gpu") or {}
    ram = machine.value("ram") or {}
    ram_mb = ram.get("total_mb")
    total = gpu.get("vram_total_mb")
    free_gpu = None
    if gpu.get("vendor") == "NVIDIA" and isinstance(total, int):
        others = (gpu.get("vram_used_mb") or 0) - sum(m.get("vram_mb", 0) for m in ollama.get("loaded", []))
        free_gpu = max(0, total - max(0, others) - (WHISPER_GPU_MB if speech_on_gpu else 0))

    def describe(name: str, size_mb: float, reused: bool, why: str, download_bytes: int = 0) -> dict[str, Any]:
        fit = gpu_fit(size_mb, free_gpu) if free_gpu is not None else "cpu"
        need = needs_mb(size_mb)
        note = {"fits": "runs entirely on the GPU",
                "partial": f"splits between GPU and CPU: about {min(99, int(100 * (free_gpu or 0) / need))} % on the "
                           f"GPU ({free_gpu} MB free for it, {need:.0f} MB needed), so answers come slower",
                "cpu": "runs on the CPU" + ("" if free_gpu is None else f" (only {free_gpu} MB of GPU memory free for it)")}[fit]
        return {"name": name, "size_mb": round(size_mb, 1), "download_bytes": 0 if reused else download_bytes,
                "reused": reused, "gpu_fit": fit, "needs_mb": need,
                "gpu_free_for_model_mb": free_gpu, "note": note, "why": why}

    def fits_ram(size_mb: float) -> bool:
        return ram_mb is None or needs_mb(size_mb) <= ram_mb

    if choices.model:
        match = next((m for m in installed if m["name"] in (choices.model, choices.model + ":latest")), None)
        if match:
            return describe(match["name"], match["size_mb"], True, "chosen by you")
        cand = next((c for c in candidates if c["name"] == choices.model), None)
        if cand is None:
            return {"name": "", "error": f"{choices.model} is not installed and is not one of the models this installer offers"}
        size_mb = cand["download_bytes"] / 2**20
        if not fits_ram(size_mb):
            return {"name": "", "error": f"{cand['name']} needs {needs_mb(size_mb):.0f} MB and this machine has {ram_mb} MB of RAM"}
        return describe(cand["name"], size_mb, False, "chosen by you", cand["download_bytes"])
    usable = [m for m in installed if fits_ram(m["size_mb"])]
    if free_gpu is not None:
        fitting = [m for m in usable if gpu_fit(m["size_mb"], free_gpu) == "fits"]
        if fitting:
            best = max(fitting, key=lambda m: m["size_mb"])
            return describe(best["name"], best["size_mb"], True, "the largest installed model that can call tools and fits the GPU")
    if usable:
        best = min(usable, key=lambda m: m["size_mb"])
        return describe(best["name"], best["size_mb"], True, "already installed and able to call tools; the smallest of them spills the least")
    if choices.offline:
        return {"name": "", "error": "offline, and no installed Ollama model can call tools"}
    pullable = [c for c in candidates if fits_ram(c["download_bytes"] / 2**20)
                and (free_disk_mb is None or c["download_bytes"] / 2**20 < free_disk_mb)]
    if not pullable:
        return {"name": "", "error": "no model this installer offers fits this machine's RAM and free disk"}
    if free_gpu is not None:
        fitting = [c for c in pullable if gpu_fit(c["download_bytes"] / 2**20, free_gpu) == "fits"]
        if fitting:
            best = max(fitting, key=lambda c: c["download_bytes"])
            return describe(best["name"], best["download_bytes"] / 2**20, False, "the largest offered model that fits the GPU",
                            best["download_bytes"])
    best = min(pullable, key=lambda c: c["download_bytes"])
    return describe(best["name"], best["download_bytes"] / 2**20, False, "the smallest offered model; nothing larger fits",
                    best["download_bytes"])


def plan(machine: Machine, manifest: Manifest, choices: Choices | None = None) -> dict[str, Any]:
    choices = choices or Choices()
    platform = _platform(machine)
    gpu = machine.value("gpu") or {}
    audio = machine.value("audio") or {}
    ollama = machine.value("ollama") or {}
    existing = machine.value("existing") or {}
    disk = machine.value("disk") or {}
    free_mb = disk.get("free_mb")
    nvidia = gpu.get("vendor") == "NVIDIA"
    tiers = {t: bool(choices.tiers.get(t, False)) for t in DEFAULT_TIERS}
    tiers["core"] = True
    unavailable: list[dict[str, str]] = []
    if tiers["voice"] and audio.get("inputs") == 0:
        unavailable.append({"feature": "speaking to the assistant", "why": "no microphone was found; typed chat still works"})
    gpu_speech = choices.gpu_speech if choices.gpu_speech is not None else (nvidia and tiers["voice"])
    if gpu_speech and not nvidia:
        unavailable.append({"feature": "speech recognition on the GPU", "why": "it needs an NVIDIA GPU"})
        gpu_speech = False
    if not ollama.get("running"):
        unavailable.append({"feature": "answers from a local model", "why": ollama.get("reason") or "Ollama is not running"})
    pythons = machine.value("python") or []
    reuse_python = pythons[0] if pythons else None

    by_id = manifest.by_id
    candidates = by_id.get("llm-model", {}).get("candidates", [])
    model = choose_model(machine, candidates, choices, gpu_speech, free_mb)
    if model.get("error"):
        unavailable.append({"feature": "a chat model", "why": model["error"]})

    installed = set(existing.get("installed_components") or [])
    rows: list[dict[str, Any]] = []
    for c in manifest.components:
        row = {"id": c["id"], "title": c["title"], "stage": c["stage"], "tier": c["tier"], "required": c["required"],
               "download_bytes": 0, "disk_bytes": 0, "irreversible": c["rollback"] == NOT_REVERSIBLE}
        if platform not in c["platforms"]:
            row.update(action="skip", reason=f"not offered on {platform}")
        elif not tiers.get(c["tier"], False):
            row.update(action="skip", reason=f"the {c['tier']} tier is off")
        elif c.get("requires") == "nvidia" and not gpu_speech:
            row.update(action="skip", reason="needs an NVIDIA GPU" if not nvidia else "GPU speech is off")
        elif c["id"] == "python-runtime" and reuse_python:
            row.update(action="reuse", reason=f"Python {reuse_python['version']} is installed", python=reuse_python["path"])
        elif c["id"] == "llm-model":
            if not model.get("name"):
                row.update(action="skip", reason=model.get("error", "no model"))
            elif model["reused"]:
                row.update(action="reuse", reason=f"{model['name']} is already in Ollama", model=model["name"])
            else:
                row.update(action="install", reason=model["why"], model=model["name"],
                           download_bytes=model["download_bytes"], disk_bytes=model["download_bytes"])
        elif c["id"] == "vision-model" and any(m["name"] in (c.get("model"), f"{c.get('model')}:latest")
                                               for m in ollama.get("models", [])):
            row.update(action="reuse", reason=f"{c['model']} is already in Ollama")
        elif c["id"] == "ollama" and ollama.get("running"):
            row.update(action="reuse", reason=f"Ollama {ollama.get('version', '')} is running".replace("  ", " "))
        elif c["id"] in installed:
            row.update(action="reuse", reason="installed and verified before; checked again")
        elif c["id"] in set(existing.get("files_present") or []):
            row.update(action="reuse", reason="the pinned files are already in place; their hashes are checked again")
        else:
            size = c["size"]
            row.update(action="install", reason=c["reason"], download_bytes=size.get("download_bytes") or 0,
                       disk_bytes=size.get("disk_bytes") or 0, size_unverified=size.get("download_bytes") is None)
        rows.append(row)
    active = [r for r in rows if r["action"] != "skip"]
    download = sum(r["download_bytes"] for r in active if r["action"] == "install")
    keep = sum(r["disk_bytes"] for r in active if r["action"] == "install")
    needed = int((keep + download) * (1 + DISK_MARGIN))
    free_bytes = free_mb * 2**20 if isinstance(free_mb, int) else None
    outside = []
    for r in active:
        note = by_id[r["id"]].get("outside_install")
        if note and r["action"] == "install":
            outside.append({"component": r["id"], "change": note})
    hosts = sorted({h for r in active if r["action"] == "install" for h in by_id[r["id"]].get("hosts", [])})
    return {
        "platform": platform,
        "offline": choices.offline,
        "tiers": tiers,
        "gpu_speech": gpu_speech,
        "python": {"reuse": reuse_python} if reuse_python else {"private": "the pinned Python 3.13.15 runtime"},
        "model": model,
        "components": rows,
        "totals": {"download_bytes": download, "disk_bytes": keep, "needed_with_margin_bytes": needed,
                   "free_bytes": free_bytes, "margin": DISK_MARGIN,
                   "fits": None if free_bytes is None else needed <= free_bytes},
        "outside_install": outside,
        "unavailable": unavailable,
        # Only steps that change something: a check-only component ("nothing"
        # to install) has nothing to undo, and listing it hid the ones that do.
        "irreversible": [r["id"] for r in active if r["irreversible"] and r["action"] == "install"
                         and by_id[r["id"]]["install"] != "nothing"],
        "hosts": [] if choices.offline else hosts,
        "unverified_sizes": [r["id"] for r in active if r.get("size_unverified")],
        "path_problem": path_problem(disk, platform),
    }
