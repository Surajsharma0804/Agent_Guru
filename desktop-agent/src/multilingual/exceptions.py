"""
Multilingual Processing Exceptions

Comprehensive exception hierarchy for multilingual processing with detailed
error information, security context, and recovery guidance.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


class MultilingualError(Exception):
    """Base exception for all multilingual processing errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        recovery_suggestions: Optional[List[str]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "MULTILINGUAL_ERROR"
        self.context = context or {}
        self.recovery_suggestions = recovery_suggestions or []
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context,
            "recovery_suggestions": self.recovery_suggestions,
            "timestamp": self.timestamp.isoformat(),
        }


class LanguageDetectionError(MultilingualError):
    """Raised when language detection fails or produces invalid results."""

    def __init__(
        self,
        message: str,
        detected_language: Optional[str] = None,
        confidence_score: Optional[float] = None,
        audio_length_ms: Optional[int] = None,
        detection_method: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, error_code="LANGUAGE_DETECTION_FAILED", **kwargs)
        self.detected_language = detected_language
        self.confidence_score = confidence_score
        self.audio_length_ms = audio_length_ms
        self.detection_method = detection_method

        # Add detection-specific context
        self.context.update(
            {
                "detected_language": detected_language,
                "confidence_score": confidence_score,
                "audio_length_ms": audio_length_ms,
                "detection_method": detection_method,
            }
        )


class IntentNormalizationError(MultilingualError):
    """Raised when intent normalization fails or produces invalid canonical intents."""

    def __init__(
        self,
        message: str,
        original_text: Optional[str] = None,
        detected_language: Optional[str] = None,
        attempted_intent: Optional[str] = None,
        normalization_stage: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, error_code="INTENT_NORMALIZATION_FAILED", **kwargs)
        self.original_text = original_text
        self.detected_language = detected_language
        self.attempted_intent = attempted_intent
        self.normalization_stage = normalization_stage

        # Add normalization-specific context
        self.context.update(
            {
                "original_text_length": len(original_text) if original_text else 0,
                "detected_language": detected_language,
                "attempted_intent": attempted_intent,
                "normalization_stage": normalization_stage,
            }
        )


class UnsupportedLanguageError(MultilingualError):
    """Raised when attempting to process an unsupported language."""

    def __init__(
        self,
        message: str,
        requested_language: Optional[str] = None,
        supported_languages: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(message, error_code="UNSUPPORTED_LANGUAGE", **kwargs)
        self.requested_language = requested_language
        self.supported_languages = supported_languages or []

        # Add language-specific context
        self.context.update(
            {
                "requested_language": requested_language,
                "supported_languages": self.supported_languages,
                "supported_count": len(self.supported_languages),
            }
        )

        # Add recovery suggestions
        if self.supported_languages:
            self.recovery_suggestions.extend(
                [
                    f"Use one of the supported languages: {', '.join(self.supported_languages[:5])}",
                    "Check language configuration settings",
                    "Verify language models are properly installed",
                ]
            )


class SecurityBoundaryError(MultilingualError):
    """Raised when multilingual processing violates security boundaries."""

    def __init__(
        self,
        message: str,
        security_violation_type: Optional[str] = None,
        attempted_action: Optional[str] = None,
        security_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(message, error_code="SECURITY_BOUNDARY_VIOLATION", **kwargs)
        self.security_violation_type = security_violation_type
        self.attempted_action = attempted_action
        self.security_context = security_context or {}

        # Add security-specific context
        self.context.update(
            {
                "security_violation_type": security_violation_type,
                "attempted_action": attempted_action,
                "security_context": self.security_context,
            }
        )

        # Security violations require immediate attention
        self.recovery_suggestions.extend(
            [
                "Review security logs for potential intrusion attempts",
                "Verify system integrity and configuration",
                "Contact security administrator if violations persist",
            ]
        )


class ConfigurationError(MultilingualError):
    """Raised when multilingual configuration is invalid or missing."""

    def __init__(
        self,
        message: str,
        config_section: Optional[str] = None,
        config_key: Optional[str] = None,
        expected_type: Optional[str] = None,
        actual_value: Optional[Any] = None,
        **kwargs,
    ):
        # Extract only the kwargs that MultilingualError accepts
        context = kwargs.pop("context", {})
        recovery_suggestions = kwargs.pop("recovery_suggestions", [])

        super().__init__(
            message, error_code="CONFIGURATION_ERROR", context=context, recovery_suggestions=recovery_suggestions
        )

        self.config_section = config_section
        self.config_key = config_key
        self.expected_type = expected_type
        self.actual_value = actual_value

        # Add configuration-specific context
        self.context.update(
            {
                "config_section": config_section,
                "config_key": config_key,
                "expected_type": expected_type,
                "actual_value_type": type(actual_value).__name__ if actual_value is not None else None,
            }
        )

        # Add any extra kwargs to context
        if kwargs:
            self.context.update(kwargs)

        # Add configuration recovery suggestions
        self.recovery_suggestions.extend(
            [
                "Check multilingual configuration file syntax",
                "Verify all required configuration keys are present",
                "Restore configuration from backup if available",
                "Reset to default configuration if corruption detected",
            ]
        )


class ModelLoadingError(MultilingualError):
    """Raised when language models fail to load or initialize."""

    def __init__(
        self,
        message: str,
        model_type: Optional[str] = None,
        model_path: Optional[str] = None,
        language: Optional[str] = None,
        loading_stage: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, error_code="MODEL_LOADING_FAILED", **kwargs)
        self.model_type = model_type
        self.model_path = model_path
        self.language = language
        self.loading_stage = loading_stage

        # Add model-specific context
        self.context.update(
            {"model_type": model_type, "model_path": model_path, "language": language, "loading_stage": loading_stage}
        )

        # Add model recovery suggestions
        self.recovery_suggestions.extend(
            [
                "Verify model files exist and are not corrupted",
                "Check available disk space and memory",
                "Ensure model files have correct permissions",
                "Try downloading fresh model files if corruption suspected",
            ]
        )


class PipelineError(MultilingualError):
    """Raised when multilingual processing pipeline encounters errors."""

    def __init__(
        self,
        message: str,
        pipeline_stage: Optional[str] = None,
        input_data_type: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(message, error_code="PIPELINE_ERROR", **kwargs)
        self.pipeline_stage = pipeline_stage
        self.input_data_type = input_data_type
        self.processing_time_ms = processing_time_ms

        # Add pipeline-specific context
        self.context.update(
            {
                "pipeline_stage": pipeline_stage,
                "input_data_type": input_data_type,
                "processing_time_ms": processing_time_ms,
            }
        )


class DictationError(MultilingualError):
    """Raised when dictation mode encounters errors or content preservation violations."""

    def __init__(
        self,
        message: str,
        language: Optional[str] = None,
        text_length: Optional[int] = None,
        preservation_violated: bool = False,
        script_rendering_failed: bool = False,
        input_method_error: bool = False,
        **kwargs,
    ):
        super().__init__(message, error_code="DICTATION_ERROR", **kwargs)
        self.language = language
        self.text_length = text_length
        self.preservation_violated = preservation_violated
        self.script_rendering_failed = script_rendering_failed
        self.input_method_error = input_method_error

        # Add dictation-specific context
        self.context.update(
            {
                "language": language,
                "text_length": text_length,
                "preservation_violated": preservation_violated,
                "script_rendering_failed": script_rendering_failed,
                "input_method_error": input_method_error,
            }
        )

        # Add dictation recovery suggestions
        if preservation_violated:
            self.recovery_suggestions.extend(
                [
                    "CRITICAL: Content preservation violated - investigate immediately",
                    "Check dictation mode configuration for content alteration",
                    "Verify no normalization or filtering is enabled",
                ]
            )

        if script_rendering_failed:
            self.recovery_suggestions.extend(
                [
                    "Check script rendering configuration for the language",
                    "Verify Unicode support is properly configured",
                    "Test with simpler text to isolate rendering issues",
                ]
            )

        if input_method_error:
            self.recovery_suggestions.extend(
                [
                    "Check input method installation for the language",
                    "Verify keyboard layout configuration",
                    "Test input method activation manually",
                ]
            )


class PerformanceError(MultilingualError):
    """Raised when multilingual processing exceeds performance thresholds."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        actual_time_ms: Optional[int] = None,
        threshold_ms: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(message, error_code="PERFORMANCE_THRESHOLD_EXCEEDED", **kwargs)
        self.operation = operation
        self.actual_time_ms = actual_time_ms
        self.threshold_ms = threshold_ms

        # Add performance-specific context
        self.context.update(
            {
                "operation": operation,
                "actual_time_ms": actual_time_ms,
                "threshold_ms": threshold_ms,
                "performance_ratio": actual_time_ms / threshold_ms if threshold_ms else None,
            }
        )

        # Add performance recovery suggestions
        self.recovery_suggestions.extend(
            [
                "Check system resource usage (CPU, memory, disk)",
                "Verify hardware acceleration is functioning",
                "Consider adjusting performance thresholds if consistently exceeded",
                "Monitor for background processes affecting performance",
            ]
        )


@dataclass
class ErrorContext:
    """Structured error context for comprehensive error reporting."""

    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    language: Optional[str] = None
    operation: Optional[str] = None
    input_length: Optional[int] = None
    processing_stage: Optional[str] = None
    system_state: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert error context to dictionary."""
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "language": self.language,
            "operation": self.operation,
            "input_length": self.input_length,
            "processing_stage": self.processing_stage,
            "system_state": self.system_state,
        }


def create_error_with_context(
    exception_class: type, message: str, context: ErrorContext, **kwargs
) -> MultilingualError:
    """
    Create a multilingual exception with comprehensive context.

    Args:
        exception_class: Exception class to instantiate
        message: Error message
        context: Error context information
        **kwargs: Additional exception-specific parameters

    Returns:
        MultilingualError: Configured exception with context
    """

    # Merge context into kwargs
    kwargs["context"] = kwargs.get("context", {})
    kwargs["context"].update(context.to_dict())

    return exception_class(message, **kwargs)


def handle_multilingual_exception(
    exception: Exception, operation: str, context: Optional[ErrorContext] = None
) -> MultilingualError:
    """
    Convert any exception to a multilingual exception with context.

    Args:
        exception: Original exception
        operation: Operation that failed
        context: Optional error context

    Returns:
        MultilingualError: Wrapped exception with multilingual context
    """

    if isinstance(exception, MultilingualError):
        return exception

    # Create context if not provided
    if context is None:
        context = ErrorContext(operation=operation)
    else:
        context.operation = operation

    # Wrap in appropriate multilingual exception
    if "language" in str(exception).lower():
        return create_error_with_context(
            LanguageDetectionError, f"Language processing failed during {operation}: {str(exception)}", context
        )
    elif "intent" in str(exception).lower():
        return create_error_with_context(
            IntentNormalizationError, f"Intent processing failed during {operation}: {str(exception)}", context
        )
    elif "config" in str(exception).lower():
        return create_error_with_context(
            ConfigurationError, f"Configuration error during {operation}: {str(exception)}", context
        )
    else:
        return create_error_with_context(
            MultilingualError, f"Multilingual processing failed during {operation}: {str(exception)}", context
        )


class GuruIntegrationError(MultilingualError):
    """Raised when GURU integration encounters errors."""

    def __init__(self, message: str, component: Optional[str] = None, integration_mode: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.component = component
        self.integration_mode = integration_mode


class AuthorityIntegrationError(MultilingualError):
    """Raised when authority integration encounters errors."""

    def __init__(
        self,
        message: str,
        authority_state: Optional[str] = None,
        verification_type: Optional[str] = None,
        security_level: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, error_code="AUTHORITY_INTEGRATION_FAILED", **kwargs)
        self.authority_state = authority_state
        self.verification_type = verification_type
        self.security_level = security_level

        # Add authority-specific context
        self.context.update(
            {
                "authority_state": authority_state,
                "verification_type": verification_type,
                "security_level": security_level,
            }
        )

        # Add authority recovery suggestions
        self.recovery_suggestions.extend(
            [
                "Verify authority state machine is properly initialized",
                "Check biometric verification configuration",
                "Ensure security boundaries are properly configured",
                "Review authority integration logs for detailed error information",
            ]
        )

    """Raised when performance requirements are not met."""

    def __init__(
        self,
        message: str,
        performance_metric: Optional[str] = None,
        threshold: Optional[float] = None,
        actual: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.performance_metric = performance_metric
        self.threshold = threshold
        self.actual = actual


class MigrationError(MultilingualError):
    """Raised when migration operations fail."""

    def __init__(
        self,
        message: str,
        migration_phase: Optional[str] = None,
        backup_available: bool = False,
        rollback_possible: bool = False,
        **kwargs,
    ):
        super().__init__(message, error_code="MIGRATION_FAILED", **kwargs)
        self.migration_phase = migration_phase
        self.backup_available = backup_available
        self.rollback_possible = rollback_possible

        # Add migration-specific context
        self.context.update(
            {
                "migration_phase": migration_phase,
                "backup_available": backup_available,
                "rollback_possible": rollback_possible,
            }
        )

        # Add migration recovery suggestions
        if rollback_possible:
            self.recovery_suggestions.extend(
                [
                    "Consider rolling back to previous state",
                    "Review migration logs for detailed error information",
                    "Verify system requirements are met before retrying",
                ]
            )
        else:
            self.recovery_suggestions.extend(
                [
                    "Contact support for manual recovery assistance",
                    "Do not attempt further migration without backup",
                    "Preserve current system state for analysis",
                ]
            )


class ValidationError(MultilingualError):
    """Raised when validation operations fail."""

    def __init__(
        self,
        message: str,
        validation_type: Optional[str] = None,
        validation_failures: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(message, error_code="VALIDATION_FAILED", **kwargs)
        self.validation_type = validation_type
        self.validation_failures = validation_failures or []

        # Add validation-specific context
        self.context.update(
            {
                "validation_type": validation_type,
                "validation_failures": self.validation_failures,
                "failure_count": len(self.validation_failures),
            }
        )

        # Add validation recovery suggestions
        self.recovery_suggestions.extend(
            [
                "Review validation failures for specific issues",
                "Verify all required components are properly configured",
                "Check system logs for additional error details",
            ]
        )


# Alias for backward compatibility
SecurityViolationError = SecurityBoundaryError
