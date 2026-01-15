"""
Automatic Workstation Locking System

This module implements the automatic workstation locking functionality for GURU's
intrusion detection system. It provides immediate workstation locking capabilities
using native Windows APIs when security threats are detected.

Security Features:
- Native Windows API integration (LockWorkStation)
- Immediate lock trigger without user confirmation
- High-severity audit logging
- Thread-safe operation
- Comprehensive error handling and fallback mechanisms
- Integration with intrusion detection system

Requirements Addressed:
- 26.5: Use native OS mechanisms only
- 26.6: Log all intrusion events with high severity
- 26.7: Lock action without user confirmation or delay
"""

import ctypes
import ctypes.wintypes
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class WorkstationLockResult(Enum):
    """Results of workstation lock attempts."""

    SUCCESS = "success"
    FAILED_API_CALL = "failed_api_call"
    FAILED_PERMISSION = "failed_permission"
    FAILED_SYSTEM_ERROR = "failed_system_error"
    FAILED_NOT_SUPPORTED = "failed_not_supported"


class WorkstationLockTrigger(Enum):
    """Triggers that can cause workstation locking."""

    BIOMETRIC_FAILURE = "biometric_failure"
    VOICE_SPOOFING = "voice_spoofing"
    INTRUSION_DETECTED = "intrusion_detected"
    MULTIPLE_FAILURES = "multiple_failures"
    MANUAL_TRIGGER = "manual_trigger"
    SECURITY_VIOLATION = "security_violation"


@dataclass(frozen=True)
class WorkstationLockEvent:
    """Immutable record of a workstation lock event."""

    event_id: str
    timestamp: datetime
    trigger: WorkstationLockTrigger
    result: WorkstationLockResult
    trigger_context: Dict[str, str]
    error_details: Optional[str] = None
    session_id: Optional[str] = None

    def __post_init__(self):
        """Set event ID if not provided."""
        if not self.event_id:
            object.__setattr__(self, "event_id", str(uuid.uuid4()))


@dataclass
class WorkstationLockConfig:
    """Configuration for workstation locking system."""

    # Lock behavior
    enable_immediate_lock: bool = True
    enable_lock_logging: bool = True
    enable_fallback_mechanisms: bool = True

    # Retry configuration
    max_lock_attempts: int = 3
    retry_delay_seconds: float = 0.5

    # Logging configuration
    log_successful_locks: bool = True
    log_failed_locks: bool = True
    log_trigger_context: bool = True

    # Security settings
    require_elevated_privileges: bool = False  # LockWorkStation doesn't require elevation
    validate_lock_success: bool = True

    # Integration settings
    notify_callbacks_on_lock: bool = True

    # Event retention
    retain_lock_events_hours: int = 24
    max_lock_events_stored: int = 1000


class WorkstationLockError(Exception):
    """Base exception for workstation locking errors."""


class WorkstationLockPermissionError(WorkstationLockError):
    """Exception for permission-related lock failures."""


class WorkstationLockSystemError(WorkstationLockError):
    """Exception for system-level lock failures."""


class WorkstationLocker:
    """
    Automatic workstation locking system for GURU.

    This class provides immediate workstation locking capabilities using native
    Windows APIs. It integrates with the intrusion detection system to provide
    automatic security responses when threats are detected.

    Key Features:
    - Native Windows API integration (LockWorkStation)
    - Immediate lock trigger without user confirmation
    - Comprehensive audit logging with high severity
    - Thread-safe operation with retry mechanisms
    - Integration with intrusion detection callbacks
    - Fallback mechanisms for error conditions

    Security Design:
    - Uses only native OS mechanisms (no custom lock screen)
    - No biometric data storage or processing
    - No bypass of OS authentication
    - Immediate action without user confirmation
    - High-severity logging for all lock events
    """

    def __init__(self, config: Optional[WorkstationLockConfig] = None):
        """
        Initialize the workstation locking system.

        Args:
            config: Configuration for workstation locking behavior
        """
        self.config = config or WorkstationLockConfig()

        # Thread safety
        self._lock = threading.RLock()

        # Event tracking
        self._lock_events: List[WorkstationLockEvent] = []
        self._last_lock_attempt: Optional[datetime] = None
        self._consecutive_failures: int = 0

        # Callback management
        self._lock_callbacks: List[Callable[[WorkstationLockEvent], None]] = []

        # Windows API setup
        self._enforce_windows_api_security_boundary()

        # Validate system capabilities
        self._validate_system_capabilities()

        logger.info(
            "Workstation locking system initialized",
            config=self.config.__dict__,
            api_available=self._api_available,
            system_supported=self._system_supported,
        )

    def _enforce_windows_api_security_boundary(self) -> None:
        """Setup Windows API access for workstation locking."""
        try:
            # Load user32.dll for LockWorkStation function
            self._user32 = ctypes.windll.user32

            # Define function signature for LockWorkStation
            # BOOL LockWorkStation(void);
            self._user32.LockWorkStation.argtypes = []
            self._user32.LockWorkStation.restype = ctypes.wintypes.BOOL

            # Test API availability
            self._api_available = hasattr(self._user32, "LockWorkStation")

            if self._api_available:
                logger.info("Windows LockWorkStation API loaded successfully")
            else:
                logger.error("Windows LockWorkStation API not available")

        except Exception as e:
            self._api_available = False
            logger.error("Failed to setup Windows API for workstation locking", error=str(e))

    def _validate_system_capabilities(self) -> None:
        """Validate system capabilities for workstation locking."""
        self._system_supported = True

        try:
            # Check if we're running on Windows
            import platform

            if platform.system() != "Windows":
                self._system_supported = False
                logger.warning("Workstation locking not supported on non-Windows systems")
                return

            # Check Windows version (LockWorkStation available since Windows 2000)
            version_info = platform.version()
            logger.info("Windows version detected", version=version_info)

            # Additional capability checks could go here

        except Exception as e:
            self._system_supported = False
            logger.error("Failed to validate system capabilities", error=str(e))

    def register_lock_callback(self, callback: Callable[[WorkstationLockEvent], None]) -> None:
        """
        Register a callback function to be called when workstation lock events occur.

        Args:
            callback: Function to call with WorkstationLockEvent parameter
        """
        with self._lock:
            self._lock_callbacks.append(callback)
            logger.info("Lock callback registered", callback_count=len(self._lock_callbacks))

    def lock_workstation_immediately(
        self,
        trigger: WorkstationLockTrigger,
        trigger_context: Optional[Dict[str, str]] = None,
        session_id: Optional[str] = None,
    ) -> WorkstationLockEvent:
        """
        Lock the workstation immediately using native Windows APIs.

        This method implements the core workstation locking functionality required
        by GURU's security model. It uses the Windows LockWorkStation API to
        immediately lock the workstation without user confirmation.

        Args:
            trigger: The security event that triggered the lock
            trigger_context: Additional context about the trigger
            session_id: Optional session identifier

        Returns:
            WorkstationLockEvent with details of the lock attempt

        Raises:
            WorkstationLockError: If locking fails and no fallback is available
        """
        with self._lock:
            current_time = datetime.utcnow()
            trigger_context = trigger_context or {}

            logger.critical(
                "WORKSTATION LOCK TRIGGERED",
                trigger=trigger.value,
                trigger_context=trigger_context,
                session_id=session_id,
                immediate_action=True,
            )

            # Attempt to lock the workstation
            lock_result = self._attempt_workstation_lock()

            # Create lock event
            lock_event = WorkstationLockEvent(
                event_id=str(uuid.uuid4()),
                timestamp=current_time,
                trigger=trigger,
                _result=lock_result,
                trigger_context=trigger_context,
                error_details=None if lock_result == WorkstationLockResult.SUCCESS else self._get_last_error_details(),
                session_id=session_id,
            )

            # Store the event
            self._lock_events.append(lock_event)
            self._last_lock_attempt = current_time

            # Update failure tracking
            if lock_result == WorkstationLockResult.SUCCESS:
                self._consecutive_failures = 0
            else:
                self._consecutive_failures += 1

            # Log the event with appropriate severity
            self._log_lock_event(lock_event)

            # Notify callbacks
            if self.config.notify_callbacks_on_lock:
                self._notify_lock_callbacks(lock_event)

            # Handle lock failure
            if lock_result != WorkstationLockResult.SUCCESS:
                self._enforce_workstation_lock_failure_escalation_boundary(lock_event)

            return lock_event

    def _attempt_workstation_lock(self) -> WorkstationLockResult:
        """
        Attempt to lock the workstation using Windows API.

        Returns:
            WorkstationLockResult indicating success or failure type
        """
        if not self._api_available:
            logger.error("Cannot lock workstation: Windows API not available")
            return WorkstationLockResult.FAILED_NOT_SUPPORTED

        if not self._system_supported:
            logger.error("Cannot lock workstation: System not supported")
            return WorkstationLockResult.FAILED_NOT_SUPPORTED

        # Attempt lock with retry logic
        for attempt in range(self.config.max_lock_attempts):
            try:
                logger.info(
                    "Attempting workstation lock", attempt=attempt + 1, max_attempts=self.config.max_lock_attempts
                )

                # Call Windows LockWorkStation API
                _result = self._user32.LockWorkStation()

                if result:
                    logger.critical("WORKSTATION LOCKED SUCCESSFULLY", attempt=attempt + 1, api_result=result)
                    return WorkstationLockResult.SUCCESS
                else:
                    # Get Windows error code
                    error_code = ctypes.windll.kernel32.GetLastError()
                    logger.error(
                        "LockWorkStation API call failed", attempt=attempt + 1, error_code=error_code, api_result=result
                    )

                    # Determine failure type based on error code
                    if error_code == 5:  # ERROR_ACCESS_DENIED
                        return WorkstationLockResult.FAILED_PERMISSION
                    else:
                        # Retry for other errors
                        if attempt < self.config.max_lock_attempts - 1:
                            time.sleep(self.config.retry_delay_seconds)
                            continue
                        return WorkstationLockResult.FAILED_API_CALL

            except OSError:
                logger.error("OS error during workstation lock attempt", attempt=attempt + 1, error=str(e))
                if attempt < self.config.max_lock_attempts - 1:
                    time.sleep(self.config.retry_delay_seconds)
                    continue
                return WorkstationLockResult.FAILED_SYSTEM_ERROR

            except Exception as e:
                logger.error("Unexpected error during workstation lock attempt", attempt=attempt + 1, error=str(e))
                if attempt < self.config.max_lock_attempts - 1:
                    time.sleep(self.config.retry_delay_seconds)
                    continue
                return WorkstationLockResult.FAILED_SYSTEM_ERROR

        # All attempts failed
        return WorkstationLockResult.FAILED_API_CALL

    def _get_last_error_details(self) -> str:
        """Get details about the last Windows API error."""
        try:
            error_code = ctypes.windll.kernel32.GetLastError()

            # Common error codes for LockWorkStation
            error_messages = {
                0: "No error",
                5: "Access denied - insufficient privileges",
                87: "Invalid parameter",
                1314: "Privilege not held",
                1450: "Insufficient system resources",
            }

            error_message = error_messages.get(error_code, f"Unknown error code: {error_code}")
            return f"Windows API Error {error_code}: {error_message}"

        except Exception as e:
            return f"Failed to get error details: {str(e)}"

    def _enforce_workstation_lock_failure_escalation_boundary(self, lock_event: WorkstationLockEvent) -> None:
        """Handle workstation lock failure with appropriate escalation."""

        logger.critical(
            "WORKSTATION LOCK FAILED - SECURITY BREACH POSSIBLE",
            event_id=lock_event.event_id,
            trigger=lock_event.trigger.value,
            _result=lock_event.result.value,
            error_details=lock_event.error_details,
            consecutive_failures=self._consecutive_failures,
        )

        # Implement fallback mechanisms if enabled
        if self.config.enable_fallback_mechanisms:
            self._attempt_fallback_security_measures(lock_event)

        # If multiple consecutive failures, this indicates a serious system problem
        if self._consecutive_failures >= 3:
            logger.critical(
                "MULTIPLE WORKSTATION LOCK FAILURES - SYSTEM COMPROMISE POSSIBLE",
                consecutive_failures=self._consecutive_failures,
                last_24h_failures=self._count_recent_failures(),
            )

    def _attempt_fallback_security_measures(self, lock_event: WorkstationLockEvent) -> None:
        """Attempt fallback security measures when primary lock fails."""

        logger.warning("Attempting fallback security measures", primary_failure=lock_event.result.value)

        # Fallback 1: Try alternative Windows APIs
        try:
            # Alternative approach using ExitWindowsEx with EWX_LOCK flag
            EWX_LOCK = 0x00000000  # Lock the workstation
            _result = ctypes.windll.user32.ExitWindowsEx(EWX_LOCK, 0)

            if result:
                logger.warning("Fallback lock mechanism succeeded", method="ExitWindowsEx")
                return

        except Exception as e:
            logger.error("Fallback lock mechanism failed", method="ExitWindowsEx", error=str(e))

        # Additional fallback mechanisms could be implemented here
        # For example: triggering screensaver, minimizing all windows, etc.
        # However, these would not provide the same security as actual workstation lock

        logger.critical(
            "ALL WORKSTATION LOCK MECHANISMS FAILED", event_id=lock_event.event_id, security_status="COMPROMISED"
        )

    def _log_lock_event(self, lock_event: WorkstationLockEvent) -> None:
        """Log workstation lock event with appropriate severity."""

        log_data = {
            "event_id": lock_event.event_id,
            "trigger": lock_event.trigger.value,
            "result": lock_event.result.value,
            "trigger_context": lock_event.trigger_context,
            "session_id": lock_event.session_id,
            "timestamp": lock_event.timestamp.isoformat(),
        }

        if lock_event.error_details:
            log_data["error_details"] = lock_event.error_details

        if lock_event._result == WorkstationLockResult.SUCCESS:
            if self.config.log_successful_locks:
                logger.critical("WORKSTATION LOCKED - SECURITY RESPONSE ACTIVATED", **log_data)
        else:
            if self.config.log_failed_locks:
                logger.critical("WORKSTATION LOCK FAILED - SECURITY BREACH RISK", **log_data)

    def _notify_lock_callbacks(self, lock_event: WorkstationLockEvent) -> None:
        """Notify registered callbacks about lock event."""

        for callback in self._lock_callbacks:
            try:
                callback(lock_event)
            except Exception as e:
                logger.error(
                    "Error in lock event callback", callback=str(callback), error=str(e), event_id=lock_event.event_id
                )

    def _count_recent_failures(self, hours: int = 24) -> int:
        """Count recent lock failures within specified time window."""

        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(hours=hours)

        return sum(
            1
            for event in self._lock_events
            if (event.timestamp > cutoff_time and event.result != WorkstationLockResult.SUCCESS)
        )

    def get_lock_statistics(self) -> Dict[str, any]:
        """
        Get comprehensive workstation lock statistics.

        Returns:
            Dictionary with lock statistics and system status
        """
        with self._lock:
            # Count events by result
            result_counts = {}
            for result in WorkstationLockResult:
                result_counts[result.value] = sum(1 for event in self._lock_events if event._result == result)

            # Count events by trigger
            trigger_counts = {}
            for trigger in WorkstationLockTrigger:
                trigger_counts[trigger.value] = sum(1 for event in self._lock_events if event.trigger == trigger)

            # Recent activity
            recent_failures_1h = self._count_recent_failures(1)
            recent_failures_24h = self._count_recent_failures(24)

            return {
                "total_lock_attempts": len(self._lock_events),
                "consecutive_failures": self._consecutive_failures,
                "last_lock_attempt": self._last_lock_attempt.isoformat() if self._last_lock_attempt else None,
                "recent_failures": {"1_hour": recent_failures_1h, "24_hours": recent_failures_24h},
                "result_distribution": result_counts,
                "trigger_distribution": trigger_counts,
                "system_status": {
                    "api_available": self._api_available,
                    "system_supported": self._system_supported,
                    "config_enabled": self.config.enable_immediate_lock,
                },
                "callback_count": len(self._lock_callbacks),
            }

    def get_recent_lock_events(self, limit: int = 10) -> List[WorkstationLockEvent]:
        """
        Get recent workstation lock events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent lock events, most recent first
        """
        with self._lock:
            return list(reversed(self._lock_events[-limit:]))

    def test_lock_capability(self) -> Dict[str, any]:
        """
        Test workstation locking capability without actually locking.

        Returns:
            Dictionary with capability test results
        """
        test_results = {
            "api_available": self._api_available,
            "system_supported": self._system_supported,
            "config_enabled": self.config.enable_immediate_lock,
            "test_timestamp": datetime.utcnow().isoformat(),
        }

        # Test API access without calling LockWorkStation
        try:
            if self._api_available:
                # Verify function exists and is callable
                lock_function = getattr(self._user32, "LockWorkStation", None)
                test_results["function_accessible"] = lock_function is not None
                test_results["function_callable"] = callable(lock_function)
            else:
                test_results["function_accessible"] = False
                test_results["function_callable"] = False

        except Exception as e:
            test_results["function_accessible"] = False
            test_results["function_callable"] = False
            test_results["test_error"] = str(e)

        logger.info("Workstation lock capability test completed", results=test_results)

        return test_results

    def lock_workstation(
        self,
        trigger: WorkstationLockTrigger,
        trigger_context: Optional[Dict[str, str]] = None,
        session_id: Optional[str] = None,
    ) -> WorkstationLockEvent:
        """
        Lock the workstation immediately using native Windows APIs.

        Alias for lock_workstation_immediately for backward compatibility.

        Args:
            trigger: The security event that triggered the lock
            trigger_context: Additional context about the trigger
            session_id: Optional session identifier

        Returns:
            WorkstationLockEvent with details of the lock attempt
        """
        return self.lock_workstation_immediately(trigger, trigger_context, session_id)

    def emergency_lock(self, reason: str = "Emergency lock triggered") -> WorkstationLockEvent:
        """
        Emergency workstation lock for immediate security response.

        Alias for emergency_lock_workstation for backward compatibility.

        Args:
            reason: Reason for emergency lock

        Returns:
            WorkstationLockEvent with lock attempt results
        """
        return self.emergency_lock_workstation(reason)

    def emergency_lock_workstation(self, reason: str = "Emergency lock triggered") -> WorkstationLockEvent:
        """
        Emergency workstation lock for immediate security response.

        This method provides a direct interface for emergency locking
        when immediate security action is required.

        Args:
            reason: Reason for emergency lock

        Returns:
            WorkstationLockEvent with lock attempt results
        """
        logger.critical("EMERGENCY WORKSTATION LOCK ACTIVATED", reason=reason, immediate_action=True)

        return self.lock_workstation_immediately(
            trigger=WorkstationLockTrigger.MANUAL_TRIGGER,
            trigger_context={"reason": reason, "emergency": "true"},
            session_id=str(uuid.uuid4()),
        )


# Factory function for easy instantiation


def create_workstation_locker(config: Optional[WorkstationLockConfig] = None) -> WorkstationLocker:
    """
    Factory function to create a workstation locker.

    Args:
        config: Optional configuration, uses defaults if None

    Returns:
        Configured WorkstationLocker instance
    """
    return WorkstationLocker(config)


# Export public interface
__all__ = [
    "WorkstationLockResult",
    "WorkstationLockTrigger",
    "WorkstationLockEvent",
    "WorkstationLockConfig",
    "WorkstationLockError",
    "WorkstationLockPermissionError",
    "WorkstationLockSystemError",
    "WorkstationLocker",
    "create_workstation_locker",
]
