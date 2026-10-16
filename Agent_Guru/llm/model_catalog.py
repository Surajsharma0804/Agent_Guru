"""The models installed in Ollama, with their real size, and whether each fits this GPU.

llm/model_router/registry.py held hand-written metadata that nothing read
and that went stale with every pull. Choosing a model on this machine
turned on one fact it could not answer: which installed model fits in
the 4 GB of VRAM beside Whisper (gemma4 at 9.6 GB spills to system RAM;
a vision model swap costs 17 to 19 s). The catalog asks Ollama what is
installed (/api/tags, /api/show) and NVML how much GPU memory there is,
so its answer is always about this machine as it is now.

    python -m Agent_Guru models          the installed models
    python -m Agent_Guru models --json   the same, as JSON
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any

#: Memory beyond the weights: KV cache, activations and the CUDA context,
#: at the 4k-token context the assistant uses. Ollama's own estimate is
#: close to this for 2B to 8B models.
_OVERHEAD_FACTOR = 1.2
_OVERHEAD_MB = 500


@dataclass(slots=True)
class ModelEntry:
    name: str
    size_mb: float
    parameters: str = ""
    quantization: str = ""
    family: str = ""
    context_length: int = 0
    capabilities: list[str] = field(default_factory=list)
    #: "fits", "partial" (some layers on the CPU, slower) or "cpu", against
    #: the GPU's free memory; "" without an NVIDIA GPU.
    gpu_fit: str = ""
    needs_mb: float = 0.0


def _host() -> str:
    return (os.environ.get("OLLAMA_HOST", "").strip() or "http://localhost:11434").rstrip("/")


def _gpu_memory_mb() -> tuple[float, float]:
    """(total, used) GPU memory in MB, (0, 0) without NVML."""
    try:
        import ctypes

        from Agent_Guru.platform.hardware import nvml

        if not nvml._load():
            return 0.0, 0.0
        memory = nvml._Memory()
        if nvml._lib.nvmlDeviceGetMemoryInfo(nvml._handle, ctypes.byref(memory)) != 0:
            return 0.0, 0.0
        return memory.total / 2**20, memory.used / 2**20
    except Exception:
        return 0.0, 0.0


def installed(timeout: float = 10.0) -> list[ModelEntry]:
    """Every model Ollama has, with details; raises OSError when Ollama does not answer."""
    import httpx

    host = _host()
    try:
        with httpx.Client(timeout=timeout) as client:
            tags = client.get(f"{host}/api/tags").raise_for_status().json().get("models") or []
            total, used = _gpu_memory_mb()
            entries = []
            for tag in tags:
                name = tag.get("name") or tag.get("model") or ""
                details = tag.get("details") or {}
                entry = ModelEntry(
                    name=name, size_mb=round((tag.get("size") or 0) / 2**20, 1),
                    parameters=details.get("parameter_size", ""), quantization=details.get("quantization_level", ""),
                    family=details.get("family", ""),
                )
                try:
                    shown = client.post(f"{host}/api/show", json={"model": name}).raise_for_status().json()
                    info = shown.get("model_info") or {}
                    entry.context_length = int(next((v for k, v in info.items() if k.endswith(".context_length")), 0) or 0)
                    entry.capabilities = list(shown.get("capabilities") or [])
                except (httpx.HTTPError, ValueError, TypeError):
                    pass
                entry.needs_mb = round(entry.size_mb * _OVERHEAD_FACTOR + _OVERHEAD_MB, 0)
                if total:
                    free = total - used
                    entry.gpu_fit = "fits" if entry.needs_mb <= free else ("partial" if entry.size_mb * 0.3 <= free else "cpu")
                entries.append(entry)
    except httpx.HTTPError as exc:
        msg = f"Ollama at {host} did not answer: {exc}"
        raise OSError(msg) from exc
    return sorted(entries, key=lambda e: e.size_mb)


def find(name: str) -> ModelEntry | None:
    """The installed model called *name* (with or without ":latest"), or None."""
    want = name if ":" in name else f"{name}:latest"
    return next((e for e in installed() if e.name in (name, want)), None)


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m Agent_Guru models", description="The models installed in Ollama.")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args(argv)
    try:
        entries = installed()
    except OSError as exc:
        print(exc)  # noqa: T201  the command's output
        return 1
    if args.json:
        print(json.dumps([asdict(e) for e in entries], indent=2))  # noqa: T201
        return 0
    total, used = _gpu_memory_mb()
    if total:
        print(f"GPU memory: {total:.0f} MB, {total - used:.0f} MB free")  # noqa: T201
    for e in entries:
        caps = ",".join(e.capabilities)
        print(f"{e.name:28} {e.size_mb:8.0f} MB  {e.parameters:>6} {e.quantization:8} ctx {e.context_length:>7}  "  # noqa: T201
              f"{e.gpu_fit or '-':8} {caps}")
    return 0


def describe(entries: list[ModelEntry]) -> list[dict[str, Any]]:
    return [asdict(e) for e in entries]
