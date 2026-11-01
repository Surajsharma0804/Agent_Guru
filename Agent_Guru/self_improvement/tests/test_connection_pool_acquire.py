"""ConnectionPool.acquire() opens a connection when it may, and a failed open gives its slot back (issue #11).

1. With the idle queue empty and the pool below max_size, acquire() waited the whole timeout on the
   queue (5 s by default) before it looked at whether it could open a connection: a second caller of
   a min_size=1 pool waited 5.002 s for a connection the pool could have opened at once.
2. The empty-queue path reserved a slot (_total_connections += 1) and then opened the connection
   outside the lock. When the open raised, the reservation stayed, so every failed open cost one slot
   for good; after max_size failures the pool could never open a connection again.

Neither test reads a clock. The first records how acquire() called the idle queue.
"""

from __future__ import annotations

import sqlite3
from queue import Empty, Queue

import pytest

from Agent_Guru.self_improvement.connection_pool import ConnectionPool


class _RecordingQueue(Queue):
    """The pool's idle queue, recording each blocking get instead of waiting on it."""

    def __init__(self, maxsize: int = 0) -> None:
        super().__init__(maxsize)
        self.blocking_waits: list[float | None] = []

    def get(self, block: bool = True, timeout: float | None = None):
        if block and self.empty():
            self.blocking_waits.append(timeout)
            raise Empty
        return super().get(block=block, timeout=timeout)


@pytest.fixture
def pool(tmp_path):
    p = ConnectionPool(str(tmp_path / "pool.db"), min_size=1, max_size=3, timeout=5.0)
    yield p
    p.close_all()


def test_a_second_caller_gets_a_new_connection_without_waiting_on_the_queue(pool):
    recording = _RecordingQueue(maxsize=pool.max_size)
    while not pool._pool.empty():
        recording.put(pool._pool.get_nowait())
    pool._pool = recording
    first = pool.acquire()
    second = pool.acquire()  # the queue is empty now, and the pool has room for two more
    try:
        assert recording.blocking_waits == []  # nosec B101
        assert pool.get_stats().total_connections == 2  # nosec B101
    finally:
        pool.release(first)
        pool.release(second)


def test_a_failed_open_gives_its_slot_back(pool, monkeypatch):
    held = [pool.acquire()]  # empties the idle queue, so every further acquire must open
    real_open = pool._create_connection_unlocked
    failures = {"left": pool.max_size}

    def flaky_open():
        if failures["left"]:
            failures["left"] -= 1
            raise sqlite3.OperationalError("database is locked")
        return real_open()

    monkeypatch.setattr(pool, "_create_connection_unlocked", flaky_open)
    for _ in range(pool.max_size):
        with pytest.raises(sqlite3.OperationalError):
            pool.acquire(timeout=0.01)
    held.append(pool.acquire(timeout=0.01))  # the opens work again: the pool must still have room
    try:
        assert pool.get_stats().total_connections == 2  # nosec B101
    finally:
        for conn in held:
            pool.release(conn)
