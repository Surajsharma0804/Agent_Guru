"""After a clean shutdown the process ends, even if a library thread is still running.

`service stop` asked the assistant to stop; its shutdown finished within a
second, but a non-daemon thread (aiosqlite's connection worker, the memory's
open connection) kept the interpreter alive until the command ended it 30 s
later. Runs in a fresh interpreter, as importing main.py rewraps stdout.
"""

from __future__ import annotations

import subprocess  # nosec B404 - this interpreter on a fixed script
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

_LINGERING = """
import threading, time
import main
threading.Thread(target=time.sleep, args=(60,), name="stuck-worker").start()
main._exit_after_clean_shutdown(grace_s=0.5)
print("returned")
"""

_CLEAN = """
import main
main._exit_after_clean_shutdown(grace_s=0.5)
print("returned")
"""


def _run(script: str) -> tuple[subprocess.CompletedProcess[str], float]:
    started = time.monotonic()
    done = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True,  # nosec B603
                          timeout=120, check=False)
    return done, time.monotonic() - started


def test_a_lingering_thread_does_not_keep_the_process_alive():
    done, _ = _run(_LINGERING)
    # Exited from the helper (no "returned"), well before the thread's 60 s.
    assert done.returncode == 0 and "returned" not in done.stdout  # nosec B101
    assert "stuck-worker" in done.stdout + done.stderr  # nosec B101  the thread is named in the log


def test_with_nothing_left_running_it_simply_returns():
    done, _ = _run(_CLEAN)
    assert done.returncode == 0 and "returned" in done.stdout  # nosec B101


_SLOW_TEARDOWN = """
import asyncio, time
import main

class SlowNativeTeardown:
    # Stands in for a Whisper model: CTranslate2's destructor joined its thread pool.
    def __del__(self):
        time.sleep(30)

async def fake_run():
    model = SlowNativeTeardown()
    # Stands in for a transcription of overheard speech still running when Ctrl+C came.
    asyncio.get_running_loop().run_in_executor(None, time.sleep, 30)
    print("goodbye", flush=True)
    main._end_without_native_teardown()

main.run = fake_run
main.main()
"""


def test_a_clean_shutdown_ends_without_waiting_on_threads_or_teardown():
    # Ctrl+C took 12 to 18 s to give the console back after "Goodbye": the models' destructors
    # and asyncio.run's wait for jobs still on its worker threads.
    done, seconds = _run(_SLOW_TEARDOWN)
    assert done.returncode == 0 and "goodbye" in done.stdout and seconds < 15, (seconds, done.stderr[-800:])  # nosec B101
