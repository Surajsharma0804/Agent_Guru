"""
Guru Deployment System - Secure package management with cryptographic verification.

This package provides a secure, transactional package management system built on top
of Python's packaging ecosystem with cryptographic verification, atomic updates,
and intelligent dependency resolution.
"""

__version__ = "0.1.0"

from guru_deployment.exceptions import (
    DeploymentError,
    PackageNotFoundError,
    InstallationError,
    NetworkError,
    ChecksumError,
    SignatureError,
    DependencyConflictError,
    CircularDependencyError,
    InsufficientSpaceError,
    SnapshotNotFoundError,
    RestoreError,
    TransactionError,
)

__all__ = [
    "DeploymentError",
    "PackageNotFoundError",
    "InstallationError",
    "NetworkError",
    "ChecksumError",
    "SignatureError",
    "DependencyConflictError",
    "CircularDependencyError",
    "InsufficientSpaceError",
    "SnapshotNotFoundError",
    "RestoreError",
    "TransactionError",
]
