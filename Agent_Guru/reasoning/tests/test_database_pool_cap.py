"""DatabasePool never has more than max_size connections in use, however many callers overlap (issue #11).

acquire() checked len(_in_use) < max_size and opened the connection in one lock block, but added it to
_in_use only in a later one. Every caller that reached the check before the first added its
connection saw room and opened another: six overlapping callers of a max_size=2 pool held six
connections at once. The callers here overlap on asyncio sleeps, so nothing depends on how fast the
machine is.
"""

from __future__ import annotations

import asyncio

from Agent_Guru.reasoning.utils.connection_pool import DatabasePool


async def test_six_overlapping_callers_never_exceed_max_size(tmp_path):
    pool = DatabasePool(str(tmp_path / "pool.db"), min_size=0, max_size=2, timeout=10.0)
    opened, peak = [0], [0]
    real_open = pool._create_connection

    async def counting_open():
        opened[0] += 1
        return await real_open()

    pool._create_connection = counting_open

    async def caller():
        async with pool.acquire() as conn:
            peak[0] = max(peak[0], len(pool._in_use))
            conn.execute("select 1")
            await asyncio.sleep(0.05)

    try:
        await asyncio.gather(*(caller() for _ in range(6)))
    finally:
        await pool.close()
    assert peak[0] <= 2 and opened[0] <= 2, f"peak in use {peak[0]}, opened {opened[0]}"  # nosec B101
