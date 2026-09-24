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
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from Agent_Guru.policy.confirmation import ConfirmationHandler, ConfirmationStatus
from Agent_Guru.policy.engine import PolicyEngine
from Agent_Guru.policy.models import (
    PolicyEffect,
    Principal,
    Resource,
)
from Agent_Guru.policy.permissions import PermissionManager

if TYPE_CHECKING:
    from collections.abc import Callable

    from Agent_Guru.policy.confirmation import ConfirmationRequest

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
        on_confirmation_request: Callable[[ConfirmationRequest], None] | None = None,
    ) -> None:
        self._db_path = db_path
        self._cache_size = cache_size
        self._default_ttl = default_ttl
        self._enable_caching = enable_caching
        # BUG FIX: request_confirmation() used to try `from
        # Agent_Guru.policy.confirmation import ConfirmationDialog`, a class
        # that does not exist anywhere in this codebase. That import always
        # raised ImportError, which the broad `except Exception` swallowed,
        # so every confirmation request silently and permanently failed
        # closed (DENY) regardless of what the caller wanted -- it looked
        # like it delegated to a real UI dialog but could never succeed.
        # `on_confirmation_request` lets a real UI layer hook into the
        # confirmation flow (see ConfirmationHandler's on_request callback,
        # which fires synchronously while the request is still PENDING) so
        # request_confirmation() can genuinely resolve to True. Without one
        # registered, behavior is unchanged: fail safe to DENY.
        self._on_confirmation_request = on_confirmation_request
        self._engine: PolicyEngine | None = None
        self._permissions: PermissionManager | None = None
        self._confirmation_handler: ConfirmationHandler | None = None
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
        # BUG FIX: this used to construct a brand new, independent
        # PolicyStorage(self._db_path) here for PermissionManager, separate
        # from the PolicyStorage that PolicyEngine constructs internally for
        # itself (self._engine.storage). For the default db_path=":memory:"
        # (i.e. out of the box), each PolicyStorage(":memory:") opens its own
        # private in-memory SQLite database -- so grant_permission() /
        # revoke_permission() wrote policies into a database that
        # check_permission() could never see, making every grant silently
        # no-op. Reusing self._engine.storage makes both facades operate on
        # the same underlying storage, as the class docstring's example
        # (grant then check) actually requires.
        self._permissions = PermissionManager(storage=self._engine.storage)
        self._confirmation_handler = ConfirmationHandler(
            on_request=self._on_confirmation_request,
        )
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
            roles: Deprecated / currently inert. `Principal` (see models.py)
                only carries `id` and `attributes` -- there is no per-call
                roles field. This parameter is accepted so existing call
                sites keep working, but it has no effect on the decision.
                To make RBAC roles apply, assign them ahead of time via
                `PolicyEngine.create_role()` / `assign_role()`, which are
                looked up from persistent storage during evaluation instead.
            attributes: Optional principal attributes for ABAC.

        Returns:
            True if access is allowed, False otherwise.

        """
        self._ensure_initialized()
        if roles:
            logger.debug(
                "check_permission(roles=%s) ignored: Principal has no roles field; "
                "assign roles via PolicyEngine.assign_role() instead.",
                roles,
            )
        # BUG FIX: this used to pass roles=roles or [] into Principal(...),
        # but Principal only accepts id/attributes -- every call raised
        # TypeError: __init__() got an unexpected keyword argument 'roles',
        # meaning check_permission() could never return successfully.
        principal = Principal(
            id=user_id,
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
        policy_id = self._permissions.grant(  # type: ignore[union-attr]
            principal_id=user_id,
            resource_id=resource_id,
            actions=actions,
            conditions=conditions,
        )
        # PermissionManager writes policies straight to storage (it has no
        # cache reference of its own), which is now the *same* storage
        # PolicyEngine reads from -- so a stale cached decision for this
        # user/resource/action must be evicted or check_permission() could
        # keep returning the pre-grant answer until the cache TTL expires.
        if self._engine and self._engine.cache:
            self._engine.cache.invalidate_for_policy(policy_id)
        return policy_id

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
        # See grant_permission(): same shared-storage cache-invalidation
        # requirement applies to revocation.
        if self._engine and self._engine.cache:
            self._engine.cache.invalidate()

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
        # BUG FIX: this used to `from Agent_Guru.policy.confirmation import
        # ConfirmationDialog` -- no such class exists anywhere in the
        # codebase, so this raised ImportError on every single call. The
        # broad except below caught it and returned False, so the method
        # *looked* like a working "ask the user, fail safe on timeout"
        # dialog but was actually a permanent, silent DENY no matter what.
        #
        # ConfirmationHandler (the class that does exist here) invokes its
        # on_request callback synchronously while the request is still
        # PENDING, so a real UI layer can resolve it (via .approve()/.deny())
        # before this method returns just by registering
        # on_confirmation_request in the PolicyManager constructor. With no
        # such callback registered, get_status() correctly stays PENDING and
        # this still fails safe to DENY -- but now because nothing answered,
        # not because of a broken import to a class that was never written.
        try:
            req = self._confirmation_handler.request_confirmation(  # type: ignore[union-attr]
                principal_id="system",
                resource_id="confirmation",
                action="confirm",
                description=message,
            )
            # Honor this call's timeout override rather than the handler's
            # own default_timeout_seconds.
            req.expires_at = req.created_at + timedelta(seconds=timeout_seconds)
            status = self._confirmation_handler.get_status(req.id)  # type: ignore[union-attr]
        except Exception:
            logger.exception("Confirmation request failed - defaulting to DENY")
            return False
        return status == ConfirmationStatus.APPROVED

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
