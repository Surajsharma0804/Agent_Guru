"""Startup loads the memory embedding model on a worker thread, not inside the first turn.

It loaded on first use, inside the first turn's memory stage, which waits 5 s and then answers
without memory: the first "what time is it" after a start took 13.2 s (1.5 s warm) and recalled
nothing. Runs in a fresh interpreter, as importing main.py rewraps stdout.
"""

from __future__ import annotations

import subprocess  # nosec B404 - this interpreter on a fixed script
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

_SCRIPT = """
import asyncio, threading
import main
from Agent_Guru.memory import memory_manager

loaded = []
memory_manager._get_real_embedder = lambda: loaded.append(threading.current_thread() is not threading.main_thread())

async def start():
    await main._start_memory_warmup(asyncio.get_running_loop())

asyncio.run(start())
print("LOADED", loaded)
"""


def test_startup_loads_the_embedding_model_off_the_event_loop_thread():
    done = subprocess.run([sys.executable, "-c", _SCRIPT], cwd=ROOT, capture_output=True, text=True,  # noqa: S603  # nosec B603
                          timeout=240, check=False)
    assert "LOADED [True]" in done.stdout, done.stdout[-500:] + done.stderr[-1500:]  # nosec B101
