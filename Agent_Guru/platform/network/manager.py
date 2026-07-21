"""Module: agent_guru.platform.network.manager
Purpose: Robust HTTP/HTTPS client with enterprise features
Author: Agent Guru Team
Date: 2026-02-26.

Performance Requirements:
- Time Complexity: O(1) for request initiation
- Space Complexity: O(1) per request (streaming for large responses)
- Latency: <100ms overhead (95th percentile)
- Throughput: 1000+ requests/second

Design Decisions:
- Use aiohttp for async HTTP operations (10x faster than requests)
- Connection pooling for reuse (avoid TCP handshake overhead)
- SSL/TLS validation enforced by default (security first)
- Structured logging for all operations (audit trail)
"""

import asyncio
import builtins
import logging
import ssl
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
import certifi

from .connection_pool import (
    ConnectionPoolConfig,
    ConnectionPoolManager,
    ConnectionStats,
    PoolStatistics,
)
from .rate_limiter import (
    RateLimitConfig,
    RateLimiterManager,
    RateLimitExceeded,
    RateLimitStatus,
)
from .response_cache import CacheStatistics, ResponseCache
from .webhook import (
    WebhookConfig,
    WebhookEvent,
    WebhookManager,
)

# Configure structured logging
logger = logging.getLogger(__name__)

class HttpMethod(str, Enum):
    """HTTP methods supported by NetworkManager."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"

@dataclass
class NetworkConfig:
    """Configuration for NetworkManager.

    Attributes:
        default_timeout: Default request timeout in seconds (30s recommended)
        max_connections: Maximum connections per host (100 recommended)
        max_connections_total: Total maximum connections (1000 recommended)
        verify_ssl: Whether to verify SSL/TLS certificates (True in production)
        user_agent: User agent string for requests
        max_retries: Maximum retry attempts for transient failures
        retry_delay: Initial retry delay in seconds (exponential backoff)
        enable_rate_limiting: Whether to enable rate limiting
        default_rate_limit: Default rate limit configuration
        enable_caching: Whether to enable response caching
        cache_max_size: Maximum cache size in bytes (100MB recommended)
        enable_connection_pooling: Whether to enable advanced connection pooling
        connection_pool_config: Connection pool configuration
        enable_webhooks: Whether to enable webhook support
        webhook_config: Webhook configuration

    """

    default_timeout: float = 30.0
    max_connections: int = 100
    max_connections_total: int = 1000
    verify_ssl: bool = True
    user_agent: str = "Agent-Guru/1.0"
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_rate_limiting: bool = True
    default_rate_limit: RateLimitConfig | None = None
    enable_caching: bool = True
    cache_max_size: int = 100 * 1024 * 1024  # 100MB
    enable_connection_pooling: bool = True
    connection_pool_config: ConnectionPoolConfig | None = None
    enable_webhooks: bool = True
    webhook_config: WebhookConfig | None = None

@dataclass
class HttpResponse:
    """HTTP response data.

    Attributes:
        status_code: HTTP status code (200, 404, 500, etc.)
        headers: Response headers
        body: Response body as bytes
        response_time: Request duration in seconds
        from_cache: Whether response came from cache
        url: Final URL after redirects
        method: HTTP method used

    """

    status_code: int
    headers: dict[str, str]
    body: bytes
    response_time: float
    from_cache: bool
    url: str
    method: str

    @property
    def text(self) -> str:
        """Decode body as UTF-8 text."""
        return self.body.decode("utf-8", errors="replace")

    @property
    def json(self) -> Any:
        """Parse body as JSON."""
        import json

        return json.loads(self.text)

    @property
    def is_success(self) -> bool:
        """Check if status code indicates success (2xx)."""
        return 200 <= self.status_code < 300

    @property
    def is_client_error(self) -> bool:
        """Check if status code indicates client error (4xx)."""
        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        """Check if status code indicates server error (5xx)."""
        return 500 <= self.status_code < 600

@dataclass
class DownloadResult:
    """Result of file download operation.

    Attributes:
        url: Source URL
        destination: Local file path
        total_bytes: Total bytes downloaded
        duration: Download duration in seconds
        average_speed: Average download speed in bytes/second
        success: Whether download completed successfully
        error: Error message if download failed

    """

    url: str
    destination: str
    total_bytes: int
    duration: float
    average_speed: float
    success: bool
    error: str | None = None

@dataclass
class UploadResult:
    """Result of file upload operation.

    Attributes:
        url: Destination URL
        source: Local file path
        total_bytes: Total bytes uploaded
        duration: Upload duration in seconds
        average_speed: Average upload speed in bytes/second
        success: Whether upload completed successfully
        response_status: HTTP response status code
        error: Error message if upload failed

    """

    url: str
    source: str
    total_bytes: int
    duration: float
    average_speed: float
    success: bool
    response_status: int | None = None
    error: str | None = None

    @dataclass
    class DownloadResult:
        """Result of file download operation.

        Attributes:
            url: Source URL
            destination: Local file path
            total_bytes: Total bytes downloaded
            duration: Download duration in seconds
            average_speed: Average download speed in bytes/second
            success: Whether download completed successfully
            error: Error message if download failed

        """

        url: str
        destination: str
        total_bytes: int
        duration: float
        average_speed: float
        success: bool
        error: str | None = None

    @dataclass
    class UploadResult:
        """Result of file upload operation.

        Attributes:
            url: Destination URL
            source: Local file path
            total_bytes: Total bytes uploaded
            duration: Upload duration in seconds
            average_speed: Average upload speed in bytes/second
            success: bool
            response_status: HTTP response status code
            error: Error message if upload failed

        """

        url: str
        source: str
        total_bytes: int
        duration: float
        average_speed: float
        success: bool
        response_status: int | None = None
        error: str | None = None

# Exception hierarchy

class NetworkError(Exception):
    """Base exception for network operations."""

class SSLValidationError(NetworkError):
    """Raised when SSL/TLS certificate validation fails."""

class TimeoutError(NetworkError):
    """Raised when request times out."""

class ConnectionError(NetworkError):
    """Raised when connection fails."""

class RateLimitError(NetworkError):
    """Raised when rate limit is exceeded (429 status code)."""

    def __init__(self, service: str, retry_after: float, status_code: int = 429) -> None:
        self.service = service
        self.retry_after = retry_after
        self.status_code = status_code
        super().__init__(
            f"Rate limit exceeded for service '{service}'. "
            f"Retry after {retry_after:.1f} seconds. (HTTP {status_code})",
        )

class NetworkManager:
    """Advanced network manager with enterprise features.

    Time Complexity: O(1) per request initiation
    Space Complexity: O(1) per request (streaming for large responses)

    Features:
    - All HTTP methods (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)
    - SSL/TLS certificate validation
    - Custom headers and request bodies
    - Configurable timeouts
    - Request/response logging
    - Connection pooling
    - Automatic retry with exponential backoff

    Example:
        >>> config = NetworkConfig(default_timeout=30.0)
        >>> manager = NetworkManager(config)
        >>> await manager.start()
        >>> response = await manager.http_request(
        ...     HttpMethod.GET,
        ...     "https://api.example.com/data"
        ... )
        >>> print(f"Status: {response.status_code}")
        >>> await manager.close()

    """

    def __init__(self, config: NetworkConfig) -> None:
        """Initialize network manager.

        Args:
            config: Network configuration

        """
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        self._ssl_context: ssl.SSLContext | None = None
        self._connector: aiohttp.TCPConnector | None = None

        # Initialize connection pool manager
        self._pool_manager: ConnectionPoolManager | None = None
        if config.enable_connection_pooling:
            pool_config = config.connection_pool_config or ConnectionPoolConfig(
                max_connections_per_host=config.max_connections,
                max_connections_total=config.max_connections_total,
            )
            self._pool_manager = ConnectionPoolManager(pool_config)

        # Initialize rate limiter manager
        self._rate_limiter: RateLimiterManager | None = None
        if config.enable_rate_limiting:
            default_rate_config = config.default_rate_limit or RateLimitConfig()
            self._rate_limiter = RateLimiterManager(default_rate_config)

        # Initialize response cache
        self._cache: ResponseCache | None = None
        if config.enable_caching:
            self._cache = ResponseCache(max_size=config.cache_max_size)

        # Initialize webhook manager
        self._webhook_manager: WebhookManager | None = None
        if config.enable_webhooks:
            webhook_config = config.webhook_config or WebhookConfig()
            self._webhook_manager = WebhookManager(webhook_config)

        logger.info(
            "NetworkManager initialized",
            extra={
                "timeout": config.default_timeout,
                "verify_ssl": config.verify_ssl,
                "max_connections": config.max_connections,
                "rate_limiting_enabled": config.enable_rate_limiting,
                "caching_enabled": config.enable_caching,
                "cache_max_size_mb": config.cache_max_size / (1024 * 1024)
                if config.enable_caching
                else 0,
                "connection_pooling_enabled": config.enable_connection_pooling,
                "webhooks_enabled": config.enable_webhooks,
            },
        )

    async def start(self) -> None:
        """Start network manager and create session.

        Must be called before making requests.
        """
        if self._session is not None:
            logger.warning("NetworkManager already started")
            return

        # Create SSL context
        if self.config.verify_ssl:
            self._ssl_context = ssl.create_default_context(cafile=certifi.where())
            self._ssl_context.check_hostname = True
            self._ssl_context.verify_mode = ssl.CERT_REQUIRED
        else:
            self._ssl_context = False  # Disable SSL verification (not recommended)
            logger.warning("SSL verification disabled - not recommended for production")

        # Create connector with connection pooling
        if self._pool_manager is not None:
            # Use advanced connection pool manager
            self._connector = self._pool_manager.create_connector(self._ssl_context)
            await self._pool_manager.start_cleanup()
        else:
            # Use basic connector
            self._connector = aiohttp.TCPConnector(
                limit=self.config.max_connections_total,
                limit_per_host=self.config.max_connections,
                ssl=self._ssl_context,
                ttl_dns_cache=300,  # Cache DNS for 5 minutes
                enable_cleanup_closed=True,
            )

        # Create session
        timeout = aiohttp.ClientTimeout(total=self.config.default_timeout)
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            timeout=timeout,
            headers={"User-Agent": self.config.user_agent},
        )

        logger.info("NetworkManager started successfully")

    async def close(self) -> None:
        """Close network manager and cleanup resources.

        Should be called when done with network operations.
        """
        if self._session is not None:
            await self._session.close()
            self._session = None
            logger.info("NetworkManager closed")

        if self._pool_manager is not None:
            await self._pool_manager.close()
            self._pool_manager = None

        if self._webhook_manager is not None:
            await self._webhook_manager.close()
            self._webhook_manager = None

    async def __aenter__(self):
        """Context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

    def configure_rate_limit(self, service: str, config: RateLimitConfig) -> None:
        """Configure rate limiter for specific service.

        Args:
            service: Service name (e.g., "api.example.com")
            config: Rate limit configuration

        Example:
            >>> manager.configure_rate_limit(
            ...     "api.example.com",
            ...     RateLimitConfig(requests_per_minute=100, requests_per_hour=1000)
            ... )

        """
        if self._rate_limiter is None:
            logger.warning("Rate limiting not enabled - configure_rate_limit ignored")
            return

        self._rate_limiter.configure_service(service, config)
        logger.info("Rate limit configured for service '%s'", service)

    def get_rate_limit_status(self, service: str) -> RateLimitStatus | None:
        """Get current rate limit status for service.

        Args:
            service: Service name

        Returns:
            Rate limit status or None if rate limiting disabled

        Example:
            >>> status = manager.get_rate_limit_status("api.example.com")
            >>> print(f"Remaining: {status.remaining}/{status.limit}")
            >>> print(f"Resets at: {status.reset_time}")

        """
        if self._rate_limiter is None:
            return None

        return self._rate_limiter.get_status(service)

    def get_all_rate_limit_statuses(self) -> dict[str, RateLimitStatus]:
        """Get rate limit status for all services.

        Returns:
            Dictionary mapping service names to rate limit status

        Example:
            >>> statuses = manager.get_all_rate_limit_statuses()
            >>> for service, status in statuses.items():
            ...     print(f"{service}: {status.remaining}/{status.limit}")

        """
        if self._rate_limiter is None:
            return {}

        return self._rate_limiter.get_all_statuses()

    def get_cache_statistics(self) -> CacheStatistics | None:
        """Get cache statistics.

        Returns:
            Cache statistics or None if caching disabled

        Example:
            >>> stats = manager.get_cache_statistics()
            >>> if stats:
            ...     print(f"Hit rate: {stats.hit_rate:.2%}")
            ...     print(f"Size: {stats.total_size / (1024 * 1024):.2f} MB")
            ...     print(f"Entries: {stats.entry_count}")

        """
        if self._cache is None:
            return None

        return self._cache.get_statistics()

    async def invalidate_cache(self, url_pattern: str | None = None) -> int:
        """Invalidate cache entries matching URL pattern.

        Args:
            url_pattern: URL pattern to match (None = invalidate all)

        Returns:
            Number of entries invalidated

        Example:
            >>> # Invalidate all cache entries
            >>> count = await manager.invalidate_cache()
            >>> print(f"Invalidated {count} entries")
            >>>
            >>> # Invalidate specific API
            >>> count = await manager.invalidate_cache("api.example.com")
            >>> print(f"Invalidated {count} entries for api.example.com")

        """
        if self._cache is None:
            return 0

        return await self._cache.invalidate(url_pattern)

    async def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed

        Example:
            >>> count = await manager.cleanup_expired_cache()
            >>> print(f"Removed {count} expired entries")

        """
        if self._cache is None:
            return 0

        return await self._cache.cleanup_expired()

    def reset_cache_statistics(self) -> None:
        """Reset cache statistics (keep cached entries).

        Example:
            >>> manager.reset_cache_statistics()
            >>> stats = manager.get_cache_statistics()
            >>> assert stats.hits == 0 and stats.misses == 0

        """
        if self._cache is not None:
            self._cache.reset_statistics()

    async def get_connection_pool_stats(self) -> PoolStatistics | None:
        """Get connection pool statistics.

        Returns:
            Pool statistics or None if connection pooling disabled

        Example:
            >>> stats = await manager.get_connection_pool_stats()
            >>> if stats:
            ...     print(f"Total hosts: {stats.total_hosts}")
            ...     print(f"Average reuse rate: {stats.average_reuse_rate:.2%}")
            ...     print(f"Total connections: {stats.total_created}")

        """
        if self._pool_manager is None:
            return None

        return await self._pool_manager.get_all_stats()

    async def get_host_connection_stats(self, host: str) -> ConnectionStats | None:
        """Get connection statistics for specific host.

        Args:
            host: Host name

        Returns:
            Connection statistics or None if not found or pooling disabled

        Example:
            >>> stats = await manager.get_host_connection_stats("api.example.com")
            >>> if stats:
            ...     print(f"Reuse rate: {stats.reuse_rate:.2%}")
            ...     print(f"Active connections: {stats.active_connections}")

        """
        if self._pool_manager is None:
            return None

        return await self._pool_manager.get_host_stats(host)

    async def reset_connection_pool_stats(self) -> None:
        """Reset connection pool statistics.

        Example:
            >>> await manager.reset_connection_pool_stats()

        """
        if self._pool_manager is not None:
            await self._pool_manager.reset_stats()

    def _extract_service_name(self, url: str) -> str:
        """Extract service name from URL.

        Args:
            url: Request URL

        Returns:
            Service name (hostname)

        """
        parsed = urlparse(url)
        return parsed.netloc or "unknown"

    async def http_request(
        self,
        method: HttpMethod,
        url: str,
        headers: dict[str, str] | None = None,
        body: bytes | str | dict[str, Any] | None = None,
        timeout: float | None = None,
        params: dict[str, str] | None = None,
        use_cache: bool = True,
    ) -> HttpResponse:
        """Execute HTTP request with retry logic and caching.

        Time Complexity: O(1) for request initiation
        Space Complexity: O(n) where n is response size

        Args:
            method: HTTP method
            url: Request URL
            headers: Custom headers (merged with default headers)
            body: Request body (bytes, str, or dict for JSON)
            timeout: Request timeout in seconds (overrides default)
            params: Query parameters
            use_cache: Whether to use response cache (default: True)

        Returns:
            HTTP response

        Raises:
            NetworkError: If request fails after retries
            SSLValidationError: If SSL certificate validation fails
            TimeoutError: If request times out
            ConnectionError: If connection fails
            ValueError: If URL or method is invalid

        """
        if self._session is None:
            msg = "NetworkManager not started - call start() first"
            raise NetworkError(msg)

        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            msg = f"Invalid URL: {url}"
            raise ValueError(msg)

        # Check cache for GET requests
        cached = await self._check_cache(method, url, headers, use_cache)
        if cached is not None:
            return cached

        # Rate limiting
        service = self._extract_service_name(url)
        await self._acquire_rate_limit(service, timeout)

        # Prepare request
        request_timeout = timeout if timeout is not None else self.config.default_timeout
        request_headers = headers.copy() if headers else {}
        request_body = self._encode_body(body, request_headers)

        # Retry loop
        return await self._execute_with_retries(
            method, url, request_headers, request_body,
            params, request_timeout, service, use_cache,
        )

    # ------------------------------------------------------------------
    # http_request helpers (extracted for complexity reduction)
    # ------------------------------------------------------------------

    async def _check_cache(
        self, method: HttpMethod, url: str,
        headers: dict[str, str] | None, use_cache: bool,
    ) -> HttpResponse | None:
        """Check cache for GET requests."""
        if not (use_cache and method == HttpMethod.GET and self._cache is not None):
            return None
        cached = await self._cache.get(url, method.value, headers)
        if cached is None:
            return None
        return HttpResponse(
            status_code=cached.status_code,
            headers=cached.headers,
            body=cached.body,
            response_time=0.0,
            from_cache=True,
            url=cached.url,
            method=cached.method,
        )

    async def _acquire_rate_limit(self, service: str, timeout: float | None) -> None:
        """Acquire rate limit slot, raising RateLimitError if exceeded."""
        if self._rate_limiter is None:
            return
        try:
            await self._rate_limiter.acquire(service, timeout=timeout)
        except RateLimitExceeded as e:
            logger.exception(
                "Rate limit exceeded",
                extra={"service": service, "retry_after": e.retry_after},
            )
            raise RateLimitError(service, e.retry_after) from e

    @staticmethod
    def _encode_body(
        body: bytes | str | dict[str, Any] | None,
        request_headers: dict[str, str],
    ) -> bytes | None:
        """Encode request body to bytes."""
        if body is None:
            return None
        if isinstance(body, dict):
            import json
            request_headers.setdefault("Content-Type", "application/json")
            return json.dumps(body).encode("utf-8")
        if isinstance(body, str):
            return body.encode("utf-8")
        return body

    async def _execute_with_retries(
        self,
        method: HttpMethod,
        url: str,
        request_headers: dict[str, str],
        request_body: bytes | None,
        params: dict[str, str] | None,
        request_timeout: float,
        service: str,
        use_cache: bool,
    ) -> HttpResponse:
        """Execute HTTP request with exponential backoff retries."""
        last_exception = None
        for attempt in range(self.config.max_retries):
            start_time = time.perf_counter()

            try:
                logger.debug(
                    "HTTP request",
                    extra={
                        "method": method.value, "url": url,
                        "attempt": attempt + 1, "timeout": request_timeout,
                    },
                )

                async with self._session.request(
                    method=method.value,
                    url=url,
                    headers=request_headers,
                    data=request_body,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=request_timeout),
                    allow_redirects=True,
                ) as response:
                    response_body = await response.read()
                    response_time = time.perf_counter() - start_time

                    if self._pool_manager is not None:
                        await self._pool_manager.record_connection_activity(
                            service, is_new=(attempt == 0), is_reused=(attempt > 0),
                        )

                    http_response = HttpResponse(
                        status_code=response.status,
                        headers=dict(response.headers),
                        body=response_body,
                        response_time=response_time,
                        from_cache=False,
                        url=str(response.url),
                        method=method.value,
                    )

                    if response.status == 429:
                        retry_after = float(response.headers.get("Retry-After", 60))
                        logger.warning(
                            "Server returned 429 Rate Limit",
                            extra={"service": service, "retry_after": retry_after, "url": url},
                        )
                        raise RateLimitError(service, retry_after, status_code=429)

                    # Cache successful GET responses
                    if (
                        use_cache
                        and method == HttpMethod.GET
                        and self._cache is not None
                        and 200 <= response.status < 300
                    ):
                        await self._cache.set(
                            url=str(response.url),
                            status_code=response.status,
                            headers=dict(response.headers),
                            body=response_body,
                            method=method.value,
                        )

                    logger.info(
                        "HTTP response",
                        extra={
                            "method": method.value, "url": url,
                            "status_code": response.status,
                            "response_time": response_time,
                            "body_size": len(response_body),
                            "from_cache": False,
                        },
                    )

                    return http_response

            except builtins.TimeoutError as e:
                last_exception = TimeoutError(f"Request timed out after {request_timeout}s: {url}")
                logger.exception(
                    "Request timeout",
                    extra={
                        "method": method.value, "url": url,
                        "timeout": request_timeout, "attempt": attempt + 1,
                    },
                )
                logger.exception(
                    "SSL validation failed",
                    extra={"method": method.value, "url": url, "error": str(e)},
                )
                msg = f"SSL certificate validation failed: {url}"
                raise SSLValidationError(msg) from e

            # Exponential backoff before retry
            if attempt < self.config.max_retries - 1:
                delay = self.config.retry_delay * (2**attempt)
                logger.debug("Retrying in %ss...", delay)
                await asyncio.sleep(delay)

        logger.error(
            "Request failed after all retries",
            extra={"method": method.value, "url": url, "max_retries": self.config.max_retries},
        )
        raise last_exception or NetworkError(f"Request failed: {url}")

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        timeout: float | None = None,
        use_cache: bool = True,
    ) -> HttpResponse:
        """Execute GET request.

        Args:
            url: Request URL
            headers: Custom headers
            params: Query parameters
            timeout: Request timeout in seconds
            use_cache: Whether to use response cache (default: True)

        Returns:
            HTTP response

        """
        return await self.http_request(
            HttpMethod.GET,
            url,
            headers=headers,
            params=params,
            timeout=timeout,
            use_cache=use_cache,
        )

    async def post(
        self,
        url: str,
        body: bytes | str | dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """Execute POST request.

        Args:
            url: Request URL
            body: Request body
            headers: Custom headers
            params: Query parameters
            timeout: Request timeout in seconds

        Returns:
            HTTP response

        """
        return await self.http_request(
            HttpMethod.POST,
            url,
            headers=headers,
            body=body,
            params=params,
            timeout=timeout,
        )

    async def put(
        self,
        url: str,
        body: bytes | str | dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """Execute PUT request.

        Args:
            url: Request URL
            body: Request body
            headers: Custom headers
            params: Query parameters
            timeout: Request timeout in seconds

        Returns:
            HTTP response

        """
        return await self.http_request(
            HttpMethod.PUT,
            url,
            headers=headers,
            body=body,
            params=params,
            timeout=timeout,
        )

    async def delete(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """Execute DELETE request.

        Args:
            url: Request URL
            headers: Custom headers
            params: Query parameters
            timeout: Request timeout in seconds

        Returns:
            HTTP response

        """
        return await self.http_request(
            HttpMethod.DELETE,
            url,
            headers=headers,
            params=params,
            timeout=timeout,
        )

    async def patch(
        self,
        url: str,
        body: bytes | str | dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """Execute PATCH request.

        Args:
            url: Request URL
            body: Request body
            headers: Custom headers
            params: Query parameters
            timeout: Request timeout in seconds

        Returns:
            HTTP response

        """
        return await self.http_request(
            HttpMethod.PATCH,
            url,
            headers=headers,
            body=body,
            params=params,
            timeout=timeout,
        )

    async def head(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """Execute HEAD request.

        Args:
            url: Request URL
            headers: Custom headers
            params: Query parameters
            timeout: Request timeout in seconds

        Returns:
            HTTP response (body will be empty)

        """
        return await self.http_request(
            HttpMethod.HEAD,
            url,
            headers=headers,
            params=params,
            timeout=timeout,
        )

    async def options(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """Execute OPTIONS request.

        Args:
            url: Request URL
            headers: Custom headers
            params: Query parameters
            timeout: Request timeout in seconds

        Returns:
            HTTP response

        """
        return await self.http_request(
            HttpMethod.OPTIONS,
            url,
            headers=headers,
            params=params,
            timeout=timeout,
        )

    # Streaming methods

    async def stream_response(
        self,
        method: HttpMethod,
        url: str,
        headers: dict[str, str] | None = None,
        body: bytes | str | dict[str, Any] | None = None,
        timeout: float | None = None,
        params: dict[str, str] | None = None,
        chunk_size: int = 8192,
    ) -> AsyncIterator[bytes]:
        """Stream HTTP response in chunks.

        Time Complexity: O(1) per chunk
        Space Complexity: O(chunk_size) - constant memory usage

        Args:
            method: HTTP method
            url: Request URL
            headers: Custom headers
            body: Request body
            timeout: Request timeout in seconds
            params: Query parameters
            chunk_size: Size of each chunk in bytes (default: 8KB)

        Yields:
            Response body chunks

        Raises:
            NetworkError: If request fails
            SSLValidationError: If SSL certificate validation fails
            TimeoutError: If request times out
            ConnectionError: If connection fails

        Example:
            >>> async for chunk in manager.stream_response(
            ...     HttpMethod.GET,
            ...     "https://example.com/large-file.zip"
            ... ):
            ...     process_chunk(chunk)

        """
        if self._session is None:
            msg = "NetworkManager not started - call start() first"
            raise NetworkError(msg)

        # Validate URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            msg = f"Invalid URL: {url}"
            raise ValueError(msg)

        # Extract service name for rate limiting
        service = self._extract_service_name(url)

        # Check rate limit
        if self._rate_limiter is not None:
            try:
                await self._rate_limiter.acquire(service, timeout=timeout)
            except RateLimitExceeded as e:
                logger.exception(
                    "Rate limit exceeded",
                    extra={
                        "service": service,
                        "retry_after": e.retry_after,
                    },
                )
                raise RateLimitError(service, e.retry_after) from e
        # Prepare request
        request_timeout = timeout if timeout is not None else self.config.default_timeout
        request_headers = headers.copy() if headers else {}

        # Handle body encoding
        request_body = None
        if body is not None:
            if isinstance(body, dict):
                import json

                request_body = json.dumps(body).encode("utf-8")
                request_headers.setdefault("Content-Type", "application/json")
            elif isinstance(body, str):
                request_body = body.encode("utf-8")
            else:
                request_body = body

        # Log request
        logger.debug(
            "HTTP streaming request",
            extra={
                "method": method.value,
                "url": url,
                "chunk_size": chunk_size,
                "timeout": request_timeout,
            },
        )

        try:
            # Execute streaming request
            async with self._session.request(
                method=method.value,
                url=url,
                headers=request_headers,
                data=request_body,
                params=params,
                timeout=aiohttp.ClientTimeout(total=request_timeout),
                allow_redirects=True,
            ) as response:
                # Check status code
                if response.status >= 400:
                    error_body = await response.read()
                    msg = f"HTTP {response.status}: {error_body.decode('utf-8', errors='replace')}"
                    raise NetworkError(
                        msg,
                    )

                # Stream response chunks
                total_bytes = 0
                async for chunk in response.content.iter_chunked(chunk_size):
                    total_bytes += len(chunk)
                    yield chunk

                logger.info(
                    "HTTP streaming response complete",
                    extra={
                        "method": method.value,
                        "url": url,
                        "status_code": response.status,
                        "total_bytes": total_bytes,
                    },
                )

        except builtins.TimeoutError as e:
            logger.exception(
                "Streaming request timeout",
                extra={
                    "method": method.value,
                    "url": url,
                    "timeout": request_timeout,
                },
            )
            msg = f"Request timed out after {request_timeout}s: {url}"
            raise TimeoutError(msg) from e

    async def download_file(
        self,
        url: str,
        destination: Path,
        progress_callback: Callable[[int, int], None] | None = None,
        chunk_size: int = 8192,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
    ) -> DownloadResult:
        """Download file with progress tracking.

        Time Complexity: O(n) where n is file size
        Space Complexity: O(chunk_size) - constant memory usage

        Args:
            url: File URL
            destination: Local file path
            progress_callback: Progress callback (bytes_downloaded, total_bytes)
            chunk_size: Size of each chunk in bytes (default: 8KB)
            timeout: Request timeout in seconds
            headers: Custom headers

        Returns:
            Download result with statistics

        Example:
            >>> def progress(downloaded, total):
            ...     percent = (downloaded / total) * 100 if total > 0 else 0
            ...     print(f"Downloaded: {percent:.1f}%")
            >>>
            >>> result = await manager.download_file(
            ...     url="https://example.com/large-file.zip",
            ...     destination=Path("/tmp/large-file.zip"),
            ...     progress_callback=progress
            ... )
            >>> print(f"Downloaded {result.total_bytes} bytes in {result.duration:.2f}s")
            >>> print(f"Average speed: {result.average_speed / 1024 / 1024:.2f} MB/s")

        """
        start_time = time.perf_counter()
        total_bytes = 0
        content_length = 0

        try:
            # Create parent directories if needed
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Open file for writing
            with open(destination, "wb") as f:  # noqa: ASYNC230
                # Stream download - get content-length from response headers
                request_timeout = timeout if timeout is not None else self.config.default_timeout
                request_headers = headers.copy() if headers else {}

                async with self._session.request(
                    method=HttpMethod.GET.value,
                    url=url,
                    headers=request_headers,
                    timeout=aiohttp.ClientTimeout(total=request_timeout),
                    allow_redirects=True,
                ) as response:
                    if response.status >= 400:
                        error_body = await response.read()
                        msg = f"HTTP {response.status}: {error_body.decode('utf-8', errors='replace')}"
                        raise NetworkError(
                            msg,
                        )

                    # Get content length from response headers
                    content_length = int(response.headers.get("Content-Length", 0))

                    # Stream chunks
                    async for chunk in response.content.iter_chunked(chunk_size):
                        f.write(chunk)
                        total_bytes += len(chunk)

                        # Call progress callback
                        if progress_callback is not None:
                            try:
                                progress_callback(total_bytes, content_length)
                            except Exception:
                                logger.exception("Progress callback error")
            # Calculate statistics
            duration = time.perf_counter() - start_time
            average_speed = total_bytes / duration if duration > 0 else 0

            logger.info(
                "File download complete",
                extra={
                    "url": url,
                    "destination": str(destination),
                    "total_bytes": total_bytes,
                    "duration": duration,
                    "average_speed_mbps": average_speed / 1024 / 1024,
                },
            )

            return DownloadResult(
                url=url,
                destination=str(destination),
                total_bytes=total_bytes,
                duration=duration,
                average_speed=average_speed,
                success=True,
            )

        except Exception as e:
            duration = time.perf_counter() - start_time
            average_speed = total_bytes / duration if duration > 0 else 0
            logger.exception(
                "File download failed",
                extra={
                    "url": url,
                    "destination": str(destination),
                    "error": str(e),
                    "bytes_downloaded": total_bytes,
                },
            )
            # Clean up partial download
            if destination.exists():
                try:
                    destination.unlink()
                except Exception:
                    logger.exception("Failed to clean up partial download")
            return DownloadResult(
                url=url,
                destination=str(destination),
                total_bytes=total_bytes,
                duration=duration,
                average_speed=average_speed,
                success=False,
                error=str(e),
            )

    async def upload_file(
        self,
        url: str,
        file_path: Path,
        progress_callback: Callable[[int, int], None] | None = None,
        chunk_size: int = 8192,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
        method: HttpMethod = HttpMethod.POST,
    ) -> UploadResult:
        """Upload file with progress tracking.

        Time Complexity: O(n) where n is file size
        Space Complexity: O(chunk_size) - constant memory usage

        Args:
            url: Upload URL
            file_path: Local file path
            progress_callback: Progress callback (bytes_uploaded, total_bytes)
            chunk_size: Size of each chunk in bytes (default: 8KB)
            timeout: Request timeout in seconds
            headers: Custom headers
            method: HTTP method (POST or PUT)

        Returns:
            Upload result with statistics

        Example:
            >>> def progress(uploaded, total):
            ...     percent = (uploaded / total) * 100 if total > 0 else 0
            ...     print(f"Uploaded: {percent:.1f}%")
            >>>
            >>> result = await manager.upload_file(
            ...     url="https://example.com/upload",
            ...     file_path=Path("/tmp/large-file.zip"),
            ...     progress_callback=progress
            ... )
            >>> print(f"Uploaded {result.total_bytes} bytes in {result.duration:.2f}s")
            >>> print(f"Response status: {result.response_status}")

        """
        start_time = time.perf_counter()
        total_bytes = 0
        response_status = None

        try:
            # Validate file exists
            if not file_path.exists():
                msg = f"File not found: {file_path}"
                raise FileNotFoundError(msg)

            # Get file size
            file_size = file_path.stat().st_size

            # Create async generator for file chunks
            async def file_chunk_generator():
                nonlocal total_bytes
                with open(file_path, "rb") as f:  # noqa: ASYNC230
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        total_bytes += len(chunk)

                        # Call progress callback
                        if progress_callback is not None:
                            try:
                                progress_callback(total_bytes, file_size)
                            except Exception:
                                logger.exception("Progress callback error")
                        yield chunk

            # Prepare headers
            request_headers = headers.copy() if headers else {}
            request_headers.setdefault("Content-Type", "application/octet-stream")
            request_headers.setdefault("Content-Length", str(file_size))

            # Execute upload request
            request_timeout = timeout if timeout is not None else self.config.default_timeout

            logger.debug(
                "File upload starting",
                extra={
                    "url": url,
                    "file_path": str(file_path),
                    "file_size": file_size,
                    "method": method.value,
                },
            )

            async with self._session.request(
                method=method.value,
                url=url,
                headers=request_headers,
                data=file_chunk_generator(),
                timeout=aiohttp.ClientTimeout(total=request_timeout),
            ) as response:
                response_status = response.status
                response_body = await response.read()

                # Check for errors
                if response.status >= 400:
                    msg = (
                        f"Upload failed with HTTP {response.status}: "
                        f"{response_body.decode('utf-8', errors='replace')}"
                    )
                    raise NetworkError(
                        msg,
                    )

            # Calculate statistics
            duration = time.perf_counter() - start_time
            average_speed = total_bytes / duration if duration > 0 else 0

            logger.info(
                "File upload complete",
                extra={
                    "url": url,
                    "file_path": str(file_path),
                    "total_bytes": total_bytes,
                    "duration": duration,
                    "average_speed_mbps": average_speed / 1024 / 1024,
                    "response_status": response_status,
                },
            )

            return UploadResult(
                url=url,
                source=str(file_path),
                total_bytes=total_bytes,
                duration=duration,
                average_speed=average_speed,
                success=True,
                response_status=response_status,
            )

        except Exception as e:
            duration = time.perf_counter() - start_time
            average_speed = total_bytes / duration if duration > 0 else 0
            logger.exception(
                "File upload failed",
                extra={
                    "url": url,
                    "file_path": str(file_path),
                    "error": str(e),
                    "bytes_uploaded": total_bytes,
                },
            )
            return UploadResult(
                url=url,
                source=str(file_path),
                total_bytes=total_bytes,
                duration=duration,
                average_speed=average_speed,
                success=False,
                response_status=response_status,
                error=str(e),
            )

    # Webhook methods

    def register_webhook(
        self,
        endpoint: str,
        handler: Callable[[WebhookEvent], Awaitable[None]],
        secret_key: str | None = None,
        config: WebhookConfig | None = None,
        event_types: list[str] | None = None,
    ) -> None:
        """Register webhook handler for endpoint.

        Args:
            endpoint: Webhook endpoint path (e.g., "/webhooks/github")
            handler: Async handler function
            secret_key: Secret key for signature verification
            config: Webhook configuration (uses default if None)
            event_types: List of event types to handle (empty = all types)

        Raises:
            ValueError: If webhooks not enabled or endpoint already registered

        Example:
            >>> async def handle_github_event(event: WebhookEvent):
            ...     print(f"GitHub event: {event.event_type}")
            ...     print(f"Payload: {event.payload}")
            >>>
            >>> manager.register_webhook(
            ...     endpoint="/webhooks/github",
            ...     handler=handle_github_event,
            ...     secret_key="github_webhook_secret",
            ...     event_types=["push", "pull_request"]
            ... )

        """
        if self._webhook_manager is None:
            msg = "Webhooks not enabled - set enable_webhooks=True in config"
            raise ValueError(msg)

        self._webhook_manager.register_webhook(
            endpoint=endpoint,
            handler=handler,
            secret_key=secret_key,
            config=config,
            event_types=event_types,
        )

    def unregister_webhook(self, endpoint: str) -> bool:
        """Unregister webhook handler.

        Args:
            endpoint: Webhook endpoint path

        Returns:
            True if handler was unregistered, False if not found

        Example:
            >>> manager.unregister_webhook("/webhooks/github")
            True

        """
        if self._webhook_manager is None:
            return False

        return self._webhook_manager.unregister_webhook(endpoint)

    def get_registered_webhooks(self) -> list[str]:
        """Get list of registered webhook endpoints.

        Returns:
            List of endpoint paths

        Example:
            >>> endpoints = manager.get_registered_webhooks()
            >>> print(f"Registered webhooks: {endpoints}")
            ['/webhooks/github', '/webhooks/stripe']

        """
        if self._webhook_manager is None:
            return []

        return self._webhook_manager.get_registered_endpoints()

    def get_webhook_stats(self, endpoint: str) -> dict[str, Any] | None:
        """Get statistics for webhook handler.

        Args:
            endpoint: Webhook endpoint path

        Returns:
            Handler statistics or None if not found

        Example:
            >>> stats = manager.get_webhook_stats("/webhooks/github")
            >>> if stats:
            ...     print(f"Triggers: {stats['trigger_count']}")
            ...     print(f"Last triggered: {stats['last_triggered']}")

        """
        if self._webhook_manager is None:
            return None

        return self._webhook_manager.get_handler_stats(endpoint)

    async def process_webhook(
        self,
        endpoint: str,
        headers: dict[str, str],
        body: bytes,
    ) -> WebhookEvent:
        """Process incoming webhook request.

        Args:
            endpoint: Webhook endpoint path
            headers: HTTP headers from request
            body: Request body bytes

        Returns:
            Webhook event

        Raises:
            ValueError: If webhooks not enabled
            HandlerNotFoundError: If no handler registered for endpoint
            SignatureVerificationError: If signature verification fails
            TimestampValidationError: If timestamp validation fails
            WebhookError: If webhook processing fails

        Example:
            >>> event = await manager.process_webhook(
            ...     endpoint="/webhooks/github",
            ...     headers={
            ...         "X-Webhook-Signature": "sha256=abc123...",
            ...         "X-Webhook-Timestamp": "1234567890",
            ...         "X-GitHub-Event": "push",
            ...     },
            ...     body=b'{"repository": "agent-guru", "ref": "refs/heads/main"}',
            ... )
            >>> print(f"Event type: {event.event_type}")
            >>> print(f"Verified: {event.verified}")

        """
        if self._webhook_manager is None:
            msg = "Webhooks not enabled - set enable_webhooks=True in config"
            raise ValueError(msg)

        return await self._webhook_manager.process_webhook(
            endpoint=endpoint,
            headers=headers,
            body=body,
        )
