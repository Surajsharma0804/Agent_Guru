"""
Tests for Agent_Guru.platform.integration.goal_manager_client
Coverage Target: >80% (enforced by CI/CD)

Author: Agent Guru Platform Team
Date: 2026-02-26
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID

import aiohttp
import pytest
from hypothesis import given, strategies as st

from Agent_Guru.platform.integration.goal_manager_client import (
    GoalManagerClient,
    NotificationStatus,
    OperationResult,
    OperationStatus,
    TaskCompletionNotification,
)


class TestGoalManagerClient:
    """Unit tests for GoalManagerClient."""
    
    def test_initialization(self):
        """Test client initialization with default parameters."""
        client = GoalManagerClient()
        
        assert client.base_url == "http://localhost:8080"
        assert client.timeout == 30.0
        assert client.max_retries == 3
        assert client.retry_delay == 1.0
        assert client.circuit_breaker_threshold == 5
        assert client.circuit_breaker_timeout == 60.0
        assert client._session is None
        assert not client._circuit_open
    
    def test_initialization_with_custom_params(self):
        """Test client initialization with custom parameters."""
        client = GoalManagerClient(
            base_url="http://goal-manager:9000",
            timeout=60.0,
            max_retries=5,
            retry_delay=2.0,
            circuit_breaker_threshold=10,
            circuit_breaker_timeout=120.0,
        )
        
        assert client.base_url == "http://goal-manager:9000"
        assert client.timeout == 60.0
        assert client.max_retries == 5
        assert client.retry_delay == 2.0
        assert client.circuit_breaker_threshold == 10
        assert client.circuit_breaker_timeout == 120.0
    
    def test_initialization_strips_trailing_slash(self):
        """Test that trailing slash is stripped from base_url."""
        client = GoalManagerClient(base_url="http://localhost:8080/")
        assert client.base_url == "http://localhost:8080"
    
    def test_invalid_timeout(self):
        """Test validation of invalid timeout."""
        with pytest.raises(ValueError, match="timeout must be positive"):
            GoalManagerClient(timeout=-1.0)
    
    def test_invalid_max_retries(self):
        """Test validation of invalid max_retries."""
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            GoalManagerClient(max_retries=-1)
    
    def test_invalid_retry_delay(self):
        """Test validation of invalid retry_delay."""
        with pytest.raises(ValueError, match="retry_delay must be positive"):
            GoalManagerClient(retry_delay=0.0)
    
    def test_invalid_circuit_breaker_threshold(self):
        """Test validation of invalid circuit_breaker_threshold."""
        with pytest.raises(ValueError, match="circuit_breaker_threshold must be positive"):
            GoalManagerClient(circuit_breaker_threshold=0)
    
    def test_invalid_circuit_breaker_timeout(self):
        """Test validation of invalid circuit_breaker_timeout."""
        with pytest.raises(ValueError, match="circuit_breaker_timeout must be positive"):
            GoalManagerClient(circuit_breaker_timeout=-1.0)
    
    def test_empty_base_url(self):
        """Test validation of empty base_url."""
        with pytest.raises(ValueError, match="base_url cannot be empty"):
            GoalManagerClient(base_url="")
    
    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connecting to Goal Manager."""
        client = GoalManagerClient()
        
        await client.connect()
        
        assert client._session is not None
        assert isinstance(client._session, aiohttp.ClientSession)
        
        await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_connect_already_connected(self):
        """Test error when connecting while already connected."""
        client = GoalManagerClient()
        
        await client.connect()
        
        with pytest.raises(RuntimeError, match="already connected"):
            await client.connect()
        
        await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting from Goal Manager."""
        client = GoalManagerClient()
        
        await client.connect()
        await client.disconnect()
        
        assert client._session is None
    
    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        """Test disconnecting when not connected (should not error)."""
        client = GoalManagerClient()
        
        # Should not raise error
        await client.disconnect()
        assert client._session is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using client as async context manager."""
        async with GoalManagerClient() as client:
            assert client._session is not None
        
        # Session should be closed after context exit
        assert client._session is None
    
    @pytest.mark.asyncio
    async def test_notify_task_completion_not_connected(self):
        """Test error when notifying without connecting."""
        client = GoalManagerClient()
        
        notification = TaskCompletionNotification(
            task_id="task-123",
            task_description="Test task"
        )
        
        with pytest.raises(RuntimeError, match="not connected"):
            await client.notify_task_completion(notification)
    
    @pytest.mark.asyncio
    async def test_notify_task_completion_success(self):
        """Test successful task completion notification."""
        client = GoalManagerClient()
        
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        
        await client.connect()
        
        with patch.object(client._session, 'post', return_value=mock_response):
            notification = TaskCompletionNotification(
                task_id="task-123",
                task_description="Test task",
                operations=[
                    OperationResult(
                        operation_id="op-1",
                        operation_type="file_write",
                        status=OperationStatus.SUCCESS,
                        start_time=datetime.now(tz=timezone.utc),
                        end_time=datetime.now(tz=timezone.utc),
                        execution_time=0.5,
                    )
                ],
            )
            
            status = await client.notify_task_completion(notification)
            
            assert status == NotificationStatus.SENT
            assert client._notifications_sent == 1
            assert client._notifications_failed == 0
        
        await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_notify_task_completion_rate_limited(self):
        """Test notification when rate limited."""
        client = GoalManagerClient(max_retries=2)
        
        # Mock HTTP response with rate limit
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        
        await client.connect()
        
        with patch.object(client._session, 'post', return_value=mock_response):
            notification = TaskCompletionNotification(
                task_id="task-123",
                task_description="Test task"
            )
            
            status = await client.notify_task_completion(notification)
            
            assert status == NotificationStatus.FAILED
            assert client._notifications_failed == 1
            # Rate limit returns RETRYING status, not exception, so no retry attempts
        
        await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_notify_task_completion_server_error(self):
        """Test notification when server returns error."""
        client = GoalManagerClient(max_retries=1)
        
        # Mock HTTP response with server error
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        
        await client.connect()
        
        with patch.object(client._session, 'post', return_value=mock_response):
            notification = TaskCompletionNotification(
                task_id="task-123",
                task_description="Test task"
            )
            
            status = await client.notify_task_completion(notification)
            
            assert status == NotificationStatus.FAILED
            assert client._notifications_failed == 1
        
        await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold(self):
        """Test that circuit breaker opens after threshold failures."""
        client = GoalManagerClient(
            max_retries=1,
            circuit_breaker_threshold=3
        )
        
        # Mock HTTP response with error
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Error")
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        
        await client.connect()
        
        with patch.object(client._session, 'post', return_value=mock_response):
            notification = TaskCompletionNotification(
                task_id="task-123",
                task_description="Test task"
            )
            
            # Fail 3 times to open circuit
            for _ in range(3):
                await client.notify_task_completion(notification)
            
            assert client._circuit_open
            assert client._failure_count == 3
            
            # Next attempt should fail fast
            status = await client.notify_task_completion(notification)
            assert status == NotificationStatus.FAILED
        
        await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_after_timeout(self):
        """Test that circuit breaker resets after timeout."""
        client = GoalManagerClient(
            max_retries=1,
            circuit_breaker_threshold=2,
            circuit_breaker_timeout=0.1  # Short timeout for testing
        )
        
        # Mock HTTP response with error
        mock_response_error = AsyncMock()
        mock_response_error.status = 500
        mock_response_error.text = AsyncMock(return_value="Error")
        mock_response_error.__aenter__.return_value = mock_response_error
        mock_response_error.__aexit__.return_value = None
        
        # Mock HTTP response with success
        mock_response_success = AsyncMock()
        mock_response_success.status = 200
        mock_response_success.__aenter__.return_value = mock_response_success
        mock_response_success.__aexit__.return_value = None
        
        await client.connect()
        
        notification = TaskCompletionNotification(
            task_id="task-123",
            task_description="Test task"
        )
        
        # Fail twice to open circuit
        with patch.object(client._session, 'post', return_value=mock_response_error):
            for _ in range(2):
                await client.notify_task_completion(notification)
            
            assert client._circuit_open
        
        # Wait for circuit breaker timeout
        await asyncio.sleep(0.2)
        
        # Next attempt should try again and succeed
        with patch.object(client._session, 'post', return_value=mock_response_success):
            status = await client.notify_task_completion(notification)
            assert status == NotificationStatus.SENT
            assert not client._circuit_open
        
        await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_report_operation_result(self):
        """Test reporting individual operation result."""
        client = GoalManagerClient()
        
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        
        await client.connect()
        
        with patch.object(client._session, 'post', return_value=mock_response):
            operation = OperationResult(
                operation_id="op-1",
                operation_type="command_execution",
                status=OperationStatus.SUCCESS,
                start_time=datetime.now(tz=timezone.utc),
                end_time=datetime.now(tz=timezone.utc),
                execution_time=1.5,
                parameters={"command": "ls -la"},
                result_data={"output": "file1.txt\nfile2.txt"},
            )
            
            status = await client.report_operation_result(operation)
            
            assert status == NotificationStatus.SENT
            assert client._notifications_sent == 1
        
        await client.disconnect()
    
    def test_get_statistics(self):
        """Test getting client statistics."""
        client = GoalManagerClient()
        
        stats = client.get_statistics()
        
        assert stats["notifications_sent"] == 0
        assert stats["notifications_failed"] == 0
        assert stats["total_retry_attempts"] == 0
        assert stats["circuit_open"] is False
        assert stats["failure_count"] == 0


class TestTaskCompletionNotification:
    """Unit tests for TaskCompletionNotification."""
    
    def test_initialization_with_defaults(self):
        """Test notification initialization with default values."""
        notification = TaskCompletionNotification()
        
        assert isinstance(notification.notification_id, UUID)
        assert notification.task_id == ""
        assert notification.task_description == ""
        assert isinstance(notification.completion_time, datetime)
        assert notification.operations == []
        assert notification.overall_status == OperationStatus.SUCCESS
        assert notification.metadata == {}
    
    def test_initialization_with_values(self):
        """Test notification initialization with custom values."""
        now = datetime.now(tz=timezone.utc)
        operation = OperationResult(
            operation_id="op-1",
            operation_type="file_write",
            status=OperationStatus.SUCCESS,
            start_time=now,
            end_time=now,
            execution_time=0.5,
        )
        
        notification = TaskCompletionNotification(
            task_id="task-123",
            task_description="Create user profile",
            completion_time=now,
            operations=[operation],
            overall_status=OperationStatus.SUCCESS,
            metadata={"user_id": "user-456"},
        )
        
        assert notification.task_id == "task-123"
        assert notification.task_description == "Create user profile"
        assert notification.completion_time == now
        assert len(notification.operations) == 1
        assert notification.overall_status == OperationStatus.SUCCESS
        assert notification.metadata == {"user_id": "user-456"}
    
    def test_to_dict(self):
        """Test converting notification to dictionary."""
        now = datetime.now(tz=timezone.utc)
        operation = OperationResult(
            operation_id="op-1",
            operation_type="file_write",
            status=OperationStatus.SUCCESS,
            start_time=now,
            end_time=now,
            execution_time=0.5,
            parameters={"path": "/tmp/test.txt"},  # nosec B108
            result_data={"bytes_written": 1024},
        )
        
        notification = TaskCompletionNotification(
            task_id="task-123",
            task_description="Write file",
            operations=[operation],
        )
        
        data = notification.to_dict()
        
        assert "notification_id" in data
        assert data["task_id"] == "task-123"
        assert data["task_description"] == "Write file"
        assert "completion_time" in data
        assert len(data["operations"]) == 1
        assert data["operations"][0]["operation_id"] == "op-1"
        assert data["operations"][0]["operation_type"] == "file_write"
        assert data["operations"][0]["status"] == "success"
        assert data["overall_status"] == "success"


class TestOperationResult:
    """Unit tests for OperationResult."""
    
    def test_initialization(self):
        """Test operation result initialization."""
        now = datetime.now(tz=timezone.utc)
        
        result = OperationResult(
            operation_id="op-1",
            operation_type="command_execution",
            status=OperationStatus.SUCCESS,
            start_time=now,
            end_time=now + timedelta(seconds=2),
            execution_time=2.0,
            parameters={"command": "ls -la"},
            result_data={"exit_code": 0, "output": "file1.txt"},
            error_message=None,
            resource_usage={"cpu_percent": 5.0, "memory_mb": 10.0},
        )
        
        assert result.operation_id == "op-1"
        assert result.operation_type == "command_execution"
        assert result.status == OperationStatus.SUCCESS
        assert result.start_time == now
        assert result.execution_time == 2.0
        assert result.parameters == {"command": "ls -la"}
        assert result.result_data == {"exit_code": 0, "output": "file1.txt"}
        assert result.error_message is None
        assert result.resource_usage == {"cpu_percent": 5.0, "memory_mb": 10.0}
    
    def test_initialization_with_error(self):
        """Test operation result initialization with error."""
        now = datetime.now(tz=timezone.utc)
        
        result = OperationResult(
            operation_id="op-2",
            operation_type="file_write",
            status=OperationStatus.FAILURE,
            start_time=now,
            end_time=now + timedelta(seconds=1),
            execution_time=1.0,
            error_message="Permission denied",
        )
        
        assert result.status == OperationStatus.FAILURE
        assert result.error_message == "Permission denied"


class TestGoalManagerClientProperties:
    """Property-based tests for GoalManagerClient."""
    
    @given(
        timeout=st.floats(min_value=0.1, max_value=300.0),
        max_retries=st.integers(min_value=0, max_value=10),
        retry_delay=st.floats(min_value=0.1, max_value=10.0),
    )
    def test_valid_config_always_works(
        self,
        timeout: float,
        max_retries: int,
        retry_delay: float
    ):
        """Property: Valid config always creates client."""
        client = GoalManagerClient(
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        
        assert client.timeout == timeout
        assert client.max_retries == max_retries
        assert client.retry_delay == retry_delay
    
    @given(
        task_id=st.text(min_size=1, max_size=100),
        task_description=st.text(min_size=1, max_size=500),
    )
    def test_notification_always_has_valid_structure(
        self,
        task_id: str,
        task_description: str
    ):
        """Property: Notification always has valid structure."""
        notification = TaskCompletionNotification(
            task_id=task_id,
            task_description=task_description,
        )
        
        data = notification.to_dict()
        
        assert "notification_id" in data
        assert "task_id" in data
        assert "task_description" in data
        assert "completion_time" in data
        assert "operations" in data
        assert "overall_status" in data
        assert isinstance(data["operations"], list)


@pytest.mark.integration
class TestGoalManagerClientIntegration:
    """Integration tests for GoalManagerClient."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_notification_flow(self):
        """Test complete notification flow from creation to delivery."""
        # This would require a running Goal Manager instance
        # For now, we mock the HTTP layer
        
        client = GoalManagerClient()
        
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        
        await client.connect()
        
        with patch.object(client._session, 'post', return_value=mock_response):
            # Create operation result
            operation = OperationResult(
                operation_id="op-1",
                operation_type="file_write",
                status=OperationStatus.SUCCESS,
                start_time=datetime.now(tz=timezone.utc),
                end_time=datetime.now(tz=timezone.utc),
                execution_time=0.5,
                parameters={"path": "/tmp/test.txt", "content": "Hello World"},  # nosec B108
                result_data={"bytes_written": 11},
            )
            
            # Create notification
            notification = TaskCompletionNotification(
                task_id="task-123",
                task_description="Write test file",
                operations=[operation],
                overall_status=OperationStatus.SUCCESS,
            )
            
            # Send notification
            status = await client.notify_task_completion(notification)
            
            assert status == NotificationStatus.SENT
            
            # Verify statistics
            stats = client.get_statistics()
            assert stats["notifications_sent"] == 1
            assert stats["notifications_failed"] == 0
        
        await client.disconnect()
