"""
LLM Adapter Exception Classes

Comprehensive exception hierarchy for LLM adapter operations with
security-focused error handling and audit trail integration.
"""

from typing import Optional, Dict, Any
from datetime import datetime


class LLMAdapterError(Exception):
    """Base exception for all LLM adapter operations."""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = "LLM_ADAPTER_ERROR",
        context: Optional[Dict[str, Any]] = None,
        security_impact: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.security_impact = security_impact
        self.timestamp = datetime.utcnow()
        
    def to_audit_dict(self) -> Dict[str, Any]:
        """Convert exception to audit log format."""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'context': self.context,
            'security_impact': self.security_impact,
            'timestamp': self.timestamp.isoformat()
        }


class ProviderError(LLMAdapterError):
    """Exception for LLM provider-specific errors."""
    
    def __init__(
        self, 
        message: str, 
        provider_name: str,
        provider_error: Optional[Exception] = None,
        retry_after: Optional[int] = None
    ):
        super().__init__(
            message, 
            error_code="PROVIDER_ERROR",
            context={
                'provider_name': provider_name,
                'provider_error': str(provider_error) if provider_error else None,
                'retry_after': retry_after
            }
        )
        self.provider_name = provider_name
        self.provider_error = provider_error
        self.retry_after = retry_after


class SafetyViolationError(LLMAdapterError):
    """Exception for LLM safety and content filtering violations."""
    
    def __init__(
        self, 
        message: str, 
        violation_type: str,
        filtered_content: Optional[str] = None,
        severity: str = "medium"
    ):
        super().__init__(
            message, 
            error_code="SAFETY_VIOLATION",
            context={
                'violation_type': violation_type,
                'severity': severity,
                'content_filtered': filtered_content is not None
            },
            security_impact=True
        )
        self.violation_type = violation_type
        self.filtered_content = filtered_content
        self.severity = severity


class IntentValidationError(LLMAdapterError):
    """Exception for structured intent validation failures."""
    
    def __init__(
        self, 
        message: str, 
        validation_errors: list,
        raw_response: Optional[str] = None
    ):
        super().__init__(
            message, 
            error_code="INTENT_VALIDATION_ERROR",
            context={
                'validation_errors': validation_errors,
                'has_raw_response': raw_response is not None
            }
        )
        self.validation_errors = validation_errors
        self.raw_response = raw_response


class IsolationBreachError(LLMAdapterError):
    """Critical exception for LLM isolation boundary violations."""
    
    def __init__(
        self, 
        message: str, 
        breach_type: str,
        attempted_action: Optional[str] = None
    ):
        super().__init__(
            message, 
            error_code="ISOLATION_BREACH",
            context={
                'breach_type': breach_type,
                'attempted_action': attempted_action
            },
            security_impact=True
        )
        self.breach_type = breach_type
        self.attempted_action = attempted_action


class ProviderRegistrationError(LLMAdapterError):
    """Exception for provider registration and discovery failures."""
    
    def __init__(
        self, 
        message: str, 
        provider_name: str,
        registration_phase: str
    ):
        super().__init__(
            message, 
            error_code="PROVIDER_REGISTRATION_ERROR",
            context={
                'provider_name': provider_name,
                'registration_phase': registration_phase
            }
        )
        self.provider_name = provider_name
        self.registration_phase = registration_phase


class CapabilityDetectionError(LLMAdapterError):
    """Exception for provider capability detection failures."""
    
    def __init__(
        self, 
        message: str, 
        provider_name: str,
        capability_type: str
    ):
        super().__init__(
            message, 
            error_code="CAPABILITY_DETECTION_ERROR",
            context={
                'provider_name': provider_name,
                'capability_type': capability_type
            }
        )
        self.provider_name = provider_name
        self.capability_type = capability_type


class RateLimitExceededError(ProviderError):
    """Exception for provider rate limit violations."""
    
    def __init__(
        self, 
        message: str, 
        provider_name: str,
        retry_after: int,
        limit_type: str = "requests"
    ):
        super().__init__(
            message, 
            provider_name=provider_name,
            retry_after=retry_after
        )
        self.error_code = "RATE_LIMIT_EXCEEDED"
        self.context.update({
            'limit_type': limit_type,
            'retry_after': retry_after
        })
        self.limit_type = limit_type


class AuthenticationError(ProviderError):
    """Exception for provider authentication failures."""
    
    def __init__(
        self, 
        message: str, 
        provider_name: str,
        auth_method: Optional[str] = None
    ):
        super().__init__(
            message, 
            provider_name=provider_name
        )
        self.error_code = "AUTHENTICATION_ERROR"
        self.context.update({
            'auth_method': auth_method
        })
        self.auth_method = auth_method


class NetworkError(ProviderError):
    """Exception for network-related provider failures."""
    
    def __init__(
        self, 
        message: str, 
        provider_name: str,
        network_error: Optional[Exception] = None,
        retry_recommended: bool = True
    ):
        super().__init__(
            message, 
            provider_name=provider_name,
            provider_error=network_error
        )
        self.error_code = "NETWORK_ERROR"
        self.context.update({
            'retry_recommended': retry_recommended
        })
        self.retry_recommended = retry_recommended