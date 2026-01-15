"""
Multilingual Processing Types

Shared type definitions for multilingual processing components to avoid
circular import dependencies.
"""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SecurePipelineState(Enum):
    """Secure pipeline execution states."""

    IDLE = "idle"
    AUTHORITY_CHECK = "authority_check"
    MULTILINGUAL_PROCESSING = "multilingual_processing"
    AUTHORITY_VALIDATION = "authority_validation"
    EXECUTION_READY = "execution_ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SECURITY_VIOLATION = "security_violation"


@dataclass
class VoiceProcessingResult:
    """Result of voice processing operation."""

    success: bool
    language: Optional[str] = None
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    transcription: Optional[str] = None
    error: Optional[str] = None
    fallback_used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "success": self.success,
            "language": self.language,
            "confidence": self.confidence,
            "processing_time_ms": self.processing_time_ms,
            "transcription": self.transcription,
            "error": self.error,
            "fallback_used": self.fallback_used,
        }


@dataclass
class AuthorityIntegrationResult:
    """Result of authority integration validation."""

    authority_state: str
    authority_granted: bool
    biometric_verified: bool
    security_level: str
    additional_verification_required: bool = False
    authority_errors: List[str] = field(default_factory=list)
    authority_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "authority_state": self.authority_state,
            "authority_granted": self.authority_granted,
            "biometric_verified": self.biometric_verified,
            "security_level": self.security_level,
            "additional_verification_required": self.additional_verification_required,
            "authority_errors": self.authority_errors,
            "authority_warnings": self.authority_warnings,
        }


@dataclass
class SecurePipelineResult:
    """Comprehensive result of secure multilingual pipeline processing."""

    # Request identification
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None

    # Pipeline execution
    success: bool = False
    state: SecurePipelineState = SecurePipelineState.IDLE

    # Processing results
    multilingual_result: Optional[Any] = None  # Will be PipelineResult when imported
    authority_result: Optional[AuthorityIntegrationResult] = None
    execution_result: Optional[Dict[str, Any]] = None

    # Performance metrics
    total_processing_time_ms: int = 0
    authority_check_time_ms: int = 0
    multilingual_processing_time_ms: int = 0
    execution_time_ms: int = 0

    # Error handling
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    security_violations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "success": self.success,
            "state": self.state.value,
            "multilingual_result": (
                self.multilingual_result.to_dict()
                if self.multilingual_result and hasattr(self.multilingual_result, "to_dict")
                else None
            ),
            "authority_result": self.authority_result.to_dict() if self.authority_result else None,
            "execution_result": self.execution_result,
            "total_processing_time_ms": self.total_processing_time_ms,
            "authority_check_time_ms": self.authority_check_time_ms,
            "multilingual_processing_time_ms": self.multilingual_processing_time_ms,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
            "warnings": self.warnings,
            "security_violations": self.security_violations,
        }


# Export all types
__all__ = ["SecurePipelineState", "VoiceProcessingResult", "AuthorityIntegrationResult", "SecurePipelineResult"]

# Re-export commonly used types from other modules for convenience
# This avoids circular imports while providing a central import location
try:
    pass

    __all__.extend(
        [
            "LanguageDetectionResult",
            "LanguageSegment",
            "MixedLanguageResult",
            "CanonicalIntent",
            "ProcessingMode",
            "NormalizationResult",
            "ModeClassificationResult",
            "PipelineResult",
            "PipelineStage",
            "PipelineState",
        ]
    )
except ImportError:
    # If imports fail (e.g., during initial module loading), that's okay
    # Tests can import directly from the source modules
    pass
