"""
Custom exception classes for GuruVision facial recognition system.

This module defines a hierarchy of exceptions for different error scenarios
throughout the GuruVision system, enabling precise error handling and recovery.
"""


class GuruVisionError(Exception):
    """
    Base exception class for all GuruVision errors.
    
    All custom exceptions in the GuruVision system inherit from this base class,
    allowing for catch-all error handling when needed.
    """
    pass


class InitializationError(GuruVisionError):
    """
    Raised during system initialization failures.
    
    Examples:
    - Model file not found
    - Invalid configuration
    - GPU unavailable when required
    - Database corruption during load
    - Module initialization failure
    """
    pass


class DetectionError(GuruVisionError):
    """
    Raised during face detection failures.
    
    Examples:
    - Detection model inference failure
    - Invalid input frame format
    - Detection model not loaded
    - Extreme processing errors
    """
    pass


class RecognitionError(GuruVisionError):
    """
    Raised during face recognition failures.
    
    Examples:
    - Embedding extraction failure
    - Recognition model inference error
    - Invalid aligned face input
    - Identity matching computation error
    """
    pass


class DatabaseError(GuruVisionError):
    """
    Raised during database operation failures.
    
    Examples:
    - Database file read/write errors
    - JSON serialization/deserialization errors
    - Identity not found
    - Invalid database format
    - Persistence failures
    """
    pass


class ConfigurationError(GuruVisionError):
    """
    Raised for invalid configuration issues.
    
    Examples:
    - Invalid configuration file format
    - Configuration values out of acceptable range
    - Missing required configuration parameters
    - Type mismatch in configuration values
    """
    pass
