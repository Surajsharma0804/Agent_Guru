"""NVIDIA GPU counters through the driver's own NVML library, for one turn at a time.

The turn records said how long each stage took but nothing about the GPU
it ran on, so a slow turn could not be told apart from a GPU stuck in a
low power state (seen on this laptop: 210 MHz in P8 while answering).
nvml.dll / libnvidia-ml.so come with the NVIDIA driver, so this needs no
package. The total-energy counter makes a turn's energy one subtraction
between two reads instead of a polling thread.

Every function returns {} or None when there is no NVIDIA GPU, no driver
library, or the call fails: the readings are extra detail, never a
reason for a turn to fail.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
from typing import Any

logger = logging.getLogger(__name__)

_NVML_CLOCK_SM = 1
_lock = threading.Lock()
_lib: Any = None
_handle: Any = None
_tried = False


class _Utilization(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class _Memory(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]


def _load() -> bool:
    global _lib, _handle, _tried
    with _lock:
        if _tried:
            return _handle is not None
        _tried = True
        names = ["nvml.dll"] if sys.platform == "win32" else ["libnvidia-ml.so.1", "libnvidia-ml.so"]
        for name in names:
            try:
                lib = ctypes.CDLL(name)
                break
            except OSError:
                continue
        else:
            return False
        try:
            if lib.nvmlInit_v2() != 0:
                return False
            handle = ctypes.c_void_p()
            if lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(handle)) != 0:
                return False
        except (AttributeError, OSError):
            return False
        _lib, _handle = lib, handle
        return True


def ready() -> bool:
    """True once the library has been loaded (or found missing): read() then costs about 2 ms."""
    return _tried


def warm() -> None:
    """Load the library on a background thread. Its first load took 1.9 s here, too long inside a turn."""
    if not _tried:
        threading.Thread(target=_load, name="nvml-warm", daemon=True).start()


def read() -> dict[str, float]:
    """One reading of GPU 0: energy_mj (total since driver load), power_w, util_pct, mem_used_mb, sm_mhz, pstate."""
    if not _load():
        return {}
    out: dict[str, float] = {}
    with _lock:
        lib, h = _lib, _handle
        value = ctypes.c_ulonglong()
        if lib.nvmlDeviceGetTotalEnergyConsumption(h, ctypes.byref(value)) == 0:
            out["energy_mj"] = float(value.value)
        power = ctypes.c_uint()
        if lib.nvmlDeviceGetPowerUsage(h, ctypes.byref(power)) == 0:
            out["power_w"] = power.value / 1000.0
        util = _Utilization()
        if lib.nvmlDeviceGetUtilizationRates(h, ctypes.byref(util)) == 0:
            out["util_pct"] = float(util.gpu)
        memory = _Memory()
        if lib.nvmlDeviceGetMemoryInfo(h, ctypes.byref(memory)) == 0:
            out["mem_used_mb"] = memory.used / (1024 * 1024)
        clock = ctypes.c_uint()
        if lib.nvmlDeviceGetClockInfo(h, _NVML_CLOCK_SM, ctypes.byref(clock)) == 0:
            out["sm_mhz"] = float(clock.value)
        pstate = ctypes.c_int()
        if lib.nvmlDeviceGetPerformanceState(h, ctypes.byref(pstate)) == 0:
            out["pstate"] = float(pstate.value)
    return out


def turn_detail(before: dict[str, float], after: dict[str, float], seconds: float) -> dict[str, float]:
    """What a turn cost the GPU, from readings at its start and end: energy_j, avg_power_w and the end state."""
    if not after:
        return {}
    detail = {k: round(v, 1) for k, v in after.items() if k != "energy_mj"}
    if "energy_mj" in before and "energy_mj" in after and after["energy_mj"] >= before["energy_mj"]:
        joules = (after["energy_mj"] - before["energy_mj"]) / 1000.0
        detail["energy_j"] = round(joules, 2)
        if seconds > 0:
            detail["avg_power_w"] = round(joules / seconds, 2)
    return detail
