"""Agent Guru - Deployment System.

Professional package management, installer creation, onboarding,
and auto-update for AGENT_GURU.
"""

from .crypto_verifier import CryptoVerifier
from .dependency_resolver import DependencyResolver
from .exceptions import (
    CircularDependencyError,
    ConfigurationError,
    DependencyConflictError,
    DeploymentError,
    InstallationError,
    InvalidKeyError,
    KeyNotFoundError,
    NetworkError,
    PackageNotFoundError,
    RestoreError,
    SignatureVerificationError,
    SnapshotNotFoundError,
    TransactionInProgressError,
    UnsignedPackageError,
)
from .installer_builder import (
    AndroidBuildConfig,
    InstallerBuilder,
    IOSBuildConfig,
    LinuxPackageConfig,
    MacOSInstallerConfig,
    WindowsInstallerConfig,
)
from .models import (
    AuditLogEntry,
    Configuration,
    Conflict,
    DependencyGraph,
    OperationType,
    PackageInfo,
    PackageNode,
    RepositoryConfig,
    RetentionPolicy,
    Snapshot,
    Transaction,
    TransactionResult,
    TransactionState,
    TrustedKey,
    VerificationPolicy,
)
from .onboarding import (
    LLMConfig,
    OnboardingManager,
    OnboardingState,
    OnboardingStep,
    UserProfile,
)
from .package_manager import PackageManager
from .rollback_manager import RollbackManager
from .update_manager import UpdateInfo, UpdateManager
from .update_orchestrator import UpdateOrchestrator

__version__ = "1.0.0"

__all__ = [
    "AndroidBuildConfig",
    "AuditLogEntry",
    "CircularDependencyError",
    # Models
    "Configuration",
    "ConfigurationError",
    "Conflict",
    "CryptoVerifier",
    "DependencyConflictError",
    "DependencyGraph",
    "DependencyResolver",
    # Exceptions
    "DeploymentError",
    "IOSBuildConfig",
    "InstallationError",
    "InstallerBuilder",
    "InvalidKeyError",
    "KeyNotFoundError",
    "LLMConfig",
    "LinuxPackageConfig",
    "MacOSInstallerConfig",
    "NetworkError",
    "OnboardingManager",
    # Onboarding
    "OnboardingManager",
    "OnboardingState",
    "OnboardingStep",
    "OperationType",
    "PackageInfo",
    # Core components
    "PackageManager",
    "PackageNode",
    "PackageNotFoundError",
    "RepositoryConfig",
    "RestoreError",
    "RetentionPolicy",
    "RollbackManager",
    "SignatureVerificationError",
    "Snapshot",
    "SnapshotNotFoundError",
    "Transaction",
    "TransactionInProgressError",
    "TransactionResult",
    "TransactionState",
    "TrustedKey",
    "UnsignedPackageError",
    "UpdateInfo",
    "UpdateManager",
    "UpdateOrchestrator",
    "UserProfile",
    "VerificationPolicy",
    # Installer configs
    "WindowsInstallerConfig",
]
