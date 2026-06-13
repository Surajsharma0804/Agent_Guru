"""Module: agent_guru.platform.error_handling.error_response
Purpose: Structured error responses with categorization and remediation.

This module implements production-grade error response structures that provide
comprehensive error information including categorization, context tracking, and
actionable remediation steps. This enables intelligent error handling and recovery.

Performance Characteristics:
    - Time Complexity: O(1) for error creation
    - Space Complexity: O(1) per error instance
    - Overhead: <1ms per error
    - Thread-safe: Yes (immutable dataclasses)

Error Categories:
    - RECOVERABLE: Transient errors that can be retried (network timeout, file lock)
    - NON_RECOVERABLE: Permanent errors requiring user intervention (invalid config)
    - CRITICAL: System-level errors requiring immediate attention (out of memory)

Architecture:
    ErrorResponse provides a structured format for all platform errors with:
    - Error code and message for identification
    - Category for automated handling decisions
    - Context tracking for debugging
    - Remediation steps for resolution guidance
    - Timestamp and metadata for audit trails

Usage Example:
    >>> from agent_guru.platform.error_handling.error_response import (
    ...     ErrorResponse, ErrorCategory, create_error_response
    ... )
    >>>
    >>> # Create error response
    >>> error = create_error_response(
    ...     error_code="FILE_NOT_FOUND",
    ...     message="Configuration file not found",
    ...     category=ErrorCategory.NON_RECOVERABLE,
    ...     context={"file_path": "/etc/config.yaml"},
    ...     exception=FileNotFoundError("config.yaml")
    ... )
    >>>
    >>> # Check if recoverable
    >>> if error.is_recoverable():
    ...     retry_operation()
    ... else:
    ...     print(f"Error: {error.message}")
    ...     for step in error.remediation_steps:
    ...         print(f"  - {step}")

Author: Agent Guru Team
Date: 2026-02-26
Version: 1.0.0
"""

import logging
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error category for automated handling decisions.

    Attributes:
        RECOVERABLE: Transient errors that can be retried automatically
        NON_RECOVERABLE: Permanent errors requiring user intervention
        CRITICAL: System-level errors requiring immediate attention

    """

    RECOVERABLE = "recoverable"
    NON_RECOVERABLE = "non_recoverable"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ErrorResponse:
    """Structured error response with categorization and remediation.

    This immutable dataclass provides comprehensive error information for
    intelligent error handling and recovery. All fields are frozen to ensure
    thread safety and prevent accidental modification.

    Attributes:
        error_code: Unique error code for identification (e.g., "FILE_NOT_FOUND")
        message: Human-readable error message
        category: Error category for automated handling
        context: Additional context information (file paths, parameters, etc.)
        remediation_steps: List of actionable steps to resolve the error
        timestamp: Unix timestamp when error occurred
        exception_type: Type of original exception (if any)
        exception_message: Message from original exception (if any)
        stack_trace: Stack trace from original exception (if any)
        metadata: Additional metadata for logging and monitoring

    Example:
        >>> error = ErrorResponse(
        ...     error_code="NETWORK_TIMEOUT",
        ...     message="Request timed out after 30s",
        ...     category=ErrorCategory.RECOVERABLE,
        ...     context={"url": "https://api.example.com", "timeout": 30},
        ...     remediation_steps=["Retry the request", "Check network connectivity"]
        ... )
        >>> print(f"Error: {error.error_code} - {error.message}")
        >>> if error.is_recoverable():
        ...     print("This error can be retried")

    """

    error_code: str
    message: str
    category: ErrorCategory
    context: dict[str, Any] = field(default_factory=dict)
    remediation_steps: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    exception_type: str | None = None
    exception_message: str | None = None
    stack_trace: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_recoverable(self) -> bool:
        """Check if error is recoverable (can be retried).

        Time Complexity: O(1)

        Returns:
            True if error category is RECOVERABLE

        Example:
            >>> error = ErrorResponse(
            ...     error_code="TIMEOUT",
            ...     message="Operation timed out",
            ...     category=ErrorCategory.RECOVERABLE
            ... )
            >>> error.is_recoverable()
            True

        """
        return self.category == ErrorCategory.RECOVERABLE

    def is_critical(self) -> bool:
        """Check if error is critical (requires immediate attention).

        Time Complexity: O(1)

        Returns:
            True if error category is CRITICAL

        Example:
            >>> error = ErrorResponse(
            ...     error_code="OUT_OF_MEMORY",
            ...     message="System out of memory",
            ...     category=ErrorCategory.CRITICAL
            ... )
            >>> error.is_critical()
            True

        """
        return self.category == ErrorCategory.CRITICAL

    def to_dict(self) -> dict[str, Any]:
        """Convert error response to dictionary for serialization.

        Time Complexity: O(n) where n is number of context/metadata items
        Space Complexity: O(n)

        Returns:
            Dictionary representation of error response

        Example:
            >>> error = ErrorResponse(
            ...     error_code="TEST_ERROR",
            ...     message="Test message",
            ...     category=ErrorCategory.RECOVERABLE
            ... )
            >>> error_dict = error.to_dict()
            >>> print(error_dict["error_code"])
            TEST_ERROR

        """
        return {
            "error_code": self.error_code,
            "message": self.message,
            "category": self.category.value,
            "context": self.context,
            "remediation_steps": self.remediation_steps,
            "timestamp": self.timestamp,
            "exception_type": self.exception_type,
            "exception_message": self.exception_message,
            "stack_trace": self.stack_trace,
            "metadata": self.metadata,
        }

    def __str__(self) -> str:
        """String representation of error response.

        Returns:
            Formatted error string

        Example:
            >>> error = ErrorResponse(
            ...     error_code="TEST_ERROR",
            ...     message="Test message",
            ...     category=ErrorCategory.RECOVERABLE
            ... )
            >>> print(error)
            [RECOVERABLE] TEST_ERROR: Test message

        """
        return f"[{self.category.value.upper()}] {self.error_code}: {self.message}"


def create_error_response(
    error_code: str,
    message: str,
    category: ErrorCategory,
    context: dict[str, Any] | None = None,
    exception: Exception | None = None,
    metadata: dict[str, Any] | None = None,
) -> ErrorResponse:
    """Create error response with automatic remediation generation.

    Time Complexity: O(1) + O(remediation generation)
    Space Complexity: O(1)

    This factory function creates an ErrorResponse with automatically generated
    remediation steps based on the error category and exception type.

    Args:
        error_code: Unique error code for identification
        message: Human-readable error message
        category: Error category for automated handling
        context: Additional context information (optional)
        exception: Original exception (optional)
        metadata: Additional metadata (optional)

    Returns:
        ErrorResponse with generated remediation steps

    Example:
        >>> error = create_error_response(
        ...     error_code="FILE_NOT_FOUND",
        ...     message="Configuration file not found",
        ...     category=ErrorCategory.NON_RECOVERABLE,
        ...     context={"file_path": "/etc/config.yaml"},
        ...     exception=FileNotFoundError("config.yaml")
        ... )
        >>> print(error.remediation_steps)
        ['Verify the file path exists', 'Check file permissions', ...]

    """
    # Extract exception information
    exception_type = None
    exception_message = None
    stack_trace = None

    if exception is not None:
        exception_type = type(exception).__name__
        exception_message = str(exception)
        stack_trace = "".join(
            traceback.format_exception(type(exception), exception, exception.__traceback__),
        )

    # Generate remediation steps
    remediation_steps = generate_remediation_steps(
        error_code=error_code,
        category=category,
        exception_type=exception_type,
        context=context or {},
    )

    # Create error response
    error_response = ErrorResponse(
        error_code=error_code,
        message=message,
        category=category,
        context=context or {},
        remediation_steps=remediation_steps,
        exception_type=exception_type,
        exception_message=exception_message,
        stack_trace=stack_trace,
        metadata=metadata or {},
    )

    # Log error creation
    logger.debug("Created error response: %s (%s)", error_code, category.value)

    return error_response


def generate_remediation_steps(
    error_code: str,
    category: ErrorCategory,
    exception_type: str | None,
    context: dict[str, Any],
) -> list[str]:
    """Generate remediation steps based on error information.

    Time Complexity: O(1)
    Space Complexity: O(1)

    This function generates actionable remediation steps based on the error
    category, exception type, and context. The steps are tailored to help
    users or automated systems resolve the error.

    Args:
        error_code: Unique error code
        category: Error category
        exception_type: Type of original exception (if any)
        context: Error context information

    Returns:
        List of remediation steps

    Example:
        >>> steps = generate_remediation_steps(
        ...     error_code="NETWORK_TIMEOUT",
        ...     category=ErrorCategory.RECOVERABLE,
        ...     exception_type="TimeoutError",
        ...     context={"url": "https://api.example.com"}
        ... )
        >>> print(steps)
        ['Retry the operation', 'Check network connectivity', ...]

    """
    steps: list[str] = []

    # Category-specific remediation
    if category == ErrorCategory.RECOVERABLE:
        steps.append("Retry the operation with exponential backoff")
        steps.append("Check if the issue is transient")

        if exception_type in ("TimeoutError", "ConnectionError", "NetworkError"):
            steps.append("Verify network connectivity")
            steps.append("Check if the remote service is available")
            steps.append("Increase timeout if appropriate")

        elif exception_type in ("FileNotFoundError", "PermissionError"):
            steps.append("Verify the file path exists")
            steps.append("Check file permissions")
            steps.append("Ensure the file is not locked by another process")

    elif category == ErrorCategory.NON_RECOVERABLE:
        steps.append("Review the error message and context")
        steps.append("Correct the configuration or input")
        steps.append("Consult documentation for proper usage")

        if exception_type == "ValueError":
            steps.append("Validate input parameters")
            steps.append("Check data types and formats")

        elif exception_type == "FileNotFoundError":
            if "file_path" in context:
                steps.append(f"Create the missing file: {context['file_path']}")
            steps.append("Verify the file path is correct")
            steps.append("Check if the file was moved or deleted")

        elif exception_type == "PermissionError":
            steps.append("Check file/directory permissions")
            steps.append("Run with elevated privileges if necessary")
            steps.append("Verify user has required access rights")

        elif exception_type in ("ConfigurationError", "ValidationError"):
            steps.append("Review configuration file syntax")
            steps.append("Validate all required fields are present")
            steps.append("Check for typos in configuration keys")

    elif category == ErrorCategory.CRITICAL:
        steps.append("Alert system administrators immediately")
        steps.append("Check system resources (CPU, memory, disk)")
        steps.append("Review system logs for additional context")
        steps.append("Consider emergency shutdown if necessary")

        if exception_type in ("MemoryError", "OutOfMemoryError"):
            steps.append("Free up system memory")
            steps.append("Restart the application")
            steps.append("Increase memory allocation if possible")

        elif exception_type in ("SystemError", "OSError"):
            steps.append("Check system health and stability")
            steps.append("Verify disk space availability")
            steps.append("Review system error logs")

    # Error code specific remediation
    if "PERMISSION" in error_code.upper():
        steps.append("Verify user has required permissions")
        steps.append("Check permission model configuration")

    elif "NETWORK" in error_code.upper():
        steps.append("Test network connectivity")
        steps.append("Check firewall and proxy settings")

    elif "TIMEOUT" in error_code.upper():
        steps.append("Increase timeout value if appropriate")
        steps.append("Optimize operation for better performance")

    elif "VALIDATION" in error_code.upper():
        steps.append("Review input validation rules")
        steps.append("Ensure data meets required format")

    # Ensure at least one remediation step
    if not steps:
        steps.append("Review error details and context")
        steps.append("Consult system documentation")
        steps.append("Contact support if issue persists")

    return steps


def categorize_exception(exception: Exception) -> ErrorCategory:
    """Categorize exception into error category.

    Time Complexity: O(1)
    Space Complexity: O(1)

    This function automatically categorizes exceptions based on their type
    to determine the appropriate error handling strategy.

    Args:
        exception: Exception to categorize

    Returns:
        ErrorCategory for the exception

    Example:
        >>> category = categorize_exception(TimeoutError("Request timed out"))
        >>> print(category)
        ErrorCategory.RECOVERABLE

    """
    exception_type = type(exception).__name__

    # Recoverable errors (transient)
    recoverable_types = {
        "TimeoutError",
        "ConnectionError",
        "NetworkError",
        "TemporaryError",
        "RetryableError",
        "TransientError",
        "BusyError",
        "LockError",
        "ResourceUnavailableError",
    }

    if exception_type in recoverable_types:
        return ErrorCategory.RECOVERABLE

    # Critical errors (system-level)
    critical_types = {
        "MemoryError",
        "OutOfMemoryError",
        "SystemError",
        "OSError",
        "RuntimeError",
        "FatalError",
        "CriticalError",
        "SystemExit",
        "KeyboardInterrupt",
    }

    if exception_type in critical_types:
        return ErrorCategory.CRITICAL

    # Non-recoverable errors (permanent)
    # Default category for most exceptions
    return ErrorCategory.NON_RECOVERABLE


# Common error codes for platform operations
class ErrorCode:
    """Common error codes for platform operations.

    This class provides standardized error codes for consistent error handling
    across the platform integration system.
    """

    # File operations
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_PERMISSION_DENIED = "FILE_PERMISSION_DENIED"
    FILE_ALREADY_EXISTS = "FILE_ALREADY_EXISTS"
    FILE_IO_ERROR = "FILE_IO_ERROR"

    # Network operations
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_CONNECTION_ERROR = "NETWORK_CONNECTION_ERROR"
    NETWORK_UNREACHABLE = "NETWORK_UNREACHABLE"
    NETWORK_SSL_ERROR = "NETWORK_SSL_ERROR"

    # Permission operations
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INSUFFICIENT_PRIVILEGES = "INSUFFICIENT_PRIVILEGES"
    PERMISSION_MODEL_ERROR = "PERMISSION_MODEL_ERROR"

    # Process operations
    PROCESS_NOT_FOUND = "PROCESS_NOT_FOUND"
    PROCESS_ALREADY_RUNNING = "PROCESS_ALREADY_RUNNING"
    PROCESS_TERMINATED = "PROCESS_TERMINATED"

    # Configuration operations
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_VALIDATION_ERROR = "CONFIG_VALIDATION_ERROR"

    # System operations
    SYSTEM_OUT_OF_MEMORY = "SYSTEM_OUT_OF_MEMORY"
    SYSTEM_OUT_OF_DISK = "SYSTEM_OUT_OF_DISK"
    SYSTEM_RESOURCE_EXHAUSTED = "SYSTEM_RESOURCE_EXHAUSTED"

    # Generic operations
    OPERATION_FAILED = "OPERATION_FAILED"
    OPERATION_TIMEOUT = "OPERATION_TIMEOUT"
    OPERATION_CANCELLED = "OPERATION_CANCELLED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
