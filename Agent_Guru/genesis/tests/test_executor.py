"""The executor on fake runners, downloads and files: every outcome lands in the journal."""

from __future__ import annotations

import hashlib
import io
import threading

import pytest

from Agent_Guru.genesis import actions as act
from Agent_Guru.genesis import executor as ex
from Agent_Guru.genesis import journal as jr
from Agent_Guru.genesis import verify
from Agent_Guru.genesis.layout import Layout
from Agent_Guru.genesis.manifest import Manifest
from Agent_Guru.utils import verified_files as vf

DATA = b"pinned model bytes " * 2000
PIN = {"name": "model.bin", "size": len(DATA), "sha256": hashlib.sha256(DATA).hexdigest(),
       "url": "https://models.example.test/m/model.bin"}


def component(cid, stage="Foundation", tier="core", required=True, deps=(), install="fake", probe="fake",
              rollback="fake.undo", **extra):
    return {"id": cid, "title": cid, "stage": stage, "tier": tier, "required": required, "platforms": ["windows"],
            "depends_on": list(deps), "size": {"download_bytes": 0, "disk_bytes": 0, "measured": "test"},
            "source": "test", "license": "", "probe": probe, "install": install, "rollback": rollback,
            "reason": "test", **extra}


MANIFEST = Manifest((
    component("core"),
    component("memory", "Memory", deps=["core"], install="files.download", probe="files.pinned",
              rollback="files.remove", files=[PIN], dest="runtime:models"),
    component("voice", "Voice", tier="voice", required=False, deps=["core"]),
    component("voice-check", "Voice", tier="voice", required=False, deps=["voice"]),
    component("awake", "Awakening", deps=["core", "memory"], rollback="not reversible"),
))


def plan_for(rows=None, fits=True):
    rows = rows or {}
    return {"offline": False, "components": [{"id": c["id"], "action": rows.get(c["id"], "install"), "reason": "test",
                                              "download_bytes": 0} for c in MANIFEST.components],
            "totals": {"fits": fits, "needed_with_margin_bytes": 900 * 2**20, "free_bytes": 100 * 2**20, "margin": 0.1}}


class Fakes:
    """Install actions and probes that record calls; a probe passes once its component was installed."""

    def __init__(self, fail_install=(), fail_probe=()):
        self.installed: set[str] = set()
        self.calls: list[str] = []
        self.fail_install, self.fail_probe = set(fail_install), set(fail_probe)

    def fake_install(self, ctx, c):
        self.calls.append("install " + c["id"])
        if c["id"] in self.fail_install:
            raise act.ActionError(f"PermissionError: [WinError 5] Access is denied: {c['id']}")
        ctx.emit("progress", {"done": 3, "total": 3})
        self.installed.add(c["id"])
        return act.Outcome()

    def fake_undo(self, ctx, c):
        self.calls.append("undo " + c["id"])
        self.installed.discard(c["id"])
        return act.Outcome(detail={"undone": c["id"]})

    def probe(self, probe_id, ctx, c):
        if probe_id == "fake":
            self.calls.append("probe " + c["id"])
            ok = c["id"] in self.installed and c["id"] not in self.fail_probe
            return verify.Result("PASS" if ok else "NOT INSTALLED", "fake probe")
        return verify.run(probe_id, ctx, c)

    def actions(self):
        return {**act.ACTIONS, "fake": self.fake_install, "fake.undo": self.fake_undo}


class Server:
    """Serves DATA; honours Range; the first connection can drop or hang up the whole process."""

    def __init__(self, data=DATA, drop_after=None, crash_after=None):
        self.data, self.drop_after, self.crash_after = data, drop_after, crash_after
        self.ranges = []

    def __call__(self, request, timeout=None):
        wanted = request.get_header("Range")
        self.ranges.append(wanted)
        start = int(wanted.split("=")[1].rstrip("-")) if wanted else 0
        body = io.BytesIO(self.data[start:])
        drop, crash = self.drop_after, self.crash_after
        self.drop_after = self.crash_after = None
        sent = [0]

        class R:
            status = 206 if start else 200

            def read(self, n=-1):
                if drop is not None and sent[0] >= drop:
                    raise ConnectionResetError("connection reset by peer")
                if crash is not None and sent[0] >= crash:
                    raise SystemExit("process killed")  # what a hard stop looks like from inside
                chunk = body.read(4096)
                sent[0] += len(chunk)
                return chunk

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return R()


@pytest.fixture
def layout(tmp_path):
    return Layout(install_root=tmp_path / "Agent Guru", app_root=tmp_path / "app")


def run(layout, fakes, plan=None, journal=None, **kw):
    e = ex.Executor(layout, MANIFEST, plan or plan_for(), actions=fakes.actions(), probes=fakes.probe, journal=journal, **kw)
    return e, e.run()


def kinds(layout, run_id):
    return [(e.component_id, e.kind) for e in jr.read(layout.journal_path)[0]
            if e.run_id == run_id and e.kind not in ("progress", "log")]


def test_a_fresh_install_verifies_every_component_in_dependency_order(layout, monkeypatch):
    monkeypatch.setattr(vf.urllib.request, "urlopen", Server())
    fakes = Fakes()
    _, s = run(layout, fakes)
    assert s.verified == ["core", "memory", "voice", "voice-check", "awake"] and not s.failed  # nosec B101
    assert (layout.runtime_root / "models" / "model.bin").read_bytes() == DATA  # nosec B101
    views = jr.project(jr.read(layout.journal_path)[0], s.run_id)
    assert all(v.state == "verified" for k, v in views.items())  # nosec B101


def test_a_second_run_performs_zero_actions_and_says_so(layout, monkeypatch):
    monkeypatch.setattr(vf.urllib.request, "urlopen", Server())
    fakes = Fakes()
    run(layout, fakes)
    fakes.calls.clear()
    server = Server()
    monkeypatch.setattr(vf.urllib.request, "urlopen", server)
    _, again = run(layout, fakes)
    assert again.zero_actions and again.performed == []  # nosec B101
    assert sorted(again.reused) == sorted(["core", "memory", "voice", "voice-check", "awake"])  # nosec B101
    assert not [c for c in fakes.calls if c.startswith("install")] and server.ranges == []  # nosec B101


def test_a_process_killed_mid_download_resumes_where_it_stopped(layout, monkeypatch):
    monkeypatch.setattr(vf.urllib.request, "urlopen", Server(crash_after=8192))
    fakes = Fakes()
    with pytest.raises(SystemExit):
        run(layout, fakes)
    events = jr.read(layout.journal_path)[0]
    assert (events[-1].component_id, events[-1].kind) in {("memory", "started"), ("memory", "progress")}  # nosec B101
    part = layout.cache_dir / "files" / PIN["sha256"][:16] / "model.bin.part"
    assert part.stat().st_size == 8192  # nosec B101
    server = Server()
    monkeypatch.setattr(vf.urllib.request, "urlopen", server)
    _, s = run(layout, fakes)
    assert server.ranges == ["bytes=8192-"] and "memory" in s.verified  # nosec B101
    assert (layout.runtime_root / "models" / "model.bin").read_bytes() == DATA  # nosec B101


def test_a_hash_mismatch_is_rejected_and_nothing_gets_the_real_name(layout, monkeypatch):
    monkeypatch.setattr(vf.urllib.request, "urlopen", Server(data=b"X" + DATA[1:]))
    _, s = run(layout, Fakes())
    assert "pinned sha256" in s.failed["memory"] and "awake" in s.skipped  # nosec B101
    assert not (layout.runtime_root / "models" / "model.bin").exists()  # nosec B101


def test_a_dropped_connection_fails_with_the_host_and_keeps_the_bytes(layout, monkeypatch):
    monkeypatch.setattr(vf.urllib.request, "urlopen", Server(drop_after=4096))
    _, s = run(layout, Fakes())
    assert s.failed["memory"].startswith("models.example.test: model.bin:")  # nosec B101


def test_too_little_disk_refuses_before_any_download_or_action(layout, monkeypatch):
    server = Server()
    monkeypatch.setattr(vf.urllib.request, "urlopen", server)
    fakes = Fakes()
    _, s = run(layout, fakes, plan=plan_for(fits=False))
    assert s.refused and fakes.calls == [] and server.ranges == []  # nosec B101
    last = jr.read(layout.journal_path)[0][-1]
    assert last.kind == "failed" and "not enough disk space" in last.data["error"]  # nosec B101


def test_offline_installs_from_the_folder_without_the_network(layout, monkeypatch, tmp_path):
    def no_network(*a, **k):
        raise AssertionError("the network was used during an offline install")

    monkeypatch.setattr(vf.urllib.request, "urlopen", no_network)
    offline = tmp_path / "usb"
    (offline / "files").mkdir(parents=True)
    (offline / "files" / "model.bin").write_bytes(DATA)
    _, s = run(layout, Fakes(), context={"offline_dir": offline})
    assert "memory" in s.verified and not s.failed  # nosec B101


def test_permission_denied_on_an_optional_tier_still_installs_the_core(layout, monkeypatch):
    monkeypatch.setattr(vf.urllib.request, "urlopen", Server())
    _, s = run(layout, Fakes(fail_install={"voice"}))
    assert "Access is denied" in s.failed["voice"]  # nosec B101
    assert s.skipped["voice-check"].startswith("needs voice")  # nosec B101
    assert {"core", "memory", "awake"} <= set(s.verified)  # nosec B101


def test_a_component_whose_probe_fails_is_failed_not_installed(layout, monkeypatch):
    monkeypatch.setattr(vf.urllib.request, "urlopen", Server())
    _, s = run(layout, Fakes(fail_probe={"voice"}))
    assert s.failed["voice"] == "fake probe" and "voice" not in s.verified  # nosec B101
    assert "voice" not in jr.installed_components(jr.read(layout.journal_path)[0])  # nosec B101


def test_cancel_leaves_every_component_with_an_outcome(layout, monkeypatch):
    monkeypatch.setattr(vf.urllib.request, "urlopen", Server())
    fakes = Fakes()
    holder = {}

    def cancelling_install(ctx, c):
        if c["id"] == "voice":
            holder["e"].cancel()
        return fakes.fake_install(ctx, c)

    acts = {**fakes.actions(), "fake": cancelling_install}
    e = ex.Executor(layout, MANIFEST, plan_for(), actions=acts, probes=fakes.probe)
    holder["e"] = e
    s = e.run()
    assert s.cancelled == ["voice", "voice-check", "awake"]  # nosec B101
    views = jr.project(jr.read(layout.journal_path)[0], s.run_id)
    assert {v.state for v in views.values()} <= {"verified", "cancelled"}  # nosec B101  nothing left "started"


def test_pause_keeps_the_partial_download_and_the_next_run_resumes_it(layout, monkeypatch):
    server = Server()
    monkeypatch.setattr(vf.urllib.request, "urlopen", server)
    fakes = Fakes()
    e = ex.Executor(layout, MANIFEST, plan_for(), actions=fakes.actions(), probes=fakes.probe)
    calls = {"n": 0}
    real_download = vf.download

    def pausing_download(*a, **k):
        def stop():
            calls["n"] += 1
            if calls["n"] == 2:
                e.pause()
            return e._stop.is_set()
        k["should_stop"] = stop
        return real_download(*a, **k)

    e._context_kw = {"download": pausing_download}
    s = e.run()
    assert "memory" in s.cancelled  # nosec B101
    paused = [ev for ev in jr.read(layout.journal_path)[0] if ev.component_id == "memory" and ev.kind == "cancelled"]
    assert paused[-1].data["paused"] is True  # nosec B101
    _, again = run(layout, fakes)
    assert server.ranges[-1] == "bytes=8192-" and "memory" in again.verified  # nosec B101


def test_a_corrupted_journal_tail_is_recovered_and_the_run_completes(layout, monkeypatch):
    monkeypatch.setattr(vf.urllib.request, "urlopen", Server())
    layout.journal_path.parent.mkdir(parents=True)
    layout.journal_path.write_text('{"seq": 1, "ts": 1, "run_id": "x", "comp', encoding="utf-8")
    _, s = run(layout, Fakes())
    events, bad = jr.read(layout.journal_path)
    assert bad == 0 and events[0].kind == "log" and "torn" in events[0].data["message"]  # nosec B101
    assert len(s.verified) == 5  # nosec B101


def test_only_one_installer_runs_at_a_time(layout):
    with ex.InstallLock(layout), pytest.raises(ex.AlreadyRunning):
        with ex.InstallLock(layout):
            pass


def test_rollback_undoes_reversible_steps_dependents_first_and_lists_the_rest(layout, monkeypatch):
    monkeypatch.setattr(vf.urllib.request, "urlopen", Server())
    fakes = Fakes()
    e, _ = run(layout, fakes)
    fakes.calls.clear()
    out = e.rollback(["core", "voice", "awake", "memory"])
    assert out == {"awake": "not reversible", "voice": "rolled back", "memory": "rolled back", "core": "rolled back"}  # nosec B101
    assert fakes.calls == ["undo voice", "undo core"]  # nosec B101  memory used files.remove
    assert not (layout.runtime_root / "models" / "model.bin").exists()  # nosec B101


def test_skipped_components_are_written_as_skipped(layout, monkeypatch):
    monkeypatch.setattr(vf.urllib.request, "urlopen", Server())
    plan = plan_for(rows={"voice": "skip", "voice-check": "skip"})
    _, s = run(layout, Fakes(), plan=plan)
    assert set(s.skipped) == {"voice", "voice-check"} and "voice" not in s.verified  # nosec B101


def test_the_cancel_flag_is_safe_to_set_from_another_thread(layout, monkeypatch):
    monkeypatch.setattr(vf.urllib.request, "urlopen", Server())
    e = ex.Executor(layout, MANIFEST, plan_for(), actions=Fakes().actions(), probes=Fakes().probe)
    t = threading.Thread(target=e.cancel)
    t.start()
    t.join()
    s = e.run()
    assert s.cancelled == ["core", "memory", "voice", "voice-check", "awake"] and not s.performed  # nosec B101


def test_the_python_the_plan_reuses_reaches_every_component(layout, monkeypatch):
    # The first real install failed at the venv: the reused Python was given
    # only to the python-runtime row, so the venv step looked for the private
    # runtime and raised FileNotFoundError.
    monkeypatch.setattr(vf.urllib.request, "urlopen", Server())
    seen = {}
    fakes = Fakes()

    def install(ctx, c):
        seen[c["id"]] = ctx.python
        return fakes.fake_install(ctx, c)

    plan = plan_for()
    plan["python"] = {"reuse": {"version": "3.13.15", "path": "C:/Py/313/python.exe"}}
    e = ex.Executor(layout, MANIFEST, plan, actions={**fakes.actions(), "fake": install}, probes=fakes.probe)
    e.run()
    assert seen and set(seen.values()) == {"C:/Py/313/python.exe"}  # nosec B101


def test_a_rerun_still_reports_warnings(layout, monkeypatch):
    # The all-tier rerun had an empty warnings list while the wake word was on
    # its fallback: only the install path recorded them.
    monkeypatch.setattr(vf.urllib.request, "urlopen", Server())
    fakes = Fakes()
    real_probe = fakes.probe

    def probe(probe_id, ctx, c):
        result = real_probe(probe_id, ctx, c)
        if c["id"] == "voice" and result.label == "PASS":
            return verify.Result("WARNING", "fallback detector")
        return result

    e = ex.Executor(layout, MANIFEST, plan_for(), actions=fakes.actions(), probes=probe)
    assert e.run().warnings == ["voice"]  # nosec B101
    again = ex.Executor(layout, MANIFEST, plan_for(), actions=fakes.actions(), probes=probe).run()
    assert again.zero_actions and again.warnings == ["voice"]  # nosec B101
