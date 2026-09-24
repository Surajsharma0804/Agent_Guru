"""Property-based tests for Phase 9: Report generation.

Task 13.6 - Property 20.

Property 20: Report Section Completeness
    For any AuditReport object passed to MasterReportWriter.write(),
    the resulting AUDIT_REPORT_MASTER.md contains exactly 9 top-level
    sections with the exact headings in the specified order.

Subsystem: audit/tests
Requirements: 9.1, 9.2
"""

from __future__ import annotations

import re
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from audit.models import (
    AuditReport,
    Finding,
    FindingCategory,
    IntegrationCheckResult,
    ModuleInventory,
    PerformanceMetric,
    RemediationItem,
    Severity,
)
from audit.report import MasterReportWriter


# ---------------------------------------------------------------------------
# Required section headings in the mandated order (Requirement 9.1)
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = [
    "Repository Intelligence",
    "Competitive Analysis",
    "Bug and Failure Report",
    "Performance Optimization",
    "Architectural Cleanup",
    "Integration Validation",
    "Code Quality",
    "Deployment Readiness",
    "Executive Summary",
]


def _extract_h2_headings(content: str) -> list[str]:
    """Return ## heading titles in document order."""
    return [
        m.group(1).strip()
        for m in re.finditer(r"^##\s+(.+)$", content, re.MULTILINE)
    ]


# ---------------------------------------------------------------------------
# Hypothesis strategies for AuditReport components
# ---------------------------------------------------------------------------

_severity_strategy = st.sampled_from(list(Severity))
_category_strategy = st.sampled_from(list(FindingCategory))

_finding_strategy = st.builds(
    Finding,
    id=st.text(min_size=1, max_size=20, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-"),
    phase=st.integers(min_value=1, max_value=9),
    category=_category_strategy,
    severity=_severity_strategy,
    file_path=st.just("Agent_Guru/core/module.py"),
    line_number=st.integers(min_value=1, max_value=9999),
    rule=st.text(min_size=1, max_size=20),
    description=st.text(min_size=1, max_size=200),
    remediation=st.text(min_size=0, max_size=200),
    fixed=st.booleans(),
)

_inventory_strategy = st.builds(
    ModuleInventory,
    file_path=st.just("Agent_Guru/core/module.py"),
    line_count=st.integers(min_value=1, max_value=5000),
    public_class_count=st.integers(min_value=0, max_value=50),
    public_function_count=st.integers(min_value=0, max_value=100),
    import_count=st.integers(min_value=0, max_value=100),
)

_metric_strategy = st.builds(
    PerformanceMetric,
    metric_name=st.text(min_size=1, max_size=50),
    unit=st.sampled_from(["ms", "MB", "%", "s"]),
    before_p95=st.floats(min_value=0.0, max_value=10_000.0, allow_nan=False),
    after_p95=st.floats(min_value=0.0, max_value=10_000.0, allow_nan=False),
    target=st.floats(min_value=0.001, max_value=10_000.0, allow_nan=False),
    meets_target=st.booleans(),
)

_integration_strategy = st.builds(
    IntegrationCheckResult,
    check_id=st.integers(min_value=1, max_value=12),
    description=st.text(min_size=1, max_size=100),
    passed=st.booleans(),
    details=st.text(min_size=0, max_size=200),
)

_remediation_strategy = st.builds(
    RemediationItem,
    id=st.text(min_size=1, max_size=20, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"),
    phase=st.integers(min_value=1, max_value=9),
    severity=_severity_strategy,
    affected_module=st.just("Agent_Guru/llm/runtime.py"),
    description=st.text(min_size=1, max_size=200),
    expected_improvement=st.text(min_size=1, max_size=100),
    estimated_effort_hours=st.floats(min_value=0.0, max_value=200.0, allow_nan=False),
    competitive_impact_score=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False),
)


# ===========================================================================
# Property 20: Report Section Completeness
# ===========================================================================


class TestReportSectionCompletenessProperty20:
    """Property 20 - write() always produces exactly 9 ## sections in order."""

    # ── Core property ──────────────────────────────────────────────────────

    @given(
        findings=st.lists(_finding_strategy, min_size=0, max_size=5),
        inventory=st.lists(_inventory_strategy, min_size=0, max_size=3),
        metrics=st.lists(_metric_strategy, min_size=0, max_size=3),
        integration=st.lists(_integration_strategy, min_size=0, max_size=3),
        remediation=st.lists(_remediation_strategy, min_size=0, max_size=3),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[__import__("hypothesis").HealthCheck.function_scoped_fixture],
    )
    def test_property_20_always_nine_sections(
        self,
        findings: list[Finding],
        inventory: list[ModuleInventory],
        metrics: list[PerformanceMetric],
        integration: list[IntegrationCheckResult],
        remediation: list[RemediationItem],
    ) -> None:
        """Property 20: any AuditReport → exactly 9 ## sections in order."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            report = AuditReport(
                findings=findings,
                inventory=inventory,
                performance_metrics=metrics,
                integration_results=integration,
                remediation_backlog=remediation,
            )
            path = Path(tmpdir) / "report.md"
            writer = MasterReportWriter(report_path=path)
            writer.write(report)

            content = path.read_text(encoding="utf-8")
            headings = _extract_h2_headings(content)

            assert headings == REQUIRED_SECTIONS, (
                f"Expected {REQUIRED_SECTIONS}, got {headings}"
            )

    # ── Deterministic edge cases ───────────────────────────────────────────

    def test_empty_report_nine_sections(self, tmp_path: Path) -> None:
        path = tmp_path / "r.md"
        writer = MasterReportWriter(report_path=path)
        writer.write(AuditReport())
        headings = _extract_h2_headings(path.read_text(encoding="utf-8"))
        assert headings == REQUIRED_SECTIONS

    def test_sections_not_reordered_after_multiple_writes(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "r.md"
        writer = MasterReportWriter(report_path=path)
        report = AuditReport()
        for _ in range(3):
            writer.write(report)
            headings = _extract_h2_headings(path.read_text(encoding="utf-8"))
            assert headings == REQUIRED_SECTIONS

    def test_no_extra_top_level_sections(self, tmp_path: Path) -> None:
        path = tmp_path / "r.md"
        writer = MasterReportWriter(report_path=path)
        writer.write(AuditReport())
        headings = _extract_h2_headings(path.read_text(encoding="utf-8"))
        assert len(headings) == len(REQUIRED_SECTIONS)  # noqa: PLR2004

    def test_sections_present_with_phase_errors(self, tmp_path: Path) -> None:
        path = tmp_path / "r.md"
        writer = MasterReportWriter(report_path=path)
        writer.add_phase_error("Phase 3", RuntimeError("bandit crashed"))
        writer.add_phase_error("Phase 7", TimeoutError("mypy timeout"))
        writer.write(AuditReport())
        headings = _extract_h2_headings(path.read_text(encoding="utf-8"))
        assert headings == REQUIRED_SECTIONS

    def test_repository_intelligence_is_first(self, tmp_path: Path) -> None:
        path = tmp_path / "r.md"
        writer = MasterReportWriter(report_path=path)
        writer.write(AuditReport())
        headings = _extract_h2_headings(path.read_text(encoding="utf-8"))
        assert headings[0] == "Repository Intelligence"

    def test_executive_summary_is_last(self, tmp_path: Path) -> None:
        path = tmp_path / "r.md"
        writer = MasterReportWriter(report_path=path)
        writer.write(AuditReport())
        headings = _extract_h2_headings(path.read_text(encoding="utf-8"))
        assert headings[-1] == "Executive Summary"

    def test_report_starts_with_h1_title(self, tmp_path: Path) -> None:
        path = tmp_path / "r.md"
        writer = MasterReportWriter(report_path=path)
        writer.write(AuditReport())
        content = path.read_text(encoding="utf-8")
        assert content.startswith("# Agent Guru")

    def test_no_unclosed_code_blocks(self, tmp_path: Path) -> None:
        """Every ``` must be matched - no unclosed code fences."""
        path = tmp_path / "r.md"
        writer = MasterReportWriter(report_path=path)
        writer.write(AuditReport())
        content = path.read_text(encoding="utf-8")
        fence_count = content.count("```")
        assert fence_count % 2 == 0, (
            f"Odd number of code fences ({fence_count}) - unclosed block"
        )

    def test_section_content_not_empty(self, tmp_path: Path) -> None:
        """Each section must have at least one non-heading line."""
        path = tmp_path / "r.md"
        writer = MasterReportWriter(report_path=path)
        writer.write(AuditReport())
        content = path.read_text(encoding="utf-8")

        # Split by ## headings and check each section body
        parts = re.split(r"^## .+$", content, flags=re.MULTILINE)
        # parts[0] = header/intro, parts[1:] = section bodies
        for i, body in enumerate(parts[1:], start=1):
            stripped = body.strip()
            assert len(stripped) > 0, (
                f"Section {i} ({REQUIRED_SECTIONS[i-1]}) has empty body"
            )


# ---------------------------------------------------------------------------
# No check on a committed AUDIT_REPORT_MASTER.md
# ---------------------------------------------------------------------------
# The report is output: MasterReportWriter writes it whenever audit/runner.py
# runs. A test that required a copy at the repository root asserted the state
# of a checkout, not the behaviour of the writer. It failed from the moment
# commit 450e42c5 deleted the stale file. Its sibling section check could
# never fail at all: the deleted file was hand-written with 15 sections, not
# the writer's 9, so the check returned early on the mismatch, and it would
# accept any file with that name. Property 20 is proved above against the
# writer's real output in tmp_path, which is the only report whose sections
# this suite can vouch for.
#
# What the removed check was reaching for, Requirement 9.1's "at the
# repository root", is a property of the writer and is asserted on it
# directly, without needing a report to exist in the checkout.


class TestDefaultReportLocation:
    """The audit runner's writer targets AUDIT_REPORT_MASTER.md at the repo root."""

    def test_default_report_path_is_repository_root(self, repo_root: Path) -> None:
        writer = MasterReportWriter()
        assert writer.report_path.resolve() == (repo_root / "AUDIT_REPORT_MASTER.md").resolve()
