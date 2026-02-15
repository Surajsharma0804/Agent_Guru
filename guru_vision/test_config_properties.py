"""
Property-based tests for GuruVision configuration module.

This module contains property tests that verify universal correctness properties
of the configuration management system, particularly configuration validation
and fallback behavior.
"""

import logging
import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import patch
import tempfile
import json
from pathlib import Path

from .config import GuruVisionConfig


# Strategy for generating invalid recognition thresholds (outside 0.4-0.9 range)
invalid_recognition_thresholds = st.one_of(
    st.floats(min_value=-10.0, max_value=0.39, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0.91, max_value=10.0, allow_nan=False, allow_infinity=False)
)

# Strategy for generating invalid detection confidence (outside 0.0-1.0 range)
invalid_detection_confidence = st.one_of(
    st.floats(min_value=-10.0, max_value=-0.01, allow_nan=False, allow_infinity=False),
    st.floats(min_value=1.01, max_value=10.0, allow_nan=False, allow_infinity=False)
)

# Strategy for generating invalid target_fps (non-positive)
invalid_target_fps = st.integers(max_value=0)

# Strategy for generating invalid tracker algorithms
invalid_tracker_algorithms = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
    min_size=1,
    max_size=20
).filter(lambda x: x.lower() not in ["deepsort", "bytetrack"])

# Strategy for generating invalid tracker_max_age (non-positive)
invalid_tracker_max_age = st.integers(max_value=0)

# Strategy for generating invalid log levels
invalid_log_levels = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
    min_size=1,
    max_size=20
).filter(lambda x: x.upper() not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

# Strategy for generating invalid log_max_size_mb (non-positive)
invalid_log_max_size_mb = st.integers(max_value=0)

# Strategy for generating invalid camera_index (negative)
invalid_camera_index = st.integers(max_value=-1)


@settings(max_examples=50, deadline=None)
@given(invalid_threshold=invalid_recognition_thresholds)
def test_property_22_recognition_threshold_fallback(invalid_threshold):
    """
    Property 22: Configuration Fallback - Recognition Threshold
    
    For any invalid recognition_threshold value (outside 0.4-0.9 range),
    the system should use the default value (0.6) and log a warning.
    
    Validates: Requirements 18.3
    """
    with patch('guru_vision.config.logger') as mock_logger:
        config = GuruVisionConfig(recognition_threshold=invalid_threshold)
        
        # Assert: Invalid value should be replaced with default
        assert config.recognition_threshold == 0.6, \
            f"Expected default 0.6, got {config.recognition_threshold}"
        
        # Assert: Warning should be logged
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "Invalid recognition_threshold" in warning_message
        assert "Using default: 0.6" in warning_message


@settings(max_examples=50, deadline=None)
@given(invalid_confidence=invalid_detection_confidence)
def test_property_22_detection_confidence_fallback(invalid_confidence):
    """
    Property 22: Configuration Fallback - Detection Confidence
    
    For any invalid detection_confidence value (outside 0.0-1.0 range),
    the system should use the default value (0.5) and log a warning.
    
    Validates: Requirements 18.3
    """
    with patch('guru_vision.config.logger') as mock_logger:
        config = GuruVisionConfig(detection_confidence=invalid_confidence)
        
        # Assert: Invalid value should be replaced with default
        assert config.detection_confidence == 0.5, \
            f"Expected default 0.5, got {config.detection_confidence}"
        
        # Assert: Warning should be logged
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "Invalid detection_confidence" in warning_message
        assert "Using default: 0.5" in warning_message


@settings(max_examples=50, deadline=None)
@given(invalid_fps=invalid_target_fps)
def test_property_22_target_fps_fallback(invalid_fps):
    """
    Property 22: Configuration Fallback - Target FPS
    
    For any invalid target_fps value (non-positive),
    the system should use the default value (10) and log a warning.
    
    Validates: Requirements 18.3
    """
    with patch('guru_vision.config.logger') as mock_logger:
        config = GuruVisionConfig(target_fps=invalid_fps)
        
        # Assert: Invalid value should be replaced with default
        assert config.target_fps == 10, \
            f"Expected default 10, got {config.target_fps}"
        
        # Assert: Warning should be logged
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "Invalid target_fps" in warning_message
        assert "Using default: 10" in warning_message


@settings(max_examples=50, deadline=None)
@given(invalid_algorithm=invalid_tracker_algorithms)
def test_property_22_tracker_algorithm_fallback(invalid_algorithm):
    """
    Property 22: Configuration Fallback - Tracker Algorithm
    
    For any invalid tracker_algorithm value (not "deepsort" or "bytetrack"),
    the system should use the default value ("deepsort") and log a warning.
    
    Validates: Requirements 18.3
    """
    with patch('guru_vision.config.logger') as mock_logger:
        config = GuruVisionConfig(tracker_algorithm=invalid_algorithm)
        
        # Assert: Invalid value should be replaced with default
        assert config.tracker_algorithm == "deepsort", \
            f"Expected default 'deepsort', got '{config.tracker_algorithm}'"
        
        # Assert: Warning should be logged
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "Invalid tracker_algorithm" in warning_message
        assert "Using default: deepsort" in warning_message


@settings(max_examples=50, deadline=None)
@given(invalid_max_age=invalid_tracker_max_age)
def test_property_22_tracker_max_age_fallback(invalid_max_age):
    """
    Property 22: Configuration Fallback - Tracker Max Age
    
    For any invalid tracker_max_age value (non-positive),
    the system should use the default value (30) and log a warning.
    
    Validates: Requirements 18.3
    """
    with patch('guru_vision.config.logger') as mock_logger:
        config = GuruVisionConfig(tracker_max_age=invalid_max_age)
        
        # Assert: Invalid value should be replaced with default
        assert config.tracker_max_age == 30, \
            f"Expected default 30, got {config.tracker_max_age}"
        
        # Assert: Warning should be logged
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "Invalid tracker_max_age" in warning_message
        assert "Using default: 30" in warning_message


@settings(max_examples=50, deadline=None)
@given(invalid_level=invalid_log_levels)
def test_property_22_log_level_fallback(invalid_level):
    """
    Property 22: Configuration Fallback - Log Level
    
    For any invalid log_level value (not a valid logging level),
    the system should use the default value ("INFO") and log a warning.
    
    Validates: Requirements 18.3
    """
    with patch('guru_vision.config.logger') as mock_logger:
        config = GuruVisionConfig(log_level=invalid_level)
        
        # Assert: Invalid value should be replaced with default
        assert config.log_level == "INFO", \
            f"Expected default 'INFO', got '{config.log_level}'"
        
        # Assert: Warning should be logged
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "Invalid log_level" in warning_message
        assert "Using default: INFO" in warning_message


@settings(max_examples=50, deadline=None)
@given(invalid_size=invalid_log_max_size_mb)
def test_property_22_log_max_size_fallback(invalid_size):
    """
    Property 22: Configuration Fallback - Log Max Size
    
    For any invalid log_max_size_mb value (non-positive),
    the system should use the default value (100) and log a warning.
    
    Validates: Requirements 18.3
    """
    with patch('guru_vision.config.logger') as mock_logger:
        config = GuruVisionConfig(log_max_size_mb=invalid_size)
        
        # Assert: Invalid value should be replaced with default
        assert config.log_max_size_mb == 100, \
            f"Expected default 100, got {config.log_max_size_mb}"
        
        # Assert: Warning should be logged
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "Invalid log_max_size_mb" in warning_message
        assert "Using default: 100" in warning_message


@settings(max_examples=50, deadline=None)
@given(invalid_index=invalid_camera_index)
def test_property_22_camera_index_fallback(invalid_index):
    """
    Property 22: Configuration Fallback - Camera Index
    
    For any invalid camera_index value (negative),
    the system should use the default value (0) and log a warning.
    
    Validates: Requirements 18.3
    """
    with patch('guru_vision.config.logger') as mock_logger:
        config = GuruVisionConfig(camera_index=invalid_index)
        
        # Assert: Invalid value should be replaced with default
        assert config.camera_index == 0, \
            f"Expected default 0, got {config.camera_index}"
        
        # Assert: Warning should be logged
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "Invalid camera_index" in warning_message
        assert "Using default: 0" in warning_message


@settings(max_examples=20, deadline=None)
@given(
    invalid_threshold=invalid_recognition_thresholds,
    invalid_confidence=invalid_detection_confidence,
    invalid_fps=invalid_target_fps
)
def test_property_22_multiple_invalid_values_fallback(
    invalid_threshold, invalid_confidence, invalid_fps
):
    """
    Property 22: Configuration Fallback - Multiple Invalid Values
    
    For any configuration with multiple invalid values,
    the system should replace all invalid values with their defaults
    and log a warning for each invalid value.
    
    Validates: Requirements 18.3
    """
    with patch('guru_vision.config.logger') as mock_logger:
        config = GuruVisionConfig(
            recognition_threshold=invalid_threshold,
            detection_confidence=invalid_confidence,
            target_fps=invalid_fps
        )
        
        # Assert: All invalid values should be replaced with defaults
        assert config.recognition_threshold == 0.6
        assert config.detection_confidence == 0.5
        assert config.target_fps == 10
        
        # Assert: Warning should be logged for each invalid value
        assert mock_logger.warning.call_count == 3, \
            f"Expected 3 warnings, got {mock_logger.warning.call_count}"


@settings(max_examples=20, deadline=None)
@given(invalid_threshold=invalid_recognition_thresholds)
def test_property_22_file_loading_with_invalid_values(invalid_threshold):
    """
    Property 22: Configuration Fallback - File Loading
    
    For any configuration file containing invalid values,
    when loaded, the system should replace invalid values with defaults
    and log warnings.
    
    Validates: Requirements 18.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.json"
        
        # Create config file with invalid value
        config_data = {
            "recognition_threshold": invalid_threshold,
            "onnx_model_path": "test/path/model.onnx"
        }
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        # Load config from file
        with patch('guru_vision.config.logger') as mock_logger:
            config = GuruVisionConfig.from_file(str(config_path))
            
            # Assert: Invalid value should be replaced with default
            assert config.recognition_threshold == 0.6
            
            # Assert: Valid value should be preserved
            assert config.onnx_model_path == "test/path/model.onnx"
            
            # Assert: Warning should be logged
            mock_logger.warning.assert_called_once()
            warning_message = mock_logger.warning.call_args[0][0]
            assert "Invalid recognition_threshold" in warning_message
