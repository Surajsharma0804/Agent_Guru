"""
Custom exceptions for the Guru Deployment System.
"""


class DeploymentError(Exception):
    """Base exception for all deployment errors."""


class NetworkError(DeploymentError):
    """Network operation failed."""


class PackageNotFoundError(DeploymentError):
    """Package not found in any repository."""


class InstallationError(DeploymentError):
    """Package installation failed."""


class InvalidKeyError(DeploymentError):
    """Cryptographic key is invalid."""


class KeyNotFoundError(DeploymentError):
    """Key not found in trust store."""


class SignatureVerificationError(DeploymentError):
    """Package signature verification failed."""


class UnsignedPackageError(DeploymentError):
    """Package has no signature and policy requires signatures."""


class DependencyConflictError(DeploymentError):
    """Version conflict in dependency resolution."""


class CircularDependencyError(DeploymentError):
    """Circular dependency detected."""


class SnapshotNotFoundError(DeploymentError):
    """Snapshot not found."""


class RestoreError(DeploymentError):
    """Snapshot restore failed."""


class InsufficientSpaceError(DeploymentError):
    """Insufficient disk space."""


class TransactionInProgressError(DeploymentError):
    """Another transaction is already in progress."""


class RepositoryError(DeploymentError):
    """Repository operation failed."""


class ConfigurationError(DeploymentError):
    """Invalid configuration."""
