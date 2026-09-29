"""PolicyStorage must close every file-database connection it opens.

_conn() used `with sqlite3.connect(...) as conn:`, which commits or rolls back
but never closes. Every policy lookup, one per voice turn, left a connection
open: construction plus 3 lookups left 4 open, and on Windows the database
folder stayed locked. A locked folder only shows on Windows, so these tests
count closes directly, which fails the same way on every platform.
"""

from __future__ import annotations

import sqlite3

import pytest

from Agent_Guru.policy.policy_storage import PolicyStorage

from .conftest import make_policy, make_role


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


def test_file_store_leaves_no_connection_open(tmp_path, opened):
    store = PolicyStorage(str(tmp_path / "policy.db"))
    store.create_role(make_role())
    store.get_all_roles()
    store.get_all_roles()

    assert len(opened) >= 4
    assert [c for c in opened if not c.closed] == []


def test_writes_still_commit_for_a_new_reader(tmp_path):
    path = str(tmp_path / "policy.db")
    policy_id = PolicyStorage(path).create_policy(make_policy())

    assert PolicyStorage(path).get_policy(policy_id) is not None


def test_a_failed_write_is_rolled_back(tmp_path):
    store = PolicyStorage(str(tmp_path / "policy.db"))
    store.create_role(make_role())

    with pytest.raises(sqlite3.Error):
        store.create_role(make_role())

    assert len(store.get_all_roles()) == 1


def test_in_memory_store_keeps_its_one_connection(opened):
    """An in-memory database lives only as long as its connection."""
    store = PolicyStorage(":memory:")
    store.create_role(make_role())

    assert len(opened) == 1
    assert [r.name for r in store.get_all_roles()] == ["TestRole"]
