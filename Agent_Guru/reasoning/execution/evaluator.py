"""Execution Evaluator with feedback loop for Core Reasoning Engine.

Performance Requirements:
- Time Complexity: O(1) per evaluation
- Space Complexity: O(1) (no unbounded growth)
- Latency: <50ms per evaluation
- Max retries: 3 attempts with exponential backoff

Design Decisions:
- Schema validation for result format checking
- Sanity checks for value reasonableness
- Business rules validation
- Retry decision logic with transient error detection
- Clarification trigger detection
- Dynamic plan adjustment support
- Task abandonment conditions

Validates Requirements: 25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7

Author: Kiro AI
Date: 2026-02-22
Version: 1.0.0
"""

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ValidationResult(Enum):
    """Result of validation check."""

    VALID = "valid"  # Result is valid
    INVALID = "invalid"  # Result is invalid
    INCOMPLETE = "incomplete"  # Result is missing data
    AMBIGUOUS = "ambiguous"  # Result has multiple interpretations
    UNEXPECTED = "unexpected"  # Result doesn't match expected format


class RetryDecision(Enum):
    """Decision on whether to retry execution."""

    RETRY = "retry"  # Retry execution
    NO_RETRY = "no_retry"  # Don't retry
    CLARIFY = "clarify"  # Ask user for clarification
    ADJUST_PLAN = "adjust_plan"  # Adjust execution plan
    ABANDON = "abandon"  # Abandon task


class ErrorType(Enum):
    """Classification of error types."""

    TRANSIENT = "transient"  # Temporary error (network timeout, rate limit)
    TEMPORARY_UNAVAILABLE = "temporary_unavailable"  # Service temporarily down
    RECOVERABLE = "recoverable"  # Recoverable error (invalid parameter)
    UNRECOVERABLE = "unrecoverable"  # Permanent error
    USER_CANCELLED = "user_cancelled"  # User cancelled execution
    TIMEOUT = "timeout"  # Execution timeout


@dataclass
class ValidationIssue:
    """Represents a validation issue found in result.

    Attributes:
        issue_type: Type of validation issue
        field: Field name where issue was found
        message: Human-readable description
        severity: Severity level (error, warning, info)
        details: Additional details about the issue

    """

    issue_type: ValidationResult
    field: str
    message: str
    severity: str = "error"  # error, warning, info
    details: dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass
class EvaluationResult:
    """Result of execution evaluation.

    Attributes:
        is_valid: Whether result passed validation
        validation_result: Overall validation result
        issues: List of validation issues found
        retry_decision: Decision on whether to retry
        retry_delay: Delay before retry (seconds)
        clarification_needed: Whether clarification is needed
        clarification_question: Question to ask user
        plan_adjustment: Suggested plan adjustment
        should_abandon: Whether task should be abandoned
        abandonment_reason: Reason for abandonment
        timestamp: When evaluation was performed

    """

    is_valid: bool
    validation_result: ValidationResult
    issues: list[ValidationIssue] = dataclass_field(default_factory=list)
    retry_decision: RetryDecision = RetryDecision.NO_RETRY
    retry_delay: float = 0.0
    clarification_needed: bool = False
    clarification_question: str | None = None
    plan_adjustment: dict[str, Any] | None = None
    should_abandon: bool = False
    abandonment_reason: str | None = None
    timestamp: datetime = dataclass_field(default_factory=lambda: datetime.now(tz=UTC))


class ResultValidator:
    """Validates execution results against expected format and business rules.

    Time Complexity: O(1) per validation
    Space Complexity: O(1)

    Example:
        >>> validator = ResultValidator()
        >>> result = {"timer_id": "timer_123", "duration": 300}
        >>> schema = {"timer_id": str, "duration": int}
        >>> validation = validator.validate(result, schema)
        >>> print(f"Valid: {validation.is_valid}")

    """

    def __init__(self) -> None:
        """Initialize result validator."""
        self._validation_rules: dict[str, Callable[[Any], bool]] = {}

    def validate(
        self,
        result_data: Any,
        expected_schema: dict[str, type] | None = None,
        business_rules: dict[str, Callable[[Any], bool]] | None = None,
    ) -> EvaluationResult:
        """Validate execution result.

        Time Complexity: O(1) - fixed number of checks
        Space Complexity: O(1)

        Args:
            result_data: Result data to validate
            expected_schema: Expected schema (field -> type mapping)
            business_rules: Business rules (field -> validation function),
                merged with any rules registered via add_validation_rule().

        Returns:
            EvaluationResult with validation results

        """
        issues: list[ValidationIssue] = []

        # Check if result is None
        if result_data is None:
            issues.append(
                ValidationIssue(
                    issue_type=ValidationResult.INCOMPLETE,
                    field="result_data",
                    message="Result data is None",
                    severity="error",
                ),
            )
            return EvaluationResult(
                is_valid=False,
                validation_result=ValidationResult.INCOMPLETE,
                issues=issues,
            )

        # Schema validation
        if expected_schema:
            schema_issues = self._validate_schema(result_data, expected_schema)
            issues.extend(schema_issues)

        # Business rules validation
        # FIX: previously only ever consulted the `business_rules` argument
        # passed explicitly to THIS call - self._validation_rules (populated
        # by add_validation_rule()/removed by remove_validation_rule()) was
        # never read anywhere in this method. That made add_validation_rule
        # a complete no-op: a caller could register a rule, validate data
        # that clearly violated it, and get zero issues back. Verified this
        # concretely before fixing. Now both sources are actually applied -
        # explicitly-passed business_rules first, then any rules registered
        # on the instance via add_validation_rule().
        effective_business_rules: dict[str, Callable[[Any], bool]] = {}
        if business_rules:
            effective_business_rules.update(business_rules)
        if self._validation_rules:
            # Instance-registered rules don't override an explicitly-passed
            # rule for the same field in this call - the caller's explicit,
            # per-call rule wins if both target the same field.
            for field_name, rule_func in self._validation_rules.items():
                effective_business_rules.setdefault(field_name, rule_func)

        if effective_business_rules:
            rule_issues = self._validate_business_rules(result_data, effective_business_rules)
            issues.extend(rule_issues)

        # Sanity checks
        sanity_issues = self._validate_sanity(result_data)
        issues.extend(sanity_issues)

        # Completeness check
        completeness_issues = self._validate_completeness(result_data, expected_schema)
        issues.extend(completeness_issues)

        # Determine overall validation result
        if not issues:
            return EvaluationResult(
                is_valid=True,
                validation_result=ValidationResult.VALID,
            )

        # Check for critical issues
        has_errors = any(issue.severity == "error" for issue in issues)
        if has_errors:
            # Determine specific validation result
            if any(issue.issue_type == ValidationResult.INCOMPLETE for issue in issues):
                validation_result = ValidationResult.INCOMPLETE
            elif any(issue.issue_type == ValidationResult.AMBIGUOUS for issue in issues):
                validation_result = ValidationResult.AMBIGUOUS
            elif any(issue.issue_type == ValidationResult.UNEXPECTED for issue in issues):
                validation_result = ValidationResult.UNEXPECTED
            else:
                validation_result = ValidationResult.INVALID

            return EvaluationResult(
                is_valid=False,
                validation_result=validation_result,
                issues=issues,
            )

        # Only warnings - consider valid but with issues
        return EvaluationResult(
            is_valid=True,
            validation_result=ValidationResult.VALID,
            issues=issues,
        )

    def _validate_schema(
        self,
        result_data: Any,
        expected_schema: dict[str, type],
    ) -> list[ValidationIssue]:
        """Validate result matches expected schema.

        Args:
            result_data: Result data to validate
            expected_schema: Expected schema

        Returns:
            List of validation issues

        """
        issues: list[ValidationIssue] = []

        # Check if result is dict-like
        if not isinstance(result_data, dict):
            issues.append(
                ValidationIssue(
                    issue_type=ValidationResult.UNEXPECTED,
                    field="result_data",
                    message=f"Expected dict, got {type(result_data).__name__}",
                    severity="error",
                ),
            )
            return issues

        # Check each field in schema
        for field_name, expected_type in expected_schema.items():
            if field_name not in result_data:
                issues.append(
                    ValidationIssue(
                        issue_type=ValidationResult.INCOMPLETE,
                        field=field_name,
                        message=f"Missing required field: {field_name}",
                        severity="error",
                    ),
                )
                continue

            # Check type
            value = result_data[field_name]
            if not isinstance(value, expected_type):
                issues.append(
                    ValidationIssue(
                        issue_type=ValidationResult.INVALID,
                        field=field_name,
                        message=f"Expected {expected_type.__name__}, got {type(value).__name__}",
                        severity="error",
                        details={
                            "expected_type": expected_type.__name__,
                            "actual_type": type(value).__name__,
                        },
                    ),
                )

        return issues

    def _validate_business_rules(
        self,
        result_data: Any,
        business_rules: dict[str, Callable[[Any], bool]],
    ) -> list[ValidationIssue]:
        """Validate result against business rules.

        Args:
            result_data: Result data to validate
            business_rules: Business rules to check

        Returns:
            List of validation issues

        """
        issues: list[ValidationIssue] = []

        if not isinstance(result_data, dict):
            return issues

        for field_name, rule_func in business_rules.items():
            if field_name not in result_data:
                continue

            value = result_data[field_name]
            try:
                if not rule_func(value):
                    issues.append(
                        ValidationIssue(
                            issue_type=ValidationResult.INVALID,
                            field=field_name,
                            message=f"Business rule validation failed for {field_name}",
                            severity="error",
                        ),
                    )
            except Exception as e:
                issues.append(
                    ValidationIssue(
                        issue_type=ValidationResult.INVALID,
                        field=field_name,
                        message=f"Business rule validation error: {e!s}",
                        severity="error",
                        details={"exception": str(e)},
                    ),
                )

        return issues

    def _validate_sanity(self, result_data: Any) -> list[ValidationIssue]:
        """Perform sanity checks on result values.

        Args:
            result_data: Result data to validate

        Returns:
            List of validation issues

        """
        issues: list[ValidationIssue] = []

        if not isinstance(result_data, dict):
            return issues

        # Check for common sanity issues
        for field_name, value in result_data.items():
            # Check for negative values where they don't make sense
            if isinstance(value, (int, float)):
                # Common fields that should be non-negative
                if field_name in {"duration", "count", "size", "length", "amount", "quantity"}:
                    if value < 0:
                        issues.append(
                            ValidationIssue(
                                issue_type=ValidationResult.INVALID,
                                field=field_name,
                                message=f"{field_name} should be non-negative, got {value}",
                                severity="warning",
                            ),
                        )

                # Check for unreasonably large values
                if value > 1e10:  # Arbitrary large threshold
                    issues.append(
                        ValidationIssue(
                            issue_type=ValidationResult.INVALID,
                            field=field_name,
                            message=f"{field_name} has unreasonably large value: {value}",
                            severity="warning",
                        ),
                    )

            # Check for empty strings
            if isinstance(value, str) and not value.strip():
                issues.append(
                    ValidationIssue(
                        issue_type=ValidationResult.INCOMPLETE,
                        field=field_name,
                        message=f"{field_name} is empty string",
                        severity="warning",
                    ),
                )

        return issues

    def _validate_completeness(
        self,
        result_data: Any,
        expected_schema: dict[str, type] | None,
    ) -> list[ValidationIssue]:
        """Check if result has all required data.

        Args:
            result_data: Result data to validate
            expected_schema: Expected schema

        Returns:
            List of validation issues

        """
        issues: list[ValidationIssue] = []

        if not isinstance(result_data, dict):
            return issues

        # If no schema provided, check for empty dict
        if expected_schema is None:
            if not result_data:
                issues.append(
                    ValidationIssue(
                        issue_type=ValidationResult.INCOMPLETE,
                        field="result_data",
                        message="Result data is empty",
                        severity="warning",
                    ),
                )
            return issues

        # Check all required fields are present (already done in schema validation)
        # This is a placeholder for additional completeness checks

        return issues

    def add_validation_rule(
        self,
        rule_name: str,
        rule_func: Callable[[Any], bool],
    ) -> None:
        """Add custom validation rule.

        NOTE: `rule_name` doubles as the field name the rule is applied to
        (it's looked up against `result_data[rule_name]` during validate()),
        matching how `business_rules` dicts are already keyed elsewhere in
        this class - not an arbitrary label.

        Args:
            rule_name: Name of the rule (== the field it validates).
            rule_func: Validation function (returns True if valid)

        """
        self._validation_rules[rule_name] = rule_func

    def remove_validation_rule(self, rule_name: str) -> None:
        """Remove custom validation rule.

        Args:
            rule_name: Name of the rule to remove

        """
        if rule_name in self._validation_rules:
            del self._validation_rules[rule_name]


class ExecutionEvaluator:
    """Evaluates execution results and makes retry/clarification/adjustment decisions.

    Time Complexity: O(1) per evaluation
    Space Complexity: O(1)

    Example:
        >>> evaluator = ExecutionEvaluator(max_retries=3)
        >>> result = ExecutionResult(success=False, error="Network timeout")
        >>> evaluation = evaluator.evaluate(result, retry_count=0)
        >>> print(f"Should retry: {evaluation.retry_decision == RetryDecision.RETRY}")

    """

    def __init__(
        self,
        max_retries: int = 3,
        base_retry_delay: float = 1.0,
    ) -> None:
        """Initialize execution evaluator.

        Args:
            max_retries: Maximum number of retries (default: 3)
            base_retry_delay: Base delay for exponential backoff (default: 1.0s)

        Raises:
            ValueError: If parameters are invalid

        """
        if max_retries < 0:
            msg = f"Invalid max_retries: {max_retries}"
            raise ValueError(msg)
        if base_retry_delay <= 0:
            msg = f"Invalid base_retry_delay: {base_retry_delay}"
            raise ValueError(msg)

        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.validator = ResultValidator()

        # Track retry patterns for improvement - use defaultdict of deque for O(1) bounded append
        self._retry_stats: dict[str, deque[bool]] = defaultdict(lambda: deque(maxlen=100))

    def evaluate(
        self,
        execution_result: Any,
        retry_count: int = 0,
        expected_schema: dict[str, type] | None = None,
        business_rules: dict[str, Callable[[Any], bool]] | None = None,
    ) -> EvaluationResult:
        """Evaluate execution result and make decisions.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            execution_result: Execution result to evaluate
            retry_count: Current retry count
            expected_schema: Expected result schema
            business_rules: Business rules to validate

        Returns:
            EvaluationResult with decisions

        """
        # Check if execution was successful
        if hasattr(execution_result, "success") and execution_result.success:
            # Validate successful result
            result_data = getattr(execution_result, "result_data", None)
            validation = self.validator.validate(result_data, expected_schema, business_rules)

            if validation.is_valid:
                return validation

            # Result is invalid - determine action
            if validation.validation_result == ValidationResult.INCOMPLETE:
                # Missing data - may need clarification
                validation.clarification_needed = True
                validation.clarification_question = self._generate_clarification_question(
                    validation.issues,
                )
                validation.retry_decision = RetryDecision.CLARIFY
            elif validation.validation_result == ValidationResult.AMBIGUOUS:
                # Ambiguous result - need clarification
                validation.clarification_needed = True
                validation.clarification_question = self._generate_clarification_question(
                    validation.issues,
                )
                validation.retry_decision = RetryDecision.CLARIFY
            # Invalid or unexpected - may need retry or adjustment
            elif retry_count < self.max_retries:
                validation.retry_decision = RetryDecision.RETRY
                validation.retry_delay = self._calculate_retry_delay(retry_count)
            else:
                validation.should_abandon = True
                validation.abandonment_reason = "Max retries exceeded with invalid results"
                validation.retry_decision = RetryDecision.ABANDON

            return validation

        # Execution failed - analyze error
        error = getattr(execution_result, "error", None)
        error_type = self._classify_error(error)

        # Make retry decision
        retry_decision = self._make_retry_decision(error_type, retry_count)

        # Calculate retry delay if retrying
        retry_delay = 0.0
        if retry_decision == RetryDecision.RETRY:
            retry_delay = self._calculate_retry_delay(retry_count)

        # Check for abandonment conditions
        should_abandon, abandonment_reason = self._check_abandonment(
            error_type,
            retry_count,
            execution_result,
        )

        return EvaluationResult(
            is_valid=False,
            validation_result=ValidationResult.INVALID,
            retry_decision=retry_decision,
            retry_delay=retry_delay,
            should_abandon=should_abandon,
            abandonment_reason=abandonment_reason,
        )

    def _classify_error(self, error: Any) -> ErrorType:
        """Classify error type.

        Args:
            error: Error to classify

        Returns:
            ErrorType classification

        """
        if error is None:
            return ErrorType.UNRECOVERABLE

        # Convert error to string for analysis
        if isinstance(error, dict):
            error_code = error.get("error_code", "")
            error_msg = error.get("message", "")
        else:
            error_code = ""
            error_msg = str(error)

        error_text = f"{error_code} {error_msg}".lower()

        # Check for specific error types
        if "cancel" in error_text:
            return ErrorType.USER_CANCELLED

        if "timeout" in error_text:
            return ErrorType.TIMEOUT

        # Transient errors (network, rate limit)
        # FIX: "timeout" previously appeared in this list too, but the
        # explicit `if "timeout" in error_text: return ErrorType.TIMEOUT`
        # check above always catches it first - so "timeout" here was
        # provably unreachable dead weight, not a bug that changes
        # behavior (TIMEOUT correctly took precedence either way), just
        # misleading: it implied this branch could still be reached for
        # timeout-related text, which it never could be. Removed.
        transient_indicators = [
            "network",
            "connection",
            "rate limit",
            "too many requests",
            "503",
            "502",
            "504",
        ]
        if any(indicator in error_text for indicator in transient_indicators):
            return ErrorType.TRANSIENT

        # Temporary unavailability
        unavailable_indicators = [
            "unavailable",
            "service down",
            "maintenance",
            "temporarily",
        ]
        if any(indicator in error_text for indicator in unavailable_indicators):
            return ErrorType.TEMPORARY_UNAVAILABLE

        # Recoverable errors (invalid parameter, etc.)
        recoverable_indicators = [
            "invalid parameter",
            "invalid input",
            "validation failed",
            "bad request",
            "400",
        ]
        if any(indicator in error_text for indicator in recoverable_indicators):
            return ErrorType.RECOVERABLE

        # Default to unrecoverable
        return ErrorType.UNRECOVERABLE

    def _make_retry_decision(
        self,
        error_type: ErrorType,
        retry_count: int,
    ) -> RetryDecision:
        """Make decision on whether to retry.

        Args:
            error_type: Type of error
            retry_count: Current retry count

        Returns:
            RetryDecision

        """
        # Check max retries
        if retry_count >= self.max_retries:
            return RetryDecision.ABANDON

        # User cancelled - don't retry
        if error_type == ErrorType.USER_CANCELLED:
            return RetryDecision.ABANDON

        # Unrecoverable error - don't retry
        if error_type == ErrorType.UNRECOVERABLE:
            return RetryDecision.ABANDON

        # Recoverable error - may need clarification
        if error_type == ErrorType.RECOVERABLE:
            return RetryDecision.CLARIFY

        # Transient or temporary unavailable - retry
        if error_type in {ErrorType.TRANSIENT, ErrorType.TEMPORARY_UNAVAILABLE, ErrorType.TIMEOUT}:
            return RetryDecision.RETRY

        # Default to no retry
        return RetryDecision.NO_RETRY

    def _calculate_retry_delay(self, retry_count: int) -> float:
        """Calculate retry delay with exponential backoff.

        Args:
            retry_count: Current retry count

        Returns:
            Delay in seconds (1s, 2s, 4s for retries 0, 1, 2)

        """
        # Exponential backoff: base_delay * 2^retry_count
        return float(self.base_retry_delay * (2**retry_count))

    def _check_abandonment(
        self,
        error_type: ErrorType,
        retry_count: int,
        execution_result: Any,
    ) -> tuple[bool, str | None]:
        """Check if task should be abandoned.

        Args:
            error_type: Type of error
            retry_count: Current retry count
            execution_result: Execution result

        Returns:
            Tuple of (should_abandon, reason)

        """
        # Max retries exceeded
        if retry_count >= self.max_retries:
            return True, f"Max retries ({self.max_retries}) exceeded"

        # Unrecoverable error
        if error_type == ErrorType.UNRECOVERABLE:
            return True, "Unrecoverable error encountered"

        # User cancelled
        if error_type == ErrorType.USER_CANCELLED:
            return True, "User cancelled execution"

        # Timeout exceeded (check if total timeout exceeded)
        if hasattr(execution_result, "execution_time"):
            if execution_result.execution_time > 60.0:  # 60s total timeout
                return True, "Total timeout (60s) exceeded"

        return False, None

    def _generate_clarification_question(
        self,
        issues: list[ValidationIssue],
    ) -> str:
        """Generate clarification question based on validation issues.

        Args:
            issues: List of validation issues

        Returns:
            Clarification question

        """
        if not issues:
            return "Could you provide more information?"

        # Focus on first critical issue
        critical_issues = [issue for issue in issues if issue.severity == "error"]
        if not critical_issues:
            critical_issues = issues

        first_issue = critical_issues[0]

        if first_issue.issue_type == ValidationResult.INCOMPLETE:
            return f"The result is missing {first_issue.field}. Could you provide this information?"
        if first_issue.issue_type == ValidationResult.AMBIGUOUS:
            return f"The {first_issue.field} value is ambiguous. Could you clarify what you mean?"
        if first_issue.issue_type == ValidationResult.UNEXPECTED:
            return f"The {first_issue.field} has an unexpected format. Could you verify the input?"
        return f"There's an issue with {first_issue.field}. Could you check and try again?"

    def track_retry_result(self, error_type: str, success: bool) -> None:
        """Track retry result for pattern analysis.

        Args:
            error_type: Type of error that was retried
            success: Whether retry was successful

        """
        # defaultdict(deque(maxlen=100)) auto-creates and auto-evicts - no manual management needed
        self._retry_stats[error_type].append(success)

    def get_retry_stats(self, error_type: str) -> dict[str, Any]:
        """Get retry statistics for error type.

        Args:
            error_type: Type of error

        Returns:
            Dictionary with retry statistics

        """
        if error_type not in self._retry_stats or not self._retry_stats[error_type]:
            return {
                "total_retries": 0,
                "successful_retries": 0,
                "success_rate": 0.0,
            }

        stats = self._retry_stats[error_type]
        successful = sum(1 for s in stats if s)

        return {
            "total_retries": len(stats),
            "successful_retries": successful,
            "success_rate": successful / len(stats) if stats else 0.0,
        }

    def clear_retry_stats(self, error_type: str | None = None) -> None:
        """Clear retry statistics.

        Args:
            error_type: Error type to clear (clears all if None)

        """
        if error_type is None:
            self._retry_stats.clear()
        elif error_type in self._retry_stats:
            del self._retry_stats[error_type]