"""Core data models for the Verifier System.

All models use Pydantic v2 for validation and serialization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class VerificationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    SKIPPED = "skipped"


class HallucinationType(str, Enum):
    FACTUAL_INCONSISTENCY = "factual_inconsistency"
    CROSS_REFERENCE_FAILURE = "cross_reference_failure"
    LOW_CONFIDENCE_SIGNAL = "low_confidence_signal"
    PATTERN_MATCH = "pattern_match"


class ValidationFailureType(str, Enum):
    SCHEMA_VIOLATION = "schema_violation"
    TYPE_MISMATCH = "type_mismatch"
    FORMAT_ERROR = "format_error"
    MISSING_FIELD = "missing_field"
    CONSTRAINT_VIOLATION = "constraint_violation"


class VerificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class VerificationError(Exception):
    """Base exception for all verifier errors."""


class HallucinationDetectionError(VerificationError):
    """Raised when hallucination detection fails."""


class OutputValidationError(VerificationError):
    """Raised when output validation encounters an error."""


class LoopDetectionError(VerificationError):
    """Raised when loop detection encounters an error."""


class StorageError(VerificationError):
    """Raised when result storage fails."""


# ---------------------------------------------------------------------------
# Sub-result models
# ---------------------------------------------------------------------------


class HallucinationDetectionResult(BaseModel):
    """Result from hallucination detection."""

    detected: bool = False
    hallucination_types: list[HallucinationType] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    details: str = ""
    techniques_used: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class ValidationViolation(BaseModel):
    """A single validation violation."""

    field: str = ""
    failure_type: ValidationFailureType = ValidationFailureType.SCHEMA_VIOLATION
    message: str = ""
    expected: str = ""
    actual: str = ""


class OutputValidationResult(BaseModel):
    """Result from output validation."""

    valid: bool = True
    violations: list[ValidationViolation] = Field(default_factory=list)
    format_detected: str = "unknown"
    details: str = ""


class ToolOutputCheckResult(BaseModel):
    """Result from tool output checking."""

    safe: bool = True
    error_indicators: list[str] = Field(default_factory=list)
    schema_valid: bool = True
    semantically_consistent: bool = True
    details: str = ""


class LoopDetectionResult(BaseModel):
    """Result from loop detection."""

    loop_detected: bool = False
    repetition_count: int = 0
    loop_pattern: str = ""
    trace_length: int = 0
    details: str = ""


class ConfidenceScore(BaseModel):
    """Aggregated confidence score."""

    score: float = Field(default=1.0, ge=0.0, le=1.0)
    component_scores: dict[str, float] = Field(default_factory=dict)
    recommendation: str = "proceed"

    @field_validator("score")
    @classmethod
    def clamp_score(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class SelfCorrectionFeedback(BaseModel):
    """Actionable feedback for self-correction."""

    has_feedback: bool = False
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    severity: str = "low"  # low, medium, high, critical


# ---------------------------------------------------------------------------
# Main result model
# ---------------------------------------------------------------------------


class VerificationResult(BaseModel):
    """Complete verification result."""

    result_id: UUID = Field(default_factory=uuid4)
    status: VerificationStatus = VerificationStatus.PASSED
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    hallucination: HallucinationDetectionResult = Field(
        default_factory=HallucinationDetectionResult
    )
    validation: OutputValidationResult = Field(default_factory=OutputValidationResult)
    tool_check: ToolOutputCheckResult = Field(default_factory=ToolOutputCheckResult)
    loop_detection: LoopDetectionResult = Field(default_factory=LoopDetectionResult)
    confidence_score: ConfidenceScore = Field(default_factory=ConfidenceScore)
    feedback: SelfCorrectionFeedback = Field(default_factory=SelfCorrectionFeedback)
    latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @property
    def passed(self) -> bool:
        return self.status == VerificationStatus.PASSED

    @property
    def failed(self) -> bool:
        return self.status == VerificationStatus.FAILED


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class VerificationConfig(BaseModel):
    """Runtime configuration for the Verifier System."""

    # Confidence thresholds
    min_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    hallucination_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)

    # Strategy enablement
    enable_hallucination_detection: bool = True
    enable_output_validation: bool = True
    enable_tool_output_checking: bool = True
    enable_loop_detection: bool = True
    enable_confidence_scoring: bool = True

    # Latency limits (ms)
    max_latency_ms: float = 200.0

    # Loop detection
    loop_detection_threshold: int = Field(default=3, ge=1)

    # Accuracy targets
    max_false_positive_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    max_false_negative_rate: float = Field(default=0.02, ge=0.0, le=1.0)

    # Caching
    enable_caching: bool = True
    cache_ttl_seconds: float = 60.0

    # Testing mode
    testing_mode: bool = False

    @field_validator("min_confidence_threshold", "hallucination_confidence_threshold")
    @classmethod
    def clamp_threshold(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


# ---------------------------------------------------------------------------
# Storage / audit models
# ---------------------------------------------------------------------------


class VerificationLogEntry(BaseModel):
    """Stored verification result for audit and analytics."""

    entry_id: UUID = Field(default_factory=uuid4)
    result_id: UUID
    status: VerificationStatus
    confidence: float
    latency_ms: float
    hallucination_detected: bool
    validation_passed: bool
    loop_detected: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    context_type: str = ""  # "llm_response", "task_output", "storage"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AccuracyMetrics(BaseModel):
    """Accuracy metrics for the verifier."""

    total_verifications: int = 0
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0

    @property
    def false_positive_rate(self) -> float:
        denom = self.false_positives + self.true_negatives
        return self.false_positives / denom if denom > 0 else 0.0

    @property
    def false_negative_rate(self) -> float:
        denom = self.false_negatives + self.true_positives
        return self.false_negatives / denom if denom > 0 else 0.0

    @property
    def accuracy(self) -> float:
        total = self.total_verifications
        correct = self.true_positives + self.true_negatives
        return correct / total if total > 0 else 1.0
