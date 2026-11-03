"""`python -m Agent_Guru logs` prints the last warnings and errors on one screen.

Finding what went wrong meant knowing where the logs are (service.log in the
data folder, logs/errors.log) and searching them by hand. The command reads
both formats the assistant writes: the stdlib one and structlog's.
"""

from __future__ import annotations

import subprocess  # nosec B404 - runs this interpreter on the package
import sys

from Agent_Guru.utils import commands


def _write_log(path, n_problems):
    lines = []
    for i in range(n_problems):
        lines.append(f"07:00:{i:02d}  INFO      guru.main - turn {i} answered")
        lines.append(f"07:00:{i:02d}  WARNING   Agent_Guru.x - slow thing {i}")
    lines.append("2026-11-03 09:30:01 [error    ] connector_failed  detail=boom")
    lines.append("2026-11-03 09:30:02 [info     ] all_good")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_the_last_20_problems_are_printed_oldest_first(tmp_path, monkeypatch, capsys):
    log = tmp_path / "service.log"
    _write_log(log, 30)
    monkeypatch.setattr(commands, "_log_files", lambda: [log, tmp_path / "missing.log"])
    assert commands.logs([]) == 0  # nosec B101
    shown = [line.strip() for line in capsys.readouterr().out.splitlines()[1:]]
    assert len(shown) == 20  # nosec B101
    assert shown[0].endswith("slow thing 11") and shown[-1].endswith("detail=boom")  # nosec B101
    assert not any("INFO" in line or "all_good" in line for line in shown)  # nosec B101


def test_with_no_log_it_says_where_logs_come_from(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(commands, "_log_files", lambda: [tmp_path / "service.log"])
    assert commands.logs([]) == 0  # nosec B101
    out = capsys.readouterr().out
    assert "service start" in out and "python main.py" in out  # nosec B101


def test_the_command_is_listed():
    run = subprocess.run([sys.executable, "-m", "Agent_Guru", "--help"], capture_output=True, text=True,  # nosec B603
                         timeout=120, check=False)
    assert "logs" in run.stdout + run.stderr  # nosec B101
