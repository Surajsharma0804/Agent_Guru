"""
Exception classes for the Guru Deployment System.

All exceptions follow a consistent hierarchy and include context information
for debugging and error reporting.
"""

from typing import Optional, Dict, Any


class DeploymentError(Exception):
    """Base exception for all deployment system errors."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize deployment error.
        
        Args:
            message: Human-readable error message
            context: Additional context information (package name, version, etc.)
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}
    
    def __str__(self) -> str:
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message


class PackageNotFoundError(DeploymentError):
    """Raised when a package cannot be found in any repository."""
    pass


class InstallationError(DeploymentError):
    """Raised when package installation fails."""
    pass


class NetworkError(DeploymentError):
    """Raised when network operations fail."""
    pass


class ChecksumError(DeploymentError):
    """Raised when package checksum verification fails."""
    pass


class SignatureError(DeploymentError):
    """Raised when cryptographic signature verification fails."""
    pass


class DependencyConflictError(DeploymentError):
    """Raised when package dependencies have version conflicts."""
    pass


class CircularDependencyError(DeploymentError):
    """Raised when circular dependencies are detected."""
    pass


class InsufficientSpaceError(DeploymentError):
    """Raised when insufficient disk space is available."""
    pass


class SnapshotNotFoundError(DeploymentError):
    """Raised when a snapshot cannot be found."""
    pass


class RestoreError(DeploymentError):
    """Raised when snapshot restore operation fails."""
    pass


class TransactionError(DeploymentError):
    """Raised when transaction operations fail."""
    pass
