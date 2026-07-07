"""Tests for Redis cache."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from Agent_Guru.reasoning.models.conversation import ConversationState, ConversationTurn
from Agent_Guru.reasoning.state.redis_cache import RedisCache


@pytest.fixture
def sample_state():
    return ConversationState(
        conversation_id="conv_123",
        user_id="user_456",
        turns=[
            ConversationTurn(
                turn_id="t1",
                turn_number=1,
                user_input="Hi",
                assistant_response="Hello",
                timestamp=datetime.now(tz=timezone.utc),
            )
        ],
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )


class TestRedisCache:
    def test_init(self):
        cache = RedisCache()
        assert cache.url == "redis://localhost:6379"  # nosec B101
        assert cache.ttl == 3600  # nosec B101

    @pytest.mark.asyncio
    async def test_initialize_without_redis(self):
        with patch("Agent_Guru.reasoning.state.redis_cache.redis", None):
            cache = RedisCache()
            with pytest.raises(RuntimeError, match="redis not installed"):
                await cache.initialize()

    @pytest.mark.asyncio
    async def test_get_not_initialized(self, sample_state):
        cache = RedisCache()
        result = await cache.get("conv_123")
        assert result is None  # nosec B101

    @pytest.mark.asyncio
    async def test_set_not_initialized(self, sample_state):
        cache = RedisCache()
        result = await cache.set(sample_state)
        assert result is False  # nosec B101

    @pytest.mark.asyncio
    async def test_delete_not_initialized(self):
        cache = RedisCache()
        result = await cache.delete("conv_123")
        assert result is False  # nosec B101
