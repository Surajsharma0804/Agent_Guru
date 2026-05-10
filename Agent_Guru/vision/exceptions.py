"""Custom exception hierarchy for the GuruVision facial recognition system.

All exceptions derive from GuruVisionError so callers can catch the entire
family with a single except clause when needed.

Requirements: 17.1, 17.2, 17.3, 32.1
"""


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class GuruVisionError(Exception):
    """Base exception for all GuruVision errors."""


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class InitializationError(GuruVisionError):
    """Raised when the engine or a sub-module fails to initialise."""


class ConfigurationError(GuruVisionError):
    """Raised when a configuration value is invalid and cannot be recovered."""


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class DetectionError(GuruVisionError):
    """Raised when face detection fails unrecoverably."""


class AlignmentError(GuruVisionError):
    """Raised when face alignment fails."""


class RecognitionError(GuruVisionError):
    """Raised when embedding extraction or identity matching fails."""


class LivenessError(GuruVisionError):
    """Raised when the liveness detector encounters an unrecoverable error."""


class EmotionError(GuruVisionError):
    """Raised when the emotion recogniser encounters an unrecoverable error."""


class TrackingError(GuruVisionError):
    """Raised when the face tracker encounters an unrecoverable error."""


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


class DatabaseError(GuruVisionError):
    """Raised when the face database operation fails."""


# ---------------------------------------------------------------------------
# Legacy / feature-extraction aliases (kept for backward compatibility)
# ---------------------------------------------------------------------------


class FaceExtractionError(GuruVisionError):
    """Base exception for face feature extraction errors (legacy alias)."""


class FaceNotFoundError(FaceExtractionError):
    """Raised when no face is detected in the provided image."""


class LivenessFailedError(FaceExtractionError):
    """Raised when liveness detection determines the face is not live."""


class InvalidImageError(FaceExtractionError):
    """Raised when the provided image data is invalid or cannot be decoded."""


class ExtractionTimeoutError(FaceExtractionError):
    """Raised when feature extraction exceeds the 500 ms time limit."""
