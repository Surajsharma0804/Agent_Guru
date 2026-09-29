"""Every SQLite connection self_improvement opens must be closed.

`with sqlite3.connect(path) as conn:` only ends the transaction; the
connection stays open until garbage collection. On Windows that keeps the
database file locked: 149 self_improvement tests errored at teardown with
WinError 32 because their temporary database could not be deleted, and the
running engine held the same handles.

Deleting the file would only fail on Windows, so these tests track closes
directly: sqlite3.connect is wrapped to hand out a connection subclass that
records close(), and each module's real operations must leave nothing open.
That fails the same way on every platform.
"""

from __future__ import annotations

import sqlite3

import pytest

from Agent_Guru.utils.sqlite import open_sqlite


class _Tracked(sqlite3.Connection):
    closed = False

    def close(self) -> None:
        self.closed = True
        super().close()


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[_Tracked]:
    connections: list[_Tracked] = []
    real_connect = sqlite3.connect

    def connect(*args, **kwargs):
        kwargs.setdefault("factory", _Tracked)
        conn = real_connect(*args, **kwargs)
        connections.append(conn)
        return conn

    monkeypatch.setattr(sqlite3, "connect", connect)
    return connections


@pytest.fixture
def db(tmp_path, opened) -> str:
    from Agent_Guru.self_improvement.database_schema import DatabaseSchema

    path = str(tmp_path / "si.db")
    DatabaseSchema.create_schema(path)
    return path


def _left_open(opened: list[_Tracked]) -> int:
    return sum(1 for conn in opened if not conn.closed)


class TestOpenSqlite:
    def test_commits_and_closes(self, tmp_path, opened):
        path = tmp_path / "t.db"
        with open_sqlite(path) as conn:
            conn.execute("create table t(a)")
            conn.execute("insert into t values (1)")
        with open_sqlite(path) as conn:
            count = conn.execute("select count(*) from t").fetchone()[0]

        assert count == 1
        assert _left_open(opened) == 0

    def test_rolls_back_on_error_and_still_closes(self, tmp_path, opened):
        path = tmp_path / "t.db"
        with open_sqlite(path) as conn:
            conn.execute("create table t(a)")

        def insert_then_fail() -> None:
            with open_sqlite(path) as conn:
                conn.execute("insert into t values (1)")
                raise RuntimeError

        with pytest.raises(RuntimeError):
            insert_then_fail()
        with open_sqlite(path) as conn:
            count = conn.execute("select count(*) from t").fetchone()[0]

        assert count == 0
        assert _left_open(opened) == 0


class TestSelfImprovementModulesCloseTheirConnections:
    def test_schema(self, db, opened):
        from Agent_Guru.self_improvement.database_schema import DatabaseSchema

        assert DatabaseSchema.verify_schema(db)
        DatabaseSchema.get_schema_version(db)

        assert opened
        assert _left_open(opened) == 0

    def test_meta_learner(self, db, opened):
        """The engine's path: executions in, patterns out."""
        from datetime import UTC, datetime
        from types import SimpleNamespace

        from Agent_Guru.self_improvement.meta_learner import MetaLearner

        learner = MetaLearner(db)
        for i in range(12):
            learner.process_execution(SimpleNamespace(
                task_id=f"task_{i}", task_type="test_task", strategy_id="strategy_1",
                success=i % 3 != 0, execution_time_ms=100.0 + i, context={"key": "value"},
                error_details={}, timestamp=datetime.now(tz=UTC),
            ))
        learner.update_patterns()
        learner.analyze_feature_correlations()

        assert _left_open(opened) == 0

    def test_health_checker(self, db, opened):
        from Agent_Guru.self_improvement.health_check import HealthChecker

        checker = HealthChecker(db)
        checker.check_health()
        checker.get_metrics()

        assert _left_open(opened) == 0

    def test_improvement_monitor(self, db, opened):
        from Agent_Guru.self_improvement.monitoring import ImprovementMonitor

        monitor = ImprovementMonitor(db)
        monitor.check_all()
        monitor.get_dashboard_metrics()

        assert _left_open(opened) == 0

    def test_migration_system(self, db, opened):
        from Agent_Guru.self_improvement.migrations import MigrationSystem

        system = MigrationSystem(db)
        system.migrate_to_latest()
        system.get_applied_migrations()

        assert _left_open(opened) == 0
