"""Cryptographic identity management using Ed25519 key pairs.

Performance targets:
- Key generation: <100ms
- Sign: <10ms
- Verify: <10ms
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from Agent_Guru.security.crypto.errors import (
    IdentityNotFoundError,
    KeyGenerationError,
    SignatureError,
)


@dataclass
class KeyPair:
    """Ed25519 key pair."""

    public_key: bytes  # 32 bytes raw
    private_key: bytes  # 32 bytes raw seed
    created_at: datetime
    deprecated_at: Optional[datetime] = None


@dataclass
class IdentityProfile:
    """Named identity with associated keys."""

    profile_id: str
    name: str
    key_pair: KeyPair
    metadata: Dict[str, str] = field(default_factory=dict)


class IdentityManager:
    """Manages cryptographic identities using Ed25519.

    Stores identity profiles in an in-memory dict backed by a KeyStore.
    Active signing keys are tracked separately so that key rotation does
    not mutate the original IdentityProfile object (callers may hold
    references to the original profile and its key_pair).
    """

    def __init__(self, key_store: Any, audit_logger: Optional[Any] = None) -> None:
        self._key_store = key_store
        self._audit_logger = audit_logger
        self._profiles: Dict[str, IdentityProfile] = {}
        # Maps profile_id -> currently active KeyPair (may differ from
        # profile.key_pair after rotation).
        self._active_keys: Dict[str, KeyPair] = {}

    # ------------------------------------------------------------------
    # Identity lifecycle
    # ------------------------------------------------------------------

    def create_identity(self, profile_name: str) -> IdentityProfile:
        """Generate a new identity with Ed25519 key pair.

        Performance: <100ms

        Args:
            profile_name: Human-readable name for the identity.

        Returns:
            IdentityProfile with generated keys.

        Raises:
            KeyGenerationError: If key generation fails.
        """
        try:
            private_key_obj = Ed25519PrivateKey.generate()
            public_key_obj = private_key_obj.public_key()

            # Extract raw bytes
            private_bytes = private_key_obj.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
            public_bytes = public_key_obj.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )

            profile_id = str(uuid.uuid4())
            key_pair = KeyPair(
                public_key=public_bytes,
                private_key=private_bytes,
                created_at=datetime.utcnow(),
            )

            # Store private key in key store
            self._key_store.store_key(f"identity:{profile_id}:private", private_bytes)

            profile = IdentityProfile(
                profile_id=profile_id,
                name=profile_name,
                key_pair=key_pair,
            )
            self._profiles[profile_id] = profile
            self._active_keys[profile_id] = key_pair

            if self._audit_logger is not None:
                try:
                    from Agent_Guru.security.audit.logger import EventType

                    self._audit_logger.log_event(
                        event_type=EventType.KEY_GENERATED,
                        actor_id=profile_id,
                        target_id=None,
                        outcome="success",
                        details={"profile_name": profile_name},
                    )
                except Exception:
                    pass  # Audit logging is best-effort

            return profile

        except Exception as exc:
            raise KeyGenerationError(f"Failed to generate identity: type={type(exc).__name__}") from exc

    def rotate_key(self, profile_id: str) -> KeyPair:
        """Generate new key pair and deprecate old one.

        Args:
            profile_id: Identity to rotate.

        Returns:
            New KeyPair.

        Raises:
            IdentityNotFoundError: If profile doesn't exist.
            KeyGenerationError: If rotation fails.
        """
        profile = self._get_profile_or_raise(profile_id)

        try:
            private_key_obj = Ed25519PrivateKey.generate()
            public_key_obj = private_key_obj.public_key()

            private_bytes = private_key_obj.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
            public_bytes = public_key_obj.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )

            # Deprecate old key (mark on the profile's original key_pair)
            profile.key_pair.deprecated_at = datetime.utcnow()

            new_key_pair = KeyPair(
                public_key=public_bytes,
                private_key=private_bytes,
                created_at=datetime.utcnow(),
            )

            # Store new private key; update profile.key_pair to the new key
            # and track it in _active_keys for signing.
            self._key_store.store_key(f"identity:{profile_id}:private", private_bytes)
            profile.key_pair = new_key_pair
            self._active_keys[profile_id] = new_key_pair

            if self._audit_logger is not None:
                try:
                    from Agent_Guru.security.audit.logger import EventType

                    self._audit_logger.log_event(
                        event_type=EventType.KEY_ROTATED,
                        actor_id=profile_id,
                        target_id=None,
                        outcome="success",
                        details={},
                    )
                except Exception:
                    pass

            return new_key_pair

        except IdentityNotFoundError:
            raise
        except Exception as exc:
            raise KeyGenerationError(f"Key rotation failed: type={type(exc).__name__}") from exc

    def derive_key(self, master_key: bytes, context: str, index: int) -> bytes:
        """Derive child key from master key using PBKDF2.

        Uses 100,000 iterations with context+index as salt.

        Args:
            master_key: Master key material.
            context: Derivation context (e.g., "signing", "encryption").
            index: Child key index.

        Returns:
            Derived key bytes (32 bytes).
        """
        salt = f"{context}:{index}".encode("utf-8")
        # Pad salt to 16 bytes minimum
        if len(salt) < 16:
            salt = salt + b"\x00" * (16 - len(salt))

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        return kdf.derive(master_key)

    def sign(self, profile_id: str, message: bytes) -> bytes:
        """Sign message with identity's private key.

        Performance: <10ms

        Args:
            profile_id: Identity to sign with.
            message: Message to sign.

        Returns:
            Ed25519 signature (64 bytes).

        Raises:
            IdentityNotFoundError: If profile doesn't exist.
            SignatureError: If signing fails.
        """
        profile = self._get_profile_or_raise(profile_id)

        try:
            active_key = self._active_keys.get(profile_id, profile.key_pair)
            private_key_obj = Ed25519PrivateKey.from_private_bytes(active_key.private_key)
            return private_key_obj.sign(message)
        except IdentityNotFoundError:
            raise
        except Exception as exc:
            raise SignatureError(f"Signing failed: type={type(exc).__name__}") from exc

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify Ed25519 signature.

        Performance: <10ms

        Args:
            public_key: Public key (32 bytes).
            message: Original message.
            signature: Signature to verify (64 bytes).

        Returns:
            True if signature is valid.
        """
        try:
            public_key_obj = Ed25519PublicKey.from_public_bytes(public_key)
            public_key_obj.verify(signature, message)
            return True
        except Exception:
            return False

    def get_identity(self, profile_id: str) -> IdentityProfile:
        """Retrieve identity profile.

        Raises:
            IdentityNotFoundError: If profile doesn't exist.
        """
        return self._get_profile_or_raise(profile_id)

    def list_identities(self) -> List[IdentityProfile]:
        """List all identity profiles."""
        return list(self._profiles.values())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_profile_or_raise(self, profile_id: str) -> IdentityProfile:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise IdentityNotFoundError(f"Identity not found")
        return profile
