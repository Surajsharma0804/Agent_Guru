"""
Frame Dispatcher for the Agent Guru Vision System.

Receives raw frames and fans them out to all enabled vision modules in
parallel using ``asyncio.gather``.  Module failures are isolated: an
exception in one module does not prevent other modules from running.

Design notes:
- Each registered module handler is an async callable: ``(frame, frame_seq) → Any``.
- Modules can be enabled/disabled at runtime.
- The dispatcher optionally integrates with a VisionEventBus to skip modules
  that have no active subscribers (module suspension).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, Optional

import numpy as np
import structlog

from Agent_Guru.vision.bus import VisionEventBus

logger: structlog.BoundLogger = structlog.get_logger(__name__)

# Type alias for module handler callables
ModuleHandler = Callable[[np.ndarray, int], Coroutine[Any, Any, Any]]


class FrameDispatcher:
    """Fans out frames to all enabled vision modules concurrently.

    Args:
        event_bus: Optional VisionEventBus used for module suspension checks.
            When provided, modules with no subscribers are skipped.
    """

    def __init__(self, event_bus: Optional[VisionEventBus] = None) -> None:
        self._handlers: dict[str, ModuleHandler] = {}
        self._enabled: set[str] = set()
        self._event_bus: Optional[VisionEventBus] = event_bus

    # ------------------------------------------------------------------
    # Module registration
    # ------------------------------------------------------------------

    def register_module(self, name: str, handler: ModuleHandler) -> None:
        """Register a vision module handler.

        Newly registered modules are enabled by default.

        Args:
            name: Unique module name (e.g. "scene", "depth", "ocr").
            handler: Async callable ``(frame: np.ndarray, frame_seq: int) → Any``.
        """
        self._handlers[name] = handler
        self._enabled.add(name)
        logger.debug("Module registered", module=name)

    # ------------------------------------------------------------------
    # Enable / disable
    # ------------------------------------------------------------------

    def enable_module(self, name: str) -> None:
        """Enable a registered module so it receives frames.

        Args:
            name: Module name to enable.

        Raises:
            KeyError: If the module has not been registered.
        """
        if name not in self._handlers:
            raise KeyError(f"Module not registered: {name!r}")
        self._enabled.add(name)
        logger.debug("Module enabled", module=name)

    def disable_module(self, name: str) -> None:
        """Disable a registered module so it no longer receives frames.

        Args:
            name: Module name to disable.

        Raises:
            KeyError: If the module has not been registered.
        """
        if name not in self._handlers:
            raise KeyError(f"Module not registered: {name!r}")
        self._enabled.discard(name)
        logger.debug("Module disabled", module=name)

    def get_active_modules(self) -> list[str]:
        """Return the names of all currently enabled modules.

        Returns:
            Sorted list of enabled module names.
        """
        return sorted(self._enabled)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, frame: np.ndarray, frame_seq: int) -> dict[str, Any]:
        """Fan out a frame to all active modules concurrently.

        Each module runs as an independent coroutine via ``asyncio.gather``.
        Exceptions in individual modules are caught, logged, and recorded in
        the result dict under the module name with the exception as the value.

        Args:
            frame: Raw RGB frame as a uint8 ndarray of shape (H, W, 3).
            frame_seq: Monotonically increasing frame sequence number.

        Returns:
            Dict mapping module name → result (or Exception on failure).
        """
        active = self._get_dispatchable_modules()

        if not active:
            return {}

        results: dict[str, Any] = {}

        async def _run_module(name: str) -> None:
            handler = self._handlers[name]
            try:
                result = await handler(frame, frame_seq)
                results[name] = result
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Module raised exception during dispatch",
                    module=name,
                    frame_seq=frame_seq,
                    error=str(exc),
                )
                results[name] = exc

        await asyncio.gather(*(_run_module(name) for name in active))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_dispatchable_modules(self) -> list[str]:
        """Return enabled modules that should receive the current frame.

        When an event bus is attached, modules with no subscribers are
        excluded (module suspension per Requirement 12.6).
        """
        dispatchable: list[str] = []
        for name in sorted(self._enabled):
            if self._event_bus is not None and not self._event_bus.has_subscribers(name):
                logger.debug("Module suspended (no subscribers)", module=name)
                continue
            dispatchable.append(name)
        return dispatchable
