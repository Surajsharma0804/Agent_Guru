"""Cryptographic verification for the Guru Deployment System.

Verifies package signatures using Ed25519 and maintains a trust store.
All verification failures are logged to the audit log.

Time Complexity: O(n) for file hashing (n = file size in chunks)
Space Complexity: O(1) streaming verification
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_der_public_key

from .exceptions import (
    InvalidKeyError,
    KeyNotFoundError,
    SignatureVerificationError,
    UnsignedPackageError,
)
from .models import AuditLogEntry, Configuration, OperationType, TrustedKey, VerificationPolicy

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

logger = structlog.get_logger(__name__)

_CHUNK_SIZE = 65536  # 64 KB chunks for streaming


class CryptoVerifier:
    """Verifies cryptographic signatures of packages using Ed25519.

    Trust store is persisted in SQLite. All verification events are
    logged to the audit log for security traceability.
    """

    def __init__(self, config: Configuration, db_path: Path | None = None) -> None:
        self._config = config
        self._db_path = db_path or (config.cache_dir / "trust_store.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._audit_entries: list[AuditLogEntry] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify_package_signature(
        self,
        package_path: Path,
        signature: bytes | None,
        public_key: bytes | None,
    ) -> bool:
        """Verify package signature using Ed25519.

        Args:
            package_path: Path to the package file.
            signature: Raw Ed25519 signature bytes, or None if unsigned.
            public_key: DER-encoded Ed25519 public key bytes, or None.

        Returns:
            True if signature is valid.

        Raises:
            UnsignedPackageError: If package is unsigned and policy is STRICT.
            SignatureVerificationError: If signature is invalid.

        """
        if signature is None or public_key is None:
            if self._config.verification_policy == VerificationPolicy.STRICT:
                self._audit(
                    OperationType.VERIFY,
                    str(package_path.name),
                    "FAILURE",
                    {"reason": "unsigned_package"},
                )
                msg = f"Package '{package_path.name}' has no signature and policy is STRICT"
                raise UnsignedPackageError(
                    msg,
                )
            logger.warning("unsigned_package_allowed", package=str(package_path.name))
            return True

        pkg_hash = self.compute_package_hash(package_path)

        try:
            key_obj = self._load_ed25519_key(public_key)
            key_obj.verify(signature, pkg_hash)
        except (InvalidSignature, Exception) as exc:
            self._audit(
                OperationType.VERIFY,
                str(package_path.name),
                "FAILURE",
                {"reason": str(exc)},
            )
            msg = f"Signature verification failed for '{package_path.name}': {exc}"
            raise SignatureVerificationError(
                msg,
            ) from exc

        self._audit(OperationType.VERIFY, str(package_path.name), "SUCCESS", {})
        logger.info("signature_verified", package=str(package_path.name))
        return True

    def add_trusted_key(
        self,
        key_id: str,
        public_key: bytes,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Add a public key to the trust store.

        Raises:
            InvalidKeyError: If key is not a valid Ed25519 key.

        """
        if not key_id or not key_id.strip():
            msg = "key_id must not be empty"
            raise InvalidKeyError(msg)
        try:
            self._load_ed25519_key(public_key)
        except Exception as exc:
            msg = f"Invalid Ed25519 key: {exc}"
            raise InvalidKeyError(msg) from exc

        now = datetime.now(UTC)
        meta_json = json.dumps(metadata or {})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO trusted_keys
                    (key_id, public_key, owner, added_timestamp, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    key_id,
                    public_key,
                    metadata.get("owner", "") if metadata else "",
                    now.isoformat(),
                    meta_json,
                ),
            )
        logger.info("trusted_key_added", key_id=key_id)

    def remove_trusted_key(self, key_id: str) -> None:
        """Remove a key from the trust store.

        Raises:
            KeyNotFoundError: If key does not exist.

        """
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM trusted_keys WHERE key_id = ?", (key_id,))
            if cur.rowcount == 0:
                msg = f"Key '{key_id}' not found in trust store"
                raise KeyNotFoundError(msg)
        logger.info("trusted_key_removed", key_id=key_id)

    def get_trusted_keys(self) -> list[TrustedKey]:
        """Return all trusted keys."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key_id, public_key, owner, added_timestamp, metadata FROM trusted_keys",
            ).fetchall()
        keys = []
        for row in rows:
            meta = json.loads(row[4]) if row[4] else {}
            keys.append(
                TrustedKey(
                    key_id=row[0],
                    public_key=row[1],
                    owner=row[2],
                    added_timestamp=datetime.fromisoformat(row[3]),
                    metadata=meta,
                ),
            )
        return keys

    def compute_package_hash(self, package_path: Path) -> bytes:
        """Compute SHA-256 hash of a package file using streaming.

        Space Complexity: O(1) - processes in 64 KB chunks.

        Raises:
            ValueError: If package_path resolves outside the configured cache_dir.

        """
        base = self._config.cache_dir.resolve()
        resolved = package_path.resolve()
        if not resolved.is_relative_to(base):
            msg = f"Package path '{package_path}' resolves outside allowed cache directory '{base}'"
            raise ValueError(
                msg,
            )
        hasher = hashlib.sha256()
        with resolved.open("rb") as fh:
            while chunk := fh.read(_CHUNK_SIZE):
                hasher.update(chunk)
        return hasher.digest()

    def get_audit_entries(self) -> list[AuditLogEntry]:
        """Return in-memory audit entries (for testing/inspection)."""
        return list(self._audit_entries)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_ed25519_key(self, public_key: bytes) -> Ed25519PublicKey:
        """Load and validate an Ed25519 public key from DER bytes."""
        try:
            key = load_der_public_key(public_key)
            if not isinstance(key, Ed25519PublicKey):
                msg = "Key is not an Ed25519 public key"
                raise InvalidKeyError(msg)
            return key
        except Exception as exc:
            msg = f"Failed to load key: {exc}"
            raise InvalidKeyError(msg) from exc

    def _audit(
        self,
        operation: OperationType,
        package_name: str,
        result: str,
        details: dict,
    ) -> None:
        entry = AuditLogEntry(
            timestamp=datetime.now(UTC),
            operation=operation,
            result=result,
            package_name=package_name,
            details=details,
        )
        self._audit_entries.append(entry)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trusted_keys (
                    key_id TEXT PRIMARY KEY,
                    public_key BLOB NOT NULL,
                    owner TEXT NOT NULL,
                    added_timestamp TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
                """,
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a SQLite connection, committing on success and rolling back
        on failure, and guaranteeing closure either way.

        BUG FIX (Round 10): this previously only wrapped the connection in
        contextlib.closing(), which guarantees close() but NOT commit().
        Python's sqlite3 connections do not auto-commit on close() -- per
        the standard library's own documentation, closing a connection
        with uncommitted changes discards them. That meant every
        add_trusted_key() / remove_trusted_key() call (both of which use
        this method and never called commit() themselves) appeared to
        succeed -- it logged "trusted_key_added", raised no exception --
        but the INSERT/DELETE was silently rolled back the moment the
        connection closed. The trust store was, in effect, write-only in
        memory for the lifetime of a single call and empty on every
        subsequent read: confirmed by a real round-trip test (add a key,
        immediately call get_trusted_keys()) returning an empty list. Fixed
        at the root -- in this shared connection helper -- rather than
        patching each call site, so any future caller of _connect() gets
        correct commit/rollback semantics for free.
        """
        conn = sqlite3.connect(str(self._db_path))
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
