"""Runs a plan: each component in dependency order, every step written to the journal.

For each component the executor writes "started", runs its install action,
then its verify probe, and writes "verified" (PASS or WARNING) or "failed".
A component that is already installed is probed first and, if the probe
passes, gets "reused" without its install action running: a second run on a
finished install performs zero actions and says so in its summary.

- A failed optional component does not stop the run; components that depend
  on it are "skipped" with the reason. A failed required component stops
  only the components that need it.
- Cancel and pause stop at a safe point: a download keeps its bytes (the next
  run resumes it with a Range request) and the journal ends with
  "cancelled" for the component in progress and every one not yet started.
- A crash leaves at most a torn last journal line, which the journal drops
  on open; the next run re-probes what was verified and redoes the rest.
- Only one installer runs at a time (InstallLock).
- rollback() undoes reversible steps in reverse order and writes
  "rolled_back"; steps marked "not reversible" are listed in the plan.
- Before the first download, a plan that does not fit the disk is refused.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from Agent_Guru.genesis import actions as act
from Agent_Guru.genesis import verify
from Agent_Guru.genesis.journal import Journal, installed_components, new_run_id
from Agent_Guru.genesis.layout import Layout
from Agent_Guru.genesis.manifest import NOT_REVERSIBLE, Manifest, order


class AlreadyRunning(RuntimeError):
    """Another installer holds the lock for this install folder."""


class InstallLock:
    """An exclusive lock on a file in the install folder, released when the process ends."""

    def __init__(self, layout: Layout) -> None:
        self.path = layout.lock_path
        self._fh: Any = None

    def __enter__(self) -> InstallLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            fh.close()
            msg = f"another installer is already running for {self.path.parent.parent}"
            raise AlreadyRunning(msg) from exc
        self._fh = fh
        return self

    def __exit__(self, *exc: object) -> None:
        if self._fh is not None:
            if os.name == "nt":
                import msvcrt

                self._fh.seek(0)
                try:
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            self._fh.close()
            self._fh = None


@dataclass
class Summary:
    run_id: str
    performed: list[str] = field(default_factory=list)
    reused: list[str] = field(default_factory=list)
    verified: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    cancelled: list[str] = field(default_factory=list)
    refused: str = ""

    @property
    def zero_actions(self) -> bool:
        return not self.performed and not self.failed and not self.refused

    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "performed": self.performed, "reused": self.reused, "verified": self.verified,
                "warnings": self.warnings, "failed": self.failed, "skipped": self.skipped,
                "cancelled": self.cancelled, "refused": self.refused, "zero_actions": self.zero_actions}


class Executor:
    def __init__(self, layout: Layout, manifest: Manifest, plan: dict[str, Any], *,
                 journal: Journal | None = None, context: dict[str, Any] | None = None,
                 actions: dict[str, Callable[..., act.Outcome]] | None = None,
                 probes: Callable[[str, act.ActionContext, dict[str, Any]], verify.Result] | None = None) -> None:
        self.layout = layout
        self.manifest = manifest
        self.plan = plan
        self.journal = journal or Journal(layout.journal_path)
        self._context_kw = context or {}
        self._actions = actions or act.ACTIONS
        self._probe = probes or verify.run
        self._stop = threading.Event()
        self._paused = False

    def cancel(self) -> None:
        self._stop.set()

    def pause(self) -> None:
        """Stop at the next safe point and keep downloaded bytes; a new run resumes them."""
        self._paused = True
        self._stop.set()

    def _ctx(self, run_id: str, cid: str, stage: str) -> act.ActionContext:
        def emit(kind: str, data: dict[str, Any]) -> None:
            self.journal.append(run_id, cid, stage, kind, data)

        kw = dict(self._context_kw)
        row = next((r for r in self.plan["components"] if r["id"] == cid), {})
        # The Python the plan chose is every component's, not only the
        # python-runtime row's: the venv is built from it. When it was set
        # only on that row, the first real install looked for the private
        # runtime instead and failed with FileNotFoundError (2026-11-04).
        reuse = (self.plan.get("python") or {}).get("reuse") or {}
        if reuse.get("path"):
            kw.setdefault("python", reuse["path"])
        if row.get("model"):
            kw["model"] = row["model"]
        return act.ActionContext(layout=self.layout, emit=emit, should_stop=self._stop.is_set, **kw)

    def run(self, run_id: str | None = None) -> Summary:
        with InstallLock(self.layout):
            return self._run(run_id or new_run_id())

    def _run(self, run_id: str) -> Summary:
        summary = Summary(run_id)
        j = self.journal
        rows = {r["id"]: r for r in self.plan["components"]}
        totals = self.plan["totals"]
        if self.plan.get("path_problem"):
            summary.refused = self.plan["path_problem"]
            j.append(run_id, "run", "Foundation", "failed", {"error": summary.refused})
            return summary
        if totals.get("fits") is False:
            summary.refused = (f"needs {totals['needed_with_margin_bytes'] // 2**20} MB with a "
                               f"{int(totals['margin'] * 100)} % margin; {totals['free_bytes'] // 2**20} MB are free")
            j.append(run_id, "run", "Foundation", "failed", {"error": "not enough disk space: " + summary.refused})
            return summary
        wanted = [cid for cid, r in rows.items() if r["action"] != "skip"]
        sequence = order(self.manifest, wanted)
        by_id = self.manifest.by_id
        j.append(run_id, "run", "Foundation", "started", {"components": sequence, "offline": self.plan.get("offline")})
        for cid in sequence:
            c = by_id[cid]
            j.append(run_id, cid, c["stage"], "planned", {"action": rows.get(cid, {}).get("action", "install"),
                                                          "download_bytes": rows.get(cid, {}).get("download_bytes", 0)})
        for cid, r in rows.items():
            if r["action"] == "skip":
                j.append(run_id, cid, by_id[cid]["stage"], "skipped", {"reason": r["reason"]})
                summary.skipped[cid] = r["reason"]
        verified_before = installed_components(j.events())
        done_ok: set[str] = set()
        for index, cid in enumerate(sequence):
            c = by_id[cid]
            stage = c["stage"]
            if self._stop.is_set():
                for rest in sequence[index:]:
                    j.append(run_id, rest, by_id[rest]["stage"], "cancelled",
                             {"reason": "paused" if self._paused else "cancelled before it started", "paused": self._paused})
                    summary.cancelled.append(rest)
                break
            blocked = [d for d in c["depends_on"] if d in rows and d not in done_ok]
            if blocked:
                reason = f"needs {', '.join(blocked)}, which did not install"
                j.append(run_id, cid, stage, "skipped", {"reason": reason})
                summary.skipped[cid] = reason
                continue
            ctx = self._ctx(run_id, cid, stage)
            j.append(run_id, cid, stage, "started", {})
            try:
                if (cid in verified_before or rows[cid]["action"] == "reuse") and not act.is_stale(ctx, c):
                    result = self._probe(c["probe"], ctx, c)
                    if result.counts_as_installed:
                        j.append(run_id, cid, stage, "reused", {"result": result.label, "detail": result.detail,
                                                                "needs_person": result.needs_person, **result.data})
                        summary.reused.append(cid)
                        # A rerun must report what still only half works, as
                        # the first run did: this list stayed empty on reuse,
                        # though --verify showed the wake-word fallback.
                        if result.label == "WARNING":
                            summary.warnings.append(cid)
                        done_ok.add(cid)
                        continue
                outcome = self._actions[c["install"]](ctx, c)
                if not outcome.reused:
                    summary.performed.append(cid)
                ctx.check()
                result = self._probe(c["probe"], ctx, c)
            except act.Cancelled as exc:
                j.append(run_id, cid, stage, "cancelled", {"reason": str(exc), "paused": self._paused})
                summary.cancelled.append(cid)
                for rest in sequence[index + 1:]:
                    j.append(run_id, rest, by_id[rest]["stage"], "cancelled",
                             {"reason": "not started", "paused": self._paused})
                    summary.cancelled.append(rest)
                break
            except act.ActionError as exc:
                j.append(run_id, cid, stage, "failed", {"error": str(exc), "during": "install"})
                summary.failed[cid] = str(exc)
                continue
            except Exception as exc:  # an unexpected error is a failed component with its real message
                j.append(run_id, cid, stage, "failed", {"error": f"{type(exc).__name__}: {exc}", "during": "install"})
                summary.failed[cid] = f"{type(exc).__name__}: {exc}"
                continue
            data = {"result": result.label, "detail": result.detail, "needs_person": result.needs_person, **result.data}
            if result.counts_as_installed:
                kind = "reused" if outcome.reused and cid not in summary.performed else "verified"
                j.append(run_id, cid, stage, kind, data)
                (summary.reused if kind == "reused" else summary.verified).append(cid)
                if result.label == "WARNING":
                    summary.warnings.append(cid)
                done_ok.add(cid)
            else:
                j.append(run_id, cid, stage, "failed", {"error": result.detail, "during": "verify", **data})
                summary.failed[cid] = result.detail
        j.append(run_id, "run", "Awakening", "log", {"summary": summary.to_dict()})
        return summary

    def rollback(self, component_ids: list[str], run_id: str | None = None) -> dict[str, str]:
        """Undo reversible components, dependents first; returns {id: outcome}."""
        run_id = run_id or new_run_id()
        by_id = self.manifest.by_id
        outcomes: dict[str, str] = {}
        with InstallLock(self.layout):
            for cid in reversed(order(self.manifest, component_ids)):
                if cid not in component_ids:
                    continue
                c = by_id[cid]
                if c["rollback"] == NOT_REVERSIBLE:
                    self.journal.append(run_id, cid, c["stage"], "log", {"message": "not reversible; left in place"})
                    outcomes[cid] = NOT_REVERSIBLE
                    continue
                ctx = self._ctx(run_id, cid, c["stage"])
                try:
                    out = self._actions[c["rollback"]](ctx, c)
                except act.ActionError as exc:
                    self.journal.append(run_id, cid, c["stage"], "failed", {"error": str(exc), "during": "rollback"})
                    outcomes[cid] = f"failed: {exc}"
                    continue
                self.journal.append(run_id, cid, c["stage"], "rolled_back", out.detail)
                outcomes[cid] = "rolled back"
        return outcomes
