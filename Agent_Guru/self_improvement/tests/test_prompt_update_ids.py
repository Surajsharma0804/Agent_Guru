"""Two prompt updates recorded within one clock tick both get stored.

The update id was "update_<type>_<timestamp>". Windows reads the wall clock in steps of about
15.6 ms, so two updates in one step got the same id and the second insert raised IntegrityError
("UNIQUE constraint failed: prompt_updates.update_id"): 15 to 19 tests in test_prompt_evolution.py
failed that way on the Windows py3.12 CI legs, and the owner's second registration was lost. Here the
clock is frozen, so the same tick happens on any machine.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

import Agent_Guru.self_improvement.prompt_evolution as prompt_evolution
from Agent_Guru.self_improvement.connection_pool import ConnectionPool
from Agent_Guru.self_improvement.database_schema import DatabaseSchema
from Agent_Guru.self_improvement.prompt_evolution import PromptEvolutionSystem


class _FrozenClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 11, 1, 12, 0, 0, tzinfo=tz or UTC)


@pytest.fixture
def system(tmp_path):
    db = Path(tmp_path) / "test.db"
    DatabaseSchema.create_schema(str(db))
    pool = ConnectionPool(str(db), min_size=1, max_size=2)
    yield PromptEvolutionSystem(pool, min_update_interval_seconds=0.0), db
    pool.close_all()


def test_two_updates_in_one_clock_tick_are_both_recorded(system, monkeypatch):
    evolution, db = system
    monkeypatch.setattr(prompt_evolution, "datetime", _FrozenClock)
    evolution.register_prompt(prompt_type="task_analysis", content="Version 1 text", version=1)
    evolution.register_prompt(prompt_type="task_analysis", content="Version 2 text", version=2)
    with sqlite3.connect(db) as conn:
        ids = [r[0] for r in conn.execute("select update_id from prompt_updates")]
    assert len(ids) == 2 and len(set(ids)) == 2  # nosec B101
