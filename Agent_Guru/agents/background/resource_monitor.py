"""
Resource Monitor - Monitors battery, thermal, network, and audio focus.

Tracks system resource states and triggers appropriate responses:
- Low battery (<20%): enter sleep mode
- Critical battery (<10%): stop all services
- Thermal critical: throttle / enter sleep mode
- Network offline: switch to offline mode
- Audio focus lost: pause audio processing

Performance Characteristics:
    - Time Complexity: O(1) per state update
    - Space Complexity: O(1) fixed state storage
    - Poll latency: <1ms

Validates: Requirement 12.9, 12.10, 12.15, 12.16
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Battery thresholds
BATTERY_LOW_THRESHOLD = 20.0       # % — enter sleep mode
BATTERY_CRITICAL_THRESHOLD = 10.0  # % — stop all services


class ThermalState(Enum):
    """Device thermal state levels."""

    NORMAL = "normal"
    FAIR = "fair"
    SERIOUS = "serious"
    CRITICAL = "critical"


class NetworkState(Enum):
    """Network connectivity state."""

    ONLINE = "online"
    OFFLINE = "offline"
    METERED = "metered"   # Connected but limited (mobile data)


class AudioFocusState(Enum):
    """Audio focus state."""

    GAINED = "gained"
    LOST = "lost"
    LOST_TRANSIENT = "lost_transient"   # Temporary loss (e.g. phone call)
    DUCKED = "ducked"                   # Reduced volume (e.g. notification)


@dataclass
class ResourceSnapshot:
    """Point-in-time snapshot of all monitored resources.

    Attributes:
        battery_percent: Battery level 0–100. None if not applicable.
        is_charging: Whether the device is currently charging.
        thermal_state: Current thermal state.
        network_state: Current network connectivity.
        audio_focus: Current audio focus state.
        timestamp: When this snapshot was taken.
    """

    battery_percent: Optional[float]
    is_charging: bool
    thermal_state: ThermalState
    network_state: NetworkState
    audio_focus: AudioFocusState
    timestamp: datetime = field(default_factory=datetime.now)


# Async callback type
ResourceCallback = Callable[[ResourceSnapshot], Coroutine[Any, Any, None]]


class ResourceMonitor:
    """Monitors system resources and triggers callbacks on state changes.

    Tracks:
    - Battery level and charging state
    - Thermal state (normal → critical)
    - Network connectivity (online/offline/metered)
    - Audio focus (gained/lost/ducked)

    Callbacks are invoked whenever any resource state changes.

    Time Complexity: O(cb) per update where cb is number of callbacks
    Space Complexity: O(1) for state + O(cb) for callbacks

    Example:
        >>> monitor = ResourceMonitor()
        >>> monitor.register_callback(my_handler)
        >>> await monitor.update_battery(15.0, is_charging=False)
        >>> snapshot = monitor.get_snapshot()

    Validates: Requirements 12.9, 12.10, 12.15, 12.16
    """

    def __init__(self) -> None:
        """Initialise the resource monitor with safe default states."""
        self._battery_percent: Optional[float] = 100.0
        self._is_charging: bool = False
        self._thermal_state: ThermalState = ThermalState.NORMAL
        self._network_state: NetworkState = NetworkState.ONLINE
        self._audio_focus: AudioFocusState = AudioFocusState.GAINED

        self._callbacks: list[ResourceCallback] = []

    # ------------------------------------------------------------------
    # Callback management
    # ------------------------------------------------------------------

    def register_callback(self, callback: ResourceCallback) -> None:
        """Register a callback invoked on any resource state change.

        Args:
            callback: Async callable(ResourceSnapshot).
        """
        self._callbacks.append(callback)

    def unregister_callback(self, callback: ResourceCallback) -> None:
        """Remove a previously registered callback.

        Args:
            callback: Callback to remove.

        Raises:
            ValueError: If callback is not registered.
        """
        self._callbacks.remove(callback)

    # ------------------------------------------------------------------
    # State updates
    # ------------------------------------------------------------------

    async def update_battery(
        self, percent: float, is_charging: bool = False
    ) -> None:
        """Update battery level and trigger callbacks.

        Args:
            percent: Battery percentage 0–100.
            is_charging: Whether the device is charging.

        Raises:
            ValueError: If percent is outside [0, 100].

        Validates: Requirement 12.5, 12.10
        """
        if not 0.0 <= percent <= 100.0:
            raise ValueError(f"Battery percent must be in [0, 100], got {percent}")

        self._battery_percent = percent
        self._is_charging = is_charging

        if percent <= BATTERY_CRITICAL_THRESHOLD and not is_charging:
            logger.warning("CRITICAL battery: %.1f%%", percent)
        elif percent <= BATTERY_LOW_THRESHOLD and not is_charging:
            logger.warning("LOW battery: %.1f%%", percent)

        await self._notify_callbacks()

    async def update_thermal_state(self, state: ThermalState) -> None:
        """Update thermal state and trigger callbacks.

        Args:
            state: New thermal state.

        Validates: Requirement 12.9
        """
        if state != self._thermal_state:
            logger.info("Thermal state changed: %s → %s", self._thermal_state.value, state.value)
            self._thermal_state = state
            await self._notify_callbacks()

    async def update_network_state(self, state: NetworkState) -> None:
        """Update network connectivity state and trigger callbacks.

        Args:
            state: New network state.

        Validates: Requirement 12.15
        """
        if state != self._network_state:
            logger.info("Network state changed: %s → %s", self._network_state.value, state.value)
            self._network_state = state
            await self._notify_callbacks()

    async def update_audio_focus(self, state: AudioFocusState) -> None:
        """Update audio focus state and trigger callbacks.

        Args:
            state: New audio focus state.

        Validates: Requirement 12.16
        """
        if state != self._audio_focus:
            logger.info("Audio focus changed: %s → %s", self._audio_focus.value, state.value)
            self._audio_focus = state
            await self._notify_callbacks()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_snapshot(self) -> ResourceSnapshot:
        """Return a snapshot of current resource states."""
        return ResourceSnapshot(
            battery_percent=self._battery_percent,
            is_charging=self._is_charging,
            thermal_state=self._thermal_state,
            network_state=self._network_state,
            audio_focus=self._audio_focus,
        )

    def is_low_battery(self) -> bool:
        """Return True if battery is below the low threshold and not charging."""
        if self._battery_percent is None:
            return False
        return self._battery_percent <= BATTERY_LOW_THRESHOLD and not self._is_charging

    def is_critical_battery(self) -> bool:
        """Return True if battery is below the critical threshold and not charging."""
        if self._battery_percent is None:
            return False
        return self._battery_percent <= BATTERY_CRITICAL_THRESHOLD and not self._is_charging

    def is_thermal_critical(self) -> bool:
        """Return True if device is in a critical thermal state."""
        return self._thermal_state == ThermalState.CRITICAL

    def is_online(self) -> bool:
        """Return True if network is available."""
        return self._network_state != NetworkState.OFFLINE

    def has_audio_focus(self) -> bool:
        """Return True if audio focus is currently held."""
        return self._audio_focus == AudioFocusState.GAINED

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _notify_callbacks(self) -> None:
        """Invoke all registered callbacks with the current snapshot."""
        snapshot = self.get_snapshot()
        for callback in self._callbacks:
            try:
                await callback(snapshot)
            except Exception as exc:  # noqa: BLE001
                logger.error("Resource callback failed: %s", exc)
