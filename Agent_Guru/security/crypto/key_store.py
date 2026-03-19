"""Secure key storage with AES-256-GCM encryption and PBKDF2 key derivation.

Keys are encrypted at rest using AES-256-GCM. The encryption key is derived
from a master password using PBKDF2 with 100,000+ iterations.

Storage backend: SQLite (in-memory or file-based).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from Agent_Guru.security.crypto.errors import KeyNotFoundError, KeyStorageError

# PBKDF2 parameters
_KDF_ITERATIONS = 100_000
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

    def __init__(self, storage_path: str = ":memory:", master_password: str = "") -> None:
        self._storage_path = storage_path
        self._conn = sqlite3.connect(storage_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

        # Derive or load encryption key
        self._salt = self._get_or_create_salt()
        self._encryption_key = self._derive_encryption_key(master_password, self._salt)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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

            with self._conn:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO keys (key_id, encrypted_key, nonce, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (key_id, encrypted, nonce, datetime.utcnow().isoformat()),
                )
        except Exception as exc:
            raise KeyStorageError(f"Failed to store key: type={type(exc).__name__}") from exc

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
        row = self._conn.execute(
            "SELECT encrypted_key, nonce FROM keys WHERE key_id = ?",
            (key_id,),
        ).fetchone()

        if row is None:
            raise KeyNotFoundError(f"Key not found")

        try:
            aesgcm = AESGCM(self._encryption_key)
            decrypted = aesgcm.decrypt(bytes(row["nonce"]), bytes(row["encrypted_key"]), key_id.encode())
            return decrypted
        except Exception as exc:
            raise KeyStorageError(f"Failed to decrypt key: type={type(exc).__name__}") from exc

    def delete_key(self, key_id: str) -> None:
        """Securely delete key.

        Args:
            key_id: Key to delete.

        Raises:
            KeyNotFoundError: If key doesn't exist.
        """
        cursor = self._conn.execute(
            "SELECT COUNT(*) FROM keys WHERE key_id = ?", (key_id,)
        )
        if cursor.fetchone()[0] == 0:
            raise KeyNotFoundError(f"Key not found")

        with self._conn:
            self._conn.execute("DELETE FROM keys WHERE key_id = ?", (key_id,))

    def key_exists(self, key_id: str) -> bool:
        """Check if a key exists."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM keys WHERE key_id = ?", (key_id,)
        ).fetchone()
        return row[0] > 0

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS keys (
                    key_id TEXT PRIMARY KEY,
                    encrypted_key BLOB NOT NULL,
                    nonce BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    deprecated_at TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value BLOB NOT NULL
                )
                """
            )

    def _get_or_create_salt(self) -> bytes:
        """Get existing salt or create a new one."""
        row = self._conn.execute(
            "SELECT value FROM metadata WHERE key = 'kdf_salt'"
        ).fetchone()

        if row is not None:
            return bytes(row["value"])

        salt = os.urandom(_KDF_SALT_SIZE)
        with self._conn:
            self._conn.execute(
                "INSERT INTO metadata (key, value) VALUES ('kdf_salt', ?)",
                (salt,),
            )
        return salt

    def _derive_encryption_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2.

        Uses 100,000 iterations with SHA-256.

        Args:
            password: Master password.
            salt: Random salt (32 bytes).

        Returns:
            32-byte encryption key.
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=_AES_KEY_SIZE,
            salt=salt,
            iterations=_KDF_ITERATIONS,
        )
        return kdf.derive(password.encode("utf-8") if password else b"")

    @staticmethod
    def _secure_zero(data: bytearray) -> None:
        """Zero memory to prevent key material leakage."""
        for i in range(len(data)):
            data[i] = 0
