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
def test_each_screen_shows_exactly_what_the_journal_says(tmp_path, engine, scenario, monkeypatch):
    # The recording's fake actions write no build stamps: its components are current.
    monkeypatch.setattr(act, "is_stale", lambda ctx, component: False)
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


@pytest.mark.timeout(60)
@pytest.mark.parametrize("screen", ["opening", "scan", "plan", "install", "verify", "online"])
def test_every_genesis_screen_opens_in_a_replay_with_its_label(tmp_path, engine, screen):
    journal = record(tmp_path, "fresh")
    app = ga.GenesisApp(Layout(tmp_path / "AG", tmp_path / "app"), MANIFEST, replay_journal=journal)
    server = GenesisServer(app.routes(), replay=True)
    url = server.start()
    page = engine.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(url + "&screen=" + screen)
        wait_until(page, f"document.getElementById('s-{screen}').classList.contains('active')")
        wait_until(page, "document.getElementById('replay').textContent.length > 0")
        assert page.text_content("#replay") == "REPLAY - NOT A REAL RUN" and errors == []  # nosec B101
    finally:
        page.close()
        server.stop()


class FakeOrb:
    """The workspace's data, set by the test as the server would report it."""

    def __init__(self):
        self.state = {"orb": "idle", "seq": 1, "turns": [], "waiting": 0, "microphone": "on", "questions": [], "source": "workspace"}
        self.owner = "Suraj"

    def routes(self):
        titles = {"core-packages": {"title": "Core packages", "tier": "core"}, "voice-packages": {"title": "Voice packages", "tier": "voice"}}
        components = {"core-packages": {"state": "verified", "detail": {"result": "PASS", "explanation": "Working."}},
                      "voice-packages": {"state": "failed", "detail": {"result": "FAILED", "explanation": "It did not import."}}}
        machine_state = {"titles": titles, "installed": ["core-packages", "voice-packages"], "components": components, "running": False}
        settings = {"controls": [{"key": "AGENT_GURU_TRACES", "label": "Keep a record of each turn", "control": "flag", "group": "Memory", "value": True}],
                    "credentials": {"OPENAI_API_KEY": "not set"}}
        return {("GET", "/api/workspace"): lambda b: (200, self.state), ("POST", "/api/heartbeat"): lambda b: (200, {}),
                ("POST", "/api/mic"): lambda b: (200, {}), ("POST", "/api/answer"): lambda b: (202, {}),
                ("GET", "/api/state"): lambda b: (200, machine_state), ("GET", "/api/events"): lambda b: (200, {"events": []}),
                ("GET", "/api/tasks"): lambda b: (200, {"tasks": []}), ("GET", "/api/settings"): lambda b: (200, settings),
                ("GET", "/api/owner"): lambda b: (200, {"name": self.owner}), ("POST", "/api/owner"): self.set_owner}

    def set_owner(self, body):
        self.owner = body["name"]
        return 200, body


@pytest.fixture
def workspace_page(engine):
    fake = FakeOrb()
    server = GenesisServer(fake.routes())
    url = server.start().replace("/#t=", "/workspace.html#t=")
    page = engine.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    slowly(page)
    page.goto(url)
    wait_until(page, "document.querySelectorAll('[role=tab]').length === 5")
    yield fake, page, errors
    page.close()
    server.stop()


@pytest.mark.timeout(60)
@pytest.mark.parametrize("state", ["idle", "listening", "thinking", "speaking", "muted"])
def test_the_orb_shows_the_state_the_server_reports(workspace_page, state):
    fake, page, errors = workspace_page
    fake.state["orb"] = state
    wait_until(page, f"document.getElementById('orb').dataset.state === '{state}'")
    assert page.get_attribute("#orb", "aria-label") and errors == []  # nosec B101


@pytest.mark.timeout(60)
def test_the_conversation_shows_sources_the_queue_and_whose_question_it_is(workspace_page):
    fake, page, errors = workspace_page
    fake.state.update(waiting=2, turns=[{"turn": 1, "source": "workspace", "heard": "hello", "said": "Hi.", "sources": ["https://example.test/a"]}],
                      questions=[{"source": "voice", "turn": 4, "question": "Delete notes.txt?"},
                                 {"source": "workspace", "turn": 5, "question": "Send it?"}])
    wait_until(page, "document.querySelectorAll('.question').length === 2")
    assert "2 waiting" in page.text_content("#queue")  # nosec B101
    assert page.text_content(".sources") == "https://example.test/a"  # nosec B101
    cards = page.eval_on_selector_all(".question", "cs => cs.map(c => [c.textContent, c.querySelectorAll('button').length])")
    assert "Asked by voice in turn 4" in cards[0][0] and cards[0][1] == 0  # nosec B101  no button can answer it from here
    assert "turn 5" in cards[1][0] and cards[1][1] == 2  # nosec B101
    assert errors == []  # nosec B101


@pytest.mark.timeout(60)
def test_a_turn_says_working_only_while_it_is(workspace_page):
    fake, page, errors = workspace_page
    fake.state["turns"] = [{"turn": 1, "source": "workspace", "heard": "first", "said": "", "status": "working"},
                           {"turn": 2, "source": "workspace", "heard": "second", "said": "", "status": "no reply"}]
    wait_until(page, "document.querySelectorAll('.turn').length === 2")
    rows = page.eval_on_selector_all(".turn", "ts => ts.map(t => t.textContent)")
    assert "first" in rows[0] and "Working on it" in rows[0]  # nosec B101  the question shows before the answer
    assert "second" in rows[1] and "No reply came back" in rows[1] and "Working" not in rows[1]  # nosec B101
    assert errors == []  # nosec B101


@pytest.mark.timeout(60)
def test_the_tabs_work_from_the_keyboard(workspace_page):
    _, page, errors = workspace_page
    page.focus("#t-talk")
    page.keyboard.press("ArrowRight")
    wait_until(page, "document.activeElement.id === 't-tasks'")
    assert page.get_attribute("#t-tasks", "aria-selected") == "true"  # nosec B101
    page.keyboard.press("ArrowLeft")
    wait_until(page, "document.activeElement.id === 't-talk'")
    assert errors == []  # nosec B101


@pytest.mark.timeout(60)
def test_a_refresh_leaves_keyboard_focus_on_the_yes_button(workspace_page):
    """The lists were rebuilt every 400 ms, so Yes could not be reached without a mouse."""
    fake, page, errors = workspace_page
    fake.state["questions"] = [{"source": "workspace", "turn": 5, "question": "Send it?"}]
    fake.state["turns"] = [{"turn": 1, "source": "workspace", "heard": "hello", "said": "Hi."}]
    wait_until(page, "document.querySelectorAll('.question button').length === 2")
    page.focus(".question button")
    page.evaluate("window.keptRow = document.querySelector('.turn')")
    page.wait_for_timeout(1200)
    assert page.evaluate("document.activeElement.textContent") == "Yes"  # nosec B101
    # A live list that is not replaced is not read out again.
    assert page.evaluate("window.keptRow.isConnected") and errors == []  # nosec B101


@pytest.mark.timeout(60)
@pytest.mark.parametrize(("tab", "button"), [("control", "#control button"), ("doctor", "#doctor button")])
def test_a_refresh_leaves_keyboard_focus_on_a_repair_button(workspace_page, tab, button):
    _, page, errors = workspace_page
    page.click(f"#t-{tab}")
    wait_until(page, f"document.querySelectorAll('{button}').length > 0")
    page.focus(button)
    page.wait_for_timeout(1200)
    assert page.evaluate("document.activeElement.tagName") == "BUTTON" and errors == []  # nosec B101


@pytest.mark.timeout(60)
def test_the_keyboard_reaches_every_control_in_order_with_a_visible_focus(workspace_page):
    _, page, errors = workspace_page
    seen = []
    for _ in range(6):
        page.keyboard.press("Tab")
        seen.append(page.evaluate("document.activeElement.id || document.activeElement.className"))
        assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") != "none", seen[-1]  # nosec B101
    assert seen == ["skip", "mute", "contrast", "t-talk", "text", "btn"] and errors == []  # nosec B101


CONTRAST = """() => {
  function parse(c) { const m = c.match(/[\\d.]+/g).map(Number); return { r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1 }; }
  function lum(c) {
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }
  function backdrop(e) {
    for (let n = e; n; n = n.parentElement) {
      const st = getComputedStyle(n);
      if (st.backgroundImage !== "none") return null;
      const b = parse(st.backgroundColor);
      if (b.a === 1) return b;
    }
    return parse(getComputedStyle(document.body).backgroundColor);
  }
  const bad = []; let checked = 0;
  for (const e of document.querySelectorAll("body *")) {
    if (e.closest("[hidden]") || e.matches(":disabled") || e.classList.contains("sr-only") || e.tagName === "OPTION") continue;
    const text = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    const r = e.getBoundingClientRect();
    if (!text || r.width < 1 || r.height < 1 || getComputedStyle(e).visibility === "hidden") continue;
    const bg = backdrop(e);
    if (!bg) continue;
    const a = lum(parse(getComputedStyle(e).color)), b = lum(bg);
    const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    checked += 1;
    if (ratio < 4.5) bad.push([e.tagName, e.className, e.textContent.trim().slice(0, 30), Math.round(ratio * 100) / 100]);
  }
  return [checked, bad];
}"""


@pytest.mark.timeout(90)
@pytest.mark.parametrize("contrast", [False, True])
def test_every_visible_text_on_the_workspace_meets_4_5_to_1(workspace_page, contrast):
    fake, page, errors = workspace_page
    fake.state.update(waiting=1, turns=[{"turn": 1, "source": "workspace", "heard": "hello", "said": "Hi.", "sources": ["https://example.test/a"]},
                                        {"turn": 2, "source": "voice", "heard": "next", "said": "", "status": "working"}],
                      questions=[{"source": "workspace", "turn": 5, "question": "Send it?"}])
    wait_until(page, "document.querySelectorAll('.question').length === 1")
    if contrast:
        page.click("#contrast")
    total = 0
    for tab in ("talk", "tasks", "studio", "control", "doctor"):
        page.click(f"#t-{tab}")
        page.wait_for_timeout(700)
        checked, bad = page.evaluate(CONTRAST)
        assert bad == [], tab  # nosec B101
        total += checked
    assert total > 30 and errors == []  # nosec B101


@pytest.mark.timeout(90)
@pytest.mark.parametrize("width", [640, 320])
def test_text_at_200_percent_and_a_narrow_window_needs_no_sideways_scroll(workspace_page, width):
    """A 1280 pixel window at 200 percent zoom is a 640 pixel page; 320 is the WCAG reflow width."""
    _, page, errors = workspace_page
    page.set_viewport_size({"width": width, "height": 450})
    for tab in ("talk", "tasks", "studio", "control", "doctor"):
        page.click(f"#t-{tab}")
        page.wait_for_timeout(700)
        over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert over <= 0, (tab, over)  # nosec B101
    assert errors == []  # nosec B101


CORE_WITH = {
    "webgl": "",
    "canvas2d": """const real = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function (kind, o) { return kind === "2d" ? real.call(this, kind, o) : null; };""",
    "static": "HTMLCanvasElement.prototype.getContext = function () { return null; };",
}


def opening(tmp_path, engine, init="", reduced=False):
    journal = record(tmp_path, "fresh")
    app = ga.GenesisApp(Layout(tmp_path / "AG", tmp_path / "app"), MANIFEST, replay_journal=journal)
    server = GenesisServer(app.routes(), replay=True)
    context = engine.new_context(reduced_motion="reduce" if reduced else "no-preference")
    # A headless page has no window to hold focus, so the test states it.
    context.add_init_script("document.hasFocus = () => true;" + init)
    page = context.new_page()
    page.goto(server.start() + "&screen=opening")
    wait_until(page, "window.GenesisDebug && !!GenesisDebug.core()")
    return server, context, page


def frames_in(page, ms):
    before = page.evaluate("GenesisDebug.core().frames")
    page.wait_for_timeout(ms)
    return page.evaluate("GenesisDebug.core().frames") - before


@pytest.mark.timeout(60)
@pytest.mark.parametrize("mode", ["webgl", "canvas2d", "static"])
def test_the_core_falls_back_from_webgl_to_canvas_to_a_static_picture(tmp_path, engine, mode):
    server, context, page = opening(tmp_path, engine, CORE_WITH[mode])
    try:
        assert page.evaluate("GenesisDebug.core().mode") == mode  # nosec B101
        drawn = page.evaluate("[document.querySelectorAll('#core canvas').length, document.querySelectorAll('#core svg').length]")
        assert drawn == ([0, 1] if mode == "static" else [1, 0])  # nosec B101
    finally:
        context.close()
        server.stop()


@pytest.mark.timeout(60)
def test_the_core_stops_while_the_window_is_hidden_and_starts_again(tmp_path, engine):
    server, context, page = opening(tmp_path, engine, "Object.defineProperty(document, 'hidden', { get: () => window.isHidden === true });")
    try:
        assert frames_in(page, 500) > 5  # nosec B101
        page.evaluate("window.isHidden = true; document.dispatchEvent(new Event('visibilitychange'))")
        page.wait_for_timeout(100)
        assert frames_in(page, 600) == 0  # nosec B101
        page.evaluate("window.isHidden = false; document.dispatchEvent(new Event('visibilitychange'))")
        assert frames_in(page, 500) > 5  # nosec B101
    finally:
        context.close()
        server.stop()


@pytest.mark.timeout(60)
def test_the_core_runs_at_30_frames_on_battery(tmp_path, engine):
    server, context, page = opening(
        tmp_path, engine, "navigator.getBattery = () => Promise.resolve({ charging: false, addEventListener() {} });")
    try:
        page.wait_for_timeout(200)
        assert 5 < frames_in(page, 2000) <= 66  # nosec B101  30 a second, and a real display would give 120
    finally:
        context.close()
        server.stop()


@pytest.mark.timeout(60)
def test_the_core_never_exceeds_60_frames_on_mains(tmp_path, engine):
    server, context, page = opening(
        tmp_path, engine, "navigator.getBattery = () => Promise.resolve({ charging: true, addEventListener() {} });")
    try:
        page.wait_for_timeout(200)
        assert 5 < frames_in(page, 2000) <= 130  # nosec B101
    finally:
        context.close()
        server.stop()


@pytest.mark.timeout(60)
def test_reduced_motion_draws_a_still_picture(tmp_path, engine):
    server, context, page = opening(tmp_path, engine, reduced=True)
    try:
        assert frames_in(page, 800) == 0  # nosec B101
    finally:
        context.close()
        server.stop()


@pytest.mark.timeout(60)
def test_the_studio_shows_and_saves_the_owners_name(workspace_page):
    fake, page, errors = workspace_page
    page.click("#t-studio")
    wait_until(page, "document.getElementById('owner').value === 'Suraj'")
    page.fill("#owner", "Chotu")
    page.keyboard.press("Tab")
    deadline = time.monotonic() + 5
    while fake.owner != "Chotu" and time.monotonic() < deadline:
        page.wait_for_timeout(50)
    assert fake.owner == "Chotu" and errors == []  # nosec B101


@pytest.mark.timeout(60)
def test_the_window_says_when_the_assistant_has_gone_and_when_it_is_back(workspace_page):
    """The window now outlives the assistant, and a page that stops hearing from it looked alive."""
    _, page, errors = workspace_page
    wait_until(page, "document.getElementById('orb-label').textContent === 'Idle'")
    page.route("**/api/workspace", lambda route: route.abort())
    wait_until(page, "document.getElementById('orb-label').textContent === 'The assistant is not running'")
    page.unroute("**/api/workspace")
    wait_until(page, "document.getElementById('orb-label').textContent === 'Idle'")
    assert errors == []  # nosec B101
