"""Agent Guru - Vision Module.

Provides face detection and 512-dimensional embedding extraction.

This module does NOT perform authentication.  All authentication decisions
are delegated to the ``BiometricAuthenticator`` in
``Agent_Guru.security``.

Public API:
    FaceFeatureExtractor  - detect faces and extract embeddings
    FaceFeatures          - extraction result (embedding + quality + liveness)
    FaceDetection         - single detected face with bounding box
    FaceQuality           - quality metrics for a detected face
    BoundingBox           - face bounding box in image coordinates

Exceptions:
    FaceExtractionError   - base exception
    FaceNotFoundError     - no face detected
    LivenessFailedError   - liveness check failed
    InvalidImageError     - image cannot be decoded
    ExtractionTimeoutError - extraction exceeded 500 ms

Example:
    >>> from Agent_Guru.vision import FaceFeatureExtractor
    >>> extractor = FaceFeatureExtractor()
    >>> with open("face.jpg", "rb") as f:
    ...     features = extractor.extract_face_embedding(f.read())
    >>> print(features.embedding.shape)  # (512,)
    >>> # Pass features to BiometricAuthenticator for identity verification

"""

from Agent_Guru.vision.exceptions import (
    ExtractionTimeoutError,
    FaceExtractionError,
    FaceNotFoundError,
    InvalidImageError,
    LivenessFailedError,
)
from Agent_Guru.vision.face_features import FaceFeatureExtractor
from Agent_Guru.vision.models import BoundingBox, FaceDetection, FaceFeatures, FaceQuality

__version__ = "0.2.0"
__status__ = "IMPLEMENTED"

__all__ = [
    "BoundingBox",
    "ExtractionTimeoutError",
    "FaceDetection",
    # Exceptions
    "FaceExtractionError",
    # Main extractor
    "FaceFeatureExtractor",
    # Data models
    "FaceFeatures",
    "FaceNotFoundError",
    "FaceQuality",
    "InvalidImageError",
    "LivenessFailedError",
]
