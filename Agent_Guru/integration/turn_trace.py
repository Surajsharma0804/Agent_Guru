"""A record of every voice turn: what was heard, what was done, what was said, and how long each stage took.

Before this, main.py logged a turn's PipelineResult and dropped it. Nothing
kept per-stage timings, the action's verified status or the spoken reply,
and the per-turn audit event went to an in-memory database that was gone
when the app exited. So "which stage made that answer slow" or "what did it
say when the close failed" could only be answered by re-running the turn
with a scratch script and searching the log.

One row per turn in ``turns``, one row per stage in ``turn_stages``, and a
full-text index over what was heard and said. Each call opens and closes its
own connection (utils.sqlite.open_sqlite): turns are recorded from worker
threads, and a connection held open would keep the file locked on Windows
for as long as the app runs.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from Agent_Guru.utils.secure_file import restrict_file_permissions
from Agent_Guru.utils.sqlite import open_sqlite

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS turns (
        turn_id       TEXT PRIMARY KEY,
        started_at    REAL NOT NULL,
        seconds       REAL NOT NULL,
        personality   TEXT NOT NULL,
        heard         TEXT NOT NULL,
        said          TEXT NOT NULL,
        intent        TEXT,
        action_status TEXT,
        outcome       TEXT,
        model         TEXT NOT NULL,
        rating        REAL,
        details       TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS turn_stages (
        turn_id    TEXT NOT NULL REFERENCES turns(turn_id),
        position   INTEGER NOT NULL,
        name       TEXT NOT NULL,
        started_at REAL NOT NULL,
        seconds    REAL NOT NULL,
        detail     TEXT NOT NULL,
        PRIMARY KEY (turn_id, position)
    )""",
    "CREATE INDEX IF NOT EXISTS turns_by_time ON turns(started_at)",
    """CREATE VIRTUAL TABLE IF NOT EXISTS turn_text
        USING fts5(heard, said, content='turns', content_rowid='rowid')""",
    """CREATE TRIGGER IF NOT EXISTS turn_text_add AFTER INSERT ON turns BEGIN
        INSERT INTO turn_text(rowid, heard, said) VALUES (new.rowid, new.heard, new.said);
    END""",
)


@dataclass(slots=True)
class StageTiming:
    """One stage of a turn and how long it took, with whatever it is useful to know about its result."""

    name: str
    started_at: float
    seconds: float
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TurnRecord:
    """One voice turn.

    outcome is "success", "failure", or None when that is not known: an
    answer that may or may not have been right, an action that could not be
    confirmed, refused or cancelled.
    """

    started_at: float
    seconds: float
    personality: str
    heard: str
    said: str = ""
    intent: str | None = None
    action_status: str | None = None
    outcome: str | None = None
    model: str = ""
    stages: list[StageTiming] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    rating: float | None = None
    turn_id: str = field(default_factory=lambda: uuid.uuid4().hex)


class TurnTraceStore:
    """The turn records on disk."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open_sqlite(self.path) as conn:
            for statement in _SCHEMA:
                conn.execute(statement)
        # Transcripts and replies are personal, as they are in memory.db.
        restrict_file_permissions(self.path)

    def record(self, turn: TurnRecord) -> None:
        """Store one turn. A second record with the same turn_id raises sqlite3.IntegrityError."""
        with open_sqlite(self.path) as conn:
            conn.execute(
                "INSERT INTO turns VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    turn.turn_id, turn.started_at, turn.seconds, turn.personality, turn.heard, turn.said,
                    turn.intent, turn.action_status, turn.outcome, turn.model, turn.rating,
                    json.dumps(turn.details),
                ),
            )
            conn.executemany(
                "INSERT INTO turn_stages VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (turn.turn_id, i, s.name, s.started_at, s.seconds, json.dumps(s.detail))
                    for i, s in enumerate(turn.stages)
                ],
            )

    def get(self, turn_id: str) -> TurnRecord | None:
        """The turn with this id, or None."""
        found = self._load("WHERE turn_id = ?", [turn_id], limit=1)
        return found[0] if found else None

    def recent(
        self,
        *,
        limit: int = 50,
        personality: str | None = None,
        outcome: str | None = None,
        since: float | None = None,
    ) -> list[TurnRecord]:
        """The latest turns first, optionally only one personality's, one outcome's, or those after *since*."""
        conditions, values = [], []
        if personality is not None:
            conditions.append("personality = ?")
            values.append(personality)
        if outcome is not None:
            conditions.append("outcome = ?")
            values.append(outcome)
        if since is not None:
            conditions.append("started_at >= ?")
            values.append(since)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return self._load(where, values, limit=limit)

    def count(self) -> int:
        with open_sqlite(self.path) as conn:
            return conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]

    def find(self, words: str, *, limit: int = 20) -> list[TurnRecord]:
        """Turns whose heard or said text contains any of *words*, best match first.

        Each word is quoted before it reaches FTS5, so quotes, OR or
        brackets in what the user typed are searched for as text, not run as
        query syntax.
        """
        terms = re.findall(r"\w+", words)
        if not terms:
            return []
        match = " OR ".join(f'"{t}"' for t in terms)
        with open_sqlite(self.path) as conn:
            ids = [
                row[0]
                for row in conn.execute(
                    "SELECT turns.turn_id FROM turn_text JOIN turns ON turns.rowid = turn_text.rowid "
                    "WHERE turn_text MATCH ? ORDER BY rank LIMIT ?",
                    (match, limit),
                )
            ]
        return [t for t in (self.get(i) for i in ids) if t is not None]

    def stage_summary(self, *, since: float | None = None) -> dict[str, dict[str, float]]:
        """For each stage: how many turns ran it, and its median and 95th-percentile seconds.

        Nearest-rank percentiles over the recorded values, so with few turns
        the p95 is simply the slowest one, not an interpolated guess.
        """
        query = "SELECT s.name, s.seconds FROM turn_stages s JOIN turns t ON t.turn_id = s.turn_id"
        values: list[Any] = []
        if since is not None:
            query += " WHERE t.started_at >= ?"
            values.append(since)
        by_stage: dict[str, list[float]] = {}
        with open_sqlite(self.path) as conn:
            for name, seconds in conn.execute(query, values):
                by_stage.setdefault(name, []).append(seconds)
        summary = {}
        for name, seconds in by_stage.items():
            seconds.sort()
            summary[name] = {
                "count": len(seconds),
                "median_s": seconds[(len(seconds) - 1) // 2],
                "p95_s": seconds[max(0, -(-len(seconds) * 95 // 100) - 1)],
            }
        return summary

    def outcome_counts(self, *, since: float | None = None) -> dict[str, int]:
        """How many turns ended in success, failure, or unknown ("unknown" for None)."""
        query = "SELECT COALESCE(outcome, 'unknown'), COUNT(*) FROM turns"
        values: list[Any] = []
        if since is not None:
            query += " WHERE started_at >= ?"
            values.append(since)
        query += " GROUP BY 1"
        with open_sqlite(self.path) as conn:
            return dict(conn.execute(query, values).fetchall())

    def rate(self, turn_id: str, score: float) -> bool:
        """Give a turn a quality score in [0, 1]; False if there is no such turn."""
        if not 0.0 <= score <= 1.0:
            msg = f"rating must be between 0 and 1, not {score}"
            raise ValueError(msg)
        with open_sqlite(self.path) as conn:
            return conn.execute("UPDATE turns SET rating = ? WHERE turn_id = ?", (score, turn_id)).rowcount > 0

    def _load(self, where: str, values: list[Any], *, limit: int) -> list[TurnRecord]:
        # where is built only from the fixed conditions in recent() and get();
        # every value is a bound parameter.
        query = f"SELECT * FROM turns {where} ORDER BY started_at DESC LIMIT ?"  # nosec B608  # noqa: S608
        with open_sqlite(self.path) as conn:
            rows = conn.execute(query, [*values, limit]).fetchall()
            turns = []
            for row in rows:
                stages = [
                    StageTiming(name=s[0], started_at=s[1], seconds=s[2], detail=json.loads(s[3]))
                    for s in conn.execute(
                        "SELECT name, started_at, seconds, detail FROM turn_stages "
                        "WHERE turn_id = ? ORDER BY position",
                        (row[0],),
                    )
                ]
                turns.append(TurnRecord(
                    turn_id=row[0], started_at=row[1], seconds=row[2], personality=row[3], heard=row[4],
                    said=row[5], intent=row[6], action_status=row[7], outcome=row[8], model=row[9],
                    rating=row[10], details=json.loads(row[11]), stages=stages,
                ))
        return turns
