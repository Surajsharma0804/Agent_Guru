"""
Redis caching layer for conversation state.

Performance: O(1) cache operations, <10ms latency
"""

import json
from typing import Optional

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

from Agent_Guru.reasoning.models.conversation import ConversationState


class RedisCache:
    """Redis cache for hot conversation data."""

    def __init__(self, url: str = "redis://localhost:6379", ttl: int = 3600):
        self.url = url
        self.ttl = ttl
        self._client: Optional[redis.Redis] = None

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        if redis is None:
            raise RuntimeError("redis not installed. Install with: pip install redis")
        self._client = await redis.from_url(self.url, decode_responses=True)

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()

    async def get(self, conversation_id: str) -> Optional[ConversationState]:
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
                f"conv:{state.conversation_id}", self.ttl, state.model_dump_json()
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
