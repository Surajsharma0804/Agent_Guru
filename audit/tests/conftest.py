"""Pytest configuration and shared fixtures for the audit test suite.

This module registers Hypothesis profiles and provides shared pytest fixtures
used across all property-based and unit tests in the ``audit/tests/`` package.

The CI profile is activated immediately at import time so every test run —
including local developer runs — uses the same deterministic, reproducible
settings as CI.

Hypothesis profiles:

    ci:
        max_examples=100        — 100 examples per property (quality.md: ≥100)
        derandomize=True        — fixed seed derived from test name for
                                  reproducibility across runs
        suppress_health_check=[HealthCheck.too_slow]
                                — suppress the "too slow" health check so that
                                  property tests involving I/O or subprocess
                                  calls are not aborted prematurely

    dev:
        max_examples=10         — only 10 examples for fast local iteration
        derandomize=False       — random seed so each run explores new space

Subsystem: audit
Primary public API: repo_root, sample_audit_report (pytest fixtures)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings

from audit.models import (
    AuditReport,
    Finding,
    FindingCategory,
    IntegrationCheckResult,
    ModuleInventory,
    PerformanceMetric,
    Severity,
)

# ---------------------------------------------------------------------------
# Hypothesis profiles
# ---------------------------------------------------------------------------

settings.register_profile(
    "ci",
    max_examples=100,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)

settings.register_profile(
    "dev",
    max_examples=10,
    derandomize=False,
)

# Activate the CI profile for this session.  All tests in audit/tests/ will
# use these settings unless a test explicitly overrides them with
# @settings(profile="dev") or a direct @settings(...) decorator.
settings.load_profile("ci")

# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the absolute path to the repository root.

    The repository root is the parent of the ``audit/`` package directory.
    This fixture is session-scoped because the path never changes within a
    test session.

    Returns:
        Absolute Path to the repository root (parent of ``audit/``).

    Example::

        def test_audit_package_exists(repo_root: Path) -> None:
            assert (repo_root / "audit" / "__init__.py").exists()
    """
    # conftest.py lives at audit/tests/conftest.py
    # audit/tests/ -> audit/ -> repo root
    return Path(__file__).parent.parent.parent.resolve()


@pytest.fixture
def sample_audit_report() -> AuditReport:
    """Return a minimal but structurally complete AuditReport for testing.

    The report contains exactly:
        - 2 findings (one CRITICAL compile error, one HIGH type error)
        - 2 inventory entries (two distinct Python modules)
        - 1 performance metric (wake word P95 latency)
        - 1 integration check result (pipeline startup check)

    This fixture is function-scoped (default) so each test receives a fresh
    instance with no shared mutable state.

    Returns:
        A populated AuditReport suitable for exercising the report writer
        and any code that consumes AuditReport objects.

    Example::

        def test_report_has_findings(sample_audit_report: AuditReport) -> None:
            assert len(sample_audit_report.findings) == 2
    """
    findings = [
        Finding(
            id="BUG-001",
            phase=3,
            category=FindingCategory.COMPILE_ERROR,
            severity=Severity.CRITICAL,
            file_path="Agent_Guru/core/agent_guru.py",
            line_number=42,
            rule="E999",
            description="SyntaxError: invalid syntax",
            remediation="Fix missing closing parenthesis on line 42.",
            fixed=False,
        ),
        Finding(
            id="BUG-002",
            phase=3,
            category=FindingCategory.TYPE_ERROR,
            severity=Severity.HIGH,
            file_path="Agent_Guru/llm/runtime.py",
            line_number=117,
            rule="mypy:error",
            description='Argument 1 to "generate" has incompatible type "None"; expected "str"',
            remediation="Add None guard before calling generate().",
            fixed=True,
        ),
    ]

    inventory = [
        ModuleInventory(
            file_path="Agent_Guru/core/agent_guru.py",
            line_count=320,
            public_class_count=2,
            public_function_count=5,
            import_count=14,
            imports=["asyncio", "pathlib", "Agent_Guru.core.retry"],
        ),
        ModuleInventory(
            file_path="Agent_Guru/llm/runtime.py",
            line_count=480,
            public_class_count=3,
            public_function_count=8,
            import_count=21,
            imports=["asyncio", "openai", "anthropic", "Agent_Guru.llm.router"],
        ),
    ]

    performance_metrics = [
        PerformanceMetric(
            metric_name="Wake Word P95 Latency",
            unit="ms",
            before_p95=350.0,
            after_p95=145.0,
            target=200.0,
            meets_target=True,
        ),
    ]

    integration_results = [
        IntegrationCheckResult(
            check_id=1,
            description="IntegrationOrchestrator.startup() completes without exception",
            passed=True,
            details="All 11 subsystems initialized in 8.3 s on NVIDIA RTX 3080.",
        ),
    ]

    return AuditReport(
        findings=findings,
        inventory=inventory,
        performance_metrics=performance_metrics,
        integration_results=integration_results,
    )
