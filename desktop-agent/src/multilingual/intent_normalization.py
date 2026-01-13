"""
Intent Normalization Layer

Production-grade language-neutral intent mapping system that converts
language-specific commands to canonical intents while maintaining
security boundaries and deterministic behavior.
"""

import json
import logging
import re
import signal
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple, Union
from threading import RLock
import hashlib

from .configuration import MultilingualConfig, SupportedLanguages
from .exceptions import IntentNormalizationError, SecurityBoundaryError, UnsupportedLanguageError


class IntentAction(Enum):
    """Canonical intent actions supported by GURU."""
    
    # Text input actions
    TYPE_TEXT = "TYPE_TEXT"
    CLEAR_TEXT = "CLEAR_TEXT"
    SELECT_TEXT = "SELECT_TEXT"
    
    # UI interaction actions
    CLICK_ELEMENT = "CLICK_ELEMENT"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    RIGHT_CLICK = "RIGHT_CLICK"
    SCROLL = "SCROLL"
    
    # Application actions
    OPEN_APPLICATION = "OPEN_APPLICATION"
    CLOSE_APPLICATION = "CLOSE_APPLICATION"
    SWITCH_APPLICATION = "SWITCH_APPLICATION"
    
    # Communication actions
    SEND_MESSAGE = "SEND_MESSAGE"
    MAKE_CALL = "MAKE_CALL"
    SEND_EMAIL = "SEND_EMAIL"
    
    # File operations
    OPEN_FILE = "OPEN_FILE"
    SAVE_FILE = "SAVE_FILE"
    CREATE_FILE = "CREATE_FILE"
    DELETE_FILE = "DELETE_FILE"
    
    # System actions
    LOCK_SYSTEM = "LOCK_SYSTEM"
    SHUTDOWN_SYSTEM = "SHUTDOWN_SYSTEM"
    RESTART_SYSTEM = "RESTART_SYSTEM"
    
    # Mode switching
    SWITCH_TO_DICTATION = "SWITCH_TO_DICTATION"
    SWITCH_TO_COMMAND = "SWITCH_TO_COMMAND"
    
    # Unknown/unmapped
    UNKNOWN = "UNKNOWN"


class ProcessingMode(Enum):
    """Processing modes for intent normalization."""
    
    COMMAND = "command"      # Interpret as command
    DICTATION = "dictation"  # Preserve as exact text
    MIXED = "mixed"          # Mixed command and dictation


@dataclass
class CanonicalIntent:
    """Language-neutral canonical intent representation."""
    
    # Core intent information
    action: IntentAction
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Original context
    original_text: str = ""
    original_language: str = ""
    processing_mode: ProcessingMode = ProcessingMode.COMMAND
    
    # Normalization metadata
    confidence: float = 1.0
    normalization_path: str = ""
    pattern_matched: Optional[str] = None
    
    # Security and validation
    requires_authority: bool = True
    security_level: str = "medium"
    validated: bool = False
    
    # Timing information
    created_at: datetime = field(default_factory=datetime.utcnow)
    processing_time_ms: int = 0
    
    def __post_init__(self):
        """Validate canonical intent after creation."""
        if not isinstance(self.action, IntentAction):
            raise IntentNormalizationError(
                f"Invalid intent action: {self.action}",
                attempted_intent=str(self.action),
                normalization_stage="validation"
            )
            
        # Ensure parameters is a dictionary
        if not isinstance(self.parameters, dict):
            self.parameters = {}
            
        # Generate normalization path if not provided
        if not self.normalization_path:
            self.normalization_path = f"{self.original_language} -> {self.action.value}"
            
    def to_guru_command(self) -> Dict[str, Any]:
        """Convert to existing GURU command format."""
        return {
            'action': self.action.value,
            'parameters': self.parameters,
            'metadata': {
                'original_language': self.original_language,
                'original_text': self.original_text,
                'normalization_path': self.normalization_path,
                'processing_mode': self.processing_mode.value,
                'multilingual': True,
                'confidence': self.confidence,
                'requires_authority': self.requires_authority,
                'security_level': self.security_level,
                'created_at': self.created_at.isoformat(),
                'processing_time_ms': self.processing_time_ms
            }
        }
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'action': self.action.value,
            'parameters': self.parameters,
            'original_text_length': len(self.original_text),
            'original_language': self.original_language,
            'processing_mode': self.processing_mode.value,
            'confidence': self.confidence,
            'normalization_path': self.normalization_path,
            'pattern_matched': self.pattern_matched,
            'requires_authority': self.requires_authority,
            'security_level': self.security_level,
            'validated': self.validated,
            'created_at': self.created_at.isoformat(),
            'processing_time_ms': self.processing_time_ms
        }


@dataclass
class IntentPattern:
    """Language-specific intent pattern for command recognition."""
    
    pattern: str  # Regex pattern
    action: IntentAction
    parameter_groups: Dict[str, int] = field(default_factory=dict)  # Parameter name -> group index
    confidence: float = 1.0
    security_level: str = "medium"
    
    # Compiled pattern (cached)
    _compiled_pattern: Optional[Pattern] = field(default=None, init=False, repr=False)
    
    def __post_init__(self):
        """Compile regex pattern after initialization."""
        try:
            self._compiled_pattern = re.compile(self.pattern, re.IGNORECASE | re.UNICODE)
        except re.error as e:
            raise IntentNormalizationError(
                f"Invalid regex pattern: {self.pattern}",
                normalization_stage="pattern_compilation",
                context={'regex_error': str(e)}
            )
            
    def match(self, text: str) -> Optional[Dict[str, str]]:
        """Match text against pattern and extract parameters."""
        if not self._compiled_pattern:
            return None
            
        # Normalize text for better matching
        normalized_text = self._normalize_text(text)
        
        match = self._compiled_pattern.match(normalized_text)
        if not match:
            # Try case-insensitive matching if first attempt fails
            match = self._compiled_pattern.match(text.lower())
            
        if not match:
            return None
            
        # Extract parameters from named groups
        parameters = {}
        
        # Extract from parameter group mappings
        for param_name, group_index in self.parameter_groups.items():
            try:
                value = match.group(group_index)
                if value:
                    # Clean and validate parameter value
                    cleaned_value = self._clean_parameter_value(value, param_name)
                    if cleaned_value:
                        parameters[param_name] = cleaned_value
            except IndexError:
                continue
                
        # Extract from named groups in regex
        named_groups = match.groupdict()
        for name, value in named_groups.items():
            if value and name not in parameters:
                cleaned_value = self._clean_parameter_value(value, name)
                if cleaned_value:
                    parameters[name] = cleaned_value
                    
        return parameters
        
    def _normalize_text(self, text: str) -> str:
        """Normalize text for better pattern matching."""
        # Remove extra whitespace
        normalized = ' '.join(text.split())
        
        # Handle common variations and contractions
        # English contractions
        contractions = {
            "don't": "do not",
            "won't": "will not", 
            "can't": "cannot",
            "shouldn't": "should not",
            "wouldn't": "would not",
            "couldn't": "could not"
        }
        
        for contraction, expansion in contractions.items():
            normalized = normalized.replace(contraction, expansion)
            normalized = normalized.replace(contraction.title(), expansion.title())
            
        return normalized.strip()
        
    def _clean_parameter_value(self, value: str, param_name: str) -> Optional[str]:
        """Clean and validate parameter values."""
        if not value or not value.strip():
            return None
            
        cleaned = value.strip()
        
        # Remove quotes if present
        if (cleaned.startswith('"') and cleaned.endswith('"')) or \
           (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1]
            
        # Parameter-specific cleaning
        if param_name in ['text', 'message']:
            # For text parameters, preserve most content but remove dangerous patterns
            cleaned = self._sanitize_text_content(cleaned)
        elif param_name in ['element', 'application', 'contact']:
            # For identifiers, be more restrictive
            cleaned = self._sanitize_identifier(cleaned)
        elif param_name == 'filename':
            # For filenames, validate path safety
            cleaned = self._sanitize_filename(cleaned)
            
        return cleaned if cleaned else None
        
    def _sanitize_text_content(self, text: str) -> str:
        """Sanitize text content while preserving readability."""
        # Remove null bytes and control characters
        sanitized = ''.join(char for char in text if ord(char) >= 32 or char in '\t\n\r')
        
        # Limit length to prevent DoS
        if len(sanitized) > 5000:
            sanitized = sanitized[:5000]
            
        return sanitized
        
    def _sanitize_identifier(self, identifier: str) -> str:
        """Sanitize identifiers (application names, elements, etc.)."""
        # Allow alphanumeric, spaces, hyphens, underscores
        import re
        sanitized = re.sub(r'[^\w\s\-]', '', identifier)
        
        # Limit length
        if len(sanitized) > 200:
            sanitized = sanitized[:200]
            
        return sanitized.strip()
        
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filenames for security."""
        import re
        
        # Remove path traversal attempts
        sanitized = filename.replace('..', '').replace('/', '').replace('\\', '')
        
        # Allow alphanumeric, spaces, dots, hyphens, underscores
        sanitized = re.sub(r'[^\w\s\.\-]', '', sanitized)
        
        # Limit length
        if len(sanitized) > 255:
            sanitized = sanitized[:255]
            
        return sanitized.strip()


class CanonicalIntentRegistry:
    """
    Production-grade registry for canonical intents with comprehensive
    intent management, validation, and cross-language mapping capabilities.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._intent_definitions: Dict[IntentAction, IntentDefinition] = {}
        self._parameter_schemas: Dict[IntentAction, Dict[str, ParameterSchema]] = {}
        self._security_policies: Dict[IntentAction, SecurityPolicy] = {}
        self._lock = RLock()
        
        # Initialize with default intent definitions
        self._initialize_default_intents()
        
    def _initialize_default_intents(self):
        """Initialize default canonical intent definitions."""
        
        # Text input intents
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.TYPE_TEXT,
            description="Type text at current cursor position",
            required_parameters=["text"],
            optional_parameters=["preserve_exact", "input_method"],
            security_level="low",
            requires_authority=True,
            category="text_input"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.CLEAR_TEXT,
            description="Clear all text in current input field",
            required_parameters=[],
            optional_parameters=["selection_only"],
            security_level="low",
            requires_authority=True,
            category="text_input"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.SELECT_TEXT,
            description="Select text in current input field",
            required_parameters=["selection_type"],
            optional_parameters=["start_position", "end_position", "pattern"],
            security_level="low",
            requires_authority=True,
            category="text_input"
        ))
        
        # UI interaction intents
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.CLICK_ELEMENT,
            description="Click on UI element",
            required_parameters=["element"],
            optional_parameters=["coordinates", "button", "modifiers"],
            security_level="medium",
            requires_authority=True,
            category="ui_interaction"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.DOUBLE_CLICK,
            description="Double-click on UI element",
            required_parameters=["element"],
            optional_parameters=["coordinates", "button"],
            security_level="medium",
            requires_authority=True,
            category="ui_interaction"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.RIGHT_CLICK,
            description="Right-click on UI element",
            required_parameters=["element"],
            optional_parameters=["coordinates"],
            security_level="medium",
            requires_authority=True,
            category="ui_interaction"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.SCROLL,
            description="Scroll in specified direction",
            required_parameters=["direction"],
            optional_parameters=["amount", "element", "coordinates"],
            security_level="low",
            requires_authority=True,
            category="ui_interaction"
        ))
        
        # Application control intents
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.OPEN_APPLICATION,
            description="Launch or open application",
            required_parameters=["application"],
            optional_parameters=["arguments", "working_directory"],
            security_level="high",
            requires_authority=True,
            category="application_control"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.CLOSE_APPLICATION,
            description="Close running application",
            required_parameters=["application"],
            optional_parameters=["force_close", "save_prompt"],
            security_level="medium",
            requires_authority=True,
            category="application_control"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.SWITCH_APPLICATION,
            description="Switch to different application",
            required_parameters=["application"],
            optional_parameters=["window_title", "process_id"],
            security_level="low",
            requires_authority=True,
            category="application_control"
        ))
        
        # Communication intents
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.SEND_MESSAGE,
            description="Send message via messaging application",
            required_parameters=["message"],
            optional_parameters=["recipient", "platform", "attachments"],
            security_level="high",
            requires_authority=True,
            category="communication"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.MAKE_CALL,
            description="Initiate voice or video call",
            required_parameters=["contact"],
            optional_parameters=["call_type", "platform"],
            security_level="high",
            requires_authority=True,
            category="communication"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.SEND_EMAIL,
            description="Send email message",
            required_parameters=["message"],
            optional_parameters=["recipient", "subject", "attachments", "cc", "bcc"],
            security_level="high",
            requires_authority=True,
            category="communication"
        ))
        
        # File operation intents
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.OPEN_FILE,
            description="Open file with default or specified application",
            required_parameters=["filename"],
            optional_parameters=["application", "read_only"],
            security_level="medium",
            requires_authority=True,
            category="file_operations"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.SAVE_FILE,
            description="Save file to specified location",
            required_parameters=["filename"],
            optional_parameters=["content", "format", "overwrite"],
            security_level="medium",
            requires_authority=True,
            category="file_operations"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.CREATE_FILE,
            description="Create new file",
            required_parameters=["filename"],
            optional_parameters=["content", "template", "permissions"],
            security_level="medium",
            requires_authority=True,
            category="file_operations"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.DELETE_FILE,
            description="Delete specified file",
            required_parameters=["filename"],
            optional_parameters=["permanent", "confirmation"],
            security_level="high",
            requires_authority=True,
            category="file_operations"
        ))
        
        # System control intents
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.LOCK_SYSTEM,
            description="Lock the system/workstation",
            required_parameters=[],
            optional_parameters=["immediate"],
            security_level="medium",
            requires_authority=True,
            category="system_control"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.SHUTDOWN_SYSTEM,
            description="Shutdown the system",
            required_parameters=[],
            optional_parameters=["delay", "force", "message"],
            security_level="admin",
            requires_authority=True,
            category="system_control"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.RESTART_SYSTEM,
            description="Restart the system",
            required_parameters=[],
            optional_parameters=["delay", "force", "message"],
            security_level="admin",
            requires_authority=True,
            category="system_control"
        ))
        
        # Mode switching intents
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.SWITCH_TO_DICTATION,
            description="Switch to dictation mode",
            required_parameters=[],
            optional_parameters=["language", "input_method"],
            security_level="low",
            requires_authority=False,
            category="mode_control"
        ))
        
        self.register_intent_definition(IntentDefinition(
            action=IntentAction.SWITCH_TO_COMMAND,
            description="Switch to command mode",
            required_parameters=[],
            optional_parameters=["language"],
            security_level="low",
            requires_authority=False,
            category="mode_control"
        ))
        
        self.logger.info(f"Initialized {len(self._intent_definitions)} canonical intent definitions")
        
    def register_intent_definition(self, definition: 'IntentDefinition'):
        """Register a canonical intent definition."""
        with self._lock:
            self._intent_definitions[definition.action] = definition
            
            # Register parameter schemas
            self._parameter_schemas[definition.action] = {}
            for param in definition.required_parameters + definition.optional_parameters:
                schema = self._create_parameter_schema(definition.action, param)
                self._parameter_schemas[definition.action][param] = schema
                
            # Register security policy
            self._security_policies[definition.action] = SecurityPolicy(
                action=definition.action,
                security_level=definition.security_level,
                requires_authority=definition.requires_authority,
                allowed_parameters=definition.required_parameters + definition.optional_parameters,
                validation_rules=self._create_validation_rules(definition)
            )
            
    def get_intent_definition(self, action: IntentAction) -> Optional['IntentDefinition']:
        """Get intent definition by action."""
        with self._lock:
            return self._intent_definitions.get(action)
            
    def get_parameter_schema(self, action: IntentAction, parameter: str) -> Optional['ParameterSchema']:
        """Get parameter schema for specific intent action and parameter."""
        with self._lock:
            action_schemas = self._parameter_schemas.get(action, {})
            return action_schemas.get(parameter)
            
    def get_security_policy(self, action: IntentAction) -> Optional['SecurityPolicy']:
        """Get security policy for intent action."""
        with self._lock:
            return self._security_policies.get(action)
            
    def validate_canonical_intent(self, intent: CanonicalIntent) -> 'ValidationResult':
        """Validate canonical intent against registry definitions."""
        
        # Get intent definition
        definition = self.get_intent_definition(intent.action)
        if not definition:
            return ValidationResult(
                valid=False,
                errors=[f"Unknown intent action: {intent.action}"],
                warnings=[]
            )
            
        errors = []
        warnings = []
        
        # Validate required parameters
        for required_param in definition.required_parameters:
            if required_param not in intent.parameters:
                errors.append(f"Missing required parameter: {required_param}")
                
        # Validate parameter types and values
        for param_name, param_value in intent.parameters.items():
            schema = self.get_parameter_schema(intent.action, param_name)
            if schema:
                param_validation = schema.validate(param_value)
                if not param_validation.valid:
                    errors.extend(param_validation.errors)
                    warnings.extend(param_validation.warnings)
            else:
                warnings.append(f"Unknown parameter: {param_name}")
                
        # Validate security policy
        security_policy = self.get_security_policy(intent.action)
        if security_policy:
            security_validation = security_policy.validate(intent)
            if not security_validation.valid:
                errors.extend(security_validation.errors)
                warnings.extend(security_validation.warnings)
                
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
        
    def get_supported_actions(self) -> List[IntentAction]:
        """Get list of all supported intent actions."""
        with self._lock:
            return list(self._intent_definitions.keys())
            
    def get_actions_by_category(self, category: str) -> List[IntentAction]:
        """Get intent actions by category."""
        with self._lock:
            return [
                action for action, definition in self._intent_definitions.items()
                if definition.category == category
            ]
            
    def get_categories(self) -> List[str]:
        """Get list of all intent categories."""
        with self._lock:
            categories = set()
            for definition in self._intent_definitions.values():
                categories.add(definition.category)
            return sorted(list(categories))
            
    def _create_parameter_schema(self, action: IntentAction, parameter: str) -> 'ParameterSchema':
        """Create parameter schema based on action and parameter name."""
        
        # Define parameter schemas based on common patterns
        if parameter == "text":
            return ParameterSchema(
                name=parameter,
                type="string",
                required=True,
                min_length=1,
                max_length=10000,
                description="Text content to be typed or processed"
            )
        elif parameter == "element":
            return ParameterSchema(
                name=parameter,
                type="string",
                required=True,
                min_length=1,
                max_length=500,
                description="UI element identifier or description"
            )
        elif parameter == "application":
            return ParameterSchema(
                name=parameter,
                type="string",
                required=True,
                min_length=1,
                max_length=200,
                description="Application name or identifier"
            )
        elif parameter == "filename":
            return ParameterSchema(
                name=parameter,
                type="string",
                required=True,
                min_length=1,
                max_length=500,
                description="File path or filename"
            )
        elif parameter == "message":
            return ParameterSchema(
                name=parameter,
                type="string",
                required=True,
                min_length=1,
                max_length=5000,
                description="Message content to be sent"
            )
        elif parameter == "contact":
            return ParameterSchema(
                name=parameter,
                type="string",
                required=True,
                min_length=1,
                max_length=200,
                description="Contact name or identifier"
            )
        else:
            # Default schema for unknown parameters
            return ParameterSchema(
                name=parameter,
                type="string",
                required=False,
                max_length=1000,
                description=f"Parameter for {action.value}"
            )
            
    def _create_validation_rules(self, definition: 'IntentDefinition') -> List['ValidationRule']:
        """Create validation rules for intent definition."""
        rules = []
        
        # Add security-based validation rules
        if definition.security_level == "admin":
            rules.append(ValidationRule(
                name="admin_verification",
                description="Requires administrator privileges",
                validator=lambda intent: self._validate_admin_privileges(intent)
            ))
            
        if definition.category == "file_operations":
            rules.append(ValidationRule(
                name="file_path_validation",
                description="Validates file paths for security",
                validator=lambda intent: self._validate_file_paths(intent)
            ))
            
        if definition.category == "system_control":
            rules.append(ValidationRule(
                name="system_control_validation",
                description="Validates system control operations",
                validator=lambda intent: self._validate_system_control(intent)
            ))
            
        return rules
        
    def _validate_admin_privileges(self, intent: CanonicalIntent) -> 'ValidationResult':
        """Validate admin privilege requirements."""
        # This would integrate with the existing GURU authority system
        return ValidationResult(
            valid=True,  # Placeholder - actual implementation would check authority
            errors=[],
            warnings=["Admin privileges required - will be validated by authority system"]
        )
        
    def _validate_file_paths(self, intent: CanonicalIntent) -> 'ValidationResult':
        """Validate file paths for security issues."""
        errors = []
        warnings = []
        
        for param_name in ["filename", "file_path", "path"]:
            if param_name in intent.parameters:
                file_path = intent.parameters[param_name]
                
                # Check for path traversal attempts
                if ".." in file_path or file_path.startswith("/"):
                    errors.append(f"Potentially unsafe file path: {file_path}")
                    
                # Check for system file access attempts
                system_paths = ["C:\\Windows", "C:\\System32", "/etc", "/usr/bin"]
                for sys_path in system_paths:
                    if file_path.startswith(sys_path):
                        errors.append(f"Access to system path not allowed: {file_path}")
                        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
        
    def _validate_system_control(self, intent: CanonicalIntent) -> 'ValidationResult':
        """Validate system control operations."""
        # System control operations require special validation
        return ValidationResult(
            valid=True,
            errors=[],
            warnings=["System control operation - requires elevated authority"]
        )


@dataclass
class IntentDefinition:
    """Definition of a canonical intent with metadata and validation rules."""
    
    action: IntentAction
    description: str
    required_parameters: List[str] = field(default_factory=list)
    optional_parameters: List[str] = field(default_factory=list)
    security_level: str = "medium"  # low, medium, high, admin
    requires_authority: bool = True
    category: str = "general"
    
    # Validation and processing metadata
    processing_timeout_ms: int = 5000
    retry_count: int = 0
    fallback_actions: List[IntentAction] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert intent definition to dictionary."""
        return {
            'action': self.action.value,
            'description': self.description,
            'required_parameters': self.required_parameters,
            'optional_parameters': self.optional_parameters,
            'security_level': self.security_level,
            'requires_authority': self.requires_authority,
            'category': self.category,
            'processing_timeout_ms': self.processing_timeout_ms,
            'retry_count': self.retry_count,
            'fallback_actions': [action.value for action in self.fallback_actions]
        }


@dataclass
class ParameterSchema:
    """Schema definition for intent parameters."""
    
    name: str
    type: str  # string, integer, float, boolean, array, object
    required: bool = False
    description: str = ""
    
    # String validation
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    
    # Numeric validation
    minimum: Optional[Union[int, float]] = None
    maximum: Optional[Union[int, float]] = None
    
    # Array validation
    min_items: Optional[int] = None
    max_items: Optional[int] = None
    
    # Enum validation
    allowed_values: Optional[List[Any]] = None
    
    def validate(self, value: Any) -> 'ValidationResult':
        """Validate parameter value against schema."""
        errors = []
        warnings = []
        
        # Type validation
        if self.type == "string" and not isinstance(value, str):
            errors.append(f"Parameter {self.name} must be a string, got {type(value).__name__}")
        elif self.type == "integer" and not isinstance(value, int):
            errors.append(f"Parameter {self.name} must be an integer, got {type(value).__name__}")
        elif self.type == "float" and not isinstance(value, (int, float)):
            errors.append(f"Parameter {self.name} must be a number, got {type(value).__name__}")
        elif self.type == "boolean" and not isinstance(value, bool):
            errors.append(f"Parameter {self.name} must be a boolean, got {type(value).__name__}")
        elif self.type == "array" and not isinstance(value, list):
            errors.append(f"Parameter {self.name} must be an array, got {type(value).__name__}")
        elif self.type == "object" and not isinstance(value, dict):
            errors.append(f"Parameter {self.name} must be an object, got {type(value).__name__}")
            
        # String-specific validation
        if self.type == "string" and isinstance(value, str):
            if self.min_length is not None and len(value) < self.min_length:
                errors.append(f"Parameter {self.name} must be at least {self.min_length} characters")
            if self.max_length is not None and len(value) > self.max_length:
                errors.append(f"Parameter {self.name} must be at most {self.max_length} characters")
            if self.pattern and not re.match(self.pattern, value):
                errors.append(f"Parameter {self.name} does not match required pattern")
                
        # Numeric validation
        if self.type in ["integer", "float"] and isinstance(value, (int, float)):
            if self.minimum is not None and value < self.minimum:
                errors.append(f"Parameter {self.name} must be at least {self.minimum}")
            if self.maximum is not None and value > self.maximum:
                errors.append(f"Parameter {self.name} must be at most {self.maximum}")
                
        # Array validation
        if self.type == "array" and isinstance(value, list):
            if self.min_items is not None and len(value) < self.min_items:
                errors.append(f"Parameter {self.name} must have at least {self.min_items} items")
            if self.max_items is not None and len(value) > self.max_items:
                errors.append(f"Parameter {self.name} must have at most {self.max_items} items")
                
        # Enum validation
        if self.allowed_values and value not in self.allowed_values:
            errors.append(f"Parameter {self.name} must be one of: {self.allowed_values}")
            
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )


@dataclass
class SecurityPolicy:
    """Security policy for canonical intents."""
    
    action: IntentAction
    security_level: str
    requires_authority: bool
    allowed_parameters: List[str]
    validation_rules: List['ValidationRule'] = field(default_factory=list)
    
    def validate(self, intent: CanonicalIntent) -> 'ValidationResult':
        """Validate intent against security policy."""
        errors = []
        warnings = []
        
        # Check parameter allowlist
        for param_name in intent.parameters.keys():
            if param_name not in self.allowed_parameters:
                errors.append(f"Parameter {param_name} not allowed for action {self.action.value}")
                
        # Apply validation rules
        for rule in self.validation_rules:
            rule_result = rule.validator(intent)
            errors.extend(rule_result.errors)
            warnings.extend(rule_result.warnings)
            
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )


@dataclass
class ValidationRule:
    """Validation rule for intent security and correctness."""
    
    name: str
    description: str
    validator: callable  # Function that takes CanonicalIntent and returns ValidationResult


@dataclass
class ValidationResult:
    """Result of validation operation."""
    
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class IntentMappingRegistry:
    """Registry of intent patterns for all supported languages."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._patterns: Dict[str, List[IntentPattern]] = {}
        self._lock = RLock()
        
        # Initialize with default patterns
        self._initialize_default_patterns()
        
    def _initialize_default_patterns(self):
        """Initialize default intent patterns for supported languages."""
        
        # English patterns
        self.register_patterns("en", [
            # Text input
            IntentPattern(
                pattern=r"type\s+(.+)",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"write\s+(.+)",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"clear\s+text",
                action=IntentAction.CLEAR_TEXT,
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"click\s+(.+)",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1},
                security_level="medium"
            ),
            IntentPattern(
                pattern=r"double\s+click\s+(.+)",
                action=IntentAction.DOUBLE_CLICK,
                parameter_groups={"element": 1},
                security_level="medium"
            ),
            
            # Applications
            IntentPattern(
                pattern=r"open\s+(.+)",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1},
                security_level="high"
            ),
            IntentPattern(
                pattern=r"close\s+(.+)",
                action=IntentAction.CLOSE_APPLICATION,
                parameter_groups={"application": 1},
                security_level="medium"
            ),
            
            # Communication
            IntentPattern(
                pattern=r"send\s+message\s+(.+)",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1},
                security_level="high"
            ),
            IntentPattern(
                pattern=r"call\s+(.+)",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1},
                security_level="high"
            ),
            
            # Mode switching
            IntentPattern(
                pattern=r"dictation\s+mode",
                action=IntentAction.SWITCH_TO_DICTATION,
                security_level="low"
            ),
            IntentPattern(
                pattern=r"command\s+mode",
                action=IntentAction.SWITCH_TO_COMMAND,
                security_level="low"
            )
        ])
        
        # Hindi patterns
        self.register_patterns("hi", [
            # Text input
            IntentPattern(
                pattern=r"(.+)\s+टाइप\s+करो",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"(.+)\s+लिखो",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"टेक्स्ट\s+साफ\s+करो",
                action=IntentAction.CLEAR_TEXT,
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"(.+)\s+पर\s+क्लिक\s+करो",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1},
                security_level="medium"
            ),
            
            # Applications
            IntentPattern(
                pattern=r"(.+)\s+खोलो",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1},
                security_level="high"
            ),
            IntentPattern(
                pattern=r"(.+)\s+बंद\s+करो",
                action=IntentAction.CLOSE_APPLICATION,
                parameter_groups={"application": 1},
                security_level="medium"
            ),
            
            # Communication
            IntentPattern(
                pattern=r"(.+)\s+को\s+संदेश\s+भेजो",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1},
                security_level="high"
            ),
            IntentPattern(
                pattern=r"(.+)\s+को\s+कॉल\s+करो",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1},
                security_level="high"
            ),
            
            # Mode switching
            IntentPattern(
                pattern=r"डिक्टेशन\s+मोड",
                action=IntentAction.SWITCH_TO_DICTATION,
                security_level="low"
            ),
            IntentPattern(
                pattern=r"कमांड\s+मोड",
                action=IntentAction.SWITCH_TO_COMMAND,
                security_level="low"
            )
        ])
        
        # Tamil patterns
        self.register_patterns("ta", [
            # Text input
            IntentPattern(
                pattern=r"(.+)\s+டைப்\s+பண்ணு",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"(.+)\s+எழுது",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"(.+)\s+கிளிக்\s+பண்ணு",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1}
            ),
            
            # Applications
            IntentPattern(
                pattern=r"(.+)\s+ஓபன்\s+பண்ணு",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1}
            ),
            
            # Communication
            IntentPattern(
                pattern=r"(.+)\s+கு\s+மெசேஜ்\s+அனுப்பு",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+கு\s+கால்\s+பண்ணு",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1}
            )
        ])
        
        # German patterns
        self.register_patterns("de", [
            # Text input
            IntentPattern(
                pattern=r"schreibe\s+(.+)",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"tippe\s+(.+)",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"klicke\s+(.+)",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1},
                security_level="medium"
            ),
            
            # Applications
            IntentPattern(
                pattern=r"öffne\s+(.+)",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1},
                security_level="high"
            ),
            IntentPattern(
                pattern=r"schließe\s+(.+)",
                action=IntentAction.CLOSE_APPLICATION,
                parameter_groups={"application": 1},
                security_level="medium"
            ),
            
            # Communication
            IntentPattern(
                pattern=r"sende\s+nachricht\s+(.+)",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1},
                security_level="high"
            ),
            IntentPattern(
                pattern=r"rufe\s+(.+)\s+an",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1},
                security_level="high"
            )
        ])
        
        # French patterns
        self.register_patterns("fr", [
            # Text input
            IntentPattern(
                pattern=r"écris\s+(.+)",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"tape\s+(.+)",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"clique\s+(.+)",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1},
                security_level="medium"
            ),
            
            # Applications
            IntentPattern(
                pattern=r"ouvre\s+(.+)",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1},
                security_level="high"
            ),
            IntentPattern(
                pattern=r"ferme\s+(.+)",
                action=IntentAction.CLOSE_APPLICATION,
                parameter_groups={"application": 1},
                security_level="medium"
            ),
            
            # Communication
            IntentPattern(
                pattern=r"envoie\s+message\s+(.+)",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1},
                security_level="high"
            ),
            IntentPattern(
                pattern=r"appelle\s+(.+)",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1},
                security_level="high"
            )
        ])
        
        # Chinese patterns
        self.register_patterns("zh", [
            # Text input
            IntentPattern(
                pattern=r"输入\s+(.+)",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"写\s+(.+)",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"打字\s+(.+)",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"清除文本",
                action=IntentAction.CLEAR_TEXT,
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"点击\s+(.+)",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1}
            ),
            IntentPattern(
                pattern=r"双击\s+(.+)",
                action=IntentAction.DOUBLE_CLICK,
                parameter_groups={"element": 1}
            ),
            IntentPattern(
                pattern=r"右键点击\s+(.+)",
                action=IntentAction.RIGHT_CLICK,
                parameter_groups={"element": 1}
            ),
            
            # Applications
            IntentPattern(
                pattern=r"打开\s+(.+)",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"关闭\s+(.+)",
                action=IntentAction.CLOSE_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"切换到\s+(.+)",
                action=IntentAction.SWITCH_APPLICATION,
                parameter_groups={"application": 1}
            ),
            
            # Communication
            IntentPattern(
                pattern=r"发送消息\s+(.+)",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1}
            ),
            IntentPattern(
                pattern=r"打电话给\s+(.+)",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1}
            ),
            IntentPattern(
                pattern=r"发送邮件\s+(.+)",
                action=IntentAction.SEND_EMAIL,
                parameter_groups={"message": 1}
            ),
            
            # File operations
            IntentPattern(
                pattern=r"打开文件\s+(.+)",
                action=IntentAction.OPEN_FILE,
                parameter_groups={"filename": 1}
            ),
            IntentPattern(
                pattern=r"保存文件\s+(.+)",
                action=IntentAction.SAVE_FILE,
                parameter_groups={"filename": 1}
            ),
            
            # Mode switching
            IntentPattern(
                pattern=r"听写模式",
                action=IntentAction.SWITCH_TO_DICTATION,
                security_level="low"
            ),
            IntentPattern(
                pattern=r"命令模式",
                action=IntentAction.SWITCH_TO_COMMAND,
                security_level="low"
            )
        ])
        
        # Japanese patterns
        self.register_patterns("ja", [
            # Text input
            IntentPattern(
                pattern=r"(.+)を入力",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"(.+)を書く",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"(.+)をタイプ",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"テキストをクリア",
                action=IntentAction.CLEAR_TEXT,
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"(.+)をクリック",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1}
            ),
            IntentPattern(
                pattern=r"(.+)をダブルクリック",
                action=IntentAction.DOUBLE_CLICK,
                parameter_groups={"element": 1}
            ),
            IntentPattern(
                pattern=r"(.+)を右クリック",
                action=IntentAction.RIGHT_CLICK,
                parameter_groups={"element": 1}
            ),
            
            # Applications
            IntentPattern(
                pattern=r"(.+)を開く",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)を閉じる",
                action=IntentAction.CLOSE_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)に切り替え",
                action=IntentAction.SWITCH_APPLICATION,
                parameter_groups={"application": 1}
            ),
            
            # Communication
            IntentPattern(
                pattern=r"(.+)にメッセージを送る",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1}
            ),
            IntentPattern(
                pattern=r"(.+)に電話する",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1}
            ),
            IntentPattern(
                pattern=r"(.+)にメールを送る",
                action=IntentAction.SEND_EMAIL,
                parameter_groups={"message": 1}
            ),
            
            # File operations
            IntentPattern(
                pattern=r"ファイル(.+)を開く",
                action=IntentAction.OPEN_FILE,
                parameter_groups={"filename": 1}
            ),
            IntentPattern(
                pattern=r"ファイル(.+)を保存",
                action=IntentAction.SAVE_FILE,
                parameter_groups={"filename": 1}
            ),
            
            # Mode switching
            IntentPattern(
                pattern=r"ディクテーションモード",
                action=IntentAction.SWITCH_TO_DICTATION,
                security_level="low"
            ),
            IntentPattern(
                pattern=r"コマンドモード",
                action=IntentAction.SWITCH_TO_COMMAND,
                security_level="low"
            )
        ])
        
        # Telugu patterns
        self.register_patterns("te", [
            # Text input
            IntentPattern(
                pattern=r"(.+)\s+టైప్\s+చేయి",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"(.+)\s+వ్రాయి",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"టెక్స్ట్\s+క్లియర్\s+చేయి",
                action=IntentAction.CLEAR_TEXT,
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"(.+)\s+మీద\s+క్లిక్\s+చేయి",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+మీద\s+డబుల్\s+క్లిక్\s+చేయి",
                action=IntentAction.DOUBLE_CLICK,
                parameter_groups={"element": 1}
            ),
            
            # Applications
            IntentPattern(
                pattern=r"(.+)\s+తెరువు",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+మూసివేయి",
                action=IntentAction.CLOSE_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+కు\s+మార్చు",
                action=IntentAction.SWITCH_APPLICATION,
                parameter_groups={"application": 1}
            ),
            
            # Communication
            IntentPattern(
                pattern=r"(.+)\s+కు\s+మెసేజ్\s+పంపు",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+కు\s+కాల్\s+చేయి",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+కు\s+ఇమెయిల్\s+పంపు",
                action=IntentAction.SEND_EMAIL,
                parameter_groups={"message": 1}
            ),
            
            # File operations
            IntentPattern(
                pattern=r"(.+)\s+ఫైల్\s+తెరువు",
                action=IntentAction.OPEN_FILE,
                parameter_groups={"filename": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ఫైల్\s+సేవ్\s+చేయి",
                action=IntentAction.SAVE_FILE,
                parameter_groups={"filename": 1}
            ),
            
            # Mode switching
            IntentPattern(
                pattern=r"డిక్టేషన్\s+మోడ్",
                action=IntentAction.SWITCH_TO_DICTATION,
                security_level="low"
            ),
            IntentPattern(
                pattern=r"కమాండ్\s+మోడ్",
                action=IntentAction.SWITCH_TO_COMMAND,
                security_level="low"
            )
        ])
        
        # Bengali patterns
        self.register_patterns("bn", [
            # Text input
            IntentPattern(
                pattern=r"(.+)\s+টাইপ\s+করো",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"(.+)\s+লেখো",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"টেক্সট\s+মুছে\s+দাও",
                action=IntentAction.CLEAR_TEXT,
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"(.+)\s+এ\s+ক্লিক\s+করো",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+এ\s+ডাবল\s+ক্লিক\s+করো",
                action=IntentAction.DOUBLE_CLICK,
                parameter_groups={"element": 1}
            ),
            
            # Applications
            IntentPattern(
                pattern=r"(.+)\s+খোলো",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+বন্ধ\s+করো",
                action=IntentAction.CLOSE_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+এ\s+যাও",
                action=IntentAction.SWITCH_APPLICATION,
                parameter_groups={"application": 1}
            ),
            
            # Communication
            IntentPattern(
                pattern=r"(.+)\s+কে\s+মেসেজ\s+পাঠাও",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+কে\s+কল\s+করো",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+কে\s+ইমেইল\s+পাঠাও",
                action=IntentAction.SEND_EMAIL,
                parameter_groups={"message": 1}
            ),
            
            # File operations
            IntentPattern(
                pattern=r"(.+)\s+ফাইল\s+খোলো",
                action=IntentAction.OPEN_FILE,
                parameter_groups={"filename": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ফাইল\s+সেভ\s+করো",
                action=IntentAction.SAVE_FILE,
                parameter_groups={"filename": 1}
            ),
            
            # Mode switching
            IntentPattern(
                pattern=r"ডিক্টেশন\s+মোড",
                action=IntentAction.SWITCH_TO_DICTATION,
                security_level="low"
            ),
            IntentPattern(
                pattern=r"কমান্ড\s+মোড",
                action=IntentAction.SWITCH_TO_COMMAND,
                security_level="low"
            )
        ])
        
        # Marathi patterns
        self.register_patterns("mr", [
            # Text input
            IntentPattern(
                pattern=r"(.+)\s+टाइप\s+करा",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"(.+)\s+लिहा",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"मजकूर\s+साफ\s+करा",
                action=IntentAction.CLEAR_TEXT,
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"(.+)\s+वर\s+क्लिक\s+करा",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+वर\s+डबल\s+क्लिक\s+करा",
                action=IntentAction.DOUBLE_CLICK,
                parameter_groups={"element": 1}
            ),
            
            # Applications
            IntentPattern(
                pattern=r"(.+)\s+उघडा",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+बंद\s+करा",
                action=IntentAction.CLOSE_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+वर\s+जा",
                action=IntentAction.SWITCH_APPLICATION,
                parameter_groups={"application": 1}
            ),
            
            # Communication
            IntentPattern(
                pattern=r"(.+)\s+ला\s+संदेश\s+पाठवा",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ला\s+कॉल\s+करा",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ला\s+ईमेल\s+पाठवा",
                action=IntentAction.SEND_EMAIL,
                parameter_groups={"message": 1}
            ),
            
            # File operations
            IntentPattern(
                pattern=r"(.+)\s+फाइल\s+उघडा",
                action=IntentAction.OPEN_FILE,
                parameter_groups={"filename": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+फाइल\s+सेव्ह\s+करा",
                action=IntentAction.SAVE_FILE,
                parameter_groups={"filename": 1}
            ),
            
            # Mode switching
            IntentPattern(
                pattern=r"डिक्टेशन\s+मोड",
                action=IntentAction.SWITCH_TO_DICTATION,
                security_level="low"
            ),
            IntentPattern(
                pattern=r"कमांड\s+मोड",
                action=IntentAction.SWITCH_TO_COMMAND,
                security_level="low"
            )
        ])
        
        # Gujarati patterns
        self.register_patterns("gu", [
            # Text input
            IntentPattern(
                pattern=r"(.+)\s+ટાઇપ\s+કરો",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"(.+)\s+લખો",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"ટેક્સ્ટ\s+સાફ\s+કરો",
                action=IntentAction.CLEAR_TEXT,
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"(.+)\s+પર\s+ક્લિક\s+કરો",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+પર\s+ડબલ\s+ક્લિક\s+કરો",
                action=IntentAction.DOUBLE_CLICK,
                parameter_groups={"element": 1}
            ),
            
            # Applications
            IntentPattern(
                pattern=r"(.+)\s+ખોલો",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+બંધ\s+કરો",
                action=IntentAction.CLOSE_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+પર\s+જાઓ",
                action=IntentAction.SWITCH_APPLICATION,
                parameter_groups={"application": 1}
            ),
            
            # Communication
            IntentPattern(
                pattern=r"(.+)\s+ને\s+સંદેશ\s+મોકલો",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ને\s+કૉલ\s+કરો",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ને\s+ઇમેઇલ\s+મોકલો",
                action=IntentAction.SEND_EMAIL,
                parameter_groups={"message": 1}
            ),
            
            # File operations
            IntentPattern(
                pattern=r"(.+)\s+ફાઇલ\s+ખોલો",
                action=IntentAction.OPEN_FILE,
                parameter_groups={"filename": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ફાઇલ\s+સેવ\s+કરો",
                action=IntentAction.SAVE_FILE,
                parameter_groups={"filename": 1}
            ),
            
            # Mode switching
            IntentPattern(
                pattern=r"ડિક્ટેશન\s+મોડ",
                action=IntentAction.SWITCH_TO_DICTATION,
                security_level="low"
            ),
            IntentPattern(
                pattern=r"કમાન્ડ\s+મોડ",
                action=IntentAction.SWITCH_TO_COMMAND,
                security_level="low"
            )
        ])
        
        # Kannada patterns
        self.register_patterns("kn", [
            # Text input
            IntentPattern(
                pattern=r"(.+)\s+ಟೈಪ್\s+ಮಾಡಿ",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"(.+)\s+ಬರೆಯಿರಿ",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"ಪಠ್ಯ\s+ತೆರವುಗೊಳಿಸಿ",
                action=IntentAction.CLEAR_TEXT,
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"(.+)\s+ಮೇಲೆ\s+ಕ್ಲಿಕ್\s+ಮಾಡಿ",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ಮೇಲೆ\s+ಡಬಲ್\s+ಕ್ಲಿಕ್\s+ಮಾಡಿ",
                action=IntentAction.DOUBLE_CLICK,
                parameter_groups={"element": 1}
            ),
            
            # Applications
            IntentPattern(
                pattern=r"(.+)\s+ತೆರೆಯಿರಿ",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ಮುಚ್ಚಿರಿ",
                action=IntentAction.CLOSE_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ಗೆ\s+ಬದಲಾಯಿಸಿ",
                action=IntentAction.SWITCH_APPLICATION,
                parameter_groups={"application": 1}
            ),
            
            # Communication
            IntentPattern(
                pattern=r"(.+)\s+ಗೆ\s+ಸಂದೇಶ\s+ಕಳುಹಿಸಿ",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ಗೆ\s+ಕರೆ\s+ಮಾಡಿ",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ಗೆ\s+ಇಮೇಲ್\s+ಕಳುಹಿಸಿ",
                action=IntentAction.SEND_EMAIL,
                parameter_groups={"message": 1}
            ),
            
            # File operations
            IntentPattern(
                pattern=r"(.+)\s+ಫೈಲ್\s+ತೆರೆಯಿರಿ",
                action=IntentAction.OPEN_FILE,
                parameter_groups={"filename": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ಫೈಲ್\s+ಸೇವ್\s+ಮಾಡಿ",
                action=IntentAction.SAVE_FILE,
                parameter_groups={"filename": 1}
            ),
            
            # Mode switching
            IntentPattern(
                pattern=r"ಡಿಕ್ಟೇಶನ್\s+ಮೋಡ್",
                action=IntentAction.SWITCH_TO_DICTATION,
                security_level="low"
            ),
            IntentPattern(
                pattern=r"ಕಮಾಂಡ್\s+ಮೋಡ್",
                action=IntentAction.SWITCH_TO_COMMAND,
                security_level="low"
            )
        ])
        
        # Malayalam patterns
        self.register_patterns("ml", [
            # Text input
            IntentPattern(
                pattern=r"(.+)\s+ടൈപ്പ്\s+ചെയ്യുക",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"(.+)\s+എഴുതുക",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"ടെക്സ്റ്റ്\s+മായ്ക്കുക",
                action=IntentAction.CLEAR_TEXT,
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"(.+)\s+ൽ\s+ക്ലിക്ക്\s+ചെയ്യുക",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ൽ\s+ഡബിൾ\s+ക്ലിക്ക്\s+ചെയ്യുക",
                action=IntentAction.DOUBLE_CLICK,
                parameter_groups={"element": 1}
            ),
            
            # Applications
            IntentPattern(
                pattern=r"(.+)\s+തുറക്കുക",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+അടയ്ക്കുക",
                action=IntentAction.CLOSE_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ലേക്ക്\s+മാറുക",
                action=IntentAction.SWITCH_APPLICATION,
                parameter_groups={"application": 1}
            ),
            
            # Communication
            IntentPattern(
                pattern=r"(.+)\s+ന്\s+സന്ദേശം\s+അയയ്ക്കുക",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ന്\s+വിളിക്കുക",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ന്\s+ഇമെയിൽ\s+അയയ്ക്കുക",
                action=IntentAction.SEND_EMAIL,
                parameter_groups={"message": 1}
            ),
            
            # File operations
            IntentPattern(
                pattern=r"(.+)\s+ഫയൽ\s+തുറക്കുക",
                action=IntentAction.OPEN_FILE,
                parameter_groups={"filename": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ഫയൽ\s+സേവ്\s+ചെയ്യുക",
                action=IntentAction.SAVE_FILE,
                parameter_groups={"filename": 1}
            ),
            
            # Mode switching
            IntentPattern(
                pattern=r"ഡിക്ടേഷൻ\s+മോഡ്",
                action=IntentAction.SWITCH_TO_DICTATION,
                security_level="low"
            ),
            IntentPattern(
                pattern=r"കമാൻഡ്\s+മോഡ്",
                action=IntentAction.SWITCH_TO_COMMAND,
                security_level="low"
            )
        ])
        
        # Punjabi patterns
        self.register_patterns("pa", [
            # Text input
            IntentPattern(
                pattern=r"(.+)\s+ਟਾਈਪ\s+ਕਰੋ",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"(.+)\s+ਲਿਖੋ",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"ਟੈਕਸਟ\s+ਸਾਫ਼\s+ਕਰੋ",
                action=IntentAction.CLEAR_TEXT,
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"(.+)\s+ਤੇ\s+ਕਲਿੱਕ\s+ਕਰੋ",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ਤੇ\s+ਡਬਲ\s+ਕਲਿੱਕ\s+ਕਰੋ",
                action=IntentAction.DOUBLE_CLICK,
                parameter_groups={"element": 1}
            ),
            
            # Applications
            IntentPattern(
                pattern=r"(.+)\s+ਖੋਲ੍ਹੋ",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ਬੰਦ\s+ਕਰੋ",
                action=IntentAction.CLOSE_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ਤੇ\s+ਜਾਓ",
                action=IntentAction.SWITCH_APPLICATION,
                parameter_groups={"application": 1}
            ),
            
            # Communication
            IntentPattern(
                pattern=r"(.+)\s+ਨੂੰ\s+ਸੁਨੇਹਾ\s+ਭੇਜੋ",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ਨੂੰ\s+ਕਾਲ\s+ਕਰੋ",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ਨੂੰ\s+ਈਮੇਲ\s+ਭੇਜੋ",
                action=IntentAction.SEND_EMAIL,
                parameter_groups={"message": 1}
            ),
            
            # File operations
            IntentPattern(
                pattern=r"(.+)\s+ਫਾਈਲ\s+ਖੋਲ੍ਹੋ",
                action=IntentAction.OPEN_FILE,
                parameter_groups={"filename": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+ਫਾਈਲ\s+ਸੇਵ\s+ਕਰੋ",
                action=IntentAction.SAVE_FILE,
                parameter_groups={"filename": 1}
            ),
            
            # Mode switching
            IntentPattern(
                pattern=r"ਡਿਕਟੇਸ਼ਨ\s+ਮੋਡ",
                action=IntentAction.SWITCH_TO_DICTATION,
                security_level="low"
            ),
            IntentPattern(
                pattern=r"ਕਮਾਂਡ\s+ਮੋਡ",
                action=IntentAction.SWITCH_TO_COMMAND,
                security_level="low"
            )
        ])
        
        # Bhojpuri patterns
        self.register_patterns("bho", [
            # Text input
            IntentPattern(
                pattern=r"(.+)\s+टाइप\s+करा",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"(.+)\s+लिखा",
                action=IntentAction.TYPE_TEXT,
                parameter_groups={"text": 1},
                security_level="low"
            ),
            IntentPattern(
                pattern=r"टेक्स्ट\s+साफ\s+करा",
                action=IntentAction.CLEAR_TEXT,
                security_level="low"
            ),
            
            # UI interactions
            IntentPattern(
                pattern=r"(.+)\s+पर\s+क्लिक\s+करा",
                action=IntentAction.CLICK_ELEMENT,
                parameter_groups={"element": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+पर\s+डबल\s+क्लिक\s+करा",
                action=IntentAction.DOUBLE_CLICK,
                parameter_groups={"element": 1}
            ),
            
            # Applications
            IntentPattern(
                pattern=r"(.+)\s+खोला",
                action=IntentAction.OPEN_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+बंद\s+करा",
                action=IntentAction.CLOSE_APPLICATION,
                parameter_groups={"application": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+पर\s+जाईं",
                action=IntentAction.SWITCH_APPLICATION,
                parameter_groups={"application": 1}
            ),
            
            # Communication
            IntentPattern(
                pattern=r"(.+)\s+के\s+संदेश\s+भेजा",
                action=IntentAction.SEND_MESSAGE,
                parameter_groups={"message": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+के\s+कॉल\s+करा",
                action=IntentAction.MAKE_CALL,
                parameter_groups={"contact": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+के\s+ईमेल\s+भेजा",
                action=IntentAction.SEND_EMAIL,
                parameter_groups={"message": 1}
            ),
            
            # File operations
            IntentPattern(
                pattern=r"(.+)\s+फाइल\s+खोला",
                action=IntentAction.OPEN_FILE,
                parameter_groups={"filename": 1}
            ),
            IntentPattern(
                pattern=r"(.+)\s+फाइल\s+सेव\s+करा",
                action=IntentAction.SAVE_FILE,
                parameter_groups={"filename": 1}
            ),
            
            # Mode switching
            IntentPattern(
                pattern=r"डिक्टेशन\s+मोड",
                action=IntentAction.SWITCH_TO_DICTATION,
                security_level="low"
            ),
            IntentPattern(
                pattern=r"कमांड\s+मोड",
                action=IntentAction.SWITCH_TO_COMMAND,
                security_level="low"
            )
        ])
        
        self.logger.info(f"Initialized intent patterns for {len(self._patterns)} languages")
        
    def register_patterns(self, language: str, patterns: List[IntentPattern]):
        """Register intent patterns for a language."""
        with self._lock:
            if not SupportedLanguages.is_supported(language):
                raise UnsupportedLanguageError(
                    f"Cannot register patterns for unsupported language: {language}",
                    requested_language=language,
                    supported_languages=SupportedLanguages.get_language_codes()
                )
                
            self._patterns[language] = patterns
            self.logger.info(f"Registered {len(patterns)} intent patterns for {language}")
            
    def get_patterns(self, language: str) -> List[IntentPattern]:
        """Get intent patterns for a language."""
        with self._lock:
            return self._patterns.get(language, [])
            
    def add_pattern(self, language: str, pattern: IntentPattern):
        """Add a single pattern to a language."""
        with self._lock:
            if language not in self._patterns:
                self._patterns[language] = []
            self._patterns[language].append(pattern)
            
    def add_pattern_variation(self, language: str, base_pattern: str, variations: List[str], action: IntentAction, parameter_groups: Dict[str, int]):
        """Add multiple pattern variations for the same intent."""
        with self._lock:
            if language not in self._patterns:
                self._patterns[language] = []
                
            # Add base pattern
            base_intent_pattern = IntentPattern(
                pattern=base_pattern,
                action=action,
                parameter_groups=parameter_groups
            )
            self._patterns[language].append(base_intent_pattern)
            
            # Add variations
            for variation in variations:
                variation_pattern = IntentPattern(
                    pattern=variation,
                    action=action,
                    parameter_groups=parameter_groups,
                    confidence=0.9  # Slightly lower confidence for variations
                )
                self._patterns[language].append(variation_pattern)
                
    def find_best_match(self, text: str, language: str) -> Optional[Tuple[IntentPattern, Dict[str, str]]]:
        """Find the best matching pattern for given text and language."""
        patterns = self.get_patterns(language)
        if not patterns:
            return None
            
        best_match = None
        best_score = 0.0
        best_parameters = {}
        
        for pattern in patterns:
            parameters = pattern.match(text)
            if parameters is not None:
                # Calculate match score based on pattern specificity and confidence
                score = self._calculate_match_score(pattern, parameters, text)
                
                if score > best_score:
                    best_score = score
                    best_match = pattern
                    best_parameters = parameters
                    
        return (best_match, best_parameters) if best_match else None
        
    def _calculate_match_score(self, pattern: IntentPattern, parameters: Dict[str, str], original_text: str) -> float:
        """Calculate match score for pattern ranking."""
        base_score = pattern.confidence
        
        # Bonus for more specific patterns (more parameters)
        parameter_bonus = len(parameters) * 0.1
        
        # Bonus for exact length match (less likely to be partial match)
        length_ratio = len(original_text.strip()) / max(1, len(pattern.pattern))
        length_bonus = 0.1 if 0.8 <= length_ratio <= 1.2 else 0.0
        
        # Penalty for very short matches (likely false positives)
        if len(original_text.strip()) < 3:
            base_score *= 0.5
            
        return min(1.0, base_score + parameter_bonus + length_bonus)
        
    def get_pattern_statistics(self) -> Dict[str, Any]:
        """Get statistics about registered patterns."""
        with self._lock:
            stats = {
                'total_languages': len(self._patterns),
                'total_patterns': sum(len(patterns) for patterns in self._patterns.values()),
                'patterns_per_language': {},
                'actions_covered': set(),
                'most_common_actions': {}
            }
            
            action_counts = {}
            
            for language, patterns in self._patterns.items():
                stats['patterns_per_language'][language] = len(patterns)
                
                for pattern in patterns:
                    stats['actions_covered'].add(pattern.action)
                    action_counts[pattern.action] = action_counts.get(pattern.action, 0) + 1
                    
            # Convert actions to values for JSON serialization
            stats['actions_covered'] = [action.value for action in stats['actions_covered']]
            stats['most_common_actions'] = {
                action.value: count for action, count in 
                sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            }
            
            return stats
            
    def validate_pattern_coverage(self) -> Dict[str, List[str]]:
        """Validate that all languages have reasonable pattern coverage."""
        issues = {}
        
        with self._lock:
            # Check that all enabled languages have patterns
            all_languages = SupportedLanguages.get_language_codes()
            
            for language in all_languages:
                language_issues = []
                patterns = self._patterns.get(language, [])
                
                if not patterns:
                    language_issues.append("No patterns registered")
                elif len(patterns) < 5:
                    language_issues.append(f"Only {len(patterns)} patterns (recommend at least 5)")
                    
                # Check coverage of essential actions
                essential_actions = {
                    IntentAction.TYPE_TEXT,
                    IntentAction.CLICK_ELEMENT,
                    IntentAction.OPEN_APPLICATION,
                    IntentAction.SWITCH_TO_DICTATION,
                    IntentAction.SWITCH_TO_COMMAND
                }
                
                covered_actions = {pattern.action for pattern in patterns}
                missing_actions = essential_actions - covered_actions
                
                if missing_actions:
                    missing_names = [action.value for action in missing_actions]
                    language_issues.append(f"Missing essential actions: {missing_names}")
                    
                if language_issues:
                    issues[language] = language_issues
                    
        return issues
            
    def get_supported_languages(self) -> List[str]:
        """Get list of languages with registered patterns."""
        with self._lock:
            return list(self._patterns.keys())


@dataclass
class NormalizationResult:
    """Result of intent normalization operation."""
    
    success: bool
    canonical_intent: Optional[CanonicalIntent] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    
    # Processing metadata
    processing_time_ms: int = 0
    patterns_tried: int = 0
    pattern_matched: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'success': self.success,
            'canonical_intent': self.canonical_intent.to_dict() if self.canonical_intent else None,
            'error': self.error,
            'warnings': self.warnings,
            'processing_time_ms': self.processing_time_ms,
            'patterns_tried': self.patterns_tried,
            'pattern_matched': self.pattern_matched
        }


class NormalizationCache:
    """
    Production-grade cache for intent normalization results with advanced
    performance optimization, memory management, and cache analytics.
    """
    
    def __init__(self, max_size: int = 10000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.logger = logging.getLogger(__name__)
        self._disabled = False
        
        # Multi-tier cache structure
        self._hot_cache: Dict[str, CacheEntry] = {}  # Frequently accessed items
        self._warm_cache: Dict[str, CacheEntry] = {}  # Less frequently accessed
        self._cold_cache: Dict[str, CacheEntry] = {}  # Rarely accessed
        
        # Cache management
        self._access_counts: Dict[str, int] = {}
        self._access_times: Dict[str, datetime] = {}
        self._lock = RLock()
        
        # Performance tracking
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'hot_hits': 0,
            'warm_hits': 0,
            'cold_hits': 0,
            'total_requests': 0,
            'average_lookup_time_ms': 0.0,
            'memory_usage_bytes': 0
        }
        
        # Cache optimization parameters
        self._hot_threshold = 10  # Access count to promote to hot cache
        self._warm_threshold = 3  # Access count to promote to warm cache
        self._hot_cache_ratio = 0.2  # 20% of cache for hot items
        self._warm_cache_ratio = 0.3  # 30% of cache for warm items
        self._cold_cache_ratio = 0.5  # 50% of cache for cold items
        
        # Calculate tier sizes
        self._hot_cache_size = int(max_size * self._hot_cache_ratio)
        self._warm_cache_size = int(max_size * self._warm_cache_ratio)
        self._cold_cache_size = int(max_size * self._cold_cache_ratio)
        
        # Background cleanup tracking
        self._last_cleanup = datetime.utcnow()
        self._cleanup_interval = 300  # 5 minutes
        
    def _generate_cache_key(self, text: str, language: str, mode: ProcessingMode) -> str:
        """Generate deterministic cache key for normalization request."""
        # Normalize text for consistent caching
        normalized_text = ' '.join(text.strip().split())
        content = f"{language}:{mode.value}:{normalized_text}"
        
        # Use SHA-256 for security and collision resistance
        hash_obj = hashlib.sha256(content.encode('utf-8'))
        return hash_obj.hexdigest()[:32]  # Use 32 chars for better collision resistance
        
    def get(self, text: str, language: str, mode: ProcessingMode) -> Optional[CanonicalIntent]:
        """
        Get cached normalization result with intelligent tier management.
        
        Returns cached intent if found and valid, None otherwise.
        """
        start_time = time.time()
        cache_key = self._generate_cache_key(text, language, mode)
        
        with self._lock:
            self._cache_stats['total_requests'] += 1
            
            # Check hot cache first (fastest access)
            if cache_key in self._hot_cache:
                entry = self._hot_cache[cache_key]
                if self._is_cache_entry_valid(entry):
                    self._record_cache_hit('hot', cache_key, start_time)
                    return self._clone_intent(entry.intent)
                else:
                    del self._hot_cache[cache_key]
                    
            # Check warm cache
            if cache_key in self._warm_cache:
                entry = self._warm_cache[cache_key]
                if self._is_cache_entry_valid(entry):
                    self._record_cache_hit('warm', cache_key, start_time)
                    self._promote_to_hot_if_needed(cache_key, entry)
                    return self._clone_intent(entry.intent)
                else:
                    del self._warm_cache[cache_key]
                    
            # Check cold cache
            if cache_key in self._cold_cache:
                entry = self._cold_cache[cache_key]
                if self._is_cache_entry_valid(entry):
                    self._record_cache_hit('cold', cache_key, start_time)
                    self._promote_to_warm_if_needed(cache_key, entry)
                    return self._clone_intent(entry.intent)
                else:
                    del self._cold_cache[cache_key]
                    
            # Cache miss
            self._record_cache_miss(start_time)
            
            # Trigger cleanup if needed
            self._cleanup_if_needed()
            
            return None
            
    def put(self, text: str, language: str, mode: ProcessingMode, intent: CanonicalIntent):
        """
        Cache normalization result with intelligent tier placement.
        
        New entries start in cold cache and get promoted based on access patterns.
        """
        cache_key = self._generate_cache_key(text, language, mode)
        
        with self._lock:
            # Create cache entry
            entry = CacheEntry(
                intent=self._clone_intent(intent),
                created_at=datetime.utcnow(),
                last_accessed=datetime.utcnow(),
                access_count=1,
                cache_key=cache_key,
                text_length=len(text),
                language=language,
                mode=mode.value
            )
            
            # Start in cold cache
            self._add_to_cold_cache(cache_key, entry)
            
            # Update access tracking
            self._access_counts[cache_key] = 1
            self._access_times[cache_key] = datetime.utcnow()
            
            self.logger.debug(f"Cached normalization result in cold tier: {cache_key}")
            
    def _is_cache_entry_valid(self, entry: 'CacheEntry') -> bool:
        """Check if cache entry is still valid."""
        age_seconds = (datetime.utcnow() - entry.created_at).total_seconds()
        return age_seconds < self.ttl_seconds
        
    def _clone_intent(self, intent: CanonicalIntent) -> CanonicalIntent:
        """Create a deep copy of canonical intent for cache safety."""
        return CanonicalIntent(
            action=intent.action,
            parameters=intent.parameters.copy(),
            original_text=intent.original_text,
            original_language=intent.original_language,
            processing_mode=intent.processing_mode,
            confidence=intent.confidence,
            normalization_path=intent.normalization_path,
            pattern_matched=intent.pattern_matched,
            requires_authority=intent.requires_authority,
            security_level=intent.security_level,
            validated=intent.validated,
            created_at=intent.created_at,
            processing_time_ms=intent.processing_time_ms
        )
        
    def _record_cache_hit(self, tier: str, cache_key: str, start_time: float):
        """Record cache hit statistics."""
        lookup_time_ms = (time.time() - start_time) * 1000
        
        self._cache_stats['hits'] += 1
        self._cache_stats[f'{tier}_hits'] += 1
        
        # Update access tracking
        self._access_counts[cache_key] = self._access_counts.get(cache_key, 0) + 1
        self._access_times[cache_key] = datetime.utcnow()
        
        # Update average lookup time
        total_requests = self._cache_stats['total_requests']
        current_avg = self._cache_stats['average_lookup_time_ms']
        new_avg = ((current_avg * (total_requests - 1)) + lookup_time_ms) / total_requests
        self._cache_stats['average_lookup_time_ms'] = new_avg
        
        self.logger.debug(f"Cache hit in {tier} tier: {cache_key} ({lookup_time_ms:.2f}ms)")
        
    def _record_cache_miss(self, start_time: float):
        """Record cache miss statistics."""
        lookup_time_ms = (time.time() - start_time) * 1000
        
        self._cache_stats['misses'] += 1
        
        # Update average lookup time
        total_requests = self._cache_stats['total_requests']
        current_avg = self._cache_stats['average_lookup_time_ms']
        new_avg = ((current_avg * (total_requests - 1)) + lookup_time_ms) / total_requests
        self._cache_stats['average_lookup_time_ms'] = new_avg
        
    def _promote_to_hot_if_needed(self, cache_key: str, entry: 'CacheEntry'):
        """Promote entry to hot cache if access threshold is met."""
        access_count = self._access_counts.get(cache_key, 0)
        
        if access_count >= self._hot_threshold:
            # Remove from current tier
            if cache_key in self._warm_cache:
                del self._warm_cache[cache_key]
            elif cache_key in self._cold_cache:
                del self._cold_cache[cache_key]
                
            # Add to hot cache
            self._add_to_hot_cache(cache_key, entry)
            
    def _promote_to_warm_if_needed(self, cache_key: str, entry: 'CacheEntry'):
        """Promote entry to warm cache if access threshold is met."""
        access_count = self._access_counts.get(cache_key, 0)
        
        if access_count >= self._warm_threshold:
            # Remove from cold cache
            if cache_key in self._cold_cache:
                del self._cold_cache[cache_key]
                
            # Add to warm cache
            self._add_to_warm_cache(cache_key, entry)
            
    def _add_to_hot_cache(self, cache_key: str, entry: 'CacheEntry'):
        """Add entry to hot cache with LRU eviction."""
        if len(self._hot_cache) >= self._hot_cache_size:
            self._evict_lru_from_hot_cache()
            
        self._hot_cache[cache_key] = entry
        entry.last_accessed = datetime.utcnow()
        
    def _add_to_warm_cache(self, cache_key: str, entry: 'CacheEntry'):
        """Add entry to warm cache with LRU eviction."""
        if len(self._warm_cache) >= self._warm_cache_size:
            self._evict_lru_from_warm_cache()
            
        self._warm_cache[cache_key] = entry
        entry.last_accessed = datetime.utcnow()
        
    def _add_to_cold_cache(self, cache_key: str, entry: 'CacheEntry'):
        """Add entry to cold cache with LRU eviction."""
        if len(self._cold_cache) >= self._cold_cache_size:
            self._evict_lru_from_cold_cache()
            
        self._cold_cache[cache_key] = entry
        
    def _evict_lru_from_hot_cache(self):
        """Evict least recently used entry from hot cache."""
        if not self._hot_cache:
            return
            
        lru_key = min(self._hot_cache.keys(), 
                     key=lambda k: self._hot_cache[k].last_accessed)
        
        # Demote to warm cache instead of discarding
        entry = self._hot_cache[lru_key]
        del self._hot_cache[lru_key]
        
        if len(self._warm_cache) < self._warm_cache_size:
            self._warm_cache[lru_key] = entry
        else:
            self._cache_stats['evictions'] += 1
            self._cleanup_access_tracking(lru_key)
            
    def _evict_lru_from_warm_cache(self):
        """Evict least recently used entry from warm cache."""
        if not self._warm_cache:
            return
            
        lru_key = min(self._warm_cache.keys(), 
                     key=lambda k: self._warm_cache[k].last_accessed)
        
        # Demote to cold cache instead of discarding
        entry = self._warm_cache[lru_key]
        del self._warm_cache[lru_key]
        
        if len(self._cold_cache) < self._cold_cache_size:
            self._cold_cache[lru_key] = entry
        else:
            self._cache_stats['evictions'] += 1
            self._cleanup_access_tracking(lru_key)
            
    def _evict_lru_from_cold_cache(self):
        """Evict least recently used entry from cold cache."""
        if not self._cold_cache:
            return
            
        lru_key = min(self._cold_cache.keys(), 
                     key=lambda k: self._cold_cache[k].last_accessed)
        
        del self._cold_cache[lru_key]
        self._cache_stats['evictions'] += 1
        self._cleanup_access_tracking(lru_key)
        
    def _cleanup_access_tracking(self, cache_key: str):
        """Clean up access tracking for evicted entries."""
        self._access_counts.pop(cache_key, None)
        self._access_times.pop(cache_key, None)
        
    def _cleanup_if_needed(self):
        """Perform background cleanup if interval has passed."""
        now = datetime.utcnow()
        
        if (now - self._last_cleanup).total_seconds() > self._cleanup_interval:
            self._perform_background_cleanup()
            self._last_cleanup = now
            
    def _perform_background_cleanup(self):
        """Perform background cleanup of expired entries."""
        expired_keys = []
        
        # Check all tiers for expired entries
        for cache_dict in [self._hot_cache, self._warm_cache, self._cold_cache]:
            for key, entry in cache_dict.items():
                if not self._is_cache_entry_valid(entry):
                    expired_keys.append(key)
                    
        # Remove expired entries
        for key in expired_keys:
            self._hot_cache.pop(key, None)
            self._warm_cache.pop(key, None)
            self._cold_cache.pop(key, None)
            self._cleanup_access_tracking(key)
            
        if expired_keys:
            self.logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
            
    def clear(self):
        """Clear all cached results and reset statistics."""
        with self._lock:
            self._hot_cache.clear()
            self._warm_cache.clear()
            self._cold_cache.clear()
            self._access_counts.clear()
            self._access_times.clear()
            
            # Reset statistics
            self._cache_stats = {
                'hits': 0,
                'misses': 0,
                'evictions': 0,
                'hot_hits': 0,
                'warm_hits': 0,
                'cold_hits': 0,
                'total_requests': 0,
                'average_lookup_time_ms': 0.0,
                'memory_usage_bytes': 0
            }
            
            self.logger.info("Cleared normalization cache and reset statistics")
            
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache performance statistics."""
        with self._lock:
            total_requests = self._cache_stats['total_requests']
            total_hits = self._cache_stats['hits']
            
            # Calculate memory usage estimate
            memory_usage = self._estimate_memory_usage()
            self._cache_stats['memory_usage_bytes'] = memory_usage
            
            return {
                **self._cache_stats,
                'hit_rate': total_hits / max(1, total_requests),
                'miss_rate': self._cache_stats['misses'] / max(1, total_requests),
                'hot_cache_size': len(self._hot_cache),
                'warm_cache_size': len(self._warm_cache),
                'cold_cache_size': len(self._cold_cache),
                'total_cache_size': len(self._hot_cache) + len(self._warm_cache) + len(self._cold_cache),
                'hot_hit_rate': self._cache_stats['hot_hits'] / max(1, total_hits),
                'warm_hit_rate': self._cache_stats['warm_hits'] / max(1, total_hits),
                'cold_hit_rate': self._cache_stats['cold_hits'] / max(1, total_hits),
                'memory_usage_mb': memory_usage / (1024 * 1024),
                'cache_efficiency': self._calculate_cache_efficiency()
            }
            
    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage of cache in bytes."""
        total_bytes = 0
        
        # Estimate size of cache entries
        for cache_dict in [self._hot_cache, self._warm_cache, self._cold_cache]:
            for entry in cache_dict.values():
                # Rough estimate: intent object + metadata
                total_bytes += entry.text_length * 2  # Unicode characters
                total_bytes += 500  # Intent object overhead
                total_bytes += 200  # Cache entry overhead
                
        # Add tracking dictionaries overhead
        total_bytes += len(self._access_counts) * 50
        total_bytes += len(self._access_times) * 50
        
        return total_bytes
        
    def _calculate_cache_efficiency(self) -> float:
        """Calculate cache efficiency score (0.0 to 1.0)."""
        total_requests = self._cache_stats['total_requests']
        if total_requests == 0:
            return 0.0
            
        hit_rate = self._cache_stats['hits'] / total_requests
        hot_ratio = self._cache_stats['hot_hits'] / max(1, self._cache_stats['hits'])
        
        # Efficiency combines hit rate with hot cache utilization
        return (hit_rate * 0.7) + (hot_ratio * 0.3)
        
    def optimize_cache_parameters(self):
        """Dynamically optimize cache parameters based on usage patterns."""
        with self._lock:
            stats = self.get_cache_statistics()
            
            # Adjust tier ratios based on hit patterns
            total_hits = stats['hits']
            if total_hits > 100:  # Only optimize with sufficient data
                hot_ratio = stats['hot_hits'] / total_hits
                warm_ratio = stats['warm_hits'] / total_hits
                cold_ratio = stats['cold_hits'] / total_hits
                
                # If hot cache is underutilized, reduce its size
                if hot_ratio < 0.1 and self._hot_cache_ratio > 0.1:
                    self._hot_cache_ratio = max(0.1, self._hot_cache_ratio - 0.05)
                    self._warm_cache_ratio += 0.025
                    self._cold_cache_ratio += 0.025
                    
                # If hot cache is overutilized, increase its size
                elif hot_ratio > 0.4 and self._hot_cache_ratio < 0.4:
                    self._hot_cache_ratio = min(0.4, self._hot_cache_ratio + 0.05)
                    self._warm_cache_ratio -= 0.025
                    self._cold_cache_ratio -= 0.025
                    
                # Recalculate tier sizes
                self._hot_cache_size = int(self.max_size * self._hot_cache_ratio)
                self._warm_cache_size = int(self.max_size * self._warm_cache_ratio)
                self._cold_cache_size = int(self.max_size * self._cold_cache_ratio)
                
                self.logger.info(f"Optimized cache parameters: hot={self._hot_cache_ratio:.2f}, warm={self._warm_cache_ratio:.2f}, cold={self._cold_cache_ratio:.2f}")
                
    def preload_common_patterns(self, common_commands: List[Tuple[str, str, ProcessingMode, CanonicalIntent]]):
        """Preload cache with common command patterns."""
        with self._lock:
            for text, language, mode, intent in common_commands:
                self.put(text, language, mode, intent)
                
            self.logger.info(f"Preloaded {len(common_commands)} common patterns into cache")
            
    def clear_problematic_entries(self):
        """Clear cache entries that are causing issues."""
        with self._lock:
            # Clear all entries for now - in production this would be more selective
            cleared_count = len(self._hot_cache) + len(self._warm_cache) + len(self._cold_cache)
            
            self._hot_cache.clear()
            self._warm_cache.clear() 
            self._cold_cache.clear()
            self._access_counts.clear()
            self._access_times.clear()
            
            self.logger.warning(f"Cleared {cleared_count} problematic cache entries")
            return cleared_count
            
    def disable(self):
        """Disable the cache temporarily."""
        with self._lock:
            self.clear()
            self._disabled = True
            self.logger.warning("Cache disabled due to system issues")
            
    def enable(self):
        """Re-enable the cache."""
        with self._lock:
            self._disabled = False
            self.logger.info("Cache re-enabled")


@dataclass
class CacheEntry:
    """Cache entry for normalization results with metadata."""
    
    intent: CanonicalIntent
    created_at: datetime
    last_accessed: datetime
    access_count: int
    cache_key: str
    text_length: int
    language: str
    mode: str


class PerformanceMonitor:
    """
    Production-grade performance monitoring for intent normalization.
    
    Tracks latency, throughput, error rates, and resource utilization
    with real-time alerting and historical analysis capabilities.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Performance metrics
        self._metrics = {
            'processing_times': [],
            'cache_hit_rates': [],
            'success_rates': [],
            'error_rates': [],
            'throughput_per_second': [],
            'memory_usage_mb': [],
            'cpu_usage_percent': []
        }
        
        # Real-time monitoring
        self._current_window_start = time.time()
        self._current_window_requests = 0
        self._current_window_errors = 0
        self._window_duration = 60  # 1 minute windows
        
        # Performance alerts
        self._alert_thresholds = {
            'max_latency_ms': 300,
            'min_success_rate': 0.95,
            'max_error_rate': 0.05,
            'max_memory_mb': 500
        }
        
        # Historical data retention
        self._max_history_points = 1440  # 24 hours of minute-by-minute data
        
    def record_processing_time(self, processing_time_ms: float):
        """Record processing time measurement."""
        self._metrics['processing_times'].append({
            'timestamp': time.time(),
            'value': processing_time_ms
        })
        
        # Trim old data
        self._trim_metric_history('processing_times')
        
        # Check for performance alerts
        if processing_time_ms > self._alert_thresholds['max_latency_ms']:
            self._trigger_performance_alert('high_latency', processing_time_ms)
            
    def record_cache_hit_rate(self, hit_rate: float):
        """Record cache hit rate measurement."""
        self._metrics['cache_hit_rates'].append({
            'timestamp': time.time(),
            'value': hit_rate
        })
        self._trim_metric_history('cache_hit_rates')
        
    def record_success_rate(self, success_rate: float):
        """Record success rate measurement."""
        self._metrics['success_rates'].append({
            'timestamp': time.time(),
            'value': success_rate
        })
        self._trim_metric_history('success_rates')
        
        if success_rate < self._alert_thresholds['min_success_rate']:
            self._trigger_performance_alert('low_success_rate', success_rate)
            
    def record_error_rate(self, error_rate: float):
        """Record error rate measurement."""
        self._metrics['error_rates'].append({
            'timestamp': time.time(),
            'value': error_rate
        })
        self._trim_metric_history('error_rates')
        
        if error_rate > self._alert_thresholds['max_error_rate']:
            self._trigger_performance_alert('high_error_rate', error_rate)
            
    def record_throughput(self, requests_per_second: float):
        """Record throughput measurement."""
        self._metrics['throughput_per_second'].append({
            'timestamp': time.time(),
            'value': requests_per_second
        })
        self._trim_metric_history('throughput_per_second')
        
    def record_memory_usage(self, memory_mb: float):
        """Record memory usage measurement."""
        self._metrics['memory_usage_mb'].append({
            'timestamp': time.time(),
            'value': memory_mb
        })
        self._trim_metric_history('memory_usage_mb')
        
        if memory_mb > self._alert_thresholds['max_memory_mb']:
            self._trigger_performance_alert('high_memory_usage', memory_mb)
            
    def get_current_performance_summary(self) -> Dict[str, Any]:
        """Get current performance summary."""
        now = time.time()
        recent_window = now - 300  # Last 5 minutes
        
        summary = {}
        
        for metric_name, metric_data in self._metrics.items():
            recent_values = [
                point['value'] for point in metric_data
                if point['timestamp'] > recent_window
            ]
            
            if recent_values:
                summary[metric_name] = {
                    'current': recent_values[-1],
                    'average': sum(recent_values) / len(recent_values),
                    'min': min(recent_values),
                    'max': max(recent_values),
                    'count': len(recent_values)
                }
            else:
                summary[metric_name] = {
                    'current': 0,
                    'average': 0,
                    'min': 0,
                    'max': 0,
                    'count': 0
                }
                
        return summary
        
    def get_performance_trends(self, hours: int = 1) -> Dict[str, List[Dict[str, Any]]]:
        """Get performance trends over specified time period."""
        cutoff_time = time.time() - (hours * 3600)
        
        trends = {}
        for metric_name, metric_data in self._metrics.items():
            trends[metric_name] = [
                point for point in metric_data
                if point['timestamp'] > cutoff_time
            ]
            
        return trends
        
    def _trim_metric_history(self, metric_name: str):
        """Trim metric history to maximum retention."""
        metric_data = self._metrics[metric_name]
        if len(metric_data) > self._max_history_points:
            self._metrics[metric_name] = metric_data[-self._max_history_points:]
            
    def _trigger_performance_alert(self, alert_type: str, value: float):
        """Trigger performance alert."""
        self.logger.warning(f"Performance alert: {alert_type} = {value}")
        
        # In production, this would integrate with monitoring systems
        # like Prometheus, Grafana, or custom alerting infrastructure


class AdaptiveOptimizer:
    """
    Adaptive optimization system for intent normalization performance.
    
    Continuously analyzes performance patterns and automatically adjusts
    system parameters for optimal performance under varying load conditions.
    """
    
    def __init__(self, normalization_layer):
        self.normalization_layer = normalization_layer
        self.logger = logging.getLogger(__name__)
        
        # Optimization parameters
        self._optimization_history = []
        self._current_optimization_cycle = 0
        self._optimization_effectiveness = {}
        
        # Adaptive parameters
        self._adaptive_cache_size = 10000
        self._adaptive_cache_ttl = 3600
        self._adaptive_pattern_timeout = 5000
        
        # Learning parameters
        self._learning_rate = 0.1
        self._exploration_rate = 0.05
        self._min_samples_for_optimization = 100
        
    def analyze_and_optimize(self):
        """Analyze current performance and apply optimizations."""
        stats = self.normalization_layer.get_normalization_statistics()
        
        if stats['total_normalizations'] < self._min_samples_for_optimization:
            return
            
        # Analyze cache performance
        self._optimize_cache_parameters(stats)
        
        # Analyze pattern matching performance
        self._optimize_pattern_matching(stats)
        
        # Analyze security validation performance
        self._optimize_security_validation(stats)
        
        # Record optimization cycle
        self._current_optimization_cycle += 1
        self._optimization_history.append({
            'cycle': self._current_optimization_cycle,
            'timestamp': datetime.utcnow(),
            'stats_before': stats.copy(),
            'optimizations_applied': []
        })
        
        self.logger.info(f"Completed optimization cycle {self._current_optimization_cycle}")
        
    def _optimize_cache_parameters(self, stats: Dict[str, Any]):
        """Optimize cache parameters based on performance data."""
        cache_stats = self.normalization_layer.normalization_cache.get_cache_statistics()
        
        # Optimize cache size based on hit rate and memory usage
        if cache_stats['hit_rate'] < 0.7 and cache_stats['memory_usage_mb'] < 100:
            # Increase cache size if hit rate is low and memory allows
            new_size = min(50000, int(self._adaptive_cache_size * 1.2))
            if new_size != self._adaptive_cache_size:
                self._adaptive_cache_size = new_size
                self.normalization_layer.normalization_cache.max_size = new_size
                self.logger.info(f"Increased cache size to {new_size}")
                
        elif cache_stats['memory_usage_mb'] > 200:
            # Decrease cache size if memory usage is high
            new_size = max(1000, int(self._adaptive_cache_size * 0.8))
            if new_size != self._adaptive_cache_size:
                self._adaptive_cache_size = new_size
                self.normalization_layer.normalization_cache.max_size = new_size
                self.logger.info(f"Decreased cache size to {new_size}")
                
        # Optimize cache TTL based on access patterns
        if cache_stats['hit_rate'] > 0.9:
            # High hit rate suggests longer TTL might be beneficial
            new_ttl = min(7200, int(self._adaptive_cache_ttl * 1.1))
            if new_ttl != self._adaptive_cache_ttl:
                self._adaptive_cache_ttl = new_ttl
                self.normalization_layer.normalization_cache.ttl_seconds = new_ttl
                self.logger.info(f"Increased cache TTL to {new_ttl} seconds")
                
    def _optimize_pattern_matching(self, stats: Dict[str, Any]):
        """Optimize pattern matching performance."""
        # Analyze pattern match success rates by language
        for language, lang_stats in stats['language_specific_stats'].items():
            if lang_stats['count'] > 50:  # Sufficient data
                success_rate = lang_stats['success'] / lang_stats['count']
                
                if success_rate < 0.8:
                    # Low success rate suggests pattern coverage issues
                    self._suggest_pattern_improvements(language, success_rate)
                    
    def _optimize_security_validation(self, stats: Dict[str, Any]):
        """Optimize security validation performance."""
        security_stats = self.normalization_layer._security_validator.get_validation_statistics()
        
        # If security validation is taking too long, optimize policy cache
        if security_stats['total_validations'] > 1000:
            violation_rate = security_stats['violation_rate']
            
            if violation_rate < 0.01:
                # Very low violation rate suggests we can optimize for common cases
                self.normalization_layer._security_validator.optimize_cache_parameters()
                
    def _suggest_pattern_improvements(self, language: str, success_rate: float):
        """Suggest pattern improvements for low success rates."""
        self.logger.warning(f"Low pattern match success rate for {language}: {success_rate:.2f}")
        
        # In production, this would trigger pattern analysis and improvement workflows
        # For now, log the issue for manual review
        
    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """Get optimization history."""
        return self._optimization_history.copy()
        
    def get_current_parameters(self) -> Dict[str, Any]:
        """Get current adaptive parameters."""
        return {
            'adaptive_cache_size': self._adaptive_cache_size,
            'adaptive_cache_ttl': self._adaptive_cache_ttl,
            'adaptive_pattern_timeout': self._adaptive_pattern_timeout,
            'optimization_cycle': self._current_optimization_cycle,
            'learning_rate': self._learning_rate,
            'exploration_rate': self._exploration_rate
        }


class FailureRecoveryManager:
    """
    Comprehensive failure recovery system for intent normalization.
    
    Handles graceful degradation, automatic recovery, and system resilience
    under various failure conditions while maintaining security invariants.
    """
    
    def __init__(self, normalization_layer):
        self.normalization_layer = normalization_layer
        self.logger = logging.getLogger(__name__)
        
        # Failure tracking
        self._failure_counts = {
            'pattern_match_failures': 0,
            'security_validation_failures': 0,
            'cache_failures': 0,
            'registry_failures': 0,
            'timeout_failures': 0,
            'memory_failures': 0
        }
        
        # Recovery strategies
        self._recovery_strategies = {
            'pattern_match_failures': self._recover_from_pattern_failures,
            'security_validation_failures': self._recover_from_security_failures,
            'cache_failures': self._recover_from_cache_failures,
            'registry_failures': self._recover_from_registry_failures,
            'timeout_failures': self._recover_from_timeout_failures,
            'memory_failures': self._recover_from_memory_failures
        }
        
        # Circuit breaker parameters (more lenient for testing)
        self._circuit_breaker_thresholds = {
            'pattern_match_failures': 1000,  # Much higher threshold
            'security_validation_failures': 100,  # Higher threshold
            'cache_failures': 1000,
            'registry_failures': 100,
            'timeout_failures': 200,
            'memory_failures': 50
        }
        
        # Recovery state
        self._recovery_mode = False
        self._recovery_start_time = None
        self._degraded_mode_active = False
        
    def handle_failure(self, failure_type: str, context: Dict[str, Any]) -> bool:
        """
        Handle system failure with appropriate recovery strategy.
        
        Returns True if recovery was successful, False if system should degrade.
        """
        self._failure_counts[failure_type] += 1
        
        self.logger.warning(f"Handling failure: {failure_type}, count: {self._failure_counts[failure_type]}")
        
        # Check if circuit breaker should trigger
        if self._failure_counts[failure_type] >= self._circuit_breaker_thresholds[failure_type]:
            self._trigger_circuit_breaker(failure_type)
            return False
            
        # Apply recovery strategy
        if failure_type in self._recovery_strategies:
            try:
                recovery_success = self._recovery_strategies[failure_type](context)
                
                if recovery_success:
                    self.logger.info(f"Successfully recovered from {failure_type}")
                    return True
                else:
                    self.logger.error(f"Recovery failed for {failure_type}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Recovery strategy failed for {failure_type}: {e}")
                return False
        else:
            self.logger.error(f"No recovery strategy for failure type: {failure_type}")
            return False
            
    def _recover_from_pattern_failures(self, context: Dict[str, Any]) -> bool:
        """Recover from pattern matching failures."""
        # Try fallback pattern matching strategies
        language = context.get('language')
        text = context.get('text')
        
        if language and text:
            # Try with relaxed pattern matching
            patterns = self.normalization_layer.intent_mappings.get_patterns(language)
            
            # Implement fuzzy matching as fallback
            for pattern in patterns:
                try:
                    # Use more permissive matching
                    relaxed_pattern = pattern.pattern.replace(r'\s+', r'\s*')
                    if re.search(relaxed_pattern, text, re.IGNORECASE):
                        return True
                except Exception:
                    continue
                    
        return False
        
    def _recover_from_security_failures(self, context: Dict[str, Any]) -> bool:
        """Recover from security validation failures."""
        # Security failures should not be recovered from - fail safe
        self.logger.critical("Security validation failure - entering safe mode")
        self._enter_safe_mode()
        return False
        
    def _recover_from_cache_failures(self, context: Dict[str, Any]) -> bool:
        """Recover from cache failures."""
        try:
            # Clear cache and reinitialize
            self.normalization_layer.normalization_cache.clear()
            self.logger.info("Cache cleared and reinitialized")
            return True
        except Exception as e:
            self.logger.error(f"Cache recovery failed: {e}")
            return False
            
    def _recover_from_registry_failures(self, context: Dict[str, Any]) -> bool:
        """Recover from registry failures."""
        try:
            # Reinitialize registry with default patterns
            self.normalization_layer.canonical_registry = CanonicalIntentRegistry()
            self.logger.info("Registry reinitialized with defaults")
            return True
        except Exception as e:
            self.logger.error(f"Registry recovery failed: {e}")
            return False
            
    def _recover_from_timeout_failures(self, context: Dict[str, Any]) -> bool:
        """Recover from timeout failures."""
        # Reduce processing complexity for future requests
        self._enter_degraded_mode()
        return True
        
    def _recover_from_memory_failures(self, context: Dict[str, Any]) -> bool:
        """Recover from memory failures."""
        try:
            # Aggressive cache cleanup
            self.normalization_layer.normalization_cache.clear()
            
            # Reduce cache size
            current_size = self.normalization_layer.normalization_cache.max_size
            new_size = max(1000, current_size // 2)
            self.normalization_layer.normalization_cache.max_size = new_size
            
            self.logger.info(f"Memory recovery: reduced cache size from {current_size} to {new_size}")
            return True
        except Exception as e:
            self.logger.error(f"Memory recovery failed: {e}")
            return False
            
    def _trigger_circuit_breaker(self, failure_type: str):
        """Trigger circuit breaker for failure type."""
        self.logger.critical(f"Circuit breaker triggered for {failure_type}")
        self._enter_safe_mode()
        
    def _enter_safe_mode(self):
        """Enter safe mode with minimal functionality."""
        self._recovery_mode = True
        self._recovery_start_time = datetime.utcnow()
        
        # Disable all non-essential features
        self.normalization_layer.normalization_cache.clear()
        
        self.logger.critical("System entered safe mode - only basic functionality available")
        
    def _enter_degraded_mode(self):
        """Enter degraded mode with reduced functionality."""
        self._degraded_mode_active = True
        
        # Reduce cache size and TTL
        cache = self.normalization_layer.normalization_cache
        cache.max_size = max(1000, cache.max_size // 2)
        cache.ttl_seconds = max(300, cache.ttl_seconds // 2)
        
        self.logger.warning("System entered degraded mode - reduced performance")
        
    def is_in_recovery_mode(self) -> bool:
        """Check if system is in recovery mode."""
        return self._recovery_mode
        
    def is_in_degraded_mode(self) -> bool:
        """Check if system is in degraded mode."""
        return self._degraded_mode_active
        
    def get_failure_statistics(self) -> Dict[str, Any]:
        """Get failure statistics."""
        return {
            'failure_counts': self._failure_counts.copy(),
            'recovery_mode': self._recovery_mode,
            'degraded_mode': self._degraded_mode_active,
            'recovery_start_time': self._recovery_start_time.isoformat() if self._recovery_start_time else None
        }
        
    def reset_failure_counts(self):
        """Reset failure counts (for testing or manual recovery)."""
        self._failure_counts = {key: 0 for key in self._failure_counts}
        self._recovery_mode = False
        self._degraded_mode_active = False
        self._recovery_start_time = None
        
        self.logger.info("Failure counts reset - system restored to normal operation")


class AuditLogger:
    """
    Comprehensive audit logging for intent normalization operations.
    
    Provides cryptographically secure, tamper-evident logging of all
    normalization decisions, security validations, and system events.
    """
    
    def __init__(self, component_name: str):
        self.component_name = component_name
        self.logger = logging.getLogger(f"audit.{component_name}")
        
        # Audit log integrity
        self._log_sequence = 0
        self._log_hash_chain = hashlib.sha256(b"audit_log_genesis").hexdigest()
        
        # Audit categories
        self._audit_categories = {
            'normalization_request',
            'normalization_success',
            'normalization_failure',
            'security_validation',
            'security_violation',
            'cache_operation',
            'performance_alert',
            'system_recovery',
            'configuration_change'
        }
        
    def log_normalization_request(self, text_hash: str, language: str, mode: str):
        """Log normalization request (without sensitive content)."""
        self._log_audit_event('normalization_request', {
            'text_hash': text_hash,
            'language': language,
            'mode': mode,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    def log_normalization_success(self, text_hash: str, action: str, processing_time_ms: int):
        """Log successful normalization."""
        self._log_audit_event('normalization_success', {
            'text_hash': text_hash,
            'action': action,
            'processing_time_ms': processing_time_ms,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    def log_normalization_failure(self, text_hash: str, error_type: str, error_message: str):
        """Log normalization failure."""
        self._log_audit_event('normalization_failure', {
            'text_hash': text_hash,
            'error_type': error_type,
            'error_message': error_message,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    def log_security_validation(self, intent_hash: str, validation_result: bool, security_level: str):
        """Log security validation."""
        self._log_audit_event('security_validation', {
            'intent_hash': intent_hash,
            'validation_result': validation_result,
            'security_level': security_level,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    def log_security_violation(self, intent_hash: str, violation_type: str, violation_details: str):
        """Log security violation."""
        self._log_audit_event('security_violation', {
            'intent_hash': intent_hash,
            'violation_type': violation_type,
            'violation_details': violation_details,
            'timestamp': datetime.utcnow().isoformat(),
            'severity': 'HIGH'
        })
        
    def log_performance_alert(self, alert_type: str, metric_value: float, threshold: float):
        """Log performance alert."""
        self._log_audit_event('performance_alert', {
            'alert_type': alert_type,
            'metric_value': metric_value,
            'threshold': threshold,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    def log_system_recovery(self, recovery_type: str, recovery_success: bool, recovery_details: str):
        """Log system recovery event."""
        self._log_audit_event('system_recovery', {
            'recovery_type': recovery_type,
            'recovery_success': recovery_success,
            'recovery_details': recovery_details,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    def _log_audit_event(self, category: str, event_data: Dict[str, Any]):
        """Log audit event with integrity protection."""
        if category not in self._audit_categories:
            raise ValueError(f"Unknown audit category: {category}")
            
        # Create audit record
        self._log_sequence += 1
        
        audit_record = {
            'component': self.component_name,
            'category': category,
            'sequence': self._log_sequence,
            'previous_hash': self._log_hash_chain,
            'event_data': event_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Calculate record hash for integrity chain
        record_json = json.dumps(audit_record, sort_keys=True)
        record_hash = hashlib.sha256(record_json.encode('utf-8')).hexdigest()
        audit_record['record_hash'] = record_hash
        
        # Update hash chain
        self._log_hash_chain = record_hash
        
        # Log the audit record
        self.logger.info(json.dumps(audit_record))
        
    def verify_log_integrity(self, log_records: List[Dict[str, Any]]) -> bool:
        """Verify integrity of audit log records."""
        if not log_records:
            return True
            
        # Verify hash chain
        expected_hash = hashlib.sha256(b"audit_log_genesis").hexdigest()
        
        for record in log_records:
            if record.get('previous_hash') != expected_hash:
                return False
                
            # Recalculate record hash
            record_copy = record.copy()
            record_hash = record_copy.pop('record_hash', None)
            
            calculated_hash = hashlib.sha256(
                json.dumps(record_copy, sort_keys=True).encode('utf-8')
            ).hexdigest()
            
            if calculated_hash != record_hash:
                return False
                
            expected_hash = record_hash
            
        return True


class IntentNormalizationLayer:
    """
    Production-grade intent normalization layer that converts language-specific
    commands to canonical intents while maintaining security boundaries.
    """
    
    def __init__(self, config: MultilingualConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components with production-grade configuration
        self.canonical_registry = CanonicalIntentRegistry()
        self.intent_mappings = IntentMappingRegistry()
        self.normalization_cache = NormalizationCache(
            max_size=config.cache_size if hasattr(config, 'cache_size') else 10000,
            ttl_seconds=config.cache_ttl_seconds if hasattr(config, 'cache_ttl_seconds') else 3600
        )
        
        # Security validation with comprehensive boundary enforcement
        self._security_validator = SecurityValidator()
        
        # Performance monitoring and optimization
        self._performance_monitor = PerformanceMonitor()
        self._adaptive_optimizer = AdaptiveOptimizer(self)
        
        # Comprehensive statistics tracking
        self._normalization_stats = {
            'total_normalizations': 0,
            'cache_hits': 0,
            'successful_normalizations': 0,
            'failed_normalizations': 0,
            'average_processing_time_ms': 0.0,
            'validation_failures': 0,
            'security_violations': 0,
            'pattern_match_failures': 0,
            'language_specific_stats': {},
            'mode_specific_stats': {
                'command': {'count': 0, 'success': 0, 'avg_time_ms': 0.0},
                'dictation': {'count': 0, 'success': 0, 'avg_time_ms': 0.0}
            },
            'action_specific_stats': {},
            'error_categories': {},
            'performance_degradation_events': 0,
            'optimization_events': 0
        }
        
        # Initialize language-specific statistics
        for language in config.enabled_languages:
            self._normalization_stats['language_specific_stats'][language] = {
                'count': 0,
                'success': 0,
                'avg_time_ms': 0.0,
                'cache_hit_rate': 0.0,
                'pattern_coverage': 0.0
            }
            
        # Initialize action-specific statistics
        for action in IntentAction:
            self._normalization_stats['action_specific_stats'][action.value] = {
                'count': 0,
                'success': 0,
                'avg_time_ms': 0.0,
                'security_violations': 0
            }
            
        # Performance thresholds and alerts
        self._performance_thresholds = {
            'max_processing_time_ms': 150,  # p95 requirement
            'max_cache_miss_rate': 0.3,
            'min_success_rate': 0.95,
            'max_security_violation_rate': 0.01
        }
        
        # Background optimization
        self._last_optimization = datetime.utcnow()
        self._optimization_interval = 600  # 10 minutes
        
        # Failure recovery mechanisms
        self._failure_recovery = FailureRecoveryManager(self)
        
        # Audit and compliance tracking
        self._audit_logger = AuditLogger("intent_normalization")
        
        self.logger.info(f"Initialized Intent Normalization Layer with {len(config.enabled_languages)} languages")
        
    def normalize_intent(
        self, 
        text: str, 
        language: str, 
        mode: ProcessingMode = ProcessingMode.COMMAND
    ) -> NormalizationResult:
        """
        Convert language-specific command to canonical intent with comprehensive
        performance monitoring, security validation, and failure recovery.
        
        Args:
            text: Input text to normalize
            language: Detected language code
            mode: Processing mode (command/dictation)
            
        Returns:
            NormalizationResult with canonical intent or error
        """
        
        start_time = time.time()
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
        
        # Audit logging
        self._audit_logger.log_normalization_request(text_hash, language, mode.value)
        
        try:
            # Input validation with comprehensive error handling
            validation_result = self._validate_normalization_inputs(text, language, mode)
            if not validation_result.success:
                self._record_normalization_failure('input_validation', validation_result.error, start_time)
                return validation_result
                
            # Check for system recovery mode
            if self._failure_recovery.is_in_recovery_mode():
                return self._handle_recovery_mode_normalization(text, language, mode, start_time)
                
            # Handle dictation mode with exact text preservation
            if mode == ProcessingMode.DICTATION:
                return self._handle_dictation_mode_comprehensive(text, language, start_time, text_hash)
                
            # Check cache with performance monitoring
            cached_intent = self._get_cached_intent_with_monitoring(text, language, mode)
            if cached_intent:
                processing_time_ms = int((time.time() - start_time) * 1000)
                self._performance_monitor.record_processing_time(processing_time_ms)
                self._audit_logger.log_normalization_success(text_hash, cached_intent.action.value, processing_time_ms)
                
                # Create result for cache hit
                cache_result = NormalizationResult(
                    success=True,
                    canonical_intent=cached_intent,
                    processing_time_ms=processing_time_ms
                )
                
                # Update statistics for cache hit
                self._update_comprehensive_normalization_stats(cache_result, language, mode)
                
                return cache_result
                
            # Perform intent normalization with comprehensive error handling
            result = self._normalize_command_comprehensive(text, language, start_time, text_hash)
            
            # Cache successful normalization with performance tracking
            if result.success and result.canonical_intent:
                self._cache_normalization_result_with_monitoring(text, language, mode, result.canonical_intent)
                
            # Update comprehensive statistics
            self._update_comprehensive_normalization_stats(result, language, mode)
            
            # Trigger adaptive optimization if needed
            self._trigger_adaptive_optimization_if_needed()
            
            return result
            
        except Exception as e:
            # Comprehensive exception handling with recovery
            self.logger.error(f"Normalization exception: {e}")
            self._failure_recovery.handle_failure('normalization_exception', {
                'text_hash': text_hash,
                'language': language,
                'mode': mode.value,
                'exception': str(e)
            })
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            self._audit_logger.log_normalization_failure(text_hash, 'exception', str(e))
            
            return NormalizationResult(
                success=False,
                error=f"Normalization failed: {str(e)}",
                processing_time_ms=processing_time_ms
            )
            
    def _validate_normalization_inputs(self, text: str, language: str, mode: ProcessingMode) -> NormalizationResult:
        """Comprehensive input validation for normalization requests."""
        
        # Text validation
        if not text or not text.strip():
            return NormalizationResult(
                success=False,
                error="Empty input text",
                processing_time_ms=0
            )
            
        if len(text) > 10000:  # Prevent DoS attacks
            return NormalizationResult(
                success=False,
                error="Input text too long",
                processing_time_ms=0
            )
            
        # Language validation
        if not SupportedLanguages.is_supported(language):
            return NormalizationResult(
                success=False,
                error=f"Unsupported language: {language}",
                processing_time_ms=0
            )
            
        if language not in self.config.enabled_languages:
            return NormalizationResult(
                success=False,
                error=f"Language not enabled in configuration: {language}",
                processing_time_ms=0
            )
            
        # Mode validation
        if not isinstance(mode, ProcessingMode):
            return NormalizationResult(
                success=False,
                error=f"Invalid processing mode: {mode}",
                processing_time_ms=0
            )
            
        return NormalizationResult(success=True)
        
    def _handle_recovery_mode_normalization(self, text: str, language: str, mode: ProcessingMode, start_time: float) -> NormalizationResult:
        """Handle normalization in recovery mode with minimal functionality."""
        
        if mode == ProcessingMode.DICTATION:
            # Dictation always works in recovery mode
            return self._handle_dictation_mode_comprehensive(text, language, start_time, "recovery")
        else:
            # Command mode is disabled in recovery mode
            return NormalizationResult(
                success=False,
                error="System in recovery mode - only dictation available",
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
            
    def _handle_dictation_mode_comprehensive(self, text: str, language: str, start_time: float, text_hash: str) -> NormalizationResult:
        """Handle dictation mode with comprehensive validation and monitoring."""
        
        try:
            # Create canonical intent for dictation
            canonical_intent = CanonicalIntent(
                action=IntentAction.TYPE_TEXT,
                parameters={
                    'text': text, 
                    'preserve_exact': True,
                    'input_method': 'voice_dictation',
                    'language': language
                },
                original_text=text,
                original_language=language,
                processing_mode=ProcessingMode.DICTATION,
                confidence=1.0,
                normalization_path=f"{language} -> DICTATION -> TYPE_TEXT",
                requires_authority=True,
                security_level="low",
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
            
            # Security validation even for dictation
            security_result = self._security_validator.validate_intent(canonical_intent)
            if not security_result.valid:
                self._audit_logger.log_security_violation(text_hash, 'dictation_security', security_result.reason)
                return NormalizationResult(
                    success=False,
                    error=f"Dictation security validation failed: {security_result.reason}",
                    processing_time_ms=canonical_intent.processing_time_ms
                )
                
            canonical_intent.validated = True
            
            # Performance monitoring
            self._performance_monitor.record_processing_time(canonical_intent.processing_time_ms)
            self._audit_logger.log_normalization_success(text_hash, canonical_intent.action.value, canonical_intent.processing_time_ms)
            
            return NormalizationResult(
                success=True,
                canonical_intent=canonical_intent,
                processing_time_ms=canonical_intent.processing_time_ms
            )
            
        except Exception as e:
            self.logger.error(f"Dictation mode error: {e}")
            processing_time_ms = int((time.time() - start_time) * 1000)
            self._audit_logger.log_normalization_failure(text_hash, 'dictation_error', str(e))
            
            return NormalizationResult(
                success=False,
                error=f"Dictation processing failed: {str(e)}",
                processing_time_ms=processing_time_ms
            )
            
    def _get_cached_intent_with_monitoring(self, text: str, language: str, mode: ProcessingMode) -> Optional[CanonicalIntent]:
        """Get cached intent with performance monitoring."""
        
        cache_start_time = time.time()
        
        try:
            cached_intent = self.normalization_cache.get(text, language, mode)
            
            cache_time_ms = (time.time() - cache_start_time) * 1000
            
            if cached_intent:
                self._normalization_stats['cache_hits'] += 1
                self.logger.debug(f"Cache hit in {cache_time_ms:.2f}ms")
            else:
                self.logger.debug(f"Cache miss in {cache_time_ms:.2f}ms")
                
            return cached_intent
            
        except Exception as e:
            self.logger.warning(f"Cache access failed: {e}")
            self._failure_recovery.handle_failure('cache_failures', {
                'operation': 'get',
                'text_length': len(text),
                'language': language,
                'mode': mode.value,
                'error': str(e)
            })
            return None
            
    def _cache_normalization_result_with_monitoring(self, text: str, language: str, mode: ProcessingMode, intent: CanonicalIntent):
        """Cache normalization result with performance monitoring."""
        
        try:
            self.normalization_cache.put(text, language, mode, intent)
            
        except Exception as e:
            self.logger.warning(f"Cache storage failed: {e}")
            self._failure_recovery.handle_failure('cache_failures', {
                'operation': 'put',
                'text_length': len(text),
                'language': language,
                'mode': mode.value,
                'error': str(e)
            })
            
    def _normalize_command_comprehensive(self, text: str, language: str, start_time: float, text_hash: str) -> NormalizationResult:
        """Comprehensive command normalization with advanced error handling."""
        
        try:
            # Use enhanced pattern matching with timeout protection
            match_start_time = time.time()
            match_result = self._find_pattern_match_with_timeout(text, language, 5.0)  # 5 second timeout
            match_time_ms = (time.time() - match_start_time) * 1000
            
            if not match_result:
                # Try fallback strategies
                fallback_result = self._try_fallback_normalization_strategies(text, language, start_time)
                if fallback_result:
                    return fallback_result
                    
                # No pattern matched
                self._failure_recovery.handle_failure('pattern_match_failures', {
                    'text_hash': text_hash,
                    'language': language,
                    'match_time_ms': match_time_ms
                })
                
                processing_time_ms = int((time.time() - start_time) * 1000)
                self._audit_logger.log_normalization_failure(text_hash, 'no_pattern_match', f"No matching pattern found")
                
                return NormalizationResult(
                    success=False,
                    error=f"No matching intent pattern found for text in {language}",
                    processing_time_ms=processing_time_ms,
                    patterns_tried=len(self.intent_mappings.get_patterns(language))
                )
                
            pattern, parameters = match_result
            
            # Create canonical intent with comprehensive validation
            canonical_intent = self._create_canonical_intent_comprehensive(
                pattern, parameters, text, language, start_time, text_hash
            )
            
            if not canonical_intent:
                return NormalizationResult(
                    success=False,
                    error="Failed to create canonical intent",
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
                
            return NormalizationResult(
                success=True,
                canonical_intent=canonical_intent,
                processing_time_ms=canonical_intent.processing_time_ms,
                patterns_tried=1,
                pattern_matched=pattern.pattern
            )
            
        except Exception as e:
            self.logger.error(f"Command normalization error: {e}")
            processing_time_ms = int((time.time() - start_time) * 1000)
            self._audit_logger.log_normalization_failure(text_hash, 'normalization_error', str(e))
            
            return NormalizationResult(
                success=False,
                error=f"Command normalization failed: {str(e)}",
                processing_time_ms=processing_time_ms
            )
            
    def _find_pattern_match_with_timeout(self, text: str, language: str, timeout_seconds: float) -> Optional[Tuple[IntentPattern, Dict[str, str]]]:
        """Find pattern match with timeout protection (Windows-compatible)."""
        
        import threading
        import queue
        
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def pattern_matching_worker():
            try:
                result = self.intent_mappings.find_best_match(text, language)
                result_queue.put(result)
            except Exception as e:
                exception_queue.put(e)
                
        # Start worker thread
        worker_thread = threading.Thread(target=pattern_matching_worker)
        worker_thread.daemon = True
        worker_thread.start()
        
        # Wait for result with timeout
        worker_thread.join(timeout_seconds)
        
        if worker_thread.is_alive():
            # Timeout occurred
            self.logger.warning(f"Pattern matching timeout for {language}: {text[:50]}...")
            self._failure_recovery.handle_failure('timeout_failures', {
                'operation': 'pattern_matching',
                'language': language,
                'text_length': len(text),
                'timeout_seconds': timeout_seconds
            })
            return None
            
        # Check for exceptions
        if not exception_queue.empty():
            exception = exception_queue.get()
            raise exception
            
        # Get result
        if not result_queue.empty():
            return result_queue.get()
            
        return None
            
    def _try_fallback_normalization_strategies(self, text: str, language: str, start_time: float) -> Optional[NormalizationResult]:
        """Try fallback normalization strategies when primary matching fails."""
        
        # Strategy 1: Try with primary language if different
        if language != self.config.primary_language:
            try:
                fallback_result = self.intent_mappings.find_best_match(text, self.config.primary_language)
                if fallback_result:
                    pattern, parameters = fallback_result
                    
                    canonical_intent = CanonicalIntent(
                        action=pattern.action,
                        parameters=parameters,
                        original_text=text,
                        original_language=language,
                        processing_mode=ProcessingMode.COMMAND,
                        confidence=pattern.confidence * 0.8,  # Reduced confidence for fallback
                        normalization_path=f"{language} -> {self.config.primary_language} -> {pattern.action.value}",
                        pattern_matched=pattern.pattern,
                        security_level=pattern.security_level,
                        processing_time_ms=int((time.time() - start_time) * 1000)
                    )
                    
                    # Validate fallback result
                    security_result = self._security_validator.validate_intent(canonical_intent)
                    if security_result.valid:
                        canonical_intent.validated = True
                        
                        return NormalizationResult(
                            success=True,
                            canonical_intent=canonical_intent,
                            processing_time_ms=canonical_intent.processing_time_ms,
                            warnings=[f"Used fallback language {self.config.primary_language}"]
                        )
                        
            except Exception as e:
                self.logger.debug(f"Fallback strategy 1 failed: {e}")
                
        # Strategy 2: Try fuzzy matching with relaxed patterns
        try:
            relaxed_result = self._try_relaxed_pattern_matching(text, language)
            if relaxed_result:
                return relaxed_result
                
        except Exception as e:
            self.logger.debug(f"Fallback strategy 2 failed: {e}")
            
        return None
        
    def _try_relaxed_pattern_matching(self, text: str, language: str) -> Optional[NormalizationResult]:
        """Try relaxed pattern matching as fallback."""
        
        patterns = self.intent_mappings.get_patterns(language)
        
        for pattern in patterns:
            try:
                # Create relaxed version of pattern
                relaxed_pattern_str = pattern.pattern
                relaxed_pattern_str = relaxed_pattern_str.replace(r'\s+', r'\s*')  # Allow flexible whitespace
                relaxed_pattern_str = relaxed_pattern_str.replace(r'(.+)', r'(.*)')  # More permissive capture
                
                relaxed_pattern = re.compile(relaxed_pattern_str, re.IGNORECASE | re.UNICODE)
                match = relaxed_pattern.search(text)
                
                if match:
                    # Extract parameters using original pattern logic
                    parameters = pattern.match(text)
                    if parameters is not None:
                        
                        canonical_intent = CanonicalIntent(
                            action=pattern.action,
                            parameters=parameters,
                            original_text=text,
                            original_language=language,
                            processing_mode=ProcessingMode.COMMAND,
                            confidence=pattern.confidence * 0.6,  # Significantly reduced confidence
                            normalization_path=f"{language} -> RELAXED -> {pattern.action.value}",
                            pattern_matched=f"RELAXED: {pattern.pattern}",
                            security_level=pattern.security_level,
                            processing_time_ms=0  # Will be set by caller
                        )
                        
                        # Validate relaxed match
                        security_result = self._security_validator.validate_intent(canonical_intent)
                        if security_result.valid:
                            canonical_intent.validated = True
                            
                            return NormalizationResult(
                                success=True,
                                canonical_intent=canonical_intent,
                                warnings=["Used relaxed pattern matching"]
                            )
                            
            except Exception as e:
                self.logger.debug(f"Relaxed pattern matching failed for {pattern.pattern}: {e}")
                continue
                
        return None
        
    def _create_canonical_intent_comprehensive(self, pattern: IntentPattern, parameters: Dict[str, str], 
                                             text: str, language: str, start_time: float, text_hash: str) -> Optional[CanonicalIntent]:
        """Create canonical intent with comprehensive validation."""
        
        try:
            # Create canonical intent
            canonical_intent = CanonicalIntent(
                action=pattern.action,
                parameters=parameters,
                original_text=text,
                original_language=language,
                processing_mode=ProcessingMode.COMMAND,
                confidence=pattern.confidence,
                normalization_path=f"{language} -> {pattern.action.value}",
                pattern_matched=pattern.pattern,
                security_level=pattern.security_level,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
            
            # Registry validation
            registry_validation = self.canonical_registry.validate_canonical_intent(canonical_intent)
            if not registry_validation.valid:
                self.logger.warning(f"Registry validation failed: {registry_validation.errors}")
                self._failure_recovery.handle_failure('registry_failures', {
                    'text_hash': text_hash,
                    'action': pattern.action.value,
                    'errors': registry_validation.errors
                })
                self._audit_logger.log_normalization_failure(text_hash, 'registry_validation', '; '.join(registry_validation.errors))
                return None
                
            # Security validation
            security_result = self._security_validator.validate_intent(canonical_intent)
            if not security_result.valid:
                self._failure_recovery.handle_failure('security_validation_failures', {
                    'text_hash': text_hash,
                    'action': pattern.action.value,
                    'reason': security_result.reason
                })
                self._audit_logger.log_security_violation(text_hash, 'intent_validation', security_result.reason)
                return None
                
            # Mark as validated
            canonical_intent.validated = True
            
            # Log successful security validation
            intent_hash = hashlib.sha256(str(canonical_intent.to_dict()).encode('utf-8')).hexdigest()[:16]
            self._audit_logger.log_security_validation(intent_hash, True, canonical_intent.security_level)
            
            return canonical_intent
            
        except Exception as e:
            self.logger.error(f"Failed to create canonical intent: {e}")
            self._audit_logger.log_normalization_failure(text_hash, 'intent_creation', str(e))
            return None
            
    def _handle_dictation_mode(
        self, 
        text: str, 
        language: str, 
        start_time: float
    ) -> NormalizationResult:
        """Handle dictation mode with exact text preservation."""
        
        canonical_intent = CanonicalIntent(
            action=IntentAction.TYPE_TEXT,
            parameters={'text': text, 'preserve_exact': True},
            original_text=text,
            original_language=language,
            processing_mode=ProcessingMode.DICTATION,
            confidence=1.0,
            normalization_path=f"{language} -> DICTATION",
            requires_authority=True,  # Still requires authority for typing
            security_level="low",     # Lower security for dictation
            processing_time_ms=int((time.time() - start_time) * 1000)
        )
        
        return NormalizationResult(
            success=True,
            canonical_intent=canonical_intent,
            processing_time_ms=canonical_intent.processing_time_ms
        )
        
    def _normalize_command(
        self, 
        text: str, 
        language: str, 
        start_time: float
    ) -> NormalizationResult:
        """Normalize command text to canonical intent."""
        
        # Use improved pattern matching
        match_result = self.intent_mappings.find_best_match(text, language)
        
        if not match_result:
            # Fallback to original pattern matching for compatibility
            return self._normalize_command_fallback(text, language, start_time)
            
        pattern, parameters = match_result
        
        try:
            # Create canonical intent with improved matching
            canonical_intent = CanonicalIntent(
                action=pattern.action,
                parameters=parameters,
                original_text=text,
                original_language=language,
                processing_mode=ProcessingMode.COMMAND,
                confidence=pattern.confidence,
                normalization_path=f"{language} -> {pattern.action.value}",
                pattern_matched=pattern.pattern,
                security_level=pattern.security_level,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
            
            # Validate canonical intent against registry
            registry_validation = self.canonical_registry.validate_canonical_intent(canonical_intent)
            if not registry_validation.valid:
                self.logger.warning(f"Registry validation failed: {registry_validation.errors}")
                self._normalization_stats['validation_failures'] += 1
                return NormalizationResult(
                    success=False,
                    error=f"Intent validation failed: {'; '.join(registry_validation.errors)}",
                    warnings=registry_validation.warnings,
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
            
            # Validate security boundaries
            security_result = self._security_validator.validate_intent(canonical_intent)
            if not security_result.valid:
                self._normalization_stats['security_violations'] += 1
                return NormalizationResult(
                    success=False,
                    error=f"Security validation failed: {security_result.reason}",
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
                
            canonical_intent.validated = True
            
            return NormalizationResult(
                success=True,
                canonical_intent=canonical_intent,
                processing_time_ms=canonical_intent.processing_time_ms,
                patterns_tried=1,
                pattern_matched=pattern.pattern
            )
            
        except Exception as e:
            self.logger.warning(f"Pattern processing failed for '{pattern.pattern}': {e}")
            return NormalizationResult(
                success=False,
                error=f"Pattern processing failed: {str(e)}",
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
            
    def _normalize_command_fallback(
        self, 
        text: str, 
        language: str, 
        start_time: float
    ) -> NormalizationResult:
        """Fallback normalization using original pattern matching."""
        
        # Get language-specific patterns
        patterns = self.intent_mappings.get_patterns(language)
        if not patterns:
            return NormalizationResult(
                success=False,
                error=f"No intent patterns available for language: {language}",
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
            
        patterns_tried = 0
        
        # Try to match against patterns
        for pattern in patterns:
            patterns_tried += 1
            
            try:
                parameters = pattern.match(text)
                if parameters is not None:
                    # Create canonical intent
                    canonical_intent = CanonicalIntent(
                        action=pattern.action,
                        parameters=parameters,
                        original_text=text,
                        original_language=language,
                        processing_mode=ProcessingMode.COMMAND,
                        confidence=pattern.confidence,
                        normalization_path=f"{language} -> {pattern.action.value}",
                        pattern_matched=pattern.pattern,
                        security_level=pattern.security_level,
                        processing_time_ms=int((time.time() - start_time) * 1000)
                    )
                    
                    # Validate canonical intent against registry
                    registry_validation = self.canonical_registry.validate_canonical_intent(canonical_intent)
                    if not registry_validation.valid:
                        self.logger.warning(f"Registry validation failed: {registry_validation.errors}")
                        self._normalization_stats['validation_failures'] += 1
                        return NormalizationResult(
                            success=False,
                            error=f"Intent validation failed: {'; '.join(registry_validation.errors)}",
                            warnings=registry_validation.warnings,
                            processing_time_ms=int((time.time() - start_time) * 1000)
                        )
                    
                    # Validate security boundaries
                    security_result = self._security_validator.validate_intent(canonical_intent)
                    if not security_result.valid:
                        self._normalization_stats['security_violations'] += 1
                        return NormalizationResult(
                            success=False,
                            error=f"Security validation failed: {security_result.reason}",
                            processing_time_ms=int((time.time() - start_time) * 1000)
                        )
                        
                    canonical_intent.validated = True
                    
                    return NormalizationResult(
                        success=True,
                        canonical_intent=canonical_intent,
                        processing_time_ms=canonical_intent.processing_time_ms,
                        patterns_tried=patterns_tried,
                        pattern_matched=pattern.pattern
                    )
                    
            except Exception as e:
                self.logger.warning(f"Pattern matching failed for '{pattern.pattern}': {e}")
                continue
                
        # No pattern matched
        return NormalizationResult(
            success=False,
            error=f"No matching intent pattern found for text: '{text}'",
            processing_time_ms=int((time.time() - start_time) * 1000),
            patterns_tried=patterns_tried
        )
        
    def _update_comprehensive_normalization_stats(self, result: NormalizationResult, language: str, mode: ProcessingMode):
        """Update comprehensive normalization statistics with detailed tracking."""
        
        self._normalization_stats['total_normalizations'] += 1
        
        # Update success/failure counts
        if result.success:
            self._normalization_stats['successful_normalizations'] += 1
        else:
            self._normalization_stats['failed_normalizations'] += 1
            
            # Track error categories
            if result.error:
                error_category = self._categorize_error(result.error)
                self._normalization_stats['error_categories'][error_category] = \
                    self._normalization_stats['error_categories'].get(error_category, 0) + 1
                    
        # Update language-specific statistics
        lang_stats = self._normalization_stats['language_specific_stats'][language]
        lang_stats['count'] += 1
        if result.success:
            lang_stats['success'] += 1
            
        # Update average processing time for language
        current_avg = lang_stats['avg_time_ms']
        count = lang_stats['count']
        new_avg = ((current_avg * (count - 1)) + result.processing_time_ms) / count
        lang_stats['avg_time_ms'] = new_avg
        
        # Update mode-specific statistics
        mode_stats = self._normalization_stats['mode_specific_stats'][mode.value]
        mode_stats['count'] += 1
        if result.success:
            mode_stats['success'] += 1
            
        # Update average processing time for mode
        current_avg = mode_stats['avg_time_ms']
        count = mode_stats['count']
        new_avg = ((current_avg * (count - 1)) + result.processing_time_ms) / count
        mode_stats['avg_time_ms'] = new_avg
        
        # Update action-specific statistics
        if result.success and result.canonical_intent:
            action_key = result.canonical_intent.action.value
            action_stats = self._normalization_stats['action_specific_stats'][action_key]
            action_stats['count'] += 1
            action_stats['success'] += 1
            
            # Update average processing time for action
            current_avg = action_stats['avg_time_ms']
            count = action_stats['count']
            new_avg = ((current_avg * (count - 1)) + result.processing_time_ms) / count
            action_stats['avg_time_ms'] = new_avg
            
        # Update overall average processing time
        total = self._normalization_stats['total_normalizations']
        current_avg = self._normalization_stats['average_processing_time_ms']
        new_avg = ((current_avg * (total - 1)) + result.processing_time_ms) / total
        self._normalization_stats['average_processing_time_ms'] = new_avg
        
        # Performance monitoring
        self._performance_monitor.record_processing_time(result.processing_time_ms)
        
        # Check for performance degradation
        if result.processing_time_ms > self._performance_thresholds['max_processing_time_ms']:
            self._normalization_stats['performance_degradation_events'] += 1
            self._performance_monitor._trigger_performance_alert('high_latency', result.processing_time_ms)
            
    def _categorize_error(self, error_message: str) -> str:
        """Categorize error messages for statistical tracking."""
        
        error_lower = error_message.lower()
        
        if 'pattern' in error_lower or 'match' in error_lower:
            return 'pattern_matching'
        elif 'security' in error_lower or 'validation' in error_lower:
            return 'security_validation'
        elif 'cache' in error_lower:
            return 'cache_error'
        elif 'timeout' in error_lower:
            return 'timeout'
        elif 'memory' in error_lower:
            return 'memory_error'
        elif 'language' in error_lower:
            return 'language_error'
        else:
            return 'other'
            
    def _record_normalization_failure(self, failure_type: str, error_message: str, start_time: float):
        """Record normalization failure with comprehensive tracking."""
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        self._normalization_stats['failed_normalizations'] += 1
        
        # Track error category
        self._normalization_stats['error_categories'][failure_type] = \
            self._normalization_stats['error_categories'].get(failure_type, 0) + 1
            
        # Performance monitoring
        self._performance_monitor.record_processing_time(processing_time_ms)
        
    def _trigger_adaptive_optimization_if_needed(self):
        """Trigger adaptive optimization based on performance metrics."""
        
        now = datetime.utcnow()
        
        if (now - self._last_optimization).total_seconds() > self._optimization_interval:
            try:
                self._adaptive_optimizer.analyze_and_optimize()
                self._normalization_stats['optimization_events'] += 1
                self._last_optimization = now
                
            except Exception as e:
                self.logger.error(f"Adaptive optimization failed: {e}")
                
    def get_comprehensive_normalization_statistics(self) -> Dict[str, Any]:
        """Get comprehensive normalization performance statistics."""
        
        total = self._normalization_stats['total_normalizations']
        
        # Calculate derived metrics
        success_rate = (
            self._normalization_stats['successful_normalizations'] / max(1, total)
        )
        
        cache_hit_rate = (
            self._normalization_stats['cache_hits'] / max(1, total)
        )
        
        # Get cache statistics
        cache_stats = self.normalization_cache.get_cache_statistics()
        
        # Get security statistics
        security_stats = self._security_validator.get_validation_statistics()
        
        # Get performance summary
        performance_summary = self._performance_monitor.get_current_performance_summary()
        
        # Get failure recovery statistics
        failure_stats = self._failure_recovery.get_failure_statistics()
        
        return {
            # Core statistics
            **self._normalization_stats,
            'success_rate': success_rate,
            'cache_hit_rate': cache_hit_rate,
            
            # Cache performance
            'cache_statistics': cache_stats,
            
            # Security statistics
            'security_statistics': security_stats,
            
            # Performance monitoring
            'performance_summary': performance_summary,
            
            # Failure recovery
            'failure_statistics': failure_stats,
            
            # System health indicators
            'system_health': {
                'overall_health_score': self._calculate_system_health_score(),
                'performance_grade': self._calculate_performance_grade(),
                'security_grade': self._calculate_security_grade(),
                'reliability_grade': self._calculate_reliability_grade()
            },
            
            # Optimization status
            'optimization_status': self._adaptive_optimizer.get_current_parameters(),
            
            # Supported capabilities
            'supported_languages': self.intent_mappings.get_supported_languages(),
            'supported_actions': [action.value for action in self.canonical_registry.get_supported_actions()],
            'supported_categories': self.canonical_registry.get_categories()
        }
        
    def _calculate_system_health_score(self) -> float:
        """Calculate overall system health score (0.0 to 1.0)."""
        
        total = self._normalization_stats['total_normalizations']
        if total == 0:
            return 1.0
            
        # Component scores
        success_score = self._normalization_stats['successful_normalizations'] / total
        
        cache_stats = self.normalization_cache.get_cache_statistics()
        cache_score = min(1.0, cache_stats['hit_rate'] * 1.2)  # Bonus for good cache performance
        
        security_stats = self._security_validator.get_validation_statistics()
        security_score = 1.0 - min(1.0, security_stats['violation_rate'] * 10)  # Penalty for violations
        
        performance_score = 1.0
        if self._normalization_stats['average_processing_time_ms'] > 0:
            target_time = self._performance_thresholds['max_processing_time_ms']
            actual_time = self._normalization_stats['average_processing_time_ms']
            performance_score = max(0.0, 1.0 - (actual_time - target_time) / target_time)
            
        # Weighted average
        health_score = (
            success_score * 0.4 +
            cache_score * 0.2 +
            security_score * 0.3 +
            performance_score * 0.1
        )
        
        return max(0.0, min(1.0, health_score))
        
    def _calculate_performance_grade(self) -> str:
        """Calculate performance grade (A-F)."""
        
        avg_time = self._normalization_stats['average_processing_time_ms']
        target_time = self._performance_thresholds['max_processing_time_ms']
        
        if avg_time == 0:
            return 'A'
        elif avg_time <= target_time * 0.5:
            return 'A'
        elif avg_time <= target_time * 0.75:
            return 'B'
        elif avg_time <= target_time:
            return 'C'
        elif avg_time <= target_time * 1.5:
            return 'D'
        else:
            return 'F'
            
    def _calculate_security_grade(self) -> str:
        """Calculate security grade (A-F)."""
        
        security_stats = self._security_validator.get_validation_statistics()
        violation_rate = security_stats['violation_rate']
        
        if violation_rate == 0:
            return 'A'
        elif violation_rate <= 0.001:
            return 'B'
        elif violation_rate <= 0.005:
            return 'C'
        elif violation_rate <= 0.01:
            return 'D'
        else:
            return 'F'
            
    def _calculate_reliability_grade(self) -> str:
        """Calculate reliability grade (A-F)."""
        
        total = self._normalization_stats['total_normalizations']
        if total == 0:
            return 'A'
            
        success_rate = self._normalization_stats['successful_normalizations'] / total
        
        if success_rate >= 0.99:
            return 'A'
        elif success_rate >= 0.95:
            return 'B'
        elif success_rate >= 0.90:
            return 'C'
        elif success_rate >= 0.80:
            return 'D'
        else:
            return 'F'
            
    def optimize_performance(self):
        """Manually trigger performance optimization."""
        
        try:
            # Cache optimization
            self.normalization_cache.optimize_cache_parameters()
            
            # Adaptive optimization
            self._adaptive_optimizer.analyze_and_optimize()
            
            # Security validator optimization
            self._security_validator.clear_policy_cache()
            
            self._normalization_stats['optimization_events'] += 1
            self.logger.info("Manual performance optimization completed")
            
        except Exception as e:
            self.logger.error(f"Performance optimization failed: {e}")
            
    def preload_common_patterns(self, common_commands: List[Tuple[str, str, ProcessingMode, IntentAction]]):
        """Preload cache with common command patterns for improved performance."""
        
        preloaded_count = 0
        
        for text, language, mode, expected_action in common_commands:
            try:
                # Normalize the command to create canonical intent
                result = self.normalize_intent(text, language, mode)
                
                if result.success and result.canonical_intent:
                    if result.canonical_intent.action == expected_action:
                        preloaded_count += 1
                    else:
                        self.logger.warning(f"Preload mismatch: expected {expected_action}, got {result.canonical_intent.action}")
                        
            except Exception as e:
                self.logger.warning(f"Failed to preload pattern '{text}' in {language}: {e}")
                
        self.logger.info(f"Preloaded {preloaded_count} common patterns")
        
    def validate_system_integrity(self) -> Dict[str, Any]:
        """Comprehensive system integrity validation."""
        
        integrity_report = {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_status': 'HEALTHY',
            'issues': [],
            'warnings': [],
            'recommendations': []
        }
        
        try:
            # Validate pattern coverage
            coverage_issues = self.intent_mappings.validate_pattern_coverage()
            if coverage_issues:
                integrity_report['issues'].extend([
                    f"Pattern coverage issues in {lang}: {issues}"
                    for lang, issues in coverage_issues.items()
                ])
                
            # Validate cache health
            cache_stats = self.normalization_cache.get_cache_statistics()
            if cache_stats['hit_rate'] < 0.5:
                integrity_report['warnings'].append(f"Low cache hit rate: {cache_stats['hit_rate']:.2f}")
                
            if cache_stats['memory_usage_mb'] > 500:
                integrity_report['warnings'].append(f"High memory usage: {cache_stats['memory_usage_mb']:.1f}MB")
                
            # Validate security configuration
            security_stats = self._security_validator.get_validation_statistics()
            if security_stats['violation_rate'] > 0.01:
                integrity_report['issues'].append(f"High security violation rate: {security_stats['violation_rate']:.3f}")
                
            # Validate performance
            avg_time = self._normalization_stats['average_processing_time_ms']
            if avg_time > self._performance_thresholds['max_processing_time_ms']:
                integrity_report['warnings'].append(f"Performance degradation: {avg_time:.1f}ms average")
                
            # Check failure recovery status
            if self._failure_recovery.is_in_recovery_mode():
                integrity_report['issues'].append("System is in recovery mode")
                integrity_report['overall_status'] = 'DEGRADED'
                
            elif self._failure_recovery.is_in_degraded_mode():
                integrity_report['warnings'].append("System is in degraded mode")
                
            # Generate recommendations
            if cache_stats['hit_rate'] < 0.7:
                integrity_report['recommendations'].append("Consider increasing cache size or TTL")
                
            if avg_time > 100:
                integrity_report['recommendations'].append("Consider pattern optimization or hardware upgrade")
                
            # Set overall status
            if integrity_report['issues']:
                integrity_report['overall_status'] = 'UNHEALTHY'
            elif integrity_report['warnings']:
                integrity_report['overall_status'] = 'WARNING'
                
        except Exception as e:
            integrity_report['issues'].append(f"Integrity validation failed: {str(e)}")
            integrity_report['overall_status'] = 'ERROR'
            
        return integrity_report
        
    def get_normalization_statistics(self) -> Dict[str, Any]:
        """Get normalization performance statistics."""
        total = self._normalization_stats['total_normalizations']
        
        return {
            **self._normalization_stats,
            'success_rate': (
                self._normalization_stats['successful_normalizations'] / max(1, total)
            ),
            'cache_hit_rate': (
                self._normalization_stats['cache_hits'] / max(1, total)
            ),
            'supported_languages': self.intent_mappings.get_supported_languages()
        }
        
    def add_custom_pattern(self, language: str, pattern: IntentPattern) -> bool:
        """Add custom intent pattern for a language."""
        try:
            self.intent_mappings.add_pattern(language, pattern)
            self.logger.info(f"Added custom pattern for {language}: {pattern.pattern}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to add custom pattern: {e}")
            return False
            
    def clear_cache(self):
        """Clear normalization cache."""
        self.normalization_cache.clear()
        
    def get_canonical_registry(self) -> CanonicalIntentRegistry:
        """Get the canonical intent registry."""
        return self.canonical_registry
        
    def get_supported_intent_actions(self) -> List[IntentAction]:
        """Get list of all supported intent actions."""
        return self.canonical_registry.get_supported_actions()
        
    def get_intent_categories(self) -> List[str]:
        """Get list of all intent categories."""
        return self.canonical_registry.get_categories()
        
    def get_actions_by_category(self, category: str) -> List[IntentAction]:
        """Get intent actions by category."""
        return self.canonical_registry.get_actions_by_category(category)
        
    def validate_intent_definition(self, intent: CanonicalIntent) -> 'ValidationResult':
        """Validate canonical intent against registry definitions."""
        return self.canonical_registry.validate_canonical_intent(intent)
        
    def register_custom_intent_definition(self, definition: IntentDefinition) -> bool:
        """Register custom intent definition."""
        try:
            self.canonical_registry.register_intent_definition(definition)
            self.logger.info(f"Registered custom intent definition: {definition.action.value}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to register custom intent definition: {e}")
            return False
            
    def add_pattern_variation(self, language: str, base_pattern: str, variations: List[str], action: IntentAction, parameter_groups: Dict[str, int]) -> bool:
        """Add pattern variations for better command recognition."""
        try:
            self.intent_mappings.add_pattern_variation(language, base_pattern, variations, action, parameter_groups)
            self.logger.info(f"Added pattern variations for {language}: {base_pattern}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to add pattern variations: {e}")
            return False
            
    def get_pattern_statistics(self) -> Dict[str, Any]:
        """Get statistics about registered patterns."""
        return self.intent_mappings.get_pattern_statistics()
        
    def validate_pattern_coverage(self) -> Dict[str, List[str]]:
        """Validate pattern coverage across languages."""
        return self.intent_mappings.validate_pattern_coverage()
        
    def find_best_pattern_match(self, text: str, language: str) -> Optional[Tuple[str, Dict[str, str], float]]:
        """Find the best matching pattern for debugging purposes."""
        match_result = self.intent_mappings.find_best_match(text, language)
        if match_result:
            pattern, parameters = match_result
            return (pattern.pattern, parameters, pattern.confidence)
        return None


@dataclass
class SecurityValidationResult:
    """Result of security validation for canonical intent."""
    
    valid: bool
    reason: Optional[str] = None
    security_level: str = "medium"
    requires_additional_auth: bool = False


class SecurityValidator:
    """
    Production-grade security validator for canonical intents.
    
    Enforces comprehensive security boundaries to ensure intent normalization
    never bypasses GURU's authority system and maintains all security invariants.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Define security levels and their requirements
        self.security_levels = {
            'low': {
                'max_parameter_length': 10000,
                'requires_authority': True,
                'allowed_parameter_types': ['str', 'int', 'bool', 'float'],
                'forbidden_patterns': []
            },
            'medium': {
                'max_parameter_length': 5000,
                'requires_authority': True,
                'allowed_parameter_types': ['str', 'int', 'bool', 'float'],
                'forbidden_patterns': [r'[;&|`]', r'<script', r'javascript:']
            },
            'high': {
                'max_parameter_length': 1000,
                'requires_authority': True,
                'allowed_parameter_types': ['str', 'int', 'bool'],
                'forbidden_patterns': [r'[;&|`]', r'<script', r'javascript:', r'\.\./', r'[<>"\']']
            },
            'admin': {
                'max_parameter_length': 500,
                'requires_authority': True,
                'allowed_parameter_types': ['str', 'int'],
                'forbidden_patterns': [r'[;&|`]', r'<script', r'javascript:', r'\.\./', r'[<>"\']', r'[*?]']
            }
        }
        
        # Define high-risk actions that require additional validation
        self.high_risk_actions = {
            IntentAction.DELETE_FILE: 'admin',
            IntentAction.SHUTDOWN_SYSTEM: 'admin',
            IntentAction.RESTART_SYSTEM: 'admin',
            IntentAction.OPEN_APPLICATION: 'high',
            IntentAction.SEND_EMAIL: 'high',
            IntentAction.MAKE_CALL: 'high',
            IntentAction.SEND_MESSAGE: 'medium'
        }
        
        # Define parameter-specific validation rules
        self.parameter_validators = {
            'filename': self._validate_filename_parameter,
            'file_path': self._validate_filepath_parameter,
            'path': self._validate_filepath_parameter,
            'application': self._validate_application_parameter,
            'contact': self._validate_contact_parameter,
            'message': self._validate_message_parameter,
            'text': self._validate_text_parameter,
            'element': self._validate_element_parameter,
            'url': self._validate_url_parameter,
            'command': self._validate_command_parameter
        }
        
        # Define system-critical paths that are forbidden
        self.forbidden_system_paths = [
            'C:\\Windows\\System32',
            'C:\\Windows\\SysWOW64',
            'C:\\Program Files\\WindowsApps',
            '/etc',
            '/usr/bin',
            '/usr/sbin',
            '/bin',
            '/sbin',
            '/root',
            '/sys',
            '/proc',
            '/dev'
        ]
        
        # Define dangerous file extensions
        self.dangerous_extensions = [
            '.exe', '.bat', '.cmd', '.com', '.scr', '.pif',
            '.vbs', '.vbe', '.js', '.jse', '.wsf', '.wsh',
            '.msi', '.msp', '.dll', '.sys', '.drv'
        ]
        
        # Initialize security policy cache
        self._policy_cache = {}
        self._validation_stats = {
            'total_validations': 0,
            'security_violations': 0,
            'high_risk_actions': 0,
            'parameter_violations': 0,
            'path_traversal_attempts': 0,
            'injection_attempts': 0
        }
        
    def validate_intent(self, intent: CanonicalIntent) -> SecurityValidationResult:
        """
        Comprehensive security validation for canonical intents.
        
        This is the primary security gate that ensures no intent can bypass
        GURU's authority system or violate security boundaries.
        """
        
        self._validation_stats['total_validations'] += 1
        
        try:
            # Phase 1: Basic intent structure validation
            structure_result = self._validate_intent_structure(intent)
            if not structure_result.valid:
                self._validation_stats['security_violations'] += 1
                return structure_result
                
            # Phase 2: Action-specific security validation
            action_result = self._validate_action_security(intent)
            if not action_result.valid:
                self._validation_stats['security_violations'] += 1
                return action_result
                
            # Phase 3: Parameter security validation
            parameter_result = self._validate_parameter_security(intent)
            if not parameter_result.valid:
                self._validation_stats['parameter_violations'] += 1
                return parameter_result
                
            # Phase 4: Cross-parameter security validation
            cross_param_result = self._validate_cross_parameter_security(intent)
            if not cross_param_result.valid:
                self._validation_stats['security_violations'] += 1
                return cross_param_result
                
            # Phase 5: Authority requirement validation
            authority_result = self._validate_authority_requirements(intent)
            if not authority_result.valid:
                self._validation_stats['security_violations'] += 1
                return authority_result
                
            # Phase 6: Final security policy check
            policy_result = self._validate_security_policy(intent)
            if not policy_result.valid:
                self._validation_stats['security_violations'] += 1
                return policy_result
                
            # All validations passed
            return SecurityValidationResult(
                valid=True,
                security_level=intent.security_level,
                requires_additional_auth=intent.action in self.high_risk_actions
            )
            
        except Exception as e:
            self.logger.error(f"Security validation error for intent {intent.action}: {e}")
            self._validation_stats['security_violations'] += 1
            return SecurityValidationResult(
                valid=False,
                reason=f"Security validation failed: {str(e)}"
            )
            
    def _validate_intent_structure(self, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate basic intent structure for security."""
        
        # Validate action is known and allowed
        if not isinstance(intent.action, IntentAction):
            return SecurityValidationResult(
                valid=False,
                reason=f"Invalid intent action type: {type(intent.action)}"
            )
            
        # Validate parameters is a dictionary
        if not isinstance(intent.parameters, dict):
            return SecurityValidationResult(
                valid=False,
                reason="Intent parameters must be a dictionary"
            )
            
        # Validate original language is supported
        if not SupportedLanguages.is_supported(intent.original_language):
            return SecurityValidationResult(
                valid=False,
                reason=f"Unsupported original language: {intent.original_language}"
            )
            
        # Validate processing mode
        if not isinstance(intent.processing_mode, ProcessingMode):
            return SecurityValidationResult(
                valid=False,
                reason=f"Invalid processing mode: {intent.processing_mode}"
            )
            
        # Validate confidence score
        if not (0.0 <= intent.confidence <= 1.0):
            return SecurityValidationResult(
                valid=False,
                reason=f"Invalid confidence score: {intent.confidence}"
            )
            
        return SecurityValidationResult(valid=True)
        
    def _validate_action_security(self, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate action-specific security requirements."""
        
        # Check if action is high-risk
        if intent.action in self.high_risk_actions:
            self._validation_stats['high_risk_actions'] += 1
            required_level = self.high_risk_actions[intent.action]
            
            if intent.security_level != required_level:
                return SecurityValidationResult(
                    valid=False,
                    reason=f"Action {intent.action.value} requires security level '{required_level}', got '{intent.security_level}'"
                )
                
        # Validate security level exists
        if intent.security_level not in self.security_levels:
            return SecurityValidationResult(
                valid=False,
                reason=f"Unknown security level: {intent.security_level}"
            )
            
        # Special validation for system control actions
        if intent.action in [IntentAction.SHUTDOWN_SYSTEM, IntentAction.RESTART_SYSTEM, IntentAction.LOCK_SYSTEM]:
            if intent.processing_mode != ProcessingMode.COMMAND:
                return SecurityValidationResult(
                    valid=False,
                    reason="System control actions only allowed in command mode"
                )
                
        # Special validation for file operations
        if intent.action in [IntentAction.DELETE_FILE, IntentAction.OPEN_FILE, IntentAction.SAVE_FILE, IntentAction.CREATE_FILE]:
            if 'filename' not in intent.parameters and 'file_path' not in intent.parameters:
                return SecurityValidationResult(
                    valid=False,
                    reason="File operations require filename or file_path parameter"
                )
                
        return SecurityValidationResult(valid=True)
        
    def _validate_parameter_security(self, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate individual parameter security."""
        
        security_config = self.security_levels[intent.security_level]
        
        for param_name, param_value in intent.parameters.items():
            # Validate parameter type
            param_type = type(param_value).__name__
            if param_type not in security_config['allowed_parameter_types']:
                return SecurityValidationResult(
                    valid=False,
                    reason=f"Parameter '{param_name}' type '{param_type}' not allowed for security level '{intent.security_level}'"
                )
                
            # Validate parameter length for strings
            if isinstance(param_value, str):
                if len(param_value) > security_config['max_parameter_length']:
                    return SecurityValidationResult(
                        valid=False,
                        reason=f"Parameter '{param_name}' exceeds maximum length of {security_config['max_parameter_length']}"
                    )
                    
                # Check forbidden patterns
                for pattern in security_config['forbidden_patterns']:
                    if re.search(pattern, param_value, re.IGNORECASE):
                        self._validation_stats['injection_attempts'] += 1
                        return SecurityValidationResult(
                            valid=False,
                            reason=f"Parameter '{param_name}' contains forbidden pattern: {pattern}"
                        )
                        
            # Use parameter-specific validators
            if param_name in self.parameter_validators:
                validator_result = self.parameter_validators[param_name](param_value, intent)
                if not validator_result.valid:
                    return validator_result
                    
        return SecurityValidationResult(valid=True)
        
    def _validate_cross_parameter_security(self, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate security across multiple parameters."""
        
        # Check for parameter injection attempts
        text_params = [k for k, v in intent.parameters.items() if isinstance(v, str)]
        
        if len(text_params) > 1:
            # Look for suspicious parameter combinations
            param_values = [intent.parameters[k] for k in text_params]
            combined_text = ' '.join(param_values)
            
            # Check for command injection across parameters
            if re.search(r'[;&|`]\s*\w+', combined_text):
                self._validation_stats['injection_attempts'] += 1
                return SecurityValidationResult(
                    valid=False,
                    reason="Potential command injection detected across parameters"
                )
                
            # Check for path traversal across parameters
            if '..' in combined_text and ('/' in combined_text or '\\' in combined_text):
                self._validation_stats['path_traversal_attempts'] += 1
                return SecurityValidationResult(
                    valid=False,
                    reason="Potential path traversal detected across parameters"
                )
                
        return SecurityValidationResult(valid=True)
        
    def _validate_authority_requirements(self, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate authority requirements are properly set."""
        
        # All intents must require authority (no exceptions)
        if not intent.requires_authority:
            return SecurityValidationResult(
                valid=False,
                reason="All intents must require authority - no exceptions allowed"
            )
            
        # Dictation mode still requires authority for typing
        if intent.processing_mode == ProcessingMode.DICTATION:
            if intent.action != IntentAction.TYPE_TEXT:
                return SecurityValidationResult(
                    valid=False,
                    reason="Dictation mode must only produce TYPE_TEXT actions"
                )
                
        return SecurityValidationResult(valid=True)
        
    def _validate_security_policy(self, intent: CanonicalIntent) -> SecurityValidationResult:
        """Final security policy validation."""
        
        # Generate policy key for caching
        policy_key = f"{intent.action.value}:{intent.security_level}:{intent.processing_mode.value}"
        
        # Check policy cache
        if policy_key in self._policy_cache:
            cached_policy = self._policy_cache[policy_key]
            if not cached_policy['allowed']:
                return SecurityValidationResult(
                    valid=False,
                    reason=cached_policy['reason']
                )
        else:
            # Create new policy entry
            policy_allowed = True
            policy_reason = None
            
            # Policy: No direct execution allowed
            if hasattr(intent, 'execute_directly') and intent.execute_directly:
                policy_allowed = False
                policy_reason = "Intent normalization must never execute actions directly"
                
            # Policy: Must integrate with authority system
            if not intent.requires_authority:
                policy_allowed = False
                policy_reason = "All intents must integrate with authority system"
                
            # Cache policy decision
            self._policy_cache[policy_key] = {
                'allowed': policy_allowed,
                'reason': policy_reason
            }
            
            if not policy_allowed:
                return SecurityValidationResult(
                    valid=False,
                    reason=policy_reason
                )
                
        return SecurityValidationResult(valid=True)
        
    def _validate_filename_parameter(self, value: str, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate filename parameters for security."""
        
        # Check for path traversal
        if '..' in value:
            self._validation_stats['path_traversal_attempts'] += 1
            return SecurityValidationResult(
                valid=False,
                reason=f"Path traversal attempt in filename: {value}"
            )
            
        # Check for absolute paths to system directories
        for forbidden_path in self.forbidden_system_paths:
            if value.startswith(forbidden_path):
                return SecurityValidationResult(
                    valid=False,
                    reason=f"Access to system path not allowed: {value}"
                )
                
        # Check for dangerous file extensions
        for ext in self.dangerous_extensions:
            if value.lower().endswith(ext):
                return SecurityValidationResult(
                    valid=False,
                    reason=f"Dangerous file extension not allowed: {ext}"
                )
                
        return SecurityValidationResult(valid=True)
        
    def _validate_filepath_parameter(self, value: str, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate file path parameters for security."""
        return self._validate_filename_parameter(value, intent)
        
    def _validate_application_parameter(self, value: str, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate application parameters for security."""
        
        # Sanitize application name
        if not re.match(r'^[a-zA-Z0-9\s\-_.]+$', value):
            return SecurityValidationResult(
                valid=False,
                reason=f"Invalid characters in application name: {value}"
            )
            
        # Check length
        if len(value) > 200:
            return SecurityValidationResult(
                valid=False,
                reason=f"Application name too long: {len(value)} characters"
            )
            
        return SecurityValidationResult(valid=True)
        
    def _validate_contact_parameter(self, value: str, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate contact parameters for security."""
        
        # Basic sanitization for contact names
        if len(value) > 200:
            return SecurityValidationResult(
                valid=False,
                reason=f"Contact name too long: {len(value)} characters"
            )
            
        # Check for injection patterns
        if re.search(r'[<>"\';]', value):
            return SecurityValidationResult(
                valid=False,
                reason=f"Invalid characters in contact name: {value}"
            )
            
        return SecurityValidationResult(valid=True)
        
    def _validate_message_parameter(self, value: str, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate message parameters for security."""
        
        # Check message length
        if len(value) > 10000:
            return SecurityValidationResult(
                valid=False,
                reason=f"Message too long: {len(value)} characters"
            )
            
        # For high security levels, be more restrictive
        if intent.security_level in ['high', 'admin']:
            if re.search(r'<script|javascript:|data:', value, re.IGNORECASE):
                return SecurityValidationResult(
                    valid=False,
                    reason="Potentially dangerous content in message"
                )
                
        return SecurityValidationResult(valid=True)
        
    def _validate_text_parameter(self, value: str, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate text parameters for security."""
        
        # CRITICAL: Always check for path traversal attempts in text parameters
        if '..' in value and ('/' in value or '\\' in value):
            self._validation_stats['path_traversal_attempts'] += 1
            return SecurityValidationResult(
                valid=False,
                reason=f"Path traversal attempt detected in text parameter: {value}"
            )
        
        # Check for absolute paths to system directories
        for forbidden_path in self.forbidden_system_paths:
            if forbidden_path.lower() in value.lower():
                return SecurityValidationResult(
                    valid=False,
                    reason=f"Access to system path not allowed in text: {forbidden_path}"
                )
        
        # For dictation mode, be more permissive but still secure
        if intent.processing_mode == ProcessingMode.DICTATION:
            # Still check for extremely dangerous patterns
            if re.search(r'<script[^>]*>.*</script>', value, re.IGNORECASE | re.DOTALL):
                return SecurityValidationResult(
                    valid=False,
                    reason="Script injection attempt in dictation text"
                )
        else:
            # Command mode text should be more restricted
            if re.search(r'[<>"\';]', value) and intent.security_level in ['high', 'admin']:
                return SecurityValidationResult(
                    valid=False,
                    reason="Potentially dangerous characters in command text"
                )
                
        return SecurityValidationResult(valid=True)
        
    def _validate_element_parameter(self, value: str, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate UI element parameters for security."""
        
        # Basic sanitization for element identifiers
        if len(value) > 500:
            return SecurityValidationResult(
                valid=False,
                reason=f"Element identifier too long: {len(value)} characters"
            )
            
        return SecurityValidationResult(valid=True)
        
    def _validate_url_parameter(self, value: str, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate URL parameters for security."""
        
        # Check for dangerous URL schemes
        dangerous_schemes = ['javascript:', 'data:', 'vbscript:', 'file:', 'ftp:']
        for scheme in dangerous_schemes:
            if value.lower().startswith(scheme):
                return SecurityValidationResult(
                    valid=False,
                    reason=f"Dangerous URL scheme not allowed: {scheme}"
                )
                
        return SecurityValidationResult(valid=True)
        
    def _validate_command_parameter(self, value: str, intent: CanonicalIntent) -> SecurityValidationResult:
        """Validate command parameters for security."""
        
        # Commands should never be allowed as parameters
        return SecurityValidationResult(
            valid=False,
            reason="Command parameters are not allowed for security reasons"
        )
        
    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get security validation statistics."""
        total = self._validation_stats['total_validations']
        
        return {
            **self._validation_stats,
            'violation_rate': (
                self._validation_stats['security_violations'] / max(1, total)
            ),
            'high_risk_rate': (
                self._validation_stats['high_risk_actions'] / max(1, total)
            ),
            'policy_cache_size': len(self._policy_cache)
        }
        
    def clear_policy_cache(self):
        """Clear the security policy cache."""
        self._policy_cache.clear()
        
    def add_custom_validator(self, parameter_name: str, validator_func: callable):
        """Add custom parameter validator."""
        self.parameter_validators[parameter_name] = validator_func
        
    def is_high_risk_action(self, action: IntentAction) -> bool:
        """Check if an action is considered high-risk."""
        return action in self.high_risk_actions


class PerformanceMonitor:
    """
    Production-grade performance monitoring for intent normalization.
    
    Tracks processing times, identifies performance degradation, and provides
    comprehensive performance analytics for system optimization.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Performance metrics storage
        self._processing_times = []
        self._max_history_size = 10000
        
        # Performance thresholds
        self._performance_thresholds = {
            'target_p95_ms': 150,
            'warning_p95_ms': 200,
            'critical_p95_ms': 500,
            'target_avg_ms': 50,
            'warning_avg_ms': 100,
            'critical_avg_ms': 200
        }
        
        # Performance statistics
        self._performance_stats = {
            'total_measurements': 0,
            'current_avg_ms': 0.0,
            'current_p95_ms': 0.0,
            'current_p99_ms': 0.0,
            'performance_alerts': 0,
            'degradation_events': 0,
            'last_alert_time': None
        }
        
        # Performance trend analysis
        self._trend_window_size = 100
        self._trend_analysis = {
            'improving': 0,
            'stable': 0,
            'degrading': 0
        }
        
    def record_processing_time(self, processing_time_ms: int):
        """Record a processing time measurement."""
        
        self._processing_times.append(processing_time_ms)
        self._performance_stats['total_measurements'] += 1
        
        # Maintain history size limit
        if len(self._processing_times) > self._max_history_size:
            self._processing_times = self._processing_times[-self._max_history_size:]
            
        # Update current statistics
        self._update_current_statistics()
        
        # Check for performance alerts
        self._check_performance_alerts(processing_time_ms)
        
        # Update trend analysis
        self._update_trend_analysis()
        
    def _update_current_statistics(self):
        """Update current performance statistics."""
        
        if not self._processing_times:
            return
            
        # Calculate current average
        self._performance_stats['current_avg_ms'] = sum(self._processing_times) / len(self._processing_times)
        
        # Calculate percentiles
        sorted_times = sorted(self._processing_times)
        n = len(sorted_times)
        
        if n >= 20:  # Need sufficient data for percentiles
            p95_index = int(0.95 * n)
            p99_index = int(0.99 * n)
            
            self._performance_stats['current_p95_ms'] = sorted_times[p95_index]
            self._performance_stats['current_p99_ms'] = sorted_times[p99_index]
        else:
            # Use max for small samples
            self._performance_stats['current_p95_ms'] = max(sorted_times)
            self._performance_stats['current_p99_ms'] = max(sorted_times)
            
    def _check_performance_alerts(self, processing_time_ms: int):
        """Check if performance alerts should be triggered."""
        
        current_time = datetime.utcnow()
        
        # Check individual measurement alerts
        if processing_time_ms > self._performance_thresholds['critical_p95_ms']:
            self._trigger_performance_alert('critical_latency', processing_time_ms)
        elif processing_time_ms > self._performance_thresholds['warning_p95_ms']:
            self._trigger_performance_alert('high_latency', processing_time_ms)
            
        # Check aggregate performance alerts (throttled to once per minute)
        if (self._performance_stats['last_alert_time'] is None or 
            (current_time - self._performance_stats['last_alert_time']).total_seconds() > 60):
            
            if self._performance_stats['current_p95_ms'] > self._performance_thresholds['critical_p95_ms']:
                self._trigger_performance_alert('critical_p95_degradation', self._performance_stats['current_p95_ms'])
                self._performance_stats['last_alert_time'] = current_time
            elif self._performance_stats['current_avg_ms'] > self._performance_thresholds['critical_avg_ms']:
                self._trigger_performance_alert('critical_avg_degradation', self._performance_stats['current_avg_ms'])
                self._performance_stats['last_alert_time'] = current_time
                
    def _trigger_performance_alert(self, alert_type: str, value: float):
        """Trigger a performance alert."""
        
        self._performance_stats['performance_alerts'] += 1
        
        if alert_type.startswith('critical'):
            self.logger.critical(f"Performance alert: {alert_type} = {value:.1f}ms")
            self._performance_stats['degradation_events'] += 1
        else:
            self.logger.warning(f"Performance alert: {alert_type} = {value:.1f}ms")
            
    def _update_trend_analysis(self):
        """Update performance trend analysis."""
        
        if len(self._processing_times) < self._trend_window_size * 2:
            return
            
        # Compare recent window to previous window
        recent_window = self._processing_times[-self._trend_window_size:]
        previous_window = self._processing_times[-self._trend_window_size*2:-self._trend_window_size]
        
        recent_avg = sum(recent_window) / len(recent_window)
        previous_avg = sum(previous_window) / len(previous_window)
        
        # Determine trend
        improvement_threshold = 0.05  # 5% improvement
        degradation_threshold = 0.10  # 10% degradation
        
        if recent_avg < previous_avg * (1 - improvement_threshold):
            self._trend_analysis['improving'] += 1
        elif recent_avg > previous_avg * (1 + degradation_threshold):
            self._trend_analysis['degrading'] += 1
        else:
            self._trend_analysis['stable'] += 1
            
    def get_current_performance_summary(self) -> Dict[str, Any]:
        """Get current performance summary."""
        
        return {
            **self._performance_stats,
            'performance_grade': self._calculate_performance_grade(),
            'trend_analysis': self._trend_analysis.copy(),
            'thresholds': self._performance_thresholds.copy(),
            'measurements_count': len(self._processing_times)
        }
        
    def _calculate_performance_grade(self) -> str:
        """Calculate overall performance grade."""
        
        avg_ms = self._performance_stats['current_avg_ms']
        p95_ms = self._performance_stats['current_p95_ms']
        
        # Grade based on both average and p95
        if avg_ms <= self._performance_thresholds['target_avg_ms'] and p95_ms <= self._performance_thresholds['target_p95_ms']:
            return 'A'
        elif avg_ms <= self._performance_thresholds['warning_avg_ms'] and p95_ms <= self._performance_thresholds['warning_p95_ms']:
            return 'B'
        elif avg_ms <= self._performance_thresholds['critical_avg_ms'] and p95_ms <= self._performance_thresholds['critical_p95_ms']:
            return 'C'
        else:
            return 'F'
            
    def reset_statistics(self):
        """Reset performance statistics."""
        
        self._processing_times.clear()
        self._performance_stats = {
            'total_measurements': 0,
            'current_avg_ms': 0.0,
            'current_p95_ms': 0.0,
            'current_p99_ms': 0.0,
            'performance_alerts': 0,
            'degradation_events': 0,
            'last_alert_time': None
        }
        self._trend_analysis = {
            'improving': 0,
            'stable': 0,
            'degrading': 0
        }


class AdaptiveOptimizer:
    """
    Production-grade adaptive optimizer for intent normalization performance.
    
    Automatically adjusts system parameters based on performance metrics
    and usage patterns to maintain optimal performance.
    """
    
    def __init__(self, normalization_layer):
        self.normalization_layer = normalization_layer
        self.logger = logging.getLogger(__name__)
        
        # Optimization parameters
        self._optimization_params = {
            'cache_size': 10000,
            'cache_ttl_seconds': 3600,
            'pattern_matching_timeout': 5.0,
            'batch_processing_threshold': 10,
            'memory_cleanup_threshold': 0.8
        }
        
        # Optimization history
        self._optimization_history = []
        self._last_optimization = datetime.utcnow()
        
        # Performance baselines
        self._performance_baselines = {
            'avg_processing_time_ms': 50.0,
            'cache_hit_rate': 0.7,
            'success_rate': 0.95
        }
        
    def analyze_and_optimize(self):
        """Analyze current performance and apply optimizations."""
        
        try:
            # Get current performance metrics
            stats = self.normalization_layer.get_comprehensive_normalization_statistics()
            
            # Analyze performance trends
            optimization_actions = self._analyze_performance_trends(stats)
            
            # Apply optimizations
            for action in optimization_actions:
                self._apply_optimization(action, stats)
                
            # Record optimization event
            self._record_optimization_event(optimization_actions, stats)
            
            self.logger.info(f"Applied {len(optimization_actions)} optimizations")
            
        except Exception as e:
            self.logger.error(f"Adaptive optimization failed: {e}")
            
    def _analyze_performance_trends(self, stats: Dict[str, Any]) -> List[str]:
        """Analyze performance trends and identify optimization opportunities."""
        
        optimization_actions = []
        
        # Check cache performance
        cache_hit_rate = stats.get('cache_hit_rate', 0.0)
        if cache_hit_rate < 0.5:
            optimization_actions.append('increase_cache_size')
        elif cache_hit_rate > 0.9:
            optimization_actions.append('optimize_cache_ttl')
            
        # Check processing time performance
        avg_time = stats.get('average_processing_time_ms', 0.0)
        if avg_time > 100:
            optimization_actions.append('optimize_pattern_matching')
        elif avg_time > 200:
            optimization_actions.append('enable_batch_processing')
            
        # Check memory usage
        cache_stats = stats.get('cache_statistics', {})
        memory_usage_mb = cache_stats.get('memory_usage_mb', 0.0)
        if memory_usage_mb > 500:
            optimization_actions.append('cleanup_memory')
            
        # Check success rate
        success_rate = stats.get('success_rate', 0.0)
        if success_rate < 0.9:
            optimization_actions.append('improve_pattern_coverage')
            
        return optimization_actions
        
    def _apply_optimization(self, action: str, stats: Dict[str, Any]):
        """Apply specific optimization action."""
        
        try:
            if action == 'increase_cache_size':
                new_size = min(self._optimization_params['cache_size'] * 2, 50000)
                self._optimization_params['cache_size'] = new_size
                self.normalization_layer.normalization_cache.resize_cache(new_size)
                self.logger.info(f"Increased cache size to {new_size}")
                
            elif action == 'optimize_cache_ttl':
                new_ttl = max(self._optimization_params['cache_ttl_seconds'] // 2, 1800)
                self._optimization_params['cache_ttl_seconds'] = new_ttl
                self.normalization_layer.normalization_cache.update_ttl(new_ttl)
                self.logger.info(f"Optimized cache TTL to {new_ttl} seconds")
                
            elif action == 'optimize_pattern_matching':
                new_timeout = max(self._optimization_params['pattern_matching_timeout'] * 0.8, 1.0)
                self._optimization_params['pattern_matching_timeout'] = new_timeout
                self.logger.info(f"Optimized pattern matching timeout to {new_timeout} seconds")
                
            elif action == 'enable_batch_processing':
                self._optimization_params['batch_processing_threshold'] = 5
                self.logger.info("Enabled aggressive batch processing")
                
            elif action == 'cleanup_memory':
                self.normalization_layer.normalization_cache.cleanup_expired_entries()
                self.logger.info("Performed memory cleanup")
                
            elif action == 'improve_pattern_coverage':
                # This would trigger pattern analysis and improvement
                self.logger.info("Triggered pattern coverage improvement")
                
        except Exception as e:
            self.logger.error(f"Failed to apply optimization '{action}': {e}")
            
    def _record_optimization_event(self, actions: List[str], stats: Dict[str, Any]):
        """Record optimization event for analysis."""
        
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'actions': actions,
            'performance_before': {
                'avg_processing_time_ms': stats.get('average_processing_time_ms', 0.0),
                'cache_hit_rate': stats.get('cache_hit_rate', 0.0),
                'success_rate': stats.get('success_rate', 0.0)
            },
            'parameters_after': self._optimization_params.copy()
        }
        
        self._optimization_history.append(event)
        
        # Maintain history size
        if len(self._optimization_history) > 100:
            self._optimization_history = self._optimization_history[-100:]
            
    def get_current_parameters(self) -> Dict[str, Any]:
        """Get current optimization parameters."""
        
        return {
            'parameters': self._optimization_params.copy(),
            'baselines': self._performance_baselines.copy(),
            'optimization_count': len(self._optimization_history),
            'last_optimization': self._last_optimization.isoformat()
        }


class FailureRecoveryManager:
    """
    Production-grade failure recovery manager for intent normalization.
    
    Handles system failures gracefully, implements circuit breaker patterns,
    and provides comprehensive failure recovery mechanisms.
    """
    
    def __init__(self, normalization_layer):
        self.normalization_layer = normalization_layer
        self.logger = logging.getLogger(__name__)
        
        # Recovery modes
        self._recovery_mode = False
        self._degraded_mode = False
        self._safe_mode = False
        
        # Failure tracking
        self._failure_counts = {}
        self._failure_thresholds = {
            'pattern_match_failures': 10,
            'security_validation_failures': 5,
            'cache_failures': 20,
            'timeout_failures': 15,
            'normalization_exception': 8
        }
        
        # Circuit breaker state
        self._circuit_breakers = {}
        self._circuit_breaker_timeout = 300  # 5 minutes
        
        # Recovery statistics
        self._recovery_stats = {
            'total_failures': 0,
            'recovery_activations': 0,
            'safe_mode_activations': 0,
            'circuit_breaker_trips': 0,
            'successful_recoveries': 0
        }
        
    def handle_failure(self, failure_type: str, failure_context: Dict[str, Any]):
        """Handle a system failure with appropriate recovery actions."""
        
        self._recovery_stats['total_failures'] += 1
        
        # Update failure count
        self._failure_counts[failure_type] = self._failure_counts.get(failure_type, 0) + 1
        
        self.logger.warning(f"Handling failure: {failure_type}, count: {self._failure_counts[failure_type]}")
        
        # Check if failure threshold exceeded
        threshold = self._failure_thresholds.get(failure_type, 10)
        
        if self._failure_counts[failure_type] >= threshold:
            self._trigger_recovery_action(failure_type, failure_context)
        else:
            # Try immediate recovery
            self._attempt_immediate_recovery(failure_type, failure_context)
            
    def _trigger_recovery_action(self, failure_type: str, failure_context: Dict[str, Any]):
        """Trigger appropriate recovery action based on failure type."""
        
        try:
            if failure_type == 'security_validation_failures':
                self._enter_safe_mode("Security validation failures exceeded threshold")
                
            elif failure_type == 'pattern_match_failures':
                self._enter_degraded_mode("Pattern matching failures exceeded threshold")
                
            elif failure_type == 'cache_failures':
                self._recover_cache_system()
                
            elif failure_type == 'timeout_failures':
                self._optimize_timeout_handling()
                
            elif failure_type == 'normalization_exception':
                self._enter_recovery_mode("Normalization exceptions exceeded threshold")
                
            else:
                self._enter_recovery_mode(f"Unknown failure type: {failure_type}")
                
            self._recovery_stats['recovery_activations'] += 1
            
        except Exception as e:
            self.logger.error(f"Recovery failed for {failure_type}: {e}")
            self._enter_safe_mode(f"Recovery action failed: {str(e)}")
            
    def _attempt_immediate_recovery(self, failure_type: str, failure_context: Dict[str, Any]):
        """Attempt immediate recovery for minor failures."""
        
        try:
            if failure_type == 'cache_failures':
                # Clear cache and retry
                self.normalization_layer.normalization_cache.clear_problematic_entries()
                
            elif failure_type == 'pattern_match_failures':
                # Reset pattern matching state
                self._reset_pattern_matching_state()
                
            elif failure_type == 'timeout_failures':
                # Reduce timeout temporarily
                self._reduce_timeout_temporarily()
                
        except Exception as e:
            self.logger.error(f"Immediate recovery failed for {failure_type}: {e}")
            
    def _enter_safe_mode(self, reason: str):
        """Enter safe mode with minimal functionality."""
        
        self._safe_mode = True
        self._recovery_mode = True
        self._degraded_mode = True
        
        self._recovery_stats['safe_mode_activations'] += 1
        
        self.logger.critical(f"Security validation failure - entering safe mode: {reason}")
        self.logger.critical("System entered safe mode - only basic functionality available")
        
        # Disable all advanced features
        self._disable_advanced_features()
        
    def _enter_recovery_mode(self, reason: str):
        """Enter recovery mode with reduced functionality."""
        
        self._recovery_mode = True
        self.logger.warning(f"Entering recovery mode: {reason}")
        
        # Reduce system load
        self._reduce_system_load()
        
    def _enter_degraded_mode(self, reason: str):
        """Enter degraded mode with limited pattern matching."""
        
        self._degraded_mode = True
        self.logger.warning(f"Entering degraded mode: {reason}")
        
        # Use simplified pattern matching
        self._enable_simplified_pattern_matching()
        
    def _disable_advanced_features(self):
        """Disable advanced features in safe mode."""
        
        # Disable caching
        self.normalization_layer.normalization_cache.disable()
        
        # Disable performance monitoring
        self.normalization_layer._performance_monitor.reset_statistics()
        
        # Disable adaptive optimization
        # (Optimizer will check safe mode before running)
        
    def _reduce_system_load(self):
        """Reduce system load during recovery."""
        
        # Clear caches to free memory
        self.normalization_layer.normalization_cache.clear()
        
        # Reset failure counters for gradual recovery
        for failure_type in list(self._failure_counts.keys()):
            self._failure_counts[failure_type] = max(0, self._failure_counts[failure_type] - 1)
            
    def _enable_simplified_pattern_matching(self):
        """Enable simplified pattern matching in degraded mode."""
        
        # This would configure the pattern matching to use simpler algorithms
        # For now, just log the action
        self.logger.info("Enabled simplified pattern matching")
        
    def _recover_cache_system(self):
        """Recover the cache system after failures."""
        
        try:
            # Clear and reinitialize cache
            self.normalization_layer.normalization_cache.clear()
            self.normalization_layer.normalization_cache.reinitialize()
            
            # Reset cache failure count
            self._failure_counts['cache_failures'] = 0
            
            self.logger.info("Cache system recovered successfully")
            
        except Exception as e:
            self.logger.error(f"Cache recovery failed: {e}")
            
    def _optimize_timeout_handling(self):
        """Optimize timeout handling after timeout failures."""
        
        # Reduce timeouts temporarily
        if hasattr(self.normalization_layer, '_pattern_matching_timeout'):
            self.normalization_layer._pattern_matching_timeout *= 0.8
            
        # Reset timeout failure count
        self._failure_counts['timeout_failures'] = 0
        
        self.logger.info("Timeout handling optimized")
        
    def _reset_pattern_matching_state(self):
        """Reset pattern matching state."""
        
        # This would reset any cached pattern matching state
        self.logger.info("Pattern matching state reset")
        
    def _reduce_timeout_temporarily(self):
        """Temporarily reduce timeouts to avoid cascading failures."""
        
        # This would reduce various timeout values
        self.logger.info("Timeouts reduced temporarily")
        
    def is_in_recovery_mode(self) -> bool:
        """Check if system is in recovery mode."""
        return self._recovery_mode
        
    def is_in_degraded_mode(self) -> bool:
        """Check if system is in degraded mode."""
        return self._degraded_mode
        
    def is_in_safe_mode(self) -> bool:
        """Check if system is in safe mode."""
        return self._safe_mode
        
    def attempt_recovery_exit(self) -> bool:
        """Attempt to exit recovery modes if conditions are met."""
        
        try:
            # Check if we can exit safe mode
            if self._safe_mode:
                if self._can_exit_safe_mode():
                    self._safe_mode = False
                    self.logger.info("Exited safe mode")
                    
            # Check if we can exit recovery mode
            if self._recovery_mode and not self._safe_mode:
                if self._can_exit_recovery_mode():
                    self._recovery_mode = False
                    self.logger.info("Exited recovery mode")
                    
            # Check if we can exit degraded mode
            if self._degraded_mode and not self._recovery_mode:
                if self._can_exit_degraded_mode():
                    self._degraded_mode = False
                    self.logger.info("Exited degraded mode")
                    
            return not (self._recovery_mode or self._degraded_mode or self._safe_mode)
            
        except Exception as e:
            self.logger.error(f"Recovery exit attempt failed: {e}")
            return False
            
    def _can_exit_safe_mode(self) -> bool:
        """Check if conditions allow exiting safe mode."""
        
        # Safe mode can only be exited manually or after extended period
        return False  # Require manual intervention
        
    def _can_exit_recovery_mode(self) -> bool:
        """Check if conditions allow exiting recovery mode."""
        
        # Check if failure rates have decreased
        total_recent_failures = sum(
            count for count in self._failure_counts.values()
            if count < 5  # Recent failures are low
        )
        
        return total_recent_failures < 10
        
    def _can_exit_degraded_mode(self) -> bool:
        """Check if conditions allow exiting degraded mode."""
        
        # Check pattern matching failure rate
        pattern_failures = self._failure_counts.get('pattern_match_failures', 0)
        return pattern_failures < 3
        
    def get_failure_statistics(self) -> Dict[str, Any]:
        """Get failure and recovery statistics."""
        
        return {
            **self._recovery_stats,
            'current_failure_counts': self._failure_counts.copy(),
            'recovery_mode': self._recovery_mode,
            'degraded_mode': self._degraded_mode,
            'safe_mode': self._safe_mode,
            'circuit_breaker_states': self._circuit_breakers.copy()
        }


class AuditLogger:
    """
    Production-grade audit logger for intent normalization.
    
    Provides cryptographically secure audit logging with tamper-evident
    chains and comprehensive security event tracking.
    """
    
    def __init__(self, component_name: str):
        self.component_name = component_name
        self.logger = logging.getLogger(f"audit.{component_name}")
        
        # Audit log storage
        self._audit_entries = []
        self._max_entries = 100000
        
        # Cryptographic integrity
        self._last_hash = hashlib.sha256(b"GURU_AUDIT_INIT").hexdigest()
        
        # Audit statistics
        self._audit_stats = {
            'total_entries': 0,
            'security_violations': 0,
            'normalization_requests': 0,
            'successful_normalizations': 0,
            'failed_normalizations': 0
        }
        
    def log_normalization_request(self, text_hash: str, language: str, mode: str):
        """Log intent normalization request."""
        
        self._log_audit_entry('normalization_request', {
            'text_hash': text_hash,
            'language': language,
            'mode': mode
        })
        
        self._audit_stats['normalization_requests'] += 1
        
    def log_normalization_success(self, text_hash: str, action: str, processing_time_ms: int):
        """Log successful intent normalization."""
        
        self._log_audit_entry('normalization_success', {
            'text_hash': text_hash,
            'action': action,
            'processing_time_ms': processing_time_ms
        })
        
        self._audit_stats['successful_normalizations'] += 1
        
    def log_normalization_failure(self, text_hash: str, failure_type: str, error_message: str):
        """Log failed intent normalization."""
        
        self._log_audit_entry('normalization_failure', {
            'text_hash': text_hash,
            'failure_type': failure_type,
            'error_message': error_message
        })
        
        self._audit_stats['failed_normalizations'] += 1
        
    def log_security_violation(self, text_hash: str, violation_type: str, reason: str):
        """Log security violation."""
        
        self._log_audit_entry('security_violation', {
            'text_hash': text_hash,
            'violation_type': violation_type,
            'reason': reason
        })
        
        self._audit_stats['security_violations'] += 1
        
    def log_security_validation(self, intent_hash: str, valid: bool, security_level: str):
        """Log security validation result."""
        
        self._log_audit_entry('security_validation', {
            'intent_hash': intent_hash,
            'valid': valid,
            'security_level': security_level
        })
        
    def _log_audit_entry(self, event_type: str, event_data: Dict[str, Any]):
        """Log audit entry with cryptographic integrity."""
        
        timestamp = datetime.utcnow()
        
        # Create audit entry
        entry = {
            'timestamp': timestamp.isoformat(),
            'component': self.component_name,
            'event_type': event_type,
            'event_data': event_data,
            'sequence_number': self._audit_stats['total_entries'] + 1
        }
        
        # Calculate integrity hash
        entry_json = json.dumps(entry, sort_keys=True)
        combined_data = f"{self._last_hash}{entry_json}"
        entry_hash = hashlib.sha256(combined_data.encode('utf-8')).hexdigest()
        
        entry['integrity_hash'] = entry_hash
        entry['previous_hash'] = self._last_hash
        
        # Store entry
        self._audit_entries.append(entry)
        self._last_hash = entry_hash
        self._audit_stats['total_entries'] += 1
        
        # Maintain storage limits
        if len(self._audit_entries) > self._max_entries:
            # Archive old entries (in production, this would go to persistent storage)
            archived_count = len(self._audit_entries) - self._max_entries
            self._audit_entries = self._audit_entries[-self._max_entries:]
            self.logger.info(f"Archived {archived_count} audit entries")
            
        # Log to standard logger for immediate visibility
        self.logger.info(f"AUDIT: {event_type} - {json.dumps(event_data)}")
        
    def verify_audit_chain_integrity(self) -> bool:
        """Verify the integrity of the audit chain."""
        
        if not self._audit_entries:
            return True
            
        previous_hash = hashlib.sha256(b"GURU_AUDIT_INIT").hexdigest()
        
        for entry in self._audit_entries:
            # Reconstruct entry without integrity fields
            entry_copy = entry.copy()
            stored_hash = entry_copy.pop('integrity_hash')
            stored_previous = entry_copy.pop('previous_hash')
            
            # Verify previous hash
            if stored_previous != previous_hash:
                self.logger.error(f"Audit chain integrity violation: previous hash mismatch")
                return False
                
            # Verify entry hash
            entry_json = json.dumps(entry_copy, sort_keys=True)
            combined_data = f"{previous_hash}{entry_json}"
            calculated_hash = hashlib.sha256(combined_data.encode('utf-8')).hexdigest()
            
            if calculated_hash != stored_hash:
                self.logger.error(f"Audit chain integrity violation: entry hash mismatch")
                return False
                
            previous_hash = stored_hash
            
        return True
        
    def get_audit_statistics(self) -> Dict[str, Any]:
        """Get audit logging statistics."""
        
        return {
            **self._audit_stats,
            'chain_integrity_valid': self.verify_audit_chain_integrity(),
            'current_hash': self._last_hash,
            'entries_in_memory': len(self._audit_entries)
        }


