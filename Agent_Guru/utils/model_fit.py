"""How much GPU memory a model needs, and whether it fits: one rule for every caller.

llm/model_catalog.py answered this for `agent-guru models`, and the installer
needs the same answer before Agent Guru's own packages exist. The catalog
lives in the llm package, whose __init__ imports pydantic, requests, psutil
and prometheus_client, none of which the installer's small launcher carries.
Copying the two numbers into the installer would let the two answers drift,
so the rule lives here, in a module that imports nothing, and both use it.
"""

from __future__ import annotations

#: Memory beyond the weights: KV cache, activations and the CUDA context,
#: at the 4k-token context the assistant uses. Ollama's own estimate is
#: close to this for 2B to 8B models.
OVERHEAD_FACTOR = 1.2
OVERHEAD_MB = 500

#: Below this share of its weights in GPU memory a model is called "cpu":
#: so few layers on the GPU that it runs about as fast as on the CPU alone.
PARTIAL_SHARE = 0.3


def needs_mb(size_mb: float) -> float:
    """GPU memory a model of *size_mb* on disk needs to run entirely on the GPU."""
    return round(size_mb * OVERHEAD_FACTOR + OVERHEAD_MB, 0)


def gpu_fit(size_mb: float, free_mb: float) -> str:
    """"fits", "partial" (some layers on the CPU, slower) or "cpu", against *free_mb* of GPU memory."""
    if needs_mb(size_mb) <= free_mb:
        return "fits"
    return "partial" if size_mb * PARTIAL_SHARE <= free_mb else "cpu"
