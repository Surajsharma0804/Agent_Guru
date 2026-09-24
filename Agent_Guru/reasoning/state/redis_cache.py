"""Redis caching layer for conversation state.

Performance: O(1) cache operations, <10ms latency
"""

import json
from typing import Any

try:
    import redis.asyncio as redis
except ImportError:
    redis: Any = None  # type: ignore[assignment]

from Agent_Guru.reasoning.models.conversation import ConversationState

# Matches RedisPool's default in reasoning/utils/connection_pool.py, so the two
# Redis users in this codebase agree on where Redis lives when nothing says
# otherwise.
DEFAULT_REDIS_URL = "redis://localhost:6379"


class RedisCache:
    """Redis cache for hot conversation data."""

    def __init__(self, url: str | None = None, ttl: int = 3600) -> None:
        # `url or DEFAULT` rather than plain assignment: the parameter is
        # declared optional, but nothing supplied a fallback, so RedisCache()
        # left self.url as None and initialize() then called
        # redis.from_url(None), which fails with an obscure type error instead
        # of connecting to the obvious default.
        self.url = url or DEFAULT_REDIS_URL
        self.ttl = ttl
        self._client: redis.Redis | None = None

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        if redis is None:
            msg = "redis not installed. Install with: pip install redis"
            raise RuntimeError(msg)
        self._client = await redis.from_url(self.url, decode_responses=True)

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            client, self._client = self._client, None
            # redis-py >= 5.0.1 spells this aclose(); close() is the
            # deprecated alias. Preferring aclose() where present keeps this
            # quiet on current releases without breaking older ones.
            closer = getattr(client, "aclose", None) or client.close
            await closer()

    async def get(self, conversation_id: str) -> ConversationState | None:
        """Get conversation from cache."""
        if not self._client:
            return None
        try:
            data = await self._client.get(f"conv:{conversation_id}")
            if data:
                return ConversationState(**json.loads(data))
            return None
        except Exception:
            return None

    async def set(self, state: ConversationState) -> bool:
        """Set conversation in cache with TTL."""
        if not self._client:
            return False
        try:
            await self._client.setex(
                f"conv:{state.conversation_id}",
                self.ttl,
                state.model_dump_json(),
            )
            return True
        except Exception:
            return False

    async def delete(self, conversation_id: str) -> bool:
        """Delete conversation from cache."""
        if not self._client:
            return False
        try:
            await self._client.delete(f"conv:{conversation_id}")
            return True
        except Exception:
            return False
