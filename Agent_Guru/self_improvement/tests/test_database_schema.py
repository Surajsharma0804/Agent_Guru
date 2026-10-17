"""Tests for DatabaseSchema.create_schema.

create_schema() used to run its 36 CREATE statements without a
transaction, because sqlite3 opens none implicitly for DDL. Each
statement committed on its own: 144 fsyncs per call, 91 ms on a new file
on the development machine, and on CI runners enough to time out property
tests that build a schema per example. A failure part-way through also
left the tables created so far in the file.
"""

import sqlite3

import pytest

from Agent_Guru.self_improvement.database_schema import DatabaseSchema


def _tables(db_path) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    finally:
        conn.close()
    return {name for (name,) in rows}


def test_a_failure_part_way_leaves_no_tables(tmp_path, monkeypatch):
    """The schema is created whole or not at all."""
    db_path = tmp_path / "schema.db"

    def fail(_cursor):
        raise RuntimeError("index creation failed")

    monkeypatch.setattr(DatabaseSchema, "_create_indexes", staticmethod(fail))

    with pytest.raises(RuntimeError, match="index creation failed"):
        DatabaseSchema.create_schema(str(db_path))

    # Before the fix the nine tables created ahead of the indexes stayed.
    assert _tables(db_path) == set()  # nosec B101
    assert DatabaseSchema.verify_schema(str(db_path)) is False  # nosec B101


def test_a_complete_schema_verifies_and_can_be_created_again(tmp_path):
    """One transaction must not change what is created, or break a rerun."""
    db_path = str(tmp_path / "schema.db")

    DatabaseSchema.create_schema(db_path)
    DatabaseSchema.create_schema(db_path)

    assert DatabaseSchema.verify_schema(db_path) is True  # nosec B101
    assert DatabaseSchema.get_schema_version(db_path) == DatabaseSchema.SCHEMA_VERSION  # nosec B101
    conn = sqlite3.connect(db_path)
    try:
        indexes = conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert indexes == 26  # nosec B101
