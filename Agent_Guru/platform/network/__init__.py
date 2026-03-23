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
- Webhook registration and handling
- Signature verification (HMAC-SHA256/SHA512)
- Event routing with async handlers
"""

from Agent_Guru.platform.network.connection_pool import (
    ConnectionPoolConfig,
    ConnectionPoolManager,
    ConnectionStats,
    PoolStatistics,
)
from Agent_Guru.platform.network.manager import (
    ConnectionError,
    HttpMethod,
    HttpResponse,
    NetworkConfig,
    NetworkError,
    NetworkManager,
    RateLimitError,
    SSLValidationError,
    TimeoutError,
)
from Agent_Guru.platform.network.rate_limiter import (
    RateLimitConfig,
    RateLimiter,
    RateLimiterManager,
    RateLimitExceeded,
    RateLimitStatus,
    TokenBucket,
)
from Agent_Guru.platform.network.response_cache import (
    CachedResponse,
    CacheStatistics,
    ResponseCache,
)
from Agent_Guru.platform.network.webhook import (
    HandlerNotFoundError,
    SignatureAlgorithm,
    SignatureVerificationError,
    TimestampValidationError,
    WebhookConfig,
    WebhookError,
    WebhookEvent,
    WebhookHandler,
    WebhookManager,
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
    # Webhooks
    "WebhookManager",
    "WebhookConfig",
    "WebhookEvent",
    "WebhookHandler",
    "SignatureAlgorithm",
    "WebhookError",
    "SignatureVerificationError",
    "TimestampValidationError",
    "HandlerNotFoundError",
]

