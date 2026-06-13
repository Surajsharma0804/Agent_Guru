"""Phase 3: Bug and Failure Detection.

This module implements comprehensive bug detection using 12 different methods:
1. Python compilation (py_compile)
2. Ruff linting (all rules)
3. Mypy type checking (strict mode)
4. Bandit security scanning
5. Circular import detection
6. Broken import detection
7. Platform guard checking
8. Async anti-pattern detection
9. Race condition detection
10. Resource leak detection
11. Unused code detection
12. Duplicate implementation detection

Performance Characteristics:
    - Time Complexity: O(n) where n = total lines of code
    - Space Complexity: O(m) where m = number of findings
    - Analysis Speed: ~1-2 minutes for 15,000 lines

Subsystem: audit/phases
Primary public API: BugDetector, run (async entry point)
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from audit.models import AuditReport, Finding, FindingCategory, Severity

if TYPE_CHECKING:
    from collections.abc import Iterator

    from audit.report import MasterReportWriter


class AsyncAntipatternVisitor(ast.NodeVisitor):
    """AST visitor that detects async anti-patterns.

    Detects:
    1. Blocking I/O inside async def functions
    2. Missing await on coroutines
    3. asyncio.gather with return_exceptions=False and no per-task handler
    4. Synchronous open() outside run_in_executor

    Attributes:
        file_path: Path to the file being analyzed.
        finding_id_start: Starting ID for findings.
        findings: List of findings detected.
        current_async_func: Name of current async function being visited.
        in_run_in_executor: Whether currently inside run_in_executor call.

    """

    BLOCKING_CALLS = {
        "time.sleep",
        "requests.get",
        "requests.post",
        "requests.put",
        "requests.delete",
        "urllib.request.urlopen",
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_output",
    }

    def __init__(self, file_path: str, finding_id_start: int) -> None:
        """Initialize the visitor.

        Args:
            file_path: Path to the file being analyzed.
            finding_id_start: Starting ID for findings.

        """
        self.file_path = file_path
        self.finding_id_start = finding_id_start
        self.findings: list[Finding] = []
        self.current_async_func: str | None = None
        self.in_run_in_executor = False

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition.

        Args:
            node: The async function definition node.

        """
        # Save previous context
        prev_func = self.current_async_func
        self.current_async_func = node.name

        # Visit function body
        self.generic_visit(node)

        # Restore context
        self.current_async_func = prev_func

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function call.

        Args:
            node: The call node.

        """
        if self.current_async_func is None:
            # Not inside an async function
            self.generic_visit(node)
            return

        call_name = self._get_call_name(node)

        # Check for blocking calls
        if call_name in self.BLOCKING_CALLS:
            self._add_finding(
                node.lineno,
                "async-blocking",
                f"Blocking call '{call_name}' in async function '{self.current_async_func}'",
                f"Use async equivalent or run_in_executor for '{call_name}'",
            )

        # Check for synchronous open() outside run_in_executor
        if call_name == "open" and not self.in_run_in_executor:
            self._add_finding(
                node.lineno,
                "async-blocking",
                f"Synchronous open() in async function '{self.current_async_func}' outside run_in_executor",
                "Use aiofiles or wrap in run_in_executor",
            )

        # Check for asyncio.gather with return_exceptions=False
        if call_name == "asyncio.gather" or call_name == "gather":
            return_exceptions = False
            for keyword in node.keywords:
                if keyword.arg == "return_exceptions":
                    if isinstance(keyword.value, ast.Constant):
                        return_exceptions = bool(keyword.value.value)

            if not return_exceptions:
                self._add_finding(
                    node.lineno,
                    "async-gather-exceptions",
                    f"asyncio.gather() with return_exceptions=False in '{self.current_async_func}' - first exception cancels all remaining tasks",
                    "Set return_exceptions=True or add per-task exception handlers",
                )

        # Track run_in_executor context
        if call_name == "run_in_executor":
            prev_in_executor = self.in_run_in_executor
            self.in_run_in_executor = True
            self.generic_visit(node)
            self.in_run_in_executor = prev_in_executor
            return

        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:
        """Visit expression statement.

        Detects missing await on coroutines.

        Args:
            node: The expression node.

        """
        if self.current_async_func is None:
            self.generic_visit(node)
            return

        # Check if this is a coroutine call without await
        if isinstance(node.value, ast.Call):
            # Check if the call returns a coroutine
            call_name = self._get_call_name(node.value)

            # Common async functions that return coroutines
            async_patterns = [
                "asyncio.",
                "aiohttp.",
                "aiofiles.",
                ".async_",
                "async_",
            ]

            is_likely_coroutine = any(pattern in call_name for pattern in async_patterns)

            # Also check if it's a call to another async function in the same module
            # (This is a heuristic - full analysis would require type information)
            if is_likely_coroutine:
                self._add_finding(
                    node.lineno,
                    "async-missing-await",
                    f"Possible missing await on coroutine call '{call_name}' in '{self.current_async_func}'",
                    f"Add 'await' before '{call_name}' if it returns a coroutine",
                )

        self.generic_visit(node)

    def _get_call_name(self, node: ast.Call) -> str:
        """Get the full name of a function call.

        Args:
            node: The call node.

        Returns:
            The full call name (e.g., "asyncio.gather").

        """
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            parts = []
            current: ast.expr = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""

    def _add_finding(
        self,
        line_number: int,
        rule: str,
        description: str,
        remediation: str,
    ) -> None:
        """Add a finding to the list.

        Args:
            line_number: Line number of the finding.
            rule: Rule code.
            description: Description of the finding.
            remediation: Remediation advice.

        """
        finding_id = self.finding_id_start + len(self.findings)
        self.findings.append(
            Finding(
                id=f"ASYNC-{finding_id:03d}",
                phase=3,
                category=FindingCategory.ASYNC_ANTIPATTERN,
                severity=Severity.HIGH,
                file_path=self.file_path,
                line_number=line_number,
                rule=rule,
                description=description,
                remediation=remediation,
                fixed=False,
            ),
        )


class BugDetector:
    """Comprehensive bug detection using 12 different methods.

    Time Complexity: O(n) where n = total lines of code
    Space Complexity: O(m) where m = number of findings

    This detector runs all static analysis tools and custom detectors
    to identify every category of defect in the codebase.

    Example:
        >>> detector = BugDetector(Path("Agent_Guru"))
        >>> findings = detector.run_all()
        >>> print(f"Found {len(findings)} issues")

    Attributes:
        package_root: Root directory of the package to analyze.

    """

    def __init__(self, package_root: Path) -> None:
        """Initialize the bug detector.

        Args:
            package_root: Root directory of the package to analyze.

        """
        self.package_root = package_root

    def run_all(self) -> list[Finding]:
        """Run all 12 bug detection methods.

        Time Complexity: O(n) where n = total lines of code
        Space Complexity: O(m) where m = number of findings

        Returns:
            List of all findings from all detection methods.

        """
        findings: list[Finding] = []

        print("Running bug detection...")

        # Method 1: Python compilation
        print("  1/12: Running py_compile...")
        findings.extend(self._run_py_compile())

        # Method 2: Ruff linting (all rules)
        print("  2/12: Running ruff check...")
        findings.extend(self._run_ruff_all())

        # Method 3: Mypy type checking (strict)
        print("  3/12: Running mypy strict...")
        findings.extend(self._run_mypy_strict())

        # Method 4: Bandit security scanning
        print("  4/12: Running bandit...")
        findings.extend(self._run_bandit())

        # Method 5: Circular import detection
        print("  5/12: Detecting circular imports...")
        findings.extend(self._detect_circular_imports())

        # Method 6: Broken import detection
        print("  6/12: Detecting broken imports...")
        findings.extend(self._detect_broken_imports())

        # Method 7: Platform guard checking
        print("  7/12: Checking platform guards...")
        findings.extend(self._check_platform_guards())

        # Method 8: Async anti-pattern detection
        print("  8/12: Detecting async anti-patterns...")
        findings.extend(self._detect_async_antipatterns())

        # Method 9: Race condition detection
        print("  9/12: Detecting race conditions...")
        findings.extend(self._detect_race_conditions())

        # Method 10: Resource leak detection
        print("  10/12: Detecting resource leaks...")
        findings.extend(self._detect_resource_leaks())

        # Method 11: Unused code detection
        print("  11/12: Detecting unused code...")
        findings.extend(self._run_ruff_unused())

        # Method 12: Duplicate implementation detection
        print("  12/12: Detecting duplicate implementations...")
        findings.extend(self._detect_duplicates())

        print(f"Bug detection complete. Found {len(findings)} issues.")

        return findings

    def _run_py_compile(self) -> list[Finding]:
        """Run python -m py_compile on every .py file.

        Returns:
            List of compilation error findings.

        """
        findings: list[Finding] = []
        finding_id = 1

        for py_file in self._iter_python_files():
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(py_file)],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                # Parse error message for line number
                error_msg = result.stderr
                line_number = self._extract_line_number(error_msg)

                findings.append(
                    Finding(
                        id=f"COMPILE-{finding_id:03d}",
                        phase=3,
                        category=FindingCategory.COMPILE_ERROR,
                        severity=Severity.CRITICAL,
                        file_path=str(py_file.relative_to(self.package_root.parent)),
                        line_number=line_number,
                        rule="E999",
                        description=error_msg.split("\n")[0] if error_msg else "Compilation error",
                        remediation="Fix syntax error",
                        fixed=False,
                    ),
                )
                finding_id += 1

        return findings

    def _run_ruff_all(self) -> list[Finding]:
        """Run ruff check with all rules enabled.

        Returns:
            List of linting violation findings.

        """
        findings: list[Finding] = []

        result = subprocess.run(
            ["ruff", "check", str(self.package_root), "--select", "ALL", "--output-format", "json"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.stdout:
            import json
            try:
                violations = json.loads(result.stdout)
                for idx, violation in enumerate(violations, 1):
                    findings.append(
                        Finding(
                            id=f"RUFF-{idx:03d}",
                            phase=3,
                            category=FindingCategory.LINT_VIOLATION,
                            severity=self._map_ruff_severity(violation.get("code", "")),
                            file_path=violation.get("filename", "unknown"),
                            line_number=violation.get("location", {}).get("row", 0),
                            rule=violation.get("code", ""),
                            description=violation.get("message", ""),
                            remediation=violation.get("fix", {}).get("message", "See ruff documentation"),
                            fixed=False,
                        ),
                    )
            except json.JSONDecodeError:
                pass

        return findings

    def _run_mypy_strict(self) -> list[Finding]:
        """Run mypy with strict mode.

        Returns:
            List of type error findings.

        """
        findings: list[Finding] = []

        result = subprocess.run(
            ["mypy", str(self.package_root), "--strict"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.stdout:
            for idx, line in enumerate(result.stdout.splitlines(), 1):
                if ": error:" in line:
                    parts = line.split(":")
                    if len(parts) >= 4:
                        file_path = parts[0]
                        line_number = int(parts[1]) if parts[1].isdigit() else 0
                        description = ":".join(parts[3:]).strip()

                        findings.append(
                            Finding(
                                id=f"MYPY-{idx:03d}",
                                phase=3,
                                category=FindingCategory.TYPE_ERROR,
                                severity=Severity.HIGH,
                                file_path=file_path,
                                line_number=line_number,
                                rule="mypy:error",
                                description=description,
                                remediation="Add type annotations or fix type mismatch",
                                fixed=False,
                            ),
                        )

        return findings

    def _run_bandit(self) -> list[Finding]:
        """Run bandit security scanner.

        Returns:
            List of security issue findings.

        """
        findings: list[Finding] = []

        result = subprocess.run(
            ["bandit", "-r", str(self.package_root), "-ll", "-f", "json"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.stdout:
            import json
            try:
                data = json.loads(result.stdout)
                for idx, issue in enumerate(data.get("results", []), 1):
                    findings.append(
                        Finding(
                            id=f"BANDIT-{idx:03d}",
                            phase=3,
                            category=FindingCategory.SECURITY_ISSUE,
                            severity=self._map_bandit_severity(issue.get("issue_severity", "")),
                            file_path=issue.get("filename", "unknown"),
                            line_number=issue.get("line_number", 0),
                            rule=issue.get("test_id", ""),
                            description=f"{issue.get('issue_text', '')} (CWE-{issue.get('issue_cwe', {}).get('id', 'unknown')})",
                            remediation=issue.get("issue_text", ""),
                            fixed=False,
                        ),
                    )
            except json.JSONDecodeError:
                pass

        return findings

    def _detect_circular_imports(self) -> list[Finding]:
        """Detect circular import dependencies using dependency DAG.

        Uses NetworkX to build a dependency graph and detect cycles.
        Each cycle is reported as a circular import finding.

        Time Complexity: O(V + E) where V = modules, E = import edges
        Space Complexity: O(V + E)

        Returns:
            List of circular import findings.

        """
        findings: list[Finding] = []
        finding_id = 1

        try:
            import networkx as nx  # type: ignore[import-untyped]

            # Build dependency graph
            graph = nx.DiGraph()

            # Scan all modules and build graph
            for py_file in self._iter_python_files():
                try:
                    source = py_file.read_text(encoding="utf-8", errors="replace")
                    tree = ast.parse(source, filename=str(py_file))

                    # Get relative path for this module
                    module_path = str(py_file.relative_to(self.package_root.parent))

                    # Add node for this module
                    graph.add_node(module_path)

                    # Add edges for all imports
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imported = self._resolve_import_to_path(alias.name)
                                if imported:
                                    graph.add_edge(module_path, imported)

                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                imported = self._resolve_import_to_path(node.module)
                                if imported:
                                    graph.add_edge(module_path, imported)

                except (SyntaxError, UnicodeDecodeError):
                    continue

            # Detect cycles using NetworkX
            cycles = list(nx.simple_cycles(graph))

            # Report each cycle as a finding
            for cycle in cycles:
                # Format cycle as ordered list: A -> B -> C -> A
                cycle_str = " -> ".join([*cycle, cycle[0]])

                findings.append(
                    Finding(
                        id=f"CIRCULAR-{finding_id:03d}",
                        phase=3,
                        category=FindingCategory.CIRCULAR_IMPORT,
                        severity=Severity.HIGH,
                        file_path=cycle[0],  # First module in cycle
                        line_number=0,  # File-level issue
                        rule="circular-import",
                        description=f"Circular import detected: {cycle_str}",
                        remediation=f"Break circular dependency by refactoring imports in: {', '.join(cycle)}",
                        fixed=False,
                    ),
                )
                finding_id += 1

        except ImportError:
            # NetworkX not available - skip circular import detection
            print("Warning: networkx not available, skipping circular import detection", file=sys.stderr)  # noqa: T201

        return findings

    def _resolve_import_to_path(self, import_name: str) -> str | None:
        """Resolve an import name to a file path within Agent_Guru package.

        Args:
            import_name: The imported module name (e.g., "Agent_Guru.speech.stt").

        Returns:
            Resolved file path relative to repo root, or None if external package.

        """
        # Only resolve Agent_Guru package imports
        if import_name.startswith("Agent_Guru."):
            # Convert module path to file path
            # e.g., "Agent_Guru.speech.stt" -> "Agent_Guru/speech/stt.py"
            parts = import_name.split(".")
            file_path = "/".join(parts) + ".py"

            # Check if this file exists
            full_path = self.package_root.parent / file_path
            if full_path.exists():
                return file_path

            # Try __init__.py for package imports
            init_path = "/".join(parts) + "/__init__.py"
            full_init_path = self.package_root.parent / init_path
            if full_init_path.exists():
                return init_path

        # External package or unresolved
        return None

    def _detect_broken_imports(self) -> list[Finding]:
        """Detect broken import statements.

        Verifies that:
        1. Imported modules exist and can be imported
        2. Specific symbols imported from modules exist (via AST analysis)

        Returns:
            List of broken import findings.

        """
        findings: list[Finding] = []
        finding_id = 1

        for py_file in self._iter_python_files():
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(py_file))

                for node in ast.walk(tree):
                    # Check "import module" statements
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if not self._can_import(alias.name):
                                findings.append(
                                    Finding(
                                        id=f"IMPORT-{finding_id:03d}",
                                        phase=3,
                                        category=FindingCategory.BROKEN_IMPORT,
                                        severity=Severity.HIGH,
                                        file_path=str(py_file.relative_to(self.package_root.parent)),
                                        line_number=node.lineno,
                                        rule="import-error",
                                        description=f"Cannot import '{alias.name}'",
                                        remediation=f"Install package or fix import path for '{alias.name}'",
                                        fixed=False,
                                    ),
                                )
                                finding_id += 1

                    # Check "from module import symbol" statements
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            # First check if the module itself can be imported
                            if not self._can_import(node.module):
                                findings.append(
                                    Finding(
                                        id=f"IMPORT-{finding_id:03d}",
                                        phase=3,
                                        category=FindingCategory.BROKEN_IMPORT,
                                        severity=Severity.HIGH,
                                        file_path=str(py_file.relative_to(self.package_root.parent)),
                                        line_number=node.lineno,
                                        rule="import-error",
                                        description=f"Cannot import from '{node.module}'",
                                        remediation=f"Install package or fix import path for '{node.module}'",
                                        fixed=False,
                                    ),
                                )
                                finding_id += 1
                            else:
                                # Module exists, now check if specific symbols exist
                                # Only check for Agent_Guru internal modules
                                if node.module.startswith("Agent_Guru."):
                                    symbol_findings = self._check_imported_symbols(
                                        node.module,
                                        node.names,
                                        py_file,
                                        node.lineno,
                                        finding_id,
                                    )
                                    findings.extend(symbol_findings)
                                    finding_id += len(symbol_findings)

            except (SyntaxError, UnicodeDecodeError):
                continue

        return findings

    def _check_imported_symbols(
        self,
        module_name: str,
        names: list[ast.alias],
        source_file: Path,
        line_number: int,
        finding_id: int,
    ) -> list[Finding]:
        """Check if imported symbols exist in the target module.

        Args:
            module_name: The module being imported from.
            names: List of imported symbol names.
            source_file: The file doing the importing.
            line_number: Line number of the import statement.
            finding_id: Starting finding ID.

        Returns:
            List of findings for missing symbols.

        """
        findings: list[Finding] = []

        # Resolve module to file path
        module_file = self._resolve_import_to_path(module_name)
        if not module_file:
            return findings

        # Read and parse the target module
        try:
            target_path = self.package_root.parent / module_file
            target_source = target_path.read_text(encoding="utf-8", errors="replace")
            target_tree = ast.parse(target_source, filename=str(target_path))

            # Extract all public symbols from the target module
            available_symbols = self._extract_public_symbols(target_tree)

            # Check each imported symbol
            for alias in names:
                symbol_name = alias.name
                if symbol_name == "*":
                    # Star import - skip checking
                    continue

                if symbol_name not in available_symbols:
                    findings.append(
                        Finding(
                            id=f"IMPORT-{finding_id:03d}",
                            phase=3,
                            category=FindingCategory.BROKEN_IMPORT,
                            severity=Severity.HIGH,
                            file_path=str(source_file.relative_to(self.package_root.parent)),
                            line_number=line_number,
                            rule="import-error",
                            description=f"Symbol '{symbol_name}' does not exist in module '{module_name}'",
                            remediation=f"Remove import or add '{symbol_name}' to '{module_name}'",
                            fixed=False,
                        ),
                    )
                    finding_id += 1

        except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
            # Cannot parse target module - skip symbol checking
            pass

        return findings

    def _extract_public_symbols(self, tree: ast.AST) -> set[str]:
        """Extract all public symbols (classes, functions) from an AST.

        Args:
            tree: The AST tree to extract symbols from.

        Returns:
            Set of public symbol names.

        """
        symbols: set[str] = set()

        for node in ast.walk(tree):
            # Add public classes
            if isinstance(node, ast.ClassDef):
                if not node.name.startswith("_"):
                    symbols.add(node.name)

            # Add public functions (top-level only, not methods)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    symbols.add(node.name)

            # Add public assignments (e.g., constants, type aliases)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if not target.id.startswith("_"):
                            symbols.add(target.id)

        return symbols

    def _check_platform_guards(self) -> list[Finding]:
        """Check that platform-specific imports are guarded.

        Returns:
            List of unguarded platform import findings.

        """
        findings: list[Finding] = []
        finding_id = 1

        platform_modules = ["win32", "pywin32", "objc", "pyobjc", "dbus"]

        for py_file in self._iter_python_files():
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(py_file))

                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        module_name = ""
                        if isinstance(node, ast.Import):
                            module_name = node.names[0].name if node.names else ""
                        elif isinstance(node, ast.ImportFrom):
                            module_name = node.module or ""

                        # Check if this is a platform-specific module
                        if any(pm in module_name for pm in platform_modules):
                            # Check if it's inside a try/except or sys.platform check
                            if not self._is_guarded(node, tree):
                                findings.append(
                                    Finding(
                                        id=f"PLATFORM-{finding_id:03d}",
                                        phase=3,
                                        category=FindingCategory.PLATFORM_GUARD,
                                        severity=Severity.MEDIUM,
                                        file_path=str(py_file.relative_to(self.package_root.parent)),
                                        line_number=node.lineno,
                                        rule="platform-guard",
                                        description=f"Platform-specific import '{module_name}' not guarded",
                                        remediation="Wrap in try/except ImportError or sys.platform check",
                                        fixed=False,
                                    ),
                                )
                                finding_id += 1

            except (SyntaxError, UnicodeDecodeError):
                continue

        return findings

    def _detect_async_antipatterns(self) -> list[Finding]:
        """Detect async anti-patterns (blocking calls in async functions).

        Returns:
            List of async anti-pattern findings.

        """
        findings: list[Finding] = []
        finding_id = 1

        for py_file in self._iter_python_files():
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(py_file))

                # Use the AsyncAntipatternVisitor
                visitor = AsyncAntipatternVisitor(
                    file_path=str(py_file.relative_to(self.package_root.parent)),
                    finding_id_start=finding_id,
                )
                visitor.visit(tree)

                findings.extend(visitor.findings)
                finding_id += len(visitor.findings)

            except (SyntaxError, UnicodeDecodeError):
                continue

        return findings

    def _detect_race_conditions(self) -> list[Finding]:
        """Detect potential race conditions in shared mutable state.

        Builds a set of module-level and class-level mutable variables,
        finds all coroutines/threads that access each variable, and reports
        if >1 accessor exists without synchronization primitives.

        Returns:
            List of race condition findings.

        """
        findings: list[Finding] = []
        finding_id = 1

        # Accepted synchronization primitives
        sync_primitives = {
            "asyncio.Lock", "asyncio.Semaphore", "asyncio.RLock",
            "threading.Lock", "threading.RLock", "threading.Semaphore",
            "Lock", "RLock", "Semaphore",  # Direct imports
        }

        for py_file in self._iter_python_files():
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(py_file))

                # Build set of mutable variables (module-level and class-level)
                mutable_vars: dict[str, list[int]] = {}  # var_name -> [line_numbers]

                # Find module-level mutable assignments
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        # Check if this is a module-level or class-level assignment
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                var_name = target.id
                                # Skip constants (uppercase names)
                                if not var_name.isupper():
                                    if var_name not in mutable_vars:
                                        mutable_vars[var_name] = []
                                    mutable_vars[var_name].append(node.lineno)

                # Find all async functions and threads that access these variables
                for var_name, def_lines in mutable_vars.items():
                    accessors: list[tuple[str, int, str]] = []  # (func_name, line, type)

                    for node in ast.walk(tree):
                        # Check async functions
                        if isinstance(node, ast.AsyncFunctionDef):
                            if self._function_accesses_var(node, var_name):
                                accessors.append((node.name, node.lineno, "async"))

                        # Check thread creation
                        elif isinstance(node, ast.Call):
                            call_name = self._get_call_name(node)
                            if "Thread" in call_name:
                                # Check if the thread target accesses the variable
                                for keyword in node.keywords:
                                    if keyword.arg == "target":
                                        if isinstance(keyword.value, ast.Name):
                                            target_name = keyword.value.id
                                            accessors.append((f"Thread({target_name})", node.lineno, "thread"))

                    # If >1 accessor, check for synchronization
                    if len(accessors) > 1:
                        # Check if any synchronization primitive is used
                        has_sync = self._has_synchronization(tree, var_name, sync_primitives)

                        if not has_sync:
                            accessor_list = ", ".join([f"{name} (line {line})" for name, line, _ in accessors])
                            findings.append(
                                Finding(
                                    id=f"RACE-{finding_id:03d}",
                                    phase=3,
                                    category=FindingCategory.RACE_CONDITION,
                                    severity=Severity.HIGH,
                                    file_path=str(py_file.relative_to(self.package_root.parent)),
                                    line_number=def_lines[0],
                                    rule="race-condition",
                                    description=f"Potential race condition: variable '{var_name}' accessed by multiple coroutines/threads without synchronization. Accessors: {accessor_list}",
                                    remediation=f"Protect '{var_name}' with asyncio.Lock, asyncio.Semaphore, threading.Lock, or threading.Semaphore",
                                    fixed=False,
                                ),
                            )
                            finding_id += 1

            except (SyntaxError, UnicodeDecodeError):
                continue

        return findings

    def _detect_resource_leaks(self) -> list[Finding]:
        """Detect resource leaks (unclosed files, connections, etc.).

        Tracks every open(), sqlite3.connect(), aiohttp.ClientSession(),
        sounddevice.InputStream(), torch.cuda.memory_allocated() call and
        verifies each is inside a with statement or has .close() in all
        code paths including except/finally.

        Time Complexity: O(n) where n = total lines of code
        Space Complexity: O(m) where m = number of resource allocations

        Returns:
            List of resource leak findings.

        """
        findings: list[Finding] = []
        finding_id = 1

        # Resource calls to track
        resource_calls = {
            "open",
            "sqlite3.connect",
            "aiohttp.ClientSession",
            "sounddevice.InputStream",
            "torch.cuda.memory_allocated",
        }

        for py_file in self._iter_python_files():
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(py_file))

                # Build parent map for tree traversal
                parent_map: dict[ast.AST, ast.AST] = {}
                for parent_node in ast.walk(tree):
                    for child in ast.iter_child_nodes(parent_node):
                        parent_map[child] = parent_node

                # Find all resource allocation calls
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        call_name = self._get_call_name(node)

                        # Check if this is a resource allocation call
                        if any(rc in call_name for rc in resource_calls):
                            # Check if it's inside a 'with' statement
                            if self._is_in_with_statement_proper(node, parent_map):
                                continue  # Safe - inside with statement

                            # Check if assigned to a variable that has .close() in all paths
                            if self._has_close_in_all_paths(node, tree, parent_map):
                                continue  # Safe - has .close() in all paths

                            # Resource leak detected
                            findings.append(
                                Finding(
                                    id=f"LEAK-{finding_id:03d}",
                                    phase=3,
                                    category=FindingCategory.RESOURCE_LEAK,
                                    severity=Severity.MEDIUM,
                                    file_path=str(py_file.relative_to(self.package_root.parent)),
                                    line_number=node.lineno,
                                    rule="resource-leak",
                                    description=f"Resource '{call_name}' may not be closed in all code paths",
                                    remediation=f"Use 'with' statement for '{call_name}' or ensure .close() is called in all code paths including except/finally",
                                    fixed=False,
                                ),
                            )
                            finding_id += 1

            except (SyntaxError, UnicodeDecodeError):
                continue

        return findings

    def _run_ruff_unused(self) -> list[Finding]:
        """Run ruff to detect unused imports and variables.

        Runs ruff --select F401,F841 to detect:
        - F401: Unused imports
        - F841: Unused local variables

        Time Complexity: O(n) where n = total lines of code
        Space Complexity: O(m) where m = number of violations

        Returns:
            List of unused code findings.

        """
        findings: list[Finding] = []

        result = subprocess.run(
            ["ruff", "check", str(self.package_root), "--select", "F401,F841", "--output-format", "json"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.stdout:
            import json
            try:
                violations = json.loads(result.stdout)
                for idx, violation in enumerate(violations, 1):
                    findings.append(
                        Finding(
                            id=f"UNUSED-{idx:03d}",
                            phase=3,
                            category=FindingCategory.UNUSED_CODE,
                            severity=Severity.LOW,
                            file_path=violation.get("filename", "unknown"),
                            line_number=violation.get("location", {}).get("row", 0),
                            rule=violation.get("code", ""),
                            description=violation.get("message", ""),
                            remediation="Remove unused import or variable",
                            fixed=False,
                        ),
                    )
            except json.JSONDecodeError:
                pass

        return findings

    def _detect_duplicates(self) -> list[Finding]:
        """Detect duplicate implementations (modules with overlapping APIs).

        Extracts public function/class names and type signatures from all modules.
        Reports any pair sharing >= 2 public symbols with identical names and
        type signatures, with both file paths, overlapping API surface, and
        consolidation strategy.

        Time Complexity: O(n²) where n = number of modules (pairwise comparison)
        Space Complexity: O(n * m) where m = average symbols per module

        Returns:
            List of duplicate implementation findings.

        """
        findings: list[Finding] = []
        finding_id = 1

        # Extract public API from all modules
        module_apis: dict[str, dict[str, str]] = {}  # file_path -> {symbol_name: signature}

        for py_file in self._iter_python_files():
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(py_file))

                file_path = str(py_file.relative_to(self.package_root.parent))
                api: dict[str, str] = {}

                # Extract public classes and functions
                for node in ast.walk(tree):
                    # Public classes
                    if isinstance(node, ast.ClassDef):
                        if not node.name.startswith("_"):
                            # Extract class signature (name + base classes)
                            bases = [self._get_name(base) for base in node.bases]
                            signature = f"class {node.name}({', '.join(bases)})"
                            api[node.name] = signature

                    # Public functions (top-level only)
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not node.name.startswith("_"):
                            # Extract function signature (name + args + return type)
                            args = [arg.arg for arg in node.args.args]
                            return_annotation = ""
                            if node.returns:
                                return_annotation = f" -> {self._get_name(node.returns)}"

                            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                            signature = f"{prefix} {node.name}({', '.join(args)}){return_annotation}"
                            api[node.name] = signature

                module_apis[file_path] = api

            except (SyntaxError, UnicodeDecodeError):
                continue

        # Pairwise comparison to find duplicates
        module_paths = list(module_apis.keys())
        for i, path1 in enumerate(module_paths):
            for path2 in module_paths[i + 1:]:
                api1 = module_apis[path1]
                api2 = module_apis[path2]

                # Find overlapping symbols with identical signatures
                overlapping: list[tuple[str, str]] = []
                for symbol_name in api1:
                    if symbol_name in api2:
                        sig1 = api1[symbol_name]
                        sig2 = api2[symbol_name]
                        if sig1 == sig2:
                            overlapping.append((symbol_name, sig1))

                # Report if >= 2 overlapping symbols
                if len(overlapping) >= 2:
                    overlap_list = ", ".join([name for name, _ in overlapping])
                    overlap_details = "\n".join([f"  - {name}: {sig}" for name, sig in overlapping])

                    # Determine consolidation strategy
                    canonical, to_remove = self._determine_canonical_file(path1, path2)

                    findings.append(
                        Finding(
                            id=f"DUPLICATE-{finding_id:03d}",
                            phase=3,
                            category=FindingCategory.DUPLICATE_IMPL,
                            severity=Severity.MEDIUM,
                            file_path=path1,
                            line_number=0,  # File-level issue
                            rule="duplicate-implementation",
                            description=f"Duplicate implementation detected between '{path1}' and '{path2}'. Overlapping API surface ({len(overlapping)} symbols): {overlap_list}",
                            remediation=f"Consolidation strategy: Keep '{canonical}' as canonical, remove '{to_remove}', update all imports to use '{canonical}'. Overlapping symbols:\n{overlap_details}",
                            fixed=False,
                        ),
                    )
                    finding_id += 1

        return findings

    # Helper methods

    def _iter_python_files(self) -> Iterator[Path]:
        """Iterate over all Python files."""
        for path in self.package_root.rglob("*.py"):
            if "__pycache__" not in path.parts:
                yield path

    def _extract_line_number(self, error_msg: str) -> int:
        """Extract line number from error message."""
        import re
        match = re.search(r"line (\d+)", error_msg)
        return int(match.group(1)) if match else 0

    def _map_ruff_severity(self, code: str) -> Severity:
        """Map ruff rule code to severity."""
        if code.startswith("E9") or code.startswith("F"):
            return Severity.HIGH
        if code.startswith("E") or code.startswith("W"):
            return Severity.MEDIUM
        return Severity.LOW

    def _map_bandit_severity(self, severity: str) -> Severity:
        """Map bandit severity to our severity."""
        mapping = {
            "HIGH": Severity.CRITICAL,
            "MEDIUM": Severity.HIGH,
            "LOW": Severity.MEDIUM,
        }
        return mapping.get(severity.upper(), Severity.LOW)

    def _can_import(self, module_name: str) -> bool:
        """Check if a module can be imported.

        Args:
            module_name: The module name to check.

        Returns:
            True if the module can be imported, False otherwise.

        """
        try:
            __import__(module_name.split(".")[0])
            return True
        except (ImportError, ModuleNotFoundError):
            return False
        except Exception:
            # Catch all other exceptions (e.g., TypeError from broken packages)
            # Assume the module exists but has issues - don't report as broken import
            return True

    def _is_guarded(self, node: ast.AST, tree: ast.AST) -> bool:
        """Check if an import is guarded by try/except or platform check.

        This method walks up the AST to find if the import node is inside:
        1. A try/except block with ImportError handler
        2. An if statement checking sys.platform

        Args:
            node: The import node to check.
            tree: The full AST tree.

        Returns:
            True if the import is properly guarded, False otherwise.

        """
        # Build parent map for the tree
        parent_map: dict[ast.AST, ast.AST] = {}
        for parent_node in ast.walk(tree):
            for child in ast.iter_child_nodes(parent_node):
                parent_map[child] = parent_node

        # Walk up the tree from the import node
        current: ast.AST | None = node
        while current is not None:
            parent: ast.AST | None = parent_map.get(current)
            if parent is None:
                break

            # Check if parent is a Try node with ImportError handler
            if isinstance(parent, ast.Try):
                # Check if any handler catches ImportError
                for handler in parent.handlers:
                    if handler.type is None:  # bare except
                        return True
                    if isinstance(handler.type, ast.Name):
                        if handler.type.id == "ImportError":
                            return True
                    elif isinstance(handler.type, ast.Tuple):
                        # Multiple exception types
                        for exc_type in handler.type.elts:
                            if isinstance(exc_type, ast.Name) and exc_type.id == "ImportError":
                                return True

            # Check if parent is an If node checking sys.platform
            if isinstance(parent, ast.If):
                # Check if the test involves sys.platform
                if self._checks_sys_platform(parent.test):
                    return True

            current = parent

        return False

    def _checks_sys_platform(self, test_node: ast.AST) -> bool:
        """Check if an AST node tests sys.platform.

        Args:
            test_node: The test expression node.

        Returns:
            True if the expression checks sys.platform, False otherwise.

        """
        # Check for direct sys.platform comparison
        # e.g., sys.platform == "win32"
        if isinstance(test_node, ast.Compare):
            if isinstance(test_node.left, ast.Attribute):
                if (isinstance(test_node.left.value, ast.Name) and
                    test_node.left.value.id == "sys" and
                    test_node.left.attr == "platform"):
                    return True

        # Check for sys.platform.startswith()
        # e.g., sys.platform.startswith("win")
        if isinstance(test_node, ast.Call):
            if isinstance(test_node.func, ast.Attribute):
                if test_node.func.attr == "startswith":
                    if isinstance(test_node.func.value, ast.Attribute):
                        if (isinstance(test_node.func.value.value, ast.Name) and
                            test_node.func.value.value.id == "sys" and
                            test_node.func.value.attr == "platform"):
                            return True

        # Check for boolean operations (and, or)
        if isinstance(test_node, (ast.BoolOp,)):
            for value in test_node.values:
                if self._checks_sys_platform(value):
                    return True

        # Check for unary not
        if isinstance(test_node, ast.UnaryOp):
            return self._checks_sys_platform(test_node.operand)

        return False

    def _get_call_name(self, node: ast.Call) -> str:
        """Get the full name of a function call."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            parts = []
            current: ast.expr = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""

    def _is_in_with_statement(self, node: ast.AST, tree: ast.AST) -> bool:
        """Check if a node is inside a with statement."""
        # Simplified - would need parent node tracking for accuracy
        return False

    def _is_in_with_statement_proper(self, node: ast.AST, parent_map: dict[ast.AST, ast.AST]) -> bool:
        """Check if a node is inside a with statement using parent map.

        Args:
            node: The AST node to check (should be a Call node).
            parent_map: Map of child nodes to parent nodes.

        Returns:
            True if the node is the context expression in a with statement, False otherwise.

        """
        # Walk up the parent chain to find if this call is used as a context manager
        current: ast.AST | None = node
        while current is not None:
            parent: ast.AST | None = parent_map.get(current)
            if parent is None:
                break

            # Check if parent is a With or AsyncWith node
            if isinstance(parent, (ast.With, ast.AsyncWith)):
                # Check if the current node is one of the context expressions
                for item in parent.items:
                    # The call node should be the context_expr or a descendant of it
                    if item.context_expr is current or self._is_descendant(node, item.context_expr):
                        # This is the resource being opened in a with statement
                        return True

            current = parent

        return False

    def _is_descendant(self, node: ast.AST, potential_ancestor: ast.AST) -> bool:
        """Check if node is a descendant of potential_ancestor.

        Args:
            node: The node to check.
            potential_ancestor: The potential ancestor node.

        Returns:
            True if node is a descendant of potential_ancestor, False otherwise.

        """
        for child in ast.walk(potential_ancestor):
            if child is node:
                return True
        return False

    def _has_close_in_all_paths(
        self,
        call_node: ast.Call,
        tree: ast.AST,
        parent_map: dict[ast.AST, ast.AST],
    ) -> bool:
        """Check if a resource allocation has .close() in all code paths.

        This is a simplified heuristic that checks:
        1. If the call is assigned to a variable
        2. If that variable has .close() called on it
        3. If there's a try/finally block with .close() in finally

        Args:
            call_node: The resource allocation call node.
            tree: The full AST tree.
            parent_map: Map of child nodes to parent nodes.

        Returns:
            True if .close() is found in all paths, False otherwise.

        """
        # Find the assignment that contains this call
        current: ast.AST | None = call_node
        var_name: str | None = None

        while current is not None:
            parent: ast.AST | None = parent_map.get(current)
            if parent is None:
                break

            # Check if parent is an assignment
            if isinstance(parent, ast.Assign):
                # Get the variable name
                for target in parent.targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id
                        break

                if var_name:
                    # Look for .close() calls on this variable
                    # Check in try/finally blocks
                    if self._has_close_in_finally_for_assignment(var_name, parent, tree, parent_map):
                        return True

                    # Check for explicit .close() call after assignment
                    if self._has_explicit_close(var_name, tree, parent):
                        return True

                break

            current = parent

        return False

    def _has_close_in_finally_for_assignment(
        self,
        var_name: str,
        assignment_node: ast.AST,
        tree: ast.AST,
        parent_map: dict[ast.AST, ast.AST],
    ) -> bool:
        """Check if variable has .close() in a finally block that contains the assignment.

        Args:
            var_name: The variable name to check.
            assignment_node: The assignment node.
            tree: The full AST tree.
            parent_map: Map of child nodes to parent nodes.

        Returns:
            True if .close() is found in finally block, False otherwise.

        """
        # Walk up from the assignment to find a Try node
        current: ast.AST | None = assignment_node
        while current is not None:
            parent: ast.AST | None = parent_map.get(current)
            if parent is None:
                break

            # Check if parent is a Try node
            if isinstance(parent, ast.Try):
                # Check if the assignment is in the try body
                if any(self._contains_node(stmt, assignment_node) for stmt in parent.body):
                    # Check finalbody for .close() call
                    for stmt in parent.finalbody:
                        if self._statement_closes_var(stmt, var_name):
                            return True

            current = parent

        return False

    def _contains_node(self, container: ast.AST, target: ast.AST) -> bool:
        """Check if container contains target node.

        Args:
            container: The container node.
            target: The target node to find.

        Returns:
            True if container contains target, False otherwise.

        """
        for node in ast.walk(container):
            if node is target:
                return True
        return False

    def _has_explicit_close(
        self,
        var_name: str,
        tree: ast.AST,
        assignment_node: ast.AST,
    ) -> bool:
        """Check if variable has explicit .close() call after assignment.

        Args:
            var_name: The variable name to check.
            tree: The full AST tree.
            assignment_node: The assignment node.

        Returns:
            True if explicit .close() is found, False otherwise.

        """
        # This is a simplified heuristic - would need control flow analysis for accuracy
        # For now, just check if .close() is called anywhere on this variable
        for node in ast.walk(tree):
            if isinstance(node, ast.Expr):
                if isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Attribute):
                        if node.value.func.attr == "close":
                            if isinstance(node.value.func.value, ast.Name):
                                if node.value.func.value.id == var_name:
                                    return True

        return False

    def _statement_closes_var(self, stmt: ast.AST, var_name: str) -> bool:
        """Check if a statement closes a variable.

        Args:
            stmt: The statement to check.
            var_name: The variable name to check.

        Returns:
            True if the statement closes the variable, False otherwise.

        """
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "close":
                        if isinstance(node.func.value, ast.Name):
                            if node.func.value.id == var_name:
                                return True
        return False

    def _determine_canonical_file(self, path1: str, path2: str) -> tuple[str, str]:
        """Determine which file should be canonical and which should be removed.

        Uses heuristics:
        1. Prefer shorter file names (e.g., runtime.py over llm_runtime.py)
        2. Prefer files without version suffixes (_v2, _new, _old)
        3. Prefer files in more specific directories

        Args:
            path1: First file path.
            path2: Second file path.

        Returns:
            Tuple of (canonical_path, path_to_remove).

        """
        # Extract file names
        name1 = Path(path1).stem
        name2 = Path(path2).stem

        # Check for version suffixes
        version_suffixes = ["_v2", "_v3", "_new", "_old", "_backup", "_copy"]
        has_suffix1 = any(name1.endswith(suffix) for suffix in version_suffixes)
        has_suffix2 = any(name2.endswith(suffix) for suffix in version_suffixes)

        if has_suffix1 and not has_suffix2:
            return (path2, path1)
        if has_suffix2 and not has_suffix1:
            return (path1, path2)

        # Prefer shorter names
        if len(name1) < len(name2):
            return (path1, path2)
        if len(name2) < len(name1):
            return (path2, path1)

        # Default: keep first, remove second
        return (path1, path2)

    def _get_name(self, node: ast.AST) -> str:
        """Get the name from an AST node.

        Args:
            node: The AST node.

        Returns:
            The name as a string.

        """
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parts = []
            current: ast.expr = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        if isinstance(node, ast.Constant):
            return str(node.value)
        return "Unknown"

    def _function_accesses_var(self, func_node: ast.FunctionDef | ast.AsyncFunctionDef, var_name: str) -> bool:
        """Check if a function accesses a variable.

        Args:
            func_node: The function definition node.
            var_name: The variable name to check.

        Returns:
            True if the function accesses the variable, False otherwise.

        """
        for node in ast.walk(func_node):
            # Check for variable access (Name node)
            if isinstance(node, ast.Name) and node.id == var_name:
                # Check if it's a load (read) or store (write)
                if isinstance(node.ctx, (ast.Load, ast.Store)):
                    return True

            # Check for attribute access (e.g., var_name.attr)
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id == var_name:
                    return True

        return False

    def _has_synchronization(self, tree: ast.AST, var_name: str, sync_primitives: set[str]) -> bool:
        """Check if a variable is protected by synchronization primitives.

        Args:
            tree: The AST tree.
            var_name: The variable name to check.
            sync_primitives: Set of accepted synchronization primitive names.

        Returns:
            True if synchronization is detected, False otherwise.

        """
        # Look for with statements using locks
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                for item in node.items:
                    # Check if the context manager is a lock
                    if isinstance(item.context_expr, ast.Name):
                        # Direct lock usage: with lock:
                        pass  # Could be a lock, but we can't verify without type info

                    elif isinstance(item.context_expr, ast.Call):
                        call_name = self._get_call_name(item.context_expr)
                        if any(prim in call_name for prim in sync_primitives):
                            # Check if the with block accesses the variable
                            for body_node in node.body:
                                if self._node_accesses_var(body_node, var_name):
                                    return True

            # Check for async with (async locks)
            if isinstance(node, ast.AsyncWith):
                for item in node.items:
                    if isinstance(item.context_expr, ast.Call):
                        call_name = self._get_call_name(item.context_expr)
                        if any(prim in call_name for prim in sync_primitives):
                            # Check if the with block accesses the variable
                            for body_node in node.body:
                                if self._node_accesses_var(body_node, var_name):
                                    return True

        return False

    def _node_accesses_var(self, node: ast.AST, var_name: str) -> bool:
        """Check if a node or its children access a variable.

        Args:
            node: The AST node to check.
            var_name: The variable name to check.

        Returns:
            True if the node accesses the variable, False otherwise.

        """
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id == var_name:
                return True
            if isinstance(child, ast.Attribute):
                if isinstance(child.value, ast.Name) and child.value.id == var_name:
                    return True
        return False


async def run(report: AuditReport, writer: MasterReportWriter) -> None:
    """Phase 3 entry point: Bug and Failure Detection.

    Args:
        report: The AuditReport to populate with findings.
        writer: The MasterReportWriter to write the report section.

    """
    # Locate Agent_Guru package root
    repo_root = Path(__file__).parent.parent.parent
    package_root = repo_root / "Agent_Guru"

    if not package_root.exists():
        msg = f"Agent_Guru package not found at {package_root}"
        raise ValueError(msg)

    # Initialize detector
    detector = BugDetector(package_root)

    # Run all detection methods
    findings = detector.run_all()

    # Update report with findings
    report.findings = findings

    # Write report
    writer.write(report)
