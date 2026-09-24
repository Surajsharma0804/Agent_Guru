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
