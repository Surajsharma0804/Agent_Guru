"""GuruVision Facial Recognition System

A production-grade facial recognition system built on state-of-the-art deep learning models.
"""

__version__ = "0.1.0"

# Export custom exceptions
from guru_vision.exceptions import (
    GuruVisionError,
    InitializationError,
    DetectionError,
    RecognitionError,
    DatabaseError,
    ConfigurationError,
)

__all__ = [
    "GuruVisionError",
    "InitializationError",
    "DetectionError",
    "RecognitionError",
    "DatabaseError",
    "ConfigurationError",
]
