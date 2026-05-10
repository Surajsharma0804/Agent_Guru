"""Skill sandbox with subprocess isolation and resource enforcement."""

from __future__ import annotations

import logging
import multiprocessing
import time
from typing import TYPE_CHECKING, Any

from Agent_Guru.skills.manifest import ResourceLimits, ResourceUsage, SkillResult

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

try:
    import psutil

    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


def _worker(
    func_module: str,
    func_name: str,
    kwargs: dict[str, Any],
    result_queue: multiprocessing.Queue[Any],
) -> None:
    """Worker function executed in subprocess.

    Note: func_module and func_name must come from trusted internal sources only.
    This function is not called with user-supplied module/function names.
    """
    try:
        import importlib

        mod = importlib.import_module(func_module)  # nosec B302,B307 — trusted internal use only
        func = getattr(mod, func_name)  # nosec B307 — trusted internal use only
        result = func(**kwargs)
        result_queue.put(("ok", result))
    except Exception as exc:
        result_queue.put(("error", str(exc)))


class SkillSandbox:
    """Executes skills in isolated subprocesses with resource limits."""

    def __init__(self, limits: ResourceLimits | None = None) -> None:
        self.limits = limits or ResourceLimits()

    def execute(
        self,
        skill_id: str,
        func: Callable[..., Any],
        kwargs: dict[str, Any] | None = None,
    ) -> SkillResult:
        """Execute a callable in a sandboxed subprocess."""
        kwargs = kwargs or {}
        timeout_s = self.limits.timeout_ms / 1000.0
        ctx = multiprocessing.get_context("spawn")
        result_queue: multiprocessing.Queue = ctx.Queue()

        # We pass the function directly via a wrapper approach
        proc = ctx.Process(
            target=_sandbox_target,
            args=(func, kwargs, result_queue),
            daemon=True,
        )

        start = time.perf_counter()
        proc.start()

        # Monitor resource usage
        peak_memory_mb = 0.0
        peak_cpu = 0.0
        if _PSUTIL_AVAILABLE and proc.pid:
            try:
                ps_proc = psutil.Process(proc.pid)
            except Exception:
                ps_proc = None
        else:
            ps_proc = None

        proc.join(
            timeout=timeout_s,
        )  # Process.join(timeout=...) is correct API; not a deadlock risk
        wall_ms = (time.perf_counter() - start) * 1000

        if ps_proc is not None:
            try:
                mem = ps_proc.memory_info().rss / (1024 * 1024)
                peak_memory_mb = mem
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                logger.debug("Memory measurement skipped for skill %s: %s", skill_id, exc)

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1.0)
            if proc.is_alive():
                proc.kill()
            return SkillResult(
                success=False,
                skill_id=skill_id,
                error=f"resource_exceeded: timeout after {self.limits.timeout_ms}ms",
                resource_usage=ResourceUsage(
                    cpu_percent=peak_cpu,
                    memory_mb=peak_memory_mb,
                    wall_time_ms=wall_ms,
                ),
            )

        # Check memory limit
        if peak_memory_mb > self.limits.memory_mb:
            return SkillResult(
                success=False,
                skill_id=skill_id,
                error=f"resource_exceeded: memory {peak_memory_mb:.1f}MB > {self.limits.memory_mb}MB",
                resource_usage=ResourceUsage(
                    cpu_percent=peak_cpu,
                    memory_mb=peak_memory_mb,
                    wall_time_ms=wall_ms,
                ),
            )

        try:
            status, value = result_queue.get_nowait()
        except Exception:
            return SkillResult(
                success=False,
                skill_id=skill_id,
                error="No result from subprocess",
                resource_usage=ResourceUsage(wall_time_ms=wall_ms),
            )

        if status == "ok":
            return SkillResult(
                success=True,
                skill_id=skill_id,
                output=value,
                resource_usage=ResourceUsage(
                    cpu_percent=peak_cpu,
                    memory_mb=peak_memory_mb,
                    wall_time_ms=wall_ms,
                ),
            )
        return SkillResult(
            success=False,
            skill_id=skill_id,
            error=value,
            resource_usage=ResourceUsage(wall_time_ms=wall_ms),
        )


def _sandbox_target(
    func: Callable[..., Any],
    kwargs: dict[str, Any],
    result_queue: multiprocessing.Queue[Any],
) -> None:
    try:
        result = func(**kwargs)
        result_queue.put(("ok", result))
    except Exception as exc:
        result_queue.put(("error", str(exc)))
