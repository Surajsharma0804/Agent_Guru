"""
Module: Agent_Guru.vision.utils.logging
Purpose: Logging setup utilities for the GuruVision system.

Provides a single entry-point, ``setup_logging``, that configures a named
logger with both a console (StreamHandler) and a rotating file handler
(RotatingFileHandler).  Log rotation is triggered when the file reaches
``max_size_mb`` megabytes; up to 5 backup files are kept.

Requirements: 17.1, 17.5, 17.6, 17.7
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

__all__ = ["setup_logging"]

_LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
_LOGGER_NAME = "guruvision"


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "Agent_Guru/vision/data/logs/guruvision.log",
    max_size_mb: int = 100,
) -> logging.Logger:
    """Configure and return the ``guruvision`` logger.

    The logger is configured with two handlers:

    * **StreamHandler** – writes to the console (stdout/stderr).
    * **RotatingFileHandler** – writes to *log_file*; rotates when the file
      reaches *max_size_mb* MB, keeping up to 5 backup files.

    Parent directories for *log_file* are created automatically if they do
    not already exist.

    Args:
        log_level: Logging level string (``"DEBUG"``, ``"INFO"``,
            ``"WARNING"``, ``"ERROR"``, or ``"CRITICAL"``).  Defaults to
            ``"INFO"``.  An unrecognised value falls back to ``"INFO"``.
        log_file: Path to the log file.  Defaults to
            ``"Agent_Guru/vision/data/logs/guruvision.log"``.
        max_size_mb: Maximum log-file size in megabytes before rotation.
            Defaults to ``100``.

    Returns:
        The configured :class:`logging.Logger` named ``"guruvision"``.

    Example::

        from Agent_Guru.vision.utils.logging import setup_logging

        logger = setup_logging(log_level="DEBUG", log_file="/tmp/gv.log")
        logger.info("GuruVision initialised")
    """
    numeric_level: int = getattr(logging, log_level.upper(), logging.INFO)

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(numeric_level)

    # Avoid adding duplicate handlers when called multiple times.
    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(_LOG_FORMAT)

    # --- Console handler ---
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(numeric_level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # --- Rotating file handler ---
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    max_bytes = max_size_mb * 1024 * 1024
    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_path),
        maxBytes=max_bytes,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
