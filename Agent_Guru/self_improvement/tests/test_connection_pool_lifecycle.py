"""Lifecycle tests for ConnectionPool.close_all and release (issue #4).

close_all() used to drain only the idle queue, so any connection a caller
still held stayed open. Linux and macOS hide that; Windows refuses to delete
the database file and fails teardown. Each test here fails against the
original implementation.
"""

import logging
import os
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from Agent_Guru.self_improvement.connection_pool import ConnectionPool


def _open_handles_to(path: Path) -> int:
    """Count file descriptors in this process that point at ``path``."""
    target = str(path.resolve())
    count = 0
    for fd in os.listdir("/proc/self/fd"):
        try:
            if os.readlink(f"/proc/self/fd/{fd}") == target:
                count += 1
        except OSError:
            continue
    return count


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "pool.db"


class TestCloseAllReachesCheckedOutConnections:
    def test_checked_out_connection_is_closed(self, db_path):
        pool = ConnectionPool(str(db_path), min_size=1, max_size=3, timeout=0.05)
        held = pool.acquire()

        pool.close_all()

        with pytest.raises(sqlite3.ProgrammingError):
            held.connection.execute("SELECT 1")

    @pytest.mark.skipif(not Path("/proc/self/fd").is_dir(), reason="needs /proc")
    def test_no_file_handle_left_open(self, db_path):
        # This is the Windows teardown failure, observed directly.
        pool = ConnectionPool(str(db_path), min_size=2, max_size=3, timeout=0.05)
        pool.acquire()
        assert _open_handles_to(db_path) > 0

        pool.close_all()

        assert _open_handles_to(db_path) == 0

    def test_waits_for_in_flight_release(self, db_path, caplog):
        pool = ConnectionPool(str(db_path), min_size=1, max_size=3, timeout=5.0)
        held = pool.acquire()

        def finish_work():
            time.sleep(0.2)
            pool.release(held)

        worker = threading.Thread(target=finish_work)
        worker.start()
        started = time.monotonic()
        with caplog.at_level(logging.WARNING):
            pool.close_all()
        elapsed = time.monotonic() - started
        worker.join()

        # It waited for the release rather than returning at once or
        # sitting out the full 5s timeout, and nothing was force-closed.
        assert 0.15 <= elapsed < 4.0
        assert "force-closing" not in caplog.text
        with pytest.raises(sqlite3.ProgrammingError):
            held.connection.execute("SELECT 1")

    def test_force_close_after_timeout_is_logged(self, db_path, caplog):
        pool = ConnectionPool(str(db_path), min_size=1, max_size=3, timeout=0.05)
        pool.acquire()
        pool.acquire()

        with caplog.at_level(logging.WARNING):
            pool.close_all()

        assert "force-closing 2 connection(s)" in caplog.text


class TestClosedPoolStaysClosed:
    def test_release_during_close_does_not_repopulate(self, db_path):
        pool = ConnectionPool(str(db_path), min_size=1, max_size=3, timeout=5.0)
        held = pool.acquire()
        worker = threading.Thread(target=lambda: (time.sleep(0.1), pool.release(held)))
        worker.start()

        pool.close_all()
        worker.join()

        assert pool.get_stats().idle_connections == 0
        with pytest.raises(sqlite3.ProgrammingError):
            held.connection.execute("SELECT 1")

    def test_acquire_after_close_raises_immediately(self, db_path):
        # Refuse up front rather than waiting out the queue timeout and
        # opening a fresh connection only to throw it away.
        pool = ConnectionPool(str(db_path), min_size=1, max_size=3, timeout=2.0)
        pool.close_all()

        started = time.monotonic()
        with pytest.raises(RuntimeError, match="closed"):
            pool.acquire()
        assert time.monotonic() - started < 0.5

    def test_acquire_racing_close_does_not_leak(self, db_path, monkeypatch):
        # An acquire() already past its entry check when close_all() runs
        # must not hand a live connection out of a closed pool.
        pool = ConnectionPool(str(db_path), min_size=0, max_size=3, timeout=0.05)
        creating = threading.Event()
        proceed = threading.Event()
        created = []
        real_create = pool._create_connection_unlocked

        def slow_create():
            creating.set()
            proceed.wait(5)
            conn = real_create()
            created.append(conn)
            return conn

        monkeypatch.setattr(pool, "_create_connection_unlocked", slow_create)
        outcome = []

        def racer():
            try:
                outcome.append(pool.acquire())
            except RuntimeError as exc:
                outcome.append(exc)

        worker = threading.Thread(target=racer)
        worker.start()
        assert creating.wait(5)
        pool.close_all()
        proceed.set()
        worker.join(5)

        assert isinstance(outcome[0], RuntimeError)
        with pytest.raises(sqlite3.ProgrammingError):
            created[0].connection.execute("SELECT 1")


class TestConnectionCount:
    def test_count_stays_exact_when_acquire_races_close(self, db_path, monkeypatch):
        # _total_connections gates creation against max_size, so it must
        # equal the connections the pool actually has open. Zeroing it in
        # close_all() while an acquire() still held a reserved slot drove it
        # to -1 once that acquire closed its connection.
        pool = ConnectionPool(str(db_path), min_size=2, max_size=3, timeout=0.05)
        pool.acquire()
        pool.acquire()
        creating = threading.Event()
        proceed = threading.Event()
        real_create = pool._create_connection_unlocked

        def slow_create():
            creating.set()
            proceed.wait(5)
            return real_create()

        monkeypatch.setattr(pool, "_create_connection_unlocked", slow_create)
        worker = threading.Thread(target=lambda: pytest.raises(RuntimeError, pool.acquire))
        worker.start()
        assert creating.wait(5)
        pool.close_all(timeout=0)
        proceed.set()
        worker.join(5)

        assert pool.get_stats().total_connections == 0
