"""
Module: agent_guru.platform.network.rate_limiter
Purpose: Token bucket rate limiting for network requests
Author: Agent Guru Team
Date: 2026-02-26

Performance Requirements:
- Time Complexity: O(1) for rate limit checks
- Space Complexity: O(1) per service
- Latency: <1ms for rate limit check
- Accuracy: >99% rate limit enforcement

Design Decisions:
- Token bucket algorithm for smooth rate limiting
- Per-service rate limiters for fine-grained control
- Async request queuing for graceful handling
- Thread-safe implementation with asyncio locks
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiter.

    Attributes:
        requests_per_minute: Maximum requests per minute
        requests_per_hour: Maximum requests per hour (optional)
        burst_size: Maximum burst size (tokens in bucket)
        queue_size: Maximum queued requests (0 = no queuing)
    """

    requests_per_minute: int = 60
    requests_per_hour: Optional[int] = None
    burst_size: Optional[int] = None
    queue_size: int = 100

    def __post_init__(self):
        """Validate configuration."""
        if self.requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")

        if self.requests_per_hour is not None and self.requests_per_hour <= 0:
            raise ValueError("requests_per_hour must be positive")

        if self.burst_size is None:
            # Default burst size is 2x rate per minute
            self.burst_size = self.requests_per_minute * 2

        if self.burst_size <= 0:
            raise ValueError("burst_size must be positive")

        if self.queue_size < 0:
            raise ValueError("queue_size must be non-negative")


@dataclass
class RateLimitStatus:
    """Current rate limit status.

    Attributes:
        remaining: Remaining requests in current window
        reset_time: When rate limit resets
        limit: Total limit per window
        service: Service name
        is_limited: Whether currently rate limited
    """

    remaining: int
    reset_time: datetime
    limit: int
    service: str
    is_limited: bool = False


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded and queuing is disabled."""

    def __init__(self, service: str, retry_after: float):
        self.service = service
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded for service '{service}'. "
            f"Retry after {retry_after:.1f} seconds."
        )


# Backward-compatible alias
RateLimitExceeded = RateLimitExceededError


class TokenBucket:
    """Token bucket rate limiter implementation.

    Time Complexity: O(1) for all operations
    Space Complexity: O(1)

    The token bucket algorithm allows for burst traffic while maintaining
    average rate limits. Tokens are added at a constant rate, and each
    request consumes one token.

    Example:
        >>> bucket = TokenBucket(capacity=100, refill_rate=10.0)
        >>> await bucket.acquire()  # Consumes 1 token
        >>> status = bucket.get_status()
        >>> print(f"Remaining: {status.remaining}")
    """

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        name: str = "default"
    ):
        """Initialize token bucket.

        Args:
            capacity: Maximum tokens in bucket (burst size)
            refill_rate: Tokens added per second
            name: Bucket name for logging
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.name = name

        # Current state
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.debug(
            f"TokenBucket '{name}' initialized",
            extra={
                "capacity": capacity,
                "refill_rate": refill_rate,
            }
        )

    def _refill(self) -> None:
        """Refill tokens based on elapsed time.

        Time Complexity: O(1)
        """
        now = time.monotonic()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    async def acquire(self, tokens: int = 1) -> bool:
        """Acquire tokens from bucket.

        Time Complexity: O(1)

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens acquired, False if insufficient tokens
        """
        async with self._lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False

    async def wait_for_token(self, timeout: Optional[float] = None) -> bool:
        """Wait until a token is available.

        Time Complexity: O(1) per check

        Args:
            timeout: Maximum wait time in seconds (None = wait forever)

        Returns:
            True if token acquired, False if timeout
        """
        start_time = time.monotonic()

        while True:
            if await self.acquire():
                return True

            # Check timeout
            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    return False

            # Calculate wait time until next token
            async with self._lock:
                self._refill()
                if self.tokens >= 1:
                    continue

                # Wait for next token
                tokens_needed = 1 - self.tokens
                wait_time = tokens_needed / self.refill_rate
                wait_time = min(wait_time, 0.1)  # Max 100ms wait

            await asyncio.sleep(wait_time)

    def get_remaining(self) -> int:
        """Get remaining tokens.

        Time Complexity: O(1)

        Returns:
            Number of available tokens
        """
        return int(self.tokens)

    def get_reset_time(self) -> datetime:
        """Get time when bucket will be full.

        Time Complexity: O(1)

        Returns:
            Datetime when bucket refills to capacity
        """
        tokens_needed = self.capacity - self.tokens
        seconds_to_full = tokens_needed / self.refill_rate
        return datetime.now() + timedelta(seconds=seconds_to_full)


class RateLimiter:
    """Per-service rate limiter with token bucket algorithm.

    Time Complexity: O(1) for rate limit checks
    Space Complexity: O(1) per service

    Features:
    - Token bucket algorithm for smooth rate limiting
    - Per-minute and per-hour limits
    - Request queuing for graceful handling
    - 429 error handling
    - Rate limit status reporting

    Example:
        >>> config = RateLimitConfig(requests_per_minute=60)
        >>> limiter = RateLimiter("api.example.com", config)
        >>> await limiter.acquire()  # Blocks if rate limited
        >>> status = limiter.get_status()
        >>> print(f"Remaining: {status.remaining}")
    """

    def __init__(self, service: str, config: RateLimitConfig):
        """Initialize rate limiter.

        Args:
            service: Service name (e.g., "api.example.com")
            config: Rate limit configuration
        """
        self.service = service
        self.config = config

        # Per-minute bucket
        self.minute_bucket = TokenBucket(
            capacity=config.burst_size,
            refill_rate=config.requests_per_minute / 60.0,  # tokens per second
            name=f"{service}_minute"
        )

        # Per-hour bucket (optional)
        self.hour_bucket: Optional[TokenBucket] = None
        if config.requests_per_hour is not None:
            self.hour_bucket = TokenBucket(
                capacity=config.requests_per_hour,
                refill_rate=config.requests_per_hour / 3600.0,  # tokens per second
                name=f"{service}_hour"
            )

        # Request queue
        self.queue: deque = deque(maxlen=config.queue_size)
        self._queue_lock = asyncio.Lock()

        logger.info(
            f"RateLimiter initialized for service '{service}'",
            extra={
                "requests_per_minute": config.requests_per_minute,
                "requests_per_hour": config.requests_per_hour,
                "burst_size": config.burst_size,
                "queue_size": config.queue_size,
            }
        )

    async def acquire(self, timeout: Optional[float] = None) -> None:
        """Acquire permission to make request.

        Time Complexity: O(1) average case

        Blocks until rate limit allows request or timeout expires.

        Args:
            timeout: Maximum wait time in seconds (None = wait forever)

        Raises:
            RateLimitExceeded: If rate limit exceeded and queuing disabled
            asyncio.TimeoutError: If timeout expires
        """
        start_time = time.monotonic()

        # Try to acquire from minute bucket
        if not await self.minute_bucket.acquire():
            # Rate limited - check if queuing enabled
            if self.config.queue_size == 0:
                retry_after = 60.0 / self.config.requests_per_minute
                raise RateLimitExceeded(self.service, retry_after)

            # Wait for token
            remaining_timeout = timeout
            if timeout is not None:
                elapsed = time.monotonic() - start_time
                remaining_timeout = max(0, timeout - elapsed)

            if not await self.minute_bucket.wait_for_token(remaining_timeout):
                raise asyncio.TimeoutError(
                    f"Rate limit timeout for service '{self.service}'"
                )

        # Check hour bucket if configured
        if self.hour_bucket is not None:
            if not await self.hour_bucket.acquire():
                # Hour limit exceeded
                if self.config.queue_size == 0:
                    retry_after = 3600.0 / self.config.requests_per_hour
                    raise RateLimitExceeded(self.service, retry_after)

                # Wait for token
                remaining_timeout = timeout
                if timeout is not None:
                    elapsed = time.monotonic() - start_time
                    remaining_timeout = max(0, timeout - elapsed)

                if not await self.hour_bucket.wait_for_token(remaining_timeout):
                    raise asyncio.TimeoutError(
                        f"Rate limit timeout for service '{self.service}'"
                    )

        logger.debug(
            f"Rate limit acquired for service '{self.service}'",
            extra={"service": self.service}
        )

    def get_status(self) -> RateLimitStatus:
        """Get current rate limit status.

        Time Complexity: O(1)

        Returns:
            Rate limit status
        """
        remaining = self.minute_bucket.get_remaining()
        reset_time = self.minute_bucket.get_reset_time()
        is_limited = remaining == 0

        return RateLimitStatus(
            remaining=remaining,
            reset_time=reset_time,
            limit=self.config.requests_per_minute,
            service=self.service,
            is_limited=is_limited,
        )

    def reset(self) -> None:
        """Reset rate limiter (for testing).

        Time Complexity: O(1)
        """
        self.minute_bucket.tokens = float(self.minute_bucket.capacity)
        if self.hour_bucket is not None:
            self.hour_bucket.tokens = float(self.hour_bucket.capacity)

        logger.info(f"Rate limiter reset for service '{self.service}'")


class RateLimiterManager:
    """Manager for multiple per-service rate limiters.

    Time Complexity: O(1) for rate limiter lookup
    Space Complexity: O(n) where n is number of services

    Features:
    - Per-service rate limiter management
    - Default rate limit configuration
    - Service-specific overrides
    - Rate limit status reporting

    Example:
        >>> manager = RateLimiterManager()
        >>> manager.configure_service(
        ...     "api.example.com",
        ...     RateLimitConfig(requests_per_minute=100)
        ... )
        >>> await manager.acquire("api.example.com")
        >>> status = manager.get_status("api.example.com")
    """

    def __init__(self, default_config: Optional[RateLimitConfig] = None):
        """Initialize rate limiter manager.

        Args:
            default_config: Default configuration for all services
        """
        self.default_config = default_config or RateLimitConfig()
        self.limiters: dict[str, RateLimiter] = {}
        self._lock = asyncio.Lock()

        logger.info(
            "RateLimiterManager initialized",
            extra={
                "default_requests_per_minute": self.default_config.requests_per_minute,
            }
        )

    def configure_service(
        self,
        service: str,
        config: RateLimitConfig
    ) -> None:
        """Configure rate limiter for specific service.

        Time Complexity: O(1)

        Args:
            service: Service name
            config: Rate limit configuration
        """
        self.limiters[service] = RateLimiter(service, config)
        logger.info(f"Rate limiter configured for service '{service}'")

    def _get_limiter(self, service: str) -> RateLimiter:
        """Get or create rate limiter for service.

        Time Complexity: O(1)

        Args:
            service: Service name

        Returns:
            Rate limiter for service
        """
        if service not in self.limiters:
            self.limiters[service] = RateLimiter(service, self.default_config)

        return self.limiters[service]

    async def acquire(
        self,
        service: str,
        timeout: Optional[float] = None
    ) -> None:
        """Acquire permission to make request to service.

        Time Complexity: O(1) average case

        Args:
            service: Service name
            timeout: Maximum wait time in seconds

        Raises:
            RateLimitExceeded: If rate limit exceeded
            asyncio.TimeoutError: If timeout expires
        """
        limiter = self._get_limiter(service)
        await limiter.acquire(timeout)

    def get_status(self, service: str) -> RateLimitStatus:
        """Get rate limit status for service.

        Time Complexity: O(1)

        Args:
            service: Service name

        Returns:
            Rate limit status
        """
        limiter = self._get_limiter(service)
        return limiter.get_status()

    def get_all_statuses(self) -> dict[str, RateLimitStatus]:
        """Get rate limit status for all services.

        Time Complexity: O(n) where n is number of services

        Returns:
            Dictionary mapping service names to rate limit status
        """
        return {
            service: limiter.get_status()
            for service, limiter in self.limiters.items()
        }

    def reset_service(self, service: str) -> None:
        """Reset rate limiter for service (for testing).

        Time Complexity: O(1)

        Args:
            service: Service name
        """
        if service in self.limiters:
            self.limiters[service].reset()

    def reset_all(self) -> None:
        """Reset all rate limiters (for testing).

        Time Complexity: O(n) where n is number of services
        """
        for limiter in self.limiters.values():
            limiter.reset()
