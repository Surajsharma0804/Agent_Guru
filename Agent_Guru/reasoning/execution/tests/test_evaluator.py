"""
Tests for execution evaluator.

Coverage Target: >80%
"""


import pytest

from Agent_Guru.reasoning.execution.evaluator import (
    ErrorType,
    EvaluationResult,
    ExecutionEvaluator,
    ResultValidator,
    RetryDecision,
    ValidationIssue,
    ValidationResult,
)


class TestResultValidator:
    """Unit tests for ResultValidator."""

    def test_initialization(self):
        """Test validator initialization."""
        validator = ResultValidator()
        assert validator is not None  # nosec B101
        assert validator._validation_rules == {}  # nosec B101

    def test_validate_none_result(self):
        """Test validation of None result."""
        validator = ResultValidator()
        result = validator.validate(None)

        assert not result.is_valid  # nosec B101
        assert result.validation_result == ValidationResult.INCOMPLETE  # nosec B101
        assert len(result.issues) == 1  # nosec B101
        assert result.issues[0].field == "result_data"  # nosec B101

    def test_validate_valid_result(self):
        """Test validation of valid result."""
        validator = ResultValidator()
        result_data = {"timer_id": "timer_123", "duration": 300}
        schema = {"timer_id": str, "duration": int}

        result = validator.validate(result_data, schema)

        assert result.is_valid  # nosec B101
        assert result.validation_result == ValidationResult.VALID  # nosec B101
        assert len(result.issues) == 0  # nosec B101

    def test_validate_missing_field(self):
        """Test validation with missing required field."""
        validator = ResultValidator()
        result_data = {"timer_id": "timer_123"}
        schema = {"timer_id": str, "duration": int}

        result = validator.validate(result_data, schema)

        assert not result.is_valid  # nosec B101
        assert result.validation_result == ValidationResult.INCOMPLETE  # nosec B101
        assert len(result.issues) == 1  # nosec B101
        assert result.issues[0].field == "duration"  # nosec B101

    def test_validate_wrong_type(self):
        """Test validation with wrong field type."""
        validator = ResultValidator()
        result_data = {"timer_id": "timer_123", "duration": "300"}  # Should be int
        schema = {"timer_id": str, "duration": int}

        result = validator.validate(result_data, schema)

        assert not result.is_valid  # nosec B101
        assert result.validation_result == ValidationResult.INVALID  # nosec B101
        assert len(result.issues) == 1  # nosec B101
        assert result.issues[0].field == "duration"  # nosec B101

    def test_validate_business_rules(self):
        """Test validation with business rules."""
        validator = ResultValidator()
        result_data = {"duration": -5}  # Negative duration
        schema = {"duration": int}
        business_rules = {"duration": lambda x: x > 0}

        result = validator.validate(result_data, schema, business_rules)

        assert not result.is_valid  # nosec B101
        assert len(result.issues) >= 1  # nosec B101
        # Should have business rule violation
        assert any(issue.field == "duration" for issue in result.issues)  # nosec B101

    def test_validate_sanity_negative_duration(self):
        """Test sanity check for negative duration."""
        validator = ResultValidator()
        result_data = {"duration": -10}

        result = validator.validate(result_data)

        # Should have warning about negative duration
        assert any(  # nosec B101
            issue.field == "duration" and "negative" in issue.message.lower()
            for issue in result.issues
        )

    def test_validate_sanity_large_value(self):
        """Test sanity check for unreasonably large value."""
        validator = ResultValidator()
        result_data = {"count": 1e15}  # Unreasonably large

        result = validator.validate(result_data)

        # Should have warning about large value
        assert any(  # nosec B101
            issue.field == "count" and "large" in issue.message.lower() for issue in result.issues
        )

    def test_validate_sanity_empty_string(self):
        """Test sanity check for empty string."""
        validator = ResultValidator()
        result_data = {"name": "   "}  # Empty/whitespace string

        result = validator.validate(result_data)

        # Should have warning about empty string
        assert any(  # nosec B101
            issue.field == "name" and "empty" in issue.message.lower() for issue in result.issues
        )

    def test_validate_non_dict_result(self):
        """Test validation of non-dict result."""
        validator = ResultValidator()
        result_data = "not a dict"
        schema = {"field": str}

        result = validator.validate(result_data, schema)

        assert not result.is_valid  # nosec B101
        assert result.validation_result == ValidationResult.UNEXPECTED  # nosec B101
        assert len(result.issues) == 1  # nosec B101

    def test_add_validation_rule(self):
        """Test adding custom validation rule."""
        validator = ResultValidator()
        validator.add_validation_rule("positive", lambda x: x > 0)

        assert "positive" in validator._validation_rules  # nosec B101

    def test_remove_validation_rule(self):
        """Test removing validation rule."""
        validator = ResultValidator()
        validator.add_validation_rule("positive", lambda x: x > 0)
        validator.remove_validation_rule("positive")

        assert "positive" not in validator._validation_rules  # nosec B101

    def test_validate_with_warnings_only(self):
        """Test validation with only warnings (should be valid)."""
        validator = ResultValidator()
        result_data = {"count": 1e11}  # Large but not error

        result = validator.validate(result_data)

        # Should be valid but with warnings
        assert result.is_valid  # nosec B101
        assert len(result.issues) > 0  # nosec B101
        assert all(issue.severity == "warning" for issue in result.issues)  # nosec B101


class TestExecutionEvaluator:
    """Unit tests for ExecutionEvaluator."""

    def test_initialization(self):
        """Test evaluator initialization."""
        evaluator = ExecutionEvaluator(max_retries=3, base_retry_delay=1.0)

        assert evaluator.max_retries == 3  # nosec B101
        assert evaluator.base_retry_delay == 1.0  # nosec B101
        assert evaluator.validator is not None  # nosec B101

    def test_initialization_invalid_params(self):
        """Test initialization with invalid parameters."""
        with pytest.raises(ValueError):
            ExecutionEvaluator(max_retries=-1)

        with pytest.raises(ValueError):
            ExecutionEvaluator(base_retry_delay=0)

    def test_evaluate_successful_result(self):
        """Test evaluation of successful result."""
        evaluator = ExecutionEvaluator()

        # Mock execution result
        class MockResult:
            success = True
            result_data = {"timer_id": "timer_123", "duration": 300}

        result = MockResult()
        schema = {"timer_id": str, "duration": int}

        evaluation = evaluator.evaluate(result, expected_schema=schema)

        assert evaluation.is_valid  # nosec B101
        assert evaluation.validation_result == ValidationResult.VALID  # nosec B101
        assert evaluation.retry_decision == RetryDecision.NO_RETRY  # nosec B101

    def test_evaluate_failed_result_transient_error(self):
        """Test evaluation of failed result with transient error."""
        evaluator = ExecutionEvaluator()

        # Mock execution result with transient error
        class MockResult:
            success = False
            error = {"error_code": "NETWORK_ERROR", "message": "Connection timeout"}

        result = MockResult()
        evaluation = evaluator.evaluate(result, retry_count=0)

        assert not evaluation.is_valid  # nosec B101
        assert evaluation.retry_decision == RetryDecision.RETRY  # nosec B101
        assert evaluation.retry_delay == 1.0  # First retry  # nosec B101

    def test_evaluate_failed_result_max_retries(self):
        """Test evaluation when max retries exceeded."""
        evaluator = ExecutionEvaluator(max_retries=3)

        # Mock execution result
        class MockResult:
            success = False
            error = {"error_code": "NETWORK_ERROR", "message": "Connection timeout"}

        result = MockResult()
        evaluation = evaluator.evaluate(result, retry_count=3)

        assert not evaluation.is_valid  # nosec B101
        assert evaluation.retry_decision == RetryDecision.ABANDON  # nosec B101
        assert evaluation.should_abandon  # nosec B101
        assert "Max retries" in evaluation.abandonment_reason  # nosec B101

    def test_evaluate_user_cancelled(self):
        """Test evaluation of user cancelled error."""
        evaluator = ExecutionEvaluator()

        # Mock execution result
        class MockResult:
            success = False
            error = {"error_code": "CANCELLED", "message": "User cancelled"}

        result = MockResult()
        evaluation = evaluator.evaluate(result, retry_count=0)

        assert not evaluation.is_valid  # nosec B101
        assert evaluation.retry_decision == RetryDecision.ABANDON  # nosec B101
        assert evaluation.should_abandon  # nosec B101
        assert "cancelled" in evaluation.abandonment_reason.lower()  # nosec B101

    def test_evaluate_unrecoverable_error(self):
        """Test evaluation of unrecoverable error."""
        evaluator = ExecutionEvaluator()

        # Mock execution result
        class MockResult:
            success = False
            error = {"error_code": "FATAL_ERROR", "message": "System failure"}

        result = MockResult()
        evaluation = evaluator.evaluate(result, retry_count=0)

        assert not evaluation.is_valid  # nosec B101
        assert evaluation.retry_decision == RetryDecision.ABANDON  # nosec B101
        assert evaluation.should_abandon  # nosec B101

    def test_evaluate_recoverable_error(self):
        """Test evaluation of recoverable error."""
        evaluator = ExecutionEvaluator()

        # Mock execution result
        class MockResult:
            success = False
            error = {"error_code": "INVALID_PARAMETER", "message": "Invalid input"}

        result = MockResult()
        evaluation = evaluator.evaluate(result, retry_count=0)

        assert not evaluation.is_valid  # nosec B101
        assert evaluation.retry_decision == RetryDecision.CLARIFY  # nosec B101

    def test_evaluate_incomplete_result(self):
        """Test evaluation of incomplete successful result."""
        evaluator = ExecutionEvaluator()

        # Mock execution result with incomplete data
        class MockResult:
            success = True
            result_data = {"timer_id": "timer_123"}  # Missing duration

        result = MockResult()
        schema = {"timer_id": str, "duration": int}

        evaluation = evaluator.evaluate(result, expected_schema=schema)

        assert not evaluation.is_valid  # nosec B101
        assert evaluation.validation_result == ValidationResult.INCOMPLETE  # nosec B101
        assert evaluation.clarification_needed  # nosec B101
        assert evaluation.clarification_question is not None  # nosec B101

    def test_classify_error_transient(self):
        """Test error classification for transient errors."""
        evaluator = ExecutionEvaluator()

        error = {"error_code": "NETWORK_ERROR", "message": "Connection failed"}
        error_type = evaluator._classify_error(error)

        assert error_type == ErrorType.TRANSIENT  # nosec B101

    def test_classify_error_timeout(self):
        """Test error classification for timeout."""
        evaluator = ExecutionEvaluator()

        error = {"error_code": "TIMEOUT", "message": "Operation timed out"}
        error_type = evaluator._classify_error(error)

        assert error_type == ErrorType.TIMEOUT  # nosec B101

    def test_classify_error_unavailable(self):
        """Test error classification for service unavailable."""
        evaluator = ExecutionEvaluator()

        error = {"error_code": "SERVICE_DOWN", "message": "Service temporarily unavailable"}
        error_type = evaluator._classify_error(error)

        assert error_type == ErrorType.TEMPORARY_UNAVAILABLE  # nosec B101

    def test_classify_error_recoverable(self):
        """Test error classification for recoverable errors."""
        evaluator = ExecutionEvaluator()

        error = {"error_code": "BAD_REQUEST", "message": "Invalid parameter"}
        error_type = evaluator._classify_error(error)

        assert error_type == ErrorType.RECOVERABLE  # nosec B101

    def test_classify_error_cancelled(self):
        """Test error classification for user cancellation."""
        evaluator = ExecutionEvaluator()

        error = {"error_code": "CANCELLED", "message": "User cancelled"}
        error_type = evaluator._classify_error(error)

        assert error_type == ErrorType.USER_CANCELLED  # nosec B101

    def test_calculate_retry_delay_exponential_backoff(self):
        """Test exponential backoff calculation."""
        evaluator = ExecutionEvaluator(base_retry_delay=1.0)

        assert evaluator._calculate_retry_delay(0) == 1.0  # 1 * 2^0  # nosec B101
        assert evaluator._calculate_retry_delay(1) == 2.0  # 1 * 2^1  # nosec B101
        assert evaluator._calculate_retry_delay(2) == 4.0  # 1 * 2^2  # nosec B101

    def test_track_retry_result(self):
        """Test tracking retry results."""
        evaluator = ExecutionEvaluator()

        evaluator.track_retry_result("NETWORK_ERROR", True)
        evaluator.track_retry_result("NETWORK_ERROR", False)
        evaluator.track_retry_result("NETWORK_ERROR", True)

        stats = evaluator.get_retry_stats("NETWORK_ERROR")

        assert stats["total_retries"] == 3  # nosec B101
        assert stats["successful_retries"] == 2  # nosec B101
        assert stats["success_rate"] == pytest.approx(2 / 3)  # nosec B101

    def test_get_retry_stats_no_data(self):
        """Test getting retry stats with no data."""
        evaluator = ExecutionEvaluator()

        stats = evaluator.get_retry_stats("UNKNOWN_ERROR")

        assert stats["total_retries"] == 0  # nosec B101
        assert stats["successful_retries"] == 0  # nosec B101
        assert stats["success_rate"] == 0.0  # nosec B101

    def test_clear_retry_stats(self):
        """Test clearing retry statistics."""
        evaluator = ExecutionEvaluator()

        evaluator.track_retry_result("NETWORK_ERROR", True)
        evaluator.clear_retry_stats("NETWORK_ERROR")

        stats = evaluator.get_retry_stats("NETWORK_ERROR")
        assert stats["total_retries"] == 0  # nosec B101

    def test_clear_all_retry_stats(self):
        """Test clearing all retry statistics."""
        evaluator = ExecutionEvaluator()

        evaluator.track_retry_result("NETWORK_ERROR", True)
        evaluator.track_retry_result("TIMEOUT", False)
        evaluator.clear_retry_stats()

        assert evaluator.get_retry_stats("NETWORK_ERROR")["total_retries"] == 0  # nosec B101
        assert evaluator.get_retry_stats("TIMEOUT")["total_retries"] == 0  # nosec B101

    def test_generate_clarification_question_incomplete(self):
        """Test clarification question generation for incomplete result."""
        evaluator = ExecutionEvaluator()

        issues = [
            ValidationIssue(
                issue_type=ValidationResult.INCOMPLETE,
                field="duration",
                message="Missing duration",
                severity="error",
            )
        ]

        question = evaluator._generate_clarification_question(issues)

        assert "duration" in question.lower()  # nosec B101
        assert "missing" in question.lower()  # nosec B101

    def test_generate_clarification_question_ambiguous(self):
        """Test clarification question generation for ambiguous result."""
        evaluator = ExecutionEvaluator()

        issues = [
            ValidationIssue(
                issue_type=ValidationResult.AMBIGUOUS,
                field="location",
                message="Ambiguous location",
                severity="error",
            )
        ]

        question = evaluator._generate_clarification_question(issues)

        assert "location" in question.lower()  # nosec B101
        assert "ambiguous" in question.lower() or "clarify" in question.lower()  # nosec B101

    def test_check_abandonment_timeout(self):
        """Test abandonment check for timeout."""
        evaluator = ExecutionEvaluator()

        # Mock execution result with long execution time
        class MockResult:
            success = False
            error = {"error_code": "TIMEOUT", "message": "Timeout"}
            execution_time = 65.0  # Exceeds 60s limit

        result = MockResult()
        should_abandon, reason = evaluator._check_abandonment(
            ErrorType.TIMEOUT,
            0,
            result,
        )

        assert should_abandon  # nosec B101
        assert "timeout" in reason.lower()  # nosec B101

    def test_evaluate_with_business_rules(self):
        """Test evaluation with business rules."""
        evaluator = ExecutionEvaluator()

        # Mock execution result
        class MockResult:
            success = True
            result_data = {"amount": -100}  # Negative amount

        result = MockResult()
        schema = {"amount": int}
        business_rules = {"amount": lambda x: x >= 0}

        evaluation = evaluator.evaluate(
            result, expected_schema=schema, business_rules=business_rules
        )

        assert not evaluation.is_valid  # nosec B101
        assert len(evaluation.issues) > 0  # nosec B101


class TestValidationIssue:
    """Unit tests for ValidationIssue."""

    def test_creation(self):
        """Test validation issue creation."""
        issue = ValidationIssue(
            issue_type=ValidationResult.INVALID,
            field="test_field",
            message="Test message",
            severity="error",
            details={"key": "value"},
        )

        assert issue.issue_type == ValidationResult.INVALID  # nosec B101
        assert issue.field == "test_field"  # nosec B101
        assert issue.message == "Test message"  # nosec B101
        assert issue.severity == "error"  # nosec B101
        assert issue.details == {"key": "value"}  # nosec B101


class TestEvaluationResult:
    """Unit tests for EvaluationResult."""

    def test_creation(self):
        """Test evaluation result creation."""
        result = EvaluationResult(
            is_valid=True,
            validation_result=ValidationResult.VALID,
        )

        assert result.is_valid  # nosec B101
        assert result.validation_result == ValidationResult.VALID  # nosec B101
        assert result.issues == []  # nosec B101
        assert result.retry_decision == RetryDecision.NO_RETRY  # nosec B101
        assert not result.clarification_needed  # nosec B101
        assert not result.should_abandon  # nosec B101
