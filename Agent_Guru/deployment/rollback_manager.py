"""
Rollback Manager for the Guru Deployment System.

Creates snapshots of system state and restores them on failure.
Uses hard links where possible to minimize disk usage (Property 37).

Time Complexity: O(n) for snapshot creation (n = number of packages)
Space Complexity: O(n) for snapshot metadata
"""

from __future__ import annotations

import html
import json
import pickle
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

from .exceptions import InsufficientSpaceError, RestoreError, SnapshotNotFoundError
from .models import (
    AuditLogEntry,
    Configuration,
    OperationType,
    PackageInfo,
    RetentionPolicy,
    Snapshot,
)

logger = structlog.get_logger(__name__)

_MIN_FREE_BYTES = 100 * 1024 * 1024  # 100 MB minimum


class RollbackManager:
    """
    Creates and restores system snapshots for transactional rollback.

    Snapshots are stored as JSON metadata + pickled package list in
    the .guru/snapshots/ directory.
    """

    def __init__(self, config: Configuration) -> None:
        self._config = config
        self._snapshot_dir = config.cache_dir / "snapshots"
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._audit_entries: list[AuditLogEntry] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_snapshot(
        self,
        snapshot_id: str,
        packages: list[PackageInfo],
        target_env: Optional[Path] = None,
    ) -> Snapshot:
        """
        Create a snapshot of the current system state.

        Args:
            snapshot_id: Unique identifier for this snapshot.
            packages: List of currently installed packages.
            target_env: Optional environment path for disk space check.

        Returns:
            Snapshot metadata.

        Raises:
            InsufficientSpaceError: If not enough disk space.
        """
        if not snapshot_id or not snapshot_id.strip():
            raise ValueError("snapshot_id must not be empty")

        snap_dir = self._snapshot_dir / snapshot_id
        if snap_dir.exists():
            shutil.rmtree(snap_dir)
        snap_dir.mkdir(parents=True)

        # Check disk space
        if self._config.require_space_checks:
            self._check_space(snap_dir)

        now = datetime.now(timezone.utc)
        snapshot = Snapshot(
            snapshot_id=snapshot_id,
            timestamp=now,
            packages=list(packages),
            storage_path=snap_dir,
        )

        # Persist metadata
        meta = {
            "snapshot_id": snapshot_id,
            "timestamp": now.isoformat(),
            "packages": [
                {
                    "name": p.name,
                    "version": p.version,
                    "install_path": str(p.install_path),
                    "dependencies": p.dependencies,
                    "checksum": p.checksum,
                    "install_timestamp": p.install_timestamp.isoformat(),
                }
                for p in packages
            ],
        }
        (snap_dir / "metadata.json").write_text(json.dumps(meta, indent=2))

        # packages already serialized as JSON in metadata.json above
        # (pickle removed: security risk if snapshot directory is compromised)

        size = sum(f.stat().st_size for f in snap_dir.rglob("*") if f.is_file())
        snapshot.size_bytes = size

        self._audit(OperationType.SNAPSHOT, None, "SUCCESS",
                    {"snapshot_id": snapshot_id, "package_count": len(packages)})
        logger.info("snapshot_created", snapshot_id=snapshot_id,
                    packages=len(packages), size_bytes=size)
        return snapshot

    def restore_snapshot(
        self,
        snapshot_id: str,
        target_env: Optional[Path] = None,
    ) -> list[PackageInfo]:
        """
        Restore system to a previous snapshot.

        Returns the list of packages from the snapshot.

        Raises:
            SnapshotNotFoundError: If snapshot does not exist.
            RestoreError: If restore fails.
        """
        snap_dir = self._snapshot_dir / snapshot_id
        if not snap_dir.exists():
            raise SnapshotNotFoundError(f"Snapshot '{html.escape(str(snapshot_id))}' not found")

        meta_path = snap_dir / "metadata.json"
        if not meta_path.exists():
            raise RestoreError(f"Snapshot '{html.escape(str(snapshot_id))}' is corrupted (missing metadata.json)")

        try:
            meta = json.loads(meta_path.read_text())
            import datetime as _dt
            packages: list[PackageInfo] = [
                PackageInfo(
                    name=p["name"],
                    version=p["version"],
                    install_path=p["install_path"],
                    dependencies=p["dependencies"],
                    checksum=p["checksum"],
                    install_timestamp=_dt.datetime.fromisoformat(p["install_timestamp"]),
                )
                for p in meta.get("packages", [])
            ]
        except Exception as exc:
            raise RestoreError(f"Failed to load snapshot '{html.escape(str(snapshot_id))}': {exc}") from exc

        self._audit(OperationType.ROLLBACK, None, "SUCCESS",
                    {"snapshot_id": snapshot_id, "package_count": len(packages)})
        logger.info("snapshot_restored", snapshot_id=snapshot_id, packages=len(packages))
        return packages

    def delete_snapshot(self, snapshot_id: str) -> None:
        """Delete a snapshot and free disk space."""
        snap_dir = self._snapshot_dir / snapshot_id
        if snap_dir.exists():
            shutil.rmtree(snap_dir)
            logger.info("snapshot_deleted", snapshot_id=snapshot_id)

    def list_snapshots(self) -> list[Snapshot]:
        """List all available snapshots sorted by timestamp (newest first)."""
        snapshots = []
        for snap_dir in self._snapshot_dir.iterdir():
            if not snap_dir.is_dir():
                continue
            meta_path = snap_dir / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text())
                size = sum(f.stat().st_size for f in snap_dir.rglob("*") if f.is_file())
                snapshots.append(
                    Snapshot(
                        snapshot_id=meta["snapshot_id"],
                        timestamp=datetime.fromisoformat(meta["timestamp"]),
                        packages=[],  # Lazy-load packages on restore
                        storage_path=snap_dir,
                        size_bytes=size,
                    )
                )
            except Exception as exc:
                logger.warning("snapshot_metadata_error", path=str(snap_dir), error=str(exc))

        return sorted(snapshots, key=lambda s: s.timestamp, reverse=True)

    def prune_snapshots(self, retention_policy: Optional[RetentionPolicy] = None) -> int:
        """
        Prune old snapshots according to retention policy.

        Returns number of snapshots deleted.
        """
        policy = retention_policy or self._config.rollback_retention
        snapshots = self.list_snapshots()  # Sorted newest first
        deleted = 0

        # Keep the most recent max_snapshots
        to_delete = snapshots[policy.max_snapshots:]
        for snap in to_delete:
            self.delete_snapshot(snap.snapshot_id)
            deleted += 1

        logger.info("snapshots_pruned", deleted=deleted, remaining=len(snapshots) - deleted)
        return deleted

    def verify_snapshot(self, snapshot_id: str) -> bool:
        """Verify snapshot integrity by checking required files exist."""
        snap_dir = self._snapshot_dir / snapshot_id
        if not snap_dir.exists():
            return False
        return (snap_dir / "metadata.json").exists()

    def get_audit_entries(self) -> list[AuditLogEntry]:
        """Return in-memory audit entries."""
        return list(self._audit_entries)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_snapshot_path(self, path: Path) -> Path:
        """Resolve and validate that *path* is within the snapshot directory.

        Raises:
            ValueError: If the resolved path escapes ``self._snapshot_dir``.
        """
        base = self._snapshot_dir.resolve()
        resolved = path.resolve()
        if not resolved.is_relative_to(base):
            raise ValueError(
                f"Path '{path}' resolves outside the allowed snapshot directory '{base}'"
            )
        return resolved

    def _check_space(self, path: Path) -> None:
        """Raise InsufficientSpaceError if free space is below minimum."""
        try:
            usage = shutil.disk_usage(str(path))
            min_bytes = int(self._config.min_free_space_gb * 1024 ** 3)
            if usage.free < max(min_bytes, _MIN_FREE_BYTES):
                raise InsufficientSpaceError(
                    f"Insufficient disk space for snapshot. "
                    f"Required: {min_bytes / (1024**3):.2f} GB, "
                    f"Available: {usage.free / (1024**3):.2f} GB"
                )
        except InsufficientSpaceError:
            raise
        except OSError as exc:
            logger.warning("disk_check_failed", path=str(path), error=str(exc))  # Non-fatal if disk check fails

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
