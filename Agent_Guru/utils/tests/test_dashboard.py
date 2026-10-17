"""The terminal dashboard shows what the assistant's own files say, and changes nothing."""

from __future__ import annotations

import json
import os
import time

import pytest

pytest.importorskip("rich")
from rich.console import Console  # noqa: E402

from Agent_Guru.utils import dashboard  # noqa: E402


@pytest.fixture
def data(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA" if os.name == "nt" else "XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_GURU_CODE_SANDBOX", "1")
    monkeypatch.delenv("AGENT_GURU_BROWSER_TOOLS", raising=False)
    from Agent_Guru.utils.path_utils import app_data_dir

    return app_data_dir


def _text(snapshot) -> str:
    console = Console(record=True, width=160)
    console.print(dashboard.render(snapshot))
    return console.export_text()


def test_turns_tasks_and_switches_are_shown(data):
    from Agent_Guru.integration.turn_trace import TurnRecord, TurnTraceStore

    TurnTraceStore(data("turns.db")).record(TurnRecord(started_at=time.time() - 60, seconds=2.4, personality="guru",
                                                         heard="what time is it", said="It is 9 PM.",
                                                         action_status="success"))
    data("reminders.json").write_text(json.dumps([
        {"reminder_id": "r1", "message": "call mom", "fire_at": time.time() + 3600, "kind": "say", "fired": False},
        {"reminder_id": "r2", "message": "old", "fire_at": time.time() - 3600, "kind": "say", "fired": True}]),
        encoding="utf-8")
    shown = _text(dashboard.snapshot())
    assert "not running" in shown and "what time is it" in shown and "It is 9 PM." in shown  # nosec B101
    assert "call mom" in shown and "old" not in shown.split("Scheduled")[1]  # nosec B101
    assert "code_sandbox" in shown and "browser_tools" not in shown  # nosec B101


def test_no_files_yet_is_an_empty_view_not_an_error(data):
    snap = dashboard.snapshot()
    assert snap["turns"] == [] and snap["tasks"] == []  # nosec B101
    assert "Recent turns" in _text(snap)  # nosec B101


def test_once_draws_and_exits(data, capsys):
    assert dashboard.run(["--once"]) == 0  # nosec B101
