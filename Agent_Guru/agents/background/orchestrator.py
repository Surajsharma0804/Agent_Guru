"""Background Service Orchestrator - Coordinates all AGENT_GURU background services.

Manages service lifecycle, health monitoring, automatic restart with exponential
backoff, and watchdog timers for always-on operation across all platforms.

Performance Characteristics:
    - Time Complexity: O(s) where s is number of services
    - Space Complexity: O(s) for service health tracking
    - Heartbeat check: <1ms per service

Validates: Requirement 12 (Background Service Orchestration)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Default services managed by the orchestrator
DEFAULT_SERVICES = (
    "speech_engine",
    "llm_runtime",
    "platform_integration",
    "memory_system",
    "policy_engine",
)

# Heartbeat timeout before marking a service unresponsive
HEARTBEAT_TIMEOUT_SECONDS = 30

# Maximum exponential backoff delay in seconds
MAX_BACKOFF_SECONDS = 60


class ServiceState(Enum):
    """Operational state of a background service."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    SLEEPING = "sleeping"
    WAKING = "waking"
    STOPPING = "stopping"
    FAILED = "failed"


class SystemMode(Enum):
    """System-wide power mode."""

    SLEEP = "sleep"  # <5% battery per hour - wake word detection only
    WAKE = "wake"  # <10% battery per hour - full processing


@dataclass
class ServiceHealth:
    """Health status for a single background service.

    Attributes:
        service_name: Unique service identifier.
        state: Current operational state.
        last_heartbeat: Timestamp of last heartbeat received.
        error_count: Cumulative errors since last reset.
        restart_count: Number of times the service has been restarted.
        uptime_seconds: Seconds since the service last started.

    """

    service_name: str
    state: ServiceState
    last_heartbeat: datetime
    error_count: int = 0
    restart_count: int = 0
    uptime_seconds: float = 0.0


# Type alias for service command handlers
ServiceCommandHandler = Callable[[str, str], Coroutine[Any, Any, None]]


class BackgroundServiceOrchestrator:
    """Coordinates background services across all AGENT_GURU components.

    Responsibilities:
    - Start/stop all background services
    - Monitor service health via heartbeat checks
    - Restart failed services with exponential backoff
    - Watchdog timers for unresponsive services
    - Coordinate sleep/wake mode transitions

    Time Complexity: O(s) per health check cycle
    Space Complexity: O(s) for service registry

    Example:
        >>> orchestrator = BackgroundServiceOrchestrator()
        >>> await orchestrator.start_all_services()
        >>> health = await orchestrator.monitor_service_health()
        >>> await orchestrator.stop_all_services()

    Validates: Requirement 12

    """

    def __init__(
        self,
        services: list[str] | None = None,
        heartbeat_timeout_seconds: int = HEARTBEAT_TIMEOUT_SECONDS,
        max_backoff_seconds: int = MAX_BACKOFF_SECONDS,
    ) -> None:
        """Initialise the background service orchestrator.

        Args:
            services: List of service names to manage. Defaults to DEFAULT_SERVICES.
            heartbeat_timeout_seconds: Seconds before a service is considered unresponsive.
            max_backoff_seconds: Maximum restart backoff delay in seconds.

        Raises:
            ValueError: If heartbeat_timeout_seconds < 1 or max_backoff_seconds < 1.

        """
        if heartbeat_timeout_seconds < 1:
            msg = "heartbeat_timeout_seconds must be >= 1"
            raise ValueError(msg)
        if max_backoff_seconds < 1:
            msg = "max_backoff_seconds must be >= 1"
            raise ValueError(msg)

        self._service_names = list(services or DEFAULT_SERVICES)
        self._heartbeat_timeout = heartbeat_timeout_seconds
        self._max_backoff = max_backoff_seconds

        self.services: dict[str, ServiceHealth] = {}
        self.system_mode: SystemMode = SystemMode.SLEEP

        # Optional external command handler (service_name, command) -> None
        self._command_handler: ServiceCommandHandler | None = None

        # Watchdog task handle
        self._watchdog_task: asyncio.Task | None = None  # type: ignore[type-arg]

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_command_handler(self, handler: ServiceCommandHandler) -> None:
        """Register an external handler for service commands.

        Args:
            handler: Async callable(service_name, command) invoked when
                     the orchestrator needs to send a command to a service.

        """
        self._command_handler = handler

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start_all_services(self) -> None:
        """Start all managed background services and enter sleep mode.

        Validates: Requirement 12.1, 12.7
        """
        for name in self._service_names:
            await self._start_service(name)

        await self.enter_sleep_mode()
        logger.info("All services started; system in SLEEP mode")

    async def stop_all_services(self) -> None:
        """Stop all managed background services gracefully.

        Validates: Requirement 12.5
        """
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watchdog_task

        for name in list(self.services.keys()):
            await self._stop_service(name)

        logger.info("All services stopped")

    async def _start_service(self, service_name: str) -> None:
        """Start a single service and register its health entry."""
        health = ServiceHealth(
            service_name=service_name,
            state=ServiceState.STARTING,
            last_heartbeat=datetime.now(tz=UTC),
        )
        self.services[service_name] = health

        if self._command_handler:
            try:
                await self._command_handler(service_name, "start")
            except Exception as exc:
                health.state = ServiceState.FAILED
                health.error_count += 1
                logger.exception("Failed to start service '%s': %s", service_name, exc)
                return

        health.state = ServiceState.RUNNING
        logger.debug("Service '%s' started", service_name)

    async def _stop_service(self, service_name: str) -> None:
        """Stop a single service."""
        health = self.services.get(service_name)
        if not health:
            return

        health.state = ServiceState.STOPPING

        if self._command_handler:
            try:
                await self._command_handler(service_name, "stop")
            except Exception as exc:
                logger.exception("Error stopping service '%s': %s", service_name, exc)

        health.state = ServiceState.STOPPED
        logger.debug("Service '%s' stopped", service_name)

    # ------------------------------------------------------------------
    # Sleep / Wake
    # ------------------------------------------------------------------

    async def enter_sleep_mode(self) -> None:
        """Transition all services to sleep mode for battery optimisation.

        Sleep mode: minimal CPU, wake word detection only, <5% battery/hour.

        Validates: Requirement 12.2, 12.3
        """
        self.system_mode = SystemMode.SLEEP
        await self._send_to_all_services("enter_sleep_mode")

        for health in self.services.values():
            if health.state == ServiceState.RUNNING:
                health.state = ServiceState.SLEEPING

        logger.info("System entered SLEEP mode")

    async def enter_wake_mode(self) -> None:
        """Transition all services to wake mode for full functionality.

        Wake mode: full voice processing, LLM inference, <10% battery/hour.

        Validates: Requirement 12.2, 12.3
        """
        self.system_mode = SystemMode.WAKE
        await self._send_to_all_services("enter_wake_mode")

        for health in self.services.values():
            if health.state == ServiceState.SLEEPING:
                health.state = ServiceState.RUNNING

        logger.info("System entered WAKE mode")

    async def handle_wake_word_detected(self) -> None:
        """Wake the system when a wake word is detected.

        Validates: Requirement 12.1
        """
        if self.system_mode == SystemMode.SLEEP:
            await self.enter_wake_mode()

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------

    async def monitor_service_health(self) -> list[ServiceHealth]:
        """Check health of all services and restart unresponsive ones.

        Returns:
            List of current ServiceHealth snapshots.

        Validates: Requirement 12.7, 12.13

        """
        now = datetime.now(tz=UTC)
        for service_name, health in list(self.services.items()):
            if health.state in (ServiceState.RUNNING, ServiceState.SLEEPING):
                elapsed = (now - health.last_heartbeat).total_seconds()
                if elapsed > self._heartbeat_timeout:
                    logger.warning(
                        "Service '%s' missed heartbeat (%.1fs ago), restarting",
                        service_name,
                        elapsed,
                    )
                    await self._restart_service(service_name)

        return list(self.services.values())

    def record_heartbeat(self, service_name: str) -> None:
        """Record a heartbeat for a service.

        Args:
            service_name: Name of the service sending the heartbeat.

        """
        health = self.services.get(service_name)
        if health:
            health.last_heartbeat = datetime.now(tz=UTC)

    async def _restart_service(self, service_name: str) -> None:
        """Restart a failed/unresponsive service with exponential backoff.

        Validates: Requirement 12.6, 12.13
        """
        health = self.services.get(service_name)
        if not health:
            return

        health.restart_count += 1
        preserved_restart_count = health.restart_count
        health.state = ServiceState.FAILED

        # Exponential backoff: 2^restart_count seconds, capped at max_backoff
        delay = min(2**preserved_restart_count, self._max_backoff)
        logger.info(
            "Restarting service '%s' (attempt %d) after %.1fs backoff",
            service_name,
            preserved_restart_count,
            delay,
        )
        await asyncio.sleep(delay)

        await self._stop_service(service_name)
        await self._start_service(service_name)

        # Restore restart_count - _start_service creates a fresh ServiceHealth
        if service_name in self.services:
            self.services[service_name].restart_count = preserved_restart_count

    # ------------------------------------------------------------------
    # Watchdog
    # ------------------------------------------------------------------

    async def start_watchdog(self, interval_seconds: float = 10.0) -> None:
        """Start a background watchdog that periodically checks service health.

        Args:
            interval_seconds: How often to run health checks.

        Validates: Requirement 12.13

        """
        # BUG FIX: was unconditional -- calling start_watchdog() a
        # second time while a previous watchdog task was still
        # running overwrote self._watchdog_task, permanently leaking
        # the earlier infinite-loop task (unreachable, uncancellable,
        # and still calling monitor_service_health() forever -- even
        # across an intentional stop_all_services() shutdown, since
        # that can only cancel the most recently stored reference).
        # Cancelling any existing watchdog first closes that leak.
        if self._watchdog_task is not None and not self._watchdog_task.done():
            logger.warning(
                "start_watchdog() called while a watchdog was already "
                "running; cancelling the previous one first",
            )
            self._watchdog_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watchdog_task

        async def _watchdog_loop() -> None:
            while True:
                await asyncio.sleep(interval_seconds)
                # BUG FIX: was an unprotected `await
                # self.monitor_service_health()` -- any exception it
                # raised would kill this task silently and permanently
                # (nothing awaits it under normal operation), defeating
                # the watchdog's entire purpose: "automatic restart ...
                # for always-on operation." Isolating one failed
                # iteration lets the watchdog keep running on the next
                # interval, which is exactly the resilience a watchdog
                # exists to provide.
                try:
                    await self.monitor_service_health()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "Watchdog health check failed; will retry next interval",
                    )

        self._watchdog_task = asyncio.create_task(_watchdog_loop())
        logger.info("Watchdog started (interval=%.1fs)", interval_seconds)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _send_to_all_services(self, command: str) -> None:
        """Send a command to all running/sleeping services."""
        if not self._command_handler:
            return

        for service_name, health in self.services.items():
            if health.state in (ServiceState.RUNNING, ServiceState.SLEEPING):
                try:
                    await self._command_handler(service_name, command)
                except Exception as exc:
                    logger.exception(
                        "Command '%s' failed for service '%s': %s",
                        command,
                        service_name,
                        exc,
                    )
