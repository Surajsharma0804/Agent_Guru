"""Offline cache with SQLite FTS5 and queued action sync."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Default cache TTL: 24 hours (in seconds)
_DEFAULT_TTL_S = 86400.0


@dataclass
class CachedCommand:
    """A precomputed command response."""

    command: str
    response: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"command": self.command, "response": self.response, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CachedCommand:
        return cls(command=d["command"], response=d["response"], timestamp=d.get("timestamp", 0.0))

    def serialize(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def deserialize(cls, data: str) -> CachedCommand:
        return cls.from_dict(json.loads(data))


class OfflineCache:
    """SQLite-backed offline cache with FTS5 fuzzy matching and TTL."""

    def __init__(self, db_path: str = ":memory:", ttl_s: float = _DEFAULT_TTL_S) -> None:
        self.db_path = db_path
        self._ttl_s = ttl_s
        self._conn: sqlite3.Connection = sqlite3.connect(
            db_path,
            check_same_thread=False,
        )  # persistent; closed in close()
        self._setup_schema()
        self._queued_actions: list[dict[str, Any]] = []

    def _setup_schema(self) -> None:
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS commands (
                    command TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            # FTS5 virtual table for fuzzy search
            self._fts_available = False
            try:
                self._conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS commands_fts
                    USING fts5(command, response, content='commands', content_rowid='rowid')
                """)
                # Triggers to keep FTS5 in sync with the commands table
                self._conn.executescript("""
                    CREATE TRIGGER IF NOT EXISTS commands_ai AFTER INSERT ON commands BEGIN
                        INSERT INTO commands_fts(rowid, command, response)
                        VALUES (new.rowid, new.command, new.response);
                    END;
                    CREATE TRIGGER IF NOT EXISTS commands_ad AFTER DELETE ON commands BEGIN
                        INSERT INTO commands_fts(commands_fts, rowid, command, response)
                        VALUES ('delete', old.rowid, old.command, old.response);
                    END;
                    CREATE TRIGGER IF NOT EXISTS commands_au AFTER UPDATE ON commands BEGIN
                        INSERT INTO commands_fts(commands_fts, rowid, command, response)
                        VALUES ('delete', old.rowid, old.command, old.response);
                        INSERT INTO commands_fts(rowid, command, response)
                        VALUES (new.rowid, new.command, new.response);
                    END;
                """)
                self._fts_available = True
            except sqlite3.OperationalError:
                pass  # FTS5 not available

    def precompute(self, commands: list[CachedCommand]) -> None:
        """Store precomputed command responses."""
        with self._conn:
            for cmd in commands:
                self._conn.execute(
                    "INSERT OR REPLACE INTO commands (command, response, timestamp) VALUES (?, ?, ?)",
                    (cmd.command, cmd.response, cmd.timestamp),
                )

    def lookup(self, query: str) -> CachedCommand | None:
        """Fuzzy lookup using FTS5 with TTL enforcement.

        Expired entries are cleaned up lazily during lookup.
        """
        # Clean up expired entries periodically
        self._cleanup_expired()

        row = None
        if self._fts_available:
            try:
                with self._conn:
                    row = self._conn.execute(
                        "SELECT command, response, timestamp FROM commands_fts WHERE command MATCH ? LIMIT 1",
                        (query,),
                    ).fetchone()
            except sqlite3.OperationalError:
                row = None  # Fall through to exact match

        if row is None:
            with self._conn:
                row = self._conn.execute(
                    "SELECT command, response, timestamp FROM commands WHERE command = ? LIMIT 1",
                    (query,),
                ).fetchone()

        if row:
            # TTL check: reject stale entries
            if time.time() - row[2] > self._ttl_s:
                return None
            return CachedCommand(command=row[0], response=row[1], timestamp=row[2])
        return None

    def _cleanup_expired(self) -> None:
        """Remove entries older than TTL."""
        cutoff = time.time() - self._ttl_s
        try:
            with self._conn:
                self._conn.execute("DELETE FROM commands WHERE timestamp < ?", (cutoff,))
        except sqlite3.Error:
            # ROBUSTNESS FIX: this caught only OperationalError, but
            # _cleanup_expired() is the FIRST thing lookup() does, and lookup()
            # is the offline path -- the one that has to work when nothing else
            # can. A corrupt cache file (sqlite3.DatabaseError) or a closed
            # connection (sqlite3.ProgrammingError) therefore propagated out of
            # a step documented as lazy best-effort cleanup and took the whole
            # offline lookup down with it. Cleanup must never be able to fail a
            # lookup, so every sqlite3 error is contained here.
            # OBSERVABILITY FIX: this used to swallow the error outright, so a
            # locked or corrupt cache DB meant expired rows were NEVER pruned
            # and the offline cache grew without bound, with nothing anywhere
            # saying why. Cleanup stays best-effort (control flow unchanged) --
            # but the failure is now visible.
            logger.warning("Offline cache cleanup failed", exc_info=True)

    def queue_action(self, action: dict[str, Any]) -> None:
        """Queue an action for sync when reconnected."""
        action["queued_at"] = time.time()
        self._queued_actions.append(action)

    def sync_queued_actions(self) -> list[dict[str, Any]]:
        """Return and clear queued actions for replay."""
        actions = list(self._queued_actions)
        self._queued_actions.clear()
        return actions

    def serialize(self) -> str:
        with self._conn:
            rows = self._conn.execute(
                "SELECT command, response, timestamp FROM commands",
            ).fetchall()
        data = [{"command": r[0], "response": r[1], "timestamp": r[2]} for r in rows]
        return json.dumps({"commands": data, "queued": self._queued_actions})

    def deserialize(self, data: str) -> None:
        obj = json.loads(data)
        cmds = [CachedCommand.from_dict(d) for d in obj.get("commands", [])]
        self.precompute(cmds)
        self._queued_actions = obj.get("queued", [])

    def close(self) -> None:
        self._conn.close()
