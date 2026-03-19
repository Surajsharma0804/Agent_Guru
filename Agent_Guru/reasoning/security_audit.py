"""
Security Audit Script for Core Reasoning Engine.

Documents the security checks to run for production readiness (Task 28.1).
Implements static analysis checks that can be run programmatically.

Security Checks:
    1. SAST (Static Analysis) - Bandit
    2. Dependency Scanning - Safety
    3. Container Scanning - Trivy
    4. Penetration Testing guidelines
    5. Code-level security property validation

Usage:
    python security_audit.py [--report-file REPORT_FILE]

Requirements: 31.1
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(str, Enum):
    """Issue severity levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class SecurityIssue:
    """Represents a security issue found during audit."""

    severity: Severity
    category: str
    description: str
    file_path: str = ""
    line_number: int = 0
    recommendation: str = ""


@dataclass
class AuditResult:
    """Result of a security audit check."""

    check_name: str
    passed: bool
    issues: list[SecurityIssue] = field(default_factory=list)
    details: str = ""

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.HIGH)


# ---------------------------------------------------------------------------
# Patterns for static code analysis
# ---------------------------------------------------------------------------

# Secrets / hardcoded credentials
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("api_key_assignment", re.compile(r'(?i)(api_key|apikey)\s*=\s*["\'][A-Za-z0-9_\-]{16,}["\']')),
    ("secret_assignment", re.compile(r'(?i)(secret|password|passwd|token)\s*=\s*["\'][^"\']{8,}["\']')),
    ("aws_access_key", re.compile(r'AKIA[0-9A-Z]{16}')),
    ("private_key_header", re.compile(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----')),
]

# Dangerous function calls - match standalone eval/exec, not method calls like model.eval()
_DANGEROUS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("eval_call", re.compile(r'(?<!\.)(?<!\w)\beval\s*\(')),
    ("exec_call", re.compile(r'(?<!\.)(?<!\w)\bexec\s*\(')),
    ("pickle_loads", re.compile(r'\bpickle\.loads?\s*\(')),
    ("yaml_load_unsafe", re.compile(r'\byaml\.load\s*\([^,)]+\)')),  # without Loader=
    ("subprocess_shell_true", re.compile(r'subprocess\.[a-z_]+\s*\([^)]*shell\s*=\s*True')),
    ("os_system", re.compile(r'\bos\.system\s*\(')),
]

# Bare except patterns
_BARE_EXCEPT_PATTERN = re.compile(r'^\s*except\s*:\s*$', re.MULTILINE)

# Input validation markers (presence check)
_VALIDATION_MARKERS = [
    "validate_",
    "validator",
    "field_validator",
    "model_validator",
    "raise ValueError",
    "raise TypeError",
]


def _python_source_files(root: Path) -> list[Path]:
    """Return all .py files under root, excluding __pycache__ and test dirs."""
    return [
        p
        for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
        and ".hypothesis" not in p.parts
        and "tests" not in p.parts
    ]


def _get_docstring_line_ranges(content: str) -> list[tuple[int, int]]:
    """Return (start_line, end_line) ranges that are inside docstrings."""
    ranges: list[tuple[int, int]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return ranges

    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if body and isinstance(body, list) and body:
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                start = first.lineno
                end = first.end_lineno or first.lineno
                ranges.append((start, end))
    return ranges


def check_no_hardcoded_secrets(root: Path) -> AuditResult:
    """Scan source files for hardcoded API keys and secrets."""
    issues: list[SecurityIssue] = []

    for py_file in _python_source_files(root):
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        docstring_ranges = _get_docstring_line_ranges(content)

        def _in_docstring(line_no: int, ranges: list[tuple[int, int]] = docstring_ranges) -> bool:
            return any(start <= line_no <= end for start, end in ranges)

        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#") or "test" in py_file.name.lower():
                continue
            if _in_docstring(line_no):
                continue

            for pattern_name, pattern in _SECRET_PATTERNS:
                if pattern.search(line):
                    issues.append(
                        SecurityIssue(
                            severity=Severity.CRITICAL,
                            category="hardcoded_secret",
                            description=f"Potential hardcoded secret ({pattern_name})",
                            file_path=str(py_file.relative_to(root)),
                            line_number=line_no,
                            recommendation="Use environment variables or OS keychain for secrets.",
                        )
                    )

    return AuditResult(
        check_name="no_hardcoded_secrets",
        passed=len(issues) == 0,
        issues=issues,
        details=f"Scanned {len(_python_source_files(root))} source files.",
    )


def check_no_dangerous_functions(root: Path) -> AuditResult:
    """Detect use of dangerous functions like eval/exec on user input."""
    issues: list[SecurityIssue] = []

    for py_file in _python_source_files(root):
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            for pattern_name, pattern in _DANGEROUS_PATTERNS:
                if pattern.search(line):
                    issues.append(
                        SecurityIssue(
                            severity=Severity.HIGH,
                            category="dangerous_function",
                            description=f"Dangerous function usage: {pattern_name}",
                            file_path=str(py_file.relative_to(root)),
                            line_number=line_no,
                            recommendation=(
                                "Avoid eval/exec on user input. "
                                "Use ast.literal_eval for safe evaluation. "
                                "Use subprocess with shell=False."
                            ),
                        )
                    )

    return AuditResult(
        check_name="no_dangerous_functions",
        passed=len(issues) == 0,
        issues=issues,
    )


def check_input_validation_present(root: Path) -> AuditResult:
    """Verify that key modules contain input validation logic."""
    key_modules = [
        root / "input" / "normalizer.py",
        root / "safety" / "gate.py",
        root / "models" / "intent.py",
        root / "models" / "action.py",
    ]

    issues: list[SecurityIssue] = []

    for module_path in key_modules:
        if not module_path.exists():
            issues.append(
                SecurityIssue(
                    severity=Severity.HIGH,
                    category="missing_validation",
                    description=f"Key module not found: {module_path.name}",
                    file_path=str(module_path),
                    recommendation="Ensure all key modules exist with input validation.",
                )
            )
            continue

        content = module_path.read_text(encoding="utf-8", errors="ignore")
        has_validation = any(marker in content for marker in _VALIDATION_MARKERS)

        if not has_validation:
            issues.append(
                SecurityIssue(
                    severity=Severity.MEDIUM,
                    category="missing_validation",
                    description=f"No input validation found in {module_path.name}",
                    file_path=str(module_path.relative_to(root)),
                    recommendation="Add Pydantic validators or explicit validation logic.",
                )
            )

    return AuditResult(
        check_name="input_validation_present",
        passed=len(issues) == 0,
        issues=issues,
        details=f"Checked {len(key_modules)} key modules for validation.",
    )


def check_no_bare_excepts(root: Path) -> AuditResult:
    """Detect bare except clauses that silently swallow errors."""
    issues: list[SecurityIssue] = []

    for py_file in _python_source_files(root):
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for match in _BARE_EXCEPT_PATTERN.finditer(content):
            line_no = content[: match.start()].count("\n") + 1
            issues.append(
                SecurityIssue(
                    severity=Severity.MEDIUM,
                    category="bare_except",
                    description="Bare except clause silently swallows all exceptions",
                    file_path=str(py_file.relative_to(root)),
                    line_number=line_no,
                    recommendation="Use specific exception types: except ValueError as e:",
                )
            )

    return AuditResult(
        check_name="no_bare_excepts",
        passed=len(issues) == 0,
        issues=issues,
    )


def check_security_imports_correct(root: Path) -> AuditResult:
    """Verify security-relevant imports are used correctly."""
    issues: list[SecurityIssue] = []

    for py_file in _python_source_files(root):
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content, filename=str(py_file))
        except (OSError, SyntaxError):
            continue

        for node in ast.walk(tree):
            # Detect yaml.load without Loader argument (unsafe)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "load"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "yaml"
            ):
                has_loader = any(
                    (isinstance(kw.value, ast.Attribute) and kw.value.attr in ("SafeLoader", "FullLoader"))
                    or (isinstance(kw.value, ast.Name) and kw.value.id in ("SafeLoader", "FullLoader"))
                    for kw in node.keywords
                    if kw.arg == "Loader"
                )
                if not has_loader:
                    issues.append(
                        SecurityIssue(
                            severity=Severity.HIGH,
                            category="unsafe_yaml_load",
                            description="yaml.load() called without safe Loader",
                            file_path=str(py_file.relative_to(root)),
                            line_number=node.lineno,
                            recommendation="Use yaml.safe_load() or yaml.load(data, Loader=yaml.SafeLoader).",
                        )
                    )

    return AuditResult(
        check_name="security_imports_correct",
        passed=len(issues) == 0,
        issues=issues,
    )


def run_bandit(root: Path) -> AuditResult:
    """Run Bandit SAST tool if available."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "bandit", "-r", str(root), "-f", "json", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        passed = result.returncode == 0
        return AuditResult(
            check_name="bandit_sast",
            passed=passed,
            details=result.stdout[:2000] if result.stdout else result.stderr[:2000],
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return AuditResult(
            check_name="bandit_sast",
            passed=False,
            details=f"Bandit not available or timed out: {exc}. Install with: pip install bandit",
        )


def run_safety(root: Path) -> AuditResult:
    """Run Safety dependency scanner if available."""
    requirements_file = root.parent.parent / "requirements.txt"
    try:
        cmd = [sys.executable, "-m", "safety", "check", "--json"]
        if requirements_file.exists():
            cmd += ["-r", str(requirements_file)]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        passed = result.returncode == 0
        return AuditResult(
            check_name="safety_dependency_scan",
            passed=passed,
            details=result.stdout[:2000] if result.stdout else result.stderr[:2000],
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return AuditResult(
            check_name="safety_dependency_scan",
            passed=False,
            details=f"Safety not available or timed out: {exc}. Install with: pip install safety",
        )


def run_full_audit(root: Path | None = None) -> dict[str, AuditResult]:
    """Run all static security checks and return results."""
    if root is None:
        root = Path(__file__).parent

    checks = {
        "no_hardcoded_secrets": check_no_hardcoded_secrets(root),
        "no_dangerous_functions": check_no_dangerous_functions(root),
        "input_validation_present": check_input_validation_present(root),
        "no_bare_excepts": check_no_bare_excepts(root),
        "security_imports_correct": check_security_imports_correct(root),
    }
    return checks


def print_report(results: dict[str, AuditResult]) -> None:
    """Print a human-readable audit report."""
    print("\n" + "=" * 60)
    print("SECURITY AUDIT REPORT - Core Reasoning Engine")
    print("=" * 60)

    total_issues = 0
    critical_issues = 0
    high_issues = 0

    for check_name, result in results.items():
        status = "PASS" if result.passed else "FAIL"
        print(f"\n[{status}] {check_name}")
        if result.details:
            print(f"  Details: {result.details}")
        for issue in result.issues:
            print(f"  [{issue.severity.value}] {issue.description}")
            if issue.file_path:
                print(f"    File: {issue.file_path}:{issue.line_number}")
            if issue.recommendation:
                print(f"    Fix: {issue.recommendation}")
            total_issues += 1
            if issue.severity == Severity.CRITICAL:
                critical_issues += 1
            elif issue.severity == Severity.HIGH:
                high_issues += 1

    print("\n" + "=" * 60)
    print(f"Total issues: {total_issues}")
    print(f"Critical: {critical_issues}  High: {high_issues}")
    all_passed = all(r.passed for r in results.values())
    print(f"Overall: {'PASS' if all_passed else 'FAIL'}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Security audit for Core Reasoning Engine")
    parser.add_argument("--root", default=None, help="Root directory to scan")
    args = parser.parse_args()

    scan_root = Path(args.root) if args.root else Path(__file__).parent
    results = run_full_audit(scan_root)
    print_report(results)

    # Exit with non-zero if critical/high issues found
    has_critical_or_high = any(
        r.critical_count > 0 or r.high_count > 0 for r in results.values()
    )
    sys.exit(1 if has_critical_or_high else 0)
