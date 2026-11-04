"""The GENESIS window's endpoints, bound to the same probes, planner and executor as the command line.

Every value a screen shows comes from here, and every installer state comes
from the journal: stage_states() turns events into the eight stage nodes, and
no node is lit without a "verified" or "reused" event for its components. The
page renders what it is given; it keeps no state of its own about the install.

Each endpoint accepts only the fields it names, with their types. None takes
a command, a URL or a file path: a component is named by its manifest id, a
model by a name matching actions.MODEL_NAME, a tier by its name.
"""

from __future__ import annotations

import hashlib
import json
import subprocess  # nosec B404 - starts the installed app from a fixed argument list
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from Agent_Guru.genesis import actions as act
from Agent_Guru.genesis import cli
from Agent_Guru.genesis import executor as ex
from Agent_Guru.genesis import journal as jr
from Agent_Guru.genesis import manifest as mf
from Agent_Guru.genesis import planner, probes, verify
from Agent_Guru.genesis.layout import Layout

#: Node states, in the order a stage moves through them.
NODE_STATES = ("dim", "building", "lit", "reused", "fractured")


def stage_states(views: dict[str, jr.ComponentView], manifest: mf.Manifest,
                 active: set[str] | None = None) -> dict[str, dict[str, Any]]:
    """The state of each stage node, from component views (which come from events) only.

    fractured: a component in it failed (the error is one click away).
    building:  a component in it is started and not finished.
    lit:       every active component in it is verified, at least one installed now.
    reused:    every active component in it was reused, none installed now.
    dim:       nothing has happened in it yet.
    """
    out: dict[str, dict[str, Any]] = {}
    for stage in mf.STAGES:
        ids = [c["id"] for c in manifest.components if c["stage"] == stage and (active is None or c["id"] in active)
               # A skipped component is not part of this install. Counting it
               # left a finished Voice stage "building" forever on a machine
               # without an NVIDIA GPU, because the GPU add-on was skipped.
               and not (c["id"] in views and views[c["id"]].state == "skipped")]
        states = [views[i].state if i in views else "not started" for i in ids]
        errors = {i: views[i].error for i in ids if i in views and views[i].state == "failed"}
        if errors:
            node = "fractured"
        elif any(s in ("started",) for s in states):
            node = "building"
        elif ids and all(s in ("verified", "reused") for s in states):
            node = "lit" if any(s == "verified" for s in states) else "reused"
        elif any(s in ("verified", "reused") for s in states):
            node = "building"
        else:
            node = "dim"
        out[stage] = {"state": node, "components": ids, "errors": errors}
    return out


def _expect(body: dict[str, Any], fields: dict[str, type | tuple[type, ...]]) -> dict[str, Any]:
    unknown = set(body) - set(fields)
    if unknown:
        raise ValueError(f"unexpected fields: {', '.join(sorted(unknown))}")
    for name, kind in fields.items():
        if name in body and not isinstance(body[name], kind):
            raise ValueError(f"{name} has the wrong type")
    return body


class GenesisApp:
    def __init__(self, layout: Layout, manifest: mf.Manifest | None = None, *,
                 seams: probes.Seams | None = None, replay_journal: Path | None = None,
                 executor_factory: Callable[..., ex.Executor] | None = None,
                 launcher: Callable[[list[str], Path], Any] | None = None) -> None:
        self.layout = layout
        self.manifest = manifest or mf.load()
        self.seams = seams
        self.replay = replay_journal
        self.journal_path = replay_journal or layout.journal_path
        self._executor_factory = executor_factory or ex.Executor
        self._launcher = launcher or (lambda args, cwd: subprocess.Popen(args, cwd=str(cwd),  # nosec B603
                                                                         env=act._venv_env(layout)))
        self.lock = threading.Lock()
        self.probe_rows: list[dict[str, Any]] = []
        self.scanning = False
        self.machine: probes.Machine | None = None
        self.plan: dict[str, Any] | None = None
        self.plan_id = ""
        self.engine: ex.Executor | None = None
        self.run_thread: threading.Thread | None = None
        self.summary: dict[str, Any] | None = None
        self.run_id = ""
        self.close: Callable[[], None] = lambda: None

    # --- reading ------------------------------------------------------------

    def state(self, body: dict[str, Any]) -> tuple[int, Any]:
        events, bad = jr.read(self.journal_path)
        run_id = self.run_id or (events[-1].run_id if events else None)
        views = jr.project(events, run_id) if run_id else {}
        active = {r["id"] for r in self.plan["components"] if r["action"] != "skip"} if self.plan else None
        return 200, {
            "probes": list(self.probe_rows), "scanning": self.scanning, "plan": self.plan, "plan_id": self.plan_id,
            "running": bool(self.run_thread and self.run_thread.is_alive()), "summary": self.summary,
            "run_id": run_id, "stages": stage_states(views, self.manifest, active),
            "components": {cid: {"state": v.state, "done": v.done, "total": v.total, "error": v.error,
                                 "detail": v.detail} for cid, v in views.items()},
            "titles": {c["id"]: {"title": c["title"], "stage": c["stage"], "tier": c["tier"]}
                       for c in self.manifest.components},
            "last_seq": events[-1].seq if events else 0, "journal_unreadable_lines": bad,
            "installed": sorted(jr.installed_components(events)),
            "confirmations": self._confirmations(events),
        }

    @staticmethod
    def _confirmations(events: list[jr.Event]) -> dict[str, bool]:
        return {e.component_id: bool(e.data["confirmed_by_person"]) for e in events
                if e.kind == "log" and "confirmed_by_person" in e.data}

    def events(self, body: dict[str, Any]) -> tuple[int, Any]:
        after = int(body.get("after", 0) or 0)
        events = [e for e in jr.read(self.journal_path)[0] if e.seq > after][:500]
        return 200, {"events": [json.loads(e.to_json()) for e in events]}

    def report(self, body: dict[str, Any]) -> tuple[int, Any]:
        return 200, cli.report(self.layout, self.manifest, self.machine)

    # --- acting ---------------------------------------------------------------

    def _refuse_in_replay(self) -> tuple[int, Any] | None:
        return (403, {"error": jr.REPLAY_LABEL + ": nothing is installed from a replay"}) if self.replay else None

    def scan(self, body: dict[str, Any]) -> tuple[int, Any]:
        _expect(body, {})
        with self.lock:
            if self.scanning:
                return 202, {"scanning": True}
            self.scanning, self.probe_rows = True, []

        def work() -> None:
            try:
                self.machine = probes.scan(self.layout, sorted({h for c in self.manifest.components for h in c.get("hosts", [])}),
                                           self.seams, lambda p: self.probe_rows.append(p.to_dict()),
                                           pinned=cli.pinned_files(self.layout, self.manifest))
            finally:
                self.scanning = False

        threading.Thread(target=work, name="genesis-scan", daemon=True).start()
        return 202, {"scanning": True}

    def make_plan(self, body: dict[str, Any]) -> tuple[int, Any]:
        _expect(body, {"tiers": dict, "model": str})
        if self.machine is None:
            return 409, {"error": "scan the machine first"}
        tiers = dict(planner.DEFAULT_TIERS)
        for name, on in (body.get("tiers") or {}).items():
            if name not in planner.DEFAULT_TIERS or not isinstance(on, bool):
                return 400, {"error": f"unknown tier or value: {name}"}
            tiers[name] = on
        model = body.get("model") or ""
        if model and not act.MODEL_NAME.match(model):
            return 400, {"error": "that is not an Ollama model name"}
        self.plan = planner.plan(self.machine, self.manifest, planner.Choices(tiers=tiers, model=model))
        self.plan_id = hashlib.sha256(json.dumps(self.plan, sort_keys=True, default=str).encode()).hexdigest()[:16]
        return 200, {"plan": self.plan, "plan_id": self.plan_id}

    def install(self, body: dict[str, Any]) -> tuple[int, Any]:
        _expect(body, {"plan_id": str})
        refused = self._refuse_in_replay()
        if refused:
            return refused
        if not self.plan or body.get("plan_id") != self.plan_id:
            return 409, {"error": "approve the plan on screen; it has changed or was never made"}
        if self.run_thread and self.run_thread.is_alive():
            return 409, {"error": "an install is already running"}
        self.engine = self._executor_factory(self.layout, self.manifest, self.plan)
        self.run_id = jr.new_run_id()

        def work() -> None:
            try:
                self.summary = self.engine.run(self.run_id).to_dict()  # type: ignore[union-attr]
            except ex.AlreadyRunning as exc:
                self.summary = {"refused": str(exc)}

        self.run_thread = threading.Thread(target=work, name="genesis-install", daemon=True)
        self.run_thread.start()
        return 202, {"run_id": self.run_id}

    def cancel(self, body: dict[str, Any]) -> tuple[int, Any]:
        _expect(body, {})
        if self.engine:
            self.engine.cancel()
        return 200, {"cancelling": bool(self.engine)}

    def pause(self, body: dict[str, Any]) -> tuple[int, Any]:
        _expect(body, {})
        if self.engine:
            self.engine.pause()
        return 200, {"pausing": bool(self.engine)}

    def verify_all(self, body: dict[str, Any]) -> tuple[int, Any]:
        _expect(body, {})
        refused = self._refuse_in_replay()
        if refused:
            return refused
        journal = jr.Journal(self.layout.journal_path)
        run_id = "verify-" + jr.new_run_id()
        installed = jr.installed_components(journal.events())
        model = cli._installed_model(self.layout)

        def work() -> None:
            for c in self.manifest.components:
                if c["id"] not in installed:
                    continue
                ctx = act.ActionContext(layout=self.layout, emit=lambda k, d: None, model=model,
                                        python=cli.installed_python(self.layout))
                journal.append(run_id, c["id"], c["stage"], "started", {"check": c["probe"]})
                r = verify.run(c["probe"], ctx, c)
                journal.append(run_id, c["id"], c["stage"], "verified" if r.counts_as_installed else "failed",
                               {"result": r.label, "detail": r.detail, "needs_person": r.needs_person, **r.data,
                                **({} if r.counts_as_installed else {"error": r.detail})})

        threading.Thread(target=work, name="genesis-verify", daemon=True).start()
        self.run_id = run_id
        return 202, {"run_id": run_id}

    def confirm(self, body: dict[str, Any]) -> tuple[int, Any]:
        """A person's answer to a check only a person can make (hearing the voice, the wake phrase)."""
        _expect(body, {"component": str, "confirmed": bool})
        refused = self._refuse_in_replay()
        if refused:
            return refused
        cid = body.get("component", "")
        if cid not in self.manifest.by_id or "confirmed" not in body:
            return 400, {"error": "unknown component"}
        c = self.manifest.by_id[cid]
        jr.Journal(self.layout.journal_path).append(self.run_id or "confirm", cid, c["stage"], "log",
                                                    {"confirmed_by_person": body["confirmed"]})
        return 200, {"recorded": True}

    def launch(self, body: dict[str, Any]) -> tuple[int, Any]:
        _expect(body, {})
        refused = self._refuse_in_replay()
        if refused:
            return refused
        if "first-start" not in jr.installed_components(jr.read(self.layout.journal_path)[0]):
            return 409, {"error": "Agent Guru is not installed and verified yet"}
        proc = self._launcher([str(self.layout.venv_python), "-m", "Agent_Guru"], self.layout.app_root)
        return 202, {"started": True, "pid": getattr(proc, "pid", None)}

    def heartbeat(self, body: dict[str, Any]) -> tuple[int, Any]:
        return 200, {"ok": True}

    def close_window(self, body: dict[str, Any]) -> tuple[int, Any]:
        _expect(body, {})
        threading.Timer(0.2, self.close).start()
        return 200, {"closing": True}

    def routes(self) -> dict[tuple[str, str], Callable[[dict[str, Any]], tuple[int, Any]]]:
        def guarded(fn: Callable[[dict[str, Any]], tuple[int, Any]]) -> Callable[[dict[str, Any]], tuple[int, Any]]:
            def call(body: dict[str, Any]) -> tuple[int, Any]:
                try:
                    return fn(body)
                except ValueError as exc:
                    return 400, {"error": str(exc)}
            return call

        table = {("GET", "/api/state"): self.state, ("GET", "/api/events"): self.events,
                 ("GET", "/api/report"): self.report, ("POST", "/api/scan"): self.scan,
                 ("POST", "/api/plan"): self.make_plan, ("POST", "/api/install"): self.install,
                 ("POST", "/api/cancel"): self.cancel, ("POST", "/api/pause"): self.pause,
                 ("POST", "/api/verify"): self.verify_all, ("POST", "/api/confirm"): self.confirm,
                 ("POST", "/api/launch"): self.launch, ("POST", "/api/heartbeat"): self.heartbeat,
                 ("POST", "/api/close"): self.close_window}
        return {k: guarded(v) for k, v in table.items()}
