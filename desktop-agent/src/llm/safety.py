"""
LLM Safety and Content Filtering System

Comprehensive safety engine that enforces content filtering, response sanitization,
and isolation boundary protection for all LLM interactions.

Security Principles:
- All LLM outputs are validated and sanitized
- Content filtering prevents harmful or inappropriate responses
- Isolation breach detection triggers immediate authority revocation
- Fail-safe defaults with comprehensive audit logging
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .intent import IntentValidator, StructuredIntent


class SafetyLevel(Enum):
    """Safety classification levels."""
    SAFE = "safe"
    CAUTION = "caution"
    UNSAFE = "unsafe"
    BLOCKED = "blocked"


class ViolationType(Enum):
    """Types of safety violations."""
    HARMFUL_CONTENT = "harmful_content"
    PRIVACY_VIOLATION = "privacy_violation"
    SECURITY_RISK = "security_risk"
    ISOLATION_BREACH = "isolation_breach"
    INAPPROPRIATE_LANGUAGE = "inappropriate_language"
    SYSTEM_MANIPULATION = "system_manipulation"
    DATA_EXFILTRATION = "data_exfiltration"


@dataclass
class SafetyAssessment:
    """Comprehensive safety assessment result."""
    
    safety_level: SafetyLevel
    violations: List[ViolationType]
    confidence: float
    explanation: str
    filtered_content: Optional[str] = None
    recommendations: List[str] = None
    
    def is_safe(self) -> bool:
        """Check if content is safe to process."""
        return self.safety_level in [SafetyLevel.SAFE, SafetyLevel.CAUTION]
        
    def requires_filtering(self) -> bool:
        """Check if content requires filtering."""
        return self.safety_level in [SafetyLevel.UNSAFE, SafetyLevel.BLOCKED]


@dataclass
class SafeResponse:
    """Safe, validated LLM response."""
    
    success: bool
    safe_intent: Optional[StructuredIntent] = None
    safety_assessment: Optional[SafetyAssessment] = None
    error_message: Optional[str] = None
    original_filtered: Optional[str] = None
    processing_time_ms: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata for enhanced features
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'success': self.success,
            'safe_intent': self.safe_intent.to_dict() if self.safe_intent else None,
            'safety_assessment': {
                'safety_level': self.safety_assessment.safety_level.value,
                'violations': [v.value for v in self.safety_assessment.violations],
                'confidence': self.safety_assessment.confidence,
                'explanation': self.safety_assessment.explanation
            } if self.safety_assessment else None,
            'error_message': self.error_message,
            'processing_time_ms': self.processing_time_ms,
            'metadata': self.metadata
        }


class ContentSafetyFilter:
    """
    Advanced content safety filter with pattern matching and heuristic analysis.
    
    Detects and filters harmful, inappropriate, or security-risky content
    before it can be processed into structured intents.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("llm.safety.content_filter")
        
        # Harmful content patterns
        self.harmful_patterns = [
            # Violence and threats
            r'\b(kill|murder|harm|hurt|attack|destroy|damage)\b.*\b(person|people|human|user)\b',
            r'\b(threat|threaten|intimidate|harass)\b',
            
            # Illegal activities
            r'\b(hack|crack|exploit|breach|bypass)\b.*\b(security|system|password)\b',
            r'\b(steal|theft|rob|fraud|scam)\b',
            
            # Privacy violations
            r'\b(personal|private|confidential|secret)\b.*\b(information|data|details)\b',
            r'\b(password|credential|token|key)\b.*\b(share|send|transmit)\b',
            
            # System manipulation
            r'\b(delete|remove|wipe|format)\b.*\b(file|data|system|disk)\b',
            r'\b(install|download|execute)\b.*\b(malware|virus|trojan)\b',
        ]
        
        # Isolation breach patterns
        self.isolation_patterns = [
            r'exec\s*\(',
            r'eval\s*\(',
            r'subprocess\.',
            r'os\.system',
            r'__import__',
            r'getattr\s*\(',
            r'setattr\s*\(',
            r'open\s*\(',
            r'file\s*\(',
            r'input\s*\(',
            r'raw_input\s*\(',
        ]
        
        # Inappropriate language patterns
        self.inappropriate_patterns = [
            # Profanity (basic examples - would be more comprehensive)
            r'\b(damn|hell|crap)\b',
            # Discriminatory language
            r'\b(racist|sexist|homophobic)\b',
        ]
        
        # System command patterns
        self.system_command_patterns = [
            r'\b(cmd|powershell|bash|sh|terminal)\b',
            r'\b(sudo|admin|administrator)\b',
            r'\b(registry|regedit|gpedit)\b',
            r'\b(service|daemon|process)\b.*\b(start|stop|kill|restart)\b',
        ]
        
    def assess_content_safety(self, content: str) -> SafetyAssessment:
        """
        Perform comprehensive safety assessment of content.
        
        Args:
            content: Content to assess
            
        Returns:
            SafetyAssessment: Detailed safety analysis
        """
        
        violations = []
        safety_level = SafetyLevel.SAFE
        confidence = 1.0
        explanations = []
        
        content_lower = content.lower()
        
        # Check for harmful content
        for pattern in self.harmful_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                violations.append(ViolationType.HARMFUL_CONTENT)
                safety_level = SafetyLevel.BLOCKED
                explanations.append("Detected potentially harmful content")
                break
                
        # Check for isolation breach attempts
        for pattern in self.isolation_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(ViolationType.ISOLATION_BREACH)
                safety_level = SafetyLevel.BLOCKED
                explanations.append("Detected isolation breach attempt")
                break
                
        # Check for system manipulation
        for pattern in self.system_command_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                violations.append(ViolationType.SYSTEM_MANIPULATION)
                if safety_level == SafetyLevel.SAFE:
                    safety_level = SafetyLevel.UNSAFE
                explanations.append("Detected system manipulation attempt")
                break
                
        # Check for inappropriate language
        for pattern in self.inappropriate_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                violations.append(ViolationType.INAPPROPRIATE_LANGUAGE)
                if safety_level == SafetyLevel.SAFE:
                    safety_level = SafetyLevel.CAUTION
                explanations.append("Detected inappropriate language")
                break
                
        # Check for privacy violations
        if self._check_privacy_violations(content_lower):
            violations.append(ViolationType.PRIVACY_VIOLATION)
            if safety_level == SafetyLevel.SAFE:
                safety_level = SafetyLevel.UNSAFE
            explanations.append("Detected potential privacy violation")
            
        # Check for data exfiltration attempts
        if self._check_data_exfiltration(content_lower):
            violations.append(ViolationType.DATA_EXFILTRATION)
            safety_level = SafetyLevel.BLOCKED
            explanations.append("Detected data exfiltration attempt")
            
        explanation = "; ".join(explanations) if explanations else "Content appears safe"
        
        return SafetyAssessment(
            safety_level=safety_level,
            violations=violations,
            confidence=confidence,
            explanation=explanation
        )
        
    def filter_content(self, content: str) -> Tuple[str, SafetyAssessment]:
        """
        Filter content and return safe version with assessment.
        
        Args:
            content: Original content
            
        Returns:
            Tuple[str, SafetyAssessment]: Filtered content and assessment
        """
        
        assessment = self.assess_content_safety(content)
        
        if assessment.safety_level == SafetyLevel.BLOCKED:
            return "[CONTENT BLOCKED FOR SAFETY]", assessment
        elif assessment.safety_level == SafetyLevel.UNSAFE:
            filtered = self._apply_content_filters(content)
            assessment.filtered_content = filtered
            return filtered, assessment
        else:
            return content, assessment
            
    def _check_privacy_violations(self, content: str) -> bool:
        """Check for potential privacy violations."""
        
        privacy_keywords = [
            'social security', 'ssn', 'credit card', 'password', 'pin',
            'personal information', 'private data', 'confidential'
        ]
        
        for keyword in privacy_keywords:
            if keyword in content:
                return True
                
        # Check for patterns that look like sensitive data
        patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN pattern
            r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Credit card pattern
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email pattern
        ]
        
        for pattern in patterns:
            if re.search(pattern, content):
                return True
                
        return False
        
    def _check_data_exfiltration(self, content: str) -> bool:
        """Check for data exfiltration attempts."""
        
        exfiltration_keywords = [
            'send data', 'transmit information', 'upload file',
            'copy to clipboard', 'save to file', 'export data'
        ]
        
        for keyword in exfiltration_keywords:
            if keyword in content:
                return True
                
        return False
        
    def _apply_content_filters(self, content: str) -> str:
        """Apply content filtering to make content safer."""
        
        filtered = content
        
        # Remove potentially harmful patterns
        for pattern in self.harmful_patterns:
            filtered = re.sub(pattern, '[FILTERED]', filtered, flags=re.IGNORECASE)
            
        # Remove system commands
        for pattern in self.system_command_patterns:
            filtered = re.sub(pattern, '[SYSTEM_COMMAND_FILTERED]', filtered, flags=re.IGNORECASE)
            
        return filtered


class ResponseSanitizer:
    """
    Sanitizes LLM responses to ensure they conform to security requirements
    and cannot be used for malicious purposes.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("llm.safety.response_sanitizer")
        self.intent_validator = IntentValidator()
        
    def sanitize_response(self, response: str) -> str:
        """
        Sanitize LLM response to remove potentially dangerous content.
        
        Args:
            response: Raw LLM response
            
        Returns:
            str: Sanitized response
        """
        
        sanitized = response
        
        # Remove null bytes and control characters
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', sanitized)
        
        # Limit response length to prevent DoS
        if len(sanitized) > 50000:
            sanitized = sanitized[:50000] + "...[TRUNCATED]"
            
        # Remove potentially dangerous JavaScript/HTML
        sanitized = re.sub(r'<script.*?</script>', '[SCRIPT_REMOVED]', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r'javascript:', '[JAVASCRIPT_REMOVED]', sanitized, flags=re.IGNORECASE)
        
        # Remove shell command indicators
        sanitized = re.sub(r'^\s*[$#>]\s*', '', sanitized, flags=re.MULTILINE)
        
        return sanitized
        
    def validate_intent_safety(self, intent: StructuredIntent) -> bool:
        """
        Validate that a structured intent is safe to process.
        
        Args:
            intent: Structured intent to validate
            
        Returns:
            bool: True if intent is safe
        """
        
        # Check for direct execution attempts
        if hasattr(intent, 'intent_type'):
            dangerous_types = ['DIRECT_EXECUTION', 'SYSTEM_COMMAND']
            if intent.intent_type.name in dangerous_types:
                return False
                
        # Validate parameters
        if hasattr(intent, 'parameters'):
            for key, value in intent.parameters.items():
                if isinstance(value, str):
                    if self._contains_dangerous_content(value):
                        return False
                        
        return True
        
    def _contains_dangerous_content(self, text: str) -> bool:
        """Check if text contains dangerous content."""
        
        dangerous_patterns = [
            r'exec\s*\(',
            r'eval\s*\(',
            r'subprocess\.',
            r'os\.system',
            r'__import__',
            r'rm\s+-rf',
            r'del\s+/[sq]',
            r'format\s+c:',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
                
        return False


class LLMSafetyEngine:
    """
    Comprehensive LLM safety engine that coordinates all safety measures
    and enforces the critical security boundary: LLMs are advisory only.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("llm.safety.engine")
        self.content_filter = ContentSafetyFilter()
        self.response_sanitizer = ResponseSanitizer()
        self.intent_validator = IntentValidator()
        
        # Safety statistics
        self.total_requests = 0
        self.blocked_requests = 0
        self.filtered_requests = 0
        
    def process_llm_response(
        self, 
        response: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> SafeResponse:
        """
        Process LLM response through comprehensive safety pipeline.
        
        Args:
            response: Raw LLM response
            context: Optional request context
            
        Returns:
            SafeResponse: Validated and safe response
        """
        
        start_time = datetime.utcnow()
        self.total_requests += 1
        
        try:
            # Step 1: Content safety assessment
            safety_assessment = self.content_filter.assess_content_safety(response)
            
            if safety_assessment.safety_level == SafetyLevel.BLOCKED:
                self.blocked_requests += 1
                self.logger.warning(f"Blocked unsafe LLM response: {safety_assessment.explanation}")
                
                return SafeResponse(
                    success=False,
                    safety_assessment=safety_assessment,
                    error_message="Response blocked for safety violations",
                    processing_time_ms=self._get_processing_time(start_time)
                )
                
            # Step 2: Content filtering if needed
            if safety_assessment.requires_filtering():
                filtered_response, safety_assessment = self.content_filter.filter_content(response)
                self.filtered_requests += 1
            else:
                filtered_response = response
                
            # Step 3: Response sanitization
            sanitized_response = self.response_sanitizer.sanitize_response(filtered_response)
            
            # Step 4: Intent validation
            try:
                intent = self.intent_validator.validate_raw_response(sanitized_response)
            except Exception as e:
                self.logger.error(f"Intent validation failed: {e}")
                return SafeResponse(
                    success=False,
                    safety_assessment=safety_assessment,
                    error_message=f"Intent validation failed: {str(e)}",
                    processing_time_ms=self._get_processing_time(start_time)
                )
                
            # Step 5: Final safety validation
            if not self.response_sanitizer.validate_intent_safety(intent):
                self.blocked_requests += 1
                return SafeResponse(
                    success=False,
                    safety_assessment=safety_assessment,
                    error_message="Intent failed final safety validation",
                    processing_time_ms=self._get_processing_time(start_time)
                )
                
            # Success - return safe intent
            return SafeResponse(
                success=True,
                safe_intent=intent,
                safety_assessment=safety_assessment,
                original_filtered=sanitized_response,
                processing_time_ms=self._get_processing_time(start_time)
            )
            
        except Exception as e:
            self.logger.error(f"Safety engine processing failed: {e}")
            return SafeResponse(
                success=False,
                error_message=f"Safety processing failed: {str(e)}",
                processing_time_ms=self._get_processing_time(start_time)
            )
            
    def get_safety_statistics(self) -> Dict[str, Any]:
        """Get comprehensive safety statistics."""
        
        return {
            'total_requests': self.total_requests,
            'blocked_requests': self.blocked_requests,
            'filtered_requests': self.filtered_requests,
            'block_rate': self.blocked_requests / max(self.total_requests, 1),
            'filter_rate': self.filtered_requests / max(self.total_requests, 1),
            'safe_rate': (self.total_requests - self.blocked_requests) / max(self.total_requests, 1)
        }
        
    def reset_statistics(self):
        """Reset safety statistics."""
        self.total_requests = 0
        self.blocked_requests = 0
        self.filtered_requests = 0
        
    def _get_processing_time(self, start_time: datetime) -> int:
        """
        Calculate processing time in milliseconds with microsecond precision.
        
        For high-performance systems, processing may complete in microseconds.
        This method ensures accurate timing measurement for production monitoring.
        """
        delta = datetime.utcnow() - start_time
        total_microseconds = delta.total_seconds() * 1_000_000
        # Convert to milliseconds, ensuring minimum of 1ms for completed operations
        milliseconds = max(1, int(total_microseconds / 1000))
        return milliseconds