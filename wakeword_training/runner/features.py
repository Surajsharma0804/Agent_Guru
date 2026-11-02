"""Augment clips and compute openWakeWord features in parallel, with output independent of the worker count.

train.py's --augment_clips runs openWakeWord's augment_clips and then
compute_features_from_generator in one process, about 0.12 s per clip on the laptop:
about 95 minutes for both models' 48,000 clips, the longest stage of a run. It is
also unseeded (Python random, NumPy and torch generators are never seeded, and the
clip order is whatever the filesystem returns), so two runs never produce the same
features and a parallel version could not be checked against it.

Here the clip list is sorted and cut into batches of 16, as train.py batches them
(augmentation_batch_size), and every batch seeds random, NumPy and torch from
(run seed, batch number) before calling the same augment_clips. Augmentation is
forced onto the CPU in every worker: on the GPU, torch-audiomentations' BandStopFilter,
AddColoredNoise, AddBackgroundNoise and Gain gave different output for the same seed
on every call (the first version of this module set CUDA_VISIBLE_DEVICES="" inside the
worker, which on Windows did not hide the GPU, and 1 and 4 workers differed by up to
51 in some features). torch.cuda.is_available is patched to False instead, which
augment_clips reads at call time. Features
come from the same CPU onnxruntime path Agent Guru uses when listening. A batch's
features are then the same whichever worker computes it, so 1 worker and N workers
write byte-identical .npy files (features_test.py checks exactly that).
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import multiprocessing as mp
import os
from pathlib import Path

import numpy as np

BATCH = 16          # train.py's augmentation_batch_size
WORKER_GIB = 1.2    # measured: each worker holds about 0.4-1.1 GB (torch, onnxruntime, audio libs)
_STATE = {}


def total_length_for(positive_test_dir) -> int:
    """train.py's rule (median clip length + 750 ms, rounded; 32000 when close), over every test clip.

    train.py samples 50 clips at random for the median, so its value can change between runs;
    the median of all of them is the same quantity without the sampling noise.
    """
    import soundfile as sf
    lengths = [sf.info(f).frames for f in sorted(Path(positive_test_dir).glob("*.wav"))]
    total = int(round(np.median(lengths) / 1000) * 1000) + 12000
    if total < 32000 or abs(total - 32000) <= 4000:
        total = 32000
    return total


def _seed(run_seed: int, k: int) -> int:
    return int.from_bytes(hashlib.sha256(f"{run_seed}/{k}".encode()).digest()[:4], "little")


def _init(oww_src, background, rirs, total_length):
    os.environ["CUDA_VISIBLE_DEVICES"] = ""        # augmentation on the CPU in every worker
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    import sys
    sys.path.insert(0, oww_src)
    import colab313_compat  # noqa: F401
    import torch
    torch.set_num_threads(1)
    torch.cuda.is_available = lambda: False
    from openwakeword.utils import AudioFeatures
    _STATE.update(features=AudioFeatures(device="cpu", ncpu=1), background=background, rirs=rirs,
                  total_length=total_length)


def _work(task):
    import random
    import torch
    from openwakeword.data import augment_clips
    run_seed, first, batches = task
    if os.environ.get("FEATURES_TEST_DIE_AT") == str(first):   # features_test.py: a worker dying mid-run
        os._exit(3)
    out = []
    for j, paths in enumerate(batches):
        s = _seed(run_seed, first + j)
        random.seed(s)
        np.random.seed(s)
        torch.manual_seed(s)
        audio = next(augment_clips(paths, total_length=_STATE["total_length"], batch_size=len(paths),
                                   background_clip_paths=_STATE["background"], RIR_paths=_STATE["rirs"]))
        out.append(_STATE["features"].embed_clips(audio, batch_size=len(paths)).astype(np.float32))
    return first, np.concatenate(out)


def usable_cpus() -> int:
    """CPUs this process may run on, not CPUs in the machine.

    os.cpu_count() counts the whole node. Under SLURM a job gets --cpus-per-task of them
    (bound by affinity and announced in SLURM_CPUS_PER_TASK); sized by cpu_count, a 16-CPU
    job on a 128-core node would have started 127 feature workers.
    """
    import psutil
    try:
        n = len(psutil.Process().cpu_affinity())
    except Exception:
        n = os.cpu_count() or 2
    slurm = os.environ.get("SLURM_CPUS_PER_TASK")
    return min(n, int(slurm)) if slurm and slurm.isdigit() else n


def _cgroup_free_bytes(root="/"):
    """Memory the process's cgroup still allows (v2 or v1), or None outside a limiting cgroup."""
    root = Path(root)
    try:
        lines = (root / "proc/self/cgroup").read_text().splitlines()
    except OSError:
        return None
    for ln in lines:
        _, controllers, path = ln.split(":", 2)
        rel = path.lstrip("/")
        if controllers == "":                                            # v2
            d = root / "sys/fs/cgroup" / rel
            limit, used = d / "memory.max", d / "memory.current"
        elif "memory" in controllers.split(","):                         # v1
            d = root / "sys/fs/cgroup/memory" / rel
            limit, used = d / "memory.limit_in_bytes", d / "memory.usage_in_bytes"
        else:
            continue
        try:
            lim = limit.read_text().strip()
            if lim == "max" or int(lim) >= 2**60:                       # no limit set
                continue
            return int(lim) - int(used.read_text().strip())
        except (OSError, ValueError):
            continue
    return None


def usable_ram_gib(cgroup_root="/") -> float:
    """Free memory this job may still use: the machine's free memory, capped by the job's limit.

    psutil reports the node's free memory, which on a cluster node is far more than the job's
    --mem; the scheduler kills a job that crosses its limit, whatever the node has free. The
    cgroup's own accounting is used where it can be read; otherwise SLURM's announced limit
    less what this process already holds.
    """
    import psutil
    free = psutil.virtual_memory().available
    cg = _cgroup_free_bytes(cgroup_root) if os.name != "nt" else None
    if cg is not None:
        free = min(free, cg)
    else:
        mb = os.environ.get("SLURM_MEM_PER_NODE")
        if mb and mb.isdigit():
            free = min(free, int(mb) * 2**20 - psutil.Process().memory_info().rss)
    return max(0.0, free / 2**30)


def default_workers() -> int:
    """One per usable CPU, less one, and no more than the job's free memory holds at WORKER_GIB each."""
    by_ram = int(usable_ram_gib() / WORKER_GIB)
    return max(1, min(usable_cpus() - 1, by_ram))


def augment_and_featurize(clips, out_npy, total_length, background, rirs, oww_src, run_seed, workers,
                          tasks_per_worker=8, log=print):
    """Write features for every clip to out_npy (rows in sorted clip order), using `workers` processes."""
    from numpy.lib.format import open_memmap
    clips = sorted(str(c) for c in clips)
    batches = [clips[i:i + BATCH] for i in range(0, len(clips), BATCH)]
    per = max(1, min(8, len(batches) // max(1, workers * tasks_per_worker)))
    tasks = [(run_seed, k, batches[k:k + per]) for k in range(0, len(batches), per)]
    tmp = Path(str(out_npy) + ".partial.npy")
    rows = None
    # ProcessPoolExecutor, not multiprocessing.Pool: when a worker died (11 workers on the
    # 15.7 GB laptop ran out of memory) Pool waited forever for its lost task, silently.
    # The executor raises BrokenProcessPool instead, and the stage fails loudly.
    os.environ["CUDA_VISIBLE_DEVICES"] = ""   # set before the workers start, as a second guard
    with cf.ProcessPoolExecutor(workers, mp_context=mp.get_context("spawn"), initializer=_init,
                                initargs=(str(oww_src), list(background), list(rirs), total_length)) as pool:
        done = 0
        for first, feats in pool.map(_work, tasks):
            if rows is None:
                rows = open_memmap(tmp, mode="w+", dtype=np.float32, shape=(len(clips),) + feats.shape[1:])
            start = first * BATCH
            rows[start:start + len(feats)] = feats
            done += len(feats)
            if done % (BATCH * 200) < len(feats) or done == len(clips):
                log(f"  features {Path(out_npy).name}: {done}/{len(clips)}")
    rows.flush()
    del rows
    os.replace(tmp, out_npy)
