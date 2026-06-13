"""Confirmation Handler - Request and track user confirmations for sensitive operations.

Manages confirmation policies: which operations require user confirmation,
tracks pending confirmations, and records confirmation outcomes.

Validates: Requirement 11 (User Confirmation Policies)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class ConfirmationStatus(str, Enum):
    """Status of a confirmation request."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class ConfirmationRequest:
    """A pending confirmation request for a sensitive operation.

    Attributes:
        id: Unique request identifier.
        principal_id: Principal requesting the operation.
        resource_id: Target resource.
        action: Requested action.
        description: Human-readable description of the operation.
        context: Additional context for the confirmation prompt.
        status: Current status.
        created_at: When the request was created.
        expires_at: When the request expires.
        resolved_at: When the request was resolved (approved/denied).
        resolution_reason: Optional reason for the resolution.

    """

    id: str
    principal_id: str
    resource_id: str
    action: str
    description: str
    context: dict[str, Any]
    status: ConfirmationStatus
    created_at: datetime
    expires_at: datetime
    resolved_at: datetime | None = None
    resolution_reason: str | None = None


@dataclass
class ConfirmationPolicy:
    """Policy defining which operations require confirmation.

    Attributes:
        id: Unique policy identifier.
        name: Human-readable name.
        principals: Principal IDs or wildcards that trigger confirmation.
        resources: Resource IDs or wildcards that trigger confirmation.
        actions: Actions that trigger confirmation.
        description_template: Template for the confirmation prompt.
        timeout_seconds: How long to wait for confirmation (default 60s).
        active: Whether this policy is active.

    """

    id: str
    name: str
    principals: list[str]
    resources: list[str]
    actions: list[str]
    description_template: str = "Confirm operation: {action} on {resource_id}"
    timeout_seconds: int = 60
    active: bool = True

    def matches(self, principal_id: str, resource_id: str, action: str) -> bool:
        """Return True if this policy applies to the given request."""
        principal_match = "*" in self.principals or principal_id in self.principals
        resource_match = "*" in self.resources or resource_id in self.resources
        action_match = "*" in self.actions or action in self.actions
        return self.active and principal_match and resource_match and action_match


class ConfirmationHandler:
    """Manages confirmation requests for sensitive operations.

    Tracks pending confirmations and provides hooks for UI integration.

    Validates: Requirement 11
    """

    def __init__(
        self,
        default_timeout_seconds: int = 60,
        on_request: Callable[[ConfirmationRequest], None] | None = None,
    ) -> None:
        """Initialise the confirmation handler.

        Args:
            default_timeout_seconds: Default timeout for confirmation requests.
            on_request: Optional callback invoked when a new confirmation is needed.

        """
        self.default_timeout_seconds = default_timeout_seconds
        self._on_request = on_request
        self._policies: dict[str, ConfirmationPolicy] = {}
        self._pending: dict[str, ConfirmationRequest] = {}

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def add_policy(self, policy: ConfirmationPolicy) -> None:
        """Register a confirmation policy."""
        self._policies[policy.id] = policy

    def remove_policy(self, policy_id: str) -> None:
        """Remove a confirmation policy."""
        self._policies.pop(policy_id, None)

    # ------------------------------------------------------------------
    # Confirmation flow
    # ------------------------------------------------------------------

    def requires_confirmation(self, principal_id: str, resource_id: str, action: str) -> bool:
        """Return True if the operation requires user confirmation."""
        return any(p.matches(principal_id, resource_id, action) for p in self._policies.values())

    def request_confirmation(
        self,
        principal_id: str,
        resource_id: str,
        action: str,
        context: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> ConfirmationRequest:
        """Create a new confirmation request.

        Args:
            principal_id: Principal requesting the operation.
            resource_id: Target resource.
            action: Requested action.
            context: Additional context for the prompt.
            description: Override for the confirmation description.

        Returns:
            The created ConfirmationRequest (status=PENDING).

        """
        # Find matching policy for timeout / description template
        matching = next(
            (p for p in self._policies.values() if p.matches(principal_id, resource_id, action)),
            None,
        )
        timeout = matching.timeout_seconds if matching else self.default_timeout_seconds
        ctx = context or {}

        if description is None and matching:
            description = matching.description_template.format(
                action=action,
                resource_id=resource_id,
                principal_id=principal_id,
                **ctx,
            )
        description = description or f"Confirm: {action} on {resource_id}"

        now = datetime.now(tz=UTC)
        req = ConfirmationRequest(
            id=str(uuid.uuid4()),
            principal_id=principal_id,
            resource_id=resource_id,
            action=action,
            description=description,
            context=ctx,
            status=ConfirmationStatus.PENDING,
            created_at=now,
            expires_at=now + timedelta(seconds=timeout),
        )
        self._pending[req.id] = req

        if self._on_request:
            try:
                self._on_request(req)
            except Exception:
                logger.exception("on_request callback error")

        return req

    def approve(self, request_id: str, reason: str | None = None) -> bool:
        """Approve a pending confirmation request.

        Args:
            request_id: ID of the request to approve.
            reason: Optional reason for approval.

        Returns:
            True if approved, False if not found or already resolved.

        """
        return self._resolve(request_id, ConfirmationStatus.APPROVED, reason)

    def deny(self, request_id: str, reason: str | None = None) -> bool:
        """Deny a pending confirmation request.

        Args:
            request_id: ID of the request to deny.
            reason: Optional reason for denial.

        Returns:
            True if denied, False if not found or already resolved.

        """
        return self._resolve(request_id, ConfirmationStatus.DENIED, reason)

    def cancel(self, request_id: str) -> bool:
        """Cancel a pending confirmation request."""
        return self._resolve(request_id, ConfirmationStatus.CANCELLED, None)

    def get_status(self, request_id: str) -> ConfirmationStatus | None:
        """Return the current status of a confirmation request.

        Automatically marks expired requests.
        """
        req = self._pending.get(request_id)
        if req is None:
            return None
        if req.status == ConfirmationStatus.PENDING and datetime.now(tz=UTC) > req.expires_at:
            req.status = ConfirmationStatus.EXPIRED
            req.resolved_at = datetime.now(tz=UTC)
        return req.status

    def get_pending(self, principal_id: str | None = None) -> list[ConfirmationRequest]:
        """Return all pending (non-expired) confirmation requests.

        Args:
            principal_id: Filter by principal (None = all principals).

        """
        now = datetime.now(tz=UTC)
        result = []
        for req in self._pending.values():
            if req.status == ConfirmationStatus.PENDING:
                if now > req.expires_at:
                    req.status = ConfirmationStatus.EXPIRED
                    req.resolved_at = now
                    continue
                if principal_id is None or req.principal_id == principal_id:
                    result.append(req)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(
        self,
        request_id: str,
        status: ConfirmationStatus,
        reason: str | None,
    ) -> bool:
        req = self._pending.get(request_id)
        if req is None or req.status != ConfirmationStatus.PENDING:
            return False
        req.status = status
        req.resolved_at = datetime.now(tz=UTC)
        req.resolution_reason = reason
        return True
