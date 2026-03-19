"""
Data models for the Guru Policy Engine.

Defines all core data structures: Policy, Role, Principal, Resource,
AccessDecision, EvaluationContext, and supporting types.

Validates: Requirement 1 (Policy Definition), Requirement 12 (Python Implementation)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PolicyEffect(str, Enum):
    """Effect of a policy evaluation."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    ABSTAIN = "ABSTAIN"


class ConflictStrategy(str, Enum):
    """Strategy for resolving policy conflicts."""

    DENY_OVERRIDES = "deny-overrides"
    ALLOW_OVERRIDES = "allow-overrides"
    FIRST_APPLICABLE = "first-applicable"
    PRIORITY_BASED = "priority-based"


class MissingAttributeStrategy(str, Enum):
    """Strategy when a required attribute is missing."""

    DENY = "deny"
    ALLOW = "allow"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


@dataclass
class Principal:
    """An entity requesting access to a resource.

    Attributes:
        id: Unique identifier for the principal.
        attributes: Arbitrary key-value attributes (department, clearance_level, etc.).
    """

    id: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Resource:
    """A system entity that requires access control.

    Attributes:
        id: Unique identifier for the resource.
        type: Resource type (file, application, network, etc.).
        attributes: Arbitrary key-value attributes (classification, owner, etc.).
    """

    id: str
    type: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Policy:
    """A policy rule defining allowed or prohibited actions.

    Attributes:
        id: Unique identifier (assigned on storage).
        version: Monotonically increasing version number.
        name: Human-readable policy name.
        description: Policy description.
        effect: ALLOW or DENY.
        priority: Higher value = higher precedence.
        principals: List of principal IDs or wildcards ("*").
        resources: List of resource IDs or wildcards.
        actions: List of action names or wildcards.
        conditions: Rule expression dict (see RuleEvaluator).
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        active: Whether the policy is active.
    """

    id: str
    version: int
    name: str
    description: str
    effect: PolicyEffect
    priority: int
    principals: List[str]
    resources: List[str]
    actions: List[str]
    conditions: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    active: bool = True

    def matches_principal(self, principal_id: str) -> bool:
        """Return True if this policy applies to the given principal."""
        return "*" in self.principals or principal_id in self.principals

    def matches_resource(self, resource_id: str) -> bool:
        """Return True if this policy applies to the given resource."""
        return "*" in self.resources or resource_id in self.resources

    def matches_action(self, action: str) -> bool:
        """Return True if this policy applies to the given action."""
        return "*" in self.actions or action in self.actions

    def applies_to(self, principal_id: str, resource_id: str, action: str) -> bool:
        """Return True if this policy applies to the given request."""
        return (
            self.active
            and self.matches_principal(principal_id)
            and self.matches_resource(resource_id)
            and self.matches_action(action)
        )


@dataclass
class Role:
    """A role with associated permissions.

    Attributes:
        id: Unique identifier.
        name: Human-readable role name (must be unique).
        parent_role_id: Optional parent role for hierarchy.
        permissions: List of permission strings granted by this role.
        created_at: Creation timestamp.
    """

    id: str
    name: str
    permissions: List[str]
    created_at: datetime
    parent_role_id: Optional[str] = None


@dataclass
class EvaluationContext:
    """Context for a policy evaluation request.

    Attributes:
        principal: The requesting principal.
        resource: The target resource.
        action: The requested action.
        environment: Environmental attributes (time, location, system state).
    """

    principal: Principal
    resource: Resource
    action: str
    environment: Dict[str, Any] = field(default_factory=dict)

    def get_attribute(self, path: str) -> Any:
        """Get attribute by dot-notation path.

        Supports paths like:
        - "principal.department"
        - "resource.classification"
        - "environment.time_of_day"

        Args:
            path: Dot-separated attribute path.

        Returns:
            Attribute value or None if not found.
        """
        parts = path.split(".", 1)
        if len(parts) < 2:
            return None

        namespace, key = parts[0], parts[1]
        if namespace == "principal":
            if key == "id":
                return self.principal.id
            return self.principal.attributes.get(key)
        elif namespace == "resource":
            if key == "id":
                return self.resource.id
            if key == "type":
                return self.resource.type
            return self.resource.attributes.get(key)
        elif namespace == "environment":
            return self.environment.get(key)
        return None

    def context_hash(self) -> str:
        """Compute a stable hash of this context for cache keys."""
        data = {
            "principal_id": self.principal.id,
            "principal_attrs": self.principal.attributes,
            "resource_id": self.resource.id,
            "resource_type": self.resource.type,
            "resource_attrs": self.resource.attributes,
            "action": self.action,
            "environment": self.environment,
        }
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()


@dataclass
class AccessDecision:
    """Result of a policy evaluation.

    Attributes:
        effect: ALLOW, DENY, or ABSTAIN.
        reason: Human-readable explanation.
        applicable_policies: IDs of policies that contributed to the decision.
        evaluation_time_ms: Time taken to evaluate in milliseconds.
    """

    effect: PolicyEffect
    reason: str
    applicable_policies: List[str] = field(default_factory=list)
    evaluation_time_ms: float = 0.0


@dataclass
class EvaluatedPolicy:
    """A policy that has been evaluated against a context.

    Attributes:
        policy_id: ID of the evaluated policy.
        effect: The policy's effect.
        priority: The policy's priority.
        conditions_met: Whether the policy's conditions were satisfied.
    """

    policy_id: str
    effect: PolicyEffect
    priority: int
    conditions_met: bool


@dataclass
class PolicyDecision:
    """Result of conflict resolution among multiple evaluated policies.

    Attributes:
        effect: Final resolved effect.
        winning_policy_id: ID of the policy that determined the outcome.
        conflicting_policies: IDs of all conflicting policies.
        resolution_strategy: Strategy used to resolve the conflict.
    """

    effect: PolicyEffect
    winning_policy_id: str
    conflicting_policies: List[str]
    resolution_strategy: str


@dataclass
class AuditRecord:
    """An immutable audit log entry.

    Attributes:
        id: Unique record identifier.
        timestamp: When the decision was made.
        principal_id: ID of the requesting principal.
        resource_id: ID of the target resource.
        resource_type: Type of the target resource.
        action: Requested action.
        effect: Decision effect.
        applicable_policies: JSON-serialized list of policy IDs.
        context_hash: SHA256 of the evaluation context.
        evaluation_time_ms: Evaluation duration.
        decision_reason: Human-readable reason.
    """

    id: str
    timestamp: datetime
    principal_id: str
    resource_id: str
    resource_type: str
    action: str
    effect: PolicyEffect
    applicable_policies: List[str]
    context_hash: str
    evaluation_time_ms: float
    decision_reason: str


@dataclass
class CacheStats:
    """Cache performance statistics.

    Attributes:
        hits: Number of cache hits.
        misses: Number of cache misses.
        evictions: Number of LRU evictions.
        size: Current number of entries.
        hit_rate: Fraction of requests served from cache.
    """

    hits: int
    misses: int
    evictions: int
    size: int

    @property
    def hit_rate(self) -> float:
        """Fraction of requests that were cache hits."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


@dataclass
class TestCase:
    """A policy test case with expected outcome.

    Attributes:
        name: Test case name.
        principal: Test principal.
        resource: Test resource.
        action: Test action.
        context: Additional context attributes.
        expected_effect: Expected policy effect.
    """

    name: str
    principal: Principal
    resource: Resource
    action: str
    context: Dict[str, Any]
    expected_effect: PolicyEffect


@dataclass
class TestFailure:
    """A failed test case.

    Attributes:
        test_case: The failing test case.
        expected: Expected effect string.
        actual: Actual effect string.
        reason: Reason for the decision.
    """

    test_case: TestCase
    expected: str
    actual: str
    reason: str


@dataclass
class TestResults:
    """Results of running policy test cases.

    Attributes:
        passed: Number of passing test cases.
        failed: Number of failing test cases.
        failures: Details of each failure.
    """

    passed: int
    failed: int
    failures: List[TestFailure] = field(default_factory=list)
