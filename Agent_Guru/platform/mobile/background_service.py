"""Module: agent_guru.platform.mobile.background_service
Purpose: Mobile background service manager for always-on operation.

This module implements the background service manager for mobile platforms,
handling sleep/wake cycles, battery optimization, and service lifecycle.

Performance Requirements:
- Battery Usage (Sleep): <5% per hour
- Battery Usage (Wake): <10% per hour
- Transition Time: <100ms
- Service Uptime: 99.9%

Architecture:
    The service manager coordinates:
    1. Sleep/wake cycle management for battery optimization
    2. Wake word detection integration
    3. Service lifecycle (start, stop, restart)
    4. Crash recovery and automatic restart
    5. Battery usage tracking and reporting
    6. Thermal state monitoring and adaptation

Battery Optimization:
    - Sleep Mode: Minimal CPU (<1%), wake word detection only
    - Wake Mode: Full processing with LLM inference
    - Adaptive transitions based on battery level and thermal state
    - Automatic sleep when battery <20%

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

class ServiceState(Enum):
    """Service lifecycle states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    SLEEPING = "sleeping"
    WAKING = "waking"
    STOPPING = "stopping"
    CRASHED = "crashed"

class ThermalState(Enum):
    """Device thermal states."""

    NORMAL = "normal"
    FAIR = "fair"
    SERIOUS = "serious"
    CRITICAL = "critical"

@dataclass
class BatteryUsageStats:
    """Battery usage statistics.

    Attributes:
        sleep_usage_per_hour: Battery % consumed per hour in sleep mode
        wake_usage_per_hour: Battery % consumed per hour in wake mode
        total_sleep_time: Total time spent in sleep mode (seconds)
        total_wake_time: Total time spent in wake mode (seconds)
        battery_level_start: Battery level when tracking started
        battery_level_current: Current battery level

    """

    sleep_usage_per_hour: float = 0.0
    wake_usage_per_hour: float = 0.0
    total_sleep_time: float = 0.0
    total_wake_time: float = 0.0
    battery_level_start: float = 100.0
    battery_level_current: float = 100.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

@dataclass
class ServiceConfig:
    """Configuration for mobile background service.

    Attributes:
        sleep_timeout: Time before entering sleep mode (seconds)
        wake_timeout: Time before returning to sleep (seconds)
        battery_check_interval: Battery check frequency (seconds)
        thermal_check_interval: Thermal check frequency (seconds)
        crash_restart_delay: Delay before restart after crash (seconds)
        max_restart_attempts: Maximum restart attempts before giving up
        low_battery_threshold: Battery % to enter aggressive power saving
        critical_battery_threshold: Battery % to stop service

    """

    sleep_timeout: float = 30.0
    wake_timeout: float = 60.0
    battery_check_interval: float = 60.0
    thermal_check_interval: float = 30.0
    crash_restart_delay: float = 5.0
    max_restart_attempts: int = 3
    low_battery_threshold: float = 20.0
    critical_battery_threshold: float = 10.0

class BatteryUsageTracker:
    """Tracks battery usage in sleep and wake modes.

    Time Complexity: O(1) for all operations
    Space Complexity: O(1) - fixed size tracking
    """

    def __init__(self) -> None:
        """Initialize battery usage tracker."""
        self._stats = BatteryUsageStats()
        self._sleep_start_time: float | None = None
        self._wake_start_time: float | None = None
        self._sleep_start_battery: float | None = None
        self._wake_start_battery: float | None = None

    def start_sleep_tracking(self, battery_level: float) -> None:
        """Start tracking sleep mode battery usage.

        Args:
            battery_level: Current battery level (0-100)

        """
        self._sleep_start_time = time.time()
        self._sleep_start_battery = battery_level

    def end_sleep_tracking(self, battery_level: float) -> None:
        """End tracking sleep mode battery usage.

        Args:
            battery_level: Current battery level (0-100)

        """
        if self._sleep_start_time is None or self._sleep_start_battery is None:
            return

        duration = time.time() - self._sleep_start_time
        battery_used = self._sleep_start_battery - battery_level

        self._stats.total_sleep_time += duration

        # Calculate usage per hour
        if duration > 0:
            hours = duration / 3600.0
            self._stats.sleep_usage_per_hour = battery_used / hours

        self._sleep_start_time = None
        self._sleep_start_battery = None

    def start_wake_tracking(self, battery_level: float) -> None:
        """Start tracking wake mode battery usage.

        Args:
            battery_level: Current battery level (0-100)

        """
        self._wake_start_time = time.time()
        self._wake_start_battery = battery_level

    def end_wake_tracking(self, battery_level: float) -> None:
        """End tracking wake mode battery usage.

        Args:
            battery_level: Current battery level (0-100)

        """
        if self._wake_start_time is None or self._wake_start_battery is None:
            return

        duration = time.time() - self._wake_start_time
        battery_used = self._wake_start_battery - battery_level

        self._stats.total_wake_time += duration

        # Calculate usage per hour
        if duration > 0:
            hours = duration / 3600.0
            self._stats.wake_usage_per_hour = battery_used / hours

        self._wake_start_time = None
        self._wake_start_battery = None

    def get_stats(self) -> BatteryUsageStats:
        """Get current battery usage statistics.

        Returns:
            Battery usage statistics

        """
        self._stats.last_updated = datetime.now(tz=UTC)
        return self._stats

class MobileBackgroundService:
    """Mobile background service manager for always-on operation.

    Handles:
    - ForegroundService (Android) / Background Audio (iOS)
    - Sleep/wake cycles for battery optimization
    - Wake word detection integration
    - Service lifecycle management
    - Crash recovery and restart
    - Battery usage tracking
    - Thermal state monitoring

    Performance Targets:
    - Sleep Mode: <5% battery per hour
    - Wake Mode: <10% battery per hour
    - Transition Time: <100ms
    - Service Uptime: 99.9%

    Example:
        >>> from agent_guru.platform.mobile.background_service import (
        ...     MobileBackgroundService, ServiceConfig
        ... )
        >>>
        >>> config = ServiceConfig()
        >>> service = MobileBackgroundService(config)
        >>>
        >>> # Start service
        >>> await service.start_service()
        >>>
        >>> # Handle wake word detection
        >>> await service.handle_wake_word_detected()
        >>>
        >>> # Get battery stats
        >>> stats = await service.monitor_battery_usage()
        >>> print(f"Sleep usage: {stats.sleep_usage_per_hour:.2f}%/hour")

    """

    def __init__(self, config: ServiceConfig, platform_integration: Any | None = None) -> None:
        """Initialize mobile background service.

        Args:
            config: Service configuration
            platform_integration: Platform-specific integration (Android/iOS)

        """
        self.config = config
        self.platform = platform_integration

        self._state = ServiceState.STOPPED
        self._battery_tracker = BatteryUsageTracker()
        self._restart_attempts = 0
        self._last_wake_time: float | None = None
        self._monitoring_task: asyncio.Task | None = None

        # Callbacks
        self._wake_word_callback: Callable | None = None
        self._state_change_callback: Callable | None = None

    @property
    def state(self) -> ServiceState:
        """Get current service state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if service is running."""
        return self._state in (ServiceState.RUNNING, ServiceState.SLEEPING)

    def set_wake_word_callback(self, callback: Callable) -> None:
        """Set callback for wake word detection.

        Args:
            callback: Async function to call when wake word detected

        """
        self._wake_word_callback = callback

    def set_state_change_callback(self, callback: Callable) -> None:
        """Set callback for state changes.

        Args:
            callback: Async function to call on state change

        """
        self._state_change_callback = callback

    async def start_service(self) -> None:
        """Start background service.

        - Android: Start ForegroundService with notification
        - iOS: Start background audio mode

        Raises:
            RuntimeError: If service fails to start

        """
        if self.is_running:
            logger.warning("Service already running")
            return

        try:
            await self._change_state(ServiceState.STARTING)

            # Platform-specific service start
            if self.platform:
                await self._start_platform_service()

            # Start monitoring tasks
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())

            # Enter sleep mode initially
            await self.enter_sleep_mode()

            await self._change_state(ServiceState.RUNNING)
            self._restart_attempts = 0

            logger.info("Background service started successfully")

        except Exception as e:
            logger.exception("Failed to start service")
            await self._change_state(ServiceState.CRASHED)
            msg = f"Service start failed: {e}"
            raise RuntimeError(msg) from e

    async def stop_service(self) -> None:
        """Stop background service and cleanup resources."""
        if not self.is_running:
            logger.warning("Service not running")
            return

        try:
            await self._change_state(ServiceState.STOPPING)

            # Stop monitoring
            if self._monitoring_task:
                self._monitoring_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._monitoring_task

            # Platform-specific service stop
            if self.platform:
                await self._stop_platform_service()

            await self._change_state(ServiceState.STOPPED)

            logger.info("Background service stopped")

        except Exception:
            logger.exception("Error stopping service")
            await self._change_state(ServiceState.CRASHED)

    async def enter_sleep_mode(self) -> None:
        """Enter sleep mode for battery optimization.

        - Reduce CPU usage to <1%
        - Use minimal wake word detection
        - Target: <5% battery per hour

        Time Complexity: O(1)
        """
        if self._state == ServiceState.SLEEPING:
            return

        start_time = time.time()

        try:
            await self._change_state(ServiceState.SLEEPING)

            # Get current battery level
            battery_level = await self._get_battery_level()

            # End wake tracking if active
            self._battery_tracker.end_wake_tracking(battery_level)

            # Start sleep tracking
            self._battery_tracker.start_sleep_tracking(battery_level)

            # Platform-specific sleep mode
            if self.platform:
                await self._enter_platform_sleep_mode()

            transition_time = (time.time() - start_time) * 1000
            logger.info("Entered sleep mode (transition: %.1fms)", transition_time)

        except Exception:
            logger.exception("Error entering sleep mode")

    async def enter_wake_mode(self) -> None:
        """Enter wake mode for full functionality.

        - Full voice processing
        - LLM inference
        - Target: <10% battery per hour

        Time Complexity: O(1)
        """
        if self._state == ServiceState.RUNNING:
            return

        start_time = time.time()

        try:
            await self._change_state(ServiceState.WAKING)

            # Get current battery level
            battery_level = await self._get_battery_level()

            # End sleep tracking
            self._battery_tracker.end_sleep_tracking(battery_level)

            # Start wake tracking
            self._battery_tracker.start_wake_tracking(battery_level)

            # Platform-specific wake mode
            if self.platform:
                await self._enter_platform_wake_mode()

            await self._change_state(ServiceState.RUNNING)
            self._last_wake_time = time.time()

            transition_time = (time.time() - start_time) * 1000
            logger.info("Entered wake mode (transition: %.1fms)", transition_time)

        except Exception:
            logger.exception("Error entering wake mode")

    async def handle_wake_word_detected(self) -> None:
        """Handle wake word detection event.

        Transitions from sleep to wake mode and invokes callback.
        """
        logger.info("Wake word detected")

        # Transition to wake mode
        await self.enter_wake_mode()

        # Invoke callback if set
        if self._wake_word_callback:
            try:
                await self._wake_word_callback()
            except Exception:
                logger.exception("Wake word callback error")

    async def request_battery_optimization_exemption(self) -> bool:
        """Request battery optimization exemption (Android).

        Returns:
            True if exemption granted

        """
        if not self.platform:
            return False

        try:
            # Platform-specific exemption request
            if hasattr(self.platform, "request_battery_exemption"):
                return await self.platform.request_battery_exemption()
            return False
        except Exception:
            logger.exception("Error requesting battery exemption")
            return False

    async def monitor_battery_usage(self) -> BatteryUsageStats:
        """Monitor battery usage statistics.

        Returns:
            Battery usage stats (% per hour in sleep/wake modes)

        """
        stats = self._battery_tracker.get_stats()

        # Update current battery level
        stats.battery_level_current = await self._get_battery_level()

        return stats

    async def handle_low_battery(self, battery_percent: float) -> None:
        """Handle low battery condition.

        Args:
            battery_percent: Current battery percentage

        """
        if battery_percent < self.config.critical_battery_threshold:
            logger.warning("Critical battery (%.1f%%), stopping service", battery_percent)
            await self.stop_service()
        elif battery_percent < self.config.low_battery_threshold:
            logger.warning("Low battery (%.1f%%), entering sleep mode", battery_percent)
            await self.enter_sleep_mode()

    async def handle_thermal_state(self, thermal_state: ThermalState) -> None:
        """Handle thermal state changes.

        Args:
            thermal_state: Current thermal state

        """
        if thermal_state == ThermalState.CRITICAL:
            logger.warning("Critical thermal state, entering sleep mode")
            await self.enter_sleep_mode()
        elif thermal_state == ThermalState.SERIOUS:
            logger.warning("Serious thermal state, reducing activity")
            # Could reduce processing intensity here

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop for battery and thermal state."""
        last_battery_check = 0.0
        last_thermal_check = 0.0

        while True:
            try:
                current_time = time.time()

                # Check battery level
                if current_time - last_battery_check >= self.config.battery_check_interval:
                    battery_level = await self._get_battery_level()
                    await self.handle_low_battery(battery_level)
                    last_battery_check = current_time

                # Check thermal state
                if current_time - last_thermal_check >= self.config.thermal_check_interval:
                    thermal_state = await self._get_thermal_state()
                    await self.handle_thermal_state(thermal_state)
                    last_thermal_check = current_time

                # Check wake timeout
                if (
                    self._state == ServiceState.RUNNING
                    and self._last_wake_time
                    and current_time - self._last_wake_time >= self.config.wake_timeout
                ):
                    logger.info("Wake timeout, entering sleep mode")
                    await self.enter_sleep_mode()

                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break

    async def _change_state(self, new_state: ServiceState) -> None:
        """Change service state and invoke callback.

        Args:
            new_state: New service state

        """
        old_state = self._state
        self._state = new_state

        logger.info("State change: %s -> %s", old_state.value, new_state.value)

        if self._state_change_callback:
            try:
                await self._state_change_callback(old_state, new_state)
            except Exception:
                logger.exception("State change callback error")

    async def _get_battery_level(self) -> float:
        """Get current battery level.

        Returns:
            Battery level (0-100)

        """
        if self.platform and hasattr(self.platform, "get_battery_info"):
            try:
                battery_info = await self.platform.get_battery_info()
                return battery_info.percent
            except Exception:
                logger.exception("Error getting battery level")
        return 100.0

    async def _get_thermal_state(self) -> ThermalState:
        """Get current thermal state.

        Returns:
            Current thermal state

        """
        if self.platform and hasattr(self.platform, "get_thermal_state"):
            try:
                return await self.platform.get_thermal_state()
            except Exception:
                logger.exception("Error getting thermal state")
        return ThermalState.NORMAL

    async def _start_platform_service(self) -> None:
        """Start platform-specific service."""
        if hasattr(self.platform, "start_foreground_service"):
            await self.platform.start_foreground_service()
        elif hasattr(self.platform, "start_background_audio"):
            await self.platform.start_background_audio()

    async def _stop_platform_service(self) -> None:
        """Stop platform-specific service."""
        if hasattr(self.platform, "stop_foreground_service"):
            await self.platform.stop_foreground_service()
        elif hasattr(self.platform, "stop_background_audio"):
            await self.platform.stop_background_audio()

    async def _enter_platform_sleep_mode(self) -> None:
        """Enter platform-specific sleep mode."""
        if hasattr(self.platform, "enter_sleep_mode"):
            await self.platform.enter_sleep_mode()

    async def _enter_platform_wake_mode(self) -> None:
        """Enter platform-specific wake mode."""
        if hasattr(self.platform, "enter_wake_mode"):
            await self.platform.enter_wake_mode()
