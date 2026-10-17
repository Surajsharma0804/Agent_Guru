"""Unified diffs apply exactly, or not at all."""

from __future__ import annotations

import pytest

from Agent_Guru.utils.patching import PatchError, apply

CALC = "def add(a, b):\n    return a - b\n\n\ndef mul(a, b):\n    return a * b\n"


def test_a_hunk_replaces_exactly_its_lines():
    diff = "--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n-    return a - b\n+    return a + b\n"
    assert apply({"calc.py": CALC}, diff) == {"calc.py": CALC.replace("a - b", "a + b")}  # nosec B101


def test_a_hunk_whose_line_numbers_are_off_still_finds_its_place():
    diff = "--- a/calc.py\n+++ b/calc.py\n@@ -9,2 +9,3 @@\n def mul(a, b):\n+    # product\n     return a * b\n"
    assert "def mul(a, b):\n    # product\n    return a * b\n" in apply({"calc.py": CALC}, diff)["calc.py"]  # nosec B101


def test_new_and_deleted_files():
    diff = ("--- /dev/null\n+++ b/test_calc.py\n@@ -0,0 +1,2 @@\n+from calc import add\n+assert add(2, 3) == 5\n"
            "--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x = 1\n")
    out = apply({"calc.py": CALC, "old.py": "x = 1\n"}, diff)
    assert out == {"test_calc.py": "from calc import add\nassert add(2, 3) == 5\n", "old.py": None}  # nosec B101


@pytest.mark.parametrize(("diff", "why"), [
    ("--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,2 @@\n def add(x, y):\n-    return x - y\n+    return x + y\n", "does not match"),
    ("--- a/missing.py\n+++ b/missing.py\n@@ -1 +1 @@\n-a\n+b\n", "no such file"),
    ("--- a/../../etc/passwd\n+++ b/../../etc/passwd\n@@ -1 +1 @@\n-a\n+b\n", "inside the project"),
    ("just some words", "no file changes"),
])
def test_a_diff_that_does_not_fit_changes_nothing(diff, why):
    files = {"calc.py": CALC}
    with pytest.raises(PatchError, match=why):
        apply(files, diff)
    assert files == {"calc.py": CALC}  # nosec B101


def test_two_hunks_in_one_file_keep_their_offsets():
    diff = ("--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,3 @@\n+'''Arithmetic.'''\n def add(a, b):\n     return a - b\n"
            "@@ -5,2 +6,2 @@\n def mul(a, b):\n-    return a * b\n+    return b * a\n")
    out = apply({"calc.py": CALC}, diff)["calc.py"]
    assert out.startswith("'''Arithmetic.'''\ndef add") and "return b * a" in out  # nosec B101
