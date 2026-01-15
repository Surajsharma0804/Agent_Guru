"""
Intent Processing and Validation

Structured intent system that enforces the critical security invariant:
LLMs produce structured intents only, never direct execution commands.

All intents must pass through authority gates and validation before
any system action can be taken.
"""

from typing import Dict, Any, List, Optional, Union, Literal
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import re
from .exceptions import IntentValidationError, IsolationBreachError


class IntentType(Enum):
    """Enumeration of valid intent types that LLMs can produce."""
    
    # Input simulation intents
    TYPE_TEXT = "type_text"
    PRESS_KEY = "press_key"
    MOUSE_ACTION = "mouse_action"
    
    # Application control intents
    LAUNCH_APP = "launch_app"
    CLOSE_APP = "close_app"
    SWITCH_APP = "switch_app"
    
    # File operation intents
    OPEN_FILE = "open_file"
    SAVE_FILE = "save_file"
    
    # System query intents
    GET_STATUS = "get_status"
    SEARCH_MEMORY = "search_memory"
    
    # Skill execution intents
    EXECUTE_SKILL = "execute_skill"
    
    # Authority management intents
    REQUEST_AUTHORITY = "request_authority"
    
    # Invalid/blocked intents
    DIRECT_EXECUTION = "direct_execution"  # Always blocked
    SYSTEM_COMMAND = "system_command"      # Always blocked


@dataclass
class StructuredIntent:
    """
    Structured representation of LLM intent with validation and security checks.
    
    This is the only format that LLMs can produce - no direct execution allowed.
    """
    
    intent_type: IntentType
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    context: Optional[str] = None
    requires_authority: bool = True
    risk_level: Literal["low", "medium", "high", "admin"] = "medium"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    validation_errors: List[str] = field(default_factory=list)
    bypass_llm: bool = False  # Requirement 31.1: Flag indicating LLM was bypassed
    
    def __post_init__(self):
        """Validate intent structure after initialization."""
        self._validate_structure()
        self._assess_risk_level()
        
    def _validate_structure(self):
        """Validate the intent structure and parameters."""
        errors = []
        
        # Validate intent type
        if not isinstance(self.intent_type, IntentType):
            errors.append("Invalid intent type")
            
        # Check for isolation breach attempts
        if self.intent_type in [IntentType.DIRECT_EXECUTION, IntentType.SYSTEM_COMMAND]:
            raise IsolationBreachError(
                "LLM attempted direct execution",
                breach_type="direct_execution",
                attempted_action=str(self.intent_type)
            )
            
        # Validate confidence score
        if not 0.0 <= self.confidence <= 1.0:
            errors.append("Confidence must be between 0.0 and 1.0")
            
        # Validate parameters based on intent type
        self._validate_parameters(errors)
        
        self.validation_errors = errors
        
    def _validate_parameters(self, errors: List[str]):
        """Validate parameters based on intent type."""
        
        if self.intent_type == IntentType.TYPE_TEXT:
            if 'text' not in self.parameters:
                errors.append("TYPE_TEXT intent requires 'text' parameter")
            elif not isinstance(self.parameters['text'], str):
                errors.append("'text' parameter must be a string")
                
        elif self.intent_type == IntentType.PRESS_KEY:
            if 'key' not in self.parameters:
                errors.append("PRESS_KEY intent requires 'key' parameter")
            elif not isinstance(self.parameters['key'], str):
                errors.append("'key' parameter must be a string")
                
        elif self.intent_type == IntentType.MOUSE_ACTION:
            required_params = ['action', 'x', 'y']
            for param in required_params:
                if param not in self.parameters:
                    errors.append(f"MOUSE_ACTION intent requires '{param}' parameter")
                    
        elif self.intent_type == IntentType.LAUNCH_APP:
            if 'app_name' not in self.parameters:
                errors.append("LAUNCH_APP intent requires 'app_name' parameter")
                
        elif self.intent_type == IntentType.EXECUTE_SKILL:
            if 'skill_id' not in self.parameters:
                errors.append("EXECUTE_SKILL intent requires 'skill_id' parameter")
                
    def _assess_risk_level(self):
        """Assess and set the risk level for this intent."""
        
        # High-risk intents
        high_risk_types = [
            IntentType.EXECUTE_SKILL,
            IntentType.SAVE_FILE,
            IntentType.LAUNCH_APP
        ]
        
        # Medium-risk intents  
        medium_risk_types = [
            IntentType.OPEN_FILE,
            IntentType.CLOSE_APP,
            IntentType.SWITCH_APP
        ]
        
        # Low-risk intents
        low_risk_types = [
            IntentType.TYPE_TEXT,
            IntentType.PRESS_KEY,
            IntentType.MOUSE_ACTION,
            IntentType.GET_STATUS,
            IntentType.SEARCH_MEMORY
        ]
        
        if self.intent_type in high_risk_types:
            self.risk_level = "high"
        elif self.intent_type in medium_risk_types:
            self.risk_level = "medium"
        elif self.intent_type in low_risk_types:
            self.risk_level = "low"
        else:
            self.risk_level = "high"  # Default to high risk for unknown types
            
    def is_valid(self) -> bool:
        """Check if the intent is valid and safe to process."""
        return len(self.validation_errors) == 0
        
    def requires_biometric_auth(self) -> bool:
        """Check if this intent requires biometric authentication."""
        return self.risk_level in ["high", "admin"]
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert intent to dictionary for serialization."""
        return {
            'intent_type': self.intent_type.value if hasattr(self.intent_type, 'value') else str(self.intent_type),
            'parameters': self.parameters,
            'confidence': self.confidence,
            'context': self.context,
            'requires_authority': self.requires_authority,
            'risk_level': self.risk_level,
            'timestamp': self.timestamp.isoformat(),
            'validation_errors': self.validation_errors,
            'bypass_llm': self.bypass_llm  # Requirement 31.1
        }


class IntentValidator:
    """
    Validates and sanitizes LLM-generated intents with comprehensive security checks.
    
    Enforces the critical security boundary: LLMs are advisory only.
    """
    
    def __init__(self):
        self.blocked_patterns = [
            r'exec\(',
            r'eval\(',
            r'subprocess\.',
            r'os\.system',
            r'__import__',
            r'getattr\(',
            r'setattr\(',
            r'delattr\(',
        ]
        
    def validate_raw_response(self, raw_response: str) -> StructuredIntent:
        """
        Validate and parse raw LLM response into structured intent.
        
        Args:
            raw_response: Raw text response from LLM
            
        Returns:
            StructuredIntent: Validated and structured intent
            
        Raises:
            IntentValidationError: If response cannot be parsed or is invalid
            IsolationBreachError: If response attempts direct execution
        """
        
        # Check for direct execution attempts
        self._check_isolation_breach(raw_response)
        
        # Parse JSON response
        try:
            parsed_data = json.loads(raw_response)
        except json.JSONDecodeError as e:
            raise IntentValidationError(
                "Failed to parse LLM response as JSON",
                validation_errors=[f"JSON decode error: {str(e)}"],
                raw_response=raw_response
            )
            
        # Validate required fields
        if 'intent_type' not in parsed_data:
            raise IntentValidationError(
                "Missing required field: intent_type",
                validation_errors=["intent_type field is required"],
                raw_response=raw_response
            )
            
        # Convert to IntentType enum
        try:
            intent_type = IntentType(parsed_data['intent_type'])
        except ValueError:
            raise IntentValidationError(
                f"Invalid intent type: {parsed_data['intent_type']}",
                validation_errors=[f"Unknown intent type: {parsed_data['intent_type']}"],
                raw_response=raw_response
            )
            
        # Create structured intent
        try:
            intent = StructuredIntent(
                intent_type=intent_type,
                parameters=parsed_data.get('parameters', {}),
                confidence=parsed_data.get('confidence', 1.0),
                context=parsed_data.get('context'),
                requires_authority=parsed_data.get('requires_authority', True)
            )
        except Exception as e:
            raise IntentValidationError(
                f"Failed to create structured intent: {str(e)}",
                validation_errors=[str(e)],
                raw_response=raw_response
            )
            
        # Final validation
        if not intent.is_valid():
            raise IntentValidationError(
                "Intent validation failed",
                validation_errors=intent.validation_errors,
                raw_response=raw_response
            )
            
        return intent
        
    def _check_isolation_breach(self, response: str):
        """Check for attempts to breach LLM isolation."""
        
        # Check for blocked patterns
        for pattern in self.blocked_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                raise IsolationBreachError(
                    "LLM attempted to execute code directly",
                    breach_type="code_execution",
                    attempted_action=pattern
                )
                
        # Check for system command attempts
        system_keywords = [
            'subprocess', 'os.system', 'exec', 'eval', 'import',
            'shell', 'cmd', 'powershell', 'bash'
        ]
        
        response_lower = response.lower()
        for keyword in system_keywords:
            if keyword in response_lower:
                raise IsolationBreachError(
                    f"LLM attempted system access: {keyword}",
                    breach_type="system_access",
                    attempted_action=keyword
                )
                
    def sanitize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize intent parameters to prevent injection attacks."""
        
        sanitized = {}
        
        for key, value in parameters.items():
            # Sanitize string values
            if isinstance(value, str):
                sanitized[key] = self._sanitize_string(value)
            elif isinstance(value, (int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, (list, dict)):
                # Recursively sanitize complex types
                sanitized[key] = self._sanitize_complex(value)
            else:
                # Convert unknown types to string and sanitize
                sanitized[key] = self._sanitize_string(str(value))
                
        return sanitized
        
    def _sanitize_string(self, text: str) -> str:
        """Sanitize string values to prevent injection."""
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Limit length to prevent DoS
        if len(text) > 10000:
            text = text[:10000]
            
        # Remove potentially dangerous characters and patterns
        dangerous_chars = ['`', '$', '|', '&', ';', '(', ')', '{', '}']
        for char in dangerous_chars:
            text = text.replace(char, '')
            
        # Remove dangerous path traversal patterns
        text = text.replace('../', '')
        text = text.replace('..\\', '')
        
        # Remove common SQL injection patterns
        sql_patterns = ['DROP TABLE', 'DELETE FROM', 'INSERT INTO', 'UPDATE SET']
        for pattern in sql_patterns:
            text = text.replace(pattern, '[FILTERED]')
            text = text.replace(pattern.lower(), '[FILTERED]')
            
        # Remove dangerous system commands
        dangerous_commands = ['rm -rf', 'del /q', 'format c:', 'shutdown', 'taskkill']
        for cmd in dangerous_commands:
            text = text.replace(cmd, '[FILTERED]')
            text = text.replace(cmd.upper(), '[FILTERED]')
            
        return text
        
    def _sanitize_complex(self, obj: Union[list, dict]) -> Union[list, dict]:
        """Recursively sanitize complex objects."""
        
        if isinstance(obj, dict):
            return {
                key: self._sanitize_string(str(value)) if isinstance(value, str) else value
                for key, value in obj.items()
            }
        elif isinstance(obj, list):
            return [
                self._sanitize_string(str(item)) if isinstance(item, str) else item
                for item in obj
            ]
        else:
            return obj


# Intent factory functions for common operations
def create_typing_intent(text: str, confidence: float = 1.0) -> StructuredIntent:
    """Create a text typing intent."""
    return StructuredIntent(
        intent_type=IntentType.TYPE_TEXT,
        parameters={'text': text},
        confidence=confidence,
        risk_level="low"
    )


def create_key_press_intent(key: str, modifiers: Optional[List[str]] = None) -> StructuredIntent:
    """Create a key press intent."""
    parameters = {'key': key}
    if modifiers:
        parameters['modifiers'] = modifiers
        
    return StructuredIntent(
        intent_type=IntentType.PRESS_KEY,
        parameters=parameters,
        risk_level="low"
    )


def create_app_launch_intent(app_name: str, arguments: Optional[List[str]] = None) -> StructuredIntent:
    """Create an application launch intent."""
    parameters = {'app_name': app_name}
    if arguments:
        parameters['arguments'] = arguments
        
    return StructuredIntent(
        intent_type=IntentType.LAUNCH_APP,
        parameters=parameters,
        risk_level="high"
    )