"""
Utility functions for Goal Manager.

This module provides reusable utility functions for the Goal Manager system,
including retry logic with exponential backoff for handling transient failures.

Functions:
    retry_with_backoff: Async retry utility with exponential backoff

Usage:
    from Agent_Guru.goal_manager.utils import retry_with_backoff

    # Retry an async operation
    result = await retry_with_backoff(
        operation=lambda: llm_runtime.generate(prompt),
        max_retries=3,
        base_delay=1.0
    )
"""

import asyncio
from typing import Callable, TypeVar, Any
from Agent_Guru.goal_manager.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


async def retry_with_backoff(
    operation: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 1.0
) -> Any:
    """
    Retry an async operation with exponential backoff.

    This function implements exponential backoff retry logic for handling
    transient failures in external service calls (LLM Runtime, Agent
    Orchestration, etc.). The delay between retries increases exponentially:
    base_delay, base_delay * 2, base_delay * 4, etc.

    Time Complexity: O(1) per retry attempt
    Space Complexity: O(1)

    Args:
        operation: Async callable to retry (should take no arguments)
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 1.0)

    Returns:
        Result of the operation if successful

    Raises:
        Exception: The last exception raised by the operation after all retries
                  are exhausted

    Example:
        # Retry LLM call with default settings (3 retries, 1s base delay)
        response = await retry_with_backoff(
            operation=lambda: llm_runtime.generate(prompt)
        )

        # Retry with custom settings (5 retries, 2s base delay)
        result = await retry_with_backoff(
            operation=lambda: agent_orchestration.create_task(task),
            max_retries=5,
            base_delay=2.0
        )

    Retry Schedule (with default base_delay=1.0):
        - Attempt 1: Immediate
        - Attempt 2: After 1.0s delay (base_delay * 2^0)
        - Attempt 3: After 2.0s delay (base_delay * 2^1)
        - Attempt 4: After 4.0s delay (base_delay * 2^2)

    Validates: Requirements 11.1, 11.4, 11.5
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            # Log retry attempt
            if attempt > 0:
                logger.info(
                    "retry_attempt",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    operation=operation.__name__ if hasattr(operation, '__name__') else str(operation)
                )

            # Execute operation
            result = await operation()

            # Log success if this was a retry
            if attempt > 0:
                logger.info(
                    "retry_succeeded",
                    attempt=attempt + 1,
                    operation=operation.__name__ if hasattr(operation, '__name__') else str(operation)
                )

            return result

        except Exception as e:
            last_exception = e

            # Log the failure
            logger.warning(
                "operation_failed",
                attempt=attempt + 1,
                max_retries=max_retries,
                error=str(e),
                error_type=type(e).__name__,
                operation=operation.__name__ if hasattr(operation, '__name__') else str(operation)
            )

            # If this was the last attempt, raise the exception
            if attempt == max_retries - 1:
                logger.error(
                    "retry_exhausted",
                    max_retries=max_retries,
                    error=str(e),
                    error_type=type(e).__name__,
                    operation=operation.__name__ if hasattr(operation, '__name__') else str(operation)
                )
                raise

            # Calculate exponential backoff delay
            delay = base_delay * (2 ** attempt)

            logger.info(
                "retry_backoff",
                attempt=attempt + 1,
                delay_seconds=delay,
                next_attempt=attempt + 2
            )

            # Wait before next retry
            await asyncio.sleep(delay)

    # This should never be reached, but included for type safety
    if last_exception:
        raise last_exception
