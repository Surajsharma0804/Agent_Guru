"""Shared retry utilities — eliminates duplication across IoT, resilience, SDK.

Single source of truth for exponential backoff retry logic with jitter.
Time Complexity: O(n) where n = max_attempts
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Standard backoff schedule used across all modules
DEFAULT_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0)

# Jitter range: ±25% of the base delay to prevent thundering herd
_JITTER_FACTOR = 0.25


def _jittered_delay(base_delay: float) -> float:
    """Apply ±25% random jitter to a delay value.

    Prevents thundering herd when multiple tasks retry simultaneously.
    """
    if base_delay <= 0:
        return 0.0
    jitter = base_delay * _JITTER_FACTOR
    return base_delay + random.uniform(-jitter, jitter)  # noqa: S311


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    delays: tuple[float, ...] = DEFAULT_DELAYS,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    label: str = "operation",
) -> T:
    """Retry an async callable with exponential backoff and jitter.

    Jitter (±25%) is applied to each delay to prevent thundering herd
    when multiple concurrent tasks retry against the same resource.

    Args:
        fn: Async callable to retry.
        delays: Base sleep durations between attempts (len = max_retries).
        exceptions: Exception types that trigger a retry.
        label: Human-readable label for log messages.

    Returns:
        Result of the first successful call.

    Raises:
        Last exception if all attempts fail.

    """
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt, base_delay in enumerate([0.0, *delays]):
        if attempt > 0:
            delay = _jittered_delay(base_delay)
            logger.warning("%s: retry %d after %.1fs (base=%.1fs)", label, attempt, delay, base_delay)
            await asyncio.sleep(delay)
        try:
            return await fn()
        except exceptions as exc:
            last_exc = exc
            logger.debug("%s: attempt %d failed — %s", label, attempt + 1, exc)
    raise last_exc
