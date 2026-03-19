"""Main security system facade integrating all security components.

GuruSecuritySystem is the primary entry point for all security operations.
It integrates:
- IdentityManager: Ed25519 key pair management
- KeyStore: AES-256-GCM encrypted key storage
- AuditLogger: Immutable cryptographically-signed audit logs
- TrustManager: Dynamic trust scoring and relationship management
- ZKProofSystem: Zero-knowledge proof generation and verification
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from Agent_Guru.security.audit.logger import AuditLogger, EventType, LogQuery
from Agent_Guru.security.crypto.errors import (
    ConfigurationError,
    IdentityNotFoundError,
    SecurityError,
)
from Agent_Guru.security.crypto.identity import IdentityManager, IdentityProfile, KeyPair
from Agent_Guru.security.crypto.key_store import KeyStore
from Agent_Guru.security.crypto.zk_proofs import IdentityClaim, ZKProof, ZKProofSystem
from Agent_Guru.security.trust.manager import TrustManager, TrustRelationship, TrustScore


@dataclass
class SecurityConfig:
    """Security system configuration."""

    # Key derivation
    kdf_iterations: int = 100_000

    # Trust thresholds
    default_trust_score: float = 0.5
    min_trust_for_operations: float = 0.6
    biometric_threshold: float = 0.7

    # Storage paths (":memory:" for in-memory)
    key_store_path: str = ":memory:"
    log_store_path: str = ":memory:"
    trust_store_path: str = ":memory:"

    # Master password for key store
    master_password: str = ""

    # Test mode
    test_mode: bool = False

    def validate(self) -> None:
        """Validate configuration meets security standards."""
        if self.kdf_iterations < 100_000:
            raise ConfigurationError(
                f"KDF iterations must be >= 100000, got {self.kdf_iterations}"
            )
        if not 0.0 <= self.default_trust_score <= 1.0:
            raise ConfigurationError("default_trust_score must be in [0.0, 1.0]")
        if not 0.0 <= self.min_trust_for_operations <= 1.0:
            raise ConfigurationError("min_trust_for_operations must be in [0.0, 1.0]")
        if not 0.0 <= self.biometric_threshold <= 1.0:
            raise ConfigurationError("biometric_threshold must be in [0.0, 1.0]")


class GuruSecuritySystem:
    """Main security system facade.

    Integrates all security components and provides a unified API.

    Usage:
        config = SecurityConfig()
        security = GuruSecuritySystem(config)
        security.initialize()

        # Create identity
        profile = security.create_identity("alice")

        # Sign and verify
        sig = security.sign(profile.profile_id, b"hello")
        valid = security.verify(profile.key_pair.public_key, b"hello", sig)
    """

    def __init__(self, config: Optional[SecurityConfig] = None) -> None:
        self._config = config or SecurityConfig()
        self._initialized = False
        self._key_store: Optional[KeyStore] = None
        self._audit_logger: Optional[AuditLogger] = None
        self._trust_manager: Optional[TrustManager] = None
        self._identity_manager: Optional[IdentityManager] = None
        self._zk_proof_system: Optional[ZKProofSystem] = None

    def initialize(self) -> None:
        """Initialize all security subsystems.

        Raises:
            ConfigurationError: If configuration is invalid.
        """
        self._config.validate()

        self._key_store = KeyStore(
            storage_path=self._config.key_store_path,
            master_password=self._config.master_password,
        )

        self._audit_logger = AuditLogger(
            storage_path=self._config.log_store_path,
        )

        self._trust_manager = TrustManager(
            storage_path=self._config.trust_store_path,
            audit_logger=self._audit_logger,
        )

        self._identity_manager = IdentityManager(
            key_store=self._key_store,
            audit_logger=self._audit_logger,
        )

        self._zk_proof_system = ZKProofSystem(
            identity_manager=self._identity_manager,
        )

        self._initialized = True

    # ------------------------------------------------------------------
    # Identity management
    # ------------------------------------------------------------------

    def create_identity(self, profile_name: str) -> IdentityProfile:
        """Create a new cryptographic identity."""
        self._ensure_initialized()
        return self._identity_manager.create_identity(profile_name)  # type: ignore[union-attr]

    def get_identity(self, profile_id: str) -> IdentityProfile:
        """Retrieve an identity profile."""
        self._ensure_initialized()
        return self._identity_manager.get_identity(profile_id)  # type: ignore[union-attr]

    def list_identities(self) -> List[IdentityProfile]:
        """List all identity profiles."""
        self._ensure_initialized()
        return self._identity_manager.list_identities()  # type: ignore[union-attr]

    def rotate_key(self, profile_id: str) -> KeyPair:
        """Rotate key pair for an identity."""
        self._ensure_initialized()
        return self._identity_manager.rotate_key(profile_id)  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Cryptographic operations
    # ------------------------------------------------------------------

    def sign(self, profile_id: str, message: bytes) -> bytes:
        """Sign a message with an identity's private key."""
        self._ensure_initialized()
        return self._identity_manager.sign(profile_id, message)  # type: ignore[union-attr]

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify an Ed25519 signature."""
        self._ensure_initialized()
        return self._identity_manager.verify(public_key, message, signature)  # type: ignore[union-attr]

    def derive_key(self, master_key: bytes, context: str, index: int) -> bytes:
        """Derive a child key from a master key."""
        self._ensure_initialized()
        return self._identity_manager.derive_key(master_key, context, index)  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # ZK Proofs
    # ------------------------------------------------------------------

    def generate_proof(self, claim: IdentityClaim) -> ZKProof:
        """Generate a zero-knowledge proof for an identity claim."""
        self._ensure_initialized()
        return self._zk_proof_system.generate_proof(claim)  # type: ignore[union-attr]

    def verify_proof(self, proof: ZKProof, expected_claim_type: str) -> bool:
        """Verify a zero-knowledge proof."""
        self._ensure_initialized()
        return self._zk_proof_system.verify_proof(proof, expected_claim_type)  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Audit logging
    # ------------------------------------------------------------------

    def audit_operation(
        self,
        event_type: EventType,
        actor_id: Optional[str],
        target_id: Optional[str],
        outcome: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a security event to the audit log."""
        self._ensure_initialized()
        self._audit_logger.log_event(  # type: ignore[union-attr]
            event_type=event_type,
            actor_id=actor_id,
            target_id=target_id,
            outcome=outcome,
            details=details or {},
        )

    def query_audit_logs(self, query: LogQuery) -> list:
        """Query audit logs with filters."""
        self._ensure_initialized()
        return self._audit_logger.query_logs(query)  # type: ignore[union-attr]

    def export_audit_logs(self, query: LogQuery, format: str = "json") -> str:
        """Export audit logs in structured format."""
        self._ensure_initialized()
        return self._audit_logger.export_logs(query, format)  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Trust management
    # ------------------------------------------------------------------

    def compute_trust_score(self, profile_id: str) -> TrustScore:
        """Compute trust score for an identity."""
        self._ensure_initialized()
        return self._trust_manager.compute_trust_score(profile_id)  # type: ignore[union-attr]

    def create_trust_relationship(
        self,
        from_id: str,
        to_id: str,
        trust_level: float,
    ) -> TrustRelationship:
        """Create a trust relationship between two identities."""
        self._ensure_initialized()
        return self._trust_manager.create_relationship(from_id, to_id, trust_level)  # type: ignore[union-attr]

    def revoke_trust_relationship(self, from_id: str, to_id: str) -> None:
        """Revoke a trust relationship."""
        self._ensure_initialized()
        self._trust_manager.revoke_relationship(from_id, to_id)  # type: ignore[union-attr]

    def get_trust_relationships(
        self, profile_id: str, transitive: bool = False
    ) -> List[TrustRelationship]:
        """Get trust relationships for an identity."""
        self._ensure_initialized()
        return self._trust_manager.get_relationships(profile_id, transitive)  # type: ignore[union-attr]

    def record_auth_event(
        self,
        profile_id: str,
        success: bool,
        biometric_score: Optional[float] = None,
    ) -> None:
        """Record an authentication event for trust computation."""
        self._ensure_initialized()
        self._trust_manager.record_auth_event(profile_id, success, biometric_score)  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def identity_manager(self) -> IdentityManager:
        self._ensure_initialized()
        return self._identity_manager  # type: ignore[return-value]

    @property
    def key_store(self) -> KeyStore:
        self._ensure_initialized()
        return self._key_store  # type: ignore[return-value]

    @property
    def audit_logger(self) -> AuditLogger:
        self._ensure_initialized()
        return self._audit_logger  # type: ignore[return-value]

    @property
    def trust_manager(self) -> TrustManager:
        self._ensure_initialized()
        return self._trust_manager  # type: ignore[return-value]

    @property
    def zk_proof_system(self) -> ZKProofSystem:
        self._ensure_initialized()
        return self._zk_proof_system  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise SecurityError(
                "GuruSecuritySystem not initialized. Call initialize() first.",
                "SYSTEM_NOT_INITIALIZED",
            )
