"""
Tests for verification data models.
Coverage Target: >80% (enforced by CI/CD)
"""

from datetime import datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from Agent_Guru.reasoning.models.verification import (
    IssueSeverity,
    IssueType,
    VerificationAction,
    VerificationIssue,
    VerificationResult,
)


class TestIssueType:
    """Unit tests for IssueType enum."""

    def test_all_issue_types_defined(self):
        """Test that all expected issue types are defined."""
        expected_types = {
            "plan_correctness",
            "tool_compatibility",
            "logical_consistency",
            "intent_alignment",
        }
        actual_types = {t.value for t in IssueType}
        assert actual_types == expected_types

    def test_issue_type_values(self):
        """Test specific issue type values."""
        assert IssueType.PLAN_CORRECTNESS.value == "plan_correctness"
        assert IssueType.TOOL_COMPATIBILITY.value == "tool_compatibility"
        assert IssueType.LOGICAL_CONSISTENCY.value == "logical_consistency"
        assert IssueType.INTENT_ALIGNMENT.value == "intent_alignment"


class TestIssueSeverity:
    """Unit tests for IssueSeverity enum."""

    def test_all_severities_defined(self):
        """Test that all expected severities are defined."""
        expected_severities = {"critical", "warning", "info"}
        actual_severities = {s.value for s in IssueSeverity}
        assert actual_severities == expected_severities

    def test_severity_values(self):
        """Test specific severity values."""
        assert IssueSeverity.CRITICAL.value == "critical"
        assert IssueSeverity.WARNING.value == "warning"
        assert IssueSeverity.INFO.value == "info"


class TestVerificationAction:
    """Unit tests for VerificationAction enum."""

    def test_all_actions_defined(self):
        """Test that all expected actions are defined."""
        expected_actions = {"proceed", "clarify", "replan", "abort"}
        actual_actions = {a.value for a in VerificationAction}
        assert actual_actions == expected_actions

    def test_action_values(self):
        """Test specific action values."""
        assert VerificationAction.PROCEED.value == "proceed"
        assert VerificationAction.CLARIFY.value == "clarify"
        assert VerificationAction.REPLAN.value == "replan"
        assert VerificationAction.ABORT.value == "abort"


class TestVerificationIssue:
    """Unit tests for VerificationIssue model."""

    def test_create_valid_issue(self):
        """Test creating a valid verification issue."""
        issue = VerificationIssue(
            issue_type=IssueType.TOOL_COMPATIBILITY,
            severity=IssueSeverity.CRITICAL,
            description="Tool 'send_email' requires parameter 'recipient' which is missing",
            affected_step=2,
        )

        assert issue.issue_type == IssueType.TOOL_COMPATIBILITY
        assert issue.severity == IssueSeverity.CRITICAL
        assert "send_email" in issue.description
        assert issue.affected_step == 2
        assert isinstance(issue.timestamp, datetime)

    def test_create_issue_without_affected_step(self):
        """Test creating an issue without affected step (plan-level issue)."""
        issue = VerificationIssue(
            issue_type=IssueType.PLAN_CORRECTNESS,
            severity=IssueSeverity.WARNING,
            description="Plan may have missing steps to achieve the goal",
        )

        assert issue.affected_step is None

    def test_description_validation_empty(self):
        """Test that empty description is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            VerificationIssue(
                issue_type=IssueType.PLAN_CORRECTNESS, severity=IssueSeverity.INFO, description=""
            )

    def test_description_validation_too_short(self):
        """Test that too short description is rejected."""
        with pytest.raises(ValueError, match="at least 10 characters"):
            VerificationIssue(
                issue_type=IssueType.PLAN_CORRECTNESS,
                severity=IssueSeverity.INFO,
                description="Too short",
            )

    def test_description_validation_whitespace_trimmed(self):
        """Test that description whitespace is trimmed."""
        issue = VerificationIssue(
            issue_type=IssueType.PLAN_CORRECTNESS,
            severity=IssueSeverity.INFO,
            description="  Valid description with whitespace  ",
        )

        assert issue.description == "Valid description with whitespace"

    def test_affected_step_validation_negative(self):
        """Test that negative affected_step is rejected."""
        with pytest.raises(ValueError):
            VerificationIssue(
                issue_type=IssueType.TOOL_COMPATIBILITY,
                severity=IssueSeverity.CRITICAL,
                description="Tool parameter missing",
                affected_step=-1,
            )

    def test_json_serialization(self):
        """Test JSON serialization of issue."""
        issue = VerificationIssue(
            issue_type=IssueType.LOGICAL_CONSISTENCY,
            severity=IssueSeverity.WARNING,
            description="Conflicting actions detected in plan",
        )

        json_data = issue.model_dump()
        assert json_data["issue_type"] == "logical_consistency"
        assert json_data["severity"] == "warning"
        assert "Conflicting" in json_data["description"]


class TestVerificationResult:
    """Unit tests for VerificationResult model."""

    def test_create_valid_result(self):
        """Test creating a valid verification result."""
        issue = VerificationIssue(
            issue_type=IssueType.TOOL_COMPATIBILITY,
            severity=IssueSeverity.CRITICAL,
            description="Tool parameter missing",
        )

        result = VerificationResult(
            is_valid=False,
            confidence=0.85,
            issues=[issue],
            recommendation=VerificationAction.REPLAN,
            verification_time_ms=150.5,
        )

        assert result.is_valid is False
        assert result.confidence == 0.85
        assert len(result.issues) == 1
        assert result.recommendation == VerificationAction.REPLAN
        assert result.verification_time_ms == 150.5
        assert isinstance(result.timestamp, datetime)

    def test_create_result_no_issues(self):
        """Test creating a result with no issues."""
        result = VerificationResult(
            is_valid=True,
            confidence=0.95,
            issues=[],
            recommendation=VerificationAction.PROCEED,
            verification_time_ms=100.0,
        )

        assert result.is_valid is True
        assert len(result.issues) == 0

    def test_confidence_validation_below_zero(self):
        """Test that confidence below 0.0 is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            VerificationResult(
                is_valid=True,
                confidence=-0.1,
                issues=[],
                recommendation=VerificationAction.PROCEED,
                verification_time_ms=100.0,
            )

    def test_confidence_validation_above_one(self):
        """Test that confidence above 1.0 is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            VerificationResult(
                is_valid=True,
                confidence=1.5,
                issues=[],
                recommendation=VerificationAction.PROCEED,
                verification_time_ms=100.0,
            )

    def test_verification_time_validation_negative(self):
        """Test that negative verification time is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            VerificationResult(
                is_valid=True,
                confidence=0.9,
                issues=[],
                recommendation=VerificationAction.PROCEED,
                verification_time_ms=-10.0,
            )

    def test_verification_time_validation_too_large(self):
        """Test that excessive verification time is rejected."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            VerificationResult(
                is_valid=True,
                confidence=0.9,
                issues=[],
                recommendation=VerificationAction.PROCEED,
                verification_time_ms=6000.0,  # > 5000ms
            )

    def test_issues_validation_too_many(self):
        """Test that too many issues are rejected."""
        issues = [
            VerificationIssue(
                issue_type=IssueType.PLAN_CORRECTNESS,
                severity=IssueSeverity.INFO,
                description=f"Issue number {i} description",
            )
            for i in range(51)  # > 50
        ]

        with pytest.raises(ValueError, match="Too many issues"):
            VerificationResult(
                is_valid=False,
                confidence=0.5,
                issues=issues,
                recommendation=VerificationAction.ABORT,
                verification_time_ms=200.0,
            )

    def test_has_critical_issues_true(self):
        """Test has_critical_issues returns True when critical issues exist."""
        critical_issue = VerificationIssue(
            issue_type=IssueType.TOOL_COMPATIBILITY,
            severity=IssueSeverity.CRITICAL,
            description="Critical tool issue",
        )

        result = VerificationResult(
            is_valid=False,
            confidence=0.8,
            issues=[critical_issue],
            recommendation=VerificationAction.REPLAN,
            verification_time_ms=150.0,
        )

        assert result.has_critical_issues() is True

    def test_has_critical_issues_false(self):
        """Test has_critical_issues returns False when no critical issues."""
        warning_issue = VerificationIssue(
            issue_type=IssueType.PLAN_CORRECTNESS,
            severity=IssueSeverity.WARNING,
            description="Warning issue",
        )

        result = VerificationResult(
            is_valid=True,
            confidence=0.9,
            issues=[warning_issue],
            recommendation=VerificationAction.PROCEED,
            verification_time_ms=120.0,
        )

        assert result.has_critical_issues() is False

    def test_has_warnings_true(self):
        """Test has_warnings returns True when warnings exist."""
        warning_issue = VerificationIssue(
            issue_type=IssueType.LOGICAL_CONSISTENCY,
            severity=IssueSeverity.WARNING,
            description="Warning about logic",
        )

        result = VerificationResult(
            is_valid=True,
            confidence=0.85,
            issues=[warning_issue],
            recommendation=VerificationAction.PROCEED,
            verification_time_ms=130.0,
        )

        assert result.has_warnings() is True

    def test_get_critical_issues(self):
        """Test getting only critical issues."""
        critical_issue = VerificationIssue(
            issue_type=IssueType.TOOL_COMPATIBILITY,
            severity=IssueSeverity.CRITICAL,
            description="Critical issue",
        )
        warning_issue = VerificationIssue(
            issue_type=IssueType.PLAN_CORRECTNESS,
            severity=IssueSeverity.WARNING,
            description="Warning issue",
        )

        result = VerificationResult(
            is_valid=False,
            confidence=0.7,
            issues=[critical_issue, warning_issue],
            recommendation=VerificationAction.REPLAN,
            verification_time_ms=160.0,
        )

        critical_issues = result.get_critical_issues()
        assert len(critical_issues) == 1
        assert critical_issues[0].severity == IssueSeverity.CRITICAL

    def test_get_warnings(self):
        """Test getting only warnings."""
        critical_issue = VerificationIssue(
            issue_type=IssueType.TOOL_COMPATIBILITY,
            severity=IssueSeverity.CRITICAL,
            description="Critical issue",
        )
        warning_issue = VerificationIssue(
            issue_type=IssueType.PLAN_CORRECTNESS,
            severity=IssueSeverity.WARNING,
            description="Warning issue",
        )

        result = VerificationResult(
            is_valid=False,
            confidence=0.7,
            issues=[critical_issue, warning_issue],
            recommendation=VerificationAction.REPLAN,
            verification_time_ms=160.0,
        )

        warnings = result.get_warnings()
        assert len(warnings) == 1
        assert warnings[0].severity == IssueSeverity.WARNING

    def test_get_issues_by_type(self):
        """Test getting issues by type."""
        tool_issue = VerificationIssue(
            issue_type=IssueType.TOOL_COMPATIBILITY,
            severity=IssueSeverity.CRITICAL,
            description="Tool issue",
        )
        plan_issue = VerificationIssue(
            issue_type=IssueType.PLAN_CORRECTNESS,
            severity=IssueSeverity.WARNING,
            description="Plan issue",
        )

        result = VerificationResult(
            is_valid=False,
            confidence=0.75,
            issues=[tool_issue, plan_issue],
            recommendation=VerificationAction.REPLAN,
            verification_time_ms=140.0,
        )

        tool_issues = result.get_issues_by_type(IssueType.TOOL_COMPATIBILITY)
        assert len(tool_issues) == 1
        assert tool_issues[0].issue_type == IssueType.TOOL_COMPATIBILITY

    def test_get_issues_for_step(self):
        """Test getting issues for a specific step."""
        step1_issue = VerificationIssue(
            issue_type=IssueType.TOOL_COMPATIBILITY,
            severity=IssueSeverity.CRITICAL,
            description="Step 1 issue",
            affected_step=1,
        )
        step2_issue = VerificationIssue(
            issue_type=IssueType.LOGICAL_CONSISTENCY,
            severity=IssueSeverity.WARNING,
            description="Step 2 issue",
            affected_step=2,
        )

        result = VerificationResult(
            is_valid=False,
            confidence=0.8,
            issues=[step1_issue, step2_issue],
            recommendation=VerificationAction.REPLAN,
            verification_time_ms=170.0,
        )

        step1_issues = result.get_issues_for_step(1)
        assert len(step1_issues) == 1
        assert step1_issues[0].affected_step == 1


class TestVerificationResultProperties:
    """Property-based tests for VerificationResult."""

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0),
        verification_time_ms=st.floats(min_value=0.0, max_value=5000.0),
    )
    def test_valid_result_always_created(self, confidence: float, verification_time_ms: float):
        """Property: Valid parameters always create a result."""
        result = VerificationResult(
            is_valid=True,
            confidence=confidence,
            issues=[],
            recommendation=VerificationAction.PROCEED,
            verification_time_ms=verification_time_ms,
        )

        assert result is not None
        assert 0.0 <= result.confidence <= 1.0
        assert result.verification_time_ms >= 0.0

    @given(num_issues=st.integers(min_value=0, max_value=10))
    def test_issues_list_always_valid(self, num_issues: int):
        """Property: Any reasonable number of issues can be added."""
        issues = [
            VerificationIssue(
                issue_type=IssueType.PLAN_CORRECTNESS,
                severity=IssueSeverity.INFO,
                description=f"Test issue number {i} with sufficient length",
            )
            for i in range(num_issues)
        ]

        result = VerificationResult(
            is_valid=True,
            confidence=0.9,
            issues=issues,
            recommendation=VerificationAction.PROCEED,
            verification_time_ms=100.0,
        )

        assert len(result.issues) == num_issues
