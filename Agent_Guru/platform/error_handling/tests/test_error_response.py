"""
Tests for agent_guru.platform.error_handling.error_response
Coverage Target: >80% (enforced by CI/CD)

This module tests the structured error response system including:
- Error response creation and validation
- Error categorization logic
- Remediation step generation
- Exception handling and context tracking
"""

import pytest
import time
from typing import Dict, Any
from hypothesis import given, strategies as st

from Agent_Guru.platform.error_handling.error_response import (
    ErrorResponse,
    ErrorCategory,
    ErrorCode,
    create_error_response,
    generate_remediation_steps,
    categorize_exception
)


class TestErrorResponse:
    """Unit tests for ErrorResponse dataclass."""
    
    def test_error_response_creation(self):
        """Test basic error response creation."""
        error = ErrorResponse(
            error_code="TEST_ERROR",
            message="Test error message",
            category=ErrorCategory.RECOVERABLE,
            context={"key": "value"},
            remediation_steps=["Step 1", "Step 2"]
        )
        
        assert error.error_code == "TEST_ERROR"
        assert error.message == "Test error message"
        assert error.category == ErrorCategory.RECOVERABLE
        assert error.context == {"key": "value"}
        assert error.remediation_steps == ["Step 1", "Step 2"]
        assert error.timestamp > 0
    
    def test_error_response_immutability(self):
        """Test that error response is immutable (frozen)."""
        error = ErrorResponse(
            error_code="TEST_ERROR",
            message="Test message",
            category=ErrorCategory.RECOVERABLE
        )
        
        # Should not be able to modify frozen dataclass
        with pytest.raises(AttributeError):
            error.error_code = "MODIFIED"
    
    def test_is_recoverable(self):
        """Test is_recoverable method."""
        recoverable = ErrorResponse(
            error_code="TEST",
            message="Test",
            category=ErrorCategory.RECOVERABLE
        )
        non_recoverable = ErrorResponse(
            error_code="TEST",
            message="Test",
            category=ErrorCategory.NON_RECOVERABLE
        )
        critical = ErrorResponse(
            error_code="TEST",
            message="Test",
            category=ErrorCategory.CRITICAL
        )
        
        assert recoverable.is_recoverable() is True
        assert non_recoverable.is_recoverable() is False
        assert critical.is_recoverable() is False
    
    def test_is_critical(self):
        """Test is_critical method."""
        recoverable = ErrorResponse(
            error_code="TEST",
            message="Test",
            category=ErrorCategory.RECOVERABLE
        )
        non_recoverable = ErrorResponse(
            error_code="TEST",
            message="Test",
            category=ErrorCategory.NON_RECOVERABLE
        )
        critical = ErrorResponse(
            error_code="TEST",
            message="Test",
            category=ErrorCategory.CRITICAL
        )
        
        assert recoverable.is_critical() is False
        assert non_recoverable.is_critical() is False
        assert critical.is_critical() is True
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        error = ErrorResponse(
            error_code="TEST_ERROR",
            message="Test message",
            category=ErrorCategory.RECOVERABLE,
            context={"key": "value"},
            remediation_steps=["Step 1"],
            exception_type="ValueError",
            exception_message="Invalid value"
        )
        
        error_dict = error.to_dict()
        
        assert error_dict["error_code"] == "TEST_ERROR"
        assert error_dict["message"] == "Test message"
        assert error_dict["category"] == "recoverable"
        assert error_dict["context"] == {"key": "value"}
        assert error_dict["remediation_steps"] == ["Step 1"]
        assert error_dict["exception_type"] == "ValueError"
        assert error_dict["exception_message"] == "Invalid value"
    
    def test_str_representation(self):
        """Test string representation."""
        error = ErrorResponse(
            error_code="TEST_ERROR",
            message="Test message",
            category=ErrorCategory.RECOVERABLE
        )
        
        error_str = str(error)
        assert "RECOVERABLE" in error_str
        assert "TEST_ERROR" in error_str
        assert "Test message" in error_str
    
    def test_default_values(self):
        """Test default values for optional fields."""
        error = ErrorResponse(
            error_code="TEST",
            message="Test",
            category=ErrorCategory.RECOVERABLE
        )
        
        assert error.context == {}
        assert error.remediation_steps == []
        assert error.exception_type is None
        assert error.exception_message is None
        assert error.stack_trace is None
        assert error.metadata == {}


class TestCreateErrorResponse:
    """Unit tests for create_error_response factory function."""
    
    def test_create_without_exception(self):
        """Test creating error response without exception."""
        error = create_error_response(
            error_code="TEST_ERROR",
            message="Test message",
            category=ErrorCategory.RECOVERABLE,
            context={"key": "value"}
        )
        
        assert error.error_code == "TEST_ERROR"
        assert error.message == "Test message"
        assert error.category == ErrorCategory.RECOVERABLE
        assert error.context == {"key": "value"}
        assert len(error.remediation_steps) > 0
        assert error.exception_type is None
    
    def test_create_with_exception(self):
        """Test creating error response with exception."""
        try:
            raise ValueError("Invalid value")
        except ValueError as e:
            error = create_error_response(
                error_code="VALIDATION_ERROR",
                message="Validation failed",
                category=ErrorCategory.NON_RECOVERABLE,
                exception=e
            )
        
        assert error.error_code == "VALIDATION_ERROR"
        assert error.exception_type == "ValueError"
        assert error.exception_message == "Invalid value"
        assert error.stack_trace is not None
        assert "ValueError" in error.stack_trace
    
    def test_create_with_metadata(self):
        """Test creating error response with metadata."""
        error = create_error_response(
            error_code="TEST_ERROR",
            message="Test message",
            category=ErrorCategory.RECOVERABLE,
            metadata={"user_id": "123", "request_id": "abc"}
        )
        
        assert error.metadata == {"user_id": "123", "request_id": "abc"}
    
    def test_automatic_remediation_generation(self):
        """Test that remediation steps are automatically generated."""
        error = create_error_response(
            error_code="NETWORK_TIMEOUT",
            message="Request timed out",
            category=ErrorCategory.RECOVERABLE
        )
        
        assert len(error.remediation_steps) > 0
        assert any("retry" in step.lower() for step in error.remediation_steps)


class TestGenerateRemediationSteps:
    """Unit tests for remediation step generation."""
    
    def test_recoverable_error_remediation(self):
        """Test remediation for recoverable errors."""
        steps = generate_remediation_steps(
            error_code="NETWORK_TIMEOUT",
            category=ErrorCategory.RECOVERABLE,
            exception_type="TimeoutError",
            context={}
        )
        
        assert len(steps) > 0
        assert any("retry" in step.lower() for step in steps)
        assert any("network" in step.lower() for step in steps)
    
    def test_non_recoverable_error_remediation(self):
        """Test remediation for non-recoverable errors."""
        steps = generate_remediation_steps(
            error_code="CONFIG_INVALID",
            category=ErrorCategory.NON_RECOVERABLE,
            exception_type="ValueError",
            context={}
        )
        
        assert len(steps) > 0
        assert any("configuration" in step.lower() or "input" in step.lower() 
                   for step in steps)
    
    def test_critical_error_remediation(self):
        """Test remediation for critical errors."""
        steps = generate_remediation_steps(
            error_code="SYSTEM_OUT_OF_MEMORY",
            category=ErrorCategory.CRITICAL,
            exception_type="MemoryError",
            context={}
        )
        
        assert len(steps) > 0
        assert any("administrator" in step.lower() or "memory" in step.lower() 
                   for step in steps)
    
    def test_file_not_found_remediation(self):
        """Test remediation for file not found errors."""
        steps = generate_remediation_steps(
            error_code="FILE_NOT_FOUND",
            category=ErrorCategory.NON_RECOVERABLE,
            exception_type="FileNotFoundError",
            context={"file_path": "/etc/config.yaml"}
        )
        
        assert len(steps) > 0
        assert any("file" in step.lower() for step in steps)
        assert any("/etc/config.yaml" in step for step in steps)
    
    def test_permission_error_remediation(self):
        """Test remediation for permission errors."""
        steps = generate_remediation_steps(
            error_code="PERMISSION_DENIED",
            category=ErrorCategory.NON_RECOVERABLE,
            exception_type="PermissionError",
            context={}
        )
        
        assert len(steps) > 0
        assert any("permission" in step.lower() for step in steps)
    
    def test_network_error_remediation(self):
        """Test remediation for network errors."""
        steps = generate_remediation_steps(
            error_code="NETWORK_CONNECTION_ERROR",
            category=ErrorCategory.RECOVERABLE,
            exception_type="ConnectionError",
            context={"url": "https://api.example.com"}
        )
        
        assert len(steps) > 0
        assert any("network" in step.lower() for step in steps)
    
    def test_timeout_error_remediation(self):
        """Test remediation for timeout errors."""
        steps = generate_remediation_steps(
            error_code="OPERATION_TIMEOUT",
            category=ErrorCategory.RECOVERABLE,
            exception_type="TimeoutError",
            context={}
        )
        
        assert len(steps) > 0
        assert any("timeout" in step.lower() for step in steps)
    
    def test_validation_error_remediation(self):
        """Test remediation for validation errors."""
        steps = generate_remediation_steps(
            error_code="VALIDATION_ERROR",
            category=ErrorCategory.NON_RECOVERABLE,
            exception_type="ValidationError",
            context={}
        )
        
        assert len(steps) > 0
        assert any("validation" in step.lower() or "input" in step.lower() 
                   for step in steps)
    
    def test_always_has_remediation_steps(self):
        """Test that remediation steps are always generated."""
        steps = generate_remediation_steps(
            error_code="UNKNOWN_ERROR",
            category=ErrorCategory.NON_RECOVERABLE,
            exception_type=None,
            context={}
        )
        
        # Should always have at least one step
        assert len(steps) > 0


class TestCategorizeException:
    """Unit tests for exception categorization."""
    
    def test_categorize_timeout_error(self):
        """Test categorization of timeout errors."""
        category = categorize_exception(TimeoutError("Request timed out"))
        assert category == ErrorCategory.RECOVERABLE
    
    def test_categorize_connection_error(self):
        """Test categorization of connection errors."""
        category = categorize_exception(ConnectionError("Connection failed"))
        assert category == ErrorCategory.RECOVERABLE
    
    def test_categorize_memory_error(self):
        """Test categorization of memory errors."""
        category = categorize_exception(MemoryError("Out of memory"))
        assert category == ErrorCategory.CRITICAL
    
    def test_categorize_value_error(self):
        """Test categorization of value errors."""
        category = categorize_exception(ValueError("Invalid value"))
        assert category == ErrorCategory.NON_RECOVERABLE
    
    def test_categorize_file_not_found(self):
        """Test categorization of file not found errors."""
        category = categorize_exception(FileNotFoundError("File not found"))
        assert category == ErrorCategory.NON_RECOVERABLE
    
    def test_categorize_permission_error(self):
        """Test categorization of permission errors."""
        category = categorize_exception(PermissionError("Permission denied"))
        assert category == ErrorCategory.NON_RECOVERABLE
    
    def test_categorize_system_error(self):
        """Test categorization of system errors."""
        category = categorize_exception(SystemError("System error"))
        assert category == ErrorCategory.CRITICAL
    
    def test_categorize_os_error(self):
        """Test categorization of OS errors."""
        category = categorize_exception(OSError("OS error"))
        assert category == ErrorCategory.CRITICAL
    
    def test_categorize_runtime_error(self):
        """Test categorization of runtime errors."""
        category = categorize_exception(RuntimeError("Runtime error"))
        assert category == ErrorCategory.CRITICAL
    
    def test_categorize_generic_exception(self):
        """Test categorization of generic exceptions."""
        category = categorize_exception(Exception("Generic error"))
        assert category == ErrorCategory.NON_RECOVERABLE


class TestErrorCode:
    """Unit tests for ErrorCode constants."""
    
    def test_error_code_constants(self):
        """Test that error code constants are defined."""
        assert ErrorCode.FILE_NOT_FOUND == "FILE_NOT_FOUND"
        assert ErrorCode.NETWORK_TIMEOUT == "NETWORK_TIMEOUT"
        assert ErrorCode.PERMISSION_DENIED == "PERMISSION_DENIED"
        assert ErrorCode.SYSTEM_OUT_OF_MEMORY == "SYSTEM_OUT_OF_MEMORY"
        assert ErrorCode.OPERATION_FAILED == "OPERATION_FAILED"


class TestErrorResponseProperties:
    """Property-based tests for ErrorResponse."""
    
    @given(
        error_code=st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        message=st.text(min_size=1, max_size=200, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        category=st.sampled_from(list(ErrorCategory))
    )
    def test_error_response_always_valid(
        self,
        error_code: str,
        message: str,
        category: ErrorCategory
    ):
        """Property: ErrorResponse can be created with any valid inputs."""
        error = ErrorResponse(
            error_code=error_code,
            message=message,
            category=category
        )
        
        assert error.error_code == error_code
        assert error.message == message
        assert error.category == category
    
    @given(
        error_code=st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        message=st.text(min_size=1, max_size=200, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        category=st.sampled_from(list(ErrorCategory))
    )
    def test_to_dict_roundtrip(
        self,
        error_code: str,
        message: str,
        category: ErrorCategory
    ):
        """Property: to_dict preserves all information."""
        error = ErrorResponse(
            error_code=error_code,
            message=message,
            category=category
        )
        
        error_dict = error.to_dict()
        
        assert error_dict["error_code"] == error_code
        assert error_dict["message"] == message
        assert error_dict["category"] == category.value
    
    @given(
        category=st.sampled_from(list(ErrorCategory))
    )
    def test_is_recoverable_consistent(self, category: ErrorCategory):
        """Property: is_recoverable is consistent with category."""
        error = ErrorResponse(
            error_code="TEST",
            message="Test",
            category=category
        )
        
        if category == ErrorCategory.RECOVERABLE:
            assert error.is_recoverable() is True
        else:
            assert error.is_recoverable() is False
    
    @given(
        category=st.sampled_from(list(ErrorCategory))
    )
    def test_is_critical_consistent(self, category: ErrorCategory):
        """Property: is_critical is consistent with category."""
        error = ErrorResponse(
            error_code="TEST",
            message="Test",
            category=category
        )
        
        if category == ErrorCategory.CRITICAL:
            assert error.is_critical() is True
        else:
            assert error.is_critical() is False
    
    @given(
        error_code=st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        category=st.sampled_from(list(ErrorCategory))
    )
    def test_remediation_always_generated(
        self,
        error_code: str,
        category: ErrorCategory
    ):
        """Property: Remediation steps are always generated."""
        error = create_error_response(
            error_code=error_code,
            message="Test message",
            category=category
        )
        
        # Should always have at least one remediation step
        assert len(error.remediation_steps) > 0
    
    @given(
        exception_type=st.sampled_from([
            TimeoutError, ConnectionError, MemoryError,
            ValueError, FileNotFoundError, PermissionError,
            SystemError, OSError, RuntimeError, Exception
        ])
    )
    def test_categorize_exception_always_returns_category(
        self,
        exception_type: type
    ):
        """Property: categorize_exception always returns a valid category."""
        exception = exception_type("Test error")
        category = categorize_exception(exception)
        
        assert isinstance(category, ErrorCategory)
        assert category in [
            ErrorCategory.RECOVERABLE,
            ErrorCategory.NON_RECOVERABLE,
            ErrorCategory.CRITICAL
        ]


@pytest.mark.integration
class TestErrorResponseIntegration:
    """Integration tests for error response system."""
    
    def test_complete_error_flow(self):
        """Test complete error creation and handling flow."""
        # Simulate an error scenario
        try:
            raise FileNotFoundError("config.yaml not found")
        except FileNotFoundError as e:
            # Create error response
            error = create_error_response(
                error_code=ErrorCode.FILE_NOT_FOUND,
                message="Configuration file not found",
                category=ErrorCategory.NON_RECOVERABLE,
                context={"file_path": "config.yaml"},
                exception=e,
                metadata={"component": "platform_integration"}
            )
        
        # Verify error response
        assert error.error_code == ErrorCode.FILE_NOT_FOUND
        assert error.category == ErrorCategory.NON_RECOVERABLE
        assert not error.is_recoverable()
        assert not error.is_critical()
        assert error.exception_type == "FileNotFoundError"
        assert len(error.remediation_steps) > 0
        
        # Verify serialization
        error_dict = error.to_dict()
        assert "error_code" in error_dict
        assert "remediation_steps" in error_dict
    
    def test_error_with_retry_strategy(self):
        """Test error response integration with retry strategy."""
        from Agent_Guru.platform.error_handling.retry_strategy import (
            RetryStrategy, RetryConfig
        )
        
        # Create retry strategy
        strategy = RetryStrategy(RetryConfig(max_attempts=3))
        
        # Simulate operation that fails
        def failing_operation():
            raise TimeoutError("Operation timed out")
        
        # Execute with retry
        result = strategy.execute(failing_operation)
        
        # Create error response from retry result
        if not result.success:
            error = create_error_response(
                error_code=ErrorCode.OPERATION_TIMEOUT,
                message=f"Operation failed after {result.attempts} attempts",
                category=ErrorCategory.RECOVERABLE,
                context={
                    "attempts": result.attempts,
                    "total_delay": result.total_delay
                }
            )
            
            assert error.is_recoverable()
            assert error.context["attempts"] == 3
            assert any("retry" in step.lower() for step in error.remediation_steps)
    
    def test_error_with_circuit_breaker(self):
        """Test error response integration with circuit breaker."""
        from Agent_Guru.platform.error_handling.circuit_breaker import (
            CircuitBreaker, CircuitBreakerOpenError
        )
        
        # Create circuit breaker
        breaker = CircuitBreaker(failure_threshold=2)
        
        # Simulate failures to open circuit
        for _ in range(2):
            try:
                breaker.call(lambda: 1 / 0)
            except ZeroDivisionError:
                pass
        
        # Circuit should be open now
        try:
            breaker.call(lambda: "test")
        except CircuitBreakerOpenError as e:
            error = create_error_response(
                error_code="CIRCUIT_BREAKER_OPEN",
                message="Circuit breaker is open",
                category=ErrorCategory.RECOVERABLE,
                exception=e,
                context={"breaker_state": breaker.state.value}
            )
            
            assert error.is_recoverable()
            assert error.exception_type == "CircuitBreakerOpenError"
            assert len(error.remediation_steps) > 0
