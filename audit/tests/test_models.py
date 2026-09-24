"""Unit tests for audit/models.py - task 1.6.

Verifies that every dataclass can be instantiated with valid arguments
and that both enums have exactly the expected members.

Subsystem: audit/tests
Requirements: 9.1
"""

from __future__ import annotations

import pytest

from audit.models import (
    AuditReport,
    DependencyEdge,
    Finding,
    FindingCategory,
    IntegrationCheckResult,
    ModuleInventory,
    PerformanceMetric,
    RemediationItem,
    Severity,
)


# ---------------------------------------------------------------------------
# Severity enum
# ---------------------------------------------------------------------------


class TestSeverity:
    """Severity enum correctness."""

    def test_has_critical(self) -> None:
        assert Severity.CRITICAL == "CRITICAL"

    def test_has_high(self) -> None:
        assert Severity.HIGH == "HIGH"

    def test_has_medium(self) -> None:
        assert Severity.MEDIUM == "MEDIUM"

    def test_has_low(self) -> None:
        assert Severity.LOW == "LOW"

    def test_has_info(self) -> None:
        assert Severity.INFO == "INFO"

    def test_exact_member_count(self) -> None:
        assert len(Severity) == 5  # noqa: PLR2004

    def test_is_str_subclass(self) -> None:
        assert isinstance(Severity.CRITICAL, str)


# ---------------------------------------------------------------------------
# FindingCategory enum
# ---------------------------------------------------------------------------


class TestFindingCategory:
    """FindingCategory enum correctness."""

    EXPECTED_MEMBERS = {
        "COMPILE_ERROR", "TYPE_ERROR", "LINT_VIOLATION", "SECURITY_ISSUE",
        "CIRCULAR_IMPORT", "BROKEN_IMPORT", "ASYNC_ANTIPATTERN", "RACE_CONDITION",
        "RESOURCE_LEAK", "UNUSED_CODE", "DUPLICATE_IMPL", "PLATFORM_GUARD",
        "PERFORMANCE", "DEAD_CODE", "MISSING_DOCSTRING", "LAYER_VIOLATION",
        "HARDCODED_SECRET",
    }

    def test_all_expected_members_present(self) -> None:
        actual = {m.name for m in FindingCategory}
        assert actual == self.EXPECTED_MEMBERS

    def test_exact_member_count(self) -> None:
        assert len(FindingCategory) == len(self.EXPECTED_MEMBERS)

    def test_is_str_subclass(self) -> None:
        assert isinstance(FindingCategory.COMPILE_ERROR, str)

    def test_value_equals_name(self) -> None:
        for member in FindingCategory:
            assert member.value == member.name


# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------


class TestFinding:
    """Finding dataclass instantiation and field access."""

    def _make(self, **overrides: object) -> Finding:
        defaults: dict[str, object] = {
            "id": "BUG-001",
            "phase": 3,
            "category": FindingCategory.COMPILE_ERROR,
            "severity": Severity.CRITICAL,
            "file_path": "Agent_Guru/core/agent_guru.py",
            "line_number": 42,
            "rule": "E999",
            "description": "SyntaxError: invalid syntax",
        }
        defaults.update(overrides)
        return Finding(**defaults)  # type: ignore[arg-type]

    def test_minimal_instantiation(self) -> None:
        f = self._make()
        assert f.id == "BUG-001"
        assert f.phase == 3
        assert f.fixed is False        # default
        assert f.remediation == ""     # default

    def test_with_remediation_and_fixed(self) -> None:
        f = self._make(remediation="Add type guard", fixed=True)
        assert f.remediation == "Add type guard"
        assert f.fixed is True

    def test_phase_zero_is_valid(self) -> None:
        f = self._make(phase=0)
        assert f.phase == 0

    def test_line_number_zero_is_valid(self) -> None:
        f = self._make(line_number=0)
        assert f.line_number == 0

    def test_all_categories_accepted(self) -> None:
        for cat in FindingCategory:
            f = self._make(category=cat)
            assert f.category is cat

    def test_all_severities_accepted(self) -> None:
        for sev in Severity:
            f = self._make(severity=sev)
            assert f.severity is sev


# ---------------------------------------------------------------------------
# ModuleInventory dataclass
# ---------------------------------------------------------------------------


class TestModuleInventory:
    """ModuleInventory dataclass instantiation and field access."""

    def _make(self, **overrides: object) -> ModuleInventory:
        defaults: dict[str, object] = {
            "file_path": "Agent_Guru/speech/wake_word.py",
            "line_count": 250,
            "public_class_count": 2,
            "public_function_count": 5,
            "import_count": 8,
        }
        defaults.update(overrides)
        return ModuleInventory(**defaults)  # type: ignore[arg-type]

    def test_defaults_give_empty_imports_list(self) -> None:
        inv = self._make()
        assert inv.imports == []

    def test_imports_list_not_shared(self) -> None:
        a = self._make()
        b = self._make()
        a.imports.append("numpy")
        assert b.imports == [], "default_factory must produce independent lists"

    def test_explicit_imports(self) -> None:
        inv = self._make(imports=["asyncio", "numpy"])
        assert "numpy" in inv.imports

    def test_zero_counts_are_valid(self) -> None:
        inv = self._make(line_count=0, public_class_count=0,
                         public_function_count=0, import_count=0)
        assert inv.line_count == 0


# ---------------------------------------------------------------------------
# DependencyEdge dataclass
# ---------------------------------------------------------------------------


class TestDependencyEdge:
    """DependencyEdge dataclass instantiation."""

    def test_minimal(self) -> None:
        edge = DependencyEdge(
            source="Agent_Guru/a.py",
            target="Agent_Guru/b.py",
            import_type="import",
        )
        assert edge.symbol == ""  # default

    def test_from_import_with_symbol(self) -> None:
        edge = DependencyEdge(
            source="Agent_Guru/a.py",
            target="Agent_Guru/b.py",
            import_type="from",
            symbol="MyClass",
        )
        assert edge.symbol == "MyClass"
        assert edge.import_type == "from"


# ---------------------------------------------------------------------------
# PerformanceMetric dataclass
# ---------------------------------------------------------------------------


class TestPerformanceMetric:
    """PerformanceMetric dataclass instantiation."""

    def test_meets_target_true(self) -> None:
        m = PerformanceMetric(
            metric_name="Wake Word P95",
            unit="ms",
            before_p95=350.0,
            after_p95=145.0,
            target=200.0,
            meets_target=True,
        )
        assert m.meets_target is True
        assert m.after_p95 < m.target

    def test_meets_target_false(self) -> None:
        m = PerformanceMetric(
            metric_name="STT P95",
            unit="ms",
            before_p95=2000.0,
            after_p95=1500.0,
            target=1000.0,
            meets_target=False,
        )
        assert m.meets_target is False

    def test_zero_values_are_valid(self) -> None:
        m = PerformanceMetric(
            metric_name="idle_cpu",
            unit="%",
            before_p95=0.0,
            after_p95=0.0,
            target=10.0,
            meets_target=True,
        )
        assert m.before_p95 == 0.0


# ---------------------------------------------------------------------------
# RemediationItem dataclass
# ---------------------------------------------------------------------------


class TestRemediationItem:
    """RemediationItem dataclass instantiation."""

    def test_instantiation(self) -> None:
        item = RemediationItem(
            id="REM-001",
            phase=2,
            severity=Severity.HIGH,
            affected_module="Agent_Guru/speech/wake_word.py",
            description="Replace Vosk with pvporcupine",
            expected_improvement="-70ms at P95 wake word latency",
            estimated_effort_hours=8.0,
            competitive_impact_score=42.5,
        )
        assert item.id == "REM-001"
        assert item.competitive_impact_score == pytest.approx(42.5)

    def test_zero_effort_is_valid(self) -> None:
        item = RemediationItem(
            id="REM-002",
            phase=5,
            severity=Severity.LOW,
            affected_module="Agent_Guru/utils/path_utils.py",
            description="Remove unused import",
            expected_improvement="0ms (cosmetic)",
            estimated_effort_hours=0.0,
            competitive_impact_score=0.0,
        )
        assert item.estimated_effort_hours == 0.0


# ---------------------------------------------------------------------------
# IntegrationCheckResult dataclass
# ---------------------------------------------------------------------------


class TestIntegrationCheckResult:
    """IntegrationCheckResult dataclass instantiation."""

    def test_passed(self) -> None:
        r = IntegrationCheckResult(
            check_id=1,
            description="Orchestrator startup",
            passed=True,
            details="All 11 subsystems up in 8.3s",
        )
        assert r.passed is True
        assert r.check_id == 1

    def test_failed(self) -> None:
        r = IntegrationCheckResult(
            check_id=5,
            description="LLM produces non-empty response within 2s P95",
            passed=False,
            details="LLM timed out after 3.1s on 3 of 10 runs",
        )
        assert r.passed is False

    def test_default_details_is_empty(self) -> None:
        r = IntegrationCheckResult(check_id=2, description="VAD trigger", passed=True)
        assert r.details == ""


# ---------------------------------------------------------------------------
# AuditReport dataclass
# ---------------------------------------------------------------------------


class TestAuditReport:
    """AuditReport dataclass instantiation and default isolation."""

    def test_empty_report_instantiation(self) -> None:
        report = AuditReport()
        assert report.findings == []
        assert report.inventory == []
        assert report.dependency_edges == []
        assert report.performance_metrics == []
        assert report.remediation_backlog == []
        assert report.integration_results == []
        assert report.coverage_by_module == {}
        assert report.phase1_detailed_content == ""

    def test_all_lists_independent(self) -> None:
        a = AuditReport()
        b = AuditReport()
        a.findings.append(
            Finding(
                id="X", phase=1, category=FindingCategory.COMPILE_ERROR,
                severity=Severity.INFO, file_path="f.py", line_number=1,
                rule="E1", description="d",
            )
        )
        assert b.findings == [], "default_factory must produce independent lists"

    def test_populated_report(self, sample_audit_report: AuditReport) -> None:
        assert len(sample_audit_report.findings) == 2  # noqa: PLR2004
        assert len(sample_audit_report.inventory) == 2  # noqa: PLR2004
        assert len(sample_audit_report.performance_metrics) == 1
        assert len(sample_audit_report.integration_results) == 1
