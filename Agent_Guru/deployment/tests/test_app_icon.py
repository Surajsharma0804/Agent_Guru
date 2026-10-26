"""The application icon holds every size Windows asks for, and the builds point at it.

scripts/gen_icon.py saved the icon from its 16x16 image, and Pillow writes only the sizes no larger
than the image it saves from, so assets/icon.ico held 16x16 alone and was scaled up everywhere else.
"""

from __future__ import annotations

import runpy
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def test_the_script_writes_every_size(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runpy.run_path(str(ROOT / "scripts" / "gen_icon.py"), run_name="__main__")
    with Image.open(tmp_path / "assets" / "icon.ico") as icon:
        assert sorted(icon.ico.sizes()) == SIZES  # nosec B101


def test_the_committed_icon_has_every_size():
    with Image.open(ROOT / "assets" / "icon.ico") as icon:
        assert sorted(icon.ico.sizes()) == SIZES  # nosec B101


def test_the_exe_and_the_installer_use_that_icon():
    spec = (ROOT / "AgentGuru.spec").read_text(encoding="utf-8")
    setup = (ROOT / "AgentGuru_setup.iss").read_text(encoding="utf-8")
    assert "icon=str(ROOT / 'assets' / 'icon.ico')" in spec  # nosec B101
    assert "SetupIconFile=assets\\icon.ico" in setup  # nosec B101
