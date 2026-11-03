"""Importing the reasoning API package does not build a reasoning engine.

app.py ran `app = create_app()` at import, and create_app() builds a whole
ReasoningEngine. The assistant's local API imports this package for its auth
helpers, so every start with AGENT_GURU_API on set the intent engine up twice:
2 constructions on each of 5 measured cold starts, 1 on each after the fix.
The check runs in a fresh interpreter, where nothing has imported the package
before it.
"""

from __future__ import annotations

import subprocess  # nosec B404 - runs this interpreter on a fixed script
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

_CHILD = r"""
import logging
logging.disable(logging.CRITICAL)
import Agent_Guru.reasoning.intent.engine as engine
built = []
real = engine.IntentDetectionEngine.__init__
def counting(self, *a, **k):
    built.append(1)
    real(self, *a, **k)
engine.IntentDetectionEngine.__init__ = counting
import Agent_Guru.reasoning.api.auth  # what the local API imports
print("after-import", len(built))
from Agent_Guru.reasoning.api.app import app, get_app
print("after-app", len(built), app is get_app(), type(app).__name__)
"""


def test_importing_the_api_package_builds_no_engine_until_the_app_is_asked_for():
    run = subprocess.run([sys.executable, "-c", _CHILD], cwd=str(REPO), capture_output=True, text=True,  # nosec B603
                         encoding="utf-8", errors="replace", timeout=170, check=False)
    assert run.returncode == 0, run.stderr[-2000:]  # nosec B101
    lines = [line for line in run.stdout.splitlines() if line.startswith("after-")]
    assert lines == ["after-import 0", "after-app 1 True FastAPI"], run.stdout[-2000:]  # nosec B101
