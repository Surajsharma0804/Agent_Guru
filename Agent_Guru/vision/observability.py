"""Observability module for the Agent Guru Vision System.

Provides:
- Structured logging via structlog for every VisionEvent.
- Prometheus metrics: frames_processed_total, events_emitted_total,
  inference_latency_seconds (histogram per module), gpu_memory_bytes_used,
  active_modules_count.
- Latency warning when any module exceeds its target by >50%.
- Error counter increment on unhandled module exception.

Requirements: 14.1-14.6
"""

from __future__ import annotations

import logging
import time
from typing import Any, Self

import structlog

logger: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics (optional - graceful fallback when not installed)
# ---------------------------------------------------------------------------

try:
    from prometheus_client import (  # type: ignore[import]  # noqa: F401
        REGISTRY,
        Counter,
        Gauge,
        Histogram,
    )

    _PROM_AVAILABLE = True

    frames_processed_total = Counter(
        "vision_frames_processed_total",
        "Total number of frames processed by the vision system",
    )

    events_emitted_total = Counter(
        "vision_events_emitted_total",
        "Total number of VisionEvents emitted",
        labelnames=["event_type", "source_module"],
    )

    inference_latency_seconds = Histogram(
        "vision_inference_latency_seconds",
        "Inference latency per vision module",
        labelnames=["module"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0),
    )

    gpu_memory_bytes_used = Gauge(
        "vision_gpu_memory_bytes_used",
        "GPU memory currently used by the vision system (bytes)",
    )

    active_modules_count = Gauge(
        "vision_active_modules_count",
        "Number of currently active vision modules",
    )

    module_error_total = Counter(
        "vision_module_error_total",
        "Total number of unhandled module exceptions",
        labelnames=["module"],
    )

except ImportError:
    _PROM_AVAILABLE = False

    class _NoOpCounter:
        def inc(self, *a: Any, **kw: Any) -> None: ...
        def labels(self, *a: Any, **kw: Any) -> _NoOpCounter:
            return self

    class _NoOpHistogram:
        def observe(self, *a: Any, **kw: Any) -> None: ...
        def labels(self, *a: Any, **kw: Any) -> _NoOpHistogram:
            return self

    class _NoOpGauge:
        def set(self, *a: Any, **kw: Any) -> None: ...
        def inc(self, *a: Any, **kw: Any) -> None: ...
        def dec(self, *a: Any, **kw: Any) -> None: ...

    frames_processed_total = _NoOpCounter()  # type: ignore[assignment]
    events_emitted_total = _NoOpCounter()  # type: ignore[assignment]
    inference_latency_seconds = _NoOpHistogram()  # type: ignore[assignment]
    gpu_memory_bytes_used = _NoOpGauge()  # type: ignore[assignment]
    active_modules_count = _NoOpGauge()  # type: ignore[assignment]
    module_error_total = _NoOpCounter()  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Per-module latency targets (seconds)
# ---------------------------------------------------------------------------

MODULE_LATENCY_TARGETS: dict[str, float] = {
    "scene": 0.050,
    "depth": 0.100,
    "ocr": 0.200,
    "handwriting": 0.500,
    "gesture": 1.0 / 20,  # 20 FPS → 50ms
    "pose": 1.0 / 15,  # 15 FPS → 67ms
    "screen": 0.300,
    "vqa": 2.000,
    "tracker": 0.010,
    "activity": 1.000,
    "privacy": 0.020,
}


# ---------------------------------------------------------------------------
# VisionObservability
# ---------------------------------------------------------------------------


class VisionObservability:
    """Centralised observability helper for the Vision System.

    Usage::

        obs = VisionObservability()

        # Record a frame being processed
        obs.record_frame()

        # Record an emitted event
        obs.record_event(event)

        # Record module inference latency
        with obs.time_module("scene"):
            result = await scene_module.classify(frame)

        # Record a module exception
        obs.record_error("scene", exc)
    """

    def __init__(self) -> None:
        self._log_level: int = logging.INFO

    # ------------------------------------------------------------------
    # Log level control (hot-reload without restart)
    # ------------------------------------------------------------------

    def set_log_level(self, level: str) -> None:
        """Change the log level at runtime without restart.

        Args:
            level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.

        """
        numeric = getattr(logging, level.upper(), logging.INFO)
        self._log_level = numeric
        logging.getLogger().setLevel(numeric)
        logger.info("VisionObservability: log level changed", level=level)

    # ------------------------------------------------------------------
    # Metrics helpers
    # ------------------------------------------------------------------

    def record_frame(self) -> None:
        """Increment the frames_processed_total counter."""
        frames_processed_total.inc()

    def record_event(self, event: Any) -> None:
        """Increment events_emitted_total and emit a structured log entry.

        Args:
            event: A VisionEvent instance.

        """
        events_emitted_total.labels(
            event_type=event.event_type,
            source_module=event.source_module,
        ).inc()
        logger.info(
            "VisionEvent emitted",
            event_type=event.event_type,
            source_module=event.source_module,
            confidence=event.confidence,
            timestamp=event.timestamp,
        )

    def record_latency(self, module: str, latency_seconds: float) -> None:
        """Record inference latency for a module and warn if over target.

        Args:
            module: Module name (e.g. "scene", "depth").
            latency_seconds: Measured latency in seconds.

        """
        inference_latency_seconds.labels(module=module).observe(latency_seconds)

        target = MODULE_LATENCY_TARGETS.get(module)
        if target is not None and latency_seconds > target * 1.5:
            logger.warning(
                "Module latency exceeded target by >50%",
                module=module,
                latency_ms=round(latency_seconds * 1000, 1),
                target_ms=round(target * 1000, 1),
            )

    def record_error(self, module: str, exc: Exception) -> None:
        """Record an unhandled module exception.

        Increments the error counter and logs the full stack trace.

        Args:
            module: Module name where the exception occurred.
            exc: The exception instance.

        """
        module_error_total.labels(module=module).inc()
        logger.exception(
            "Unhandled module exception",
            module=module,
            error=str(exc),
        )

    def update_gpu_memory(self, bytes_used: int) -> None:
        """Update the GPU memory gauge.

        Args:
            bytes_used: Current GPU memory usage in bytes.

        """
        gpu_memory_bytes_used.set(bytes_used)

    def update_active_modules(self, count: int) -> None:
        """Update the active modules gauge.

        Args:
            count: Number of currently active modules.

        """
        active_modules_count.set(count)

    # ------------------------------------------------------------------
    # Context manager for timing
    # ------------------------------------------------------------------

    class _ModuleTimer:
        """Context manager that records module latency on exit."""

        def __init__(self, obs: VisionObservability, module: str) -> None:
            self._obs = obs
            self._module = module
            self._start: float = 0.0

        def __enter__(self) -> Self:
            self._start = time.perf_counter()
            return self

        def __exit__(self, *args: object) -> None:
            elapsed = time.perf_counter() - self._start
            self._obs.record_latency(self._module, elapsed)

    def time_module(self, module: str) -> _ModuleTimer:
        """Return a context manager that times a module's execution.

        Args:
            module: Module name to time.

        Returns:
            Context manager that records latency on exit.

        """
        return self._ModuleTimer(self, module)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_observability: VisionObservability | None = None


def get_observability() -> VisionObservability:
    """Return the module-level VisionObservability singleton."""
    global _default_observability
    if _default_observability is None:
        _default_observability = VisionObservability()
    return _default_observability
