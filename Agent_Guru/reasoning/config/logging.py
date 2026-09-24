"""Structured logging configuration using structlog."""

import logging
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.types import EventDict, Processor


def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application context to log entries."""
    event_dict["app"] = "agent_guru"
    event_dict["component"] = "reasoning_engine"
    return event_dict


def add_trace_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add trace context if available."""
    # This will be populated by the tracing system
    if "trace_id" not in event_dict:
        event_dict["trace_id"] = None
    if "span_id" not in event_dict:
        event_dict["span_id"] = None
    return event_dict


def configure_logging(
    log_level: str = "INFO",
    log_file: Path | None = None,
    json_format: bool = True,
    max_file_size: int = 100 * 1024 * 1024,  # 100MB
) -> None:
    """Configure structured logging with structlog.

    Args:
        log_level: Logging level (DEBUG, INFO, WARN, ERROR)
        log_file: Optional path to log file for rotation
        json_format: Whether to use JSON formatting (True for production)
        max_file_size: Maximum log file size before rotation (default 100MB)

    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
        force=True,  # Force reconfiguration even if already configured
    )

    # Build processor chain
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        add_app_context,
        add_trace_context,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_format:
        # JSON format for production
        processors.extend(
            [
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
        )
    else:
        # Console format for development
        processors.extend(
            [
                structlog.processors.ExceptionPrettyPrinter(),
                structlog.dev.ConsoleRenderer(colors=True),
            ],
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set up file rotation if log file specified
    if log_file:
        from logging.handlers import RotatingFileHandler

        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_file_size,
            backupCount=5,
        )
        file_handler.setLevel(numeric_level)
        logging.root.addHandler(file_handler)


def get_logger(name: str) -> Any:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger

    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Bind context variables that will be included in all subsequent log entries.

    Binding is ADDITIVE: keys bound earlier in the turn survive, and a repeated
    key is overwritten. It used to call ``clear_contextvars()`` first, which
    made the function a silent *replace* - so a request handler that bound
    ``user_id`` at the top of a turn lost it the moment any component further
    down bound, say, ``turn_id``, and every log line after that point was
    missing the identifier needed to correlate it. Callers that genuinely want
    a clean slate have ``clear_context()`` for exactly that.

    Args:
        **kwargs: Context key-value pairs (user_id, conversation_id, turn_id, etc.)

    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Remove specific context variables.

    Args:
        *keys: Context keys to remove

    """
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Clear all context variables."""
    structlog.contextvars.clear_contextvars()
