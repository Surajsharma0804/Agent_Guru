"""
Tests for custom exception classes.
"""

import pytest
from guru_vision.exceptions import (
    GuruVisionError,
    InitializationError,
    DetectionError,
    RecognitionError,
    DatabaseError,
    ConfigurationError,
)


def test_guruvision_error_base():
    """Test that GuruVisionError can be raised and caught."""
    with pytest.raises(GuruVisionError):
        raise GuruVisionError("Base error")


def test_initialization_error():
    """Test InitializationError inheritance and usage."""
    with pytest.raises(InitializationError):
        raise InitializationError("Model file not found")
    
    # Should also be catchable as GuruVisionError
    with pytest.raises(GuruVisionError):
        raise InitializationError("Model file not found")


def test_detection_error():
    """Test DetectionError inheritance and usage."""
    with pytest.raises(DetectionError):
        raise DetectionError("Detection model inference failed")
    
    with pytest.raises(GuruVisionError):
        raise DetectionError("Detection model inference failed")


def test_recognition_error():
    """Test RecognitionError inheritance and usage."""
    with pytest.raises(RecognitionError):
        raise RecognitionError("Embedding extraction failed")
    
    with pytest.raises(GuruVisionError):
        raise RecognitionError("Embedding extraction failed")


def test_database_error():
    """Test DatabaseError inheritance and usage."""
    with pytest.raises(DatabaseError):
        raise DatabaseError("Database file not found")
    
    with pytest.raises(GuruVisionError):
        raise DatabaseError("Database file not found")


def test_configuration_error():
    """Test ConfigurationError inheritance and usage."""
    with pytest.raises(ConfigurationError):
        raise ConfigurationError("Invalid threshold value")
    
    with pytest.raises(GuruVisionError):
        raise ConfigurationError("Invalid threshold value")


def test_exception_messages():
    """Test that exception messages are preserved."""
    error_message = "Custom error message"
    
    try:
        raise InitializationError(error_message)
    except InitializationError as e:
        assert str(e) == error_message


def test_exception_hierarchy():
    """Test that all custom exceptions inherit from GuruVisionError."""
    assert issubclass(InitializationError, GuruVisionError)
    assert issubclass(DetectionError, GuruVisionError)
    assert issubclass(RecognitionError, GuruVisionError)
    assert issubclass(DatabaseError, GuruVisionError)
    assert issubclass(ConfigurationError, GuruVisionError)


def test_catch_all_guruvision_errors():
    """Test that GuruVisionError can catch all custom exceptions."""
    exceptions_to_test = [
        InitializationError("init error"),
        DetectionError("detection error"),
        RecognitionError("recognition error"),
        DatabaseError("database error"),
        ConfigurationError("config error"),
    ]
    
    for exc in exceptions_to_test:
        with pytest.raises(GuruVisionError):
            raise exc
