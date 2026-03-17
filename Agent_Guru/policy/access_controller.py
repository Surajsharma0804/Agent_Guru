"""
Access Controller - RBAC and ABAC access control decisions.

Combines role-based and attribute-based access control with
conflict resolution and caching.

Performance Characteristics:
    - check_access: O(r * p) where r = roles, p = policies
    - get_effective_permissions: O(r * d) where d = role hierarchy depth

Validates: Requirement 3 (RBAC), Requirement 4 (ABAC)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Set

from Agent_Guru.policy.cache_manager import CacheManager
from Agent_Guru.policy.conflict_resolver import ConflictResolver
from Agent_Guru.policy.models import (
    AccessDecision,
    ConflictStrategy,
    EvaluatedPolicy,
    EvaluationContext,
    Policy,
    PolicyEffect,
    Principal,
    Resource,
    Role,
)
from Agent_Guru.policy.policy_storage import PolicyStorage
from Agent_Guru.policy.rule_evaluator import RuleEvaluator, RuleEvaluationError

logger = logging.getLogger(__name__)

# Maximum role hierarchy depth to prevent infinite loops
MAX_ROLE_DEPTH = 20


class AccessController:
    """Implements RBAC and ABAC access control.

    Validates: Requirements 3.1–3.6, 4.1–4.6
    """

    def __init__(
        self,
        storage: PolicyStorage,
        evaluator: RuleEvaluator,
        resolver: ConflictResolver,
        cache: Optional[CacheManager] = None,
    ) -> None:
        """Initialise the access controller.

        Args:
            storage: Policy and role storage.
            evaluator: Rule evaluator.
            resolver: Conflict resolver.
            cache: Optional cache manager.
        """
        self.storage = storage
        self.evaluator = evaluator
        self.resolver = resolver
        self.cache = cache

    # ------------------------------------------------------------------
    # Main access check
    # ------------------------------------------------------------------

    def check_access(
        self,
        principal: Principal,
        resource: Resource,
        action: str,
        context: Optional[Dict[str, Any]] = None,
        strategy: Optional[ConflictStrategy] = None,
    ) -> AccessDecision:
        """Check if access should be granted.

        Evaluates all applicable policies and resolves conflicts.

        Args:
            principal: The requesting principal.
            resource: The target resource.
            action: The requested action.
            context: Additional context attributes.
            strategy: Conflict resolution strategy override.

        Returns:
            AccessDecision with ALLOW or DENY.

        Validates: Requirements 3.4, 4.1–4.4
        """
        start = time.monotonic()

        eval_context = EvaluationContext(
            principal=principal,
            resource=resource,
            action=action,
            environment=context or {},
        )

        # Check cache
        if self.cache:
            cache_key = CacheManager.compute_cache_key(
                principal.id, resource.id, action, context or {},
                principal.attributes, resource.attributes,
            )
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # Retrieve applicable policies
        policies = self.storage.find_policies(
            principal=principal.id,
            resource=resource.id,
            action=action,
        )

        # Evaluate each policy's conditions
        evaluated: List[EvaluatedPolicy] = []
        memo_cache: Dict[str, bool] = {}

        for policy in policies:
            try:
                conditions_met = self.evaluator.evaluate(
                    policy.conditions, eval_context, memo_cache
                )
            except RuleEvaluationError as exc:
                logger.warning("Rule evaluation error for policy '%s': %s", policy.id, exc)
                conditions_met = False  # Fail-safe: treat as not matching

            evaluated.append(
                EvaluatedPolicy(
                    policy_id=policy.id,
                    effect=policy.effect,
                    priority=policy.priority,
                    conditions_met=conditions_met,
                )
            )

        # Resolve conflicts
        decision_obj = self.resolver.resolve(evaluated, strategy=strategy)

        elapsed_ms = (time.monotonic() - start) * 1000
        decision = AccessDecision(
            effect=decision_obj.effect,
            reason=f"Resolved via {decision_obj.resolution_strategy} "
                   f"(winner: {decision_obj.winning_policy_id or 'none'})",
            applicable_policies=[p.policy_id for p in evaluated if p.conditions_met],
            evaluation_time_ms=elapsed_ms,
        )

        # Store in cache
        if self.cache:
            self.cache.put(cache_key, decision)
        return decision

    # ------------------------------------------------------------------
    # RBAC
    # ------------------------------------------------------------------

    def check_rbac(self, principal: Principal, permission: str) -> bool:
        """Check if a principal has a permission through their roles.

        Traverses the role hierarchy to collect all inherited permissions.

        Validates: Requirements 3.2, 3.3, 3.4
        """
        effective = self.get_effective_permissions(principal)
        return permission in effective or "*" in effective

    def get_effective_permissions(self, principal: Principal) -> Set[str]:
        """Get all permissions for a principal through role hierarchy.

        Validates: Requirements 3.2, 3.3, 3.5
        """
        direct_roles = self.storage.get_principal_roles(principal.id)
        permissions: Set[str] = set()

        for role in direct_roles:
            self._collect_permissions(role, permissions, depth=0)

        return permissions

    def _collect_permissions(
        self, role: Role, permissions: Set[str], depth: int
    ) -> None:
        """Recursively collect permissions from a role and its ancestors."""
        if depth > MAX_ROLE_DEPTH:
            logger.warning("Role hierarchy depth exceeded for role '%s'", role.id)
            return

        permissions.update(role.permissions)

        if role.parent_role_id:
            parent = self.storage.get_role(role.parent_role_id)
            if parent:
                self._collect_permissions(parent, permissions, depth + 1)
