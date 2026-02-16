# Error Handling Standards for AGENT_GURU

## Overview

This document defines the mandatory error handling standards for all components in the AGENT_GURU project. These standards ensure consistent error reporting, proper error recovery, and maintainable error handling across all specifications.

## Core Principles

1. **Fail Fast**: Detect errors early and raise exceptions immediately
2. **Descriptive Errors**: All exceptions include context, cause, and suggested actions
3. **Unified Hierarchy**: All errors inherit from common base classes
4. **Structured Logging**: All errors logged with full context before propagation
5. **Graceful Degradation**: Optional features return None rather than raising exceptions

## Error Hierarchy

### Base Error Classes

All projects MUST use this unified error hierarchy defined in `guru/errors.py`:

```python
"""Unified error hierarchy for AGENT_GURU."""

from typing import Optional, Dict, Any
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorCategory(Enum):
    """Error categories for classification."""
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    VALIDATION = "VALIDATION"
    NETWORK = "NETWORK"
    STORAGE = "STORAGE"
    CRYPTOGRAPHY = "CRYPTOGRAPHY"
    CONFIGURATION = "CONFIGURATION"
    PLATFORM = "PLATFORM"
    RESOURCE = "RESOURCE"
    INTERNAL = "INTERNAL"


class GuruError(Exception):
    """
    Base exception for all AGENT_GURU errors.
    
    All custom exceptions MUST inherit from this class.
    """
    
    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        suggested_action: Optional[str] = None
    ):
        """
        Initialize GuruError.
        
        Args:
            message: Human-readable error message
            error_code: Unique error code (format: COMPONENT_ERROR_TYPE_DETAIL)
            category: Error category for classification
            severity: Error severity level
            details: Additional context information
            cause: Original exception that caused this error
            suggested_action: Suggested action for user to resolve error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.cause = cause
        self.suggested_action = suggested_action
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/serialization."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
            "suggested_action": self.suggested_action
        }
    
    def __str__(self) -> str:
        """Format error message with code and suggested action."""
        parts = [f"[{self.error_code}] {self.message}"]
        if self.details:
            parts.append(f"Details: {self.details}")
        if self.suggested_action:
            parts.append(f"Suggested action: {self.suggested_action}")
        return " | ".join(parts)


# Authentication Errors
class AuthenticationError(GuruError):
    """Base class for authentication errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.AUTHENTICATION,
            **kwargs
        )


class BiometricAuthenticationError(AuthenticationError):
    """Biometric authentication failed."""
    pass


class InvalidCredentialsError(AuthenticationError):
    """Invalid credentials provided."""
    pass


# Authorization Errors
class AuthorizationError(GuruError):
    """Base class for authorization errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.AUTHORIZATION,
            **kwargs
        )


class PermissionDeniedError(AuthorizationError):
    """Permission denied for requested operation."""
    pass


class PolicyViolationError(AuthorizationError):
    """Operation violates policy."""
    pass


# Validation Errors
class ValidationError(GuruError):
    """Base class for validation errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            **kwargs
        )


class InvalidInputError(ValidationError):
    """Invalid input provided."""
    pass


class ConfigurationError(ValidationError):
    """Invalid configuration."""
    pass


# Network Errors
class NetworkError(GuruError):
    """Base class for network errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.WARNING,  # Network errors often transient
            **kwargs
        )


class ConnectionError(NetworkError):
    """Network connection failed."""
    pass


class TimeoutError(NetworkError):
    """Network operation timed out."""
    pass


# Storage Errors
class StorageError(GuruError):
    """Base class for storage errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.STORAGE,
            **kwargs
        )


class InsufficientSpaceError(StorageError):
    """Insufficient disk space."""
    pass


class FileNotFoundError(StorageError):
    """File not found."""
    pass


class DatabaseError(StorageError):
    """Database operation failed."""
    pass


# Cryptography Errors
class CryptographyError(GuruError):
    """Base class for cryptography errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.CRYPTOGRAPHY,
            severity=ErrorSeverity.CRITICAL,  # Crypto errors are critical
            **kwargs
        )


class SignatureVerificationError(CryptographyError):
    """Signature verification failed."""
    pass


class EncryptionError(CryptographyError):
    """Encryption operation failed."""
    pass


class DecryptionError(CryptographyError):
    """Decryption operation failed."""
    pass


# Platform Errors
class PlatformError(GuruError):
    """Base class for platform errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.PLATFORM,
            **kwargs
        )


class UnsupportedPlatformError(PlatformError):
    """Platform not supported."""
    pass


class PlatformOperationError(PlatformError):
    """Platform-specific operation failed."""
    pass


# Resource Errors
class ResourceError(GuruError):
    """Base class for resource errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.RESOURCE,
            **kwargs
        )


class ResourceNotFoundError(ResourceError):
    """Resource not found."""
    pass


class ResourceExhaustedError(ResourceError):
    """Resource exhausted."""
    pass


# Internal Errors
class InternalError(GuruError):
    """Base class for internal errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.INTERNAL,
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )
```

## Error Code Format

### Standard Format

All error codes MUST follow this format:

```
COMPONENT_ERROR_TYPE_DETAIL
```

**Components**:
- `COMPONENT`: System component (e.g., AUTH, POLICY, DEPLOY, MEMORY)
- `ERROR_TYPE`: Error category (e.g., VALIDATION, NETWORK, CRYPTO)
- `DETAIL`: Specific error detail (e.g., INVALID_INPUT, CONNECTION_FAILED)

**Examples**:
- `AUTH_BIOMETRIC_FACE_NOT_RECOGNIZED`
- `DEPLOY_NETWORK_PACKAGE_DOWNLOAD_FAILED`
- `POLICY_AUTHORIZATION_PERMISSION_DENIED`
- `MEMORY_STORAGE_DATABASE_CONNECTION_FAILED`
- `PLATFORM_VALIDATION_UNSUPPORTED_OS`

### Component Prefixes

| Component | Prefix | Description |
|-----------|--------|-------------|
| Authentication | AUTH | Biometric and identity authentication |
| Policy Engine | POLICY | Access control and policy evaluation |
| Deployment | DEPLOY | Package management and deployment |
| Memory System | MEMORY | Conversation and memory storage |
| LLM Runtime | LLM | Language model operations |
| Platform Integration | PLATFORM | OS-specific operations |
| Vision System | VISION | Face recognition and detection |
| Speech Engine | SPEECH | Voice recognition and processing |
| Avatar System | AVATAR | Emotion and personality engine |

## Error Handling Patterns

### Pattern 1: Raise with Context

Always include full context when raising errors:

```python
def install_package(self, package_path: Path, target_env: Path) -> None:
    """Install package to target environment."""
    try:
        self._do_install(package_path, target_env)
    except subprocess.CalledProcessError as e:
        raise InstallationError(
            f"Failed to install package {package_path.name}",
            error_code="DEPLOY_INSTALLATION_SUBPROCESS_FAILED",
            category=ErrorCategory.INTERNAL,
            details={
                "package_path": str(package_path),
                "target_env": str(target_env),
                "return_code": e.returncode,
                "stdout": e.stdout,
                "stderr": e.stderr
            },
            cause=e,
            suggested_action="Check package file integrity and target environment permissions"
        )
```

### Pattern 2: Log Before Raising

Always log errors before raising:

```python
import logging

logger = logging.getLogger(__name__)

def verify_signature(self, package_path: Path, signature: bytes) -> bool:
    """Verify package signature."""
    try:
        # Verification logic
        ...
    except Exception as e:
        error = SignatureVerificationError(
            f"Signature verification failed for {package_path.name}",
            error_code="DEPLOY_CRYPTO_SIGNATURE_INVALID",
            category=ErrorCategory.CRYPTOGRAPHY,
            severity=ErrorSeverity.CRITICAL,
            details={"package_path": str(package_path)},
            cause=e,
            suggested_action="Verify package source and re-download if necessary"
        )
        logger.error(error.to_dict())
        raise error
```

### Pattern 3: Graceful Degradation

For optional features, return None instead of raising:

```python
def get_gpu_info(self) -> Optional[List[GPUInfo]]:
    """
    Get GPU information if available.
    
    Returns:
        List of GPU info or None if no GPU or GPUtil unavailable
    """
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        return [self._convert_gpu_info(gpu) for gpu in gpus]
    except ImportError:
        logger.warning("GPUtil not available, GPU info unavailable")
        return None
    except Exception as e:
        logger.warning(f"Failed to get GPU info: {e}")
        return None
```

### Pattern 4: Retry with Exponential Backoff

For transient errors, implement retry logic:

```python
import time
from typing import TypeVar, Callable

T = TypeVar('T')

def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    initial_delay: float = 0.1,
    backoff_factor: float = 2.0,
    retryable_errors: tuple = (NetworkError, TimeoutError)
) -> T:
    """
    Retry function with exponential backoff.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Backoff multiplier
        retryable_errors: Tuple of retryable error types
        
    Returns:
        Function result
        
    Raises:
        Last exception if all retries exhausted
    """
    delay = initial_delay
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except retryable_errors as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(f"All {max_retries + 1} attempts failed")
    
    raise last_error

# Usage
def download_package(self, package_name: str, version: str, repo_url: str) -> Path:
    """Download package with retry logic."""
    def _download():
        return self._do_download(package_name, version, repo_url)
    
    try:
        return retry_with_backoff(_download, max_retries=3)
    except Exception as e:
        raise NetworkError(
            f"Failed to download {package_name} {version} after 3 retries",
            error_code="DEPLOY_NETWORK_DOWNLOAD_FAILED",
            category=ErrorCategory.NETWORK,
            details={
                "package_name": package_name,
                "version": version,
                "repo_url": repo_url
            },
            cause=e,
            suggested_action="Check network connection and repository availability"
        )
```

### Pattern 5: Context Managers for Cleanup

Use context managers to ensure cleanup on errors:

```python
from contextlib import contextmanager
from typing import Generator

@contextmanager
def transaction_context(self, transaction_id: str) -> Generator[Transaction, None, None]:
    """
    Context manager for transactional operations.
    
    Automatically rolls back on error.
    """
    transaction = self.begin_transaction(transaction_id)
    try:
        yield transaction
        self.commit_transaction(transaction)
    except Exception as e:
        logger.error(f"Transaction {transaction_id} failed: {e}")
        self.rollback_transaction(transaction)
        raise
    finally:
        self.cleanup_transaction(transaction)

# Usage
with self.transaction_context("install-packages") as txn:
    for package in packages:
        self.install_package(package, txn)
```

## Error Recovery Strategies

### Automatic Recovery

These errors SHOULD be automatically recovered:

| Error Type | Recovery Strategy |
|------------|-------------------|
| NetworkError | Retry with exponential backoff (max 3 attempts) |
| TimeoutError | Retry with increased timeout |
| ConnectionError | Retry with alternative repository |
| TransientStorageError | Retry after short delay |

### Manual Recovery Required

These errors REQUIRE user intervention:

| Error Type | User Action |
|------------|-------------|
| AuthenticationError | Re-authenticate with valid credentials |
| PermissionDeniedError | Run with elevated privileges |
| InsufficientSpaceError | Free disk space or change installation location |
| SignatureVerificationError | Verify package source and re-download |
| UnsupportedPlatformError | Use supported platform (Windows/macOS/Linux) |
| ConfigurationError | Fix configuration file |

### Graceful Degradation

These errors SHOULD degrade gracefully:

| Error Type | Degradation Strategy |
|------------|---------------------|
| GPU not available | Fall back to CPU |
| Optional library missing | Disable feature, return None |
| Cache unavailable | Proceed without caching |
| Metrics collection failed | Continue without metrics |

## Error Logging

### Logging Configuration

All projects MUST configure structured logging:

```python
import logging
import json
from datetime import datetime

class StructuredFormatter(logging.Formatter):
    """Format log records as JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add GuruError details if present
        if hasattr(record, "error_dict"):
            log_data["error"] = record.error_dict
        
        return json.dumps(log_data)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("guru.log")
    ]
)

# Use structured formatter for file handler
for handler in logging.getLogger().handlers:
    if isinstance(handler, logging.FileHandler):
        handler.setFormatter(StructuredFormatter())
```

### Logging Errors

Always log errors with full context:

```python
def handle_error(self, error: GuruError) -> None:
    """Log error with full context."""
    logger = logging.getLogger(__name__)
    
    # Create log record with error details
    extra = {"error_dict": error.to_dict()}
    
    if error.severity == ErrorSeverity.CRITICAL:
        logger.critical(str(error), extra=extra)
    elif error.severity == ErrorSeverity.ERROR:
        logger.error(str(error), extra=extra)
    elif error.severity == ErrorSeverity.WARNING:
        logger.warning(str(error), extra=extra)
    else:
        logger.info(str(error), extra=extra)
```

## Testing Error Handling

### Unit Tests for Errors

Test all error conditions:

```python
def test_install_package_insufficient_space_raises_error(mocker):
    """Test that insufficient disk space raises InsufficientSpaceError."""
    manager = PackageManager()
    
    # Mock disk space check to return insufficient space
    mocker.patch.object(
        manager.hardware_monitor,
        'get_disk_usage',
        return_value=DiskInfo(total=1000, used=900, free=100, percent=90)
    )
    
    with pytest.raises(InsufficientSpaceError) as exc_info:
        manager.download_package("large-package", "1.0.0", "https://pypi.org")
    
    # Verify error details
    error = exc_info.value
    assert error.error_code == "DEPLOY_STORAGE_INSUFFICIENT_SPACE"
    assert error.category == ErrorCategory.STORAGE
    assert "large-package" in error.details["package_name"]
    assert error.suggested_action is not None
```

### Property Tests for Error Handling

Test error handling properties:

```python
from hypothesis import given, settings, strategies as st

@settings(max_examples=100)
@given(invalid_path=st.text())
def test_property_invalid_paths_raise_validation_error(invalid_path):
    """
    Property: All invalid paths should raise ValidationError.
    
    For any invalid path string, when passed to a function expecting a valid path,
    then a ValidationError should be raised with appropriate error code.
    """
    manager = PackageManager()
    
    with pytest.raises(ValidationError) as exc_info:
        manager.install_package(Path(invalid_path), Path("/tmp/env"))
    
    error = exc_info.value
    assert error.error_code.startswith("DEPLOY_VALIDATION_")
    assert error.category == ErrorCategory.VALIDATION
```

## Best Practices

### DO

✅ Inherit from GuruError base class
✅ Use descriptive error messages
✅ Include error codes in format COMPONENT_ERROR_TYPE_DETAIL
✅ Log errors before raising
✅ Include full context in error details
✅ Provide suggested actions for users
✅ Use appropriate error severity
✅ Implement retry logic for transient errors
✅ Use context managers for cleanup
✅ Test all error conditions

### DON'T

❌ Catch exceptions without handling them
❌ Use bare `except:` clauses
❌ Raise generic Exception
❌ Ignore errors silently
❌ Log and raise (choose one)
❌ Include sensitive data in error messages
❌ Use error codes inconsistently
❌ Forget to clean up resources on error
❌ Retry non-transient errors
❌ Return error codes instead of raising exceptions

## Compliance

### Mandatory Requirements

All specifications MUST:
1. Use unified error hierarchy from `guru/errors.py`
2. Follow error code format: COMPONENT_ERROR_TYPE_DETAIL
3. Log errors before raising
4. Include error handling section in design document
5. Test all error conditions
6. Provide suggested actions for user-facing errors
7. Implement retry logic for transient errors
8. Use context managers for resource cleanup

### Review Checklist

Before merging, verify:
- [ ] All errors inherit from GuruError
- [ ] All error codes follow standard format
- [ ] All errors include context and suggested actions
- [ ] All errors are logged before raising
- [ ] All error conditions are tested
- [ ] Retry logic implemented for transient errors
- [ ] Resources cleaned up on errors
- [ ] Error handling documented in design

## References

- [Python Exception Handling Best Practices](https://docs.python.org/3/tutorial/errors.html)
- [Effective Error Handling](https://www.martinfowler.com/articles/replaceThrowWithNotification.html)
- [Structured Logging](https://www.structlog.org/)
