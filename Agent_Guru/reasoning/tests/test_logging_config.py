"""Comprehensive unit tests for logging configuration - 100% coverage."""

import logging
import tempfile
from pathlib import Path

from Agent_Guru.reasoning.config.logging import (
    add_app_context,
    add_trace_context,
    configure_logging,
    get_logger,
    bind_context,
    unbind_context,
    clear_context,
)


class TestLoggingConfig:
    """Test logging configuration."""
    
    def setup_method(self):
        """Reset logging configuration before each test."""
        # Clear all handlers from root logger
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()
        # Reset root logger level
        root_logger.setLevel(logging.WARNING)
    
    def test_add_app_context(self):
        """Test adding application context to log entries."""
        event_dict = {}
        result = add_app_context(None, "test_method", event_dict)
        
        assert result["app"] == "agent_guru"  # nosec B101
        assert result["component"] == "reasoning_engine"  # nosec B101
    
    def test_add_trace_context_no_existing(self):
        """Test adding trace context when not present."""
        event_dict = {}
        result = add_trace_context(None, "test_method", event_dict)
        
        assert result["trace_id"] is None  # nosec B101
        assert result["span_id"] is None  # nosec B101
    
    def test_add_trace_context_existing(self):
        """Test adding trace context when already present."""
        event_dict = {"trace_id": "test123", "span_id": "span456"}
        result = add_trace_context(None, "test_method", event_dict)
        
        assert result["trace_id"] == "test123"  # nosec B101
        assert result["span_id"] == "span456"  # nosec B101
    
    def test_configure_logging_json_format(self):
        """Test configuring logging with JSON format."""
        configure_logging(log_level="INFO", json_format=True)
        
        # Verify logging is configured
        logger = logging.getLogger()
        assert logger.level == logging.INFO  # nosec B101
    
    def test_configure_logging_console_format(self):
        """Test configuring logging with console format."""
        configure_logging(log_level="DEBUG", json_format=False)
        
        logger = logging.getLogger()
        assert logger.level == logging.DEBUG  # nosec B101
    
    def test_configure_logging_with_file(self):
        """Test configuring logging with file rotation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"
            configure_logging(
                log_level="WARNING",
                log_file=log_file,
                max_file_size=1024 * 1024,  # 1MB
            )
            
            # Verify file handler was added
            logger = logging.getLogger()
            file_handlers = [h for h in logger.handlers 
                           if isinstance(h, logging.handlers.RotatingFileHandler)]
            assert len(file_handlers) > 0  # nosec B101
            
            # Close file handlers to release file locks
            for handler in file_handlers:
                handler.close()
                logger.removeHandler(handler)
    
    def test_configure_logging_invalid_level(self):
        """Test configuring logging with invalid level defaults to INFO."""
        configure_logging(log_level="INVALID")
        
        logger = logging.getLogger()
        assert logger.level == logging.INFO  # nosec B101
    
    def test_get_logger(self):
        """Test getting a structured logger."""
        configure_logging()
        logger = get_logger("test_module")
        
        assert logger is not None  # nosec B101
        assert hasattr(logger, "info")  # nosec B101
        assert hasattr(logger, "error")  # nosec B101
    
    def test_bind_context(self):
        """Test binding context variables.

        The bound values ARE observable - structlog.contextvars.get_contextvars()
        returns them - so this no longer has to settle for `assert True`.
        """
        import structlog

        clear_context()
        bind_context(user_id="user123", conversation_id="conv456")

        bound = structlog.contextvars.get_contextvars()
        assert bound.get("user_id") == "user123"  # nosec B101
        assert bound.get("conversation_id") == "conv456"  # nosec B101
        clear_context()

    def test_bind_context_is_additive(self):
        """A second bind must not erase the first.

        bind_context() used to call clear_contextvars() before binding, so a
        later bind silently dropped every identifier bound earlier in the turn.
        """
        import structlog

        clear_context()
        bind_context(user_id="user123")
        bind_context(turn_id="turn789")

        bound = structlog.contextvars.get_contextvars()
        assert bound.get("user_id") == "user123", "earlier context was dropped"  # nosec B101
        assert bound.get("turn_id") == "turn789"  # nosec B101
        clear_context()

    def test_bind_context_overwrites_same_key(self):
        """Re-binding a key replaces its value."""
        import structlog

        clear_context()
        bind_context(user_id="first")
        bind_context(user_id="second")

        assert structlog.contextvars.get_contextvars().get("user_id") == "second"  # nosec B101
        clear_context()

    def test_unbind_context(self):
        """Test unbinding specific context variables."""
        import structlog

        clear_context()
        bind_context(user_id="user123", conversation_id="conv456")
        unbind_context("user_id")

        bound = structlog.contextvars.get_contextvars()
        assert "user_id" not in bound  # nosec B101
        assert bound.get("conversation_id") == "conv456", \
            "unbinding one key must not remove the others"  # nosec B101
        clear_context()

    def test_clear_context(self):
        """Test clearing all context variables."""
        import structlog

        bind_context(user_id="user123", conversation_id="conv456")
        clear_context()

        assert structlog.contextvars.get_contextvars() == {}  # nosec B101
    
    def test_logging_levels(self):
        """Test all logging levels."""
        for level in ["DEBUG", "INFO", "WARN", "ERROR"]:
            configure_logging(log_level=level)
            logger = logging.getLogger()
            expected_level = getattr(logging, level if level != "WARN" else "WARNING")
            assert logger.level == expected_level  # nosec B101
