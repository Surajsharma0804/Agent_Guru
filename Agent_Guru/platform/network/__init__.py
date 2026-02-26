"""
Network management module for Agent Guru Platform Integration.

This module provides robust HTTP/HTTPS client functionality with enterprise features:
- All HTTP methods (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)
- SSL/TLS certificate validation
- Custom headers and request bodies
- Configurable timeouts
- Request/response logging
- Rate limiting with token bucket algorithm
- Response caching with LRU eviction
- Connection pooling with per-host limits
- Idle connection cleanup
- Connection reuse tracking
"""

from Agent_Guru.platform.network.manager import (
    NetworkManager,
    NetworkConfig,
    HttpMethod,
    HttpResponse,
    NetworkError,
    SSLValidationError,
    TimeoutError,
    ConnectionError,
    RateLimitError,
)

from Agent_Guru.platform.network.rate_limiter import (
    RateLimitConfig,
    RateLimitStatus,
    RateLimitExceeded,
    TokenBucket,
    RateLimiter,
    RateLimiterManager,
)

from Agent_Guru.platform.network.response_cache import (
    ResponseCache,
    CachedResponse,
    CacheStatistics,
)

from Agent_Guru.platform.network.connection_pool import (
    ConnectionPoolManager,
    ConnectionPoolConfig,
    ConnectionStats,
    PoolStatistics,
)

__all__ = [
    # Network Manager
    "NetworkManager",
    "NetworkConfig",
    "HttpMethod",
    "HttpResponse",
    # Exceptions
    "NetworkError",
    "SSLValidationError",
    "TimeoutError",
    "ConnectionError",
    "RateLimitError",
    # Rate Limiting
    "RateLimitConfig",
    "RateLimitStatus",
    "RateLimitExceeded",
    "TokenBucket",
    "RateLimiter",
    "RateLimiterManager",
    # Response Caching
    "ResponseCache",
    "CachedResponse",
    "CacheStatistics",
    # Connection Pooling
    "ConnectionPoolManager",
    "ConnectionPoolConfig",
    "ConnectionStats",
    "PoolStatistics",
]

