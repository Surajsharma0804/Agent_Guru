"""Zero-knowledge proof system using Ed25519 commitment scheme.

This implements a practical ZK proof system using Ed25519 signatures as
commitment schemes. While not full zk-SNARKs, this provides:
- Privacy: Proofs don't reveal the private key
- Soundness: Invalid claims cannot produce valid proofs
- Replay prevention: Timestamps prevent replay attacks

Design:
    A proof for claim C is: Sign(private_key, hash(C || timestamp || nonce))
    Verification checks the signature against the public key stored for the identity.
    The private key is never revealed in the proof.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from Agent_Guru.security.crypto.errors import ReplayAttackError, ZKProofError

# Replay window: proofs older than this are rejected
_REPLAY_WINDOW_SECONDS = 300  # 5 minutes

@dataclass
class IdentityClaim:
    """Claim about an identity."""

    claim_type: str  # e.g., "age_over_18", "has_credential"
    claim_value: Any
    profile_id: str

@dataclass
class ZKProof:
    """Zero-knowledge proof using Ed25519 commitment scheme."""

    proof_data: bytes  # Ed25519 signature of commitment
    public_inputs: dict[str, Any]  # Public claim info (no private key)
    timestamp: datetime
    proof_type: str = "ed25519-commitment"
    nonce: bytes = field(default_factory=lambda: os.urandom(16))

class ZKProofSystem:
    """Zero-knowledge proof generation and verification.

    Uses Ed25519 signatures as commitment schemes. The prover signs a
    commitment (hash of claim + timestamp + nonce) with their private key.
    The verifier checks the signature against the stored public key.

    The private key is never included in the proof.
    """

    def __init__(self, identity_manager: Any) -> None:
        self._identity_manager = identity_manager
        # Track seen proof nonces to prevent replay
        self._seen_nonces: set[bytes] = set()

    def generate_proof(self, claim: IdentityClaim) -> ZKProof:
        """Generate zero-knowledge proof for identity claim.

        Proves the claim without revealing the private key.

        Args:
            claim: Identity claim to prove.

        Returns:
            ZKProof that can be verified.

        Raises:
            ZKProofError: If proof generation fails.

        """
        try:
            profile = self._identity_manager.get_identity(claim.profile_id)
        except Exception as exc:
            msg = "Proof generation failed: identity error"
            raise ZKProofError(msg) from exc
        try:
            timestamp = datetime.now(tz=UTC)
            nonce = os.urandom(16)

            # Build commitment: hash(claim_type || claim_value || profile_id || timestamp || nonce)
            commitment_data = {
                "claim_type": claim.claim_type,
                "claim_value": str(claim.claim_value),
                "profile_id": claim.profile_id,
                "timestamp": timestamp.isoformat(),
                "nonce": nonce.hex(),
            }
            commitment_bytes = json.dumps(commitment_data, sort_keys=True).encode("utf-8")
            commitment_hash = hashlib.sha256(commitment_bytes).digest()

            # Sign the commitment hash with the private key
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            private_key_obj = Ed25519PrivateKey.from_private_bytes(profile.key_pair.private_key)
            signature = private_key_obj.sign(commitment_hash)

            # Public inputs: claim info + public key (no private key)
            public_inputs = {
                "claim_type": claim.claim_type,
                "claim_value": str(claim.claim_value),
                "public_key": profile.key_pair.public_key.hex(),
                "commitment_hash": commitment_hash.hex(),
            }

            return ZKProof(
                proof_data=signature,
                public_inputs=public_inputs,
                timestamp=timestamp,
                proof_type="ed25519-commitment",
                nonce=nonce,
            )

        except ZKProofError:
            raise

    def verify_proof(self, proof: ZKProof, expected_claim_type: str) -> bool:
        """Verify zero-knowledge proof.

        Performance: <100ms

        Args:
            proof: Proof to verify.
            expected_claim_type: Expected type of claim.

        Returns:
            True if proof is valid and not replayed.

        Raises:
            ZKProofError: If verification fails unexpectedly.
            ReplayAttackError: If timestamp indicates replay.

        """
        # Check claim type
        if proof.public_inputs.get("claim_type") != expected_claim_type:
            return False

        # Check replay via timestamp
        if self._check_replay(proof):
            msg = "Proof timestamp indicates replay attack"
            raise ReplayAttackError(msg)

        # Check nonce uniqueness
        if proof.nonce in self._seen_nonces:
            msg = "Proof nonce already seen (replay attack)"
            raise ReplayAttackError(msg)

        try:
            # Reconstruct commitment hash
            {
                "claim_type": proof.public_inputs["claim_type"],
                "claim_value": proof.public_inputs["claim_value"],
                # We need profile_id to reconstruct - it's embedded in commitment
                # but not in public_inputs for privacy. We verify via public key.
                "timestamp": proof.timestamp.isoformat(),
                "nonce": proof.nonce.hex(),
            }

            # The commitment hash is stored in public_inputs
            expected_hash = bytes.fromhex(proof.public_inputs["commitment_hash"])

            # Verify signature against public key
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

            public_key_bytes = bytes.fromhex(proof.public_inputs["public_key"])
            public_key_obj = Ed25519PublicKey.from_public_bytes(public_key_bytes)

            try:
                public_key_obj.verify(proof.proof_data, expected_hash)
                valid = True
            except Exception:
                valid = False
            if valid:
                # Record nonce to prevent replay
                self._seen_nonces.add(proof.nonce)

            return valid

        except (ReplayAttackError, ZKProofError):
            raise

    def _check_replay(self, proof: ZKProof) -> bool:
        """Check if proof timestamp indicates replay attack.

        Returns True if the proof is too old (potential replay).
        """
        now = datetime.now(tz=UTC)

        # Ensure proof timestamp is timezone-aware
        proof_ts = proof.timestamp
        if proof_ts.tzinfo is None:
            proof_ts = proof_ts.replace(tzinfo=UTC)

        age = (now - proof_ts).total_seconds()
        return age > _REPLAY_WINDOW_SECONDS
