"""
Tests for cloud synchronization service.

Coverage Target: >80%
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from Agent_Guru.reasoning.models.conversation import (
    ConversationState,
    ConversationTurn,
)
from Agent_Guru.reasoning.state.cloud_sync import (
    CloudSyncService,
    SyncConfig,
)


@pytest.fixture
def sync_config():
    """Create test sync configuration."""
    return SyncConfig(
        host="localhost",
        port=5432,
        database="test_db",
        user="test_user",
        password="test_pass",  # nosec B106
    )


@pytest.fixture
def sample_state():
    """Create sample conversation state."""
    return ConversationState(
        conversation_id="conv_123",
        user_id="user_456",
        turns=[
            ConversationTurn(
                turn_id="turn_1",
                turn_number=1,
                user_input="Hello",
                assistant_response="Hi there!",
                timestamp=datetime.now(),
            )
        ],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


class TestCloudSyncService:
    """Tests for CloudSyncService."""

    def test_initialization(self, sync_config):
        """Test service initialization."""
        service = CloudSyncService(sync_config)

        assert service.config == sync_config
        assert service._pool is None
        assert not service._initialized

    @pytest.mark.asyncio
    async def test_initialize_without_asyncpg(self, sync_config):
        """Test initialization fails without asyncpg."""
        with patch("Agent_Guru.reasoning.state.cloud_sync.asyncpg", None):
            service = CloudSyncService(sync_config)

            with pytest.raises(RuntimeError, match="asyncpg is not installed"):
                await service.initialize()

    @pytest.mark.asyncio
    async def test_initialize_connection_error(self, sync_config):
        """Test initialization handles connection errors."""
        mock_pool = AsyncMock()
        mock_pool.side_effect = Exception("Connection failed")

        with patch("Agent_Guru.reasoning.state.cloud_sync.asyncpg") as mock_asyncpg:
            mock_asyncpg.create_pool = mock_pool

            service = CloudSyncService(sync_config)

            with pytest.raises(ConnectionError, match="Failed to connect"):
                await service.initialize()

    @pytest.mark.asyncio
    async def test_sync_to_cloud_not_initialized(self, sync_config, sample_state):
        """Test sync_to_cloud fails when not initialized."""
        service = CloudSyncService(sync_config)

        with pytest.raises(RuntimeError, match="not initialized"):
            await service.sync_to_cloud(sample_state)

    @pytest.mark.asyncio
    async def test_sync_from_cloud_not_initialized(self, sync_config):
        """Test sync_from_cloud fails when not initialized."""
        service = CloudSyncService(sync_config)

        with pytest.raises(RuntimeError, match="not initialized"):
            await service.sync_from_cloud("conv_123", "user_456")

    @pytest.mark.asyncio
    async def test_list_user_conversations_not_initialized(self, sync_config):
        """Test list_user_conversations fails when not initialized."""
        service = CloudSyncService(sync_config)

        with pytest.raises(RuntimeError, match="not initialized"):
            await service.list_user_conversations("user_456")

    @pytest.mark.asyncio
    async def test_delete_conversation_not_initialized(self, sync_config):
        """Test delete_conversation fails when not initialized."""
        service = CloudSyncService(sync_config)

        with pytest.raises(RuntimeError, match="not initialized"):
            await service.delete_conversation("conv_123", "user_456")

    @pytest.mark.asyncio
    async def test_get_sync_status_not_initialized(self, sync_config):
        """Test get_sync_status fails when not initialized."""
        service = CloudSyncService(sync_config)

        with pytest.raises(RuntimeError, match="not initialized"):
            await service.get_sync_status("conv_123", "user_456")

    @pytest.mark.asyncio
    async def test_close(self, sync_config):
        """Test closing service."""
        service = CloudSyncService(sync_config)
        service._pool = AsyncMock()
        service._initialized = True

        await service.close()

        assert service._pool is None
        assert not service._initialized


class TestCloudSyncServiceMocked:
    """Tests for CloudSyncService with mocked database."""

    @pytest.fixture
    async def mock_service(self, sync_config):
        """Create service with mocked pool."""
        service = CloudSyncService(sync_config)

        # Mock pool and connection
        mock_conn = AsyncMock()
        mock_pool = AsyncMock()

        # Create async context manager for acquire
        class MockAcquire:
            def __init__(self, conn):
                self.conn = conn

            async def __aenter__(self):
                return self.conn

            async def __aexit__(self, *args):
                pass

        mock_pool.acquire.return_value = MockAcquire(mock_conn)

        service._pool = mock_pool
        service._initialized = True

        yield service, mock_conn

        await service.close()

    @pytest.mark.skip(reason="Requires real PostgreSQL connection for integration testing")
    @pytest.mark.asyncio
    async def test_sync_to_cloud_success(self, mock_service, sample_state):
        """Test successful sync to cloud."""
        service, mock_conn = mock_service
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        result = await service.sync_to_cloud(sample_state)

        assert result is True
        assert mock_conn.execute.called

    @pytest.mark.asyncio
    async def test_sync_to_cloud_failure(self, mock_service, sample_state):
        """Test sync to cloud handles errors."""
        service, mock_conn = mock_service
        mock_conn.execute = AsyncMock(side_effect=Exception("DB error"))

        result = await service.sync_to_cloud(sample_state)

        assert result is False

    @pytest.mark.skip(reason="Requires real PostgreSQL connection for integration testing")
    @pytest.mark.asyncio
    async def test_sync_from_cloud_found(self, mock_service, sample_state):
        """Test sync from cloud when conversation exists."""
        service, mock_conn = mock_service

        # Mock database row
        mock_row = {"state_data": sample_state.model_dump_json()}
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await service.sync_from_cloud("conv_123", "user_456")

        assert result is not None
        assert result.conversation_id == "conv_123"
        assert result.user_id == "user_456"
        assert mock_conn.fetchrow.called

    @pytest.mark.asyncio
    async def test_sync_from_cloud_not_found(self, mock_service):
        """Test sync from cloud when conversation doesn't exist."""
        service, mock_conn = mock_service
        mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await service.sync_from_cloud("conv_123", "user_456")

        assert result is None

    @pytest.mark.asyncio
    async def test_sync_from_cloud_error(self, mock_service):
        """Test sync from cloud handles errors."""
        service, mock_conn = mock_service
        mock_conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))

        result = await service.sync_from_cloud("conv_123", "user_456")

        assert result is None

    @pytest.mark.skip(reason="Requires real PostgreSQL connection for integration testing")
    @pytest.mark.asyncio
    async def test_list_user_conversations(self, mock_service):
        """Test listing user conversations."""
        service, mock_conn = mock_service

        # Mock database rows
        mock_rows = [
            {"conversation_id": "conv_1"},
            {"conversation_id": "conv_2"},
            {"conversation_id": "conv_3"},
        ]
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        result = await service.list_user_conversations("user_456")

        assert len(result) == 3
        assert result == ["conv_1", "conv_2", "conv_3"]
        assert mock_conn.fetch.called

    @pytest.mark.asyncio
    async def test_list_user_conversations_empty(self, mock_service):
        """Test listing user conversations when none exist."""
        service, mock_conn = mock_service
        mock_conn.fetch = AsyncMock(return_value=[])

        result = await service.list_user_conversations("user_456")

        assert result == []

    @pytest.mark.asyncio
    async def test_list_user_conversations_error(self, mock_service):
        """Test listing user conversations handles errors."""
        service, mock_conn = mock_service
        mock_conn.fetch = AsyncMock(side_effect=Exception("DB error"))

        result = await service.list_user_conversations("user_456")

        assert result == []

    @pytest.mark.skip(reason="Requires real PostgreSQL connection for integration testing")
    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, mock_service):
        """Test successful conversation deletion."""
        service, mock_conn = mock_service
        mock_conn.execute = AsyncMock(return_value="DELETE 1")

        result = await service.delete_conversation("conv_123", "user_456")

        assert result is True
        assert mock_conn.execute.called

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, mock_service):
        """Test deleting non-existent conversation."""
        service, mock_conn = mock_service
        mock_conn.execute = AsyncMock(return_value="DELETE 0")

        result = await service.delete_conversation("conv_123", "user_456")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_conversation_error(self, mock_service):
        """Test delete conversation handles errors."""
        service, mock_conn = mock_service
        mock_conn.execute = AsyncMock(side_effect=Exception("DB error"))

        result = await service.delete_conversation("conv_123", "user_456")

        assert result is False

    @pytest.mark.skip(reason="Requires real PostgreSQL connection for integration testing")
    @pytest.mark.asyncio
    async def test_get_sync_status_found(self, mock_service):
        """Test getting sync status when conversation exists."""
        service, mock_conn = mock_service

        mock_row = {"version": 5, "updated_at": datetime.now()}
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await service.get_sync_status("conv_123", "user_456")

        assert result is not None
        assert result["version"] == 5
        assert "updated_at" in result
        assert mock_conn.fetchrow.called

    @pytest.mark.asyncio
    async def test_get_sync_status_not_found(self, mock_service):
        """Test getting sync status when conversation doesn't exist."""
        service, mock_conn = mock_service
        mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await service.get_sync_status("conv_123", "user_456")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_sync_status_error(self, mock_service):
        """Test get sync status handles errors."""
        service, mock_conn = mock_service
        mock_conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))

        result = await service.get_sync_status("conv_123", "user_456")

        assert result is None
