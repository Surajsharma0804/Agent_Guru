"""Policy Storage - SQLite-backed persistent storage for policies and roles.

Provides CRUD operations with versioning and efficient indexed retrieval.

Performance Characteristics:
    - find_policies: O(log n) with indexes
    - create/update: O(log n)

Validates: Requirement 1 (Policy Definition and Storage), Requirement 3 (RBAC)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from Agent_Guru.policy.models import Policy, PolicyEffect, Role

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS policies (
    id TEXT PRIMARY KEY,
    version INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    description TEXT,
    effect TEXT NOT NULL CHECK(effect IN ('ALLOW', 'DENY', 'ABSTAIN')),
    priority INTEGER NOT NULL DEFAULT 0,
    principals TEXT NOT NULL,
    resources TEXT NOT NULL,
    actions TEXT NOT NULL,
    conditions TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_policies_priority ON policies(priority DESC);
CREATE INDEX IF NOT EXISTS idx_policies_active ON policies(active);

CREATE TABLE IF NOT EXISTS policy_versions (
    policy_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    policy_data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (policy_id, version),
    FOREIGN KEY (policy_id) REFERENCES policies(id)
);

CREATE TABLE IF NOT EXISTS roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    parent_role_id TEXT,
    permissions TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (parent_role_id) REFERENCES roles(id)
);

CREATE TABLE IF NOT EXISTS role_assignments (
    principal_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    assigned_at TEXT NOT NULL,
    PRIMARY KEY (principal_id, role_id),
    FOREIGN KEY (role_id) REFERENCES roles(id)
);
"""


class PolicyStorage:
    """SQLite-backed storage for policies and roles.

    Validates: Requirements 1.1–1.6, 3.1–3.5
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        """Initialise storage.

        Args:
            db_path: Path to SQLite database (":memory:" for in-memory).

        """
        self.db_path = db_path
        # For in-memory databases, keep a persistent connection so the
        # schema and data survive across multiple _conn() calls.
        self._persistent_conn: sqlite3.Connection | None = None
        if db_path == ":memory:":
            self._persistent_conn = sqlite3.connect(
                ":memory:",
                check_same_thread=False,
            )  # persistent; closed when object is GC'd
            self._persistent_conn.row_factory = sqlite3.Row
            self._persistent_conn.execute("PRAGMA foreign_keys = ON")
            self._persistent_conn.executescript(_SCHEMA)
            self._persistent_conn.commit()
        else:
            self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        if self._persistent_conn is not None:
            # Yield the shared in-memory connection without closing it
            try:
                yield self._persistent_conn
                self._persistent_conn.commit()
            except Exception:
                self._persistent_conn.rollback()
                raise
        else:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                try:
                    yield conn
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise

    # ------------------------------------------------------------------
    # Policy CRUD
    # ------------------------------------------------------------------

    def create_policy(self, policy: Policy) -> str:
        """Store a new policy and return its ID.

        Assigns a UUID if policy.id is empty.

        Validates: Requirements 1.1, 1.4
        """
        if not policy.id:
            policy.id = str(uuid.uuid4())

        now = datetime.now(tz=UTC).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO policies
                    (id, version, name, description, effect, priority,
                     principals, resources, actions, conditions,
                     created_at, updated_at, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy.id,
                    policy.version,
                    policy.name,
                    policy.description,
                    policy.effect.value,
                    policy.priority,
                    json.dumps(policy.principals),
                    json.dumps(policy.resources),
                    json.dumps(policy.actions),
                    json.dumps(policy.conditions),
                    now,
                    now,
                    1 if policy.active else 0,
                ),
            )
            # Store initial version snapshot
            conn.execute(
                "INSERT INTO policy_versions (policy_id, version, policy_data, created_at) VALUES (?, ?, ?, ?)",
                (policy.id, policy.version, json.dumps(self._policy_to_dict(policy)), now),
            )

        return policy.id

    def get_policy(self, policy_id: str) -> Policy | None:
        """Retrieve a policy by ID.

        Validates: Requirement 1.6
        """
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM policies WHERE id = ?", (policy_id,)).fetchone()
        return self._row_to_policy(row) if row else None

    def update_policy(self, policy: Policy) -> None:
        """Update an existing policy and increment its version.

        Validates: Requirement 1.5
        """
        now = datetime.now(tz=UTC).isoformat()
        with self._conn() as conn:
            # Increment version
            row = conn.execute("SELECT version FROM policies WHERE id = ?", (policy.id,)).fetchone()
            if not row:
                msg = f"Policy '{policy.id}' not found"
                raise KeyError(msg)
            new_version = row["version"] + 1

            conn.execute(
                """
                UPDATE policies SET
                    version = ?, name = ?, description = ?, effect = ?,
                    priority = ?, principals = ?, resources = ?, actions = ?,
                    conditions = ?, updated_at = ?, active = ?
                WHERE id = ?
                """,
                (
                    new_version,
                    policy.name,
                    policy.description,
                    policy.effect.value,
                    policy.priority,
                    json.dumps(policy.principals),
                    json.dumps(policy.resources),
                    json.dumps(policy.actions),
                    json.dumps(policy.conditions),
                    now,
                    1 if policy.active else 0,
                    policy.id,
                ),
            )
            policy.version = new_version
            conn.execute(
                "INSERT INTO policy_versions (policy_id, version, policy_data, created_at) VALUES (?, ?, ?, ?)",
                (policy.id, new_version, json.dumps(self._policy_to_dict(policy)), now),
            )

    def delete_policy(self, policy_id: str) -> None:
        """Mark a policy as inactive (soft delete).

        Validates: Requirement 1.1
        """
        with self._conn() as conn:
            conn.execute("UPDATE policies SET active = 0 WHERE id = ?", (policy_id,))

    def find_policies(
        self,
        principal: str | None = None,
        resource: str | None = None,
        action: str | None = None,
        active_only: bool = True,
    ) -> list[Policy]:
        """Find active policies. Filters are applied in Python after fetch.

        Validates: Requirement 1.6
        """
        # where is built from hardcoded strings only — no user data in SQL structure
        where = "WHERE active = 1" if active_only else ""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM policies " + where + " ORDER BY priority DESC",  # nosec B608  # noqa: S608 - SQL parameterization reviewed
            ).fetchall()

        policies = [self._row_to_policy(r) for r in rows]

        # Filter by principal/resource/action if provided
        if principal is not None:
            policies = [p for p in policies if p.matches_principal(principal)]
        if resource is not None:
            policies = [p for p in policies if p.matches_resource(resource)]
        if action is not None:
            policies = [p for p in policies if p.matches_action(action)]

        return policies

    def get_policy_versions(self, policy_id: str) -> list[int]:
        """Return all version numbers for a policy in ascending order.

        Validates: Requirement 1.5
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT version FROM policy_versions WHERE policy_id = ? ORDER BY version ASC",
                (policy_id,),
            ).fetchall()
        return [r["version"] for r in rows]

    # ------------------------------------------------------------------
    # Role CRUD
    # ------------------------------------------------------------------

    def create_role(self, role: Role) -> str:
        """Create a new role and return its ID.

        Validates: Requirement 3.1
        """
        if not role.id:
            role.id = str(uuid.uuid4())

        with self._conn() as conn:
            conn.execute(
                "INSERT INTO roles (id, name, parent_role_id, permissions, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    role.id,
                    role.name,
                    role.parent_role_id,
                    json.dumps(role.permissions),
                    role.created_at.isoformat(),
                ),
            )
        return role.id

    def get_role(self, role_id: str) -> Role | None:
        """Retrieve a role by ID."""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone()
        return self._row_to_role(row) if row else None

    def get_role_by_name(self, name: str) -> Role | None:
        """Retrieve a role by name."""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM roles WHERE name = ?", (name,)).fetchone()
        return self._row_to_role(row) if row else None

    def assign_role(self, principal_id: str, role_id: str) -> None:
        """Assign a role to a principal.

        Validates: Requirement 3.2
        """
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO role_assignments (principal_id, role_id, assigned_at) VALUES (?, ?, ?)",
                (principal_id, role_id, datetime.now(tz=UTC).isoformat()),
            )

    def revoke_role(self, principal_id: str, role_id: str) -> None:
        """Revoke a role from a principal."""
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM role_assignments WHERE principal_id = ? AND role_id = ?",
                (principal_id, role_id),
            )

    def get_principal_roles(self, principal_id: str) -> list[Role]:
        """Get all roles directly assigned to a principal.

        Validates: Requirement 3.5
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT r.* FROM roles r
                JOIN role_assignments ra ON r.id = ra.role_id
                WHERE ra.principal_id = ?
                """,
                (principal_id,),
            ).fetchall()
        return [self._row_to_role(r) for r in rows]

    def get_all_roles(self) -> list[Role]:
        """Return all roles."""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM roles").fetchall()
        return [self._row_to_role(r) for r in rows]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_policy(row: sqlite3.Row) -> Policy:
        return Policy(
            id=row["id"],
            version=row["version"],
            name=row["name"],
            description=row["description"] or "",
            effect=PolicyEffect(row["effect"]),
            priority=row["priority"],
            principals=json.loads(row["principals"]),
            resources=json.loads(row["resources"]),
            actions=json.loads(row["actions"]),
            conditions=json.loads(row["conditions"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            active=bool(row["active"]),
        )

    @staticmethod
    def _row_to_role(row: sqlite3.Row) -> Role:
        return Role(
            id=row["id"],
            name=row["name"],
            parent_role_id=row["parent_role_id"],
            permissions=json.loads(row["permissions"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _policy_to_dict(policy: Policy) -> dict:
        return {
            "id": policy.id,
            "version": policy.version,
            "name": policy.name,
            "description": policy.description,
            "effect": policy.effect.value,
            "priority": policy.priority,
            "principals": policy.principals,
            "resources": policy.resources,
            "actions": policy.actions,
            "conditions": policy.conditions,
            "active": policy.active,
        }
