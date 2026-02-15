"""
Example demonstrating the logging utilities for GuruVision.

This script shows how to use the logging module in different scenarios.
"""

from guru_vision.utils.logging import setup_logging, get_logger, configure_component_logger


def example_basic_logging():
    """Example 1: Basic logging with console output only."""
    print("\n=== Example 1: Basic Console Logging ===")
    
    # Setup logging with console output only
    setup_logging(log_level="INFO", console_output=True)
    
    # Get a logger for this module
    logger = get_logger(__name__)
    
    # Log messages at different levels
    logger.debug("This debug message won't appear (log level is INFO)")
    logger.info("System initialized successfully")
    logger.warning("Low confidence detection: 0.55")
    logger.error("Failed to connect to camera")
    

def example_file_logging():
    """Example 2: Logging to both console and file."""
    print("\n=== Example 2: Console and File Logging ===")
    
    # Setup logging with both console and file output
    setup_logging(
        log_level="DEBUG",
        log_file="guru_face/logs/example.log",
        console_output=True
    )
    
    logger = get_logger("detection_module")
    
    logger.debug("Detailed detection information")
    logger.info("Face detected at coordinates (100, 150)")
    logger.warning("Detection confidence below threshold")
    
    print("Check guru_face/logs/example.log for the log file")


def example_component_logging():
    """Example 3: Different log levels for different components."""
    print("\n=== Example 3: Component-Specific Logging ===")
    
    # Setup root logger at INFO level
    setup_logging(log_level="INFO", console_output=True)
    
    # Configure detection module with DEBUG level
    detection_logger = configure_component_logger("guru_vision.detection", "DEBUG")
    
    # Configure recognition module with WARNING level
    recognition_logger = configure_component_logger("guru_vision.recognition", "WARNING")
    
    # Detection module will show DEBUG messages
    detection_logger.debug("Detailed detection debug info")
    detection_logger.info("Face detected")
    
    # Recognition module will only show WARNING and above
    recognition_logger.info("This info message won't appear")
    recognition_logger.warning("Low recognition confidence")


def example_structured_logging():
    """Example 4: Structured logging with context."""
    print("\n=== Example 4: Structured Logging ===")
    
    setup_logging(log_level="INFO", console_output=True)
    logger = get_logger("recognition_engine")
    
    # Log with context information
    identity = "John Doe"
    confidence = 0.87
    
    logger.info(f"Identity recognized: {identity} (confidence: {confidence:.2f})")
    logger.info(f"Processing frame 1234 at timestamp 2024-01-15T10:30:00Z")
    
    # Log errors with exception information
    try:
        # Simulate an error
        raise ValueError("Invalid embedding dimension")
    except Exception as e:
        logger.error(f"Error processing frame: {e}", exc_info=True)


if __name__ == "__main__":
    print("GuruVision Logging Examples")
    print("=" * 50)
    
    # Run examples
    example_basic_logging()
    example_file_logging()
    example_component_logging()
    example_structured_logging()
    
    print("\n" + "=" * 50)
    print("Examples completed!")
