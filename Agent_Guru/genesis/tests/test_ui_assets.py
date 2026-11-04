"""The vendored UI: inside its budget, nothing remote, one tokens file, every string resolved."""

from __future__ import annotations

import json
import re
import struct

from Agent_Guru.genesis.server import UI_DIR

BUDGET = 3 * 1000 * 1000


def _text(name):
    return (UI_DIR / name).read_text(encoding="utf-8")


def test_the_ui_fits_its_budget_fonts_included():
    total = sum(p.stat().st_size for p in UI_DIR.rglob("*") if p.is_file())
    assert 0 < total <= BUDGET, total  # nosec B101


def test_nothing_is_fetched_from_another_host_while_rendering():
    for name in ("index.html", "workspace.html", "tokens.css", "app.js", "workspace.js", "core.js"):
        found = re.findall(r"https?://[^\s\"')]+", _text(name))
        assert found == [], (name, found)  # nosec B101
    assert "@import" not in _text("tokens.css")  # nosec B101


def test_no_inline_style_or_script_that_the_content_policy_would_block():
    for name in ("index.html", "workspace.html"):
        html = _text(name)
        assert "style=" not in html and not re.search(r"<script(?![^>]*\bsrc=)", html), name  # nosec B101
        assert " onclick=" not in html, name  # nosec B101


def test_colours_live_only_in_the_tokens_file():
    for name in ("index.html", "workspace.html", "app.js", "workspace.js", "core.js"):
        assert re.findall(r"#[0-9a-fA-F]{6}\b", _text(name)) == [], name  # nosec B101


def test_every_string_key_the_page_uses_exists():
    strings = json.loads(_text("strings.en.json"))
    used = set()
    for name in ("index.html", "workspace.html"):
        used |= set(re.findall(r'data-[sp]="([^"]+)"', _text(name)))
    for name in ("app.js", "workspace.js"):
        used |= set(re.findall(r'\bt\("([a-z.]+[a-zA-Z.]*)"', _text(name)))
        used |= set(re.findall(r'"(ws\.[a-z.]+)"', _text(name)))
    assert not [k for k in used if not k.endswith(".") and k not in strings]  # nosec B101
    # The two keys built at run time, from a stage name and a journal state.
    from Agent_Guru.genesis.journal import _STATE_AFTER
    from Agent_Guru.genesis.manifest import STAGES

    assert all(f"stage.{s}" in strings for s in STAGES)  # nosec B101
    assert all(f"state.{s}" in strings for s in ["not started", *_STATE_AFTER.values()])  # nosec B101
    # Built at run time from the orb state and the tab name.
    assert all(f"ws.orb.{s}" in strings for s in ("idle", "listening", "thinking", "speaking", "muted"))  # nosec B101
    assert all(f"ws.tab.{s}" in strings for s in ("talk", "tasks", "studio", "control", "doctor"))  # nosec B101


def test_the_plan_says_in_plain_words_that_the_microphone_starts_with_the_computer():
    strings = json.loads(_text("strings.en.json"))
    assert '"tier." + name' in _text("app.js")  # nosec B101
    assert "Hey Guru" in strings["tier.startup"] and "tray icon" in strings["tier.startup"]  # nosec B101


def test_the_ui_text_has_no_long_dashes():
    for name in ("index.html", "workspace.html", "strings.en.json", "app.js", "workspace.js", "core.js", "tokens.css"):
        assert not re.search("[\u2013\u2014]", _text(name)), name  # nosec B101


def _cmap(path):
    """The code points a TrueType font maps, from its format 4 cmap subtable."""
    data = path.read_bytes()
    tables = struct.unpack(">H", data[4:6])[0]
    for i in range(tables):
        tag, _, offset, _ = struct.unpack(">4sLLL", data[12 + i * 16:28 + i * 16])
        if tag == b"cmap":
            break
    subtables = struct.unpack(">H", data[offset + 2:offset + 4])[0]
    points: set[int] = set()
    for i in range(subtables):
        _, _, sub = struct.unpack(">HHL", data[offset + 4 + i * 8:offset + 12 + i * 8])
        base = offset + sub
        if struct.unpack(">H", data[base:base + 2])[0] != 4:
            continue
        segs = struct.unpack(">H", data[base + 6:base + 8])[0] // 2
        ends = struct.unpack(f">{segs}H", data[base + 14:base + 14 + segs * 2])
        starts = struct.unpack(f">{segs}H", data[base + 16 + segs * 2:base + 16 + segs * 4])
        for start, end in zip(starts, ends, strict=True):
            points.update(range(start, end + 1))
    return points


def test_the_bundled_font_has_the_devanagari_of_the_wake_words():
    needed = {ord(c) for c in "हे गुरु माया" if c != " "}
    for font in ("Rajdhani-Medium.ttf", "Rajdhani-SemiBold.ttf"):
        assert needed <= _cmap(UI_DIR / "fonts" / font), font  # nosec B101


def test_the_font_licence_travels_with_the_font():
    assert "SIL Open Font License" in _text("fonts/OFL.txt")  # nosec B101
