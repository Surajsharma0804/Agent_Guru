"""The append-only, fsynced record of every installer and maintenance action.

One JSON object per line. Each event has a sequence number, a timestamp, the
run it belongs to, the component, the stage, a kind from KINDS, and data.
Every screen, the command line, the report and the tests are projections of
this file (project() below), so a status shown anywhere is a status that was
written here first. A component counts as installed only when a "verified"
event exists for it after its last "started" or "rolled_back".

Each append is flushed and fsynced before append() returns: a crash or a
power cut can lose at most the event being written, never one already
returned. A torn last line, which is what such a crash leaves, is dropped
when the journal is opened, and a "log" event records that it was.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

KINDS = ("planned", "started", "progress", "log", "reused", "verified", "failed", "skipped", "cancelled",
         "rolled_back")

#: The label a replayed journal carries wherever it is shown.
REPLAY_LABEL = "REPLAY - NOT A REAL RUN"


@dataclass(frozen=True)
class Event:
    seq: int
    ts: float
    run_id: str
    component_id: str
    stage: str
    kind: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, separators=(",", ":"))


def _parse(line: str) -> Event | None:
    try:
        raw = json.loads(line)
        event = Event(int(raw["seq"]), float(raw["ts"]), str(raw["run_id"]), str(raw["component_id"]),
                      str(raw["stage"]), str(raw["kind"]), dict(raw.get("data") or {}))
    except (ValueError, KeyError, TypeError):
        return None
    return event if event.kind in KINDS else None


def read(path: Path) -> tuple[list[Event], int]:
    """Every event in *path*, and how many unreadable lines were skipped.

    Only the last line can be legitimately torn; read() still reports any
    unreadable line in the count so a damaged journal is visible, not hidden.
    """
    if not path.exists():
        return [], 0
    events: list[Event] = []
    bad = 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            event = _parse(line)
            if event is None:
                bad += 1
            else:
                events.append(event)
    return events, bad


class Journal:
    """Appends events to one file. Not shared between processes: the executor holds the install lock."""

    def __init__(self, path: Path, *, clock: Callable[[], float] = time.time) -> None:
        self.path = path
        self._clock = clock
        path.parent.mkdir(parents=True, exist_ok=True)
        dropped = self._drop_torn_tail()
        events, _ = read(path)
        self._seq = max((e.seq for e in events), default=0)
        if dropped:
            self.append("recovery", "journal", "open", "log",
                        {"message": f"dropped {dropped} bytes of a torn last line left by an interrupted write"})

    def _drop_torn_tail(self) -> int:
        """Remove an unfinished last line; return the bytes removed.

        Only the end of the file is touched. A last line without its newline
        was being written when the process stopped: it is removed even if it
        happens to parse, because the next append would otherwise be glued
        onto it and both events would be lost. An unreadable line in the
        middle is left in place and counted by read(), so damage stays visible.
        """
        if not self.path.exists():
            return 0
        data = self.path.read_bytes()
        keep = len(data)
        if data and not data.endswith(b"\n"):
            keep = data.rfind(b"\n") + 1
        if keep < len(data):
            with self.path.open("r+b") as fh:
                fh.truncate(keep)
                fh.flush()
                os.fsync(fh.fileno())
        return len(data) - keep

    def append(self, run_id: str, component_id: str, stage: str, kind: str,
               data: dict[str, Any] | None = None) -> Event:
        if kind not in KINDS:
            msg = f"unknown event kind {kind!r}; expected one of {', '.join(KINDS)}"
            raise ValueError(msg)
        self._seq += 1
        event = Event(self._seq, round(self._clock(), 6), run_id, component_id, stage, kind, dict(data or {}))
        line = event.to_json() + "\n"
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        return event

    def events(self) -> list[Event]:
        return read(self.path)[0]


def new_run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


@dataclass
class ComponentView:
    """What a screen shows for one component: derived from events only."""

    component_id: str
    state: str = "not started"
    done: int | None = None
    total: int | None = None
    error: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    last_seq: int = 0

    @property
    def installed(self) -> bool:
        return self.state in ("verified", "reused")


#: The state a component is in after an event of each kind. "progress" keeps
#: the state "started" and only moves the numbers; "log" changes nothing.
_STATE_AFTER = {"planned": "planned", "started": "started", "reused": "reused", "verified": "verified",
                "failed": "failed", "skipped": "skipped", "cancelled": "cancelled", "rolled_back": "rolled back"}


def project(events: Iterable[Event], run_id: str | None = None) -> dict[str, ComponentView]:
    """The state of every component, from events alone; *run_id* limits it to one run."""
    views: dict[str, ComponentView] = {}
    for e in events:
        if run_id is not None and e.run_id != run_id:
            continue
        if e.component_id in ("journal", "run"):
            continue
        view = views.setdefault(e.component_id, ComponentView(e.component_id))
        view.last_seq = e.seq
        if e.kind == "progress":
            done, total = e.data.get("done"), e.data.get("total")
            # A real numerator and denominator, or nothing: a total that is
            # unknown or zero leaves the bar indeterminate instead of inventing one.
            if isinstance(done, int) and isinstance(total, int) and total > 0:
                view.done, view.total = min(done, total), total
            else:
                view.done, view.total = (done if isinstance(done, int) else None), None
            continue
        if e.kind == "log":
            continue
        view.state = _STATE_AFTER[e.kind]
        if e.kind == "started":
            view.done = view.total = None
            view.error = ""
        if e.kind == "failed":
            view.error = str(e.data.get("error", ""))
        view.detail = dict(e.data)
    return views


def installed_components(events: Iterable[Event]) -> set[str]:
    """Components whose latest outcome across all runs is a verified or reused install."""
    latest: dict[str, str] = {}
    for e in events:
        if e.kind in ("started", "verified", "reused", "failed", "rolled_back", "cancelled"):
            latest[e.component_id] = e.kind
    return {c for c, kind in latest.items() if kind in ("verified", "reused")}
