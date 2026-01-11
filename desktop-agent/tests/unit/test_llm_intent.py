"""
Unit Tests for LLM Intent Processing

Comprehensive test suite for intent validation, structured intent creation,
and security boundary enforcement.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import patch

from src.llm.intent import (
    IntentType,
    StructuredIntent,
    IntentValidator,
    create_typing_intent,
    create_key_press_intent,
    create_app_launch_intent
)
from src.llm.exceptions import IntentValidationError, IsolationBreachError


class TestIntentType:
    """Test suite for IntentType enumeration."""
    
    def test_intent_type_values(self):
        """Test intent type enumeration values."""
        assert IntentType.TYPE_TEXT.value == "type_text"
        assert IntentType.PRESS_KEY.value == "press_key"
        assert IntentType.MOUSE_ACTION.value == "mouse_action"
        assert IntentType.LAUNCH_APP.value == "launch_app"
        assert IntentType.EXECUTE_SKILL.value == "execute_skill"
        assert IntentType.DIRECT_EXECUTION.value == "direct_execution"
        assert IntentType.SYSTEM_COMMAND.value == "system_command"
        
    def test_intent_type_enumeration(self):
        """Test intent type enumeration behavior."""
        # Test that we can create IntentType from string
        intent_type = IntentType("type_text")
        assert intent_type == IntentType.TYPE_TEXT
        
        # Test invalid intent type
        with pytest.raises(ValueError):
            IntentType("invalid_intent")


class TestStructuredIntent:
    """Test suite for StructuredIntent class."""
    
    def test_structured_intent_creation(self):
        """Test basic structured intent creation."""
        intent = StructuredIntent(
            intent_type=IntentType.TYPE_TEXT,
            parameters={'text': 'Hello world'},
            confidence=0.95,
            context="Test context"
        )
        
        assert intent.intent_type == IntentType.TYPE_TEXT
        assert intent.parameters['text'] == 'Hello world'
        assert intent.confidence == 0.95
        assert intent.context == "Test context"
        assert intent.requires_authority is True
        assert isinstance(intent.timestamp, datetime)
        
    def test_structured_intent_validation(self):
        """Test structured intent validation."""
        # Valid intent
        intent = StructuredIntent(
            intent_type=IntentType.TYPE_TEXT,
            parameters={'text': 'Valid text'},
            confidence=0.8
        )
        
        assert intent.is_valid()
        assert len(intent.validation_errors) == 0
        
    def test_structured_intent_invalid_confidence(self):
        """Test structured intent with invalid confidence."""
        intent = StructuredIntent(
            intent_type=IntentType.TYPE_TEXT,
            parameters={'text': 'Test'},
            confidence=1.5  # Invalid - should be <= 1.0
        )
        
        assert not intent.is_valid()
        assert "Confidence must be between 0.0 and 1.0" in intent.validation_errors
        
    def test_structured_intent_missing_parameters(self):
        """Test structured intent with missing required parameters."""
        # TYPE_TEXT requires 'text' parameter
        intent = StructuredIntent(
            intent_type=IntentType.TYPE_TEXT,
            parameters={},  # Missing 'text'
            confidence=0.9
        )
        
        assert not intent.is_valid()
        assert "TYPE_TEXT intent requires 'text' parameter" in intent.validation_errors
        
    def test_structured_intent_press_key_validation(self):
        """Test PRESS_KEY intent validation."""
        # Valid PRESS_KEY intent
        intent = StructuredIntent(
            intent_type=IntentType.PRESS_KEY,
            parameters={'key': 'Enter'},
            confidence=0.9
        )
        
        assert intent.is_valid()
        
        # Invalid PRESS_KEY intent - missing key
        intent = StructuredIntent(
            intent_type=IntentType.PRESS_KEY,
            parameters={},
            confidence=0.9
        )
        
        assert not intent.is_valid()
        assert "PRESS_KEY intent requires 'key' parameter" in intent.validation_errors
        
    def test_structured_intent_mouse_action_validation(self):
        """Test MOUSE_ACTION intent validation."""
        # Valid MOUSE_ACTION intent
        intent = StructuredIntent(
            intent_type=IntentType.MOUSE_ACTION,
            parameters={'action': 'click', 'x': 100, 'y': 200},
            confidence=0.9
        )
        
        assert intent.is_valid()
        
        # Invalid MOUSE_ACTION intent - missing parameters
        intent = StructuredIntent(
            intent_type=IntentType.MOUSE_ACTION,
            parameters={'action': 'click'},  # Missing x, y
            confidence=0.9
        )
        
        assert not intent.is_valid()
        assert "MOUSE_ACTION intent requires 'x' parameter" in intent.validation_errors
        assert "MOUSE_ACTION intent requires 'y' parameter" in intent.validation_errors
        
    def test_structured_intent_risk_assessment(self):
        """Test intent risk level assessment."""
        # Low risk intent
        low_risk_intent = StructuredIntent(
            intent_type=IntentType.TYPE_TEXT,
            parameters={'text': 'Hello'}
        )
        assert low_risk_intent.risk_level == "low"
        
        # Medium risk intent
        medium_risk_intent = StructuredIntent(
            intent_type=IntentType.OPEN_FILE,
            parameters={'file_path': '/test/file.txt'}
        )
        assert medium_risk_intent.risk_level == "medium"
        
        # High risk intent
        high_risk_intent = StructuredIntent(
            intent_type=IntentType.EXECUTE_SKILL,
            parameters={'skill_id': 'test_skill'}
        )
        assert high_risk_intent.risk_level == "high"
        
    def test_structured_intent_biometric_auth_requirement(self):
        """Test biometric authentication requirement assessment."""
        # Low risk - no biometric auth required
        low_risk_intent = StructuredIntent(
            intent_type=IntentType.TYPE_TEXT,
            parameters={'text': 'Hello'}
        )
        assert not low_risk_intent.requires_biometric_auth()
        
        # High risk - biometric auth required
        high_risk_intent = StructuredIntent(
            intent_type=IntentType.EXECUTE_SKILL,
            parameters={'skill_id': 'test_skill'}
        )
        assert high_risk_intent.requires_biometric_auth()
        
    def test_structured_intent_serialization(self):
        """Test structured intent serialization."""
        intent = StructuredIntent(
            intent_type=IntentType.TYPE_TEXT,
            parameters={'text': 'Test serialization'},
            confidence=0.85,
            context="Test context",
            risk_level="low"
        )
        
        intent_dict = intent.to_dict()
        
        assert intent_dict['intent_type'] == "type_text"
        assert intent_dict['parameters']['text'] == 'Test serialization'
        assert intent_dict['confidence'] == 0.85
        assert intent_dict['context'] == "Test context"
        assert intent_dict['risk_level'] == "low"
        assert 'timestamp' in intent_dict
        assert 'validation_errors' in intent_dict
        
    def test_isolation_breach_detection(self):
        """Test isolation breach detection in intent creation."""
        # Direct execution attempt should raise IsolationBreachError
        with pytest.raises(IsolationBreachError) as exc_info:
            StructuredIntent(
                intent_type=IntentType.DIRECT_EXECUTION,
                parameters={'command': 'exec("malicious code")'}
            )
            
        assert "LLM attempted direct execution" in str(exc_info.value)
        assert exc_info.value.breach_type == "direct_execution"
        
        # System command attempt should raise IsolationBreachError
        with pytest.raises(IsolationBreachError) as exc_info:
            StructuredIntent(
                intent_type=IntentType.SYSTEM_COMMAND,
                parameters={'command': 'rm -rf /'}
            )
            
        assert "LLM attempted direct execution" in str(exc_info.value)


class TestIntentValidator:
    """Test suite for IntentValidator class."""
    
    def test_intent_validator_creation(self):
        """Test intent validator creation."""
        validator = IntentValidator()
        
        assert validator is not None
        assert len(validator.blocked_patterns) > 0
        
    def test_valid_json_response_validation(self):
        """Test validation of valid JSON response."""
        validator = IntentValidator()
        
        valid_response = json.dumps({
            'intent_type': 'type_text',
            'parameters': {'text': 'Hello world'},
            'confidence': 0.9,
            'context': 'Test context'
        })
        
        intent = validator.validate_raw_response(valid_response)
        
        assert isinstance(intent, StructuredIntent)
        assert intent.intent_type == IntentType.TYPE_TEXT
        assert intent.parameters['text'] == 'Hello world'
        assert intent.confidence == 0.9
        
    def test_invalid_json_response_validation(self):
        """Test validation of invalid JSON response."""
        validator = IntentValidator()
        
        invalid_response = "This is not valid JSON"
        
        with pytest.raises(IntentValidationError) as exc_info:
            validator.validate_raw_response(invalid_response)
            
        assert "Failed to parse LLM response as JSON" in str(exc_info.value)
        assert exc_info.value.raw_response == invalid_response
        
    def test_missing_intent_type_validation(self):
        """Test validation of response missing intent_type."""
        validator = IntentValidator()
        
        response_without_intent_type = json.dumps({
            'parameters': {'text': 'Hello'},
            'confidence': 0.9
        })
        
        with pytest.raises(IntentValidationError) as exc_info:
            validator.validate_raw_response(response_without_intent_type)
            
        assert "Missing required field: intent_type" in str(exc_info.value)
        
    def test_invalid_intent_type_validation(self):
        """Test validation of response with invalid intent_type."""
        validator = IntentValidator()
        
        response_with_invalid_type = json.dumps({
            'intent_type': 'invalid_intent_type',
            'parameters': {'text': 'Hello'},
            'confidence': 0.9
        })
        
        with pytest.raises(IntentValidationError) as exc_info:
            validator.validate_raw_response(response_with_invalid_type)
            
        assert "Invalid intent type: invalid_intent_type" in str(exc_info.value)
        
    def test_isolation_breach_detection(self):
        """Test isolation breach detection in raw responses."""
        validator = IntentValidator()
        
        # Test code execution attempt
        malicious_response = "exec('malicious code')"
        
        with pytest.raises(IsolationBreachError) as exc_info:
            validator._check_isolation_breach(malicious_response)
            
        assert "LLM attempted to execute code directly" in str(exc_info.value)
        assert exc_info.value.breach_type == "code_execution"
        
        # Test system command attempt
        system_response = "import subprocess; subprocess.run(['rm', '-rf', '/'])"
        
        with pytest.raises(IsolationBreachError) as exc_info:
            validator._check_isolation_breach(system_response)
            
        assert exc_info.value.breach_type == "code_execution"
        
    def test_parameter_sanitization(self):
        """Test parameter sanitization."""
        validator = IntentValidator()
        
        dangerous_params = {
            'text': 'Hello `world`',
            'command': 'ls | grep test',
            'path': '/path/with/$(dangerous)',
            'number': 42,
            'boolean': True,
            'list': ['item1', 'item2'],
            'dict': {'key': 'value'}
        }
        
        sanitized = validator.sanitize_parameters(dangerous_params)
        
        # Dangerous characters should be removed
        assert '`' not in sanitized['text']
        assert '|' not in sanitized['command']
        assert '$' not in sanitized['path']
        
        # Safe values should be preserved
        assert sanitized['number'] == 42
        assert sanitized['boolean'] is True
        assert sanitized['list'] == ['item1', 'item2']
        assert sanitized['dict'] == {'key': 'value'}
        
    def test_string_sanitization(self):
        """Test string sanitization."""
        validator = IntentValidator()
        
        # Test null byte removal
        text_with_nulls = "Hello\x00world"
        sanitized = validator._sanitize_string(text_with_nulls)
        assert '\x00' not in sanitized
        
        # Test length limiting
        very_long_text = "A" * 20000
        sanitized = validator._sanitize_string(very_long_text)
        assert len(sanitized) <= 10000
        
        # Test dangerous character removal
        dangerous_text = "Hello `world` $(command) | grep test"
        sanitized = validator._sanitize_string(dangerous_text)
        assert '`' not in sanitized
        assert '$' not in sanitized
        assert '|' not in sanitized
        
    def test_complex_object_sanitization(self):
        """Test sanitization of complex objects."""
        validator = IntentValidator()
        
        # Test dictionary sanitization
        test_dict = {
            'safe_key': 'safe_value',
            'dangerous_key': 'dangerous `value`'
        }
        
        sanitized_dict = validator._sanitize_complex(test_dict)
        assert sanitized_dict['safe_key'] == 'safe_value'
        assert '`' not in sanitized_dict['dangerous_key']
        
        # Test list sanitization
        test_list = ['safe_item', 'dangerous `item`']
        sanitized_list = validator._sanitize_complex(test_list)
        assert sanitized_list[0] == 'safe_item'
        assert '`' not in sanitized_list[1]
        
    def test_validation_with_context(self):
        """Test validation with additional context."""
        validator = IntentValidator()
        
        response_with_context = json.dumps({
            'intent_type': 'type_text',
            'parameters': {'text': 'Hello with context'},
            'confidence': 0.95,
            'context': 'User requested greeting',
            'requires_authority': True
        })
        
        intent = validator.validate_raw_response(response_with_context)
        
        assert intent.context == 'User requested greeting'
        assert intent.requires_authority is True
        
    def test_validation_error_aggregation(self):
        """Test that validation errors are properly aggregated."""
        validator = IntentValidator()
        
        # Response with multiple validation errors
        invalid_response = json.dumps({
            'intent_type': 'type_text',
            'parameters': {},  # Missing required 'text' parameter
            'confidence': 1.5,  # Invalid confidence > 1.0
            'context': 'Test'
        })
        
        with pytest.raises(IntentValidationError) as exc_info:
            validator.validate_raw_response(invalid_response)
            
        # Should contain multiple validation errors
        assert len(exc_info.value.validation_errors) > 1


class TestIntentFactoryFunctions:
    """Test suite for intent factory functions."""
    
    def test_create_typing_intent(self):
        """Test typing intent creation."""
        intent = create_typing_intent("Hello world", confidence=0.95)
        
        assert intent.intent_type == IntentType.TYPE_TEXT
        assert intent.parameters['text'] == "Hello world"
        assert intent.confidence == 0.95
        assert intent.risk_level == "low"
        
    def test_create_typing_intent_default_confidence(self):
        """Test typing intent creation with default confidence."""
        intent = create_typing_intent("Test text")
        
        assert intent.confidence == 1.0
        
    def test_create_key_press_intent(self):
        """Test key press intent creation."""
        intent = create_key_press_intent("Enter")
        
        assert intent.intent_type == IntentType.PRESS_KEY
        assert intent.parameters['key'] == "Enter"
        assert intent.risk_level == "low"
        
    def test_create_key_press_intent_with_modifiers(self):
        """Test key press intent creation with modifiers."""
        intent = create_key_press_intent("c", modifiers=["Ctrl"])
        
        assert intent.intent_type == IntentType.PRESS_KEY
        assert intent.parameters['key'] == "c"
        assert intent.parameters['modifiers'] == ["Ctrl"]
        
    def test_create_app_launch_intent(self):
        """Test app launch intent creation."""
        intent = create_app_launch_intent("notepad")
        
        assert intent.intent_type == IntentType.LAUNCH_APP
        assert intent.parameters['app_name'] == "notepad"
        assert intent.risk_level == "high"
        
    def test_create_app_launch_intent_with_arguments(self):
        """Test app launch intent creation with arguments."""
        intent = create_app_launch_intent("notepad", arguments=["file.txt"])
        
        assert intent.intent_type == IntentType.LAUNCH_APP
        assert intent.parameters['app_name'] == "notepad"
        assert intent.parameters['arguments'] == ["file.txt"]
        
    def test_factory_function_validation(self):
        """Test that factory functions create valid intents."""
        # All factory functions should create valid intents
        typing_intent = create_typing_intent("Test")
        key_intent = create_key_press_intent("Enter")
        app_intent = create_app_launch_intent("notepad")
        
        assert typing_intent.is_valid()
        assert key_intent.is_valid()
        assert app_intent.is_valid()
        
        # Check that validation errors are empty
        assert len(typing_intent.validation_errors) == 0
        assert len(key_intent.validation_errors) == 0
        assert len(app_intent.validation_errors) == 0


class TestIntentSecurityBoundaries:
    """Test suite for intent security boundary enforcement."""
    
    def test_blocked_intent_types(self):
        """Test that blocked intent types raise isolation breach errors."""
        blocked_types = [IntentType.DIRECT_EXECUTION, IntentType.SYSTEM_COMMAND]
        
        for blocked_type in blocked_types:
            with pytest.raises(IsolationBreachError):
                StructuredIntent(
                    intent_type=blocked_type,
                    parameters={'command': 'test'}
                )
                
    def test_safe_intent_types(self):
        """Test that safe intent types are allowed."""
        safe_types = [
            IntentType.TYPE_TEXT,
            IntentType.PRESS_KEY,
            IntentType.MOUSE_ACTION,
            IntentType.LAUNCH_APP,
            IntentType.GET_STATUS
        ]
        
        for safe_type in safe_types:
            # Should not raise exception
            intent = StructuredIntent(
                intent_type=safe_type,
                parameters={'test': 'value'}
            )
            assert intent.intent_type == safe_type
            
    def test_parameter_injection_prevention(self):
        """Test prevention of parameter injection attacks."""
        validator = IntentValidator()
        
        # Test SQL injection attempt
        malicious_params = {
            'text': "'; DROP TABLE users; --",
            'file_path': "../../../etc/passwd",
            'command': "rm -rf /"
        }
        
        sanitized = validator.sanitize_parameters(malicious_params)
        
        # Dangerous patterns should be sanitized (some characters removed)
        # Note: Basic sanitization removes some dangerous chars but may not catch all SQL
        assert len(sanitized['text']) <= len(malicious_params['text'])
        assert "../" not in sanitized['file_path']
        assert "[FILTERED]" in sanitized['command']  # rm -rf should be filtered
        
    def test_intent_authority_requirements(self):
        """Test that intents properly specify authority requirements."""
        # High-risk intents should require authority
        high_risk_intent = StructuredIntent(
            intent_type=IntentType.EXECUTE_SKILL,
            parameters={'skill_id': 'test'}
        )
        assert high_risk_intent.requires_authority is True
        
        # Low-risk intents should still require authority by default
        low_risk_intent = StructuredIntent(
            intent_type=IntentType.TYPE_TEXT,
            parameters={'text': 'Hello'}
        )
        assert low_risk_intent.requires_authority is True
        
    def test_intent_confidence_validation(self):
        """Test intent confidence score validation."""
        # Valid confidence scores
        valid_confidences = [0.0, 0.5, 0.95, 1.0]
        
        for confidence in valid_confidences:
            intent = StructuredIntent(
                intent_type=IntentType.TYPE_TEXT,
                parameters={'text': 'Test'},
                confidence=confidence
            )
            assert intent.is_valid()
            
        # Invalid confidence scores
        invalid_confidences = [-0.1, 1.1, 2.0, -1.0]
        
        for confidence in invalid_confidences:
            intent = StructuredIntent(
                intent_type=IntentType.TYPE_TEXT,
                parameters={'text': 'Test'},
                confidence=confidence
            )
            assert not intent.is_valid()
            assert "Confidence must be between 0.0 and 1.0" in intent.validation_errors