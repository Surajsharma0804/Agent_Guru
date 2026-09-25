"""Open a SQLite connection that is committed and always closed.

``with sqlite3.connect(path) as conn:`` reads as if it closes the connection,
but sqlite3's context manager only commits or rolls back the transaction. The
connection stays open until the object is garbage collected, and on Windows
an open connection keeps the database file locked. Measured: calling
DatabaseSchema.create_schema(), which used that form, and then deleting its
folder failed with WinError 32 in 20 of 20 tries, and 149 self_improvement
tests errored at teardown for that reason.

The opposite mistake, contextlib.closing(sqlite3.connect(path)), closes the
connection but never commits, so writes made inside it are discarded;
deployment/crypto_verifier.py lost every trusted-key write that way. This
helper does both: commit on success, roll back on any error, close always.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@contextmanager
def open_sqlite(path: str | Path, **connect_kwargs: Any) -> Iterator[sqlite3.Connection]:
    """Yield a connection to *path*; commit on success, roll back on error, always close."""
    conn = sqlite3.connect(str(path), **connect_kwargs)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
