"""settings.toml fills in the environment variables Agent Guru reads, safely.

Settings could only be given as environment variables, set in a terminal or
the system dialog and lost the next time the app was started another way.
"""

from __future__ import annotations

import os
import subprocess  # nosec B404
import sys
from pathlib import Path

import pytest

from Agent_Guru.utils.settings import KNOWN_SETTINGS, apply_settings_file


def _write(tmp_path, text):
    path = tmp_path / "settings.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_no_file_changes_nothing(tmp_path):
    env = {}
    report = apply_settings_file(tmp_path / "settings.toml", environ=env)
    assert env == {} and report.applied == {} and report.error is None  # nosec B101


def test_known_settings_are_applied_as_the_text_each_variable_expects(tmp_path):
    path = _write(tmp_path, 'OLLAMA_MODEL = "gemma4"\nAGENT_GURU_LLM_TIMEOUT = 45\n'
                            "AGENT_GURU_NUM_CTX = 4096\nAGENT_GURU_TRACES = false\n")
    env = {}
    apply_settings_file(path, environ=env)
    assert env == {"OLLAMA_MODEL": "gemma4", "AGENT_GURU_LLM_TIMEOUT": "45",  # nosec B101
                   "AGENT_GURU_NUM_CTX": "4096", "AGENT_GURU_TRACES": "0"}


def test_a_variable_set_in_the_environment_wins(tmp_path):
    path = _write(tmp_path, 'OLLAMA_MODEL = "gemma4"\n')
    env = {"OLLAMA_MODEL": "llama3"}
    report = apply_settings_file(path, environ=env)
    assert env == {"OLLAMA_MODEL": "llama3"} and report.overridden == ["OLLAMA_MODEL"]  # nosec B101


@pytest.mark.parametrize("line", [
    'OPENAI_API_KEY = "sk-123"', 'GITHUB_TOKEN = "ghp_x"', 'NEO4J_PASSWORD = "p"', 'MONGO_URI = "mongodb://u:p@h"',
    'SENTRY_DSN = "https://k@sentry"',
])
def test_secrets_are_never_taken_from_the_file(tmp_path, line):
    env = {}
    report = apply_settings_file(_write(tmp_path, line + "\n"), environ=env)
    assert env == {} and "secrets" in next(iter(report.refused.values()))  # nosec B101


@pytest.mark.parametrize(("line", "why"), [
    ("AGENT_GURU_LLM_TIMEOUT = \"soon\"", "number"),
    ("AGENT_GURU_LLM_TIMEOUT = -5", "above 0"),
    ("AGENT_GURU_NUM_CTX = 4096.5", "whole number"),
    ("AGENT_GURU_TRACES = \"yes\"", "true or false"),
    ('OLLAMA_MODEL = ""', "non-empty"),
    ('OLLAMA_MODEL = "a\\nb"', "one line"),
    ('PATH = "C:\\\\evil"', "not a setting"),
])
def test_a_bad_value_is_refused_with_the_reason(tmp_path, line, why):
    env = {}
    report = apply_settings_file(_write(tmp_path, line + "\n"), environ=env)
    assert env == {} and why in next(iter(report.refused.values()))  # nosec B101


def test_a_broken_file_is_reported_and_nothing_is_applied(tmp_path):
    env = {}
    report = apply_settings_file(_write(tmp_path, 'OLLAMA_MODEL = "gemma4\n'), environ=env)
    assert env == {} and report.error and "TOMLDecodeError" in report.error  # nosec B101


def test_every_known_setting_is_read_somewhere_in_agent_guru():
    # A name here that no code reads would be accepted and silently do nothing.
    root = Path(__file__).resolve().parents[2]
    sources = [p.read_text(encoding="utf-8", errors="replace") for p in root.rglob("*.py")
               if "tests" not in p.parts and p.name != "settings.py"]
    sources.append((root.parent / "main.py").read_text(encoding="utf-8"))
    unread = [name for name in KNOWN_SETTINGS if not any(f'"{name}"' in s for s in sources)]
    assert unread == []  # nosec B101


def test_settings_from_the_file_reach_the_assistant(tmp_path):
    # In its own process: main.py applies the file when imported, before the
    # orchestrator reads its timeouts, and replaces sys.stdout.
    data = tmp_path / "agent_guru"
    data.mkdir()
    (data / "settings.toml").write_text("AGENT_GURU_LLM_TIMEOUT = 41\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "AGENT_GURU_LLM_TIMEOUT"}
    env.update(LOCALAPPDATA=str(tmp_path), XDG_DATA_HOME=str(tmp_path))
    out = subprocess.run(  # nosec B603
        [sys.executable, "-c",
         "import main; from Agent_Guru.integration import orchestrator; print('RESULT', orchestrator.LLM_TIMEOUT_S)"],
        cwd=Path(__file__).resolve().parents[3], env=env, capture_output=True, text=True, timeout=180, check=False,
    )
    assert "RESULT 41.0" in out.stdout, out.stderr[-2000:]  # nosec B101
