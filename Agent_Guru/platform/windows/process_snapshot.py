"""Every process's identity and resource use from one Windows system call.

WindowsIntegration.get_process_list() used to ask psutil for status, CPU and
memory process by process. For each process the user may not open (services,
other users, protected processes, most of a normal list) psutil falls back to
NtQuerySystemInformation, which returns the WHOLE process table, and does so
again for each attribute: the cost grows with the square of the process count.
Measured on the development laptop: 3.9 to 5.8 s for 272 processes, the status
read alone 1.7 s.

NtQuerySystemInformation(SystemProcessInformation) is the call Task Manager
uses. It returns, for every process at once and without opening any of them,
the image name, start time, user and kernel CPU time, working set and each
thread's state. psutil reads the same fields from the same structure in its
fallback, so the numbers agree with psutil's; this just reads the table once.

Windows only. snapshot() raises OSError if the call fails, so a caller can
fall back to psutil.
"""

from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass

_SYSTEM_PROCESS_INFORMATION = 5
_STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
# FILETIME counts 100 ns intervals from 1601-01-01; the Unix epoch is this many later.
_EPOCH_AS_FILETIME = 116444736000000000
# KTHREAD_STATE Waiting and KWAIT_REASON Suspended: psutil calls a process
# "stopped" when every one of its threads is in that state.
_THREAD_WAITING = 5
_WAIT_SUSPENDED = 5


class _UnicodeString(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", ctypes.c_void_p),
    ]


class _SystemProcessInformation(ctypes.Structure):
    _fields_ = [
        ("NextEntryOffset", wintypes.ULONG),
        ("NumberOfThreads", wintypes.ULONG),
        ("WorkingSetPrivateSize", ctypes.c_longlong),
        ("HardFaultCount", wintypes.ULONG),
        ("NumberOfThreadsHighWatermark", wintypes.ULONG),
        ("CycleTime", ctypes.c_ulonglong),
        ("CreateTime", ctypes.c_longlong),
        ("UserTime", ctypes.c_longlong),
        ("KernelTime", ctypes.c_longlong),
        ("ImageName", _UnicodeString),
        ("BasePriority", wintypes.LONG),
        ("UniqueProcessId", ctypes.c_void_p),
        ("InheritedFromUniqueProcessId", ctypes.c_void_p),
        ("HandleCount", wintypes.ULONG),
        ("SessionId", wintypes.ULONG),
        ("UniqueProcessKey", ctypes.c_size_t),
        ("PeakVirtualSize", ctypes.c_size_t),
        ("VirtualSize", ctypes.c_size_t),
        ("PageFaultCount", wintypes.ULONG),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivatePageCount", ctypes.c_size_t),
        ("ReadOperationCount", ctypes.c_longlong),
        ("WriteOperationCount", ctypes.c_longlong),
        ("OtherOperationCount", ctypes.c_longlong),
        ("ReadTransferCount", ctypes.c_longlong),
        ("WriteTransferCount", ctypes.c_longlong),
        ("OtherTransferCount", ctypes.c_longlong),
    ]


class _SystemThreadInformation(ctypes.Structure):
    _fields_ = [
        ("KernelTime", ctypes.c_longlong),
        ("UserTime", ctypes.c_longlong),
        ("CreateTime", ctypes.c_longlong),
        ("WaitTime", wintypes.ULONG),
        ("StartAddress", ctypes.c_void_p),
        ("UniqueProcess", ctypes.c_void_p),
        ("UniqueThread", ctypes.c_void_p),
        ("Priority", wintypes.LONG),
        ("BasePriority", wintypes.LONG),
        ("ContextSwitches", wintypes.ULONG),
        ("ThreadState", wintypes.ULONG),
        ("WaitReason", wintypes.ULONG),
    ]


@dataclass(frozen=True)
class ProcessRecord:
    """One process as the kernel reports it. Times in seconds."""

    pid: int
    name: str
    create_time: float  # Unix epoch seconds; 0.0 for the idle and system processes
    cpu_seconds: float  # user + kernel
    working_set: int  # bytes; what psutil calls rss
    suspended: bool


_ntdll = None


def _query() -> ctypes.Array:
    global _ntdll
    if _ntdll is None:
        _ntdll = ctypes.WinDLL("ntdll")
        _ntdll.NtQuerySystemInformation.argtypes = [
            wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG),
        ]
        _ntdll.NtQuerySystemInformation.restype = ctypes.c_long
    size = 1 << 20
    for _ in range(8):
        buf = ctypes.create_string_buffer(size)
        needed = wintypes.ULONG(0)
        status = _ntdll.NtQuerySystemInformation(
            _SYSTEM_PROCESS_INFORMATION, buf, size, ctypes.byref(needed),
        ) & 0xFFFFFFFF
        if status == 0:
            return buf
        if status != _STATUS_INFO_LENGTH_MISMATCH:
            msg = f"NtQuerySystemInformation failed with NTSTATUS 0x{status:08X}"
            raise OSError(msg)
        # Processes can start between the size query and the read.
        size = max(size * 2, needed.value + (1 << 16))
    msg = "NtQuerySystemInformation: process table kept outgrowing the buffer"
    raise OSError(msg)


def snapshot() -> list[ProcessRecord]:
    """Read every process in one call. Raises OSError if Windows refuses."""
    buf = _query()
    base = ctypes.addressof(buf)
    proc_size = ctypes.sizeof(_SystemProcessInformation)
    thread_size = ctypes.sizeof(_SystemThreadInformation)
    records = []
    offset = 0
    while True:
        info = _SystemProcessInformation.from_address(base + offset)
        pid = info.UniqueProcessId or 0
        if info.ImageName.Buffer and info.ImageName.Length:
            name = ctypes.wstring_at(info.ImageName.Buffer, info.ImageName.Length // 2)
        else:
            name = "System Idle Process" if pid == 0 else "System"
        threads = [
            _SystemThreadInformation.from_address(base + offset + proc_size + i * thread_size)
            for i in range(info.NumberOfThreads)
        ]
        suspended = bool(threads) and all(
            t.ThreadState == _THREAD_WAITING and t.WaitReason == _WAIT_SUSPENDED for t in threads
        )
        create = info.CreateTime
        # psutil reports 0.0 for the idle and System processes, whose kernel
        # start time is the boot time; keep the same convention.
        if pid in (0, 4):
            create = 0
        records.append(
            ProcessRecord(
                pid=pid,
                name=name,
                create_time=(create - _EPOCH_AS_FILETIME) / 1e7 if create > _EPOCH_AS_FILETIME else 0.0,
                cpu_seconds=(info.UserTime + info.KernelTime) / 1e7,
                working_set=info.WorkingSetSize,
                suspended=suspended,
            ),
        )
        if info.NextEntryOffset == 0:
            return records
        offset += info.NextEntryOffset


class CpuSampler:
    """CPU percent per process between successive snapshots, as psutil computes it.

    psutil's Process.cpu_percent(interval=None) is (CPU seconds used since the
    previous call) / (wall seconds since then) * 100, so a process busy on two
    cores reads 200; a process seen for the first time reads 0.0. A pid reused
    by a new process is told apart by its start time.
    """

    def __init__(self) -> None:
        self._last: dict[tuple[int, float], tuple[float, float]] = {}
        # get_process_list() runs on executor threads; two overlapping calls
        # must not interleave their read and replace of the previous sample.
        self._lock = threading.Lock()

    def percent(self, records: list[ProcessRecord]) -> dict[int, float]:
        with self._lock:
            return self._percent(records)

    def _percent(self, records: list[ProcessRecord]) -> dict[int, float]:
        now = time.monotonic()
        result: dict[int, float] = {}
        current: dict[tuple[int, float], tuple[float, float]] = {}
        for r in records:
            key = (r.pid, r.create_time)
            previous = self._last.get(key)
            if previous is None or now <= previous[1]:
                result[r.pid] = 0.0
            else:
                result[r.pid] = round(max(0.0, r.cpu_seconds - previous[0]) / (now - previous[1]) * 100, 1)
            current[key] = (r.cpu_seconds, now)
        # Only processes still running are kept, so the table cannot grow.
        self._last = current
        return result
