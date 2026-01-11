"""
Input Validation and Sanitization Engine

Production-grade input validation system that prevents injection attacks,
validates input parameters, and enforces security policies for all input simulation.

This validator implements defense-in-depth security measures to prevent:
- Input injection attacks
- Malicious key combinations
- Buffer overflow attempts
- Privilege escalation through input
- Unauthorized system access
"""

import re
import logging
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class ValidationSeverity(Enum):
    """Severity levels for validation violations"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Result of input validation operation"""
    is_valid: bool
    violations: List[str] = None
    warnings: List[str] = None
    sanitized_input: Optional[str] = None
    severity: ValidationSeverity = ValidationSeverity.INFO
    
    def __post_init__(self):
        if self.violations is None:
            self.violations = []
        if self.warnings is None:
            self.warnings = []


class InputValidator:
    """
    Comprehensive input validation and sanitization engine.
    
    This validator implements multiple layers of security validation:
    1. Content validation (malicious patterns, injection attempts)
    2. Length validation (buffer overflow prevention)
    3. Character validation (allowed character sets)
    4. Key combination validation (privilege escalation prevention)
    5. Rate limiting validation (abuse prevention)
    
    All validation failures are logged for security monitoring.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Security configuration
        self.max_text_length = 10000
        self.max_key_combination_length = 10
        self.max_single_key_length = 50
        
        # Dangerous patterns that could indicate injection attempts
        self.dangerous_patterns = self._initialize_dangerous_patterns()
        
        # Allowed character sets for different input types
        self.allowed_text_chars = self._initialize_allowed_text_chars()
        
        # Dangerous key combinations that require special validation
        self.dangerous_key_combinations = self._initialize_dangerous_key_combinations()
        
        # System keys that require elevated security
        self.system_keys = self._initialize_system_keys()
        
        self.logger.info("InputValidator initialized with comprehensive security rules")
    
    def _initialize_dangerous_patterns(self) -> List[re.Pattern]:
        """Initialize patterns that could indicate malicious input"""
        patterns = [
            # Command injection patterns
            re.compile(r'[;&|`$(){}[\]\\]', re.IGNORECASE),
            
            # Script injection patterns
            re.compile(r'<script[^>]*>', re.IGNORECASE),
            re.compile(r'javascript:', re.IGNORECASE),
            re.compile(r'vbscript:', re.IGNORECASE),
            
            # Path traversal patterns
            re.compile(r'\.\.[\\/]', re.IGNORECASE),
            re.compile(r'[\\/]\.\.', re.IGNORECASE),
            
            # Null byte injection
            re.compile(r'\x00'),
            
            # Control character abuse
            re.compile(r'[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]'),
            
            # Unicode control characters
            re.compile(r'[\u0000-\u001F\u007F-\u009F]'),
            
            # Excessive repetition (potential DoS)
            re.compile(r'(.)\1{100,}'),
            
            # Binary data patterns
            re.compile(r'[\x80-\xFF]{10,}'),
        ]
        return patterns
    
    def _initialize_allowed_text_chars(self) -> Set[str]:
        """Initialize allowed characters for text input"""
        # Allow printable ASCII, common Unicode ranges, and essential whitespace
        allowed = set()
        
        # Printable ASCII (32-126)
        for i in range(32, 127):
            allowed.add(chr(i))
        
        # Essential whitespace
        allowed.update(['\t', '\n', '\r'])
        
        # Common Unicode ranges (letters, numbers, punctuation)
        # Latin-1 Supplement (128-255)
        for i in range(128, 256):
            char = chr(i)
            if char.isprintable():
                allowed.add(char)
        
        # Additional Unicode ranges for international text
        # This is a conservative approach - expand as needed
        unicode_ranges = [
            (0x00A0, 0x00FF),  # Latin-1 Supplement
            (0x0100, 0x017F),  # Latin Extended-A
            (0x0180, 0x024F),  # Latin Extended-B
            (0x1E00, 0x1EFF),  # Latin Extended Additional
            (0x2000, 0x206F),  # General Punctuation
            (0x20A0, 0x20CF),  # Currency Symbols
            (0x2100, 0x214F),  # Letterlike Symbols
        ]
        
        for start, end in unicode_ranges:
            for i in range(start, end + 1):
                try:
                    char = chr(i)
                    if char.isprintable():
                        allowed.add(char)
                except ValueError:
                    continue
        
        return allowed
    
    def _initialize_dangerous_key_combinations(self) -> Set[Tuple[str, ...]]:
        """Initialize dangerous key combinations that require special validation"""
        return {
            # System shutdown/restart
            ('ALT', 'F4'),
            ('CTRL', 'ALT', 'DELETE'),
            ('CTRL', 'SHIFT', 'ESCAPE'),
            
            # System access
            ('WINDOWS', 'R'),
            ('WINDOWS', 'X'),
            ('WINDOWS', 'I'),
            
            # Task manager and system tools
            ('CTRL', 'SHIFT', 'ESCAPE'),
            ('CTRL', 'ALT', 'T'),
            
            # Registry and system configuration
            ('WINDOWS', 'R'),  # Run dialog
            
            # Command prompt access
            ('WINDOWS', 'R'),  # Could be used to open cmd
            
            # Browser developer tools (potential security risk)
            ('F12',),
            ('CTRL', 'SHIFT', 'I'),
            ('CTRL', 'SHIFT', 'J'),
            ('CTRL', 'SHIFT', 'C'),
        }
    
    def _initialize_system_keys(self) -> Set[str]:
        """Initialize system keys that require elevated validation"""
        return {
            'WINDOWS', 'ALT', 'CTRL', 'SHIFT',
            'F1', 'F2', 'F3', 'F4', 'F5', 'F6',
            'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
            'DELETE', 'INSERT', 'PAUSE', 'SCROLL_LOCK',
            'NUM_LOCK', 'CAPS_LOCK'
        }
    
    def validate_text_input(self, text: str) -> ValidationResult:
        """
        Validate text input for security and safety.
        
        Args:
            text: Text to validate
            
        Returns:
            ValidationResult with validation status and details
        """
        violations = []
        warnings = []
        severity = ValidationSeverity.INFO
        
        # Basic null/empty check
        if text is None:
            violations.append("Text input cannot be None")
            return ValidationResult(
                is_valid=False,
                violations=violations,
                severity=ValidationSeverity.ERROR
            )
        
        # Length validation
        if len(text) == 0:
            warnings.append("Empty text input")
        elif len(text) > self.max_text_length:
            violations.append(f"Text length {len(text)} exceeds maximum {self.max_text_length}")
            severity = ValidationSeverity.ERROR
        
        # Character validation
        invalid_chars = []
        for i, char in enumerate(text):
            if char not in self.allowed_text_chars:
                invalid_chars.append(f"'{char}' at position {i}")
                if len(invalid_chars) >= 10:  # Limit reporting
                    invalid_chars.append("... (more invalid characters)")
                    break
        
        if invalid_chars:
            violations.append(f"Invalid characters found: {', '.join(invalid_chars)}")
            severity = ValidationSeverity.WARNING
        
        # Dangerous pattern detection
        for pattern in self.dangerous_patterns:
            matches = pattern.findall(text)
            if matches:
                violations.append(f"Dangerous pattern detected: {pattern.pattern}")
                severity = ValidationSeverity.CRITICAL
                break  # Stop on first critical violation
        
        # Encoding validation
        try:
            text.encode('utf-8')
        except UnicodeEncodeError as e:
            violations.append(f"Text encoding error: {str(e)}")
            severity = ValidationSeverity.ERROR
        
        # Excessive repetition check
        if len(text) > 100:
            # Check for patterns that might indicate DoS attempts
            char_counts = {}
            for char in text:
                char_counts[char] = char_counts.get(char, 0) + 1
            
            max_char_count = max(char_counts.values()) if char_counts else 0
            if max_char_count > len(text) * 0.8:  # More than 80% same character
                violations.append("Excessive character repetition detected")
                severity = ValidationSeverity.WARNING
        
        # Binary data detection
        try:
            # Check if text contains mostly non-printable characters
            printable_count = sum(1 for char in text if char.isprintable() or char.isspace())
            if len(text) > 10 and printable_count / len(text) < 0.7:
                violations.append("Potential binary data detected")
                severity = ValidationSeverity.WARNING
        except Exception:
            pass
        
        is_valid = len(violations) == 0 or severity in [ValidationSeverity.INFO, ValidationSeverity.WARNING]
        
        # Log validation result
        if violations:
            self.logger.warning(f"Text validation violations: {violations}")
        if warnings:
            self.logger.info(f"Text validation warnings: {warnings}")
        
        return ValidationResult(
            is_valid=is_valid,
            violations=violations,
            warnings=warnings,
            severity=severity
        )
    
    def validate_key_combination(self, keys: List[str]) -> ValidationResult:
        """
        Validate key combination for security and safety.
        
        Args:
            keys: List of key names in the combination
            
        Returns:
            ValidationResult with validation status and details
        """
        violations = []
        warnings = []
        severity = ValidationSeverity.INFO
        
        # Basic validation
        if not keys:
            violations.append("Key combination cannot be empty")
            return ValidationResult(
                is_valid=False,
                violations=violations,
                severity=ValidationSeverity.ERROR
            )
        
        # Length validation
        if len(keys) > self.max_key_combination_length:
            violations.append(f"Key combination length {len(keys)} exceeds maximum {self.max_key_combination_length}")
            severity = ValidationSeverity.ERROR
        
        # Individual key validation
        for key in keys:
            if not isinstance(key, str):
                violations.append(f"Key must be string, got {type(key)}")
                severity = ValidationSeverity.ERROR
                continue
            
            if len(key) > self.max_single_key_length:
                violations.append(f"Key name '{key}' too long (max {self.max_single_key_length})")
                severity = ValidationSeverity.ERROR
            
            # Check for invalid characters in key names
            if not re.match(r'^[A-Z0-9_]+$', key):
                violations.append(f"Invalid key name format: '{key}'")
                severity = ValidationSeverity.WARNING
        
        # Dangerous combination check
        key_tuple = tuple(sorted(keys))  # Sort for consistent comparison
        if key_tuple in self.dangerous_key_combinations:
            warnings.append(f"Potentially dangerous key combination: {'+'.join(keys)}")
            severity = ValidationSeverity.WARNING
        
        # System key validation
        system_key_count = sum(1 for key in keys if key in self.system_keys)
        if system_key_count > 2:
            warnings.append(f"Multiple system keys in combination: {system_key_count}")
            severity = ValidationSeverity.WARNING
        
        # Duplicate key check
        if len(keys) != len(set(keys)):
            violations.append("Duplicate keys in combination")
            severity = ValidationSeverity.WARNING
        
        # Logical validation (e.g., conflicting modifiers)
        if 'CTRL' in keys and 'ALT' in keys and 'SHIFT' in keys and len(keys) > 4:
            warnings.append("Complex modifier combination may not work as expected")
        
        is_valid = len(violations) == 0 or severity in [ValidationSeverity.INFO, ValidationSeverity.WARNING]
        
        # Log validation result
        if violations:
            self.logger.warning(f"Key combination validation violations: {violations}")
        if warnings:
            self.logger.info(f"Key combination validation warnings: {warnings}")
        
        return ValidationResult(
            is_valid=is_valid,
            violations=violations,
            warnings=warnings,
            severity=severity
        )
    
    def validate_single_key(self, key: str) -> ValidationResult:
        """
        Validate single key input for security and safety.
        
        Args:
            key: Key name to validate
            
        Returns:
            ValidationResult with validation status and details
        """
        violations = []
        warnings = []
        severity = ValidationSeverity.INFO
        
        # Basic validation
        if not key:
            violations.append("Key cannot be empty")
            return ValidationResult(
                is_valid=False,
                violations=violations,
                severity=ValidationSeverity.ERROR
            )
        
        if not isinstance(key, str):
            violations.append(f"Key must be string, got {type(key)}")
            return ValidationResult(
                is_valid=False,
                violations=violations,
                severity=ValidationSeverity.ERROR
            )
        
        # Length validation
        if len(key) > self.max_single_key_length:
            violations.append(f"Key name too long: {len(key)} > {self.max_single_key_length}")
            severity = ValidationSeverity.ERROR
        
        # Format validation
        if not re.match(r'^[A-Z0-9_]+$', key):
            violations.append(f"Invalid key name format: '{key}'")
            severity = ValidationSeverity.WARNING
        
        # System key validation
        if key in self.system_keys:
            warnings.append(f"System key detected: '{key}'")
            severity = ValidationSeverity.WARNING
        
        # Special character validation
        dangerous_single_keys = {'DELETE', 'F4'}
        if key in dangerous_single_keys:
            warnings.append(f"Potentially dangerous key: '{key}'")
            severity = ValidationSeverity.WARNING
        
        is_valid = len(violations) == 0 or severity in [ValidationSeverity.INFO, ValidationSeverity.WARNING]
        
        # Log validation result
        if violations:
            self.logger.warning(f"Single key validation violations: {violations}")
        if warnings:
            self.logger.info(f"Single key validation warnings: {warnings}")
        
        return ValidationResult(
            is_valid=is_valid,
            violations=violations,
            warnings=warnings,
            severity=severity
        )
    
    def sanitize_text_input(self, text: str) -> str:
        """
        Sanitize text input by removing or replacing dangerous characters.
        
        Args:
            text: Text to sanitize
            
        Returns:
            Sanitized text safe for input simulation
        """
        if not text:
            return ""
        
        # Remove null bytes
        sanitized = text.replace('\x00', '')
        
        # Remove other control characters except essential whitespace
        sanitized = ''.join(
            char for char in sanitized 
            if char in self.allowed_text_chars
        )
        
        # Limit length
        if len(sanitized) > self.max_text_length:
            sanitized = sanitized[:self.max_text_length]
            self.logger.warning(f"Text truncated to {self.max_text_length} characters")
        
        # Remove excessive repetition
        # Replace sequences of more than 10 identical characters
        sanitized = re.sub(r'(.)\1{10,}', r'\1' * 10, sanitized)
        
        return sanitized
    
    def get_validation_stats(self) -> Dict:
        """Get validation statistics for monitoring"""
        return {
            "max_text_length": self.max_text_length,
            "max_key_combination_length": self.max_key_combination_length,
            "max_single_key_length": self.max_single_key_length,
            "dangerous_patterns_count": len(self.dangerous_patterns),
            "allowed_text_chars_count": len(self.allowed_text_chars),
            "dangerous_key_combinations_count": len(self.dangerous_key_combinations),
            "system_keys_count": len(self.system_keys)
        }