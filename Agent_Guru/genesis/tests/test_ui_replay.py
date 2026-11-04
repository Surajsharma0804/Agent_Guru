"""Recorded journals replayed through the real page in a real browser engine.

Four journals are recorded with the real executor and manifest (fake actions
and probes): a fresh install, a second run that reuses everything, a failure
and a cancel. Each is served in replay mode and opened in Edge or Chrome
through Playwright. The page's stage nodes and component rows must be exactly
what the journal says (stage_states() and project()), the replay label must
be shown, and the Devanagari wake-word names must be laid out by the
bundled font.
"""

from __future__ import annotations

import time

import pytest

from Agent_Guru.genesis import actions as act
from Agent_Guru.genesis import app as ga
from Agent_Guru.genesis import executor as ex
from Agent_Guru.genesis import journal as jr
from Agent_Guru.genesis import manifest as mf
from Agent_Guru.genesis import planner, verify
from Agent_Guru.genesis.layout import Layout
from Agent_Guru.genesis.server import GenesisServer
from Agent_Guru.genesis.tests.test_planner import machine

MANIFEST = mf.load()


def record(tmp_path, scenario):
    layout = Layout(tmp_path / scenario / "AG", tmp_path / "app")
    tiers = dict(planner.DEFAULT_TIERS, vision=False, browser=False, coding=False)
    plan = planner.plan(machine(), MANIFEST, planner.Choices(tiers=tiers))
    done: set[str] = set()
    holder = {}

    def install(ctx, c):
        if scenario == "failure" and c["id"] == "voice-packages":
            raise act.ActionError("files.pythonhosted.org: torch-2.14.1+cpu.whl: timed out after 41 of 124 MB")
        if scenario == "cancel" and c["id"] == "voice-packages":
            holder["e"].cancel()
            raise act.Cancelled("cancelled by the person")
        ctx.emit("progress", {"done": 5, "total": 10})
        done.add(c["id"])
        return act.Outcome()

    def probe(probe_id, ctx, c):
        return verify.Result("PASS" if c["id"] in done else "NOT INSTALLED", "fake")

    actions = {k: install for k in act.ACTIONS}
    for _ in range(2 if scenario == "reuse" else 1):
        e = ex.Executor(layout, MANIFEST, plan, actions=actions, probes=probe)
        holder["e"] = e
        e.run()
    return layout.journal_path


def wait_until(page, expression, timeout=30.0):
    """Poll from Python. Playwright's wait_for_function polls with eval inside the
    page, which the page's content policy rightly blocks: it passed on a fast
    machine, where the first check was already true, and failed all three CI legs."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if page.evaluate(expression):
            return
        page.wait_for_timeout(50)
    raise AssertionError(f"never true: {expression}")


def slowly(page):
    """Hold the page's script back, so every run sees the page before it has rendered, as CI does."""
    def hold(route):
        time.sleep(0.5)
        route.continue_()

    page.route("**/ui/app.js", hold)


def browser():
    sync = pytest.importorskip("playwright.sync_api", reason="Playwright is part of the browser tier")
    pw = sync.sync_playwright().start()
    for channel in ("msedge", "chrome"):
        try:
            return pw, pw.chromium.launch(channel=channel, headless=True)
        except Exception:  # noqa: BLE001,S112 - try the next installed browser
            continue
    pw.stop()
    pytest.skip("no installed Edge or Chrome for Playwright to drive")


@pytest.fixture(scope="module")
def engine():
    pw, b = browser()
    yield b
    b.close()
    pw.stop()


@pytest.mark.timeout(120)
@pytest.mark.parametrize("scenario", ["fresh", "reuse", "failure", "cancel"])
def test_each_screen_shows_exactly_what_the_journal_says(tmp_path, engine, scenario):
    journal = record(tmp_path, scenario)
    events, _ = jr.read(journal)
    last_run = events[-1].run_id
    views = jr.project(events, last_run)
    expected = {s: v["state"] for s, v in ga.stage_states(views, MANIFEST).items()}
    app = ga.GenesisApp(Layout(tmp_path / "AG", tmp_path / "app"), MANIFEST, replay_journal=journal)
    server = GenesisServer(app.routes(), replay=True)
    url = server.start()
    page = engine.new_page()
    try:
        slowly(page)
        page.goto(url + "&screen=install")
        wait_until(page, "document.querySelectorAll('#stages .node[data-state]').length === 8")
        wait_until(page, "document.querySelectorAll('#component-rows tr').length > 0")
        shown = page.eval_on_selector_all("#stages .node", "ns => ns.map(n => [n.dataset.stage, n.dataset.state])")
        assert dict(shown) == expected  # nosec B101
        rows = page.eval_on_selector_all("#component-rows tr",
                                         "rs => rs.map(r => [r.cells[0].textContent, r.cells[1].className])")
        titles = {c["id"]: c["title"] for c in MANIFEST.components}
        want = sorted((titles[cid], "state-label state-" + v.state.replace(" ", "_")) for cid, v in views.items())
        assert sorted(tuple(r) for r in rows) == want  # nosec B101
        assert page.text_content("#replay") == "REPLAY - NOT A REAL RUN"  # nosec B101
        lit = [s for s, st in expected.items() if st == "lit"]
        for stage in lit:  # no node lit without a verified event for its components
            ids = [c["id"] for c in MANIFEST.components
                   if c["stage"] == stage and c["id"] in views and views[c["id"]].state != "skipped"]
            assert all(views[i].state in ("verified", "reused") for i in ids) and \
                any(views[i].state == "verified" for i in ids)  # nosec B101
        if scenario == "failure":
            assert expected["Voice"] == "fractured"  # nosec B101
            page.click("#stages details summary")
            assert "timed out after 41 of 124 MB" in page.text_content("#stages .err")  # nosec B101
        if scenario == "reuse":
            assert set(expected.values()) <= {"reused", "dim"} and "reused" in expected.values()  # nosec B101
    finally:
        page.close()
        server.stop()


@pytest.mark.timeout(60)
def test_the_devanagari_wake_words_are_drawn_with_the_bundled_font(tmp_path, engine):
    app = ga.GenesisApp(Layout(tmp_path / "AG", tmp_path / "app"), MANIFEST)
    server = GenesisServer(app.routes())
    url = server.start()
    page = engine.new_page()
    try:
        slowly(page)
        page.goto(url)
        wait_until(page, "document.fonts.status === 'loaded' && document.querySelector('[data-s=\"opening.wake\"]').textContent.length > 0")
        text = page.text_content("[data-s='opening.wake']")
        assert "हे गुरु" in text and "हे माया" in text  # nosec B101
        # The browser reports which font it used for the Devanagari run: the
        # bundled Rajdhani, not a system fallback.
        used = page.evaluate("document.fonts.check('600 16px Rajdhani', 'हे गुरु')")
        assert used is True  # nosec B101
        width = page.evaluate("""() => { const s = document.createElement('span');
            s.style.font = '500 40px Rajdhani'; s.textContent = 'गुरु';
            document.body.appendChild(s); const w = s.getBoundingClientRect().width; s.remove(); return w; }""")
        assert width > 20  # nosec B101  glyphs were laid out, not empty boxes of zero width
    finally:
        page.close()
        server.stop()
