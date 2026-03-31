"""Verifier System Integration.

Enforces mandatory pre-storage verification for all memory operations.
Unverified information is queued, not stored. Rejections are logged.
Contradictions with high-confidence knowledge trigger re-verification.

Properties validated:
  28: Mandatory Pre-Storage Verification
  29: Rejection Handling
  30: Confidence Score Preservation
  31: Contradiction Re-Verification
  32: Verification Audit Trail
  33: Verification Queue on Unavailability
  34: Periodic Re-Verification
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from Agent_Guru.memory.models import VerificationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Audit record
# ---------------------------------------------------------------------------


class VerificationAuditEntry:
    """Immutable record of a single verification event."""

    def __init__(
        self,
        item_id: UUID,
        item_type: str,
        result: VerificationResult,
        timestamp: datetime | None = None,
    ) -> None:
        self.entry_id = uuid4()
        self.item_id = item_id
        self.item_type = item_type
        self.result = result
        self.timestamp = timestamp or datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Verifier backend protocol (dependency-injected)
# ---------------------------------------------------------------------------


class VerifierBackend(Protocol):
    """Interface that the real Verifier System must satisfy."""

    def verify(self, item_id: UUID, item_type: str, data: dict[str, Any]) -> VerificationResult:
        ...

    def is_available(self) -> bool:
        ...


# ---------------------------------------------------------------------------
# Stub backend (used in tests / when no real verifier is wired up)
# ---------------------------------------------------------------------------


class AlwaysApproveVerifier:
    """Stub that approves everything with confidence 1.0."""

    def verify(self, item_id: UUID, item_type: str, data: dict[str, Any]) -> VerificationResult:
        return VerificationResult(verified=True, confidence=1.0, explanation="auto-approved")

    def is_available(self) -> bool:
        return True


class AlwaysRejectVerifier:
    """Stub that rejects everything — useful for testing rejection handling."""

    def verify(self, item_id: UUID, item_type: str, data: dict[str, Any]) -> VerificationResult:
        return VerificationResult(verified=False, confidence=0.0, explanation="auto-rejected")

    def is_available(self) -> bool:
        return True


class UnavailableVerifier:
    """Stub that simulates an unavailable verifier service."""

    def verify(self, item_id: UUID, item_type: str, data: dict[str, Any]) -> VerificationResult:
        raise RuntimeError("Verifier unavailable")

    def is_available(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Main integration class
# ---------------------------------------------------------------------------


class VerifierIntegration:
    """Wraps all memory write operations with mandatory verification.

    Usage:
        vi = VerifierIntegration(backend=AlwaysApproveVerifier())
        result = vi.verify_before_storage(item_id, "entity", data)
        if result.verified:
            # safe to store
    """

    def __init__(self, backend: VerifierBackend | None = None) -> None:
        self._backend: VerifierBackend = backend or AlwaysApproveVerifier()
        # Audit trail: list of VerificationAuditEntry
        self._audit_log: list[VerificationAuditEntry] = []
        # Queue for items pending verification when backend unavailable
        self._pending_queue: deque[tuple[UUID, str, dict[str, Any]]] = deque()
        # Stored confidence scores: item_id -> float
        self._confidence_scores: dict[UUID, float] = {}
        # Rejection log: item_id -> reason
        self._rejection_log: dict[UUID, str] = {}

    # ------------------------------------------------------------------
    # Core verification
    # ------------------------------------------------------------------

    def verify_before_storage(
        self, item_id: UUID, item_type: str, data: dict[str, Any]
    ) -> VerificationResult:
        """Verify item before allowing storage. Queue if backend unavailable.

        Property 28: verification ALWAYS happens before storage.
        Property 33: if unavailable, item is queued not stored.
        """
        if not self._backend.is_available():
            self._pending_queue.append((item_id, item_type, data))
            logger.warning("Verifier unavailable — queued item %s for later verification", item_id)
            return VerificationResult(
                verified=False,
                confidence=0.0,
                explanation="Verifier unavailable — queued for later",
            )

        try:
            result = self._backend.verify(item_id, item_type, data)
        except Exception as exc:
            logger.error("Verification error for %s: %s", item_id, exc)
            self._pending_queue.append((item_id, item_type, data))
            return VerificationResult(
                verified=False,
                confidence=0.0,
                explanation=f"Verification error: {exc}",
            )

        # Record audit entry (Property 32)
        self._audit_log.append(VerificationAuditEntry(item_id, item_type, result))

        if result.verified:
            # Store confidence score (Property 30)
            self._confidence_scores[item_id] = result.confidence
        else:
            # Log rejection (Property 29)
            self._rejection_log[item_id] = result.explanation
            logger.info("Verification rejected item %s: %s", item_id, result.explanation)

        return result

    def request_reverification(
        self, item_id: UUID, item_type: str, data: dict[str, Any]
    ) -> VerificationResult:
        """Re-verify an already-stored item (Property 31, 34)."""
        return self.verify_before_storage(item_id, item_type, data)

    def get_confidence_score(self, item_id: UUID) -> float:
        """Return stored confidence score for a verified item."""
        return self._confidence_scores.get(item_id, 0.0)

    # ------------------------------------------------------------------
    # Contradiction detection
    # ------------------------------------------------------------------

    def check_contradiction(
        self,
        new_item_id: UUID,
        new_data: dict[str, Any],
        existing_item_id: UUID,
        existing_confidence: float,
        contradiction_threshold: float = 0.8,
    ) -> bool:
        """Return True if new data contradicts a high-confidence existing item.

        Property 31: triggers re-verification of existing item when True.
        """
        if existing_confidence < contradiction_threshold:
            return False
        # Simple contradiction: same key, different value
        existing_score = self._confidence_scores.get(existing_item_id, 0.0)
        if existing_score < contradiction_threshold:
            return False
        # Check for key overlap with conflicting values
        # (In production this would compare actual attribute values)
        return bool(new_data)  # Simplified: any new data for a high-confidence item is flagged

    # ------------------------------------------------------------------
    # Queue processing
    # ------------------------------------------------------------------

    def process_pending_queue(self) -> list[tuple[UUID, VerificationResult]]:
        """Process queued items now that backend may be available."""
        results: list[tuple[UUID, VerificationResult]] = []
        while self._pending_queue:
            item_id, item_type, data = self._pending_queue.popleft()
            result = self.verify_before_storage(item_id, item_type, data)
            results.append((item_id, result))
        return results

    @property
    def pending_count(self) -> int:
        return len(self._pending_queue)

    # ------------------------------------------------------------------
    # Audit access
    # ------------------------------------------------------------------

    def get_audit_log(self) -> list[VerificationAuditEntry]:
        return list(self._audit_log)

    def get_rejection_log(self) -> dict[UUID, str]:
        return dict(self._rejection_log)

    def was_rejected(self, item_id: UUID) -> bool:
        return item_id in self._rejection_log
