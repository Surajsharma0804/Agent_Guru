"""
Logging utilities for GuruVision facial recognition system.

This module provides centralized logging configuration with support for:
- Timestamps and component names in log messages
- Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Both console and file output
- Automatic log rotation when files exceed maximum size
- Structured logging format for easy parsing

Requirements: 17.1, 17.5, 17.6, 17.7
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


# Default log format with timestamp, component name, level, and message
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_max_size_mb: int = 100,
    console_output: bool = True,
    log_format: Optional[str] = None,
    date_format: Optional[str] = None
) -> logging.Logger:
    """
    Configure logging for the GuruVision system.
    
    This function sets up the root logger with the specified configuration,
    including console and/or file handlers with automatic rotation.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file. If None, only console logging is enabled
        log_max_size_mb: Maximum log file size in MB before rotation (default: 100)
        console_output: Enable console output (default: True)
        log_format: Custom log format string. If None, uses DEFAULT_LOG_FORMAT
        date_format: Custom date format string. If None, uses DEFAULT_DATE_FORMAT
    
    Returns:
        Configured root logger instance
    
    Example:
        >>> logger = setup_logging(log_level="DEBUG", log_file="app.log")
        >>> logger.info("System initialized")
        >>> logger.error("An error occurred", exc_info=True)
    
    Requirements:
        - 17.1: Log error messages with timestamps, component names, and descriptions
        - 17.5: Support configurable log levels
        - 17.6: Write logs to both console output and log files
        - 17.7: Rotate logs when files exceed 100MB
    """
    # Normalize log level to uppercase
    log_level = log_level.upper()
    
    # Validate log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in valid_levels:
        print(f"Warning: Invalid log level '{log_level}'. Using 'INFO' instead.")
        log_level = "INFO"
    
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Clear any existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Set the root logger level
    root_logger.setLevel(getattr(logging, log_level))
    
    # Use default formats if not provided
    if log_format is None:
        log_format = DEFAULT_LOG_FORMAT
    if date_format is None:
        date_format = DEFAULT_DATE_FORMAT
    
    # Create formatter
    formatter = logging.Formatter(log_format, datefmt=date_format)
    
    # Add console handler if enabled
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # Add file handler if log_file is specified
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert MB to bytes for maxBytes parameter
        max_bytes = log_max_size_mb * 1024 * 1024
        
        # Create rotating file handler
        # backupCount=5 means keep up to 5 backup files (e.g., app.log.1, app.log.2, ...)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Log the initialization
    root_logger.info(
        f"Logging initialized: level={log_level}, "
        f"console={console_output}, file={log_file is not None}"
    )
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific component.
    
    This function returns a logger with the specified name, which will
    inherit the configuration from the root logger set up by setup_logging().
    
    Args:
        name: Name of the logger, typically the module name (__name__)
    
    Returns:
        Logger instance for the specified component
    
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing frame")
        >>> logger.warning("Low confidence detection")
    
    Note:
        This function should be called after setup_logging() has been called
        to configure the root logger. If setup_logging() hasn't been called,
        the logger will use Python's default configuration.
    """
    return logging.getLogger(name)


def configure_component_logger(
    component_name: str,
    log_level: Optional[str] = None
) -> logging.Logger:
    """
    Configure a logger for a specific component with optional custom log level.
    
    This allows individual components to have different log levels than the
    root logger. For example, you might want DEBUG logging for one module
    while keeping INFO for others.
    
    Args:
        component_name: Name of the component/module
        log_level: Optional log level for this component. If None, inherits from root
    
    Returns:
        Configured logger instance for the component
    
    Example:
        >>> # Set DEBUG level for detection module only
        >>> detector_logger = configure_component_logger("guru_vision.detection", "DEBUG")
        >>> detector_logger.debug("Detailed detection info")
    """
    logger = logging.getLogger(component_name)
    
    if log_level:
        log_level = log_level.upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        if log_level in valid_levels:
            logger.setLevel(getattr(logging, log_level))
        else:
            logger.warning(
                f"Invalid log level '{log_level}' for component '{component_name}'. "
                "Using inherited level."
            )
    
    return logger


def shutdown_logging() -> None:
    """
    Shutdown the logging system and flush all handlers.
    
    This function should be called during system shutdown to ensure all
    log messages are written and file handles are properly closed.
    
    Example:
        >>> shutdown_logging()
    
    Note:
        After calling this function, logging will still work but may not
        be properly configured. Call setup_logging() again if needed.
    """
    logging.shutdown()
