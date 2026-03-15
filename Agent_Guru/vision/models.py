"""
Data models for the vision feature extraction module.

These models represent the output of face detection and embedding extraction.
They carry NO authentication logic — they are pure data containers that the
guru-security-cryptography BiometricAuthenticator uses to make auth decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np


@dataclass
class BoundingBox:
    """Axis-aligned bounding box for a detected face.

    Attributes:
        x: Left edge (pixels)
        y: Top edge (pixels)
        width: Box width (pixels)
        height: Box height (pixels)
        confidence: Detection confidence score in [0.0, 1.0]
    """

    x: int
    y: int
    width: int
    height: int
    confidence: float

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("BoundingBox width and height must be positive")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("BoundingBox confidence must be in [0.0, 1.0]")


@dataclass
class FaceDetection:
    """A single detected face with its location and landmarks.

    Attributes:
        bounding_box: Face bounding box in the source image
        landmarks: Optional facial landmark coordinates (e.g. eyes, nose, mouth)
        detection_confidence: Confidence of the face detection in [0.0, 1.0]
    """

    bounding_box: BoundingBox
    landmarks: Optional[np.ndarray] = None  # shape (N, 2) — (x, y) pairs
    detection_confidence: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.detection_confidence <= 1.0:
            raise ValueError("detection_confidence must be in [0.0, 1.0]")


@dataclass
class FaceQuality:
    """Quality metrics for a detected face.

    Attributes:
        overall_score: Aggregate quality score in [0.0, 1.0]
        sharpness: Image sharpness score in [0.0, 1.0]
        brightness: Brightness score in [0.0, 1.0] (0 = too dark, 1 = ideal)
        pose_score: Frontal-pose score in [0.0, 1.0] (1 = fully frontal)
    """

    overall_score: float
    sharpness: float = 1.0
    brightness: float = 1.0
    pose_score: float = 1.0

    def __post_init__(self) -> None:
        for name, val in [
            ("overall_score", self.overall_score),
            ("sharpness", self.sharpness),
            ("brightness", self.brightness),
            ("pose_score", self.pose_score),
        ]:
            if not 0.0 <= val <= 1.0:
                raise ValueError(f"FaceQuality.{name} must be in [0.0, 1.0], got {val}")


@dataclass
class FaceFeatures:
    """Complete face feature extraction result.

    This is the primary output of FaceFeatureExtractor.extract_face_embedding().
    It contains everything the BiometricAuthenticator needs to make an
    authentication decision — but makes NO decision itself.

    Attributes:
        embedding: 512-dimensional face embedding vector (L2-normalised)
        quality_score: Overall face quality in [0.0, 1.0]
        is_live: Whether liveness detection passed
        liveness_score: Liveness confidence in [0.0, 1.0]
        bounding_box: Location of the face in the source image
        quality: Detailed quality metrics
    """

    embedding: np.ndarray  # shape (512,), dtype float32
    quality_score: float
    is_live: bool
    liveness_score: float
    bounding_box: BoundingBox
    quality: FaceQuality = field(default_factory=lambda: FaceQuality(overall_score=1.0))

    def __post_init__(self) -> None:
        if self.embedding.shape != (512,):
            raise ValueError(
                f"FaceFeatures.embedding must have shape (512,), got {self.embedding.shape}"
            )
        if self.embedding.dtype != np.float32:
            self.embedding = self.embedding.astype(np.float32)
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError("FaceFeatures.quality_score must be in [0.0, 1.0]")
        if not 0.0 <= self.liveness_score <= 1.0:
            raise ValueError("FaceFeatures.liveness_score must be in [0.0, 1.0]")
