"""Tests for confirmation flows."""

import time


from Agent_Guru.reasoning.models.action import Tool
from Agent_Guru.reasoning.safety.confirmation import (
    BatchConfirmationRequest,
    ConfirmationManager,
    ConfirmationRequest,
    ConfirmationStatus,
)


class TestConfirmationRequest:
    """Tests for ConfirmationRequest."""

    def test_request_creation(self):
        """Test creating confirmation request."""
        tool = Tool(
            tool_id="delete_file",
            name="Delete File",
            description="Delete a file",
        )

        request = ConfirmationRequest(
            request_id="req_123",
            user_id="user123",
            tool=tool,
            parameters={"path": "/important/file.txt"},
            reason="Dangerous file deletion",
        )

        assert request.request_id == "req_123"  # nosec B101
        assert request.user_id == "user123"  # nosec B101
        assert request.tool == tool  # nosec B101
        assert request.parameters == {"path": "/important/file.txt"}  # nosec B101
        assert request.reason == "Dangerous file deletion"  # nosec B101
        assert request.status == ConfirmationStatus.PENDING  # nosec B101
        assert request.response_at is None  # nosec B101

    def test_request_with_expiration(self):
        """Test request with expiration."""
        tool = Tool(tool_id="test", name="Test", description="Test")

        expires_at = time.time() + 60  # 1 minute from now
        request = ConfirmationRequest(
            request_id="req_123",
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test",
            expires_at=expires_at,
        )

        assert not request.is_expired()  # nosec B101
        assert request.is_pending()  # nosec B101

    def test_request_expired(self):
        """Test expired request."""
        tool = Tool(tool_id="test", name="Test", description="Test")

        expires_at = time.time() - 1  # 1 second ago
        request = ConfirmationRequest(
            request_id="req_123",
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test",
            expires_at=expires_at,
        )

        assert request.is_expired()  # nosec B101
        assert not request.is_pending()  # nosec B101

    def test_request_never_expires(self):
        """Test request with no expiration."""
        tool = Tool(tool_id="test", name="Test", description="Test")

        request = ConfirmationRequest(
            request_id="req_123",
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test",
            expires_at=None,
        )

        assert not request.is_expired()  # nosec B101
        assert request.is_pending()  # nosec B101


class TestBatchConfirmationRequest:
    """Tests for BatchConfirmationRequest."""

    def test_batch_creation(self):
        """Test creating batch confirmation."""
        tool1 = Tool(tool_id="tool1", name="Tool 1", description="Test")
        tool2 = Tool(tool_id="tool2", name="Tool 2", description="Test")

        req1 = ConfirmationRequest(
            request_id="req_1",
            user_id="user123",
            tool=tool1,
            parameters={},
            reason="Test 1",
        )
        req2 = ConfirmationRequest(
            request_id="req_2",
            user_id="user123",
            tool=tool2,
            parameters={},
            reason="Test 2",
        )

        batch = BatchConfirmationRequest(
            batch_id="batch_123",
            user_id="user123",
            requests=[req1, req2],
        )

        assert batch.batch_id == "batch_123"  # nosec B101
        assert batch.user_id == "user123"  # nosec B101
        assert len(batch.requests) == 2  # nosec B101
        assert not batch.all_or_nothing  # nosec B101

    def test_batch_all_confirmed(self):
        """Test checking if all requests confirmed."""
        tool = Tool(tool_id="test", name="Test", description="Test")

        req1 = ConfirmationRequest(
            request_id="req_1",
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test",
            status=ConfirmationStatus.GRANTED,
        )
        req2 = ConfirmationRequest(
            request_id="req_2",
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test",
            status=ConfirmationStatus.GRANTED,
        )

        batch = BatchConfirmationRequest(
            batch_id="batch_123",
            user_id="user123",
            requests=[req1, req2],
        )

        assert batch.all_confirmed()  # nosec B101

    def test_batch_not_all_confirmed(self):
        """Test batch with pending requests."""
        tool = Tool(tool_id="test", name="Test", description="Test")

        req1 = ConfirmationRequest(
            request_id="req_1",
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test",
            status=ConfirmationStatus.GRANTED,
        )
        req2 = ConfirmationRequest(
            request_id="req_2",
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test",
            status=ConfirmationStatus.PENDING,
        )

        batch = BatchConfirmationRequest(
            batch_id="batch_123",
            user_id="user123",
            requests=[req1, req2],
        )

        assert not batch.all_confirmed()  # nosec B101

    def test_batch_any_denied(self):
        """Test checking if any request denied."""
        tool = Tool(tool_id="test", name="Test", description="Test")

        req1 = ConfirmationRequest(
            request_id="req_1",
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test",
            status=ConfirmationStatus.GRANTED,
        )
        req2 = ConfirmationRequest(
            request_id="req_2",
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test",
            status=ConfirmationStatus.DENIED,
        )

        batch = BatchConfirmationRequest(
            batch_id="batch_123",
            user_id="user123",
            requests=[req1, req2],
        )

        assert batch.any_denied()  # nosec B101


class TestConfirmationManager:
    """Tests for ConfirmationManager."""

    def test_manager_initialization(self):
        """Test manager initialization."""
        manager = ConfirmationManager()

        assert manager._default_expiration == 300.0  # nosec B101
        assert len(manager._pending) == 0  # nosec B101
        assert len(manager._completed) == 0  # nosec B101

    def test_manager_with_custom_expiration(self):
        """Test manager with custom default expiration."""
        manager = ConfirmationManager(default_expiration=60.0)

        assert manager._default_expiration == 60.0  # nosec B101

    def test_create_confirmation_request(self):
        """Test creating confirmation request."""
        manager = ConfirmationManager()

        tool = Tool(
            tool_id="delete_file",
            name="Delete File",
            description="Delete a file",
        )

        request = manager.create_confirmation_request(
            user_id="user123",
            tool=tool,
            parameters={"path": "/file.txt"},
            reason="Dangerous operation",
        )

        assert request.user_id == "user123"  # nosec B101
        assert request.tool == tool  # nosec B101
        assert request.parameters == {"path": "/file.txt"}  # nosec B101
        assert request.reason == "Dangerous operation"  # nosec B101
        assert request.status == ConfirmationStatus.PENDING  # nosec B101
        assert request.expires_at is not None  # nosec B101

        # Check it's in pending
        assert request.request_id in manager._pending  # nosec B101

        # Check metrics
        metrics = manager.get_metrics()
        assert metrics.total_requests == 1  # nosec B101
        assert metrics.pending == 1  # nosec B101

    def test_create_confirmation_with_custom_expiration(self):
        """Test creating request with custom expiration."""
        manager = ConfirmationManager()

        tool = Tool(tool_id="test", name="Test", description="Test")

        request = manager.create_confirmation_request(
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test",
            expires_in_seconds=60.0,
        )

        # Should expire in ~60 seconds
        assert request.expires_at is not None  # nosec B101
        assert request.expires_at - time.time() < 61  # nosec B101
        assert request.expires_at - time.time() > 59  # nosec B101

    def test_grant_confirmation(self):
        """Test granting confirmation."""
        manager = ConfirmationManager()

        tool = Tool(tool_id="test", name="Test", description="Test")

        request = manager.create_confirmation_request(
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test",
        )

        # Grant confirmation
        result = manager.grant_confirmation(request.request_id)

        assert result is True  # nosec B101
        assert request.status == ConfirmationStatus.GRANTED  # nosec B101
        assert request.response_at is not None  # nosec B101

        # Should be moved to completed
        assert request.request_id not in manager._pending  # nosec B101
        assert request.request_id in manager._completed  # nosec B101

        # Check metrics
        metrics = manager.get_metrics()
        assert metrics.granted == 1  # nosec B101
        assert metrics.pending == 0  # nosec B101

    def test_deny_confirmation(self):
        """Test denying confirmation."""
        manager = ConfirmationManager()

        tool = Tool(tool_id="test", name="Test", description="Test")

        request = manager.create_confirmation_request(
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test",
        )

        # Deny confirmation
        result = manager.deny_confirmation(request.request_id, reason="User declined")

        assert result is True  # nosec B101
        assert request.status == ConfirmationStatus.DENIED  # nosec B101
        assert request.response_at is not None  # nosec B101
        assert request.metadata["denial_reason"] == "User declined"  # nosec B101

        # Should be moved to completed
        assert request.request_id not in manager._pending  # nosec B101
        assert request.request_id in manager._completed  # nosec B101

        # Check metrics
        metrics = manager.get_metrics()
        assert metrics.denied == 1  # nosec B101
        assert metrics.pending == 0  # nosec B101

    def test_grant_nonexistent_request(self):
        """Test granting nonexistent request."""
        manager = ConfirmationManager()

        result = manager.grant_confirmation("nonexistent")

        assert result is False  # nosec B101

    def test_deny_nonexistent_request(self):
        """Test denying nonexistent request."""
        manager = ConfirmationManager()

        result = manager.deny_confirmation("nonexistent")

        assert result is False  # nosec B101

    def test_grant_expired_request(self):
        """Test granting expired request."""
        manager = ConfirmationManager()

        tool = Tool(tool_id="test", name="Test", description="Test")

        request = manager.create_confirmation_request(
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test",
            expires_in_seconds=0.01,  # Expire in 10ms
        )

        # Wait for expiration
        time.sleep(0.02)

        # Try to grant
        result = manager.grant_confirmation(request.request_id)

        assert result is False  # nosec B101
        assert request.status == ConfirmationStatus.EXPIRED  # nosec B101

        # Check metrics
        metrics = manager.get_metrics()
        assert metrics.expired == 1  # nosec B101
        assert metrics.granted == 0  # nosec B101

    def test_get_pending_confirmations_all(self):
        """Test getting all pending confirmations."""
        manager = ConfirmationManager()

        tool = Tool(tool_id="test", name="Test", description="Test")

        # Create multiple requests
        req1 = manager.create_confirmation_request(
            user_id="user1",
            tool=tool,
            parameters={},
            reason="Test 1",
        )
        req2 = manager.create_confirmation_request(
            user_id="user2",
            tool=tool,
            parameters={},
            reason="Test 2",
        )

        pending = manager.get_pending_confirmations()

        assert len(pending) == 2  # nosec B101
        assert req1 in pending  # nosec B101
        assert req2 in pending  # nosec B101

    def test_get_pending_confirmations_by_user(self):
        """Test getting pending confirmations for specific user."""
        manager = ConfirmationManager()

        tool = Tool(tool_id="test", name="Test", description="Test")

        # Create requests for different users
        req1 = manager.create_confirmation_request(
            user_id="user1",
            tool=tool,
            parameters={},
            reason="Test 1",
        )
        req2 = manager.create_confirmation_request(
            user_id="user2",
            tool=tool,
            parameters={},
            reason="Test 2",
        )

        pending = manager.get_pending_confirmations(user_id="user1")

        assert len(pending) == 1  # nosec B101
        assert req1 in pending  # nosec B101
        assert req2 not in pending  # nosec B101

    def test_create_batch_confirmation(self):
        """Test creating batch confirmation."""
        manager = ConfirmationManager()

        tool1 = Tool(tool_id="tool1", name="Tool 1", description="Test")
        tool2 = Tool(tool_id="tool2", name="Tool 2", description="Test")

        batch = manager.create_batch_confirmation(
            user_id="user123",
            requests=[
                (tool1, {"param1": "value1"}, "Reason 1"),
                (tool2, {"param2": "value2"}, "Reason 2"),
            ],
        )

        assert batch.user_id == "user123"  # nosec B101
        assert len(batch.requests) == 2  # nosec B101
        assert not batch.all_or_nothing  # nosec B101

        # Check individual requests were created
        assert len(manager._pending) == 2  # nosec B101

        # Check metrics
        metrics = manager.get_metrics()
        assert metrics.batch_requests == 1  # nosec B101
        assert metrics.total_requests == 2  # nosec B101

    def test_create_batch_all_or_nothing(self):
        """Test creating all-or-nothing batch."""
        manager = ConfirmationManager()

        tool = Tool(tool_id="test", name="Test", description="Test")

        batch = manager.create_batch_confirmation(
            user_id="user123",
            requests=[
                (tool, {}, "Reason 1"),
                (tool, {}, "Reason 2"),
            ],
            all_or_nothing=True,
        )

        assert batch.all_or_nothing is True  # nosec B101

    def test_get_batch(self):
        """Test getting batch by ID."""
        manager = ConfirmationManager()

        tool = Tool(tool_id="test", name="Test", description="Test")

        batch = manager.create_batch_confirmation(
            user_id="user123",
            requests=[(tool, {}, "Reason")],
        )

        retrieved = manager.get_batch(batch.batch_id)

        assert retrieved == batch  # nosec B101

    def test_get_nonexistent_batch(self):
        """Test getting nonexistent batch."""
        manager = ConfirmationManager()

        result = manager.get_batch("nonexistent")

        assert result is None  # nosec B101

    def test_metrics_average_response_time(self):
        """Test average response time calculation."""
        manager = ConfirmationManager()

        tool = Tool(tool_id="test", name="Test", description="Test")

        # Create and grant first request
        req1 = manager.create_confirmation_request(
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test 1",
        )
        time.sleep(0.01)
        manager.grant_confirmation(req1.request_id)

        # Create and deny second request
        req2 = manager.create_confirmation_request(
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test 2",
        )
        time.sleep(0.01)
        manager.deny_confirmation(req2.request_id)

        metrics = manager.get_metrics()

        # Should have average response time
        assert metrics.average_response_time > 0  # nosec B101

    def test_clear_completed_all(self):
        """Test clearing all completed confirmations."""
        manager = ConfirmationManager()

        tool = Tool(tool_id="test", name="Test", description="Test")

        # Create and complete some requests
        req1 = manager.create_confirmation_request(
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test 1",
        )
        req2 = manager.create_confirmation_request(
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test 2",
        )

        manager.grant_confirmation(req1.request_id)
        manager.deny_confirmation(req2.request_id)

        # Clear completed
        count = manager.clear_completed()

        assert count == 2  # nosec B101
        assert len(manager._completed) == 0  # nosec B101

    def test_clear_completed_older_than(self):
        """Test clearing old completed confirmations."""
        manager = ConfirmationManager()

        tool = Tool(tool_id="test", name="Test", description="Test")

        # Create and complete old request
        req1 = manager.create_confirmation_request(
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test 1",
        )
        manager.grant_confirmation(req1.request_id)

        # Wait a bit
        time.sleep(0.02)

        # Create and complete new request
        req2 = manager.create_confirmation_request(
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test 2",
        )
        manager.grant_confirmation(req2.request_id)

        # Clear only old ones (older than 0.01 seconds)
        count = manager.clear_completed(older_than_seconds=0.01)

        assert count == 1  # nosec B101
        assert len(manager._completed) == 1  # nosec B101
        assert req2.request_id in manager._completed  # nosec B101

    def test_cleanup_expired(self):
        """Test automatic cleanup of expired requests."""
        manager = ConfirmationManager()

        tool = Tool(tool_id="test", name="Test", description="Test")

        # Create request that expires quickly
        req = manager.create_confirmation_request(
            user_id="user123",
            tool=tool,
            parameters={},
            reason="Test",
            expires_in_seconds=0.01,
        )

        # Wait for expiration
        time.sleep(0.02)

        # Get pending (triggers cleanup)
        pending = manager.get_pending_confirmations()

        assert len(pending) == 0  # nosec B101
        assert req.request_id not in manager._pending  # nosec B101
        assert req.request_id in manager._completed  # nosec B101
        assert req.status == ConfirmationStatus.EXPIRED  # nosec B101

        # Check metrics
        metrics = manager.get_metrics()
        assert metrics.expired == 1  # nosec B101
        assert metrics.pending == 0  # nosec B101
