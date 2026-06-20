"""Permission Manager - Grant, revoke, and check fine-grained permissions.

Provides a high-level API over the RBAC/ABAC system for managing
explicit permission grants on specific resources.

Validates: Requirement 4 (ABAC), Requirement 3 (RBAC)
"""

from __future__ import annotations

import html
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from Agent_Guru.policy.access_controller import AccessController
from Agent_Guru.policy.conflict_resolver import ConflictResolver
from Agent_Guru.policy.models import (
    ConflictStrategy,
    MissingAttributeStrategy,
    Policy,
    PolicyEffect,
    Principal,
    Resource,
)
from Agent_Guru.policy.rule_evaluator import RuleEvaluator

if TYPE_CHECKING:
    from Agent_Guru.policy.policy_storage import PolicyStorage

logger = logging.getLogger(__name__)


class PermissionManager:
    """Manages explicit permission grants for principals on resources.

    Wraps PolicyStorage + AccessController to provide a simple
    grant/revoke/check API without requiring callers to construct
    full Policy objects.

    Validates: Requirements 3.1–3.6, 4.1–4.6
    """

    def __init__(
        self,
        storage: PolicyStorage,
        missing_attribute_strategy: MissingAttributeStrategy = MissingAttributeStrategy.DENY,
    ) -> None:
        self.storage = storage
        self._evaluator = RuleEvaluator(missing_attribute_strategy=missing_attribute_strategy)
        self._resolver = ConflictResolver(default_strategy=ConflictStrategy.DENY_OVERRIDES)
        self._controller = AccessController(
            storage=storage,
            evaluator=self._evaluator,
            resolver=self._resolver,
        )

    # ------------------------------------------------------------------
    # Permission grant / revoke
    # ------------------------------------------------------------------

    def grant(
        self,
        principal_id: str,
        resource_id: str,
        actions: list[str],
        conditions: dict[str, Any] | None = None,
        priority: int = 0,
        name: str | None = None,
    ) -> str:
        """Grant a principal permission to perform actions on a resource.

        Creates an ALLOW policy scoped to the given principal and resource.

        Args:
            principal_id: Principal to grant access to.
            resource_id: Resource to grant access on.
            actions: List of allowed actions (use ["*"] for all).
            conditions: Optional attribute conditions.
            priority: Policy priority (higher wins in priority-based resolution).
            name: Human-readable policy name.

        Returns:
            ID of the created policy.

        """
        policy_id = f"perm:{html.escape(principal_id)}:{html.escape(resource_id)}:{':'.join(sorted(actions))}"
        policy = Policy(
            id=policy_id,
            version=1,
            name=name
            or f"Grant {html.escape(principal_id)} on {html.escape(resource_id)}",
            description="Auto-generated permission grant",
            effect=PolicyEffect.ALLOW,
            priority=priority,
            principals=[principal_id],
            resources=[resource_id],
            actions=actions,
            conditions=conditions or {},
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
            active=True,
        )
        existing = self.storage.get_policy(policy_id)
        if existing:
            self.storage.update_policy(policy)
        else:
            self.storage.create_policy(policy)
        return policy_id

    def deny(
        self,
        principal_id: str,
        resource_id: str,
        actions: list[str],
        conditions: dict[str, Any] | None = None,
        priority: int = 100,
        name: str | None = None,
    ) -> str:
        """Explicitly deny a principal from performing actions on a resource.

        Creates a DENY policy scoped to the given principal and resource.

        Args:
            principal_id: Principal to deny.
            resource_id: Resource to deny access on.
            actions: List of denied actions.
            conditions: Optional attribute conditions.
            priority: Policy priority (default high so denies win).
            name: Human-readable policy name.

        Returns:
            ID of the created policy.

        """
        policy_id = f"deny:{html.escape(principal_id)}:{html.escape(resource_id)}:{':'.join(sorted(actions))}"
        policy = Policy(
            id=policy_id,
            version=1,
            name=name
            or f"Deny {html.escape(principal_id)} on {html.escape(resource_id)}",
            description="Auto-generated permission denial",
            effect=PolicyEffect.DENY,
            priority=priority,
            principals=[principal_id],
            resources=[resource_id],
            actions=actions,
            conditions=conditions or {},
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
            active=True,
        )
        existing = self.storage.get_policy(policy_id)
        if existing:
            self.storage.update_policy(policy)
        else:
            self.storage.create_policy(policy)
        return policy_id

    def revoke(self, principal_id: str, resource_id: str, actions: list[str]) -> None:
        """Revoke a previously granted permission.

        Args:
            principal_id: Principal whose permission to revoke.
            resource_id: Resource to revoke access on.
            actions: Actions to revoke.

        """
        policy_id = f"perm:{principal_id}:{resource_id}:{':'.join(sorted(actions))}"
        self.storage.delete_policy(policy_id)

    # ------------------------------------------------------------------
    # Permission check
    # ------------------------------------------------------------------

    def check(
        self,
        principal: Principal,
        resource: Resource,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Check if a principal has permission to perform an action on a resource.

        Args:
            principal: The requesting principal.
            resource: The target resource.
            action: The requested action.
            context: Optional evaluation context.

        Returns:
            True if access is allowed, False otherwise.

        """
        decision = self._controller.check_access(
            principal=principal,
            resource=resource,
            action=action,
            context=context,
        )
        return decision.effect == PolicyEffect.ALLOW

    def get_allowed_actions(
        self,
        principal: Principal,
        resource: Resource,
        candidate_actions: list[str] | None = None,
    ) -> set[str]:
        """Return the set of actions a principal is allowed on a resource.

        Args:
            principal: The requesting principal.
            resource: The target resource.
            candidate_actions: Actions to check (defaults to common set).

        Returns:
            Set of allowed action strings.

        """
        if candidate_actions is None:
            candidate_actions = ["read", "write", "delete", "execute", "admin"]

        allowed: set[str] = set()
        for action in candidate_actions:
            if self.check(principal, resource, action):
                allowed.add(action)
        return allowed
