"""
Unit Tests for Input Validator

Comprehensive test suite for input validation and sanitization,
covering security validation, dangerous pattern detection, and
input sanitization functionality.
"""

import pytest
import re

from src.input.input_validator import (
    InputValidator, ValidationResult, ValidationSeverity
)


class TestInputValidator:
    """Test suite for InputValidator"""
    
    @pytest.fixture
    def validator(self):
        """Create InputValidator instance"""
        return InputValidator()
    
    def test_initialization(self, validator):
        """Test proper initialization of InputValidator"""
        assert validator.max_text_length == 10000
        assert validator.max_key_combination_length == 10
        assert validator.max_single_key_length == 50
        assert len(validator.dangerous_patterns) > 0
        assert len(validator.allowed_text_chars) > 0
        assert len(validator.dangerous_key_combinations) > 0
        assert len(validator.system_keys) > 0
    
    def test_allowed_text_chars_initialization(self, validator):
        """Test allowed text characters are properly initialized"""
        # Test printable ASCII
        assert 'A' in validator.allowed_text_chars
        assert 'z' in validator.allowed_text_chars
        assert '0' in validator.allowed_text_chars
        assert '9' in validator.allowed_text_chars
        assert ' ' in validator.allowed_text_chars
        assert '!' in validator.allowed_text_chars
        
        # Test essential whitespace
        assert '\t' in validator.allowed_text_chars
        assert '\n' in validator.allowed_text_chars
        assert '\r' in validator.allowed_text_chars
        
        # Test control characters are not allowed
        assert '\x00' not in validator.allowed_text_chars
        assert '\x01' not in validator.allowed_text_chars
    
    def test_dangerous_patterns_initialization(self, validator):
        """Test dangerous patterns are properly initialized"""
        patterns = validator.dangerous_patterns
        
        # Test that we have various types of dangerous patterns
        assert len(patterns) > 5
        
        # Test some patterns work
        command_injection_found = False
        for pattern in patterns:
            if pattern.search("test;rm -rf"):
                command_injection_found = True
                break
        assert command_injection_found
    
    def test_validate_text_input_valid(self, validator):
        """Test validation of valid text input"""
        result = validator.validate_text_input("Hello World!")
        assert result.is_valid is True
        assert len(result.violations) == 0
        assert result.severity == ValidationSeverity.INFO
    
    def test_validate_text_input_empty(self, validator):
        """Test validation of empty text input"""
        result = validator.validate_text_input("")
        assert result.is_valid is True  # Empty is allowed
        assert "Empty text input" in result.warnings
    
    def test_validate_text_input_none(self, validator):
        """Test validation of None text input"""
        result = validator.validate_text_input(None)
        assert result.is_valid is False
        assert "Text input cannot be None" in result.violations
        assert result.severity == ValidationSeverity.ERROR
    
    def test_validate_text_input_too_long(self, validator):
        """Test validation of text that's too long"""
        long_text = "A" * (validator.max_text_length + 1)
        result = validator.validate_text_input(long_text)
        assert result.is_valid is False
        assert any("exceeds maximum" in violation for violation in result.violations)
        assert result.severity == ValidationSeverity.ERROR
    
    def test_validate_text_input_dangerous_patterns(self, validator):
        """Test validation of text with dangerous patterns"""
        dangerous_texts = [
            "test;rm -rf /",
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "../../../etc/passwd",
            "test\x00null"
        ]
        
        for dangerous_text in dangerous_texts:
            result = validator.validate_text_input(dangerous_text)
            assert result.is_valid is False or result.severity == ValidationSeverity.CRITICAL
            assert len(result.violations) > 0
    
    def test_validate_key_combination_valid(self, validator):
        """Test validation of valid key combinations"""
        valid_combinations = [
            ['CTRL', 'C'],
            ['ALT', 'TAB'],
            ['WINDOWS', 'R'],
            ['CTRL', 'SHIFT', 'ESCAPE']
        ]
        
        for combination in valid_combinations:
            result = validator.validate_key_combination(combination)
            assert result.is_valid is True
    
    def test_validate_key_combination_empty(self, validator):
        """Test validation of empty key combination"""
        result = validator.validate_key_combination([])
        assert result.is_valid is False
        assert "Key combination cannot be empty" in result.violations
        assert result.severity == ValidationSeverity.ERROR
    
    def test_validate_key_combination_too_long(self, validator):
        """Test validation of key combination that's too long"""
        long_combination = ['CTRL'] * (validator.max_key_combination_length + 1)
        result = validator.validate_key_combination(long_combination)
        assert result.is_valid is False
        assert any("exceeds maximum" in violation for violation in result.violations)
        assert result.severity == ValidationSeverity.ERROR
    
    def test_validate_key_combination_dangerous(self, validator):
        """Test validation of dangerous key combinations"""
        dangerous_combinations = [
            ['ALT', 'F4'],
            ['CTRL', 'ALT', 'DELETE'],
            ['CTRL', 'SHIFT', 'ESCAPE']
        ]
        
        for combination in dangerous_combinations:
            result = validator.validate_key_combination(combination)
            # Should be valid but with warnings
            assert result.is_valid is True
            assert len(result.warnings) > 0 or result.severity == ValidationSeverity.WARNING
    
    def test_validate_key_combination_duplicates(self, validator):
        """Test validation of key combination with duplicates"""
        result = validator.validate_key_combination(['CTRL', 'CTRL', 'C'])
        assert result.is_valid is False or result.severity == ValidationSeverity.WARNING
        assert any("duplicate" in violation.lower() for violation in result.violations)
    
    def test_validate_single_key_valid(self, validator):
        """Test validation of valid single keys"""
        valid_keys = ['ENTER', 'ESCAPE', 'A', 'F1', 'SPACE']
        
        for key in valid_keys:
            result = validator.validate_single_key(key)
            assert result.is_valid is True
    
    def test_validate_single_key_empty(self, validator):
        """Test validation of empty single key"""
        result = validator.validate_single_key("")
        assert result.is_valid is False
        assert "Key cannot be empty" in result.violations
        assert result.severity == ValidationSeverity.ERROR
    
    def test_validate_single_key_none(self, validator):
        """Test validation of None single key"""
        result = validator.validate_single_key(None)
        assert result.is_valid is False
        assert "Key cannot be empty" in result.violations
        assert result.severity == ValidationSeverity.ERROR
    
    def test_validate_single_key_too_long(self, validator):
        """Test validation of single key that's too long"""
        long_key = "A" * (validator.max_single_key_length + 1)
        result = validator.validate_single_key(long_key)
        assert result.is_valid is False
        assert any("too long" in violation for violation in result.violations)
        assert result.severity == ValidationSeverity.ERROR
    
    def test_validate_single_key_dangerous(self, validator):
        """Test validation of dangerous single keys"""
        dangerous_keys = ['DELETE', 'F4', 'WINDOWS']
        
        for key in dangerous_keys:
            result = validator.validate_single_key(key)
            # Should be valid but with warnings
            assert result.is_valid is True
            assert len(result.warnings) > 0 or result.severity == ValidationSeverity.WARNING
    
    def test_sanitize_text_input_basic(self, validator):
        """Test basic text sanitization"""
        text = "Hello World!"
        sanitized = validator.sanitize_text_input(text)
        assert sanitized == text
    
    def test_sanitize_text_input_empty(self, validator):
        """Test sanitization of empty text"""
        sanitized = validator.sanitize_text_input("")
        assert sanitized == ""
        
        sanitized = validator.sanitize_text_input(None)
        assert sanitized == ""
    
    def test_sanitize_text_input_null_bytes(self, validator):
        """Test sanitization removes null bytes"""
        text = "Hello\x00World"
        sanitized = validator.sanitize_text_input(text)
        assert "\x00" not in sanitized
        assert sanitized == "HelloWorld"
    
    def test_sanitize_text_input_control_chars(self, validator):
        """Test sanitization removes control characters"""
        text = "Hello\x01\x02World\x1F"
        sanitized = validator.sanitize_text_input(text)
        assert sanitized == "HelloWorld"
    
    def test_sanitize_text_input_too_long(self, validator):
        """Test sanitization truncates long text"""
        long_text = "A" * (validator.max_text_length + 100)
        sanitized = validator.sanitize_text_input(long_text)
        assert len(sanitized) == validator.max_text_length
        assert sanitized == "A" * validator.max_text_length
    
    def test_sanitize_text_input_excessive_repetition(self, validator):
        """Test sanitization reduces excessive repetition"""
        text = "A" * 50  # More than 10 identical characters
        sanitized = validator.sanitize_text_input(text)
        assert len(sanitized) <= 10  # Should be reduced to max 10
    
    def test_get_validation_stats(self, validator):
        """Test validation statistics reporting"""
        stats = validator.get_validation_stats()
        
        assert "max_text_length" in stats
        assert "max_key_combination_length" in stats
        assert "max_single_key_length" in stats
        assert "dangerous_patterns_count" in stats
        assert "allowed_text_chars_count" in stats
        assert "dangerous_key_combinations_count" in stats
        assert "system_keys_count" in stats
        
        assert stats["max_text_length"] == validator.max_text_length
        assert stats["dangerous_patterns_count"] == len(validator.dangerous_patterns)
        assert stats["allowed_text_chars_count"] == len(validator.allowed_text_chars)


if __name__ == "__main__":
    pytest.main([__file__])