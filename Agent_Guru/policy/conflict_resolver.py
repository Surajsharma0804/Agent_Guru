"""
Conflict Resolver - Resolves conflicts when multiple policies apply.

Supports four strategies:
- deny-overrides: Any DENY wins over all ALLOWs
- allow-overrides: Any ALLOW wins over all DENYs
- first-applicable: First matching policy wins (by list order)
- priority-based: Highest priority value wins

Validates: Requirement 5 (Conflict Resolution)
"""

from __future__ import annotations

import logging
from typing import Optional

from Agent_Guru.policy.models import (
    ConflictStrategy,
    EvaluatedPolicy,
    PolicyDecision,
    PolicyEffect,
)

logger = logging.getLogger(__name__)


class ConflictResolver:
    """Resolves conflicts among multiple evaluated policies.

    Time Complexity: O(n) where n is number of applicable policies
    Space Complexity: O(n)

    Validates: Requirements 5.1–5.6
    """

    def __init__(
        self,
        default_strategy: ConflictStrategy = ConflictStrategy.DENY_OVERRIDES,
    ) -> None:
        """Initialise the conflict resolver.

        Args:
            default_strategy: Default strategy when none is specified per-call.
        """
        self.default_strategy = default_strategy

    def resolve(
        self,
        policies: list[EvaluatedPolicy],
        strategy: Optional[ConflictStrategy] = None,
    ) -> PolicyDecision:
        """Resolve conflicts among evaluated policies.

        Only policies where conditions_met=True are considered.

        Args:
            policies: List of evaluated policies.
            strategy: Override strategy for this call.

        Returns:
            PolicyDecision with the resolved effect.
        """
        active = [p for p in policies if p.conditions_met]

        if not active:
            # No applicable policies → default deny (fail-safe)
            return PolicyDecision(
                effect=PolicyEffect.DENY,
                winning_policy_id="",
                conflicting_policies=[],
                resolution_strategy=(strategy or self.default_strategy).value,
            )

        used_strategy = strategy or self.default_strategy

        if used_strategy == ConflictStrategy.DENY_OVERRIDES:
            decision = self._deny_overrides(active)
        elif used_strategy == ConflictStrategy.ALLOW_OVERRIDES:
            decision = self._allow_overrides(active)
        elif used_strategy == ConflictStrategy.FIRST_APPLICABLE:
            decision = self._first_applicable(active)
        else:  # PRIORITY_BASED
            decision = self._priority_based(active)

        decision.resolution_strategy = used_strategy.value

        if len(active) > 1:
            logger.debug(
                "Conflict resolved: %d policies → %s via %s (winner: %s)",
                len(active),
                decision.effect.value,
                used_strategy.value,
                decision.winning_policy_id,
            )

        return decision

    # ------------------------------------------------------------------
    # Strategies
    # ------------------------------------------------------------------

    def _deny_overrides(self, policies: list[EvaluatedPolicy]) -> PolicyDecision:
        """Any DENY overrides all ALLOWs. Validates: Req 5.3, 5.6"""
        deny_policies = [p for p in policies if p.effect == PolicyEffect.DENY]
        allow_policies = [p for p in policies if p.effect == PolicyEffect.ALLOW]

        if deny_policies:
            winner = max(deny_policies, key=lambda p: p.priority)
            return PolicyDecision(
                effect=PolicyEffect.DENY,
                winning_policy_id=winner.policy_id,
                conflicting_policies=[p.policy_id for p in policies],
                resolution_strategy=ConflictStrategy.DENY_OVERRIDES.value,
            )

        if allow_policies:
            winner = max(allow_policies, key=lambda p: p.priority)
            return PolicyDecision(
                effect=PolicyEffect.ALLOW,
                winning_policy_id=winner.policy_id,
                conflicting_policies=[p.policy_id for p in policies],
                resolution_strategy=ConflictStrategy.DENY_OVERRIDES.value,
            )

        return self._abstain(policies)

    def _allow_overrides(self, policies: list[EvaluatedPolicy]) -> PolicyDecision:
        """Any ALLOW overrides all DENYs. Validates: Req 5.3"""
        allow_policies = [p for p in policies if p.effect == PolicyEffect.ALLOW]
        deny_policies = [p for p in policies if p.effect == PolicyEffect.DENY]

        if allow_policies:
            winner = max(allow_policies, key=lambda p: p.priority)
            return PolicyDecision(
                effect=PolicyEffect.ALLOW,
                winning_policy_id=winner.policy_id,
                conflicting_policies=[p.policy_id for p in policies],
                resolution_strategy=ConflictStrategy.ALLOW_OVERRIDES.value,
            )

        if deny_policies:
            winner = max(deny_policies, key=lambda p: p.priority)
            return PolicyDecision(
                effect=PolicyEffect.DENY,
                winning_policy_id=winner.policy_id,
                conflicting_policies=[p.policy_id for p in policies],
                resolution_strategy=ConflictStrategy.ALLOW_OVERRIDES.value,
            )

        return self._abstain(policies)

    def _first_applicable(self, policies: list[EvaluatedPolicy]) -> PolicyDecision:
        """First matching policy wins (list order). Validates: Req 5.3"""
        winner = policies[0]
        return PolicyDecision(
            effect=winner.effect,
            winning_policy_id=winner.policy_id,
            conflicting_policies=[p.policy_id for p in policies],
            resolution_strategy=ConflictStrategy.FIRST_APPLICABLE.value,
        )

    def _priority_based(self, policies: list[EvaluatedPolicy]) -> PolicyDecision:
        """Highest priority wins. Validates: Req 5.2"""
        winner = max(policies, key=lambda p: p.priority)
        return PolicyDecision(
            effect=winner.effect,
            winning_policy_id=winner.policy_id,
            conflicting_policies=[p.policy_id for p in policies],
            resolution_strategy=ConflictStrategy.PRIORITY_BASED.value,
        )

    @staticmethod
    def _abstain(policies: list[EvaluatedPolicy]) -> PolicyDecision:
        """No applicable policies — default deny."""
        return PolicyDecision(
            effect=PolicyEffect.DENY,
            winning_policy_id="",
            conflicting_policies=[p.policy_id for p in policies],
            resolution_strategy="abstain",
        )
