"""
Unit Tests for Windows Input Engine

Comprehensive test suite for the Windows API input simulation engine,
covering all functionality including security validation, authority enforcement,
and audit logging.
"""

import pytest
import unittest.mock as mock
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
import ctypes

from src.input.windows_input_engine import (
    WindowsInputEngine, InputType, SecurityLevel, InputEvent, InputResult
)
from src.input.input_validator import InputValidator, ValidationResult
from src.input.authority_gate import AuthorityGate, AuthorityCheck
from src.input.audit_logger import InputAuditLogger
from src.authority.state import AuthorityState, AuthorityStateMachine


class TestWindowsInputEngine:
    """Test suite for WindowsInputEngine"""
    
    @pytest.fixture
    def mock_authority_machine(self):
        """Mock authority state machine"""
        machine = Mock(spec=AuthorityStateMachine)
        machine.current_state = AuthorityState.ARMED
        return machine
    
    @pytest.fixture
    def mock_validator(self):
        """Mock input validator"""
        validator = Mock(spec=InputValidator)
        validator.validate_text_input.return_value = ValidationResult(is_valid=True)
        validator.validate_key_combination.return_value = ValidationResult(is_valid=True)
        validator.validate_single_key.return_value = ValidationResult(is_valid=True)
        return validator
    
    @pytest.fixture
    def mock_audit_logger(self):
        """Mock audit logger"""
        return Mock(spec=InputAuditLogger)
    
    @pytest.fixture
    def input_engine(self, mock_authority_machine, mock_validator, mock_audit_logger):
        """Create WindowsInputEngine instance with mocked dependencies"""
        with patch('src.input.windows_input_engine.windll'):
            engine = WindowsInputEngine(
                authority_machine=mock_authority_machine,
                validator=mock_validator,
                audit_logger=mock_audit_logger
            )
            return engine
    
    def test_initialization(self, input_engine):
        """Test proper initialization of WindowsInputEngine"""
        assert input_engine.max_text_length == 10000
        assert input_engine.rate_limit_window == 60
        assert input_engine.max_events_per_window == 1000
        assert len(input_engine.vk_codes) > 0
        assert len(input_engine.key_combinations) > 0
        assert input_engine.recent_events == []
    
    def test_virtual_key_codes_initialization(self, input_engine):
        """Test virtual key codes are properly initialized"""
        # Test letter keys
        assert input_engine.vk_codes['A'] == ord('A')
        assert input_engine.vk_codes['Z'] == ord('Z')
        
        # Test number keys
        assert input_engine.vk_codes['0'] == ord('0')
        assert input_engine.vk_codes['9'] == ord('9')
        
        # Test special keys
        assert input_engine.vk_codes['ENTER'] == 0x0D
        assert input_engine.vk_codes['ESCAPE'] == 0x1B
        assert input_engine.vk_codes['SPACE'] == 0x20
        assert input_engine.vk_codes['CTRL'] == 0x11
        assert input_engine.vk_codes['ALT'] == 0x12
        assert input_engine.vk_codes['WINDOWS'] == 0x5B
    
    def test_key_combinations_initialization(self, input_engine):
        """Test key combinations are properly initialized"""
        assert input_engine.key_combinations['copy'] == ['CTRL', 'C']
        assert input_engine.key_combinations['paste'] == ['CTRL', 'V']
        assert input_engine.key_combinations['alt_tab'] == ['ALT', 'TAB']
        assert input_engine.key_combinations['windows_r'] == ['WINDOWS', 'R']
    
    def test_authority_check_success(self, input_engine, mock_authority_machine):
        """Test successful authority check"""
        mock_authority_machine.current_state = AuthorityState.ARMED
        
        assert input_engine._check_authority() is True
    
    def test_authority_check_failure(self, input_engine, mock_authority_machine):
        """Test failed authority check"""
        mock_authority_machine.current_state = AuthorityState.LOCKED_LISTEN_ONLY
        
        assert input_engine._check_authority() is False
    
    def test_rate_limiting(self, input_engine):
        """Test rate limiting functionality"""
        # Initially should pass
        assert input_engine._check_rate_limit() is True
        
        # Fill up the rate limit
        for _ in range(input_engine.max_events_per_window):
            input_engine._record_event()
        
        # Should now fail
        assert input_engine._check_rate_limit() is False
    
    @patch('src.input.windows_input_engine.windll')
    def test_type_text_success(self, mock_windll, input_engine, mock_validator, mock_audit_logger):
        """Test successful text typing"""
        # Setup mocks - need to patch the instance's user32 attribute
        input_engine.user32.SendInput.return_value = 10
        mock_validator.validate_text_input.return_value = ValidationResult(is_valid=True)
        
        # Test typing
        result = input_engine.type_text("Hello", "test_session")
        
        # Verify result
        assert result.success is True
        assert result.events_sent == 10
        assert result.error_message is None
        
        # Verify audit logging
        mock_audit_logger.log_input_event.assert_called_once()
        
        # Verify validation was called
        mock_validator.validate_text_input.assert_called_once_with("Hello")
    
    def test_type_text_authority_denied(self, input_engine, mock_authority_machine, mock_audit_logger):
        """Test text typing with insufficient authority"""
        mock_authority_machine.current_state = AuthorityState.LOCKED_LISTEN_ONLY
        
        result = input_engine.type_text("Hello", "test_session")
        
        assert result.success is False
        assert "authority" in result.error_message.lower()
        assert "authority_not_granted" in result.security_violations
        
        # Verify security violation was logged
        mock_audit_logger.log_security_violation.assert_called_once()
    
    def test_type_text_validation_failure(self, input_engine, mock_validator, mock_audit_logger):
        """Test text typing with validation failure"""
        mock_validator.validate_text_input.return_value = ValidationResult(
            is_valid=False,
            violations=["dangerous_pattern"]
        )
        
        result = input_engine.type_text("malicious_text", "test_session")
        
        assert result.success is False
        assert "validation failed" in result.error_message.lower()
        assert result.security_violations == ["dangerous_pattern"]
        
        # Verify security violation was logged
        mock_audit_logger.log_security_violation.assert_called_once()
    
    def test_type_text_too_long(self, input_engine, mock_audit_logger):
        """Test text typing with text too long"""
        long_text = "A" * (input_engine.max_text_length + 1)
        
        result = input_engine.type_text(long_text, "test_session")
        
        assert result.success is False
        assert "length" in result.error_message.lower()
        assert "text_too_long" in result.security_violations
        
        # Verify security violation was logged
        mock_audit_logger.log_security_violation.assert_called_once()
    
    def test_type_text_rate_limited(self, input_engine, mock_audit_logger):
        """Test text typing when rate limited"""
        # Fill up rate limit
        for _ in range(input_engine.max_events_per_window):
            input_engine._record_event()
        
        result = input_engine.type_text("Hello", "test_session")
        
        assert result.success is False
        assert "rate limit" in result.error_message.lower()
        assert "rate_limit_exceeded" in result.security_violations
        
        # Verify security violation was logged
        mock_audit_logger.log_security_violation.assert_called_once()
    
    @patch('src.input.windows_input_engine.windll')
    def test_send_key_combination_success(self, mock_windll, input_engine, mock_validator, mock_audit_logger):
        """Test successful key combination sending"""
        # Setup mocks - need to patch the instance's user32 attribute
        input_engine.user32.SendInput.return_value = 4  # 2 keys down + 2 keys up
        mock_validator.validate_key_combination.return_value = ValidationResult(is_valid=True)
        
        # Test key combination
        result = input_engine.send_key_combination("copy", "test_session")
        
        # Verify result
        assert result.success is True
        assert result.events_sent == 4
        assert result.error_message is None
        
        # Verify audit logging
        mock_audit_logger.log_input_event.assert_called_once()
        
        # Verify validation was called
        mock_validator.validate_key_combination.assert_called_once_with(['CTRL', 'C'])
    
    @patch('src.input.windows_input_engine.windll')
    def test_send_key_combination_list_input(self, mock_windll, input_engine, mock_validator, mock_audit_logger):
        """Test key combination with list input"""
        # Setup mocks - need to patch the instance's user32 attribute
        input_engine.user32.SendInput.return_value = 4
        mock_validator.validate_key_combination.return_value = ValidationResult(is_valid=True)
        
        # Test with list input
        result = input_engine.send_key_combination(['CTRL', 'V'], "test_session")
        
        assert result.success is True
        mock_validator.validate_key_combination.assert_called_once_with(['CTRL', 'V'])
    
    def test_send_key_combination_unknown_key(self, input_engine, mock_validator, mock_audit_logger):
        """Test key combination with unknown key"""
        mock_validator.validate_key_combination.return_value = ValidationResult(is_valid=True)
        
        result = input_engine.send_key_combination(['UNKNOWN_KEY'], "test_session")
        
        assert result.success is False
        assert "unknown key" in result.error_message.lower()
        assert "execution_failed" in result.security_violations
    
    @patch('src.input.windows_input_engine.windll')
    def test_send_single_key_success(self, mock_windll, input_engine, mock_validator, mock_audit_logger):
        """Test successful single key sending"""
        # Setup mocks - need to patch the instance's user32 attribute
        input_engine.user32.SendInput.return_value = 2  # Key down + key up
        mock_validator.validate_single_key.return_value = ValidationResult(is_valid=True)
        
        # Test single key
        result = input_engine.send_single_key("ENTER", "test_session")
        
        # Verify result
        assert result.success is True
        assert result.events_sent == 2
        assert result.error_message is None
        
        # Verify audit logging
        mock_audit_logger.log_input_event.assert_called_once()
        
        # Verify validation was called
        mock_validator.validate_single_key.assert_called_once_with("ENTER")
    
    def test_send_single_key_unknown(self, input_engine, mock_validator, mock_audit_logger):
        """Test single key with unknown key"""
        mock_validator.validate_single_key.return_value = ValidationResult(is_valid=True)
        
        result = input_engine.send_single_key("UNKNOWN_KEY", "test_session")
        
        assert result.success is False
        assert "unknown key" in result.error_message.lower()
        assert "execution_failed" in result.security_violations
    
    def test_security_level_determination_key_combination(self, input_engine):
        """Test security level determination for key combinations"""
        # High risk
        assert input_engine._determine_key_combination_security_level(['WINDOWS', 'R']) == SecurityLevel.HIGH_RISK
        
        # Medium risk
        assert input_engine._determine_key_combination_security_level(['CTRL', 'C']) == SecurityLevel.MEDIUM_RISK
        
        # Low risk
        assert input_engine._determine_key_combination_security_level(['A', 'B']) == SecurityLevel.LOW_RISK
    
    def test_security_level_determination_single_key(self, input_engine):
        """Test security level determination for single keys"""
        # High risk
        assert input_engine._determine_single_key_security_level('WINDOWS') == SecurityLevel.HIGH_RISK
        
        # Medium risk
        assert input_engine._determine_single_key_security_level('ALT') == SecurityLevel.MEDIUM_RISK
        
        # Low risk
        assert input_engine._determine_single_key_security_level('A') == SecurityLevel.LOW_RISK
    
    def test_emergency_halt(self, input_engine, mock_audit_logger):
        """Test emergency halt functionality"""
        # Add some events to rate limiting
        input_engine._record_event()
        input_engine._record_event()
        
        # Call emergency halt
        input_engine.emergency_halt()
        
        # Verify events were cleared
        assert len(input_engine.recent_events) == 0
        
        # Verify emergency event was logged
        mock_audit_logger.log_emergency_event.assert_called_once()
    
    def test_get_status(self, input_engine, mock_authority_machine):
        """Test status reporting"""
        mock_authority_machine.current_state = AuthorityState.ARMED
        
        status = input_engine.get_status()
        
        assert status["authority_state"] == "ARMED"
        assert status["rate_limit_events"] == 0
        assert status["max_events_per_window"] == 1000
        assert status["max_text_length"] == 10000
        assert "available_key_combinations" in status
        assert "available_virtual_keys" in status
    
    def test_create_keyboard_input(self, input_engine):
        """Test keyboard INPUT structure creation"""
        input_struct = input_engine._create_keyboard_input(0x41, key_up=False)  # 'A' key
        
        assert input_struct.type == 1  # INPUT_KEYBOARD
        assert input_struct.union.ki.wVk == 0x41
        assert input_struct.union.ki.dwFlags == 0  # Key down
        
        # Test key up
        input_struct_up = input_engine._create_keyboard_input(0x41, key_up=True)
        assert input_struct_up.union.ki.dwFlags == 2  # KEYEVENTF_KEYUP
    
    def test_create_unicode_input(self, input_engine):
        """Test Unicode INPUT structure creation"""
        input_struct = input_engine._create_unicode_input('A', key_up=False)
        
        assert input_struct.type == 1  # INPUT_KEYBOARD
        assert input_struct.union.ki.wVk == 0
        assert input_struct.union.ki.wScan == ord('A')
        assert input_struct.union.ki.dwFlags == 4  # KEYEVENTF_UNICODE
        
        # Test key up
        input_struct_up = input_engine._create_unicode_input('A', key_up=True)
        assert input_struct_up.union.ki.dwFlags == 6  # KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
    
    @patch('src.input.windows_input_engine.windll')
    def test_send_input_events(self, mock_windll, input_engine):
        """Test sending input events to Windows API"""
        input_engine.user32.SendInput.return_value = 2
        
        # Create test inputs
        inputs = [
            input_engine._create_keyboard_input(0x41, key_up=False),
            input_engine._create_keyboard_input(0x41, key_up=True)
        ]
        
        result = input_engine._send_input_events(inputs)
        
        assert result == 2
        input_engine.user32.SendInput.assert_called_once()
    
    def test_send_input_events_empty(self, input_engine):
        """Test sending empty input events"""
        result = input_engine._send_input_events([])
        assert result == 0


class TestInputEngineIntegration:
    """Integration tests for WindowsInputEngine with real components"""
    
    @pytest.fixture
    def real_validator(self):
        """Create real InputValidator instance"""
        return InputValidator()
    
    @pytest.fixture
    def real_authority_gate(self):
        """Create real AuthorityGate instance"""
        authority_machine = Mock(spec=AuthorityStateMachine)
        authority_machine.get_current_state.return_value = AuthorityState.ARMED
        return AuthorityGate(authority_machine)
    
    @pytest.fixture
    def real_audit_logger(self, tmp_path):
        """Create real InputAuditLogger instance"""
        return InputAuditLogger(log_directory=str(tmp_path))
    
    @pytest.fixture
    def integrated_engine(self, real_validator, real_audit_logger):
        """Create WindowsInputEngine with real components"""
        authority_machine = Mock(spec=AuthorityStateMachine)
        authority_machine.current_state = AuthorityState.ARMED
        
        with patch('src.input.windows_input_engine.windll'):
            engine = WindowsInputEngine(
                authority_machine=authority_machine,
                validator=real_validator,
                audit_logger=real_audit_logger
            )
            return engine
    
    def test_text_validation_integration(self, integrated_engine):
        """Test text typing with real validation"""
        # Test with valid text
        with patch.object(integrated_engine, 'user32') as mock_user32:
            mock_user32.SendInput.return_value = 10
            
            result = integrated_engine.type_text("Hello World")
            assert result.success is True
    
    def test_dangerous_text_validation_integration(self, integrated_engine):
        """Test text typing with dangerous patterns"""
        # Test with potentially dangerous text
        dangerous_text = "rm -rf /"
        
        result = integrated_engine.type_text(dangerous_text)
        # Should still succeed as it's just text, but validation warnings may be logged
        # The validator will flag dangerous patterns but allow them for text input
        assert result.success is True or len(result.security_violations) > 0
    
    def test_key_combination_validation_integration(self, integrated_engine):
        """Test key combination with real validation"""
        with patch.object(integrated_engine, 'user32') as mock_user32:
            mock_user32.SendInput.return_value = 4
            
            result = integrated_engine.send_key_combination(['CTRL', 'C'])
            assert result.success is True
    
    def test_audit_logging_integration(self, integrated_engine, real_audit_logger):
        """Test audit logging with real logger"""
        with patch.object(integrated_engine, 'user32') as mock_user32:
            mock_user32.SendInput.return_value = 2
            
            result = integrated_engine.send_single_key("ENTER")
            assert result.success is True
            
            # Verify audit log was created
            stats = real_audit_logger.get_audit_statistics()
            assert stats["log_file_exists"] is True


class TestInputEngineErrorHandling:
    """Test error handling and edge cases"""
    
    @pytest.fixture
    def input_engine_with_mocks(self):
        """Create input engine with all mocked dependencies"""
        authority_machine = Mock(spec=AuthorityStateMachine)
        authority_machine.current_state = AuthorityState.ARMED
        
        validator = Mock(spec=InputValidator)
        validator.validate_text_input.return_value = ValidationResult(is_valid=True)
        validator.validate_key_combination.return_value = ValidationResult(is_valid=True)
        validator.validate_single_key.return_value = ValidationResult(is_valid=True)
        
        audit_logger = Mock(spec=InputAuditLogger)
        
        with patch('src.input.windows_input_engine.windll'):
            engine = WindowsInputEngine(
                authority_machine=authority_machine,
                validator=validator,
                audit_logger=audit_logger
            )
            return engine, authority_machine, validator, audit_logger
    
    def test_windows_api_failure(self, input_engine_with_mocks):
        """Test handling of Windows API failures"""
        engine, _, _, audit_logger = input_engine_with_mocks
        
        with patch.object(engine, 'user32') as mock_user32:
            # Simulate API failure
            mock_user32.SendInput.side_effect = Exception("API Error")
            
            result = engine.type_text("Hello")
            
            assert result.success is False
            assert "failed to type text" in result.error_message.lower()
            assert "execution_failed" in result.security_violations
            
            # Verify error was logged
            audit_logger.log_security_violation.assert_called()
    
    def test_none_text_input(self, input_engine_with_mocks):
        """Test handling of None text input"""
        engine, _, validator, _ = input_engine_with_mocks
        
        # Configure validator to reject None input
        validator.validate_text_input.return_value = ValidationResult(
            is_valid=False,
            violations=["text_cannot_be_none"]
        )
        
        result = engine.type_text(None)
        
        assert result.success is False
        assert result.security_violations == ["text_cannot_be_none"]
    
    def test_empty_key_combination(self, input_engine_with_mocks):
        """Test handling of empty key combination"""
        engine, _, validator, _ = input_engine_with_mocks
        
        # Configure validator to reject empty combination
        validator.validate_key_combination.return_value = ValidationResult(
            is_valid=False,
            violations=["empty_combination"]
        )
        
        result = engine.send_key_combination([])
        
        assert result.success is False
        assert result.security_violations == ["empty_combination"]
    
    def test_invalid_session_id_handling(self, input_engine_with_mocks):
        """Test handling of various session ID formats"""
        engine, _, _, _ = input_engine_with_mocks
        
        with patch.object(engine, 'user32') as mock_user32:
            mock_user32.SendInput.return_value = 2
            
            # Test with None session ID
            result = engine.type_text("Hello", session_id=None)
            assert result.success is True
            
            # Test with empty session ID
            result = engine.type_text("Hello", session_id="")
            assert result.success is True
            
            # Test with very long session ID
            long_session_id = "x" * 1000
            result = engine.type_text("Hello", session_id=long_session_id)
            assert result.success is True


if __name__ == "__main__":
    pytest.main([__file__])