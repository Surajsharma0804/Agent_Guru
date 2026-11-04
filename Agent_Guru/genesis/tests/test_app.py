"""The window's endpoints and the stage nodes: every state from the journal, every input checked."""

from __future__ import annotations

import itertools

import pytest

from Agent_Guru.genesis import app as ga
from Agent_Guru.genesis import journal as jr
from Agent_Guru.genesis import manifest as mf
from Agent_Guru.genesis.layout import Layout
from Agent_Guru.genesis.tests.test_planner import machine

MANIFEST = mf.load()


def views(*events):
    return jr.project([jr.Event(i + 1, 0, "r", cid, MANIFEST.by_id[cid]["stage"], kind, data)
                       for i, (cid, kind, data) in enumerate(events)])


def test_a_stage_is_dim_until_something_happens_in_it():
    assert {s["state"] for s in ga.stage_states({}, MANIFEST).values()} == {"dim"}  # nosec B101


def test_no_node_is_lit_without_a_verified_or_reused_event_for_every_component():
    memory = [c["id"] for c in MANIFEST.components if c["stage"] == "Memory"]
    # Every combination of non-final events across the Memory components: never lit.
    for kinds in itertools.product(["planned", "started", "skipped", "cancelled"], repeat=len(memory)):
        st = ga.stage_states(views(*[(cid, k, {}) for cid, k in zip(memory, kinds)]), MANIFEST)["Memory"]
        assert st["state"] in ("dim", "building"), kinds  # nosec B101
    # One verified and one still running: building, not lit.
    st = ga.stage_states(views((memory[0], "verified", {}), (memory[1], "started", {})), MANIFEST)["Memory"]
    assert st["state"] == "building"  # nosec B101
    # One verified and one only planned (not started yet): not lit either.
    st = ga.stage_states(views((memory[0], "verified", {}), (memory[1], "planned", {})), MANIFEST)["Memory"]
    assert st["state"] == "building"  # nosec B101
    lit = ga.stage_states(views(*[(cid, "verified", {}) for cid in memory]), MANIFEST)["Memory"]
    assert lit["state"] == "lit"  # nosec B101


def test_a_reused_stage_looks_different_from_an_installed_one():
    memory = [c["id"] for c in MANIFEST.components if c["stage"] == "Memory"]
    assert ga.stage_states(views(*[(c, "reused", {}) for c in memory]), MANIFEST)["Memory"]["state"] == "reused"  # nosec B101


def test_a_failure_fractures_the_stage_and_keeps_the_real_error():
    st = ga.stage_states(views(("core-packages", "started", {}),
                               ("core-packages", "failed", {"error": "files.pythonhosted.org: timed out"})), MANIFEST)
    assert st["Foundation"]["state"] == "fractured"  # nosec B101
    assert st["Foundation"]["errors"] == {"core-packages": "files.pythonhosted.org: timed out"}  # nosec B101


def test_skipped_components_do_not_hold_a_stage_back():
    voice = [c["id"] for c in MANIFEST.components if c["stage"] == "Voice"]
    active = {"voice-packages"}
    st = ga.stage_states(views(("voice-packages", "verified", {})), MANIFEST, active)["Voice"]
    assert st["state"] == "lit" and st["components"] == ["voice-packages"] and len(voice) > 1  # nosec B101


@pytest.fixture
def app(tmp_path):
    a = ga.GenesisApp(Layout(tmp_path / "AG", tmp_path / "app"), MANIFEST, launcher=lambda args, cwd: None)
    a.machine = machine()
    return a


def test_every_endpoint_refuses_fields_it_does_not_name(app):
    routes = app.routes()
    for key in (("POST", "/api/plan"), ("POST", "/api/install"), ("POST", "/api/confirm"), ("POST", "/api/scan"),
                ("POST", "/api/cancel"), ("POST", "/api/launch")):
        for field in ("cmd", "command", "url", "path", "file"):
            status, body = routes[key]({field: "x"})
            assert status == 400 and "unexpected fields" in body["error"], (key, field)  # nosec B101


def test_a_plan_must_name_known_tiers_and_a_valid_model(app):
    routes = app.routes()
    assert routes[("POST", "/api/plan")]({"tiers": {"rootkit": True}})[0] == 400  # nosec B101
    assert routes[("POST", "/api/plan")]({"model": "x; del C:"})[0] == 400  # nosec B101
    status, body = routes[("POST", "/api/plan")]({"tiers": {"vision": False}})
    assert status == 200 and body["plan"]["tiers"]["vision"] is False and len(body["plan_id"]) == 16  # nosec B101


def test_install_needs_the_exact_plan_that_was_shown(app):
    routes = app.routes()
    _, shown = routes[("POST", "/api/plan")]({})
    assert routes[("POST", "/api/install")]({"plan_id": "0" * 16})[0] == 409  # nosec B101
    assert routes[("POST", "/api/install")]({})[0] == 409  # nosec B101


def test_launch_waits_for_a_verified_first_start(app, tmp_path):
    routes = app.routes()
    assert routes[("POST", "/api/launch")]({})[0] == 409  # nosec B101
    j = jr.Journal(app.layout.journal_path)
    j.append("r", "first-start", "Awakening", "started")
    j.append("r", "first-start", "Awakening", "verified", {"result": "PASS"})
    started = []
    app._launcher = lambda args, cwd: started.append((args, cwd))
    assert routes[("POST", "/api/launch")]({})[0] == 202  # nosec B101
    assert started == [([str(app.layout.venv_python), "-m", "Agent_Guru"], app.layout.app_root)]  # nosec B101


def test_a_replay_installs_nothing_and_says_so(tmp_path):
    journal = tmp_path / "recorded.jsonl"
    jr.Journal(journal).append("r", "core-packages", "Foundation", "verified")
    a = ga.GenesisApp(Layout(tmp_path / "AG", tmp_path / "app"), MANIFEST, replay_journal=journal)
    a.machine, routes = machine(), a.routes()
    _, shown = routes[("POST", "/api/plan")]({})
    for key, body in ((("POST", "/api/install"), {"plan_id": shown["plan_id"]}), (("POST", "/api/launch"), {}),
                      (("POST", "/api/verify"), {}), (("POST", "/api/confirm"), {"component": "voice-check", "confirmed": True})):
        status, out = routes[key](body)
        assert status == 403 and "REPLAY - NOT A REAL RUN" in out["error"]  # nosec B101
    assert routes[("GET", "/api/state")]({})[1]["components"]["core-packages"]["state"] == "verified"  # nosec B101


def test_a_persons_confirmation_is_written_to_the_journal(app):
    routes = app.routes()
    assert routes[("POST", "/api/confirm")]({"component": "voice-check", "confirmed": False})[0] == 200  # nosec B101
    assert routes[("GET", "/api/state")]({})[1]["confirmations"] == {"voice-check": False}  # nosec B101
    assert routes[("POST", "/api/confirm")]({"component": "nope", "confirmed": True})[0] == 400  # nosec B101


def test_a_skipped_component_does_not_keep_its_stage_building():
    # Found replaying a second run on a machine without NVIDIA: the skipped
    # GPU add-on kept the finished Voice stage "building".
    voice = [c["id"] for c in MANIFEST.components if c["stage"] == "Voice"]
    events = [(c, "skipped" if c == "voice-gpu" else "reused", {}) for c in voice]
    assert ga.stage_states(views(*events), MANIFEST)["Voice"]["state"] == "reused"  # nosec B101


def test_a_required_part_cannot_be_removed_and_unknown_jobs_are_refused(app):
    routes = app.routes()
    assert routes[("POST", "/api/component")]({"id": "core-packages", "action": "remove"})[0] == 409  # nosec B101
    assert routes[("POST", "/api/component")]({"id": "nope", "action": "repair"})[0] == 400  # nosec B101
    assert routes[("POST", "/api/component")]({"id": "voice-packages", "action": "shell"})[0] == 400  # nosec B101


def test_a_replay_changes_no_component(tmp_path):
    journal = tmp_path / "recorded.jsonl"
    jr.Journal(journal).append("r", "core-packages", "Foundation", "verified")
    a = ga.GenesisApp(Layout(tmp_path / "AG", tmp_path / "app"), MANIFEST, replay_journal=journal)
    assert a.routes()[("POST", "/api/component")]({"id": "voice-packages", "action": "remove"})[0] == 403  # nosec B101


def test_the_doctor_explains_each_result_in_plain_words():
    assert ga.explain("Voice", "NOT INSTALLED", "x") == "Voice is missing. Repair installs it."  # nosec B101
    assert "what the check saw: timed out" in ga.explain("Voice", "FAILED", "timed out").lower()  # nosec B101


def test_launch_hands_the_app_where_to_leave_its_window(app):
    env = app.app_env()
    assert env["AGENT_GURU_WORKSPACE"] == "1" and env["AGENT_GURU_INSTALL_ROOT"] == str(app.layout.install_root)  # nosec B101
    assert env["AGENT_GURU_WORKSPACE_FILE"] == str(app.workspace_file)  # nosec B101
    assert app.routes()[("GET", "/api/launched")]({})[1] == {"url": ""}  # nosec B101
