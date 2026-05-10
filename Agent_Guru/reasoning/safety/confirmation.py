"""Confirmation flows for sensitive actions."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

from Agent_Guru.reasoning.models.action import Tool

logger = structlog.get_logger(__name__)


class ConfirmationStatus(Enum):
    """Status of confirmation request."""

    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass
class ConfirmationRequest:
    """Request for user confirmation of sensitive action.

    Attributes:
        request_id: Unique identifier for this request
        user_id: User who needs to confirm
        tool: Tool requiring confirmation
        parameters: Tool parameters
        reason: Reason confirmation is required
        created_at: When request was created
        expires_at: When request expires (None = no expiration)
        status: Current status of request
        response_at: When user responded (None if pending)
        metadata: Additional metadata

    """

    request_id: str
    user_id: str
    tool: Tool
    parameters: dict[str, Any]
    reason: str
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    response_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if confirmation request has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def is_pending(self) -> bool:
        """Check if confirmation is still pending."""
        return self.status == ConfirmationStatus.PENDING and not self.is_expired()


@dataclass
class BatchConfirmationRequest:
    """Request for batch confirmation of multiple actions.

    Attributes:
        batch_id: Unique identifier for this batch
        user_id: User who needs to confirm
        requests: List of individual confirmation requests
        created_at: When batch was created
        expires_at: When batch expires (None = no expiration)
        all_or_nothing: If True, all must be confirmed or all denied
        metadata: Additional metadata

    """

    batch_id: str
    user_id: str
    requests: list[ConfirmationRequest]
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    all_or_nothing: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if batch confirmation has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def all_confirmed(self) -> bool:
        """Check if all requests in batch are confirmed."""
        return all(req.status == ConfirmationStatus.GRANTED for req in self.requests)

    def any_denied(self) -> bool:
        """Check if any request in batch is denied."""
        return any(req.status == ConfirmationStatus.DENIED for req in self.requests)


@dataclass
class ConfirmationMetrics:
    """Metrics for confirmation tracking.

    Attributes:
        total_requests: Total confirmation requests
        granted: Number of granted confirmations
        denied: Number of denied confirmations
        expired: Number of expired confirmations
        pending: Number of pending confirmations
        batch_requests: Number of batch confirmation requests
        average_response_time: Average time to respond (seconds)

    """

    total_requests: int = 0
    granted: int = 0
    denied: int = 0
    expired: int = 0
    pending: int = 0
    batch_requests: int = 0
    average_response_time: float = 0.0


class ConfirmationManager:
    """Manager for confirmation flows.

    Handles creation, tracking, and resolution of confirmation requests
    for sensitive actions.

    Time Complexity: O(1) for most operations
    Space Complexity: O(n) where n is number of pending confirmations
    """

    def __init__(self, default_expiration: float = 300.0) -> None:
        """Initialize confirmation manager.

        Args:
            default_expiration: Default expiration time in seconds (5 minutes)

        """
        self._default_expiration = default_expiration

        # Pending confirmations: request_id -> ConfirmationRequest
        self._pending: dict[str, ConfirmationRequest] = {}

        # Completed confirmations (for metrics): request_id -> ConfirmationRequest
        self._completed: dict[str, ConfirmationRequest] = {}

        # Batch confirmations: batch_id -> BatchConfirmationRequest
        self._batches: dict[str, BatchConfirmationRequest] = {}

        # Metrics
        self._metrics = ConfirmationMetrics()

        # Request counter for generating IDs
        self._request_counter = 0

    def create_confirmation_request(
        self,
        user_id: str,
        tool: Tool,
        parameters: dict[str, Any],
        reason: str,
        expires_in_seconds: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConfirmationRequest:
        """Create confirmation request for sensitive action.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            user_id: User who needs to confirm
            tool: Tool requiring confirmation
            parameters: Tool parameters
            reason: Reason confirmation is required
            expires_in_seconds: Expiration time (None = default)
            metadata: Additional metadata

        Returns:
            Created ConfirmationRequest

        """
        # Generate unique request ID
        self._request_counter += 1
        request_id = f"conf_{user_id}_{self._request_counter}_{int(time.time())}"

        # Calculate expiration
        expiration = expires_in_seconds or self._default_expiration
        expires_at = time.time() + expiration

        # Create request
        request = ConfirmationRequest(
            request_id=request_id,
            user_id=user_id,
            tool=tool,
            parameters=parameters,
            reason=reason,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        # Store in pending
        self._pending[request_id] = request

        # Update metrics
        self._metrics.total_requests += 1
        self._metrics.pending += 1

        logger.info(
            "confirmation_request_created",
            request_id=request_id,
            user_id=user_id,
            tool_id=tool.tool_id,
            reason=reason,
            expires_at=expires_at,
        )

        return request

    def create_batch_confirmation(
        self,
        user_id: str,
        requests: list[tuple[Tool, dict[str, Any], str]],
        all_or_nothing: bool = False,
        expires_in_seconds: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> BatchConfirmationRequest:
        """Create batch confirmation request for multiple actions.

        Time Complexity: O(n) where n is number of requests
        Space Complexity: O(n)

        Args:
            user_id: User who needs to confirm
            requests: List of (tool, parameters, reason) tuples
            all_or_nothing: If True, all must be confirmed or all denied
            expires_in_seconds: Expiration time (None = default)
            metadata: Additional metadata

        Returns:
            Created BatchConfirmationRequest

        """
        # Generate unique batch ID
        batch_id = f"batch_{user_id}_{int(time.time())}"

        # Calculate expiration
        expiration = expires_in_seconds or self._default_expiration
        expires_at = time.time() + expiration

        # Create individual confirmation requests
        confirmation_requests = []
        for tool, parameters, reason in requests:
            request = self.create_confirmation_request(
                user_id=user_id,
                tool=tool,
                parameters=parameters,
                reason=reason,
                expires_in_seconds=expiration,
            )
            confirmation_requests.append(request)

        # Create batch
        batch = BatchConfirmationRequest(
            batch_id=batch_id,
            user_id=user_id,
            requests=confirmation_requests,
            expires_at=expires_at,
            all_or_nothing=all_or_nothing,
            metadata=metadata or {},
        )

        # Store batch
        self._batches[batch_id] = batch

        # Update metrics
        self._metrics.batch_requests += 1

        logger.info(
            "batch_confirmation_created",
            batch_id=batch_id,
            user_id=user_id,
            num_requests=len(requests),
            all_or_nothing=all_or_nothing,
            expires_at=expires_at,
        )

        return batch

    def grant_confirmation(self, request_id: str) -> bool:
        """Grant confirmation for request.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            request_id: Request identifier

        Returns:
            True if granted, False if request not found or expired

        """
        request = self._pending.get(request_id)
        if request is None:
            return False

        # Check if expired
        if request.is_expired():
            self._expire_request(request)
            return False

        # Grant confirmation
        request.status = ConfirmationStatus.GRANTED
        request.response_at = time.time()

        # Move to completed
        del self._pending[request_id]
        self._completed[request_id] = request

        # Update metrics
        self._metrics.granted += 1
        self._metrics.pending -= 1

        # Update average response time
        response_time = request.response_at - request.created_at
        total_responses = self._metrics.granted + self._metrics.denied
        self._metrics.average_response_time = (
            self._metrics.average_response_time * (total_responses - 1) + response_time
        ) / total_responses

        logger.info(
            "confirmation_granted",
            request_id=request_id,
            user_id=request.user_id,
            tool_id=request.tool.tool_id,
            response_time=response_time,
        )

        return True

    def deny_confirmation(self, request_id: str, reason: str | None = None) -> bool:
        """Deny confirmation for request.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            request_id: Request identifier
            reason: Optional reason for denial

        Returns:
            True if denied, False if request not found or expired

        """
        request = self._pending.get(request_id)
        if request is None:
            return False

        # Check if expired
        if request.is_expired():
            self._expire_request(request)
            return False

        # Deny confirmation
        request.status = ConfirmationStatus.DENIED
        request.response_at = time.time()
        if reason:
            request.metadata["denial_reason"] = reason

        # Move to completed
        del self._pending[request_id]
        self._completed[request_id] = request

        # Update metrics
        self._metrics.denied += 1
        self._metrics.pending -= 1

        # Update average response time
        response_time = request.response_at - request.created_at
        total_responses = self._metrics.granted + self._metrics.denied
        self._metrics.average_response_time = (
            self._metrics.average_response_time * (total_responses - 1) + response_time
        ) / total_responses

        logger.info(
            "confirmation_denied",
            request_id=request_id,
            user_id=request.user_id,
            tool_id=request.tool.tool_id,
            reason=reason,
            response_time=response_time,
        )

        return True

    def get_pending_confirmations(self, user_id: str | None = None) -> list[ConfirmationRequest]:
        """Get pending confirmation requests.

        Args:
            user_id: Filter by user ID (None for all users)

        Returns:
            List of pending confirmation requests

        """
        # Clean up expired requests first
        self._cleanup_expired()

        if user_id:
            return [req for req in self._pending.values() if req.user_id == user_id]

        return list(self._pending.values())

    def get_batch(self, batch_id: str) -> BatchConfirmationRequest | None:
        """Get batch confirmation request.

        Args:
            batch_id: Batch identifier

        Returns:
            BatchConfirmationRequest or None if not found

        """
        return self._batches.get(batch_id)

    def get_metrics(self) -> ConfirmationMetrics:
        """Get confirmation metrics.

        Returns:
            ConfirmationMetrics with current statistics

        """
        # Clean up expired requests first
        self._cleanup_expired()

        return ConfirmationMetrics(
            total_requests=self._metrics.total_requests,
            granted=self._metrics.granted,
            denied=self._metrics.denied,
            expired=self._metrics.expired,
            pending=self._metrics.pending,
            batch_requests=self._metrics.batch_requests,
            average_response_time=self._metrics.average_response_time,
        )

    def _expire_request(self, request: ConfirmationRequest) -> None:
        """Mark request as expired.

        Args:
            request: Request to expire

        """
        request.status = ConfirmationStatus.EXPIRED

        # Move to completed
        if request.request_id in self._pending:
            del self._pending[request.request_id]
            self._completed[request.request_id] = request

            # Update metrics
            self._metrics.expired += 1
            self._metrics.pending -= 1

            logger.info(
                "confirmation_expired",
                request_id=request.request_id,
                user_id=request.user_id,
                tool_id=request.tool.tool_id,
            )

    def _cleanup_expired(self) -> None:
        """Clean up expired confirmation requests."""
        expired_ids = [
            request_id for request_id, request in self._pending.items() if request.is_expired()
        ]

        for request_id in expired_ids:
            request = self._pending[request_id]
            self._expire_request(request)

    def clear_completed(self, older_than_seconds: float | None = None) -> int:
        """Clear completed confirmation requests.

        Args:
            older_than_seconds: Only clear requests older than this (None = all)

        Returns:
            Number of requests cleared

        """
        if older_than_seconds is None:
            count = len(self._completed)
            self._completed.clear()
            logger.info("completed_confirmations_cleared", count=count)
            return count

        cutoff_time = time.time() - older_than_seconds
        to_remove = [
            request_id
            for request_id, request in self._completed.items()
            if request.created_at < cutoff_time
        ]

        for request_id in to_remove:
            del self._completed[request_id]

        logger.info("completed_confirmations_cleared", count=len(to_remove))
        return len(to_remove)
