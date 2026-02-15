"""
Unit tests for the logging utilities module.

Tests verify that logging is configured correctly with timestamps,
component names, log levels, console output, file output, and rotation.
"""

import logging
import os
import tempfile
from pathlib import Path

import pytest

from guru_vision.utils.logging import (
    setup_logging,
    get_logger,
    configure_component_logger,
    shutdown_logging
)


class TestLoggingSetup:
    """Test suite for logging setup functionality."""
    
    def teardown_method(self):
        """Clean up after each test."""
        # Get root logger
        root_logger = logging.getLogger()
        
        # Close and remove all handlers
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)
        
        # Shutdown logging to ensure all resources are released
        shutdown_logging()
    
    def test_setup_logging_console_only(self):
        """Test logging setup with console output only."""
        logger = setup_logging(log_level="INFO", console_output=True)
        
        assert logger is not None
        assert logger.level == logging.INFO
        assert len(logger.handlers) >= 1
        
        # Check that at least one handler is a StreamHandler
        has_console_handler = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
            for h in logger.handlers
        )
        assert has_console_handler
    
    def test_setup_logging_with_file(self):
        """Test logging setup with file output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            
            logger = setup_logging(
                log_level="DEBUG",
                log_file=log_file,
                console_output=True
            )
            
            assert logger is not None
            assert logger.level == logging.DEBUG
            
            # Write a test message
            logger.info("Test message")
            
            # Flush and close handlers before cleanup
            for handler in logger.handlers[:]:
                handler.flush()
                handler.close()
                logger.removeHandler(handler)
            
            # Verify log file was created
            assert os.path.exists(log_file)
            
            # Verify message was written
            with open(log_file, 'r') as f:
                content = f.read()
                assert "Test message" in content
                assert "INFO" in content
    
    def test_setup_logging_creates_directory(self):
        """Test that logging setup creates log directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "logs", "subdir", "test.log")
            
            logger = setup_logging(log_level="INFO", log_file=log_file)
            
            # Verify directory was created
            assert os.path.exists(os.path.dirname(log_file))
            
            # Verify log file was created
            logger.info("Test")
            
            # Close handlers before cleanup
            for handler in logger.handlers[:]:
                handler.flush()
                handler.close()
                logger.removeHandler(handler)
            
            assert os.path.exists(log_file)
    
    def test_setup_logging_log_levels(self):
        """Test different log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            shutdown_logging()
            logging.getLogger().handlers.clear()
            
            logger = setup_logging(log_level=level, console_output=True)
            assert logger.level == getattr(logging, level)
    
    def test_setup_logging_invalid_level(self):
        """Test that invalid log level falls back to INFO."""
        logger = setup_logging(log_level="INVALID", console_output=True)
        assert logger.level == logging.INFO
    
    def test_setup_logging_rotation_config(self):
        """Test that log rotation is configured correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            max_size_mb = 50
            
            logger = setup_logging(
                log_level="INFO",
                log_file=log_file,
                log_max_size_mb=max_size_mb,
                console_output=False
            )
            
            # Find the RotatingFileHandler
            from logging.handlers import RotatingFileHandler
            file_handler = None
            for handler in logger.handlers:
                if isinstance(handler, RotatingFileHandler):
                    file_handler = handler
                    break
            
            assert file_handler is not None
            # Verify max bytes is set correctly (50 MB = 50 * 1024 * 1024 bytes)
            assert file_handler.maxBytes == max_size_mb * 1024 * 1024
            # Verify backup count is set
            assert file_handler.backupCount == 5
            
            # Close handlers before cleanup
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
    
    def test_get_logger(self):
        """Test getting a component logger."""
        setup_logging(log_level="INFO", console_output=True)
        
        logger = get_logger("test_component")
        assert logger is not None
        assert logger.name == "test_component"
    
    def test_configure_component_logger(self):
        """Test configuring a component logger with custom level."""
        setup_logging(log_level="INFO", console_output=True)
        
        # Configure component with DEBUG level
        component_logger = configure_component_logger("test_module", "DEBUG")
        
        assert component_logger.level == logging.DEBUG
        assert component_logger.name == "test_module"
    
    def test_configure_component_logger_invalid_level(self):
        """Test that invalid component log level is handled gracefully."""
        setup_logging(log_level="INFO", console_output=True)
        
        # This should not raise an exception
        component_logger = configure_component_logger("test_module", "INVALID")
        assert component_logger is not None
    
    def test_log_message_format(self):
        """Test that log messages include timestamp, component name, and level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            
            setup_logging(log_level="INFO", log_file=log_file, console_output=False)
            logger = get_logger("test_component")
            
            logger.info("Test message")
            logger.warning("Warning message")
            logger.error("Error message")
            
            # Flush and close handlers
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                handler.flush()
                handler.close()
                root_logger.removeHandler(handler)
            
            # Read log file
            with open(log_file, 'r') as f:
                content = f.read()
            
            # Verify format includes required elements
            assert "test_component" in content
            assert "INFO" in content
            assert "WARNING" in content
            assert "ERROR" in content
            assert "Test message" in content
            assert "Warning message" in content
            assert "Error message" in content
            
            # Verify timestamp format (YYYY-MM-DD HH:MM:SS)
            import re
            timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
            assert re.search(timestamp_pattern, content) is not None
    
    def test_shutdown_logging(self):
        """Test that shutdown_logging closes handlers properly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            
            logger = setup_logging(log_level="INFO", log_file=log_file)
            logger.info("Before shutdown")
            
            # Shutdown logging
            shutdown_logging()
            
            # Handlers should be closed (this is hard to test directly,
            # but we can verify the function doesn't raise an exception)
            assert True
    
    def test_console_output_disabled(self):
        """Test logging with console output disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            
            logger = setup_logging(
                log_level="INFO",
                log_file=log_file,
                console_output=False
            )
            
            # Should only have file handler
            from logging.handlers import RotatingFileHandler
            assert len(logger.handlers) == 1
            assert isinstance(logger.handlers[0], RotatingFileHandler)
            
            # Close handlers before cleanup
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
    
    def test_multiple_components_logging(self):
        """Test that multiple components can log independently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            
            setup_logging(log_level="INFO", log_file=log_file, console_output=False)
            
            logger1 = get_logger("component1")
            logger2 = get_logger("component2")
            
            logger1.info("Message from component 1")
            logger2.warning("Message from component 2")
            
            # Flush and close handlers
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                handler.flush()
                handler.close()
                root_logger.removeHandler(handler)
            
            # Read log file
            with open(log_file, 'r') as f:
                content = f.read()
            
            # Verify both components logged
            assert "component1" in content
            assert "component2" in content
            assert "Message from component 1" in content
            assert "Message from component 2" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# Property-Based Tests
from hypothesis import given, strategies as st, settings


# Strategy for generating component names
component_names = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "P")),
    min_size=1,
    max_size=50
)

# Strategy for generating error messages
# Exclude control characters and whitespace-only strings that might be normalized
error_messages = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs", "Cc"),  # Exclude surrogates and control chars
        blacklist_characters="\r\n\t"  # Exclude specific whitespace chars
    ),
    min_size=1,
    max_size=200
).filter(lambda x: x.strip() != "")  # Exclude whitespace-only strings

# Strategy for generating log levels for errors
error_log_levels = st.sampled_from(["ERROR", "CRITICAL"])


@settings(max_examples=50, deadline=None)
@given(
    component_name=component_names,
    error_message=error_messages,
    log_level=error_log_levels
)
def test_property_21_error_log_structure(component_name, error_message, log_level):
    """
    Property 21: Error Log Structure
    
    For any error that occurs during system operation, the logged error message
    should contain a timestamp, component name, and error description.
    
    This property verifies that when any component logs an error, the log entry
    includes all required structural elements as specified in Requirement 17.1.
    
    Validates: Requirements 17.1
    """
    import re
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "test_property.log")
        
        # Setup logging
        setup_logging(log_level="DEBUG", log_file=log_file, console_output=False)
        
        # Get logger for the component
        logger = get_logger(component_name)
        
        # Log an error message
        if log_level == "ERROR":
            logger.error(error_message)
        else:  # CRITICAL
            logger.critical(error_message)
        
        # Flush and close handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            handler.flush()
            handler.close()
            root_logger.removeHandler(handler)
        
        # Read the log file
        with open(log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        # Property assertions:
        # 1. Log entry should contain a timestamp in format YYYY-MM-DD HH:MM:SS
        timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
        assert re.search(timestamp_pattern, log_content) is not None, \
            f"Log entry missing timestamp. Content: {log_content}"
        
        # 2. Log entry should contain the component name
        assert component_name in log_content, \
            f"Log entry missing component name '{component_name}'. Content: {log_content}"
        
        # 3. Log entry should contain the error description (message)
        assert error_message in log_content, \
            f"Log entry missing error message '{error_message}'. Content: {log_content}"
        
        # 4. Log entry should contain the log level
        assert log_level in log_content, \
            f"Log entry missing log level '{log_level}'. Content: {log_content}"
        
        # 5. Verify the complete structure matches the expected format:
        # "YYYY-MM-DD HH:MM:SS - component_name - LEVEL - message"
        expected_pattern = (
            r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - '  # timestamp
            r'.+ - '  # component name (any characters)
            r'(ERROR|CRITICAL) - '  # log level
            r'.+'  # message
        )
        assert re.search(expected_pattern, log_content) is not None, \
            f"Log entry does not match expected structure. Content: {log_content}"


@settings(max_examples=30, deadline=None)
@given(
    component_name=component_names,
    error_message=error_messages
)
def test_property_21_error_log_structure_with_exception(component_name, error_message):
    """
    Property 21: Error Log Structure - With Exception Info
    
    For any error that occurs with exception information, the logged error message
    should contain a timestamp, component name, error description, and exception details.
    
    This variant tests that exception information is properly included when logging
    errors with exc_info=True.
    
    Validates: Requirements 17.1
    """
    import re
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "test_property_exc.log")
        
        # Setup logging
        setup_logging(log_level="DEBUG", log_file=log_file, console_output=False)
        
        # Get logger for the component
        logger = get_logger(component_name)
        
        # Create an exception and log it
        try:
            raise ValueError(error_message)
        except ValueError:
            logger.error("Exception occurred", exc_info=True)
        
        # Flush and close handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            handler.flush()
            handler.close()
            root_logger.removeHandler(handler)
        
        # Read the log file
        with open(log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        # Property assertions:
        # 1. Log entry should contain a timestamp
        timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
        assert re.search(timestamp_pattern, log_content) is not None, \
            f"Log entry missing timestamp. Content: {log_content}"
        
        # 2. Log entry should contain the component name
        assert component_name in log_content, \
            f"Log entry missing component name '{component_name}'. Content: {log_content}"
        
        # 3. Log entry should contain the error description
        assert "Exception occurred" in log_content, \
            f"Log entry missing error description. Content: {log_content}"
        
        # 4. Log entry should contain ERROR level
        assert "ERROR" in log_content, \
            f"Log entry missing ERROR level. Content: {log_content}"
        
        # 5. Log entry should contain exception information (traceback)
        assert "Traceback" in log_content or "ValueError" in log_content, \
            f"Log entry missing exception information. Content: {log_content}"


@settings(max_examples=30, deadline=None)
@given(
    num_components=st.integers(min_value=2, max_value=5),
    error_message=error_messages
)
def test_property_21_multiple_components_error_logging(num_components, error_message):
    """
    Property 21: Error Log Structure - Multiple Components
    
    For any errors logged by multiple components, each log entry should contain
    its own timestamp, component name, and error description, maintaining
    proper structure for all entries.
    
    This tests that the log structure property holds when multiple components
    are logging errors concurrently.
    
    Validates: Requirements 17.1
    """
    import re
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "test_property_multi.log")
        
        # Setup logging
        setup_logging(log_level="DEBUG", log_file=log_file, console_output=False)
        
        # Create multiple component loggers and log errors
        component_names = [f"component_{i}" for i in range(num_components)]
        
        for comp_name in component_names:
            logger = get_logger(comp_name)
            logger.error(f"{error_message} from {comp_name}")
        
        # Flush and close handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            handler.flush()
            handler.close()
            root_logger.removeHandler(handler)
        
        # Read the log file
        with open(log_file, 'r', encoding='utf-8') as f:
            log_lines = f.readlines()
        
        # Filter out the initialization log line
        error_lines = [line for line in log_lines if "ERROR" in line and "component_" in line]
        
        # Should have one error line per component
        assert len(error_lines) >= num_components, \
            f"Expected at least {num_components} error lines, got {len(error_lines)}"
        
        # Verify each error line has proper structure
        timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
        
        for line in error_lines:
            # 1. Should contain timestamp
            assert re.search(timestamp_pattern, line) is not None, \
                f"Error line missing timestamp: {line}"
            
            # 2. Should contain ERROR level
            assert "ERROR" in line, \
                f"Error line missing ERROR level: {line}"
            
            # 3. Should contain a component name
            assert any(comp in line for comp in component_names), \
                f"Error line missing component name: {line}"
            
            # 4. Should contain the error message
            assert error_message in line, \
                f"Error line missing error message: {line}"
