"""Adversarial Robustness Engine.

Provides:
- Conflict preservation: both versions stored, neither discarded (Property 57)
- Data poisoning detection: flags info contradicting high-confidence knowledge (Property 58)
- Source trust management: reduces trust for repeatedly suspicious sources
- Rollback to previous memory snapshots (Requirement 12.6)
- Concurrent inconsistency resolution (Requirement 12.7)
- Integrity violation handling with quarantine (Requirement 12.9)
- Tamper detection via checksums (Property 64)
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

_HIGH_CONFIDENCE_THRESHOLD = 0.85
_POISONING_SUSPICION_THRESHOLD = 3  # flag source after this many suspicious items


@dataclass
class ConflictRecord:
    conflict_id: UUID = field(default_factory=uuid4)
    item_id: UUID = field(default_factory=uuid4)
    version_a: dict[str, Any] = field(default_factory=dict)
    version_b: dict[str, Any] = field(default_factory=dict)
    confidence_a: float = 1.0
    confidence_b: float = 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    resolved: bool = False


@dataclass
class PoisoningFlag:
    flag_id: UUID = field(default_factory=uuid4)
    item_id: UUID = field(default_factory=uuid4)
    source: str = ""
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass
class IntegrityViolation:
    violation_id: UUID = field(default_factory=uuid4)
    structure_id: str = ""
    expected_checksum: str = ""
    actual_checksum: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    quarantined: bool = False


@dataclass
class MemorySnapshot:
    snapshot_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    data: dict[str, Any] = field(default_factory=dict)


class AdversarialRobustnessEngine:
    """Detects and handles adversarial inputs to the memory system.

    All operations are in-memory; swap storage backends for production.
    """

    def __init__(self, high_confidence_threshold: float = _HIGH_CONFIDENCE_THRESHOLD) -> None:
        self._threshold = high_confidence_threshold
        # Conflict storage: item_id -> list of ConflictRecord
        self._conflicts: dict[UUID, list[ConflictRecord]] = {}
        # Poisoning flags
        self._poisoning_flags: list[PoisoningFlag] = []
        # Source trust scores: source -> (trust_score, suspicious_count)
        self._source_trust: dict[str, float] = {}
        self._source_suspicious_count: dict[str, int] = {}
        # Snapshots for rollback
        self._snapshots: list[MemorySnapshot] = []
        # Integrity checksums: structure_id -> checksum
        self._checksums: dict[str, str] = {}
        # Quarantined items
        self._quarantined: set[UUID] = set()
        # Integrity violations
        self._violations: list[IntegrityViolation] = []

    # ------------------------------------------------------------------
    # Conflict preservation (Property 57, Requirement 12.1)
    # ------------------------------------------------------------------

    def store_conflict(
        self,
        item_id: UUID,
        version_a: dict[str, Any],
        version_b: dict[str, Any],
        confidence_a: float = 1.0,
        confidence_b: float = 1.0,
    ) -> ConflictRecord:
        """Store both conflicting versions - neither is discarded."""
        record = ConflictRecord(
            item_id=item_id,
            version_a=version_a,
            version_b=version_b,
            confidence_a=confidence_a,
            confidence_b=confidence_b,
        )
        self._conflicts.setdefault(item_id, []).append(record)
        logger.debug("Stored conflict for item %s", item_id)
        return record

    def get_conflicts(self, item_id: UUID) -> list[ConflictRecord]:
        return list(self._conflicts.get(item_id, []))

    def has_conflict(self, item_id: UUID) -> bool:
        return bool(self._conflicts.get(item_id))

    # ------------------------------------------------------------------
    # Data poisoning detection (Property 58, Requirements 12.2-12.4)
    # ------------------------------------------------------------------

    def check_for_poisoning(
        self,
        item_id: UUID,
        new_data: dict[str, Any],
        existing_data: dict[str, Any],
        existing_confidence: float,
        source: str = "unknown",
    ) -> bool:
        """Return True if new_data looks like a poisoning attempt.

        Poisoning is suspected when new_data contradicts existing high-confidence
        knowledge (existing_confidence >= threshold) on the same keys.
        """
        if existing_confidence < self._threshold:
            return False  # Existing knowledge not high-confidence; no poisoning concern

        contradictions = 0
        for key, new_val in new_data.items():
            if key in existing_data and existing_data[key] != new_val:
                contradictions += 1

        if contradictions == 0:
            return False

        # Flag as suspicious
        flag = PoisoningFlag(
            item_id=item_id,
            source=source,
            reason=f"Contradicts {contradictions} high-confidence field(s)",
        )
        self._poisoning_flags.append(flag)
        self._update_source_trust(source, suspicious=True)
        logger.warning("Poisoning suspected for item %s from source '%s'", item_id, source)
        return True

    def get_poisoning_flags(self) -> list[PoisoningFlag]:
        return list(self._poisoning_flags)

    def is_flagged(self, item_id: UUID) -> bool:
        return any(f.item_id == item_id for f in self._poisoning_flags)

    # ------------------------------------------------------------------
    # Source trust management (Requirement 12.5)
    # ------------------------------------------------------------------

    def _update_source_trust(self, source: str, suspicious: bool) -> None:
        if source not in self._source_trust:
            self._source_trust[source] = 1.0
            self._source_suspicious_count[source] = 0
        if suspicious:
            self._source_suspicious_count[source] += 1
            count = self._source_suspicious_count[source]
            # Reduce trust: each suspicion halves remaining trust
            self._source_trust[source] = max(0.0, 1.0 / (2**count))
        else:
            # Slightly restore trust on clean submission
            self._source_trust[source] = min(1.0, self._source_trust[source] + 0.05)

    def get_source_trust(self, source: str) -> float:
        return self._source_trust.get(source, 1.0)

    # ------------------------------------------------------------------
    # Rollback (Requirement 12.6)
    # ------------------------------------------------------------------

    def take_snapshot(self, data: dict[str, Any]) -> MemorySnapshot:
        snap = MemorySnapshot(data=dict(data))
        self._snapshots.append(snap)
        return snap

    def rollback_to(self, snapshot_id: UUID) -> dict[str, Any] | None:
        for snap in reversed(self._snapshots):
            if snap.snapshot_id == snapshot_id:
                logger.info("Rolling back to snapshot %s", snapshot_id)
                return dict(snap.data)
        return None

    def get_latest_snapshot(self) -> MemorySnapshot | None:
        return self._snapshots[-1] if self._snapshots else None

    # ------------------------------------------------------------------
    # Concurrent inconsistency resolution (Requirement 12.7)
    # ------------------------------------------------------------------

    def resolve_concurrent_conflict(
        self,
        item_id: UUID,
        version_a: dict[str, Any],
        confidence_a: float,
        version_b: dict[str, Any],
        confidence_b: float,
    ) -> dict[str, Any]:
        """Merge two concurrent versions: higher-confidence fields win; conflicts stored."""
        self.store_conflict(item_id, version_a, version_b, confidence_a, confidence_b)
        # Merge: prefer higher-confidence version's values on conflict
        merged: dict[str, Any] = {}
        all_keys = set(version_a) | set(version_b)
        for key in all_keys:
            if key in version_a and key in version_b:
                merged[key] = version_a[key] if confidence_a >= confidence_b else version_b[key]
            elif key in version_a:
                merged[key] = version_a[key]
            else:
                merged[key] = version_b[key]
        return merged

    # ------------------------------------------------------------------
    # Tamper detection (Property 64, Requirement 12.10)
    # ------------------------------------------------------------------

    @staticmethod
    def compute_checksum(data: dict[str, Any]) -> str:
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def register_checksum(self, structure_id: str, data: dict[str, Any]) -> str:
        checksum = self.compute_checksum(data)
        self._checksums[structure_id] = checksum
        return checksum

    def verify_integrity(self, structure_id: str, data: dict[str, Any]) -> bool:
        """Return True if data matches registered checksum."""
        expected = self._checksums.get(structure_id)
        if expected is None:
            return True  # Not registered - nothing to verify
        actual = self.compute_checksum(data)
        if actual != expected:
            violation = IntegrityViolation(
                structure_id=structure_id,
                expected_checksum=expected,
                actual_checksum=actual,
            )
            self._violations.append(violation)
            logger.error("Integrity violation detected for '%s'", structure_id)
            return False
        return True

    def quarantine(self, item_id: UUID) -> None:
        self._quarantined.add(item_id)
        logger.warning("Quarantined item %s", item_id)

    def is_quarantined(self, item_id: UUID) -> bool:
        return item_id in self._quarantined

    def get_violations(self) -> list[IntegrityViolation]:
        return list(self._violations)
