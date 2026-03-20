"""Shared retry utilities — eliminates duplication across IoT, resilience, SDK.

Single source of truth for exponential backoff retry logic.
Time Complexity: O(n) where n = max_attempts
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Standard backoff schedule used across all modules
DEFAULT_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0)


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    delays: tuple[float, ...] = DEFAULT_DELAYS,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    label: str = "operation",
) -> T:
    """Retry an async callable with exponential backoff.

    Args:
        fn: Async callable to retry.
        delays: Sleep durations between attempts (len = max_retries).
        exceptions: Exception types that trigger a retry.
        label: Human-readable label for log messages.

    Returns:
        Result of the first successful call.

    Raises:
        Last exception if all attempts fail.
    """
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt, delay in enumerate([0.0, *delays]):
        if attempt > 0:
            logger.warning("%s: retry %d after %.1fs", label, attempt, delay)
            await asyncio.sleep(delay)
        try:
            return await fn()
        except exceptions as exc:
            last_exc = exc
            logger.debug("%s: attempt %d failed — %s", label, attempt + 1, exc)
    raise last_exc
