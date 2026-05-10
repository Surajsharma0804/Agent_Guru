"""Sleep/Wake Coordinator - Manages power mode transitions across all components.

Coordinates sleep/wake transitions to optimise battery usage:
- Sleep mode: <5% battery per hour (wake word detection only)
- Wake mode:  <10% battery per hour (full processing)

Performance Characteristics:
    - Time Complexity: O(c) where c is number of registered components
    - Space Complexity: O(c) for component registry
    - Transition latency: <100ms

Validates: Requirement 12.2, 12.3, 12.10
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Auto-sleep after this many seconds of inactivity in WAKE mode
DEFAULT_AUTO_SLEEP_SECONDS = 30


class PowerMode(Enum):
    """Component power mode."""

    SLEEP = "sleep"
    WAKE = "wake"


@dataclass
class ComponentPowerState:
    """Power state for a single component.

    Attributes:
        name: Component identifier.
        mode: Current power mode.
        last_transition: Timestamp of last mode change.
        transition_count: Total number of mode transitions.

    """

    name: str
    mode: PowerMode
    last_transition: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    transition_count: int = 0


# Async callback type: (component_name, mode) -> None
ModeChangeCallback = Callable[[str, PowerMode], Coroutine[Any, Any, None]]


class SleepWakeCoordinator:
    """Coordinates sleep/wake transitions across all AGENT_GURU components.

    Manages:
    - Per-component power state tracking
    - Coordinated mode transitions (all components together)
    - Auto-sleep timer after inactivity
    - Battery usage optimisation

    Time Complexity: O(c) per transition
    Space Complexity: O(c) for component states

    Example:
        >>> coordinator = SleepWakeCoordinator()
        >>> coordinator.register_component("speech_engine")
        >>> coordinator.register_component("llm_runtime")
        >>> await coordinator.enter_sleep_mode()
        >>> await coordinator.enter_wake_mode()

    Validates: Requirements 12.2, 12.3, 12.10

    """

    def __init__(
        self,
        auto_sleep_seconds: float = DEFAULT_AUTO_SLEEP_SECONDS,
    ) -> None:
        """Initialise the sleep/wake coordinator.

        Args:
            auto_sleep_seconds: Inactivity timeout before auto-sleep in WAKE mode.

        Raises:
            ValueError: If auto_sleep_seconds < 0.

        """
        if auto_sleep_seconds < 0:
            msg = "auto_sleep_seconds must be >= 0"
            raise ValueError(msg)

        self._auto_sleep_seconds = auto_sleep_seconds
        self._components: dict[str, ComponentPowerState] = {}
        self._current_mode: PowerMode = PowerMode.SLEEP
        self._callback: ModeChangeCallback | None = None
        self._auto_sleep_task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._last_activity: datetime = datetime.now(tz=UTC)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_component(self, name: str) -> None:
        """Register a component for power state management.

        Args:
            name: Unique component name.

        Raises:
            ValueError: If component is already registered.

        """
        if name in self._components:
            msg = f"Component '{name}' is already registered"
            raise ValueError(msg)
        self._components[name] = ComponentPowerState(
            name=name,
            mode=PowerMode.SLEEP,
        )
        logger.debug("Registered component '%s' for power management", name)

    def deregister_component(self, name: str) -> None:
        """Remove a component from power state management.

        Args:
            name: Component name to remove.

        Raises:
            KeyError: If component is not registered.

        """
        if name not in self._components:
            msg = f"Component '{name}' is not registered"
            raise KeyError(msg)
        del self._components[name]

    def set_mode_callback(self, callback: ModeChangeCallback) -> None:
        """Set a callback invoked on each component mode change.

        Args:
            callback: Async callable(component_name, new_mode).

        """
        self._callback = callback

    # ------------------------------------------------------------------
    # Mode transitions
    # ------------------------------------------------------------------

    async def enter_sleep_mode(self) -> None:
        """Transition all components to sleep mode.

        Sleep mode characteristics:
        - Minimal CPU usage (<1%)
        - Wake word detection only
        - No LLM inference or network activity
        - Target: <5% battery per hour

        Validates: Requirement 12.2, 12.3
        """
        self._current_mode = PowerMode.SLEEP
        self._cancel_auto_sleep()

        for state in self._components.values():
            await self._set_component_mode(state, PowerMode.SLEEP)

        logger.info("All components transitioned to SLEEP mode")

    async def enter_wake_mode(self) -> None:
        """Transition all components to wake mode.

        Wake mode characteristics:
        - Full voice processing and LLM inference
        - Network activity enabled
        - Target: <10% battery per hour

        Validates: Requirement 12.2, 12.3
        """
        self._current_mode = PowerMode.WAKE
        self._last_activity = datetime.now(tz=UTC)

        for state in self._components.values():
            await self._set_component_mode(state, PowerMode.WAKE)

        # Start auto-sleep timer if configured
        if self._auto_sleep_seconds > 0:
            self._start_auto_sleep_timer()

        logger.info("All components transitioned to WAKE mode")

    def record_activity(self) -> None:
        """Record user activity to reset the auto-sleep timer."""
        self._last_activity = datetime.now(tz=UTC)
        if self._auto_sleep_seconds > 0 and self._current_mode == PowerMode.WAKE:
            self._start_auto_sleep_timer()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def current_mode(self) -> PowerMode:
        """Current system-wide power mode."""
        return self._current_mode

    def get_component_mode(self, name: str) -> PowerMode:
        """Return the current power mode for a component.

        Args:
            name: Component name.

        Returns:
            Current PowerMode.

        Raises:
            KeyError: If component is not registered.

        """
        if name not in self._components:
            msg = f"Component '{name}' is not registered"
            raise KeyError(msg)
        return self._components[name].mode

    def list_components(self) -> list[ComponentPowerState]:
        """Return power state for all registered components."""
        return list(self._components.values())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _set_component_mode(self, state: ComponentPowerState, mode: PowerMode) -> None:
        """Update a component's power mode and invoke the callback."""
        if state.mode == mode:
            return

        state.mode = mode
        state.last_transition = datetime.now(tz=UTC)
        state.transition_count += 1

        if self._callback:
            try:
                await self._callback(state.name, mode)
            except Exception as exc:
                logger.exception("Mode callback failed for '%s': %s", state.name, exc)

    def _start_auto_sleep_timer(self) -> None:
        """(Re)start the auto-sleep countdown."""
        self._cancel_auto_sleep()

        async def _auto_sleep() -> None:
            await asyncio.sleep(self._auto_sleep_seconds)
            if self._current_mode == PowerMode.WAKE:
                logger.info("Auto-sleep triggered after %.1fs inactivity", self._auto_sleep_seconds)
                await self.enter_sleep_mode()

        self._auto_sleep_task = asyncio.create_task(_auto_sleep())

    def _cancel_auto_sleep(self) -> None:
        """Cancel any pending auto-sleep task."""
        if self._auto_sleep_task and not self._auto_sleep_task.done():
            self._auto_sleep_task.cancel()
            self._auto_sleep_task = None
