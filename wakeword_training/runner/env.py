"""What this machine is, and the settings chosen from it. Every choice is printed and recorded.

The same runner runs on the Windows laptop (RTX 2050, 4 GB), a Linux A100 (40 or 80 GB)
and Colab, so device, Parler precision, Parler batch size and feature workers are read off
the hardware, each with an override flag.
"""
from __future__ import annotations

import os
import platform
import sys


def detect():
    import psutil
    import torch
    info = {"os": platform.system(), "python": sys.version.split()[0], "torch": torch.__version__,
            "cpus": os.cpu_count(), "ram_gib": round(psutil.virtual_memory().total / 2**30, 1),
            "ram_free_gib": round(psutil.virtual_memory().available / 2**30, 1), "cuda": torch.cuda.is_available()}
    # What this job may use, which on a cluster node is much less than the node's totals above.
    from features import usable_cpus, usable_ram_gib
    info.update(job_cpus=usable_cpus(), job_ram_free_gib=round(usable_ram_gib(), 1))
    if info["cuda"]:
        p = torch.cuda.get_device_properties(0)
        info.update(gpu=p.name, vram_gib=round(p.total_memory / 2**30, 1), capability=f"{p.major}.{p.minor}",
                    cuda_runtime=torch.version.cuda)
    return info


def choose(info, args):
    """Parler dtype and batch ceiling, feature workers; overrides win.

    dtype: bf16 on compute capability >= 8.0 (Ampere: A100, RTX 30xx, this laptop's RTX 2050).
    Measured on the RTX 2050 against fp16 with the same prompts: empty generations fell from
    3.1% to 0.3% (English) and 12.0% to 5.2% (Hindi) at equal quality (47 vs 46 of 50 heard
    by Whisper), so fp16 itself was producing broken clips. fp16 below 8.0 (T4, which has no
    fast bf16); fp32 on the CPU.
    Batch: Parler's memory is 1.8 GiB of half-precision weights plus about 0.05 GiB per clip
    in a batch at the 6 s Hindi cap (measured 2.0 GiB at batch 8, 3.0 GiB at 32). Memory
    stops limiting long before speed stops improving, so the ceiling only bounds the probe
    (generation.py picks the fastest size it measures, up to this).
    """
    c = {}
    if args.parler_dtype:
        c["parler_dtype"] = args.parler_dtype
    elif not info["cuda"]:
        c["parler_dtype"] = "float32"
    else:
        major = int(info["capability"].split(".")[0])
        c["parler_dtype"] = "bfloat16" if major >= 8 else "float16"
    if args.parler_batch:
        c["parler_batch_max"] = args.parler_batch
    elif not info["cuda"]:
        c["parler_batch_max"] = 4
    else:
        fit = int((info["vram_gib"] * 0.8 - 1.8) / 0.05)
        c["parler_batch_max"] = max(4, min(512, 2 ** (fit.bit_length() - 1)))
    from features import default_workers
    c["feature_workers"] = args.workers or default_workers()
    return c
