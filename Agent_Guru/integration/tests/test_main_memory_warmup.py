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


def _calls_in_run() -> list[tuple[int, str]]:
    """(line, name) of every call in main.run(), in source order, read without importing main.py."""
    import ast

    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8-sig"))  # main.py starts with a BOM
    run = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "run")
    found = []
    for node in ast.walk(run):
        if isinstance(node, ast.Call):
            f = node.func
            found.append((node.lineno, f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")))
    return sorted(found)


def test_the_preload_starts_before_the_subsystems_start():
    # It started after orch.startup() and the Whisper tiny pre-warm, about 20 s into a 24 s start,
    # and was ready about 10 s after "Listening": a question asked then waited out the 5 s memory
    # budget (median 5.007 s over 10 cold starts) and recalled nothing in 6 of 10.
    calls = _calls_in_run()
    warmup = [line for line, name in calls if name == "_start_memory_warmup"]
    startup = [line for line, name in calls if name == "startup"]
    memory = [line for line, name in calls if name == "_load_memory"]
    assert len(warmup) == 1 and startup and memory  # nosec B101
    assert memory[0] < warmup[0] < startup[0]  # nosec B101


_READY_SCRIPT = """
import asyncio, logging
import main
from Agent_Guru.memory import memory_manager

records = []
class Keep(logging.Handler):
    def emit(self, record):
        records.append((record.levelname, record.getMessage()))
main.logger.addHandler(Keep())
main.logger.setLevel(logging.INFO)
memory_manager._get_real_embedder = {embedder}

async def start():
    await main._start_memory_warmup(asyncio.get_running_loop())

asyncio.run(start())
print("RECORDS", [r for r in records if "embedding model" in r[1]])
"""


def _run_warmup(embedder: str) -> str:
    done = subprocess.run([sys.executable, "-c", _READY_SCRIPT.format(embedder=embedder)], cwd=ROOT,  # noqa: S603  # nosec B603
                          capture_output=True, text=True, timeout=240, check=False)
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-1500:]  # nosec B101
    return next(line for line in done.stdout.splitlines() if line.startswith("RECORDS"))


def test_the_preload_says_when_the_model_is_ready():
    # Nothing was logged when the preload finished, so a slow first turn could not be told apart
    # from a preload still running.
    records = _run_warmup("lambda: object()")
    assert "'INFO', 'Memory embedding model ready after" in records  # nosec B101


def test_a_failed_preload_warns_and_does_not_stop_startup():
    records = _run_warmup("lambda: (_ for _ in ()).throw(RuntimeError('weights unreadable'))")
    assert "'WARNING', 'Memory embedding model did not preload (weights unreadable)" in records  # nosec B101
    assert "ready after" not in records  # nosec B101


def test_no_ready_line_when_memory_falls_back_to_the_stub():
    # _get_real_embedder() returns None when sentence-transformers is missing and has already
    # warned; a "ready" line then would claim a model that is not there.
    records = _run_warmup("lambda: None")
    assert "ready after" not in records  # nosec B101
