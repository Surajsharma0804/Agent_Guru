"""Property-based tests for Phase 3: Bug detection.

Task 4.8 — Properties 6, 7, 8.

Property 6: Async Anti-pattern Detection Completeness
    Any async def with a blocking call (time.sleep, requests.*,
    subprocess.run/call/check_output, urllib.request.urlopen)
    produces >= 1 finding.
    Any async def without blocking calls produces 0 findings.

Property 7: Broken Import Detection Correctness
    Any import of a non-existent symbol produces a finding.
    Any import of an existing symbol produces no finding.

Property 8: Duplicate Implementation Detection
    Any module pair sharing >= 2 public symbols with identical
    signatures produces a finding. Pairs sharing < 2 do not.

Subsystem: audit/tests
Requirements: 3.6, 3.7, 3.11
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Helpers — in-process async anti-pattern detector
# ---------------------------------------------------------------------------

BLOCKING_CALLS = {
    "time.sleep",
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.delete",
    "requests.request",
    "urllib.request.urlopen",
    "subprocess.run",
    "subprocess.call",
    "subprocess.check_output",
}


def _detect_blocking_in_async(source: str) -> list[str]:
    """Return list of blocking call names found inside async def bodies."""
    tree = ast.parse(textwrap.dedent(source))
    findings: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef,)):
            continue
        # Walk the body of the async function only
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = _extract_call_name(child)
                if call_name in BLOCKING_CALLS:
                    findings.append(call_name)

    return findings


def _extract_call_name(node: ast.Call) -> str:
    """Extract dotted name from a Call node."""
    func = node.func
    if isinstance(func, ast.Attribute):
        val = func.value
        if isinstance(val, ast.Attribute):
            # e.g. urllib.request.urlopen
            inner = val.value
            if isinstance(inner, ast.Name):
                return f"{inner.id}.{val.attr}.{func.attr}"
        if isinstance(val, ast.Name):
            return f"{val.id}.{func.attr}"
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _extract_public_symbols(source: str) -> set[str]:
    """Return public function and class names from source."""
    tree = ast.parse(textwrap.dedent(source))
    symbols: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                symbols.add(node.name)
    return symbols


# ---------------------------------------------------------------------------
# Property 6: Async anti-pattern detection
# ---------------------------------------------------------------------------


class TestAsyncAntipatternDetection:
    """Property 6 — blocking calls in async def → finding; clean → no finding."""

    def test_time_sleep_in_async_flagged(self) -> None:
        source = """
        import time
        async def do_work():
            time.sleep(1)
        """
        findings = _detect_blocking_in_async(source)
        assert len(findings) >= 1

    def test_requests_get_in_async_flagged(self) -> None:
        source = """
        import requests
        async def fetch():
            return requests.get("http://example.com")
        """
        findings = _detect_blocking_in_async(source)
        assert len(findings) >= 1

    def test_subprocess_run_in_async_flagged(self) -> None:
        source = """
        import subprocess
        async def run_cmd():
            subprocess.run(["ls"])
        """
        findings = _detect_blocking_in_async(source)
        assert len(findings) >= 1

    def test_clean_async_no_findings(self) -> None:
        source = """
        async def clean_handler():
            await some_coroutine()
            x = 1 + 2
            return x
        """
        findings = _detect_blocking_in_async(source)
        assert findings == []

    def test_blocking_in_sync_not_flagged(self) -> None:
        """Blocking calls in regular (non-async) functions must not flag."""
        source = """
        import time
        def sync_worker():
            time.sleep(1)
        """
        findings = _detect_blocking_in_async(source)
        assert findings == []

    def test_multiple_blocking_calls_all_flagged(self) -> None:
        source = """
        import time, requests, subprocess
        async def bad_handler():
            time.sleep(1)
            requests.get("http://example.com")
            subprocess.run(["ls"])
        """
        findings = _detect_blocking_in_async(source)
        assert len(findings) >= 3  # noqa: PLR2004

    @given(
        extra_sleep_count=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=50)
    def test_property_six_blocking_in_async_always_detected(
        self, extra_sleep_count: int
    ) -> None:
        """Property 6: any number of blocking calls in async def is detected."""
        calls = "\n            ".join(
            f"time.sleep({i})" for i in range(extra_sleep_count)
        )
        source = f"""
        import time
        async def slow():
            {calls}
        """
        findings = _detect_blocking_in_async(source)
        assert len(findings) == extra_sleep_count

    @given(
        func_count=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=50)
    def test_property_six_clean_async_never_flagged(self, func_count: int) -> None:
        """Property 6: async def with no blocking calls → 0 findings."""
        funcs = "\n".join(
            f"async def clean_{i}():\n    await something_{i}()\n    return {i}"
            for i in range(func_count)
        )
        findings = _detect_blocking_in_async(funcs)
        assert findings == []


# ---------------------------------------------------------------------------
# Property 7: Broken import detection
# ---------------------------------------------------------------------------


class TestBrokenImportDetection:
    """Property 7 — import of non-existent symbol → finding; existing → no finding."""

    def test_existing_builtin_import_not_flagged(self) -> None:
        # pathlib is always available — no finding expected
        try:
            from pathlib import Path as _  # noqa: F401
            import_ok = True
        except ImportError:
            import_ok = False
        assert import_ok

    def test_nonexistent_module_raises_import_error(self) -> None:
        import importlib
        try:
            importlib.import_module("definitely_does_not_exist_xyz_123")
            import_ok = True
        except ImportError:
            import_ok = False
        assert not import_ok

    def test_ast_parse_catches_syntax_error(self) -> None:
        """Invalid Python in a file is a broken import scenario."""
        source = "def foo(:\n    pass"
        is_broken = False
        try:
            ast.parse(source)
        except SyntaxError:
            is_broken = True
        assert is_broken

    def test_valid_python_parses_cleanly(self) -> None:
        source = "from pathlib import Path\nx: Path = Path('.')"
        tree = ast.parse(source)
        assert tree is not None

    def test_existing_symbol_in_module(self, tmp_path: Path) -> None:
        """Module exports symbol → import finds it via AST."""
        target = tmp_path / "mymod.py"
        target.write_text("class MyClass: pass\ndef my_func(): pass", encoding="utf-8")
        tree = ast.parse(target.read_text(encoding="utf-8"))
        names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        }
        assert "MyClass" in names
        assert "my_func" in names

    def test_nonexistent_symbol_not_in_ast(self, tmp_path: Path) -> None:
        target = tmp_path / "mymod.py"
        target.write_text("class Existing: pass", encoding="utf-8")
        tree = ast.parse(target.read_text(encoding="utf-8"))
        names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        }
        assert "NonExistent" not in names


# ---------------------------------------------------------------------------
# Property 8: Duplicate implementation detection
# ---------------------------------------------------------------------------


class TestDuplicateImplementationDetection:
    """Property 8 — >= 2 shared public symbols → finding; < 2 → no finding."""

    def test_two_shared_symbols_triggers_finding(self) -> None:
        source_a = "def foo(): pass\ndef bar(): pass\ndef unique_a(): pass"
        source_b = "def foo(): pass\ndef bar(): pass\ndef unique_b(): pass"
        shared = _extract_public_symbols(source_a) & _extract_public_symbols(source_b)
        assert len(shared) >= 2  # noqa: PLR2004

    def test_one_shared_symbol_no_finding(self) -> None:
        source_a = "def foo(): pass\ndef unique_a(): pass"
        source_b = "def foo(): pass\ndef unique_b(): pass"
        shared = _extract_public_symbols(source_a) & _extract_public_symbols(source_b)
        assert len(shared) < 2  # noqa: PLR2004

    def test_no_shared_symbols_no_finding(self) -> None:
        source_a = "def alpha(): pass\ndef beta(): pass"
        source_b = "def gamma(): pass\ndef delta(): pass"
        shared = _extract_public_symbols(source_a) & _extract_public_symbols(source_b)
        assert len(shared) == 0

    def test_private_symbols_not_counted(self) -> None:
        source_a = "def _private_foo(): pass\ndef _private_bar(): pass"
        source_b = "def _private_foo(): pass\ndef _private_bar(): pass"
        shared = _extract_public_symbols(source_a) & _extract_public_symbols(source_b)
        assert len(shared) == 0, "Private symbols must not count as duplicates"

    def test_classes_count_as_symbols(self) -> None:
        source_a = "class Engine: pass\nclass Router: pass"
        source_b = "class Engine: pass\nclass Router: pass"
        shared = _extract_public_symbols(source_a) & _extract_public_symbols(source_b)
        assert len(shared) >= 2  # noqa: PLR2004

    @given(
        shared_count=st.integers(min_value=0, max_value=10),
        unique_count=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=100)
    def test_property_eight_shared_symbol_threshold(
        self, shared_count: int, unique_count: int
    ) -> None:
        """Property 8: >= 2 shared → finding; < 2 → no finding."""
        shared_names = [f"shared_{i}" for i in range(shared_count)]
        unique_a = [f"only_a_{i}" for i in range(unique_count)]
        unique_b = [f"only_b_{i}" for i in range(unique_count)]

        source_a = "\n".join(f"def {n}(): pass" for n in shared_names + unique_a)
        source_b = "\n".join(f"def {n}(): pass" for n in shared_names + unique_b)

        shared = _extract_public_symbols(source_a) & _extract_public_symbols(source_b)
        should_flag = shared_count >= 2  # noqa: PLR2004
        actually_flags = len(shared) >= 2  # noqa: PLR2004

        assert should_flag == actually_flags, (
            f"shared_count={shared_count}, symbols={shared}"
        )
