"""Unit tests for audit/report.py - task 1.7.

Validates:
- atomic_write produces correct file content with crash-safe rename
- write() produces a document with exactly 9 top-level '## ' headings
  in the specified order

Subsystem: audit/tests
Requirements: 9.1, 9.6
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from audit.models import AuditReport
from audit.report import MasterReportWriter

# The 9 required top-level section headings in order (Requirement 9.1)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_h2_headings(content: str) -> list[str]:
    """Return list of ## heading titles in document order."""
    return [
        m.group(1).strip()
        for m in re.finditer(r"^##\s+(.+)$", content, re.MULTILINE)
    ]


# ---------------------------------------------------------------------------
# atomic_write
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    """atomic_write() produces correct file content and is crash-safe."""

    def test_content_is_written_correctly(self, tmp_path: Path) -> None:
        target = tmp_path / "output.md"
        writer = MasterReportWriter(report_path=target)
        writer.atomic_write(target, "hello world")
        assert target.read_text(encoding="utf-8") == "hello world"

    def test_unicode_content_is_preserved(self, tmp_path: Path) -> None:
        target = tmp_path / "unicode.md"
        writer = MasterReportWriter(report_path=target)
        content = "# Heading\n\nText with emojis: 🚀✅❌ and accents: café"
        writer.atomic_write(target, content)
        assert target.read_text(encoding="utf-8") == content

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "existing.md"
        target.write_text("old content", encoding="utf-8")
        writer = MasterReportWriter(report_path=target)
        writer.atomic_write(target, "new content")
        assert target.read_text(encoding="utf-8") == "new content"

    def test_no_temp_file_left_on_success(self, tmp_path: Path) -> None:
        target = tmp_path / "clean.md"
        writer = MasterReportWriter(report_path=target)
        writer.atomic_write(target, "content")
        # Only the target file should exist - no .tmp files
        remaining = list(tmp_path.glob("*.tmp"))
        assert remaining == []

    def test_empty_content_is_written(self, tmp_path: Path) -> None:
        target = tmp_path / "empty.md"
        writer = MasterReportWriter(report_path=target)
        writer.atomic_write(target, "")
        assert target.read_text(encoding="utf-8") == ""

    def test_large_content_is_written(self, tmp_path: Path) -> None:
        target = tmp_path / "large.md"
        writer = MasterReportWriter(report_path=target)
        # 1 MB of content
        large = "x" * (1024 * 1024)
        writer.atomic_write(target, large)
        assert len(target.read_text(encoding="utf-8")) == 1024 * 1024

    @pytest.mark.skipif(
        __import__("sys").platform == "win32",
        reason="chmod-based permission restriction is unreliable on Windows NTFS",
    )
    def test_raises_on_unwritable_parent(self, tmp_path: Path) -> None:
        """Should propagate OSError when the directory is not writable."""
        # Make a read-only subdirectory
        ro_dir = tmp_path / "readonly"
        ro_dir.mkdir()
        target = ro_dir / "output.md"
        try:
            ro_dir.chmod(0o444)
            writer = MasterReportWriter(report_path=target)
            with pytest.raises(OSError):
                writer.atomic_write(target, "data")
        finally:
            ro_dir.chmod(0o755)  # restore so tmp_path cleanup works


# ---------------------------------------------------------------------------
# write() - section structure
# ---------------------------------------------------------------------------


class TestWrite:
    """write() produces a document with exactly 9 ## headings in order."""

    def test_empty_report_has_nine_sections(self, tmp_path: Path) -> None:
        path = tmp_path / "report.md"
        writer = MasterReportWriter(report_path=path)
        writer.write(AuditReport())
        content = path.read_text(encoding="utf-8")
        headings = _extract_h2_headings(content)
        assert len(headings) == len(REQUIRED_SECTIONS)

    def test_sections_are_in_correct_order(self, tmp_path: Path) -> None:
        path = tmp_path / "report.md"
        writer = MasterReportWriter(report_path=path)
        writer.write(AuditReport())
        content = path.read_text(encoding="utf-8")
        headings = _extract_h2_headings(content)
        assert headings == REQUIRED_SECTIONS

    def test_populated_report_has_nine_sections(
        self, tmp_path: Path, sample_audit_report: AuditReport
    ) -> None:
        path = tmp_path / "report.md"
        writer = MasterReportWriter(report_path=path)
        writer.write(sample_audit_report)
        content = path.read_text(encoding="utf-8")
        headings = _extract_h2_headings(content)
        assert headings == REQUIRED_SECTIONS

    def test_findings_appear_in_bug_report(
        self, tmp_path: Path, sample_audit_report: AuditReport
    ) -> None:
        path = tmp_path / "report.md"
        writer = MasterReportWriter(report_path=path)
        writer.write(sample_audit_report)
        content = path.read_text(encoding="utf-8")
        # The two findings from the fixture must appear
        assert "BUG-001" in content
        assert "BUG-002" in content

    def test_performance_metrics_appear(
        self, tmp_path: Path, sample_audit_report: AuditReport
    ) -> None:
        path = tmp_path / "report.md"
        writer = MasterReportWriter(report_path=path)
        writer.write(sample_audit_report)
        content = path.read_text(encoding="utf-8")
        assert "Wake Word P95 Latency" in content

    def test_integration_results_appear(
        self, tmp_path: Path, sample_audit_report: AuditReport
    ) -> None:
        path = tmp_path / "report.md"
        writer = MasterReportWriter(report_path=path)
        writer.write(sample_audit_report)
        content = path.read_text(encoding="utf-8")
        assert "startup" in content.lower()

    def test_write_is_idempotent(self, tmp_path: Path) -> None:
        """Writing twice to same path produces identical output."""
        path = tmp_path / "report.md"
        writer = MasterReportWriter(report_path=path)
        report = AuditReport()
        writer.write(report)
        first = path.read_text(encoding="utf-8")
        writer.write(report)
        second = path.read_text(encoding="utf-8")
        assert first == second

    def test_report_file_is_created(self, tmp_path: Path) -> None:
        path = tmp_path / "report.md"
        assert not path.exists()
        writer = MasterReportWriter(report_path=path)
        writer.write(AuditReport())
        assert path.exists()

    def test_h1_title_present(self, tmp_path: Path) -> None:
        path = tmp_path / "report.md"
        writer = MasterReportWriter(report_path=path)
        writer.write(AuditReport())
        content = path.read_text(encoding="utf-8")
        assert content.startswith("# Agent Guru")


# ---------------------------------------------------------------------------
# add_phase_error / add_temporary_regression
# ---------------------------------------------------------------------------


class TestPhaseErrors:
    """Phase error and regression recording."""

    def test_phase_error_appears_in_report(self, tmp_path: Path) -> None:
        path = tmp_path / "report.md"
        writer = MasterReportWriter(report_path=path)
        writer.add_phase_error("Phase 3", ValueError("bandit crashed"))
        writer.write(AuditReport())
        content = path.read_text(encoding="utf-8")
        assert "Phase 3" in content

    def test_multiple_errors_all_recorded(self, tmp_path: Path) -> None:
        path = tmp_path / "report.md"
        writer = MasterReportWriter(report_path=path)
        writer.add_phase_error("Phase 1", RuntimeError("scan failed"))
        writer.add_phase_error("Phase 4", TimeoutError("benchmark timed out"))
        assert len(writer.phase_errors) == 2  # noqa: PLR2004

    def test_temporary_regression_recorded(self, tmp_path: Path) -> None:
        path = tmp_path / "report.md"
        writer = MasterReportWriter(report_path=path)
        writer.add_temporary_regression("speech/tts", "Will fix in task 5.14")
        assert len(writer.temporary_regressions) == 1
        scope, plan = writer.temporary_regressions[0]
        assert scope == "speech/tts"
        assert "5.14" in plan
