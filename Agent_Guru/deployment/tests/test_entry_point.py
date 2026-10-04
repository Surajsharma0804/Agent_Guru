"""The packaged entry points start the assistant.

`python -m Agent_Guru` and the `agent-guru` console script (pyproject.toml,
Agent_Guru.__main__:_run) imported `main` from main.py, which only had
`run()`. Both failed at once with "cannot import name 'main'", and only
`python main.py` worked. Each test runs the real entry point in a fresh
interpreter, because importing main.py rewraps stdout and sets CUDA
variables, with main.run replaced so no microphone or model is touched.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _launch(run_body: str, **env: str) -> subprocess.CompletedProcess[str]:
    code = (
        "import sys\n"
        "sys.argv = ['agent-guru']\n"
        "import main\n"
        "async def fake_run():\n"
        f"    {run_body}\n"
        "main.run = fake_run\n"
        "from Agent_Guru.__main__ import _run\n"
        "_run()\n"
        "print('RETURNED')\n"
    )
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=25,
        check=False,
    )


def test_console_entry_point_runs_the_assistant() -> None:
    proc = _launch("print('ASSISTANT RAN')")
    assert proc.returncode == 0, proc.stderr
    assert "ASSISTANT RAN" in proc.stdout
    assert "RETURNED" in proc.stdout


def test_console_entry_point_gives_up_after_the_restart_limit() -> None:
    # The crash-restart loop now applies to this entry point too; with a
    # limit of 1 the first crash ends the process with status 1.
    proc = _launch("raise RuntimeError('simulated crash')", AGENT_GURU_MAX_RESTARTS="1")
    assert proc.returncode == 1
    assert "RETURNED" not in proc.stdout
    assert "simulated crash" in proc.stdout + proc.stderr
