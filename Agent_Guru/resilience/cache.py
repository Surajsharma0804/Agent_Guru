"""Offline cache with SQLite FTS5 and queued action sync."""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CachedCommand:
    """A precomputed command response."""
    command: str
    response: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"command": self.command, "response": self.response, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CachedCommand":
        return cls(command=d["command"], response=d["response"], timestamp=d.get("timestamp", 0.0))

    def serialize(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def deserialize(cls, data: str) -> "CachedCommand":
        return cls.from_dict(json.loads(data))


class OfflineCache:
    """SQLite-backed offline cache with FTS5 fuzzy matching."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._setup_schema()
        self._queued_actions: list[dict[str, Any]] = []

    def _setup_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS commands (
                command TEXT PRIMARY KEY,
                response TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        # FTS5 virtual table for fuzzy search
        try:
            self._conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS commands_fts
                USING fts5(command, response, content='commands', content_rowid='rowid')
            """)
        except sqlite3.OperationalError:
            pass  # FTS5 not available
        self._conn.commit()

    def precompute(self, commands: list[CachedCommand]) -> None:
        """Store precomputed command responses."""
        for cmd in commands:
            self._conn.execute(
                "INSERT OR REPLACE INTO commands (command, response, timestamp) VALUES (?, ?, ?)",
                (cmd.command, cmd.response, cmd.timestamp),
            )
        self._conn.commit()

    def lookup(self, query: str) -> Optional[CachedCommand]:
        """Fuzzy lookup using FTS5."""
        try:
            row = self._conn.execute(
                "SELECT command, response, timestamp FROM commands_fts WHERE command MATCH ? LIMIT 1",
                (query,),
            ).fetchone()
        except sqlite3.OperationalError:
            # Fallback to exact match
            row = self._conn.execute(
                "SELECT command, response, timestamp FROM commands WHERE command = ? LIMIT 1",
                (query,),
            ).fetchone()
        if row:
            return CachedCommand(command=row[0], response=row[1], timestamp=row[2])
        return None

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
        rows = self._conn.execute(
            "SELECT command, response, timestamp FROM commands"
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
