"""Trust scoring and relationship management.

Trust scores are computed from:
- Authentication history (success/failure rate)
- Biometric confidence scores
- Trust relationships (direct and transitive)
- Time since last activity

Trust scores are always in [0.0, 1.0].
Transitive trust decays by 0.8 per hop (max 3 hops).

Storage: SQLite (in-memory or file-based).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field

_logger = logging.getLogger(__name__)
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


_DEFAULT_TRUST = 0.5
_TRANSITIVE_DECAY = 0.8
_MAX_HOPS = 3


@dataclass
class TrustRelationship:
    """Trust relationship between two identities."""

    relationship_id: str
    from_id: str
    to_id: str
    trust_level: float  # 0.0 to 1.0
    created_at: datetime
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class TrustScore:
    """Computed trust score for an identity."""

    profile_id: str
    score: float  # 0.0 to 1.0
    computed_at: datetime
    factors: Dict[str, float]  # Breakdown of score components


class TrustManager:
    """Trust scoring and relationship management.

    Computes trust scores based on authentication history, biometric
    confidence, and trust relationships. Policy evaluation is handled
    externally by the policy engine.

    Args:
        storage_path: SQLite path or ":memory:".
        audit_logger: Optional audit logger for recording trust events.
    """

    def __init__(
        self,
        storage_path: str = ":memory:",
        audit_logger: Optional[Any] = None,
    ) -> None:
        self._conn = sqlite3.connect(storage_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._audit_logger = audit_logger
        self._init_schema()

    # ------------------------------------------------------------------
    # Trust score computation
    # ------------------------------------------------------------------

    def compute_trust_score(self, profile_id: str) -> TrustScore:
        """Compute trust score for identity.

        Performance: <100ms

        Considers:
        - Authentication history (success/failure rate)
        - Biometric confidence scores
        - Trust relationships
        - Time since last activity

        Args:
            profile_id: Identity to score.

        Returns:
            TrustScore with breakdown.
        """
        factors: Dict[str, float] = {}

        # Authentication history factor
        auth_factor = self._compute_auth_factor(profile_id)
        factors["auth_history"] = auth_factor

        # Biometric confidence factor
        bio_factor = self._compute_biometric_factor(profile_id)
        factors["biometric"] = bio_factor

        # Relationship factor (average trust from others)
        rel_factor = self._compute_relationship_factor(profile_id)
        factors["relationships"] = rel_factor

        # Weighted combination
        # auth_history: 50%, biometric: 30%, relationships: 20%
        score = (
            0.5 * auth_factor
            + 0.3 * bio_factor
            + 0.2 * rel_factor
        )

        # Clamp to [0.0, 1.0]
        score = max(0.0, min(1.0, score))

        return TrustScore(
            profile_id=profile_id,
            score=score,
            computed_at=datetime.now(tz=timezone.utc),
            factors=factors,
        )

    def record_auth_event(
        self,
        profile_id: str,
        success: bool,
        biometric_score: Optional[float] = None,
    ) -> None:
        """Record an authentication event for trust computation.

        Args:
            profile_id: Identity that authenticated.
            success: Whether authentication succeeded.
            biometric_score: Optional biometric confidence score.
        """
        event_type = "auth_success" if success else "auth_failure"
        score_impact = 0.1 if success else -0.1

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO trust_history
                    (history_id, profile_id, timestamp, event_type, score_impact)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    profile_id,
                    datetime.now(tz=timezone.utc).isoformat(),
                    event_type,
                    score_impact,
                ),
            )

        if biometric_score is not None:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO trust_history
                        (history_id, profile_id, timestamp, event_type, score_impact)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        profile_id,
                        datetime.now(tz=timezone.utc).isoformat(),
                        "biometric_score",
                        biometric_score,
                    ),
                )

    # ------------------------------------------------------------------
    # Relationship management
    # ------------------------------------------------------------------

    def create_relationship(
        self,
        from_id: str,
        to_id: str,
        trust_level: float,
        metadata: Optional[Dict[str, str]] = None,
    ) -> TrustRelationship:
        """Create trust relationship.

        Args:
            from_id: Trusting identity.
            to_id: Trusted identity.
            trust_level: Trust level (0.0 to 1.0).
            metadata: Optional metadata.

        Returns:
            Created TrustRelationship.

        Raises:
            ValueError: If trust_level out of range.
        """
        if not 0.0 <= trust_level <= 1.0:
            raise ValueError(f"trust_level must be in [0.0, 1.0], got {trust_level}")

        relationship_id = str(uuid.uuid4())
        created_at = datetime.now(tz=timezone.utc)
        meta = metadata or {}

        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO trust_relationships
                    (relationship_id, from_id, to_id, trust_level, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    relationship_id,
                    from_id,
                    to_id,
                    trust_level,
                    created_at.isoformat(),
                    json.dumps(meta),
                ),
            )

        rel = TrustRelationship(
            relationship_id=relationship_id,
            from_id=from_id,
            to_id=to_id,
            trust_level=trust_level,
            created_at=created_at,
            metadata=meta,
        )

        if self._audit_logger is not None:
            try:
                from Agent_Guru.security.audit.logger import EventType

                self._audit_logger.log_event(
                    event_type=EventType.TRUST_RELATIONSHIP_CREATED,
                    actor_id=from_id,
                    target_id=to_id,
                    outcome="success",
                    details={"trust_level": trust_level},
                )
            except Exception as exc:  # noqa: BLE001
                _logger.warning("Audit log failed for trust relationship creation: %s", exc)

        return rel

    def revoke_relationship(self, from_id: str, to_id: str) -> None:
        """Revoke trust relationship.

        Args:
            from_id: Trusting identity.
            to_id: Trusted identity.
        """
        with self._conn:
            self._conn.execute(
                "DELETE FROM trust_relationships WHERE from_id = ? AND to_id = ?",
                (from_id, to_id),
            )

        if self._audit_logger is not None:
            try:
                from Agent_Guru.security.audit.logger import EventType

                self._audit_logger.log_event(
                    event_type=EventType.TRUST_RELATIONSHIP_REVOKED,
                    actor_id=from_id,
                    target_id=to_id,
                    outcome="success",
                    details={},
                )
            except Exception as exc:  # noqa: BLE001
                _logger.warning("Audit log failed for trust relationship revocation: %s", exc)

    def get_relationships(
        self, profile_id: str, transitive: bool = False
    ) -> List[TrustRelationship]:
        """Get trust relationships for identity.

        Args:
            profile_id: Identity to query.
            transitive: Include transitive relationships.

        Returns:
            List of trust relationships.
        """
        rows = self._conn.execute(
            "SELECT * FROM trust_relationships WHERE from_id = ?",
            (profile_id,),
        ).fetchall()

        direct = [self._row_to_relationship(r) for r in rows]

        if not transitive:
            return direct

        # BFS for transitive relationships
        all_rels = {(r.from_id, r.to_id): r for r in direct}
        visited: Set[str] = {profile_id}
        frontier = [r.to_id for r in direct]

        for _ in range(_MAX_HOPS - 1):
            next_frontier = []
            for node in frontier:
                if node in visited:
                    continue
                visited.add(node)
                sub_rows = self._conn.execute(
                    "SELECT * FROM trust_relationships WHERE from_id = ?",
                    (node,),
                ).fetchall()
                for sub_row in sub_rows:
                    sub_rel = self._row_to_relationship(sub_row)
                    key = (sub_rel.from_id, sub_rel.to_id)
                    if key not in all_rels:
                        all_rels[key] = sub_rel
                        next_frontier.append(sub_rel.to_id)
            frontier = next_frontier

        return list(all_rels.values())

    def compute_transitive_trust(
        self, from_id: str, to_id: str, max_hops: int = _MAX_HOPS
    ) -> float:
        """Compute transitive trust with decay.

        Decay factor: 0.8 per hop.

        Args:
            from_id: Source identity.
            to_id: Target identity.
            max_hops: Maximum hops to traverse.

        Returns:
            Transitive trust score in [0.0, 1.0].
        """
        # BFS with trust decay
        # State: (current_node, accumulated_trust)
        visited: Set[str] = {from_id}
        frontier = [(from_id, 1.0)]
        best_trust = 0.0

        for hop in range(max_hops):
            next_frontier = []
            for node, current_trust in frontier:
                rows = self._conn.execute(
                    "SELECT to_id, trust_level FROM trust_relationships WHERE from_id = ?",
                    (node,),
                ).fetchall()
                for row in rows:
                    next_node = row["to_id"]
                    edge_trust = row["trust_level"]
                    new_trust = current_trust * edge_trust * (_TRANSITIVE_DECAY ** hop)

                    if next_node == to_id:
                        best_trust = max(best_trust, new_trust)

                    if next_node not in visited:
                        visited.add(next_node)
                        next_frontier.append((next_node, new_trust))

            frontier = next_frontier
            if not frontier:
                break

        return min(1.0, best_trust)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trust_relationships (
                    relationship_id TEXT PRIMARY KEY,
                    from_id TEXT NOT NULL,
                    to_id TEXT NOT NULL,
                    trust_level REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    UNIQUE (from_id, to_id)
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trust_history (
                    history_id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    score_impact REAL NOT NULL
                )
                """
            )

    def _compute_auth_factor(self, profile_id: str) -> float:
        """Compute authentication history factor."""
        rows = self._conn.execute(
            """
            SELECT event_type, score_impact FROM trust_history
            WHERE profile_id = ? AND event_type IN ('auth_success', 'auth_failure')
            ORDER BY timestamp DESC LIMIT 20
            """,
            (profile_id,),
        ).fetchall()

        if not rows:
            return _DEFAULT_TRUST

        successes = sum(1 for r in rows if r["event_type"] == "auth_success")
        total = len(rows)
        return successes / total

    def _compute_biometric_factor(self, profile_id: str) -> float:
        """Compute biometric confidence factor."""
        rows = self._conn.execute(
            """
            SELECT score_impact FROM trust_history
            WHERE profile_id = ? AND event_type = 'biometric_score'
            ORDER BY timestamp DESC LIMIT 10
            """,
            (profile_id,),
        ).fetchall()

        if not rows:
            return _DEFAULT_TRUST

        scores = [r["score_impact"] for r in rows]
        return sum(scores) / len(scores)

    def _compute_relationship_factor(self, profile_id: str) -> float:
        """Compute relationship-based trust factor."""
        rows = self._conn.execute(
            "SELECT trust_level FROM trust_relationships WHERE to_id = ?",
            (profile_id,),
        ).fetchall()

        if not rows:
            return _DEFAULT_TRUST

        levels = [r["trust_level"] for r in rows]
        return sum(levels) / len(levels)

    def _row_to_relationship(self, row: sqlite3.Row) -> TrustRelationship:
        return TrustRelationship(
            relationship_id=row["relationship_id"],
            from_id=row["from_id"],
            to_id=row["to_id"],
            trust_level=row["trust_level"],
            created_at=datetime.fromisoformat(row["created_at"]),
            metadata=json.loads(row["metadata"]),
        )
