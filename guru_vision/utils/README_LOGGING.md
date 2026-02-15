# GuruVision Logging Utilities

## Overview

The logging utilities module provides centralized logging configuration for the GuruVision facial recognition system. It supports timestamps, component names, multiple log levels, console and file output, and automatic log rotation.

## Features

- **Timestamps**: All log messages include timestamps in `YYYY-MM-DD HH:MM:SS` format
- **Component Names**: Each log message identifies the component/module that generated it
- **Log Levels**: Support for DEBUG, INFO, WARNING, ERROR, and CRITICAL levels
- **Console Output**: Optional console logging to stdout
- **File Output**: Optional file logging with automatic directory creation
- **Log Rotation**: Automatic rotation when log files exceed 100MB (configurable)
- **Component-Specific Levels**: Different log levels for different components

## Requirements Satisfied

- **17.1**: Log error messages with timestamps, component names, and descriptions
- **17.5**: Support configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **17.6**: Write logs to both console output and log files
- **17.7**: Rotate logs when files exceed 100MB

## Usage

### Basic Setup

```python
from guru_vision.utils.logging import setup_logging, get_logger

# Setup logging with console output only
setup_logging(log_level="INFO", console_output=True)

# Get a logger for your module
logger = get_logger(__name__)

# Log messages
logger.info("System initialized")
logger.warning("Low confidence detection")
logger.error("Failed to connect to camera")
```

### File Logging

```python
from guru_vision.utils.logging import setup_logging, get_logger

# Setup logging with both console and file output
setup_logging(
    log_level="DEBUG",
    log_file="guru_face/logs/guruvision.log",
    log_max_size_mb=100,  # Rotate after 100MB
    console_output=True
)

logger = get_logger("detection_module")
logger.debug("Detailed detection information")
```

### Component-Specific Log Levels

```python
from guru_vision.utils.logging import setup_logging, configure_component_logger

# Setup root logger at INFO level
setup_logging(log_level="INFO", console_output=True)

# Configure specific component with DEBUG level
detection_logger = configure_component_logger("guru_vision.detection", "DEBUG")

# This component will show DEBUG messages
detection_logger.debug("Detailed debug info")
```

### Shutdown

```python
from guru_vision.utils.logging import shutdown_logging

# Clean shutdown - flush and close all handlers
shutdown_logging()
```

## API Reference

### `setup_logging()`

Configure the root logger with specified settings.

**Parameters:**
- `log_level` (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: "INFO"
- `log_file` (str, optional): Path to log file. If None, only console logging is enabled
- `log_max_size_mb` (int): Maximum log file size in MB before rotation. Default: 100
- `console_output` (bool): Enable console output. Default: True
- `log_format` (str, optional): Custom log format string
- `date_format` (str, optional): Custom date format string

**Returns:** Configured root logger instance

### `get_logger(name)`

Get a logger instance for a specific component.

**Parameters:**
- `name` (str): Name of the logger, typically the module name (`__name__`)

**Returns:** Logger instance for the specified component

### `configure_component_logger(component_name, log_level)`

Configure a logger for a specific component with optional custom log level.

**Parameters:**
- `component_name` (str): Name of the component/module
- `log_level` (str, optional): Log level for this component

**Returns:** Configured logger instance for the component

### `shutdown_logging()`

Shutdown the logging system and flush all handlers.

## Log Format

Default log format:
```
YYYY-MM-DD HH:MM:SS - component_name - LEVEL - message
```

Example:
```
2026-02-15 11:10:36 - guru_vision.detection - INFO - Face detected at coordinates (100, 150)
```

## Log Rotation

- Log files automatically rotate when they exceed the configured size (default: 100MB)
- Up to 5 backup files are kept (e.g., `app.log.1`, `app.log.2`, etc.)
- Oldest backup files are deleted when the limit is reached

## Testing

Run the unit tests:
```bash
python -m pytest guru_vision/utils/test_logging.py -v
```

Run the examples:
```bash
python -m guru_vision.utils.example_logging
```

## Integration with GuruVision

The logging module integrates with the GuruVision configuration system:

```python
from guru_vision.config import GuruVisionConfig
from guru_vision.utils.logging import setup_logging

# Load configuration
config = GuruVisionConfig.from_file("config.yaml")

# Setup logging from configuration
setup_logging(
    log_level=config.log_level,
    log_file=config.log_file,
    log_max_size_mb=config.log_max_size_mb
)
```

## Notes

- Call `setup_logging()` once at application startup
- Use `get_logger(__name__)` in each module to get a component-specific logger
- All loggers inherit the configuration from the root logger
- Individual components can have different log levels using `configure_component_logger()`
- Always call `shutdown_logging()` during application shutdown to ensure all logs are flushed
