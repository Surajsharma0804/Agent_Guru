"""
LLM System Exceptions

Production-grade exception hierarchy for LLM system with comprehensive
error information, recovery guidance, and audit integration.

All exceptions include:
- Detailed error context
- Recovery suggestions
- Audit logging metadata
- Security classification
"""

from typing import Dict, Any, Optional, List
from datetime import datetime


class LLMException(Exception):
    """
    Base exception for all LLM system errors.
    
    Provides comprehensive error context and audit metadata.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        severity: str = "error",
        recoverable: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.severity = severity
        self.recoverable = recoverable
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging."""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'severity': self.severity,
            'recoverable': self.recoverable,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }
    
    def get_recovery_guidance(self) -> str:
        """Get user-facing recovery guidance."""
        return "Please check system logs and configuration."


class ModelRouterError(LLMException):
    """Model router initialization or operation error."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code="MODEL_ROUTER_ERROR",
            severity="error",
            recoverable=True,
            **kwargs
        )
    
    def get_recovery_guidance(self) -> str:
        return "Check model router configuration and provider availability."


class ProviderError(LLMException):
    """Provider-level error."""
    
    def __init__(
        self,
        message: str,
        provider_name: Optional[str] = None,
        provider_error: Optional[Exception] = None,
        **kwargs
    ):
        metadata = kwargs.pop('metadata', {})
        metadata['provider_name'] = provider_name
        if provider_error:
            metadata['provider_error'] = str(provider_error)
        
        super().__init__(
            message,
            error_code="PROVIDER_ERROR",
            severity="error",
            recoverable=True,
            metadata=metadata,
            **kwargs
        )
        self.provider_name = provider_name
        self.provider_error = provider_error
    
    def get_recovery_guidance(self) -> str:
        if self.provider_name == "ollama":
            return "Ensure Ollama is running: ollama serve"
        elif self.provider_name in ["openai", "gemini"]:
            return f"Check {self.provider_name} API key and internet connection."
        return "Check provider configuration and availability."


class ProviderRegistrationError(ProviderError):
    """Provider registration failed."""
    
    def __init__(
        self,
        message: str,
        provider_name: str,
        registration_phase: str,
        **kwargs
    ):
        metadata = kwargs.pop('metadata', {})
        metadata['registration_phase'] = registration_phase
        
        super().__init__(
            message,
            provider_name=provider_name,
            error_code="PROVIDER_REGISTRATION_ERROR",
            metadata=metadata,
            **kwargs
        )
        self.registration_phase = registration_phase
    
    def get_recovery_guidance(self) -> str:
        if self.registration_phase == "initialization":
            return f"Provider {self.provider_name} failed to initialize. Check configuration and dependencies."
        elif self.registration_phase == "duplicate_check":
            return f"Provider {self.provider_name} is already registered."
        return super().get_recovery_guidance()


class AuthenticationError(ProviderError):
    """Authentication failed for API provider."""
    
    def __init__(
        self,
        message: str,
        provider_name: str,
        auth_method: str = "api_key",
        **kwargs
    ):
        metadata = kwargs.pop('metadata', {})
        metadata['auth_method'] = auth_method
        
        super().__init__(
            message,
            provider_name=provider_name,
            error_code="AUTHENTICATION_ERROR",
            severity="error",
            recoverable=True,
            metadata=metadata,
            **kwargs
        )
        self.auth_method = auth_method
    
    def get_recovery_guidance(self) -> str:
        if self.auth_method == "api_key":
            return f"Check {self.provider_name} API key. Verify it is set correctly in environment variables."
        return "Check authentication credentials."


class RateLimitExceededError(ProviderError):
    """Rate limit exceeded for provider."""
    
    def __init__(
        self,
        message: str,
        provider_name: str,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        metadata = kwargs.pop('metadata', {})
        metadata['retry_after'] = retry_after
        
        super().__init__(
            message,
            provider_name=provider_name,
            error_code="RATE_LIMIT_EXCEEDED",
            severity="warning",
            recoverable=True,
            metadata=metadata,
            **kwargs
        )
        self.retry_after = retry_after
    
    def get_recovery_guidance(self) -> str:
        if self.retry_after:
            return f"Rate limit exceeded. Retry after {self.retry_after} seconds or switch to local provider."
        return "Rate limit exceeded. Wait before retrying or switch to local provider."


class NetworkError(ProviderError):
    """Network connectivity error."""
    
    def __init__(
        self,
        message: str,
        provider_name: str,
        endpoint: Optional[str] = None,
        **kwargs
    ):
        metadata = kwargs.pop('metadata', {})
        metadata['endpoint'] = endpoint
        
        super().__init__(
            message,
            provider_name=provider_name,
            error_code="NETWORK_ERROR",
            severity="error",
            recoverable=True,
            metadata=metadata,
            **kwargs
        )
        self.endpoint = endpoint
    
    def get_recovery_guidance(self) -> str:
        return "Check internet connection or switch to local provider."


class ModelNotFoundError(ProviderError):
    """Requested model not found."""
    
    def __init__(
        self,
        message: str,
        provider_name: str,
        model_name: str,
        available_models: Optional[List[str]] = None,
        **kwargs
    ):
        metadata = kwargs.pop('metadata', {})
        metadata['model_name'] = model_name
        metadata['available_models'] = available_models
        
        super().__init__(
            message,
            provider_name=provider_name,
            error_code="MODEL_NOT_FOUND",
            severity="error",
            recoverable=True,
            metadata=metadata,
            **kwargs
        )
        self.model_name = model_name
        self.available_models = available_models
    
    def get_recovery_guidance(self) -> str:
        if self.provider_name == "ollama":
            return f"Model {self.model_name} not found. Install with: ollama pull {self.model_name}"
        return f"Model {self.model_name} not available. Check provider configuration."


class CapabilityDetectionError(ProviderError):
    """Failed to detect provider capabilities."""
    
    def __init__(
        self,
        message: str,
        provider_name: str,
        capability_type: str,
        **kwargs
    ):
        metadata = kwargs.pop('metadata', {})
        metadata['capability_type'] = capability_type
        
        super().__init__(
            message,
            provider_name=provider_name,
            error_code="CAPABILITY_DETECTION_ERROR",
            severity="warning",
            recoverable=True,
            metadata=metadata,
            **kwargs
        )
        self.capability_type = capability_type


class ConfigurationError(LLMException):
    """Configuration error."""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        **kwargs
    ):
        metadata = kwargs.pop('metadata', {})
        metadata['config_key'] = config_key
        if config_value is not None:
            metadata['config_value'] = str(config_value)
        
        super().__init__(
            message,
            error_code="CONFIGURATION_ERROR",
            severity="error",
            recoverable=True,
            metadata=metadata,
            **kwargs
        )
        self.config_key = config_key
        self.config_value = config_value
    
    def get_recovery_guidance(self) -> str:
        if self.config_key:
            return f"Check configuration key: {self.config_key}"
        return "Check system configuration file."


class TaskRoutingError(LLMException):
    """Task routing error."""
    
    def __init__(
        self,
        message: str,
        task_type: Optional[str] = None,
        provider: Optional[str] = None,
        attempts: Optional[int] = None,
        **kwargs
    ):
        metadata = kwargs.pop('metadata', {})
        metadata['task_type'] = task_type
        metadata['provider'] = provider
        metadata['attempts'] = attempts
        
        super().__init__(
            message,
            error_code="TASK_ROUTING_ERROR",
            severity="error",
            recoverable=True,
            metadata=metadata,
            **kwargs
        )
        self.task_type = task_type
        self.provider = provider
        self.attempts = attempts
    
    def get_recovery_guidance(self) -> str:
        return f"Task {self.task_type} routing failed. Check provider availability and configuration."


class IntentValidationError(LLMException):
    """Intent validation failed."""
    
    def __init__(
        self,
        message: str,
        validation_errors: Optional[List[str]] = None,
        raw_response: Optional[str] = None,
        **kwargs
    ):
        metadata = kwargs.pop('metadata', {})
        metadata['validation_errors'] = validation_errors
        # Do not log raw_response - may contain sensitive data
        
        super().__init__(
            message,
            error_code="INTENT_VALIDATION_ERROR",
            severity="error",
            recoverable=False,
            metadata=metadata,
            **kwargs
        )
        self.validation_errors = validation_errors or []
        self.raw_response = raw_response
    
    def get_recovery_guidance(self) -> str:
        return "LLM produced invalid intent. This is a security violation. System remains locked."


class IsolationBreachError(LLMException):
    """
    CRITICAL: LLM attempted to breach isolation boundary.
    
    This is a security violation that must be logged and reported.
    System must fail closed immediately.
    """
    
    def __init__(
        self,
        message: str,
        breach_type: str,
        attempted_action: str,
        **kwargs
    ):
        metadata = kwargs.pop('metadata', {})
        metadata['breach_type'] = breach_type
        metadata['attempted_action'] = attempted_action
        
        super().__init__(
            message,
            error_code="ISOLATION_BREACH",
            severity="critical",
            recoverable=False,
            metadata=metadata,
            **kwargs
        )
        self.breach_type = breach_type
        self.attempted_action = attempted_action
    
    def get_recovery_guidance(self) -> str:
        return "SECURITY VIOLATION: LLM attempted direct execution. System locked. Review audit logs immediately."


class LLMAdapterError(LLMException):
    """LLM adapter error."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code="LLM_ADAPTER_ERROR",
            severity="error",
            recoverable=True,
            **kwargs
        )


class SafetyViolationError(LLMException):
    """Safety violation detected in LLM output."""
    
    def __init__(
        self,
        message: str,
        violation_type: Optional[str] = None,
        **kwargs
    ):
        metadata = kwargs.pop('metadata', {})
        metadata['violation_type'] = violation_type
        
        super().__init__(
            message,
            error_code="SAFETY_VIOLATION",
            severity="critical",
            recoverable=False,
            metadata=metadata,
            **kwargs
        )
        self.violation_type = violation_type
    
    def get_recovery_guidance(self) -> str:
        return "SAFETY VIOLATION: LLM output rejected. System locked. Review audit logs."
