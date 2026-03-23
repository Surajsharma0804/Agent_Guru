"""
Policy Engine - Main facade orchestrating all policy components.

Validates: All policy requirements (1-10, 12)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Optional

from Agent_Guru.policy.access_controller import AccessController
from Agent_Guru.policy.audit_logger import AuditLogger
from Agent_Guru.policy.cache_manager import CacheManager
from Agent_Guru.policy.conflict_resolver import ConflictResolver
from Agent_Guru.policy.models import (
    AccessDecision,
    AuditRecord,
    CacheStats,
    ConflictStrategy,
    MissingAttributeStrategy,
    Policy,
    Principal,
    Resource,
    Role,
    TestCase,
    TestFailure,
    TestResults,
)
from Agent_Guru.policy.policy_storage import PolicyStorage
from Agent_Guru.policy.rule_evaluator import RuleEvaluator

logger = logging.getLogger(__name__)


class PolicyEngine:
    """Main policy engine facade.

    Orchestrates: PolicyStorage, RuleEvaluator, AccessController,
    ConflictResolver, AuditLogger, CacheManager.

    Validates: Requirements 10.1, 10.2, 12
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        audit_db_path: Optional[str] = None,
        cache_size: int = 10_000,
        default_ttl: int = 300,
        enable_caching: bool = True,
        enable_memoization: bool = True,
        default_strategy: ConflictStrategy = ConflictStrategy.DENY_OVERRIDES,
        missing_attribute_strategy: MissingAttributeStrategy = MissingAttributeStrategy.DENY,
        retention_days: int = 90,
    ) -> None:
        self.storage = PolicyStorage(db_path)
        self.audit_logger = AuditLogger(
            db_path=audit_db_path or db_path,
            retention_days=retention_days,
        )
        self.cache: Optional[CacheManager] = (
            CacheManager(max_size=cache_size, default_ttl=default_ttl)
            if enable_caching
            else None
        )
        self.evaluator = RuleEvaluator(
            enable_memoization=enable_memoization,
            missing_attribute_strategy=missing_attribute_strategy,
        )
        self.resolver = ConflictResolver(default_strategy=default_strategy)
        self.controller = AccessController(
            storage=self.storage,
            evaluator=self.evaluator,
            resolver=self.resolver,
            cache=self.cache,
        )
        self._decision_listeners: list[Callable[[dict[str, Any]], None]] = []

    def evaluate_policy(
        self,
        principal: Principal,
        resource: Resource,
        action: str,
        context: Optional[dict[str, Any]] = None,
        strategy: Optional[ConflictStrategy] = None,
        test_mode: bool = False,
        dry_run: bool = False,
    ) -> AccessDecision:
        """Evaluate policy and return access decision.

        Validates: Requirements 9.1, 9.4, 10.1
        """
        decision = self.controller.check_access(
            principal=principal,
            resource=resource,
            action=action,
            context=context,
            strategy=strategy,
        )

        if not test_mode and not dry_run:
            try:
                self.audit_logger.log_decision(
                    principal_id=principal.id,
                    resource_id=resource.id,
                    resource_type=resource.type,
                    action=action,
                    decision=decision,
                    context=context or {},
                )
            except Exception as exc:
                logger.warning("Audit log write failed: %s", exc)

        # Emit decision event to all registered listeners. Validates: Requirement 10.6
        if self._decision_listeners:
            event: dict[str, Any] = {
                "principal_id": principal.id,
                "resource_id": resource.id,
                "action": action,
                "effect": decision.effect.value,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "applicable_policies": decision.applicable_policies,
                "evaluation_time_ms": decision.evaluation_time_ms,
            }
            for listener in self._decision_listeners:
                try:
                    listener(event)
                except Exception as exc:
                    logger.warning("Decision listener error: %s", exc)

        return decision

    async def evaluate_policy_async(
        self,
        principal: Principal,
        resource: Resource,
        action: str,
        context: Optional[dict[str, Any]] = None,
        strategy: Optional[ConflictStrategy] = None,
        test_mode: bool = False,
    ) -> AccessDecision:
        """Async version of evaluate_policy. Validates: Requirement 10.2"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.evaluate_policy(
                principal, resource, action, context, strategy, test_mode
            ),
        )

    def create_policy(self, policy: Policy) -> str:
        """Create a new policy. Validates: Requirement 1.1"""
        policy_id = self.storage.create_policy(policy)
        if self.cache:
            self.cache.invalidate_for_policy(policy_id)
        return policy_id

    def update_policy(self, policy: Policy) -> None:
        """Update an existing policy. Validates: Requirements 1.5, 3.6"""
        self.storage.update_policy(policy)
        if self.cache:
            self.cache.invalidate_for_policy(policy.id)

    def delete_policy(self, policy_id: str) -> None:
        """Soft-delete a policy. Validates: Requirement 1.1"""
        self.storage.delete_policy(policy_id)
        if self.cache:
            self.cache.invalidate_for_policy(policy_id)

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Retrieve a policy by ID."""
        return self.storage.get_policy(policy_id)

    def find_policies(
        self,
        principal: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
    ) -> list[Policy]:
        """Find policies matching criteria. Validates: Requirement 1.6"""
        return self.storage.find_policies(principal=principal, resource=resource, action=action)

    def create_role(self, role: Role) -> str:
        """Create a new role. Validates: Requirement 3.1"""
        return self.storage.create_role(role)

    def assign_role(self, principal_id: str, role_id: str) -> None:
        """Assign a role to a principal. Validates: Requirements 3.2, 3.6"""
        self.storage.assign_role(principal_id, role_id)
        if self.cache:
            self.cache.invalidate()

    def revoke_role(self, principal_id: str, role_id: str) -> None:
        """Revoke a role from a principal."""
        self.storage.revoke_role(principal_id, role_id)
        if self.cache:
            self.cache.invalidate()

    def check_rbac(self, principal: Principal, permission: str) -> bool:
        """Check RBAC permission through role hierarchy. Validates: Requirement 3.4"""
        return self.controller.check_rbac(principal, permission)

    def test_policy(self, policy: Policy, test_cases: list[TestCase]) -> TestResults:
        """Test a policy against test cases without side effects.

        Validates: Requirements 9.1-9.3, 9.5
        """
        original = self.storage.get_policy(policy.id)
        if original:
            self.storage.update_policy(policy)
        else:
            self.storage.create_policy(policy)

        passed = 0
        failures: list[TestFailure] = []

        for tc in test_cases:
            decision = self.evaluate_policy(
                principal=tc.principal,
                resource=tc.resource,
                action=tc.action,
                context=tc.context,
                test_mode=True,
            )
            if decision.effect == tc.expected_effect:
                passed += 1
            else:
                failures.append(
                    TestFailure(
                        test_case=tc,
                        expected=tc.expected_effect.value,
                        actual=decision.effect.value,
                        reason=decision.reason,
                    )
                )

        if original:
            self.storage.update_policy(original)
        else:
            self.storage.delete_policy(policy.id)

        return TestResults(passed=passed, failed=len(failures), failures=failures)

    def query_audit_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        principal_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        effect: Optional[str] = None,
        limit: int = 1000,
    ) -> list[AuditRecord]:
        """Query audit logs. Validates: Requirement 6.3"""
        return self.audit_logger.query_logs(
            start_time=start_time,
            end_time=end_time,
            principal_id=principal_id,
            resource_id=resource_id,
            action=action,
            effect=effect,
            limit=limit,
        )

    def get_cache_stats(self) -> Optional[CacheStats]:
        """Return cache statistics. Validates: Requirement 7.6"""
        return self.cache.get_stats() if self.cache else None

    def flush_cache(self) -> int:
        """Flush all cache entries."""
        if self.cache:
            return self.cache.invalidate()
        return 0

    def on_decision(self, listener: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback invoked after every policy decision.

        The callback receives a dict with keys:
        principal_id, resource_id, action, effect, timestamp,
        applicable_policies, evaluation_time_ms.

        Validates: Requirement 10.6
        """
        self._decision_listeners.append(listener)
