"""whisper_stt imports when faster_whisper cannot be loaded.

The module catches the ImportError (or the OSError of a ctranslate2 DLL that
Windows Application Control blocks) and sets WhisperModel = None, so speech
recognition can report itself unavailable. An annotation evaluated at class
definition, "tuple[WhisperModel | None, str]", then raised TypeError, and
main.py, which treats speech as critical, crashed on every start instead.
Found by starting main.py in a venv holding only the core packages.
"""

from __future__ import annotations

import os
import subprocess  # nosec B404 - runs this interpreter on a fixed script
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]

_CHILD = """
import sys
sys.modules["faster_whisper"] = None  # what an absent or blocked package looks like to an import
import Agent_Guru.speech.stt.whisper_stt as stt
print("WhisperModel", stt.WhisperModel)
print("class", stt.WhisperTranscriber.__name__)
"""


@pytest.mark.timeout(60)
def test_the_module_imports_and_falls_back_without_faster_whisper(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AGENT_GURU_")}
    env["PYTHONPATH"] = str(REPO)
    run = subprocess.run([sys.executable, "-c", _CHILD], cwd=str(tmp_path), env=env,  # nosec B603
                         capture_output=True, text=True, timeout=50, check=False)
    assert run.returncode == 0, run.stderr[-1500:]  # nosec B101
    assert run.stdout.splitlines() == ["WhisperModel None", "class WhisperTranscriber"]  # nosec B101
