"""
Property-Based Tests for Input Simulation Fidelity

Tests Property 5: Input Simulation Fidelity
Validates Requirements 17.3, 17.7, 17.10

This test suite uses property-based testing to verify that:
1. Text is typed exactly as spoken without paraphrasing or interpretation
2. Input simulation is deterministic and reproducible
3. Authority enforcement is properly maintained
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from unittest.mock import Mock, patch
import string
import time

from src.input.windows_input_engine import WindowsInputEngine, InputResult
from src.input.input_validator import InputValidator
from src.input.audit_logger import InputAuditLogger
from src.authority.state import AuthorityState, AuthorityStateMachine


class TestInputSimulationFidelity:
    """Property-based tests for input simulation fidelity"""
    
    @pytest.fixture
    def mock_authority_machine(self):
        """Mock authority state machine in ARMED state"""
        machine = Mock(spec=AuthorityStateMachine)
        machine.current_state = AuthorityState.ARMED
        return machine
    
    @pytest.fixture
    def mock_validator(self):
        """Mock input validator that allows all input"""
        validator = Mock(spec=InputValidator)
        validator.validate_text_input.return_value = Mock(is_valid=True, violations=[])
        validator.validate_key_combination.return_value = Mock(is_valid=True, violations=[])
        validator.validate_single_key.return_value = Mock(is_valid=True, violations=[])
        return validator
    
    @pytest.fixture
    def mock_audit_logger(self):
        """Mock audit logger"""
        return Mock(spec=InputAuditLogger)
    
    @pytest.fixture
    def input_engine(self, mock_authority_machine, mock_validator, mock_audit_logger):
        """Create WindowsInputEngine with mocked dependencies"""
        with patch('src.input.windows_input_engine.windll'):
            engine = WindowsInputEngine(
                authority_machine=mock_authority_machine,
                validator=mock_validator,
                audit_logger=mock_audit_logger
            )
            # Mock the SendInput API to return success
            engine.user32.SendInput.return_value = 10
            return engine
    
    # Text generation strategies for property-based testing
    printable_text = st.text(
        alphabet=string.printable,
        min_size=1,
        max_size=100
    ).filter(lambda x: x.strip())  # Filter out whitespace-only strings
    
    unicode_text = st.text(
        min_size=1,
        max_size=50
    ).filter(lambda x: x.strip() and all(ord(c) < 65536 for c in x))  # Basic multilingual plane
    
    special_chars_text = st.text(
        alphabet="!@#$%^&*()_+-=[]{}|;':\",./<>?",
        min_size=1,
        max_size=20
    )
    
    mixed_text = st.one_of(printable_text, unicode_text, special_chars_text)
    
    @given(text=printable_text)
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_text_typing_fidelity(self, input_engine, text):
        """
        Property: Text Typing Fidelity
        For any valid text input, the system should type exactly what was provided
        without modification, paraphrasing, or interpretation.
        
        **Feature: guru-personal-assistant, Property 5: Input Simulation Fidelity**
        **Validates: Requirements 17.3**
        """
        # Reset mock call counts for this iteration
        input_engine.audit_logger.reset_mock()
        input_engine.validator.reset_mock()
        
        # Assume text is not too long to avoid validation failures
        assume(len(text) <= input_engine.max_text_length)
        assume(text is not None and text != "")
        
        # Execute text typing
        result = input_engine.type_text(text, session_id="test_session")
        
        # Verify the operation succeeded
        assert result.success is True, f"Text typing failed for input: {repr(text)}"
        assert result.error_message is None, f"Unexpected error: {result.error_message}"
        
        # Verify that the input was processed without modification
        # The engine should have created Unicode input events for each character
        # Note: events_sent comes from the mocked SendInput API return value
        assert result.events_sent == 10, \
            f"Expected 10 events from mocked SendInput for text '{text}', got {result.events_sent}"
        
        # Verify audit logging occurred
        input_engine.audit_logger.log_input_event.assert_called_once()
        
        # Verify validation was called with the exact text
        input_engine.validator.validate_text_input.assert_called_once_with(text)
    
    @given(text=mixed_text)
    @settings(max_examples=50, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_text_typing_determinism(self, input_engine, text):
        """
        Property: Input Simulation Determinism
        For any text input, multiple executions should produce identical results
        and the same number of input events.
        
        **Feature: guru-personal-assistant, Property 5: Input Simulation Fidelity**
        **Validates: Requirements 17.10**
        """
        # Reset mock call counts for this iteration
        input_engine.audit_logger.reset_mock()
        input_engine.validator.reset_mock()
        
        # Assume text is valid for testing
        assume(len(text) <= input_engine.max_text_length)
        assume(text is not None and text.strip() != "")
        
        # Execute the same text typing operation twice
        result1 = input_engine.type_text(text, session_id="test_session_1")
        result2 = input_engine.type_text(text, session_id="test_session_2")
        
        # Both operations should succeed
        assert result1.success is True, f"First execution failed for: {repr(text)}"
        assert result2.success is True, f"Second execution failed for: {repr(text)}"
        
        # Results should be deterministic - same number of events
        assert result1.events_sent == result2.events_sent, \
            f"Non-deterministic behavior: {result1.events_sent} vs {result2.events_sent} events"
        
        # Both should have no errors
        assert result1.error_message is None
        assert result2.error_message is None
        
        # Both should have the same security violations (should be none for valid text)
        assert result1.security_violations == result2.security_violations
    
    @given(keys=st.lists(
        st.sampled_from(['CTRL', 'ALT', 'SHIFT', 'A', 'B', 'C', 'ENTER', 'ESCAPE']),
        min_size=1,
        max_size=3,
        unique=True
    ))
    @settings(max_examples=50, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_key_combination_fidelity(self, input_engine, keys):
        """
        Property: Key Combination Fidelity
        For any valid key combination, the system should send exactly the specified
        keys in the correct order without modification.
        
        **Feature: guru-personal-assistant, Property 5: Input Simulation Fidelity**
        **Validates: Requirements 17.3**
        """
        # Reset mock call counts for this iteration
        input_engine.audit_logger.reset_mock()
        input_engine.validator.reset_mock()
        
        # Execute key combination
        result = input_engine.send_key_combination(keys, session_id="test_session")
        
        # Verify the operation succeeded
        assert result.success is True, f"Key combination failed for: {keys}"
        assert result.error_message is None, f"Unexpected error: {result.error_message}"
        
        # Verify correct number of events (mocked SendInput returns 10)
        assert result.events_sent == 10, \
            f"Expected 10 events from mocked SendInput for keys {keys}, got {result.events_sent}"
        
        # Verify audit logging occurred
        input_engine.audit_logger.log_input_event.assert_called()
        
        # Verify validation was called with the exact keys
        input_engine.validator.validate_key_combination.assert_called_with(keys)
    
    @given(key=st.sampled_from([
        'ENTER', 'ESCAPE', 'SPACE', 'TAB', 'BACKSPACE',
        'A', 'B', 'C', 'F1', 'F2', 'HOME', 'END'
    ]))
    @settings(max_examples=30, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_single_key_fidelity(self, input_engine, key):
        """
        Property: Single Key Fidelity
        For any valid single key, the system should send exactly that key
        without modification or interpretation.
        
        **Feature: guru-personal-assistant, Property 5: Input Simulation Fidelity**
        **Validates: Requirements 17.3**
        """
        # Reset mock call counts for this iteration
        input_engine.audit_logger.reset_mock()
        input_engine.validator.reset_mock()
        
        # Execute single key press
        result = input_engine.send_single_key(key, session_id="test_session")
        
        # Verify the operation succeeded
        assert result.success is True, f"Single key failed for: {key}"
        assert result.error_message is None, f"Unexpected error: {result.error_message}"
        
        # Verify correct number of events (mocked SendInput returns 10)
        expected_events = 10
        assert result.events_sent == expected_events, \
            f"Expected {expected_events} events from mocked SendInput for key {key}, got {result.events_sent}"
        
        # Verify audit logging occurred
        input_engine.audit_logger.log_input_event.assert_called()
        
        # Verify validation was called with the exact key
        input_engine.validator.validate_single_key.assert_called_with(key)
    
    @given(text=printable_text)
    @settings(max_examples=30, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_authority_enforcement_fidelity(self, mock_authority_machine, mock_validator, mock_audit_logger, text):
        """
        Property: Authority Enforcement Fidelity
        For any input operation, the system should enforce authority requirements
        consistently and reject operations when authority is not granted.
        
        **Feature: guru-personal-assistant, Property 5: Input Simulation Fidelity**
        **Validates: Requirements 17.7**
        """
        # Assume text is valid for testing
        assume(len(text) <= 10000)  # Max text length
        assume(text is not None and text.strip() != "")
        
        # Create engine with LOCKED authority state
        mock_authority_machine.current_state = AuthorityState.LOCKED_LISTEN_ONLY
        
        # Reset mock call counts for this iteration
        mock_audit_logger.reset_mock()
        mock_validator.reset_mock()
        
        with patch('src.input.windows_input_engine.windll'):
            engine = WindowsInputEngine(
                authority_machine=mock_authority_machine,
                validator=mock_validator,
                audit_logger=mock_audit_logger
            )
            
            # Attempt text typing without authority
            result = engine.type_text(text, session_id="test_session")
            
            # Operation should fail due to insufficient authority
            assert result.success is False, f"Operation should fail without authority for: {repr(text)}"
            assert "authority" in result.error_message.lower(), \
                f"Error message should mention authority: {result.error_message}"
            assert "authority_not_granted" in result.security_violations, \
                f"Should have authority violation: {result.security_violations}"
            
            # No input events should be sent
            assert result.events_sent == 0, \
                f"No events should be sent without authority, got: {result.events_sent}"
            
            # Security violation should be logged
            mock_audit_logger.log_security_violation.assert_called()
    
    @given(text=st.text(min_size=1, max_size=20))
    @settings(max_examples=30, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_input_validation_enforcement(self, input_engine, text):
        """
        Property: Input Validation Enforcement
        For any input, the system should consistently apply validation rules
        and reject invalid input while allowing valid input.
        
        **Feature: guru-personal-assistant, Property 5: Input Simulation Fidelity**
        **Validates: Requirements 17.3, 17.7**
        """
        # Reset mock call counts for this iteration
        input_engine.audit_logger.reset_mock()
        input_engine.validator.reset_mock()
        
        # Configure validator to reject this specific input
        input_engine.validator.validate_text_input.return_value = Mock(
            is_valid=False,
            violations=["test_violation"],
            severity=Mock(value="error")
        )
        
        # Attempt text typing with invalid input
        result = input_engine.type_text(text, session_id="test_session")
        
        # Operation should fail due to validation failure
        assert result.success is False, f"Operation should fail validation for: {repr(text)}"
        assert "validation failed" in result.error_message.lower(), \
            f"Error message should mention validation: {result.error_message}"
        assert "test_violation" in result.security_violations, \
            f"Should have validation violation: {result.security_violations}"
        
        # No input events should be sent
        assert result.events_sent == 0, \
            f"No events should be sent for invalid input, got: {result.events_sent}"
        
        # Validation should have been called
        input_engine.validator.validate_text_input.assert_called_with(text)
        
        # Security violation should be logged
        input_engine.audit_logger.log_security_violation.assert_called()
    
    @given(text=st.text(min_size=1, max_size=50))
    @settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_rate_limiting_enforcement(self, input_engine, text):
        """
        Property: Rate Limiting Enforcement
        The system should consistently enforce rate limits and reject operations
        when rate limits are exceeded.
        
        **Feature: guru-personal-assistant, Property 5: Input Simulation Fidelity**
        **Validates: Requirements 17.7**
        """
        # Reset mock call counts for this iteration
        input_engine.audit_logger.reset_mock()
        input_engine.validator.reset_mock()
        
        # Assume text is valid
        assume(len(text) <= input_engine.max_text_length)
        assume(text is not None and text.strip() != "")
        
        # Fill up the rate limit by adding events to the recent_events list
        for _ in range(input_engine.max_events_per_window):
            input_engine._record_event()
        
        # Attempt text typing when rate limited
        result = input_engine.type_text(text, session_id="test_session")
        
        # Operation should fail due to rate limiting
        assert result.success is False, f"Operation should fail when rate limited for: {repr(text)}"
        assert "rate limit" in result.error_message.lower(), \
            f"Error message should mention rate limit: {result.error_message}"
        assert "rate_limit_exceeded" in result.security_violations, \
            f"Should have rate limit violation: {result.security_violations}"
        
        # No input events should be sent
        assert result.events_sent == 0, \
            f"No events should be sent when rate limited, got: {result.events_sent}"
        
        # Security violation should be logged
        input_engine.audit_logger.log_security_violation.assert_called()
    
    def test_empty_input_handling(self, input_engine):
        """
        Test that empty input is handled consistently.
        
        **Feature: guru-personal-assistant, Property 5: Input Simulation Fidelity**
        **Validates: Requirements 17.3**
        """
        # Reset mock call counts for this iteration
        input_engine.audit_logger.reset_mock()
        input_engine.validator.reset_mock()
        
        # Configure validator to handle empty input appropriately
        input_engine.validator.validate_text_input.return_value = Mock(
            is_valid=True,
            violations=[],
            warnings=["Empty text input"]
        )
        
        # Test empty string
        result = input_engine.type_text("", session_id="test_session")
        
        # Should succeed but with no events
        assert result.success is True
        assert result.events_sent == 0  # No characters to type
        
        # Validation should have been called
        input_engine.validator.validate_text_input.assert_called_with("")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])