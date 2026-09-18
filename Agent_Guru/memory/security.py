"""Security features for the Memory System.

Provides:
- AES-256-GCM encryption at rest (Requirement 18.1)
- RBAC authentication and authorization (Requirement 18.2)
- Sensitive data redaction before GitHub sync (Requirement 18.3)
- GDPR-compliant data deletion (Requirement 18.3)
- Access audit logging (Requirement 18.2)

Uses Python's built-in `cryptography` library for AES-256-GCM.
Key management: keys stored in-memory (swap for OS keychain in production).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class EncryptionUnavailableError(RuntimeError):
    """Raised when AES-256-GCM encryption/decryption cannot be performed.

    BUG FIX (Round 18): `cryptography` is a hard pinned dependency of this
    project (requirements.txt: cryptography>=41.0.0), so this should never
    trigger on a correctly-installed deployment. It exists so a broken
    install fails loudly instead of MemorySecurityManager silently
    downgrading "AES-256-GCM encryption at rest" (this class's own
    documented guarantee -- Requirement 18.1) to a trivially-broken
    repeating-key XOR cipher with no authentication and no integrity
    protection (an attacker can flip ciphertext bits undetected, and the
    keystream repeats every 32 bytes, making it breakable by ordinary
    frequency analysis on real text/JSON payloads). Encrypting sensitive,
    GDPR-governed user data with a cipher that provides essentially none
    of the security the docstring promises -- silently, with nothing but
    a debug-level "for testing only" code comment as a warning -- is worse
    than refusing to operate. See encrypt()/decrypt() and the
    allow_insecure_fallback constructor flag below.
    """


# Sensitive field patterns for redaction
_SENSITIVE_PATTERNS = (
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
    re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),  # credit card
    re.compile(r"\b\d{10,15}\b"),  # phone numbers
)
_REDACTION_PLACEHOLDER = "[REDACTED]"


class Role(str, Enum):
    ADMIN = "admin"
    WRITER = "writer"
    READER = "reader"


class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


_ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN},
    Role.WRITER: {Permission.READ, Permission.WRITE},
    Role.READER: {Permission.READ},
}


@dataclass
class AccessAuditEntry:
    entry_id: UUID = field(default_factory=uuid4)
    user_id: str = ""
    permission: Permission = Permission.READ
    resource: str = ""
    granted: bool = True
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class MemorySecurityManager:
    """Handles encryption, RBAC, redaction, and audit logging."""

    def __init__(self, *, allow_insecure_fallback: bool = False) -> None:
        """Initialize the security manager.

        Args:
            allow_insecure_fallback: if True, encrypt()/decrypt() are
                permitted to silently fall back to the non-authenticated
                XOR cipher when the `cryptography` package is unavailable.
                BUG FIX (Round 18): defaults to False. `cryptography` is a
                hard pinned dependency, so leaving this False costs nothing
                in a correct deployment and prevents a broken install from
                quietly storing "encrypted" sensitive data with a cipher
                that provides essentially no real protection. Set True
                only for tests that deliberately exercise the fallback
                path and accept that it is not secure.

        """
        # Key store: key_id -> 32-byte key
        self._keys: dict[str, bytes] = {}
        # User roles: user_id -> Role
        self._user_roles: dict[str, Role] = {}
        # Audit log
        self._audit_log: list[AccessAuditEntry] = []
        # Deleted user IDs (GDPR)
        self._deleted_users: set[str] = set()
        self._allow_insecure_fallback = allow_insecure_fallback

    # ------------------------------------------------------------------
    # Encryption at rest (AES-256-GCM via cryptography library)
    # ------------------------------------------------------------------

    def generate_key(self, key_id: str) -> bytes:
        """Generate and store a 256-bit key."""
        key = os.urandom(32)
        self._keys[key_id] = key
        return key

    def encrypt(self, key_id: str, plaintext: str) -> bytes:
        """Encrypt plaintext with AES-256-GCM. Returns nonce + tag + ciphertext.

        Raises:
            EncryptionUnavailableError: if the `cryptography` package is
                unavailable and allow_insecure_fallback was not set True.

        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            # BUG FIX (Round 18): this used to silently fall back to XOR
            # (see EncryptionUnavailableError's docstring for why that's
            # dangerous for anything claiming "encryption at rest"). Fail
            # loudly by default; only degrade if explicitly opted into.
            if not self._allow_insecure_fallback:
                logger.critical(
                    "cryptography package unavailable -- refusing to "
                    "encrypt with the insecure XOR fallback. Install "
                    "cryptography>=41.0.0 (see requirements.txt), or "
                    "construct MemorySecurityManager(allow_insecure_fallback"
                    "=True) if this is a test that intentionally accepts "
                    "no real encryption.",
                )
                msg = "cryptography package is unavailable; refusing insecure fallback"
                raise EncryptionUnavailableError(msg) from None
            return self._xor_encrypt(key_id, plaintext)
        key = self._keys.get(key_id)
        if key is None:
            msg = f"Key '{key_id}' not found"
            raise KeyError(msg)
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return nonce + ciphertext

    def decrypt(self, key_id: str, ciphertext: bytes) -> str:
        """Decrypt AES-256-GCM ciphertext.

        Raises:
            EncryptionUnavailableError: if the `cryptography` package is
                unavailable and allow_insecure_fallback was not set True.

        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            if not self._allow_insecure_fallback:
                logger.critical(
                    "cryptography package unavailable -- refusing to "
                    "decrypt with the insecure XOR fallback. Install "
                    "cryptography>=41.0.0 (see requirements.txt), or "
                    "construct MemorySecurityManager(allow_insecure_fallback"
                    "=True) if this is a test that intentionally accepts "
                    "no real encryption.",
                )
                msg = "cryptography package is unavailable; refusing insecure fallback"
                raise EncryptionUnavailableError(msg) from None
            return self._xor_decrypt(key_id, ciphertext)
        key = self._keys.get(key_id)
        if key is None:
            msg = f"Key '{key_id}' not found"
            raise KeyError(msg)
        nonce, ct = ciphertext[:12], ciphertext[12:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct, None).decode()

    def _xor_encrypt(self, key_id: str, plaintext: str) -> bytes:
        key = self._keys.get(key_id, b"")
        key_hash = hashlib.sha256(key).digest()
        data = plaintext.encode()
        return bytes(b ^ key_hash[i % 32] for i, b in enumerate(data))

    def _xor_decrypt(self, key_id: str, ciphertext: bytes) -> str:
        key = self._keys.get(key_id, b"")
        key_hash = hashlib.sha256(key).digest()
        return bytes(b ^ key_hash[i % 32] for i, b in enumerate(ciphertext)).decode()

    def rotate_key(self, old_key_id: str, new_key_id: str) -> bytes:
        """Generate a new key; old key remains for decryption of existing data."""
        return self.generate_key(new_key_id)

    # ------------------------------------------------------------------
    # RBAC (Requirement 18.2)
    # ------------------------------------------------------------------

    def assign_role(self, user_id: str, role: Role) -> None:
        self._user_roles[user_id] = role

    def check_permission(self, user_id: str, permission: Permission, resource: str = "") -> bool:
        role = self._user_roles.get(user_id, Role.READER)
        granted = permission in _ROLE_PERMISSIONS.get(role, set())
        self._audit_log.append(
            AccessAuditEntry(
                user_id=user_id,
                permission=permission,
                resource=resource,
                granted=granted,
            ),
        )
        if not granted:
            logger.warning(
                "Access denied: user=%s permission=%s resource=%s",
                user_id,
                permission,
                resource,
            )
        return granted

    def get_audit_log(self) -> list[AccessAuditEntry]:
        return list(self._audit_log)

    # ------------------------------------------------------------------
    # Sensitive data redaction (Requirement 18.3)
    # ------------------------------------------------------------------

    @staticmethod
    def redact(text: str) -> str:
        """Replace sensitive patterns with [REDACTED]."""
        for pattern in _SENSITIVE_PATTERNS:
            text = pattern.sub(_REDACTION_PLACEHOLDER, text)
        return text

    @staticmethod
    def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
        """Recursively redact sensitive values in a dict."""
        result: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, str):
                result[k] = MemorySecurityManager.redact(v)
            elif isinstance(v, dict):
                result[k] = MemorySecurityManager.redact_dict(v)
            else:
                result[k] = v
        return result

    # ------------------------------------------------------------------
    # GDPR data deletion (Requirement 18.3)
    # ------------------------------------------------------------------

    def delete_user_data(self, user_id: str) -> None:
        """Mark user data as deleted (GDPR right to erasure)."""
        self._deleted_users.add(user_id)
        # Remove role assignment
        self._user_roles.pop(user_id, None)
        logger.info("GDPR deletion: user %s data marked for erasure", user_id)

    def is_deleted(self, user_id: str) -> bool:
        return user_id in self._deleted_users
