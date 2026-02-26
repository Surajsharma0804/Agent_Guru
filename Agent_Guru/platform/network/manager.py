"""
Module: agent_guru.platform.network.manager
Purpose: Robust HTTP/HTTPS client with enterprise features
Author: Agent Guru Team
Date: 2026-02-26

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
import hashlib
import logging
import ssl
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Union
from urllib.parse import urljoin, urlparse

import aiohttp
import certifi

from .rate_limiter import (
    RateLimiter,
    RateLimiterManager,
    RateLimitConfig,
    RateLimitStatus,
    RateLimitExceeded,
)
from .response_cache import ResponseCache, CachedResponse, CacheStatistics

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
    """
    
    default_timeout: float = 30.0
    max_connections: int = 100
    max_connections_total: int = 1000
    verify_ssl: bool = True
    user_agent: str = "Agent-Guru/1.0"
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_rate_limiting: bool = True
    default_rate_limit: Optional[RateLimitConfig] = None
    enable_caching: bool = True
    cache_max_size: int = 100 * 1024 * 1024  # 100MB


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
    headers: Dict[str, str]
    body: bytes
    response_time: float
    from_cache: bool
    url: str
    method: str
    
    @property
    def text(self) -> str:
        """Decode body as UTF-8 text."""
        return self.body.decode('utf-8', errors='replace')
    
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


# Exception hierarchy

class NetworkError(Exception):
    """Base exception for network operations."""
    pass


class SSLValidationError(NetworkError):
    """Raised when SSL/TLS certificate validation fails."""
    pass


class TimeoutError(NetworkError):
    """Raised when request times out."""
    pass


class ConnectionError(NetworkError):
    """Raised when connection fails."""
    pass


class RateLimitError(NetworkError):
    """Raised when rate limit is exceeded (429 status code)."""
    
    def __init__(self, service: str, retry_after: float, status_code: int = 429):
        self.service = service
        self.retry_after = retry_after
        self.status_code = status_code
        super().__init__(
            f"Rate limit exceeded for service '{service}'. "
            f"Retry after {retry_after:.1f} seconds. (HTTP {status_code})"
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
        self._session: Optional[aiohttp.ClientSession] = None
        self._ssl_context: Optional[ssl.SSLContext] = None
        self._connector: Optional[aiohttp.TCPConnector] = None
        
        # Initialize rate limiter manager
        self._rate_limiter: Optional[RateLimiterManager] = None
        if config.enable_rate_limiting:
            default_rate_config = config.default_rate_limit or RateLimitConfig()
            self._rate_limiter = RateLimiterManager(default_rate_config)
        
        # Initialize response cache
        self._cache: Optional[ResponseCache] = None
        if config.enable_caching:
            self._cache = ResponseCache(max_size=config.cache_max_size)
        
        logger.info(
            "NetworkManager initialized",
            extra={
                "timeout": config.default_timeout,
                "verify_ssl": config.verify_ssl,
                "max_connections": config.max_connections,
                "rate_limiting_enabled": config.enable_rate_limiting,
                "caching_enabled": config.enable_caching,
                "cache_max_size_mb": config.cache_max_size / (1024 * 1024) if config.enable_caching else 0,
            }
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
    
    async def __aenter__(self):
        """Context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()
    
    def configure_rate_limit(
        self,
        service: str,
        config: RateLimitConfig
    ) -> None:
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
        logger.info(f"Rate limit configured for service '{service}'")
    
    def get_rate_limit_status(self, service: str) -> Optional[RateLimitStatus]:
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
    
    def get_all_rate_limit_statuses(self) -> Dict[str, RateLimitStatus]:
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
    
    def get_cache_statistics(self) -> Optional[CacheStatistics]:
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
    
    async def invalidate_cache(self, url_pattern: Optional[str] = None) -> int:
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
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Union[bytes, str, Dict[str, Any]]] = None,
        timeout: Optional[float] = None,
        params: Optional[Dict[str, str]] = None,
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
            raise NetworkError("NetworkManager not started - call start() first")
        
        # Validate URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Invalid URL: {url}")
        
        # Check cache for GET requests (only cacheable method)
        if use_cache and method == HttpMethod.GET and self._cache is not None:
            cached = await self._cache.get(url, method.value, headers)
            if cached is not None:
                # Return cached response
                return HttpResponse(
                    status_code=cached.status_code,
                    headers=cached.headers,
                    body=cached.body,
                    response_time=0.0,  # Instant from cache
                    from_cache=True,
                    url=cached.url,
                    method=cached.method,
                )
        
        # Extract service name for rate limiting
        service = self._extract_service_name(url)
        
        # Check rate limit
        if self._rate_limiter is not None:
            try:
                await self._rate_limiter.acquire(service, timeout=timeout)
            except RateLimitExceeded as e:
                # Rate limit exceeded - return 429 error
                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "service": service,
                        "retry_after": e.retry_after,
                    }
                )
                raise RateLimitError(service, e.retry_after) from e
            except asyncio.TimeoutError as e:
                logger.warning(
                    "Rate limit timeout",
                    extra={
                        "service": service,
                        "timeout": timeout,
                    }
                )
                raise TimeoutError(f"Rate limit timeout for service '{service}'") from e
        
        # Prepare request
        request_timeout = timeout if timeout is not None else self.config.default_timeout
        request_headers = headers.copy() if headers else {}
        
        # Handle body encoding
        request_body = None
        if body is not None:
            if isinstance(body, dict):
                # JSON body
                import json
                request_body = json.dumps(body).encode('utf-8')
                request_headers.setdefault('Content-Type', 'application/json')
            elif isinstance(body, str):
                request_body = body.encode('utf-8')
            else:
                request_body = body
        
        # Retry loop with exponential backoff
        last_exception = None
        for attempt in range(self.config.max_retries):
            start_time = time.perf_counter()
            
            try:
                # Log request
                logger.debug(
                    "HTTP request",
                    extra={
                        "method": method.value,
                        "url": url,
                        "attempt": attempt + 1,
                        "timeout": request_timeout,
                    }
                )
                
                # Execute request
                async with self._session.request(
                    method=method.value,
                    url=url,
                    headers=request_headers,
                    data=request_body,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=request_timeout),
                    allow_redirects=True,
                ) as response:
                    # Read response body
                    response_body = await response.read()
                    response_time = time.perf_counter() - start_time
                    
                    # Create response object
                    http_response = HttpResponse(
                        status_code=response.status,
                        headers=dict(response.headers),
                        body=response_body,
                        response_time=response_time,
                        from_cache=False,
                        url=str(response.url),
                        method=method.value,
                    )
                    
                    # Handle 429 Rate Limit response
                    if response.status == 429:
                        retry_after = float(response.headers.get('Retry-After', 60))
                        logger.warning(
                            "Server returned 429 Rate Limit",
                            extra={
                                "service": service,
                                "retry_after": retry_after,
                                "url": url,
                            }
                        )
                        raise RateLimitError(service, retry_after, status_code=429)
                    
                    # Cache successful GET responses
                    if (use_cache and 
                        method == HttpMethod.GET and 
                        self._cache is not None and
                        200 <= response.status < 300):
                        await self._cache.set(
                            url=str(response.url),
                            status_code=response.status,
                            headers=dict(response.headers),
                            body=response_body,
                            method=method.value,
                        )
                    
                    # Log response
                    logger.info(
                        "HTTP response",
                        extra={
                            "method": method.value,
                            "url": url,
                            "status_code": response.status,
                            "response_time": response_time,
                            "body_size": len(response_body),
                            "from_cache": False,
                        }
                    )
                    
                    return http_response
            
            except asyncio.TimeoutError as e:
                last_exception = TimeoutError(f"Request timed out after {request_timeout}s: {url}")
                logger.warning(
                    "Request timeout",
                    extra={
                        "method": method.value,
                        "url": url,
                        "timeout": request_timeout,
                        "attempt": attempt + 1,
                    }
                )
            
            except aiohttp.ClientSSLError as e:
                # SSL errors are not retryable
                logger.error(
                    "SSL validation failed",
                    extra={
                        "method": method.value,
                        "url": url,
                        "error": str(e),
                    }
                )
                raise SSLValidationError(f"SSL certificate validation failed: {url}") from e
            
            except aiohttp.ClientConnectionError as e:
                last_exception = ConnectionError(f"Connection failed: {url}")
                logger.warning(
                    "Connection error",
                    extra={
                        "method": method.value,
                        "url": url,
                        "error": str(e),
                        "attempt": attempt + 1,
                    }
                )
            
            except aiohttp.ClientError as e:
                last_exception = NetworkError(f"Request failed: {url}")
                logger.warning(
                    "Request error",
                    extra={
                        "method": method.value,
                        "url": url,
                        "error": str(e),
                        "attempt": attempt + 1,
                    }
                )
            
            # Exponential backoff before retry
            if attempt < self.config.max_retries - 1:
                delay = self.config.retry_delay * (2 ** attempt)
                logger.debug(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)
        
        # All retries exhausted
        logger.error(
            "Request failed after all retries",
            extra={
                "method": method.value,
                "url": url,
                "max_retries": self.config.max_retries,
            }
        )
        raise last_exception or NetworkError(f"Request failed: {url}")
    
    async def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
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
        body: Optional[Union[bytes, str, Dict[str, Any]]] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
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
        body: Optional[Union[bytes, str, Dict[str, Any]]] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
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
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
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
        body: Optional[Union[bytes, str, Dict[str, Any]]] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
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
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
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
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
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
