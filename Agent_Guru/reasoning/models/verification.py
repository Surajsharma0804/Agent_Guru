"""
Module: agent_guru.reasoning.models.verification
Purpose: Data models for reasoning verification and validation
Author: Agent Guru Team
Date: 2026-02-22

Performance Requirements:
- Time Complexity: O(1) for model creation and validation
- Space Complexity: O(n) where n is number of issues
- Validation: <10ms per model

Design Decisions:
- Use Pydantic for automatic validation and serialization
- Enum types for type safety and validation
- Immutable models for thread safety
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class IssueType(str, Enum):
    """Types of verification issues that can be detected.

    Attributes:
        PLAN_CORRECTNESS: Issues with plan logic or completeness
        TOOL_COMPATIBILITY: Issues with tool availability or parameters
        LOGICAL_CONSISTENCY: Issues with conflicting or impossible actions
        INTENT_ALIGNMENT: Issues with plan not matching user intent
    """

    PLAN_CORRECTNESS = "plan_correctness"
    TOOL_COMPATIBILITY = "tool_compatibility"
    LOGICAL_CONSISTENCY = "logical_consistency"
    INTENT_ALIGNMENT = "intent_alignment"


class IssueSeverity(str, Enum):
    """Severity levels for verification issues.

    Attributes:
        CRITICAL: Must be fixed before execution (blocks execution)
        WARNING: Should be reviewed but can proceed
        INFO: Informational only, no action required
    """

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class VerificationAction(str, Enum):
    """Recommended actions based on verification results.

    Attributes:
        PROCEED: Plan is valid, proceed with execution
        CLARIFY: Ask user for clarification
        REPLAN: Regenerate plan with feedback
        ABORT: Cannot proceed, abort execution
    """

    PROCEED = "proceed"
    CLARIFY = "clarify"
    REPLAN = "replan"
    ABORT = "abort"


class VerificationIssue(BaseModel):
    """Represents a single verification issue found during plan validation.

    Attributes:
        issue_type: Type of issue detected
        severity: Severity level of the issue
        description: Human-readable description of the issue
        affected_step: Optional step index that is affected (None for plan-level issues)
        timestamp: When the issue was detected

    Example:
        >>> issue = VerificationIssue(
        ...     issue_type=IssueType.TOOL_COMPATIBILITY,
        ...     severity=IssueSeverity.CRITICAL,
        ...     description="Tool 'send_email' requires parameter 'recipient' which is missing",
        ...     affected_step=2
        ... )
    """

    issue_type: IssueType = Field(..., description="Type of verification issue")
    severity: IssueSeverity = Field(..., description="Severity level of the issue")
    description: str = Field(
        ..., min_length=1, max_length=500, description="Human-readable issue description"
    )
    affected_step: Optional[int] = Field(
        None, ge=0, description="Step index affected by this issue (None for plan-level)"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc), description="When the issue was detected"
    )

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Validate description is not empty and has reasonable length."""
        if not v or not v.strip():
            raise ValueError("Description cannot be empty")
        if len(v.strip()) < 10:
            raise ValueError("Description must be at least 10 characters")
        return v.strip()

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "issue_type": "tool_compatibility",
                "severity": "critical",
                "description": "Tool 'send_email' requires parameter 'recipient' which is missing",
                "affected_step": 2,
                "timestamp": "2026-02-22T10:30:00Z",
            }
        }


class VerificationResult(BaseModel):
    """Result of reasoning plan verification.

    Attributes:
        is_valid: Whether the plan passed all critical checks
        confidence: Confidence score 0.0-1.0 in the verification result
        issues: List of issues found during verification
        recommendation: Recommended action based on verification
        verification_time_ms: Time taken for verification in milliseconds
        timestamp: When verification was performed

    Example:
        >>> result = VerificationResult(
        ...     is_valid=False,
        ...     confidence=0.85,
        ...     issues=[issue],
        ...     recommendation=VerificationAction.REPLAN,
        ...     verification_time_ms=150.5
        ... )
    """

    is_valid: bool = Field(..., description="Whether plan passed all critical checks")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in verification result (0.0-1.0)"
    )
    issues: list[VerificationIssue] = Field(
        default_factory=list, description="List of issues found"
    )
    recommendation: VerificationAction = Field(..., description="Recommended action")
    verification_time_ms: float = Field(
        ..., ge=0.0, description="Verification time in milliseconds"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc), description="When verification was performed"
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate confidence is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {v}")
        return v

    @field_validator("verification_time_ms")
    @classmethod
    def validate_verification_time(cls, v: float) -> float:
        """Validate verification time is non-negative and reasonable."""
        if v < 0:
            raise ValueError(f"Verification time cannot be negative, got {v}")
        if v > 5000:  # 5 seconds is too long
            raise ValueError(f"Verification time exceeds maximum (5000ms), got {v}")
        return v

    @field_validator("issues")
    @classmethod
    def validate_issues(cls, v: list[VerificationIssue]) -> list[VerificationIssue]:
        """Validate issues list is reasonable size."""
        if len(v) > 50:  # Sanity check
            raise ValueError(f"Too many issues ({len(v)}), maximum is 50")
        return v

    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues.

        Returns:
            True if any issue has CRITICAL severity
        """
        return any(issue.severity == IssueSeverity.CRITICAL for issue in self.issues)

    def has_warnings(self) -> bool:
        """Check if there are any warnings.

        Returns:
            True if any issue has WARNING severity
        """
        return any(issue.severity == IssueSeverity.WARNING for issue in self.issues)

    def get_critical_issues(self) -> list[VerificationIssue]:
        """Get all critical issues.

        Returns:
            List of critical issues
        """
        return [issue for issue in self.issues if issue.severity == IssueSeverity.CRITICAL]

    def get_warnings(self) -> list[VerificationIssue]:
        """Get all warnings.

        Returns:
            List of warning issues
        """
        return [issue for issue in self.issues if issue.severity == IssueSeverity.WARNING]

    def get_issues_by_type(self, issue_type: IssueType) -> list[VerificationIssue]:
        """Get all issues of a specific type.

        Args:
            issue_type: Type of issues to retrieve

        Returns:
            List of issues matching the type
        """
        return [issue for issue in self.issues if issue.issue_type == issue_type]

    def get_issues_for_step(self, step_index: int) -> list[VerificationIssue]:
        """Get all issues affecting a specific step.

        Args:
            step_index: Index of the step

        Returns:
            List of issues affecting the step
        """
        return [issue for issue in self.issues if issue.affected_step == step_index]

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "is_valid": False,
                "confidence": 0.85,
                "issues": [
                    {
                        "issue_type": "tool_compatibility",
                        "severity": "critical",
                        "description": "Tool 'send_email' requires parameter 'recipient' which is missing",
                        "affected_step": 2,
                        "timestamp": "2026-02-22T10:30:00Z",
                    }
                ],
                "recommendation": "replan",
                "verification_time_ms": 150.5,
                "timestamp": "2026-02-22T10:30:00Z",
            }
        }
