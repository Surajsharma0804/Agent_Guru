"""The one-call Windows process snapshot agrees with psutil and stays fast.

get_process_list() asked psutil for status, CPU and memory per process, which
re-reads the whole process table for every process the user cannot open:
3.9 to 5.8 s for 272 processes on the development laptop. The snapshot reads
the table once (about 10 ms there). These check that it reports the same
processes psutil does, that CPU percent follows psutil's definition, and that
the integration falls back to psutil if Windows refuses the call.
"""

from __future__ import annotations

import os
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows system call")


def test_structure_sizes_match_the_x64_layout():
    import ctypes

    from Agent_Guru.platform.windows import process_snapshot as ps

    assert ctypes.sizeof(ps._SystemProcessInformation) == 256  # nosec B101
    assert ctypes.sizeof(ps._SystemThreadInformation) == 80  # nosec B101


def test_snapshot_reports_this_process_like_psutil():
    import psutil

    from Agent_Guru.platform.windows import process_snapshot as ps

    me = psutil.Process(os.getpid())
    record = next(r for r in ps.snapshot() if r.pid == os.getpid())
    assert record.name.lower() == me.name().lower()  # nosec B101
    assert abs(record.create_time - me.create_time()) < 1.0  # nosec B101
    assert record.working_set > 0  # nosec B101
    assert not record.suspended  # nosec B101


def test_snapshot_covers_psutils_processes():
    import psutil

    from Agent_Guru.platform.windows import process_snapshot as ps

    ours = {r.pid for r in ps.snapshot()}
    theirs = set(psutil.pids())
    # Processes start and exit between the two reads.
    assert len(ours & theirs) >= 0.95 * len(theirs)  # nosec B101


def test_cpu_percent_follows_psutils_definition(monkeypatch):
    from Agent_Guru.platform.windows import process_snapshot as ps

    clock = iter([100.0, 102.0])
    monkeypatch.setattr(ps.time, "monotonic", lambda: next(clock))
    sampler = ps.CpuSampler()

    def rec(pid, cpu, start=1.0):
        return ps.ProcessRecord(pid=pid, name="x", create_time=start, cpu_seconds=cpu,
                                working_set=1, suspended=False)

    first = sampler.percent([rec(10, 5.0), rec(11, 1.0)])
    # 3 CPU seconds in 2 wall seconds: 150%, as psutil reports a process on two cores.
    # pid 11 was reused by a process started later: new process, first reading 0.0.
    second = sampler.percent([rec(10, 8.0), rec(11, 9.0, start=50.0)])
    assert first == {10: 0.0, 11: 0.0}  # nosec B101
    assert second == {10: 150.0, 11: 0.0}  # nosec B101


def test_full_listing_is_fast():
    from Agent_Guru.platform.windows.integration import WindowsIntegration

    integration = WindowsIntegration()
    integration.get_process_list()
    best = min(_timed(integration.get_process_list) for _ in range(3))
    assert best < 0.5  # nosec B101


def test_listing_falls_back_to_psutil_when_the_call_fails(monkeypatch):
    from Agent_Guru.platform.windows import process_snapshot as ps
    from Agent_Guru.platform.windows.integration import WindowsIntegration

    def refuse():
        raise OSError("NTSTATUS 0xC0000022")

    monkeypatch.setattr(ps, "snapshot", refuse)
    processes = WindowsIntegration().get_process_list(include_usage=False)
    assert any(p.pid == os.getpid() for p in processes)  # nosec B101


def _timed(fn) -> float:
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start
