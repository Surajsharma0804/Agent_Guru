"""Screen text read through PowerShell keeps every language.

PowerShell wrote in the OEM code page and Python read cp1252, so a Hindi
window title became "??????" and one "ü" (byte 0x81) killed the decoding
thread and lost all of the screen's text. These run real PowerShell.
"""

from __future__ import annotations

import sys

import pytest

from Agent_Guru.platform.features.screen_reader import _run_powershell

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="PowerShell UI Automation is Windows only")


def _chars(*codepoints):
    return " + ".join(f"[char]0x{c:04X}" for c in codepoints)


def test_non_latin_text_arrives_intact():
    # नमस्ते, built from code points so this file's own encoding cannot matter.
    out = _run_powershell(f"Write-Output ([string]({_chars(0x928, 0x92E, 0x938, 0x94D, 0x924, 0x947)}) + ' - YouTube')", 10)
    assert out.strip() == "नमस्ते - YouTube"  # nosec B101


def test_a_byte_cp1252_does_not_define_does_not_lose_the_text():
    # "ü" is 0x81 in code page 437, undefined in cp1252.
    out = _run_powershell('Write-Output ("Men" + [char]0x00FC + " anzeigen")', 10)
    assert out.strip() == "Menü anzeigen"  # nosec B101
