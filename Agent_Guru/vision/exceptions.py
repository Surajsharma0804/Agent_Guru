"""
Exceptions for the vision feature extraction module.

These exceptions represent errors during face detection and embedding extraction.
No authentication logic is present here — authentication is handled by
guru-security-cryptography.
"""


class FaceExtractionError(Exception):
    """Base exception for face feature extraction errors."""

    pass


class FaceNotFoundError(FaceExtractionError):
    """Raised when no face is detected in the provided image."""

    pass


class LivenessFailedError(FaceExtractionError):
    """Raised when liveness detection determines the face is not live (anti-spoofing)."""

    pass


class InvalidImageError(FaceExtractionError):
    """Raised when the provided image data is invalid or cannot be decoded."""

    pass


class ExtractionTimeoutError(FaceExtractionError):
    """Raised when feature extraction exceeds the 500ms time limit."""

    pass
