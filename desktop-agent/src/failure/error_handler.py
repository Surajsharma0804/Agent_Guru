"""
Production-Grade Error Handling System

Implements comprehensive error classification, recovery procedures, and
actionable error messaging for the GURU system. This module provides
the central error handling strategy that ensures graceful degradation
and prevents system crashes due to component failures.

Design Principles:
- Never crash the entire application due to a single component failure
- Provide actionable error messages (not technical stack traces)
- Automatically retry transient failures (network, LLM timeout)
- Never retry security-related failures (authentication, authorization)
- Log all errors to audit logger with appropriate severity
- Maintain security boundaries even during error conditions

Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5, 20.6
"""

import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple


class ErrorSeverity(Enum):
    """
    Error severity classification for determining recovery strategy.

    RECOVERABLE: Can retry or degrade gracefully
    DEGRADED: Feature unavailable, system continues
    CRITICAL: Requires immediate attention, may trigger degradation
    FATAL: System cannot continue, requires emergency halt
    """

    RECOVERABLE = "recoverable"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    FATAL = "fatal"


class ErrorCategory(Enum):
    """
    Error category classification for determining retry strategy.

    Security-related errors (AUTHENTICATION, AUTHORIZATION, SECURITY_VIOLATION)
    are NEVER retried automatically.

    Transient errors (NETWORK, LLM_TIMEOUT) are retried automatically.
    """

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NETWORK = "network"
    LLM_TIMEOUT = "llm_timeout"
    COMPONENT_FAILURE = "component_failure"
    COMMAND_EXECUTION = "command_execution"
    CONFIGURATION = "configuration"
    SECURITY_VIOLATION = "security_violation"
    INTEGRITY_VIOLATION = "integrity_violation"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """
    Comprehensive error context for logging and recovery.
    """

    component_name: str
    error_message: str
    severity: ErrorSeverity
    category: ErrorCategory
    timestamp: datetime = field(default_factory=datetime.now)
    exception: Optional[Exception] = None
    stack_trace: Optional[str] = None
    user_message: Optional[str] = None  # Actionable message for user
    recovery_attempted: bool = False
    recovery_successful: bool = False
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryStrategy:
    """
    Recovery strategy for a specific error category.
    """

    category: ErrorCategory
    max_retries: int
    retry_delay_seconds: float
    exponential_backoff: bool
    allow_degradation: bool
    requires_manual_intervention: bool


class ErrorHandler:
    """
    Central error handling system that provides comprehensive error
    classification, recovery, and user-friendly error messaging.

    This class implements the production-grade error handling strategy
    defined in Requirements 20.1-20.6.
    """

    # Recovery strategies per error category
    RECOVERY_STRATEGIES: Dict[ErrorCategory, RecoveryStrategy] = {
        # Security errors: NEVER retry automatically
        ErrorCategory.AUTHENTICATION: RecoveryStrategy(
            category=ErrorCategory.AUTHENTICATION,
            max_retries=0,
            retry_delay_seconds=0.0,
            exponential_backoff=False,
            allow_degradation=False,
            requires_manual_intervention=True,
        ),
        ErrorCategory.AUTHORIZATION: RecoveryStrategy(
            category=ErrorCategory.AUTHORIZATION,
            max_retries=0,
            retry_delay_seconds=0.0,
            exponential_backoff=False,
            allow_degradation=False,
            requires_manual_intervention=True,
        ),
        ErrorCategory.SECURITY_VIOLATION: RecoveryStrategy(
            category=ErrorCategory.SECURITY_VIOLATION,
            max_retries=0,
            retry_delay_seconds=0.0,
            exponential_backoff=False,
            allow_degradation=False,
            requires_manual_intervention=True,
        ),
        ErrorCategory.INTEGRITY_VIOLATION: RecoveryStrategy(
            category=ErrorCategory.INTEGRITY_VIOLATION,
            max_retries=0,
            retry_delay_seconds=0.0,
            exponential_backoff=False,
            allow_degradation=False,
            requires_manual_intervention=True,
        ),
        # Transient errors: Retry automatically
        ErrorCategory.NETWORK: RecoveryStrategy(
            category=ErrorCategory.NETWORK,
            max_retries=3,
            retry_delay_seconds=1.0,
            exponential_backoff=True,
            allow_degradation=True,
            requires_manual_intervention=False,
        ),
        ErrorCategory.LLM_TIMEOUT: RecoveryStrategy(
            category=ErrorCategory.LLM_TIMEOUT,
            max_retries=0,  # Don't retry timeouts, fall back to templates
            retry_delay_seconds=0.0,
            exponential_backoff=False,
            allow_degradation=True,
            requires_manual_intervention=False,
        ),
        # Component failures: Limited retry
        ErrorCategory.COMPONENT_FAILURE: RecoveryStrategy(
            category=ErrorCategory.COMPONENT_FAILURE,
            max_retries=3,
            retry_delay_seconds=2.0,
            exponential_backoff=True,
            allow_degradation=True,
            requires_manual_intervention=False,
        ),
        # Command execution: No retry (user should verify)
        ErrorCategory.COMMAND_EXECUTION: RecoveryStrategy(
            category=ErrorCategory.COMMAND_EXECUTION,
            max_retries=0,
            retry_delay_seconds=0.0,
            exponential_backoff=False,
            allow_degradation=False,
            requires_manual_intervention=False,
        ),
        # Configuration: No retry (requires fix)
        ErrorCategory.CONFIGURATION: RecoveryStrategy(
            category=ErrorCategory.CONFIGURATION,
            max_retries=0,
            retry_delay_seconds=0.0,
            exponential_backoff=False,
            allow_degradation=True,
            requires_manual_intervention=True,
        ),
        # Resource exhaustion: Limited retry with delay
        ErrorCategory.RESOURCE_EXHAUSTION: RecoveryStrategy(
            category=ErrorCategory.RESOURCE_EXHAUSTION,
            max_retries=2,
            retry_delay_seconds=5.0,
            exponential_backoff=False,
            allow_degradation=True,
            requires_manual_intervention=False,
        ),
        # Unknown: Conservative approach
        ErrorCategory.UNKNOWN: RecoveryStrategy(
            category=ErrorCategory.UNKNOWN,
            max_retries=1,
            retry_delay_seconds=1.0,
            exponential_backoff=False,
            allow_degradation=True,
            requires_manual_intervention=False,
        ),
    }

    def __init__(self, audit_logger=None, tts_service=None):
        """
        Initialize error handler with optional audit logger and TTS service.

        Args:
            audit_logger: Audit logger for logging errors
            tts_service: TTS service for speaking error messages to user
        """
        self.logger = logging.getLogger(__name__)
        self.audit_logger = audit_logger
        self.tts_service = tts_service

        # Error tracking
        self._error_history: List[ErrorContext] = []
        self._error_lock = threading.RLock()

        # Statistics
        self._stats = {
            "total_errors": 0,
            "errors_by_category": {cat: 0 for cat in ErrorCategory},
            "errors_by_severity": {sev: 0 for sev in ErrorSeverity},
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "security_errors": 0,
            "transient_errors": 0,
        }

        # Callbacks
        self._error_callbacks: List[Callable[[ErrorContext], None]] = []
        self._critical_error_callbacks: List[Callable[[ErrorContext], None]] = []

    def classify_error(
        self, exception: Exception, component_name: str, context: Optional[Dict[str, Any]] = None
    ) -> ErrorContext:
        """
        Classify an exception into error severity and category.

        This method analyzes the exception type and context to determine
        the appropriate error classification for recovery strategy.

        Args:
            exception: The exception to classify
            component_name: Name of the component that raised the exception
            context: Additional context about the error

        Returns:
            ErrorContext with classification and metadata
        """
        context = context or {}

        # Determine category based on exception type and context
        category = self._determine_category(exception, component_name, context)

        # Determine severity based on category and component
        severity = self._determine_severity(category, component_name, exception)

        # Generate user-friendly message
        user_message = self._generate_user_message(exception, category, component_name)

        # Create error context
        error_ctx = ErrorContext(
            component_name=component_name,
            error_message=str(exception),
            severity=severity,
            category=category,
            exception=exception,
            stack_trace=traceback.format_exc(),
            user_message=user_message,
            metadata=context,
        )

        # Track statistics
        with self._error_lock:
            self._stats["total_errors"] += 1
            self._stats["errors_by_category"][category] += 1
            self._stats["errors_by_severity"][severity] += 1

            if category in [
                ErrorCategory.AUTHENTICATION,
                ErrorCategory.AUTHORIZATION,
                ErrorCategory.SECURITY_VIOLATION,
                ErrorCategory.INTEGRITY_VIOLATION,
            ]:
                self._stats["security_errors"] += 1

            if category in [ErrorCategory.NETWORK, ErrorCategory.LLM_TIMEOUT]:
                self._stats["transient_errors"] += 1

            # Store in history
            self._error_history.append(error_ctx)
            if len(self._error_history) > 1000:
                self._error_history = self._error_history[-1000:]

        return error_ctx

    def _determine_category(self, exception: Exception, component_name: str, context: Dict[str, Any]) -> ErrorCategory:
        """Determine error category from exception type and context."""
        exception_type = type(exception).__name__
        exception_msg = str(exception).lower()

        # Check context hints first
        if "category" in context:
            try:
                return ErrorCategory(context["category"])
            except (ValueError, KeyError):
                pass

        # Authentication errors
        if any(keyword in exception_type.lower() for keyword in ["auth", "authentication"]):
            return ErrorCategory.AUTHENTICATION
        if any(keyword in exception_msg for keyword in ["authentication failed", "biometric", "windows hello"]):
            return ErrorCategory.AUTHENTICATION

        # Authorization errors
        if any(keyword in exception_type.lower() for keyword in ["authorization", "permission"]):
            return ErrorCategory.AUTHORIZATION
        if any(keyword in exception_msg for keyword in ["permission denied", "not authorized", "access denied"]):
            return ErrorCategory.AUTHORIZATION

        # Security violations
        if any(keyword in exception_type.lower() for keyword in ["security", "intrusion"]):
            return ErrorCategory.SECURITY_VIOLATION
        if any(keyword in exception_msg for keyword in ["security violation", "intrusion", "unauthorized"]):
            return ErrorCategory.SECURITY_VIOLATION

        # Integrity violations
        if any(keyword in exception_type.lower() for keyword in ["integrity", "tamper"]):
            return ErrorCategory.INTEGRITY_VIOLATION
        if any(keyword in exception_msg for keyword in ["integrity", "tamper", "signature", "checksum"]):
            return ErrorCategory.INTEGRITY_VIOLATION

        # LLM timeout (check BEFORE generic network/timeout)
        # Only classify as LLM_TIMEOUT if the error message explicitly mentions LLM timeout
        if "llm" in exception_msg and "timeout" in exception_msg:
            return ErrorCategory.LLM_TIMEOUT

        # Also check context for explicit LLM timeout indication
        if context.get("category") == "llm_timeout":
            return ErrorCategory.LLM_TIMEOUT

        # Network errors (check AFTER LLM timeout)
        if any(keyword in exception_type.lower() for keyword in ["network", "connection", "timeout", "http"]):
            return ErrorCategory.NETWORK
        if any(keyword in exception_msg for keyword in ["connection", "network", "timeout", "unreachable"]):
            return ErrorCategory.NETWORK

        # Component failure
        if any(keyword in exception_type.lower() for keyword in ["component", "failure", "crash"]):
            return ErrorCategory.COMPONENT_FAILURE

        # Command execution
        if any(keyword in exception_msg for keyword in ["command", "execution", "application not found"]):
            return ErrorCategory.COMMAND_EXECUTION

        # Configuration
        if any(keyword in exception_type.lower() for keyword in ["config", "configuration"]):
            return ErrorCategory.CONFIGURATION
        if any(keyword in exception_msg for keyword in ["configuration", "config", "settings"]):
            return ErrorCategory.CONFIGURATION

        # Resource exhaustion
        if any(keyword in exception_type.lower() for keyword in ["memory", "resource", "limit"]):
            return ErrorCategory.RESOURCE_EXHAUSTION
        if any(keyword in exception_msg for keyword in ["out of memory", "resource limit", "quota exceeded"]):
            return ErrorCategory.RESOURCE_EXHAUSTION

        return ErrorCategory.UNKNOWN

    def _determine_severity(self, category: ErrorCategory, component_name: str, exception: Exception) -> ErrorSeverity:
        """Determine error severity based on category and component criticality."""
        # Security errors are always critical or fatal
        if category in [ErrorCategory.SECURITY_VIOLATION, ErrorCategory.INTEGRITY_VIOLATION]:
            return ErrorSeverity.FATAL

        if category in [ErrorCategory.AUTHENTICATION, ErrorCategory.AUTHORIZATION]:
            return ErrorSeverity.CRITICAL

        # Critical components
        critical_components = ["authority_state_machine", "audit_logger", "biometric_provider", "intrusion_detector"]

        if component_name.lower() in critical_components:
            return ErrorSeverity.CRITICAL

        # Transient errors are recoverable
        if category in [ErrorCategory.NETWORK, ErrorCategory.LLM_TIMEOUT]:
            return ErrorSeverity.RECOVERABLE

        # Command execution errors are degraded (feature fails, system continues)
        if category == ErrorCategory.COMMAND_EXECUTION:
            return ErrorSeverity.DEGRADED

        # Configuration errors are critical (system may not function correctly)
        if category == ErrorCategory.CONFIGURATION:
            return ErrorSeverity.CRITICAL

        # Component failures depend on the component
        if category == ErrorCategory.COMPONENT_FAILURE:
            if component_name.lower() in critical_components:
                return ErrorSeverity.CRITICAL
            return ErrorSeverity.DEGRADED

        # Resource exhaustion is critical
        if category == ErrorCategory.RESOURCE_EXHAUSTION:
            return ErrorSeverity.CRITICAL

        # Default to degraded
        return ErrorSeverity.DEGRADED

    def _generate_user_message(self, exception: Exception, category: ErrorCategory, component_name: str) -> str:
        """
        Generate actionable, user-friendly error message.

        This method converts technical exceptions into clear, actionable
        messages that users can understand and act upon.

        Validates: Requirements 20.3, 20.4
        """
        exception_msg = str(exception)

        # Authentication errors
        if category == ErrorCategory.AUTHENTICATION:
            if "failed" in exception_msg.lower():
                return "Authentication failed. Please try again."
            if "unavailable" in exception_msg.lower():
                return "Biometric authentication unavailable. Please configure Windows Hello."
            return "Authentication error. Please verify your biometric settings."

        # Authorization errors
        if category == ErrorCategory.AUTHORIZATION:
            return "Permission denied. This action requires elevated privileges."

        # Security violations
        if category == ErrorCategory.SECURITY_VIOLATION:
            return "Security violation detected. System locked for your protection."

        # Integrity violations
        if category == ErrorCategory.INTEGRITY_VIOLATION:
            return "Data integrity violation detected. Please verify system integrity."

        # Network errors
        if category == ErrorCategory.NETWORK:
            return "Network connection error. Please check your internet connection."

        # LLM timeout
        if category == ErrorCategory.LLM_TIMEOUT:
            return "AI model timed out. Using fallback response."

        # Component failures
        if category == ErrorCategory.COMPONENT_FAILURE:
            return f"{component_name} is temporarily unavailable. Attempting recovery."

        # Command execution
        if category == ErrorCategory.COMMAND_EXECUTION:
            if "not found" in exception_msg.lower():
                return "Application not found. Please check if it's installed."
            if "failed to open" in exception_msg.lower():
                return f"Failed to open application. {exception_msg}"
            return f"Command failed. {exception_msg}"

        # Configuration
        if category == ErrorCategory.CONFIGURATION:
            return "Configuration error. Please check your settings."

        # Resource exhaustion
        if category == ErrorCategory.RESOURCE_EXHAUSTION:
            return "System resources exhausted. Please close some applications."

        # Unknown
        return f"An error occurred in {component_name}. Please try again."

    def handle_error(
        self,
        exception: Exception,
        component_name: str,
        context: Optional[Dict[str, Any]] = None,
        operation: Optional[Callable] = None,
    ) -> Tuple[bool, Optional[Any]]:
        """
        Handle an error with automatic classification, logging, recovery, and user notification.

        This is the main entry point for error handling. It:
        1. Classifies the error
        2. Logs to audit logger
        3. Attempts recovery if appropriate
        4. Notifies user via TTS
        5. Invokes callbacks

        Args:
            exception: The exception to handle
            component_name: Name of the component that raised the exception
            context: Additional context about the error
            operation: Optional operation to retry if recovery is appropriate

        Returns:
            Tuple of (success, result) where success indicates if recovery succeeded

        Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5, 20.6
        """
        # Classify error
        error_ctx = self.classify_error(exception, component_name, context)

        # Log to audit logger
        self._log_error(error_ctx)

        # Log to standard logger
        self.logger.error(
            f"Error in {component_name}: {error_ctx.error_message} "
            f"(category: {error_ctx.category.value}, severity: {error_ctx.severity.value})"
        )

        # Speak error message to user
        self._speak_error_message(error_ctx)

        # Invoke callbacks
        self._invoke_callbacks(error_ctx)

        # Attempt recovery if appropriate
        if operation and self._should_attempt_recovery(error_ctx):
            success, result = self._attempt_recovery(error_ctx, operation)
            return success, result

        return False, None

    def _should_attempt_recovery(self, error_ctx: ErrorContext) -> bool:
        """
        Determine if recovery should be attempted for this error.

        Security errors are NEVER retried automatically.
        Validates: Requirement 20.6
        """
        strategy = self.RECOVERY_STRATEGIES.get(error_ctx.category)
        if not strategy:
            return False

        # Never retry security-related errors
        if error_ctx.category in [
            ErrorCategory.AUTHENTICATION,
            ErrorCategory.AUTHORIZATION,
            ErrorCategory.SECURITY_VIOLATION,
            ErrorCategory.INTEGRITY_VIOLATION,
        ]:
            return False

        # Check if max retries exceeded
        if error_ctx.retry_count >= strategy.max_retries:
            return False

        return strategy.max_retries > 0

    def _attempt_recovery(self, error_ctx: ErrorContext, operation: Callable) -> Tuple[bool, Optional[Any]]:
        """
        Attempt to recover from error by retrying operation.

        Implements exponential backoff for transient failures.
        Validates: Requirement 20.5
        """
        strategy = self.RECOVERY_STRATEGIES.get(error_ctx.category)
        if not strategy:
            return False, None

        error_ctx.recovery_attempted = True

        for attempt in range(strategy.max_retries):
            error_ctx.retry_count = attempt + 1

            # Calculate delay with exponential backoff if enabled
            if strategy.exponential_backoff:
                delay = strategy.retry_delay_seconds * (2**attempt)
            else:
                delay = strategy.retry_delay_seconds

            if delay > 0:
                self.logger.info(
                    f"Retrying {error_ctx.component_name} after {delay}s "
                    f"(attempt {attempt + 1}/{strategy.max_retries})"
                )
                time.sleep(delay)

            try:
                result = operation()
                error_ctx.recovery_successful = True

                with self._error_lock:
                    self._stats["successful_recoveries"] += 1

                self.logger.info(f"Recovery successful for {error_ctx.component_name} " f"after {attempt + 1} attempts")

                return True, result

            except Exception as e:
                self.logger.warning(f"Recovery attempt {attempt + 1} failed for {error_ctx.component_name}: {e}")

                if attempt == strategy.max_retries - 1:
                    # Final attempt failed
                    with self._error_lock:
                        self._stats["failed_recoveries"] += 1

                    self.logger.error(
                        f"Recovery failed for {error_ctx.component_name} " f"after {strategy.max_retries} attempts"
                    )

        return False, None

    def _log_error(self, error_ctx: ErrorContext) -> None:
        """Log error to audit logger with appropriate severity."""
        if not self.audit_logger:
            return

        try:
            # Map error severity to audit severity
            try:
                from ..audit.audit_logging import AuditSeverity

                severity_map = {
                    ErrorSeverity.RECOVERABLE: AuditSeverity.INFO,
                    ErrorSeverity.DEGRADED: AuditSeverity.WARNING,
                    ErrorSeverity.CRITICAL: AuditSeverity.ERROR,
                    ErrorSeverity.FATAL: AuditSeverity.CRITICAL,
                }

                audit_severity = severity_map.get(error_ctx.severity, AuditSeverity.ERROR)
            except ImportError:
                # Fallback if audit logging module not available
                # Use string values directly
                severity_map = {
                    ErrorSeverity.RECOVERABLE: "INFO",
                    ErrorSeverity.DEGRADED: "WARNING",
                    ErrorSeverity.CRITICAL: "ERROR",
                    ErrorSeverity.FATAL: "CRITICAL",
                }
                audit_severity = severity_map.get(error_ctx.severity, "ERROR")

            self.audit_logger.log_system_event(
                event_type="error",
                event_data={
                    "component": error_ctx.component_name,
                    "category": error_ctx.category.value,
                    "severity": error_ctx.severity.value,
                    "message": error_ctx.error_message,
                    "user_message": error_ctx.user_message,
                    "timestamp": error_ctx.timestamp.isoformat(),
                    "metadata": error_ctx.metadata,
                },
                severity=audit_severity,
            )
        except Exception as e:
            self.logger.error(f"Failed to log error to audit logger: {e}")

    def _speak_error_message(self, error_ctx: ErrorContext) -> None:
        """Speak user-friendly error message via TTS."""
        if not self.tts_service or not error_ctx.user_message:
            return

        try:
            # Use HIGH priority for critical errors, NORMAL for others
            try:
                from ..gui.tts_service import TTSPriority

                priority = (
                    TTSPriority.HIGH
                    if error_ctx.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]
                    else TTSPriority.NORMAL
                )
            except ImportError:
                # Fallback if TTS module not available
                priority = "HIGH" if error_ctx.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL] else "NORMAL"

            self.tts_service.speak(error_ctx.user_message, priority=priority)
        except Exception as e:
            self.logger.error(f"Failed to speak error message: {e}")

    def _invoke_callbacks(self, error_ctx: ErrorContext) -> None:
        """Invoke registered error callbacks."""
        # Invoke general error callbacks
        for callback in self._error_callbacks:
            try:
                callback(error_ctx)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")

        # Invoke critical error callbacks for critical/fatal errors
        if error_ctx.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]:
            for callback in self._critical_error_callbacks:
                try:
                    callback(error_ctx)
                except Exception as e:
                    self.logger.error(f"Error in critical error callback: {e}")

    def add_error_callback(self, callback: Callable[[ErrorContext], None]) -> None:
        """Add callback for all errors."""
        self._error_callbacks.append(callback)

    def add_critical_error_callback(self, callback: Callable[[ErrorContext], None]) -> None:
        """Add callback for critical/fatal errors only."""
        self._critical_error_callbacks.append(callback)

    def get_error_history(
        self,
        limit: Optional[int] = None,
        category: Optional[ErrorCategory] = None,
        severity: Optional[ErrorSeverity] = None,
    ) -> List[ErrorContext]:
        """Get error history with optional filtering."""
        with self._error_lock:
            history = self._error_history.copy()

        # Filter by category
        if category:
            history = [e for e in history if e.category == category]

        # Filter by severity
        if severity:
            history = [e for e in history if e.severity == severity]

        # Limit results
        if limit:
            history = history[-limit:]

        return history

    def get_statistics(self) -> Dict[str, Any]:
        """Get error handling statistics."""
        with self._error_lock:
            return self._stats.copy()

    def clear_history(self) -> None:
        """Clear error history (for testing)."""
        with self._error_lock:
            self._error_history.clear()


def safe_execute(
    component_name: str, error_handler: Optional[ErrorHandler] = None, context: Optional[Dict[str, Any]] = None
):
    """
    Decorator for safe execution with automatic error handling.

    This decorator wraps functions to automatically catch and handle exceptions
    using the error handler. It ensures that exceptions never crash the application.

    Usage:
        @safe_execute("my_component", error_handler)
        def my_function():
            # Function code that might raise exceptions
            pass

    Validates: Requirements 20.1, 20.2
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if error_handler:
                    error_handler.handle_error(e, component_name, context)
                else:
                    # Fallback logging if no error handler provided
                    logging.getLogger(__name__).error(f"Error in {component_name}: {e}", exc_info=True)
                return None

        return wrapper

    return decorator


def safe_execute_with_retry(component_name: str, error_handler: ErrorHandler, context: Optional[Dict[str, Any]] = None):
    """
    Decorator for safe execution with automatic retry for transient failures.

    This decorator wraps functions to automatically catch exceptions and retry
    transient failures (network, LLM timeout) while never retrying security failures.

    Usage:
        @safe_execute_with_retry("my_component", error_handler)
        def my_function():
            # Function code that might raise transient exceptions
            pass

    Validates: Requirements 20.1, 20.2, 20.5, 20.6
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Handle error with automatic retry
                success, result = error_handler.handle_error(
                    e, component_name, context, operation=lambda: func(*args, **kwargs)
                )

                if success:
                    return result

                return None

        return wrapper

    return decorator
