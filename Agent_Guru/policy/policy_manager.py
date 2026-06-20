"""Multi-platform policy manager.

Thin facade over the existing policy components:
  - PolicyEngine (RBAC/ABAC evaluation, audit logging, caching)
  - PermissionManager (grant/revoke/check)
  - confirmation.py (dangerous operation confirmation)
  - safety.py (platform safety rules)

Provides a unified permission + safety API for all platforms.
"""

from __future__ import annotations

import logging
from typing import Any

from Agent_Guru.policy.engine import PolicyEngine
from Agent_Guru.policy.models import (
    PolicyEffect,
    Principal,
    Resource,
)
from Agent_Guru.policy.permissions import PermissionManager
from Agent_Guru.policy.policy_storage import PolicyStorage

logger = logging.getLogger(__name__)


class PolicyManager:
    """Multi-platform policy manager.

    Wraps PolicyEngine and PermissionManager to provide a simple
    check_permission / request_confirmation API for all platforms.

    Example:
        >>> pm = PolicyManager()
        >>> pm.initialize()
        >>> allowed = pm.check_permission("user_1", "files", "delete")
        >>> if pm.requires_confirmation("files", "delete"):
        ...     confirmed = pm.request_confirmation("Delete this file?")

    Performance:
        - Permission check: <1ms (cached), <10ms (uncached)
        - Audit log write: async, non-blocking

    """

    def __init__(
        self,
        db_path: str = ":memory:",
        cache_size: int = 10_000,
        default_ttl: int = 300,
        enable_caching: bool = True,
    ) -> None:
        self._db_path = db_path
        self._cache_size = cache_size
        self._default_ttl = default_ttl
        self._enable_caching = enable_caching
        self._engine: PolicyEngine | None = None
        self._permissions: PermissionManager | None = None
        self._initialized = False

        # Operations that always require explicit confirmation
        self._dangerous_actions = {
            "delete",
            "format",
            "wipe",
            "uninstall",
            "shutdown",
            "reboot",
            "send_message",
            "make_call",
            "purchase",
        }

    def initialize(self) -> None:
        """Initialize policy engine and permission manager."""
        self._engine = PolicyEngine(
            db_path=self._db_path,
            cache_size=self._cache_size,
            default_ttl=self._default_ttl,
            enable_caching=self._enable_caching,
        )
        storage = PolicyStorage(self._db_path)
        self._permissions = PermissionManager(storage=storage)
        self._initialized = True
        logger.info("PolicyManager initialized")

    # ------------------------------------------------------------------
    # Permission checking
    # ------------------------------------------------------------------

    def check_permission(
        self,
        user_id: str,
        resource_id: str,
        action: str,
        context: dict[str, Any] | None = None,
        roles: list[str] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> bool:
        """Check if a user has permission to perform an action on a resource.

        Args:
            user_id: The requesting user's ID.
            resource_id: Target resource identifier.
            action: Requested action (e.g., "read", "delete").
            context: Optional evaluation context (time, location, etc.).
            roles: Optional list of roles for the principal.
            attributes: Optional principal attributes for ABAC.

        Returns:
            True if access is allowed, False otherwise.

        """
        self._ensure_initialized()
        principal = Principal(
            id=user_id,
            roles=roles or [],
            attributes=attributes or {},
        )
        resource = Resource(id=resource_id, type="resource", attributes={})
        decision = self._engine.evaluate_policy(  # type: ignore[union-attr]
            principal=principal,
            resource=resource,
            action=action,
            context=context,
        )
        allowed = decision.effect == PolicyEffect.ALLOW
        logger.debug(
            "Permission check: user=%s resource=%s action=%s → %s",
            user_id,
            resource_id,
            action,
            "ALLOW" if allowed else "DENY",
        )
        return allowed

    def grant_permission(
        self,
        user_id: str,
        resource_id: str,
        actions: list[str],
        conditions: dict[str, Any] | None = None,
    ) -> str:
        """Grant a user permission to perform actions on a resource.

        Returns:
            Policy ID of the created grant.

        """
        self._ensure_initialized()
        return self._permissions.grant(  # type: ignore[union-attr]
            principal_id=user_id,
            resource_id=resource_id,
            actions=actions,
            conditions=conditions,
        )

    def revoke_permission(
        self,
        user_id: str,
        resource_id: str,
        actions: list[str],
    ) -> None:
        """Revoke a user's permission on a resource."""
        self._ensure_initialized()
        self._permissions.revoke(  # type: ignore[union-attr]
            principal_id=user_id,
            resource_id=resource_id,
            actions=actions,
        )

    # ------------------------------------------------------------------
    # Confirmation for dangerous operations
    # ------------------------------------------------------------------

    def requires_confirmation(self, resource_id: str, action: str) -> bool:
        """Return True if this action requires explicit user confirmation.

        Args:
            resource_id: Target resource.
            action: Requested action.

        Returns:
            True if confirmation is required before proceeding.

        """
        return action.lower() in self._dangerous_actions

    def request_confirmation(
        self,
        message: str,
        timeout_seconds: float = 30.0,
    ) -> bool:
        """Request explicit user confirmation for a dangerous operation.

        In production this integrates with the UI confirmation dialog.
        In headless/test mode it defaults to False (deny).

        Args:
            message: Human-readable confirmation prompt.
            timeout_seconds: Seconds to wait before auto-denying.

        Returns:
            True if user confirmed, False if denied or timed out.

        """
        self._ensure_initialized()
        # Delegate to policy confirmation module if available
        try:
            from Agent_Guru.policy.confirmation import ConfirmationDialog

            dialog = ConfirmationDialog(timeout_seconds=timeout_seconds)
            return dialog.ask(message)
        except Exception:
            logger.exception("Confirmation dialog unavailable — defaulting to DENY")
            return False

    # ------------------------------------------------------------------
    # Audit log access
    # ------------------------------------------------------------------

    def get_audit_log(
        self,
        user_id: str | None = None,
        resource_id: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[Any]:
        """Query the audit log for policy decisions.

        Returns:
            List of AuditRecord objects.

        """
        self._ensure_initialized()
        return self._engine.query_audit_logs(  # type: ignore[union-attr]
            principal_id=user_id,
            resource_id=resource_id,
            action=action,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        """Return True if manager has been initialized."""
        return self._initialized

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            msg = "PolicyManager not initialized. Call initialize() first."
            raise RuntimeError(msg)
