"""Secure key storage with AES-256-GCM encryption and PBKDF2 key derivation.

Keys are encrypted at rest using AES-256-GCM. The encryption key is derived
from a master password using PBKDF2 with 100,000+ iterations.

Storage backend: SQLite (in-memory or file-based).
"""

from __future__ import annotations

import contextlib
import logging
import os
import sqlite3
import threading
from datetime import UTC, datetime

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from Agent_Guru.security.crypto.errors import KeyNotFoundError, KeyStorageError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# KDF parameters
# ---------------------------------------------------------------------------
# WORK-FACTOR FIX: this was pinned at 100,000 PBKDF2-HMAC-SHA256 iterations,
# which was the guidance around 2021. OWASP's Password Storage Cheat Sheet
# currently specifies 600,000 iterations for PBKDF2-HMAC-SHA256, so the store
# was running at one sixth of the recommended work factor against an offline
# attacker who has the file (exactly the attacker this class exists to slow
# down).
#
# Raising a KDF parameter is not a one-line change, because the derived key IS
# the decryption key: bumping the constant on its own would have made every
# existing store silently undecryptable, reported only as "Failed to decrypt
# key". The parameters are therefore now PERSISTED with the store, so each
# store re-derives with whatever it was actually created with, and
# upgrade_kdf() migrates an old store forward when the caller can supply the
# master password.
#
# Not Argon2id (which OWASP ranks above PBKDF2): `cryptography` only exposes
# Argon2id from 44.0 with OpenSSL 3.2+, and this project's dependency floor is
# cryptography>=41.0.0. A store encrypted with a KDF the user's own install
# cannot provide would be unopenable on a supported configuration -- a worse
# outcome than a lower work factor. The kdf_algorithm field below is recorded
# so that switch becomes a migration rather than a breaking change once the
# floor is raised.
_KDF_ALGORITHM = "pbkdf2-hmac-sha256"
_KDF_ITERATIONS = 600_000

# Stores created before the parameters were recorded used this, implicitly.
_LEGACY_KDF_ITERATIONS = 100_000

_KDF_SALT_SIZE = 32
_AES_KEY_SIZE = 32  # 256 bits
_NONCE_SIZE = 12  # 96 bits for AES-GCM


class KeyStore:
    """Encrypted key storage using AES-256-GCM.

    Keys are encrypted before storage and decrypted only in memory.
    The encryption key is derived from a master password using PBKDF2.

    Args:
        storage_path: Path to SQLite database, or ":memory:" for in-memory.
        master_password: Password used to derive the encryption key.

    """

    def __init__(self, storage_path: str = ":memory:", master_password: str = "") -> None:  # nosec B107
        self._storage_path = storage_path
        self._conn = sqlite3.connect(storage_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # check_same_thread=False only disables sqlite3's own cross-thread
        # check, it doesn't make the connection itself safe for concurrent
        # use from multiple real threads — this lock serializes every
        # operation against self._conn (same fix applied to AuditLogger and
        # TrustManager this round, and to memory/github_sync.py last round).
        self._lock = threading.Lock()
        self._init_schema()

        # Derive or load encryption key using the parameters this store was
        # actually created with (see the _KDF_ITERATIONS comment).
        self._salt, self._kdf_iterations = self._get_or_create_kdf_params()
        self._encryption_key = self._derive_encryption_key(
            master_password, self._salt, self._kdf_iterations,
        )

        if self._kdf_iterations < _KDF_ITERATIONS:
            logger.info(
                "KeyStore(storage_path=%r) was created with %d PBKDF2 "
                "iterations; the current recommended work factor is %d. "
                "Call upgrade_kdf(master_password) to re-encrypt this store "
                "at the higher factor.",
                storage_path,
                self._kdf_iterations,
                _KDF_ITERATIONS,
            )

        if not master_password:
            # An empty master_password derives the encryption key from a
            # well-known constant (b"") plus a salt that is itself stored,
            # unencrypted, in this same database's metadata table — anyone
            # with read access to storage_path can reproduce the exact same
            # encryption key and read every "encrypted at rest" key this
            # store holds. This may be a deliberate choice when a caller
            # layers its own protection (e.g. full-disk encryption, a
            # hardware-backed keyring) on top, so it isn't refused outright
            # — but it silently defeats this class's own stated security
            # property ("Keys are encrypted at rest"), so make that visible
            # instead of letting it pass unnoticed.
            logger.warning(
                "KeyStore(storage_path=%r) created with an empty "
                "master_password: encryption-at-rest for this store "
                "provides no real protection against anyone who can read "
                "%r directly, since the derivation salt is stored "
                "alongside the encrypted keys in the same file.",
                storage_path,
                storage_path,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def kdf_iterations(self) -> int:
        """PBKDF2 iteration count this store's encryption key was derived with."""
        return self._kdf_iterations

    def upgrade_kdf(self, master_password: str, iterations: int = _KDF_ITERATIONS) -> bool:
        """Re-encrypt every stored key at a higher KDF work factor.

        A store created under the old 100,000-iteration default keeps working
        forever otherwise, because its parameters are recorded -- which is
        correct, but leaves it at the weaker factor. This migrates it.

        Every key is decrypted with the current key, re-encrypted under the
        newly derived one with a fresh nonce, and written inside a single
        transaction together with the new parameters, so an interruption
        leaves the store exactly as it was rather than half-migrated and
        unreadable.

        Args:
            master_password: The same password this store was opened with.
                It is verified against the existing key material first.
            iterations: Target iteration count (defaults to the current
                recommendation).

        Returns:
            True if the store was migrated, False if it was already at or
            above *iterations*.

        Raises:
            KeyStorageError: If the password does not match, or migration fails.

        """
        if iterations <= self._kdf_iterations:
            return False

        # Verify the caller really has this store's password before touching
        # anything: deriving from a wrong password would "succeed" and then
        # re-encrypt every key under a key nobody can reproduce.
        check = self._derive_encryption_key(master_password, self._salt, self._kdf_iterations)
        if check != self._encryption_key:
            msg = "master_password does not match the one this store was opened with"
            raise KeyStorageError(msg)

        new_salt = os.urandom(_KDF_SALT_SIZE)
        new_key = self._derive_encryption_key(master_password, new_salt, iterations)
        old_aes = AESGCM(self._encryption_key)
        new_aes = AESGCM(new_key)

        try:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT key_id, encrypted_key, nonce FROM keys",
                ).fetchall()

                reencrypted = []
                for row in rows:
                    key_id = row["key_id"]
                    plain = old_aes.decrypt(
                        bytes(row["nonce"]), bytes(row["encrypted_key"]), key_id.encode(),
                    )
                    nonce = os.urandom(_NONCE_SIZE)
                    reencrypted.append(
                        (new_aes.encrypt(nonce, plain, key_id.encode()), nonce, key_id),
                    )

                with self._conn:
                    self._conn.executemany(
                        "UPDATE keys SET encrypted_key = ?, nonce = ? WHERE key_id = ?",
                        reencrypted,
                    )
                    self._conn.execute(
                        "INSERT OR REPLACE INTO metadata (key, value) VALUES ('kdf_salt', ?)",
                        (new_salt,),
                    )
                    self._conn.execute(
                        "INSERT OR REPLACE INTO metadata (key, value) VALUES "
                        "('kdf_iterations', ?)",
                        (str(iterations).encode(),),
                    )
        except Exception as exc:
            msg = f"Failed to upgrade KDF: type={type(exc).__name__}"
            raise KeyStorageError(msg) from exc

        self._salt = new_salt
        self._kdf_iterations = iterations
        self._encryption_key = new_key
        logger.info(
            "KeyStore(storage_path=%r) re-encrypted %d key(s) at %d PBKDF2 iterations",
            self._storage_path,
            len(rows),
            iterations,
        )
        return True

    def store_key(self, key_id: str, key_material: bytes) -> None:
        """Store key encrypted with AES-256-GCM.

        Args:
            key_id: Unique identifier for the key.
            key_material: Key bytes to store.

        Raises:
            KeyStorageError: If encryption or storage fails.

        """
        try:
            nonce = os.urandom(_NONCE_SIZE)
            aesgcm = AESGCM(self._encryption_key)
            encrypted = aesgcm.encrypt(nonce, key_material, key_id.encode())

            with self._lock, self._conn:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO keys (key_id, encrypted_key, nonce, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (key_id, encrypted, nonce, datetime.now(tz=UTC).isoformat()),
                )
        except Exception as exc:
            msg = f"Failed to store key: type={type(exc).__name__}"
            raise KeyStorageError(msg) from exc

    def retrieve_key(self, key_id: str) -> bytes:
        """Retrieve and decrypt key.

        The key is decrypted in memory only, never written to disk.

        Args:
            key_id: Key identifier.

        Returns:
            Decrypted key material.

        Raises:
            KeyNotFoundError: If key doesn't exist.
            KeyStorageError: If decryption fails.

        """
        with self._lock:
            row = self._conn.execute(
                "SELECT encrypted_key, nonce FROM keys WHERE key_id = ?",
                (key_id,),
            ).fetchone()

        if row is None:
            msg = "Key not found"
            raise KeyNotFoundError(msg)

        try:
            aesgcm = AESGCM(self._encryption_key)
            return aesgcm.decrypt(
                bytes(row["nonce"]),
                bytes(row["encrypted_key"]),
                key_id.encode(),
            )
        except Exception as exc:
            msg = f"Failed to decrypt key: type={type(exc).__name__}"
            raise KeyStorageError(msg) from exc

    def delete_key(self, key_id: str) -> None:
        """Securely delete key.

        Args:
            key_id: Key to delete.

        Raises:
            KeyNotFoundError: If key doesn't exist.

        """
        with self._lock:
            cursor = self._conn.execute("SELECT COUNT(*) FROM keys WHERE key_id = ?", (key_id,))
            if cursor.fetchone()[0] == 0:
                msg = "Key not found"
                raise KeyNotFoundError(msg)

            with self._conn:
                self._conn.execute("DELETE FROM keys WHERE key_id = ?", (key_id,))

    def key_exists(self, key_id: str) -> bool:
        """Check if a key exists."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM keys WHERE key_id = ?", (key_id,),
            ).fetchone()
        return row[0] > 0

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            self._conn.close()

    def __del__(self) -> None:
        """Ensure connection is closed when object is garbage-collected."""
        with contextlib.suppress(Exception):
            self._conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS keys (
                    key_id TEXT PRIMARY KEY,
                    encrypted_key BLOB NOT NULL,
                    nonce BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    deprecated_at TEXT
                )
                """,
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value BLOB NOT NULL
                )
                """,
            )

    def _get_or_create_kdf_params(self) -> tuple[bytes, int]:
        """Return this store's (salt, iterations), creating them if new.

        The iteration count is persisted so the store is self-describing. A
        store written before that was recorded is, by definition, a store
        created under the old default, so it is read as such and the value is
        written back -- after which the parameter is explicit rather than
        implied by whatever the constant happened to be at import time.
        """
        with self._lock:
            rows = {
                row["key"]: bytes(row["value"])
                for row in self._conn.execute(
                    "SELECT key, value FROM metadata WHERE key IN "
                    "('kdf_salt', 'kdf_iterations', 'kdf_algorithm')",
                ).fetchall()
            }

            algorithm = rows.get("kdf_algorithm")
            if algorithm is not None and algorithm.decode() != _KDF_ALGORITHM:
                # Fail loudly: deriving with the wrong algorithm would produce
                # a wrong key and surface only as "Failed to decrypt key".
                msg = (
                    f"Store uses KDF {algorithm.decode()!r}, which this build "
                    f"cannot derive (supported: {_KDF_ALGORITHM!r})"
                )
                raise KeyStorageError(msg)

            if "kdf_salt" in rows:
                salt = rows["kdf_salt"]
                if "kdf_iterations" in rows:
                    iterations = int(rows["kdf_iterations"])
                else:
                    iterations = _LEGACY_KDF_ITERATIONS
                    with self._conn:
                        self._conn.execute(
                            "INSERT OR REPLACE INTO metadata (key, value) VALUES "
                            "('kdf_iterations', ?)",
                            (str(iterations).encode(),),
                        )
                        self._conn.execute(
                            "INSERT OR REPLACE INTO metadata (key, value) VALUES "
                            "('kdf_algorithm', ?)",
                            (_KDF_ALGORITHM.encode(),),
                        )
                return salt, iterations

            salt = os.urandom(_KDF_SALT_SIZE)
            with self._conn:
                self._conn.execute(
                    "INSERT INTO metadata (key, value) VALUES ('kdf_salt', ?)",
                    (salt,),
                )
                self._conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES "
                    "('kdf_iterations', ?)",
                    (str(_KDF_ITERATIONS).encode(),),
                )
                self._conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES "
                    "('kdf_algorithm', ?)",
                    (_KDF_ALGORITHM.encode(),),
                )
        return salt, _KDF_ITERATIONS

    @staticmethod
    def _derive_encryption_key(password: str, salt: bytes, iterations: int) -> bytes:
        """Derive the encryption key from a password using PBKDF2-HMAC-SHA256.

        The iteration count is a parameter rather than a module constant so an
        existing store is always re-derived with the factor it was written
        with. See _KDF_ITERATIONS for why that matters.

        Args:
            password: Master password.
            salt: Random salt (32 bytes).
            iterations: PBKDF2 iteration count for this store.

        Returns:
            32-byte encryption key.

        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=_AES_KEY_SIZE,
            salt=salt,
            iterations=iterations,
        )
        return kdf.derive(password.encode("utf-8") if password else b"")

    @staticmethod
    def _secure_zero(data: bytearray) -> None:
        """Zero memory to prevent key material leakage.

        IMPORTANT LIMITATION, documented rather than silently left implied:
        this only works on a mutable `bytearray`. It is never actually
        called anywhere in this class — `store_key()`'s `key_material` and
        `retrieve_key()`'s decrypted return value are both plain `bytes`,
        which are immutable in Python and therefore cannot be zeroed in
        place by this or any other method; the interpreter is also free to
        keep additional copies of immutable `bytes` objects in memory (e.g.
        via interning or the memory allocator's own object reuse) that this
        helper could never reach regardless. Genuinely wiping key material
        from process memory after use would require threading `bytearray`
        (or a `ctypes`/`mmap`-backed buffer) through the whole key lifecycle
        in `store_key()`/`retrieve_key()` and every caller that consumes the
        returned key bytes — a larger, deliberate design change, not a
        one-line fix. This method is kept as a real, working primitive for
        callers that do manage their key material as `bytearray`, but it
        does not currently provide the secure-erasure property its
        docstring implies for anything flowing through this class today.
        """
        for i in range(len(data)):
            data[i] = 0
