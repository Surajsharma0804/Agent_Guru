"""A terminal view of the assistant: is it running, what it heard and said, what is scheduled, what is on.

The only overview was the web page of the local API, which needs the API
switched on and a browser. `python -m Agent_Guru dashboard` reads the
same facts from the files the assistant keeps (its service record, the
turn records, the scheduled tasks, settings) and draws them in the
terminal, refreshing every few seconds until Ctrl+C; --once draws once.
It only reads: nothing here changes the assistant.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any

_FLAGS = ("AGENT_GURU_CODE_SANDBOX", "AGENT_GURU_CODING_TOOLS", "AGENT_GURU_BROWSER_TOOLS", "AGENT_GURU_API",
          "AGENT_GURU_INJECTION_CLASSIFIER", "AGENT_GURU_ALLOW_CLOUD", "AGENT_GURU_INBOUND")


def snapshot(turn_limit: int = 8) -> dict[str, Any]:
    """Everything the view shows, read from disk."""
    from Agent_Guru.utils import service
    from Agent_Guru.utils.path_utils import app_data_dir

    running = service.state()
    turns: list[dict[str, Any]] = []
    db = app_data_dir("turns.db", create=False)
    if db.exists():
        from Agent_Guru.integration.turn_trace import TurnTraceStore

        for t in TurnTraceStore(db).recent(limit=turn_limit):
            turns.append({"at": t.started_at, "seconds": t.seconds, "heard": t.heard, "said": t.said,
                          "status": t.action_status or t.outcome or "", "rating": t.rating})
    tasks: list[dict[str, Any]] = []
    store = app_data_dir("reminders.json", create=False)
    if store.exists():
        try:
            raw = json.loads(store.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = []
        items = raw.get("reminders", raw) if isinstance(raw, dict) else raw
        for r in items if isinstance(items, list) else []:
            if isinstance(r, dict) and not r.get("fired"):
                tasks.append({"at": r.get("fire_at", 0), "kind": r.get("kind", "say"), "message": r.get("message", ""),
                              "every_s": r.get("every_s")})
    flags = {name: os.environ.get(name, "").strip() or "off" for name in _FLAGS}
    return {"running": running, "turns": turns, "tasks": sorted(tasks, key=lambda t: t["at"]), "flags": flags,
            "model": os.environ.get("OLLAMA_MODEL", "gemma4")}


def render(snap: dict[str, Any]) -> Any:
    """The snapshot as a rich renderable (a Group of tables)."""
    from rich.console import Group
    from rich.table import Table

    def clock(ts: float) -> str:
        return time.strftime("%d %b %H:%M", time.localtime(ts)) if ts else ""

    running = snap["running"]
    head = Table.grid(padding=(0, 2))
    head.add_row("Assistant", f"running, process {running['pid']} since {clock(running.get('started', 0))}"
                 if running else "not running (python -m Agent_Guru service start)")
    head.add_row("Model", snap["model"])
    head.add_row("Switched on", ", ".join(k.removeprefix("AGENT_GURU_").lower() for k, v in snap["flags"].items()
                                           if v.lower() not in ("off", "0", "false", "no", "")) or "nothing optional")
    turns = Table(title="Recent turns", expand=True)
    for column in ("when", "heard", "said", "status", "s"):
        turns.add_column(column, overflow="fold", ratio={"heard": 3, "said": 4}.get(column, 1),
                         min_width={"when": 12, "status": 11, "s": 5}.get(column))
    for t in snap["turns"]:
        turns.add_row(clock(t["at"]), t["heard"][:120], t["said"][:160], t["status"], f"{t['seconds']:.1f}")
    tasks = Table(title="Scheduled", expand=True)
    for column in ("when", "kind", "what", "repeats"):
        tasks.add_column(column, overflow="fold")
    for t in snap["tasks"][:10]:
        tasks.add_row(clock(t["at"]), t["kind"], str(t["message"])[:120],
                      f"every {int(t['every_s'] // 60)} min" if t.get("every_s") else "")
    return Group(head, turns, tasks)


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m Agent_Guru dashboard", description="A terminal view of the assistant.")
    parser.add_argument("--once", action="store_true", help="draw once and exit")
    parser.add_argument("--every", type=float, default=3.0, help="seconds between refreshes")
    args = parser.parse_args(argv)
    from rich.console import Console
    from rich.live import Live

    console = Console()
    if args.once:
        console.print(render(snapshot()))
        return 0
    try:
        with Live(render(snapshot()), console=console, refresh_per_second=1, screen=False) as live:
            while True:
                time.sleep(max(0.5, args.every))
                live.update(render(snapshot()))
    except KeyboardInterrupt:
        return 0
