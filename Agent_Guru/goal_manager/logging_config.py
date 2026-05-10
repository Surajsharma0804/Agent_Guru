"""Structured logging configuration for Goal Manager.

This module sets up structlog for structured logging throughout the Goal Manager
system. All log entries include structured context (goal_id, operation, timestamp,
error details) for better observability and debugging.

Usage:
    from Agent_Guru.goal_manager.logging_config import get_logger

    logger = get_logger(__name__)
    logger.info("goal_created", goal_id=goal.id, description=goal.description)
    logger.error("storage_failed", goal_id=goal.id, operation="store", error=str(e))
"""

from typing import Any

import structlog


def configure_logging() -> None:
    """Configure structlog for Goal Manager.

    Sets up structured logging with:
    - Timestamp processor (ISO 8601 format)
    - Stack info processor (for exceptions)
    - Exception formatter (for tracebacks)
    - JSON renderer (for structured output)
    """
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Structured logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("operation_started", goal_id="123", operation="store")

    """
    return structlog.get_logger(name)


# Configure logging on module import
configure_logging()
