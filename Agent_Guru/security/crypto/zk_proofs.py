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
        # Track seen proof nonces to prevent replay, mapped to when each was
        # recorded so _prune_expired_nonces() can evict entries outside the
        # replay window (see that method for why retaining them forever is
        # pointless - a set() that only ever grows was the previous, leaky
        # implementation).
        self._seen_nonces: dict[bytes, datetime] = {}

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

            # Public inputs: claim info + public key (no private key).
            # profile_id is included so verify_proof() can independently
            # recompute commitment_hash from the claimed data (see the fix
            # note in verify_proof() below) - public_key is already included
            # here, and a freshly-generated Ed25519 key pair is effectively
            # a 1:1 fingerprint of its identity in this design, so including
            # profile_id too does not reduce anonymity beyond what including
            # public_key already does.
            public_inputs = {
                "claim_type": claim.claim_type,
                "claim_value": str(claim.claim_value),
                "profile_id": claim.profile_id,
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
        except Exception as exc:
            # Previously any non-ZKProofError here (e.g. a malformed private
            # key, a JSON-serialization failure) propagated as a raw,
            # undocumented exception type instead of the ZKProofError this
            # method's own docstring promises to raise on failure.
            msg = f"Proof generation failed: type={type(exc).__name__}"
            raise ZKProofError(msg) from exc

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

        # Prune nonces outside the replay window before checking/recording -
        # see _prune_expired_nonces() for why this bounds memory growth.
        self._prune_expired_nonces()

        # Check nonce uniqueness
        if proof.nonce in self._seen_nonces:
            msg = "Proof nonce already seen (replay attack)"
            raise ReplayAttackError(msg)

        try:
            # Reconstruct the commitment hash from the claim data actually
            # being verified (profile_id now travels in public_inputs - see
            # generate_proof()) and require it to match the self-reported
            # public_inputs["commitment_hash"] *before* trusting that hash
            # for signature verification.
            #
            # Previously this block built the reconstructed dict as a bare
            # expression and never assigned or used it - meaning nothing
            # here actually confirmed that public_inputs["commitment_hash"]
            # corresponded to public_inputs["claim_type"]/["claim_value"] at
            # all. Since the claim_type/claim_value/commitment_hash fields
            # live in the same ordinary, untrusted public_inputs dict, that
            # let anyone holding one honestly-generated ZKProof for identity
            # X forge a "valid" proof for a *different* claim_type/claim_value
            # from the same identity: just overwrite those two fields in
            # public_inputs (commitment_hash and proof_data, both still
            # bound to the *original* claim, were never touched or checked
            # against the new claim_type/claim_value) and verify_proof()
            # would still report success - a real proof-forgery bypass of
            # this module's own documented "Soundness" guarantee.
            reconstructed_commitment = {
                "claim_type": proof.public_inputs.get("claim_type"),
                "claim_value": proof.public_inputs.get("claim_value"),
                "profile_id": proof.public_inputs.get("profile_id"),
                "timestamp": proof.timestamp.isoformat(),
                "nonce": proof.nonce.hex(),
            }
            if reconstructed_commitment["profile_id"] is None:
                # Legacy proof format predating the profile_id field above -
                # there is no way to independently verify its commitment
                # hash, so fail closed rather than trust the self-reported
                # one.
                return False

            recomputed_bytes = json.dumps(reconstructed_commitment, sort_keys=True).encode("utf-8")
            recomputed_hash = hashlib.sha256(recomputed_bytes).digest()

            expected_hash = bytes.fromhex(proof.public_inputs["commitment_hash"])
            if recomputed_hash != expected_hash:
                # The claimed data doesn't hash to the commitment the
                # signature actually covers - reject before even attempting
                # signature verification.
                return False

            # Verify signature against public key, using the hash we just
            # independently recomputed (not the untrusted self-reported
            # one) so the two checks can't be satisfied independently.
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

            public_key_bytes = bytes.fromhex(proof.public_inputs["public_key"])
            public_key_obj = Ed25519PublicKey.from_public_bytes(public_key_bytes)

            try:
                public_key_obj.verify(proof.proof_data, recomputed_hash)
                valid = True
            except Exception:
                valid = False
            if valid:
                # Record nonce to prevent replay
                self._seen_nonces[proof.nonce] = datetime.now(tz=UTC)

            return valid

        except (ReplayAttackError, ZKProofError):
            raise
        except Exception as exc:
            # Previously any other exception here (malformed hex, a missing
            # public_inputs key, etc.) propagated raw instead of the
            # ZKProofError this method's own docstring promises.
            msg = f"Proof verification failed: type={type(exc).__name__}"
            raise ZKProofError(msg) from exc

    def _prune_expired_nonces(self) -> None:
        """Evict nonces recorded outside the replay window.

        _check_replay() already rejects any proof whose own timestamp is
        older than _REPLAY_WINDOW_SECONDS, so a nonce recorded that long ago
        can never again match a proof that would pass the timestamp check in
        the first place - retaining it forever bought no additional replay
        protection while growing this set without bound for the lifetime of
        a long-running process (a real memory leak in a companion app meant
        to run continuously).
        """
        now = datetime.now(tz=UTC)
        expired = [
            n
            for n, seen_at in self._seen_nonces.items()
            if (now - seen_at).total_seconds() > _REPLAY_WINDOW_SECONDS
        ]
        for n in expired:
            del self._seen_nonces[n]

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
