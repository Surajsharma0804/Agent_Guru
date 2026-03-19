"""
Data models for the Guru Deployment System.

All models use Pydantic for validation and dataclasses for lightweight structures.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class TransactionState(str, enum.Enum):
    """State of an update transaction."""

    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


class OperationType(str, enum.Enum):
    """Type of deployment operation for audit logging."""

    INSTALL = "INSTALL"
    REMOVE = "REMOVE"
    UPDATE = "UPDATE"
    VERIFY = "VERIFY"
    ROLLBACK = "ROLLBACK"
    SNAPSHOT = "SNAPSHOT"
    DOWNLOAD = "DOWNLOAD"


class VerificationPolicy(str, enum.Enum):
    """Package signature verification policy."""

    STRICT = "STRICT"       # All packages must be signed
    PERMISSIVE = "PERMISSIVE"  # Unsigned packages allowed with warning
    DISABLED = "DISABLED"   # No verification


@dataclass
class PackageInfo:
    """Information about an installed package."""

    name: str
    version: str
    install_path: Path
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    install_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    checksum: str = ""


@dataclass
class PackageNode:
    """Node in the dependency graph."""

    name: str
    version: str
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DependencyGraph:
    """Directed acyclic graph of package dependencies."""

    nodes: Dict[str, PackageNode] = field(default_factory=dict)
    edges: List[Tuple[str, str]] = field(default_factory=list)

    def has_cycle(self) -> bool:
        """Detect cycles using DFS with coloring (white=0, gray=1, black=2)."""
        color: Dict[str, int] = {n: 0 for n in self.nodes}
        adj: Dict[str, List[str]] = {n: [] for n in self.nodes}
        for src, dst in self.edges:
            if dst in adj:
                adj[src].append(dst)

        def dfs(node: str) -> bool:
            color[node] = 1
            for neighbor in adj.get(node, []):
                if color.get(neighbor, 0) == 1:
                    return True
                if color.get(neighbor, 0) == 0 and dfs(neighbor):
                    return True
            color[node] = 2
            return False

        return any(dfs(n) for n in self.nodes if color[n] == 0)

    def topological_sort(self) -> List[str]:
        """Return packages in installation order (dependencies first)."""
        if self.has_cycle():
            raise ValueError("Dependency graph contains a cycle")

        # Build adjacency: src -> [dst] where edge (src, dst) means src depends on dst
        adj: Dict[str, List[str]] = {n: [] for n in self.nodes}
        for src, dst in self.edges:
            if dst in adj:
                adj[src].append(dst)

        visited: set[str] = set()
        order: List[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            for dep in adj.get(node, []):
                if dep not in visited:
                    dfs(dep)
            order.append(node)

        for node in self.nodes:
            if node not in visited:
                dfs(node)

        # order is post-order: dependencies appended before their dependents
        # So order already has deps first — no reversal needed
        return order


@dataclass
class Conflict:
    """A version conflict between packages."""

    package_name: str
    required_versions: List[str] = field(default_factory=list)
    required_by: List[str] = field(default_factory=list)


@dataclass
class TrustedKey:
    """A trusted public key in the trust store."""

    key_id: str
    public_key: bytes
    owner: str
    added_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expiry: Optional[datetime] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class Snapshot:
    """A snapshot of the system state for rollback."""

    snapshot_id: str
    timestamp: datetime
    packages: List[PackageInfo] = field(default_factory=list)
    registry_state: bytes = b""
    storage_path: Path = field(default_factory=lambda: Path("."))
    size_bytes: int = 0


@dataclass
class Transaction:
    """An atomic update transaction."""

    transaction_id: str
    packages: List[Tuple[str, str]] = field(default_factory=list)
    snapshot_id: str = ""
    state: TransactionState = TransactionState.PENDING
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None


@dataclass
class TransactionResult:
    """Result of executing a transaction."""

    success: bool
    transaction_id: str
    installed_packages: List[str] = field(default_factory=list)
    error: Optional[str] = None
    rollback_performed: bool = False


@dataclass
class AuditLogEntry:
    """An entry in the tamper-evident audit log."""

    timestamp: datetime
    operation: OperationType
    result: str  # SUCCESS or FAILURE
    package_name: Optional[str] = None
    version: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    user: str = "system"
    entry_hash: str = ""  # SHA-256 of previous entry + this entry content


@dataclass
class RepositoryConfig:
    """Configuration for a package repository."""

    name: str
    url: str
    priority: int = 0
    verify_ssl: bool = True
    credentials: Optional[Tuple[str, str]] = None


@dataclass
class RetentionPolicy:
    """Policy for pruning old snapshots."""

    max_snapshots: int = 10
    max_age_days: int = 30


@dataclass
class Configuration:
    """Deployment system configuration."""

    repositories: List[RepositoryConfig] = field(default_factory=list)
    verification_policy: VerificationPolicy = VerificationPolicy.STRICT
    rollback_retention: RetentionPolicy = field(default_factory=RetentionPolicy)
    network_timeout: int = 30
    max_retries: int = 3
    cache_dir: Path = field(default_factory=lambda: Path(".guru/cache"))
    log_level: str = "INFO"
    require_platform_validation: bool = True
    require_permission_checks: bool = True
    require_space_checks: bool = True
    min_free_space_gb: float = 1.0
