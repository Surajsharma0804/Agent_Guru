"""Feature workers must fit the job, not the machine: run with python limits_test.py.

On a cluster node os.cpu_count() and psutil's free memory describe the whole node; a job
sized from them oversubscribes its CPUs and is killed at its memory limit. These checks pin
the CPU count to the process's affinity and SLURM_CPUS_PER_TASK, and the memory to the
cgroup's limit (v1 and v2 trees built in a temporary folder) or SLURM_MEM_PER_NODE.
"""
import os
import sys
import tempfile
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import features  # noqa: E402

GiB = 2**30


class Node:                      # a 1 TB node with most of it free
    available = 1000 * GiB
    total = 1024 * GiB


def tree(files):
    d = Path(tempfile.mkdtemp())
    for rel, text in files.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(text)
    return d


def main():
    psutil.virtual_memory = lambda: Node
    for k in ("SLURM_CPUS_PER_TASK", "SLURM_MEM_PER_NODE"):
        os.environ.pop(k, None)
    failures = []

    def expect(label, got, want):
        ok = got == want if not isinstance(want, tuple) else want[0] <= got <= want[1]
        print(f"{'ok  ' if ok else 'FAIL'} {label}: {got} (want {want})")
        if not ok:
            failures.append(label)

    all_cpus = psutil.Process().cpu_affinity()
    psutil.Process().cpu_affinity(all_cpus[:4])
    expect("CPUs under a 4-CPU affinity", features.usable_cpus(), 4)
    os.environ["SLURM_CPUS_PER_TASK"] = "2"
    expect("CPUs with SLURM_CPUS_PER_TASK=2", features.usable_cpus(), 2)
    os.environ.pop("SLURM_CPUS_PER_TASK")
    psutil.Process().cpu_affinity(all_cpus)

    v2 = tree({"proc/self/cgroup": "0::/slurm/job_7\n",
               "sys/fs/cgroup/slurm/job_7/memory.max": str(48 * GiB),
               "sys/fs/cgroup/slurm/job_7/memory.current": str(8 * GiB)})
    expect("cgroup v2 free bytes", features._cgroup_free_bytes(v2), 40 * GiB)
    v1 = tree({"proc/self/cgroup": "12:memory:/slurm/job_8\n11:cpuset:/slurm/job_8\n",
               "sys/fs/cgroup/memory/slurm/job_8/memory.limit_in_bytes": str(16 * GiB),
               "sys/fs/cgroup/memory/slurm/job_8/memory.usage_in_bytes": str(4 * GiB)})
    expect("cgroup v1 free bytes", features._cgroup_free_bytes(v1), 12 * GiB)
    unlimited = tree({"proc/self/cgroup": "0::/user.slice\n", "sys/fs/cgroup/user.slice/memory.max": "max",
                      "sys/fs/cgroup/user.slice/memory.current": "1"})
    expect("no cgroup limit", features._cgroup_free_bytes(unlimited), None)
    if os.name != "nt":
        expect("RAM under the v2 limit (GiB)", features.usable_ram_gib(v2), 40.0)
    os.environ["SLURM_MEM_PER_NODE"] = str(48 * 1024)
    rss = psutil.Process().memory_info().rss / GiB
    expect("RAM with SLURM_MEM_PER_NODE=48G (GiB)", round(features.usable_ram_gib("/nonexistent"), 1), round(48 - rss, 1))
    psutil.Process().cpu_affinity(all_cpus[:4])
    expect("workers for 4 CPUs and 48 GB", features.default_workers(), 3)
    psutil.Process().cpu_affinity(all_cpus)
    os.environ["SLURM_MEM_PER_NODE"] = str(3 * 1024)
    expect("workers for 3 GB", features.default_workers(), (1, 2))
    print("FAILED: " + ", ".join(failures) if failures else "all passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
