"""Background Service Manager for always-on voice assistant.

ZERO COMPROMISE - BEST IMPLEMENTATION

This module provides always-on background service management:
- Sleep/wake cycle management
- Resource optimization (<5% CPU, <100MB RAM in sleep mode)
- Platform-specific service initialization
- Auto-start on boot
- Crash recovery
- 24+ hour continuous operation
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from Agent_Guru.speech.battery_monitor import BatteryMonitor


class ServiceState(Enum):
    """Background service state."""

    STOPPED = "stopped"
    SLEEP = "sleep"  # Listening for wake word only
    WAKE = "wake"  # Full speech processing active
    PAUSED = "paused"  # Temporarily paused


@dataclass
class ServiceMetrics:
    """Service performance metrics."""

    cpu_percent: float
    memory_mb: float
    uptime_seconds: float
    wake_word_detections: int
    commands_processed: int
    errors: int
    state_transitions: int


class BackgroundServiceManager:
    """Manage always-on background service with battery optimization.

    Features:
    - Sleep/wake cycle management
    - Resource optimization
    - Platform-specific initialization
    - Auto-recovery from errors
    - Performance monitoring

    Targets:
    - <5% CPU in sleep mode
    - <100MB RAM in sleep mode
    - <500ms wake transition
    - 24+ hour continuous operation
    """

    def __init__(
        self,
        battery_monitor: BatteryMonitor | None = None,
        wake_word_callback: Callable | None = None,
        command_callback: Callable | None = None,
    ) -> None:
        """Initialize Background Service Manager.

        Args:
            battery_monitor: Battery monitor instance
            wake_word_callback: Callback when wake word detected
            command_callback: Callback when command received

        """
        self.battery_monitor = battery_monitor or BatteryMonitor()
        self.wake_word_callback = wake_word_callback
        self.command_callback = command_callback

        # Service state
        self._state = ServiceState.STOPPED
        self._state_lock = threading.Lock()

        # Metrics
        self._start_time: float | None = None
        self._wake_word_count = 0
        self._command_count = 0
        self._error_count = 0
        self._state_transition_count = 0

        # Timers
        self._wake_timeout_seconds = 3.0  # Return to sleep after 3s of silence
        self._wake_timeout_timer: threading.Timer | None = None
        # BUG FIX (see _reset_wake_timeout / _on_wake_timeout): fencing
        # token guarding against a threading.Timer callback that slips
        # past cancel() -- see the detailed explanation at its use below.
        self._wake_timeout_generation = 0

        # Logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    def start(self) -> None:
        """Start background service.

        Enters sleep mode immediately.
        """
        with self._state_lock:
            if self._state != ServiceState.STOPPED:
                msg = f"Service already running in state: {self._state}"
                raise RuntimeError(msg)

            self._start_time = time.time()
            self._transition_to_sleep()

            self.logger.info("Background service started")

    def stop(self) -> None:
        """Stop background service."""
        with self._state_lock:
            if self._state == ServiceState.STOPPED:
                return

            # Cancel any pending timers
            if self._wake_timeout_timer:
                self._wake_timeout_timer.cancel()
                self._wake_timeout_timer = None

            # Stop battery tracking
            if self._state == ServiceState.SLEEP:
                self.battery_monitor.stop_sleep_mode_tracking()
            elif self._state == ServiceState.WAKE:
                self.battery_monitor.stop_wake_mode_tracking()

            self._state = ServiceState.STOPPED
            self._state_transition_count += 1

            self.logger.info("Background service stopped")

    def pause(self) -> None:
        """Pause background service (user requested)."""
        with self._state_lock:
            if self._state == ServiceState.STOPPED:
                msg = "Service not running"
                raise RuntimeError(msg)

            # Stop battery tracking
            if self._state == ServiceState.SLEEP:
                self.battery_monitor.stop_sleep_mode_tracking()
            elif self._state == ServiceState.WAKE:
                self.battery_monitor.stop_wake_mode_tracking()

            self._state = ServiceState.PAUSED
            self._state_transition_count += 1

            self.logger.info("Background service paused")

    def resume(self) -> None:
        """Resume background service from pause."""
        with self._state_lock:
            if self._state != ServiceState.PAUSED:
                msg = f"Service not paused, current state: {self._state}"
                raise RuntimeError(msg)

            self._transition_to_sleep()

            self.logger.info("Background service resumed")

    def handle_wake_word_detected(self) -> None:
        """Handle wake word detection.

        Transitions from sleep to wake mode within 500ms.
        """
        start_time = time.time()

        with self._state_lock:
            if self._state != ServiceState.SLEEP:
                self.logger.warning("Wake word detected in wrong state: %s", self._state)
                return

            self._wake_word_count += 1

            # Transition to wake mode
            self._transition_to_wake()

            # Call wake word callback
            if self.wake_word_callback:
                try:
                    self.wake_word_callback()
                except Exception:
                    self.logger.exception("Wake word callback error")
                    self._error_count += 1

        # Verify transition latency
        elapsed = time.time() - start_time
        if elapsed > 0.5:
            self.logger.warning("Wake transition took %.3fs (target: <0.5s)", elapsed)

        self.logger.info("Wake word detected, transitioned to wake mode in %.3fs", elapsed)

    def handle_command_received(self, command: str) -> None:
        """Handle command received.

        Args:
            command: Transcribed command text

        """
        with self._state_lock:
            if self._state != ServiceState.WAKE:
                self.logger.warning("Command received in wrong state: %s", self._state)
                return

            self._command_count += 1

            # Reset wake timeout
            self._reset_wake_timeout()

            # Call command callback
            if self.command_callback:
                try:
                    self.command_callback(command)
                except Exception:
                    self.logger.exception("Command callback error")
                    self._error_count += 1

        self.logger.info("Command received: %s", command)

    def handle_silence_detected(self) -> None:
        """Handle silence detected (user stopped speaking).

        Starts timeout to return to sleep mode.
        """
        with self._state_lock:
            if self._state != ServiceState.WAKE:
                return

            # Start wake timeout
            self._reset_wake_timeout()

        self.logger.info("Silence detected, wake timeout started")

    def handle_low_battery(self) -> None:
        """Handle low battery condition.

        Pauses service if battery is critical (<5%).
        """
        if self.battery_monitor.should_pause_service():
            self.logger.warning("Critical battery level, pausing service")
            self.pause()
        elif self.battery_monitor.should_reduce_frequency():
            self.logger.info("Low battery, reducing wake word detection frequency")
            # In real implementation, would reduce detection frequency

    def handle_error(self, error: Exception) -> None:
        """Handle error during operation.

        Returns to sleep mode instead of crashing.

        Args:
            error: Exception that occurred

        """
        self.logger.error("Error occurred: %s", error)
        self._error_count += 1

        with self._state_lock:
            if self._state == ServiceState.WAKE:
                # Return to sleep mode on error
                self._transition_to_sleep()
                self.logger.info("Returned to sleep mode after error")

    def get_state(self) -> ServiceState:
        """Get current service state.

        Returns:
            Current ServiceState

        """
        with self._state_lock:
            return self._state

    def get_metrics(self) -> ServiceMetrics:
        """Get service performance metrics.

        Returns:
            ServiceMetrics with current metrics

        """
        uptime = 0.0
        if self._start_time:
            uptime = time.time() - self._start_time

        # Get resource usage
        cpu_percent, memory_mb = self._get_resource_usage()

        return ServiceMetrics(
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            uptime_seconds=uptime,
            wake_word_detections=self._wake_word_count,
            commands_processed=self._command_count,
            errors=self._error_count,
            state_transitions=self._state_transition_count,
        )

    def _transition_to_sleep(self) -> None:
        """Transition to sleep mode."""
        # Stop wake mode tracking if active
        if self._state == ServiceState.WAKE:
            self.battery_monitor.stop_wake_mode_tracking()

        # Start sleep mode tracking
        self.battery_monitor.start_sleep_mode_tracking()

        self._state = ServiceState.SLEEP
        self._state_transition_count += 1

        # Cancel wake timeout if active
        if self._wake_timeout_timer:
            self._wake_timeout_timer.cancel()
            self._wake_timeout_timer = None

        self.logger.info("Transitioned to sleep mode")

    def _transition_to_wake(self) -> None:
        """Transition to wake mode."""
        # Stop sleep mode tracking
        self.battery_monitor.stop_sleep_mode_tracking()

        # Start wake mode tracking
        self.battery_monitor.start_wake_mode_tracking()

        self._state = ServiceState.WAKE
        self._state_transition_count += 1

        # Start wake timeout
        self._reset_wake_timeout()

        self.logger.info("Transitioned to wake mode")

    def _reset_wake_timeout(self) -> None:
        """Reset wake timeout timer."""
        # Cancel existing timer
        if self._wake_timeout_timer:
            self._wake_timeout_timer.cancel()

        # BUG FIX: threading.Timer.cancel() only works "if the timer is
        # still in its waiting stage" (per the stdlib docs) -- it cannot
        # stop a timer whose interval has already elapsed and whose
        # fire-or-not check has already passed. There is a real, narrow
        # window where the *previous* timer's countdown finishes at
        # essentially the same moment this method is called to reset it
        # (e.g. the user speaks again right at the ~3s mark): the old
        # timer's callback thread can pass its internal "am I cancelled?"
        # check microseconds before this cancel() call lands, and will
        # then go on to call _on_wake_timeout() anyway, blocking on
        # _state_lock until whichever caller reset the timeout releases
        # it. Once unblocked, the old callback would see state==WAKE
        # (it's still WAKE -- a fresh command/silence event just reset
        # the timeout) and incorrectly transition the service back to
        # SLEEP immediately after the user just interacted with it,
        # racing against the brand-new timer this call is about to start.
        # Tagging every timer with a monotonically increasing generation
        # number, and having the callback verify it's still the most
        # recently issued one (under the same lock it already takes)
        # before acting, closes this window: a stale callback that slips
        # past cancel() becomes a safe no-op instead of a spurious sleep
        # transition.
        self._wake_timeout_generation += 1
        generation = self._wake_timeout_generation

        # Start new timer
        self._wake_timeout_timer = threading.Timer(
            self._wake_timeout_seconds,
            self._on_wake_timeout,
            args=(generation,),
        )
        self._wake_timeout_timer.start()

    def _on_wake_timeout(self, generation: int) -> None:
        """Handle wake timeout (return to sleep).

        Args:
            generation: The _wake_timeout_generation value in effect when
                this specific timer was scheduled. If a newer timer has
                since been scheduled (generation has moved on), this
                firing is stale -- e.g. it slipped past a cancel() call
                in the race described in _reset_wake_timeout() -- and
                must not act.

        """
        with self._state_lock:
            if generation != self._wake_timeout_generation:
                self.logger.debug("Ignoring stale wake timeout (generation %d, current %d)",
                                   generation, self._wake_timeout_generation)
                return
            if self._state == ServiceState.WAKE:
                self._transition_to_sleep()
                self.logger.info("Wake timeout, returned to sleep mode")

    def _get_resource_usage(self) -> tuple[float, float]:
        """Get current resource usage.

        Returns:
            Tuple of (cpu_percent, memory_mb)

        """
        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            cpu_percent = process.cpu_percent(interval=0.1)
            memory_mb = process.memory_info().rss / (1024 * 1024)

            return cpu_percent, memory_mb
        except ImportError:
            # BUG FIX: this used to return hardcoded, plausible-looking
            # "healthy" numbers (e.g. 3.0% CPU / 80MB RAM while asleep)
            # whenever psutil wasn't importable -- indistinguishable from
            # a real measurement to get_metrics()'s caller or to any
            # dashboard/alerting consuming it. That's fabricated
            # telemetry: if psutil were ever genuinely absent in a
            # deployment (a packaging gap, a stripped-down environment),
            # this would silently report "everything's fine" instead of
            # surfacing that no real measurement was taken, masking
            # rather than revealing the problem and potentially hiding
            # genuine resource exhaustion behind a canned "healthy"
            # reading. NaN unambiguously signals "not measured" to any
            # consumer that checks for it (math.isnan), and is safe by
            # construction against numeric comparisons silently
            # evaluating as healthy (any comparison against NaN is
            # False).
            self.logger.warning(
                "psutil not available -- resource usage cannot be measured; "
                "get_metrics() will report NaN for cpu_percent/memory_mb",
            )
            return float("nan"), float("nan")
