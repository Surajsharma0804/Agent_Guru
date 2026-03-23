"""
Update Orchestrator for the Guru Deployment System.

Coordinates multi-package updates with transactional semantics:
resolve → verify → snapshot → install → commit/rollback.

Implements mutual exclusion to prevent concurrent transactions (Property 22).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

from .crypto_verifier import CryptoVerifier
from .dependency_resolver import DependencyResolver
from .exceptions import (
    CircularDependencyError,
    DependencyConflictError,
    InstallationError,
    SignatureVerificationError,
    TransactionInProgressError,
    UnsignedPackageError,
)
from .models import (
    AuditLogEntry,
    Configuration,
    OperationType,
    Transaction,
    TransactionResult,
    TransactionState,
)
from .package_manager import PackageManager
from .rollback_manager import RollbackManager

logger = structlog.get_logger(__name__)


class UpdateOrchestrator:
    """
    Coordinates multi-package updates with transactional semantics.

    Execution order per transaction:
    1. Resolve dependencies
    2. Verify signatures
    3. Create rollback snapshot
    4. Install packages in dependency order
    5. Commit (or rollback on failure)
    """

    def __init__(
        self,
        config: Configuration,
        package_manager: PackageManager,
        crypto_verifier: CryptoVerifier,
        dependency_resolver: DependencyResolver,
        rollback_manager: RollbackManager,
    ) -> None:
        self._config = config
        self._pm = package_manager
        self._cv = crypto_verifier
        self._dr = dependency_resolver
        self._rm = rollback_manager
        self._active_transaction: Optional[Transaction] = None
        self._lock = asyncio.Lock()
        self._audit_entries: list[AuditLogEntry] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def begin_update(self, packages: list[tuple[str, str]]) -> Transaction:
        """
        Create a new update transaction.

        Raises:
            TransactionInProgressError: If another transaction is active.
        """
        if self._active_transaction is not None:
            raise TransactionInProgressError(
                f"Transaction '{self._active_transaction.transaction_id}' is already in progress"
            )
        txn = Transaction(
            transaction_id=str(uuid.uuid4()),
            packages=list(packages),
            state=TransactionState.PENDING,
            start_time=datetime.now(timezone.utc),
        )
        self._active_transaction = txn
        logger.info("transaction_started", transaction_id=txn.transaction_id,
                    packages=[p[0] for p in packages])
        return txn

    async def execute_transaction(
        self,
        transaction: Transaction,
        target_env: Path,
        package_paths: Optional[dict[str, Path]] = None,
        signatures: Optional[dict[str, tuple[Optional[bytes], Optional[bytes]]]] = None,
    ) -> TransactionResult:
        """
        Execute an update transaction.

        Args:
            transaction: The transaction to execute.
            target_env: Target Python environment path.
            package_paths: Map of package_name -> local Path (pre-downloaded).
            signatures: Map of package_name -> (signature_bytes, public_key_bytes).

        Returns:
            TransactionResult indicating success or failure.
        """
        async with self._lock:
            return await self._run_transaction(
                transaction, target_env, package_paths or {}, signatures or {}
            )

    def rollback_transaction(self, transaction: Transaction) -> None:
        """Mark transaction as rolled back and clear active transaction."""
        transaction.state = TransactionState.ROLLED_BACK
        transaction.end_time = datetime.now(timezone.utc)
        if self._active_transaction and \
                self._active_transaction.transaction_id == transaction.transaction_id:
            self._active_transaction = None
        logger.info("transaction_rolled_back", transaction_id=transaction.transaction_id)

    def commit_transaction(self, transaction: Transaction) -> None:
        """Commit transaction and clean up rollback snapshot."""
        transaction.state = TransactionState.COMMITTED
        transaction.end_time = datetime.now(timezone.utc)
        if transaction.snapshot_id:
            self._rm.delete_snapshot(transaction.snapshot_id)
        if self._active_transaction and \
                self._active_transaction.transaction_id == transaction.transaction_id:
            self._active_transaction = None
        logger.info("transaction_committed", transaction_id=transaction.transaction_id)

    def get_active_transaction(self) -> Optional[Transaction]:
        """Return the currently active transaction, if any."""
        return self._active_transaction

    def get_audit_entries(self) -> list[AuditLogEntry]:
        """Return in-memory audit entries."""
        return list(self._audit_entries)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _run_transaction(
        self,
        transaction: Transaction,
        target_env: Path,
        package_paths: dict[str, Path],
        signatures: dict[str, tuple[Optional[bytes], Optional[bytes]]],
    ) -> TransactionResult:
        transaction.state = TransactionState.EXECUTING
        installed: list[str] = []

        try:
            # Step 1: Resolve dependencies
            installed_pkgs = self._pm.get_installed_packages(target_env)
            install_order: list[str] = []
            for pkg_name, pkg_version in transaction.packages:
                graph = self._dr.resolve_dependencies(
                    pkg_name, pkg_version, installed_pkgs
                )
                order = self._dr.get_installation_order(graph)
                for p in order:
                    if p not in install_order:
                        install_order.append(p)

            # Step 2: Verify signatures
            for pkg_name, _ in transaction.packages:
                pkg_path = package_paths.get(pkg_name)
                if pkg_path and pkg_path.exists():
                    sig, pub_key = signatures.get(pkg_name, (None, None))
                    self._cv.verify_package_signature(pkg_path, sig, pub_key)

            # Step 3: Create rollback snapshot
            snapshot_id = f"txn_{transaction.transaction_id}"
            self._rm.create_snapshot(snapshot_id, installed_pkgs, target_env)
            transaction.snapshot_id = snapshot_id

            # Step 4: Install packages in dependency order
            pkg_map = dict(transaction.packages)
            for pkg_name in install_order:
                if pkg_name not in pkg_map:
                    continue
                pkg_path = package_paths.get(pkg_name)
                if pkg_path and pkg_path.exists():
                    self._pm.install_package(pkg_path, target_env)
                    installed.append(pkg_name)

            # Step 5: Commit
            self.commit_transaction(transaction)
            self._audit(OperationType.UPDATE, None, "SUCCESS",
                        {"transaction_id": transaction.transaction_id,
                         "installed": installed})
            return TransactionResult(
                success=True,
                transaction_id=transaction.transaction_id,
                installed_packages=installed,
            )

        except (
            DependencyConflictError,
            CircularDependencyError,
            SignatureVerificationError,
            UnsignedPackageError,
            InstallationError,
        ) as exc:
            logger.error("transaction_failed", transaction_id=transaction.transaction_id,
                         error=str(exc))
            # Rollback
            if transaction.snapshot_id:
                try:
                    self._rm.restore_snapshot(transaction.snapshot_id, target_env)
                except Exception as rb_exc:
                    logger.error("rollback_failed", error=str(rb_exc))
            self.rollback_transaction(transaction)
            self._audit(OperationType.UPDATE, None, "FAILURE",
                        {"transaction_id": transaction.transaction_id, "error": str(exc)})
            return TransactionResult(
                success=False,
                transaction_id=transaction.transaction_id,
                installed_packages=installed,
                error=str(exc),
                rollback_performed=bool(transaction.snapshot_id),
            )
        finally:
            if self._active_transaction and \
                    self._active_transaction.transaction_id == transaction.transaction_id:
                self._active_transaction = None

    def _audit(
        self,
        operation: OperationType,
        package_name: Optional[str],
        result: str,
        details: dict,
    ) -> None:
        self._audit_entries.append(
            AuditLogEntry(
                timestamp=datetime.now(timezone.utc),
                operation=operation,
                result=result,
                package_name=package_name,
                details=details,
            )
        )
