"""Policy Engine Integration - Interface for policy constraint enforcement.

This module provides integration hooks for the policy engine to ensure
self-improvement respects governance constraints.

**Integration Points**:
- Policy-aware strategy selection
- Policy validation before prompt evolution
- Constraint enforcement

Author: Agent Guru Team
Date: 2026-02-28
Version: 1.0.0
"""

import logging

logger = logging.getLogger(__name__)

from enum import Enum  # noqa: E402
from typing import Any  # noqa: E402


class PolicyDecision(Enum):
    """Policy decision outcomes."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class PolicyIntegration:
    """Policy engine integration for self-improvement engine.

    This class provides hooks for integrating with the policy engine
    to ensure self-improvement respects governance constraints.

    Time Complexity: O(1) for integration overhead
    Space Complexity: O(1)

    Example:
        >>> from Agent_Guru.self_improvement.self_improvement_engine import SelfImprovementEngine
        >>>
        >>> # Initialize with policy integration
        >>> engine = SelfImprovementEngine("data/learning.db")
        >>> policy_integration = PolicyIntegration(engine)
        >>>
        >>> # Check if strategy is allowed
        >>> decision = policy_integration.check_strategy_policy(
        ...     strategy_id="test_strategy",
        ...     task_type="analysis"
        ... )
        >>>
        >>> if decision == PolicyDecision.ALLOW:
        ...     print("Strategy allowed")

    """

    def __init__(
        self,
        self_improvement_engine: Any,
        policy_engine: Any | None = None,
        enforce_policies: bool = True,
    ) -> None:
        """Initialize policy integration.

        Args:
            self_improvement_engine: SelfImprovementEngine instance
            policy_engine: Optional policy engine instance (placeholder)
            enforce_policies: Whether to enforce policies (default: True)

        Time Complexity: O(1)

        """
        self.engine = self_improvement_engine
        self.policy_engine = policy_engine
        self.enforce_policies = enforce_policies

        # Default policies when no policy engine connected
        self.default_policies = {
            "allow_strategy_changes": True,
            "allow_prompt_evolution": True,
            "require_approval_for_critical": False,
        }

    def check_strategy_policy(
        self,
        strategy_id: str,
        task_type: str,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Check if strategy selection is allowed by policy.

        Queries policy engine to determine if a strategy can be used
        for a given task type.

        Args:
            strategy_id: Strategy to check
            task_type: Task type
            context: Optional context for policy evaluation

        Returns:
            Policy decision (ALLOW, DENY, or REQUIRE_APPROVAL)

        Time Complexity: O(1)
        Performance Target: <5ms

        Validates: Requirement 18.2

        """
        if not self.enforce_policies:
            return PolicyDecision.ALLOW

        if not self.policy_engine:
            # No policy engine - use default policies
            if self.default_policies["allow_strategy_changes"]:
                return PolicyDecision.ALLOW
            return PolicyDecision.DENY

        try:
            # Query policy engine (placeholder)
            # In real implementation, this would call policy_engine.evaluate()

            # For now, allow all strategies
            return PolicyDecision.ALLOW

        except Exception as e:
            logger.warning("Warning: Policy check failed: %s", e)
            # Fail safe - deny on error
            return PolicyDecision.DENY

    def check_prompt_evolution_policy(
        self,
        prompt_type: str,
        current_content: str,
        proposed_content: str,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Check if prompt evolution is allowed by policy.

        Validates that prompt changes comply with governance constraints
        before allowing evolution.

        Args:
            prompt_type: Type of prompt being evolved
            current_content: Current prompt content
            proposed_content: Proposed new prompt content
            context: Optional context for policy evaluation

        Returns:
            Policy decision (ALLOW, DENY, or REQUIRE_APPROVAL)

        Time Complexity: O(1)
        Performance Target: <10ms

        Validates: Requirement 18.3

        """
        if not self.enforce_policies:
            return PolicyDecision.ALLOW

        if not self.policy_engine:
            # No policy engine - use default policies
            if self.default_policies["allow_prompt_evolution"]:
                return PolicyDecision.ALLOW
            return PolicyDecision.DENY

        try:
            # Query policy engine (placeholder)
            # In real implementation, this would call policy_engine.validate_prompt()

            # For now, allow all prompt evolution
            return PolicyDecision.ALLOW

        except Exception as e:
            logger.warning("Warning: Prompt evolution policy check failed: %s", e)
            # Fail safe - deny on error
            return PolicyDecision.DENY

    def get_allowed_strategies(
        self,
        task_type: str,
        context: dict[str, Any] | None = None,
    ) -> list[str]:
        """Get list of strategies allowed by policy for task type.

        Args:
            task_type: Task type
            context: Optional context for policy evaluation

        Returns:
            List of allowed strategy IDs

        Time Complexity: O(n) where n is number of strategies
        Performance Target: <20ms

        Validates: Requirement 18.2

        """
        if not self.enforce_policies:
            # Return all strategies if policies not enforced
            return self._get_all_strategies()

        if not self.policy_engine:
            # No policy engine - return all strategies
            return self._get_all_strategies()

        try:
            # Query policy engine for allowed strategies (placeholder)
            # In real implementation, this would call policy_engine.get_allowed_strategies()

            return self._get_all_strategies()

        except Exception as e:
            logger.warning("Warning: Get allowed strategies failed: %s", e)
            return []

    def _get_all_strategies(self) -> list[str]:
        """Get all registered strategies from engine.

        Returns:
            List of all strategy IDs

        """
        try:
            # Get all strategies from strategy optimizer
            strategies = self.engine.strategy_optimizer.get_all_strategies()
            return [s.strategy_id for s in strategies]
        except Exception as e:
            logger.warning("Warning: Get all strategies failed: %s", e)
            return []

    def set_policy(self, policy_name: str, policy_value: bool) -> None:
        """Set a default policy value.

        Args:
            policy_name: Name of policy to set
            policy_value: Policy value (True/False)

        Time Complexity: O(1)

        """
        if policy_name in self.default_policies:
            self.default_policies[policy_name] = policy_value

    def get_policy_status(self) -> dict[str, Any]:
        """Get policy enforcement status.

        Returns:
            Policy status information

        Time Complexity: O(1)

        """
        return {
            "policy_engine_connected": self.policy_engine is not None,
            "enforce_policies": self.enforce_policies,
            "default_policies": self.default_policies.copy(),
        }


# Integration helper functions


def create_policy_integration(
    self_improvement_engine: Any,
    policy_engine: Any | None = None,
    enforce_policies: bool = True,
) -> PolicyIntegration:
    """Create policy integration for self-improvement engine.

    This is a convenience function that initializes the policy integration
    with proper configuration.

    Args:
        self_improvement_engine: SelfImprovementEngine instance
        policy_engine: Optional policy engine instance
        enforce_policies: Whether to enforce policies

    Returns:
        Configured PolicyIntegration instance

    Example:
        >>> from Agent_Guru.self_improvement.self_improvement_engine import SelfImprovementEngine
        >>>
        >>> engine = SelfImprovementEngine("data/learning.db")
        >>> policy_integration = create_policy_integration(engine)
        >>>
        >>> # Check strategy policy
        >>> decision = policy_integration.check_strategy_policy(
        ...     strategy_id="test_strategy",
        ...     task_type="analysis"
        ... )
        >>> print(f"Decision: {decision}")

    """
    return PolicyIntegration(
        self_improvement_engine=self_improvement_engine,
        policy_engine=policy_engine,
        enforce_policies=enforce_policies,
    )
