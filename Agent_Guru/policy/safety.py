"""
Safety Policy Engine - Detect and prevent dangerous operations.

Provides a dedicated safety layer that runs before standard policy
evaluation to block operations that could harm the system or data.

Validates: Requirement 5 (Safety Policies), Requirement 6 (Audit)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from Agent_Guru.policy.models import AccessDecision, PolicyEffect, Principal, Resource

logger = logging.getLogger(__name__)


@dataclass
class SafetyRule:
    """A rule that identifies a dangerous operation.

    Attributes:
        id: Unique rule identifier.
        name: Human-readable name.
        description: Why this operation is dangerous.
        resource_patterns: Regex patterns matched against resource IDs.
        action_patterns: Regex patterns matched against action names.
        severity: Severity level ("critical", "high", "medium", "low").
        active: Whether this rule is enforced.
    """

    id: str
    name: str
    description: str
    resource_patterns: List[str]
    action_patterns: List[str]
    severity: str = "high"
    active: bool = True

    def matches(self, resource_id: str, action: str) -> bool:
        """Return True if this rule matches the given resource and action."""
        if not self.active:
            return False
        resource_match = any(
            re.search(p, resource_id, re.IGNORECASE) for p in self.resource_patterns
        )
        action_match = any(
            re.search(p, action, re.IGNORECASE) for p in self.action_patterns
        )
        return resource_match and action_match


@dataclass
class SafetyViolation:
    """Details of a safety rule violation.

    Attributes:
        rule_id: ID of the violated rule.
        rule_name: Name of the violated rule.
        severity: Severity of the violation.
        description: Why the operation was blocked.
        resource_id: Resource that triggered the violation.
        action: Action that triggered the violation.
    """

    rule_id: str
    rule_name: str
    severity: str
    description: str
    resource_id: str
    action: str


# ---------------------------------------------------------------------------
# Built-in dangerous operation rules
# ---------------------------------------------------------------------------

BUILTIN_SAFETY_RULES: List[SafetyRule] = [
    SafetyRule(
        id="safety:format-drive",
        name="Block Format Drive",
        description="Formatting a drive destroys all data irreversibly.",
        resource_patterns=[r"drive", r"disk", r"volume", r"partition"],
        action_patterns=[r"format", r"wipe", r"erase"],
        severity="critical",
    ),
    SafetyRule(
        id="safety:system-shutdown",
        name="Block Unconfirmed Shutdown",
        description="System shutdown/restart without confirmation.",
        resource_patterns=[r"system", r"os", r"computer"],
        action_patterns=[r"shutdown", r"reboot", r"restart", r"halt", r"poweroff"],
        severity="high",
    ),
    SafetyRule(
        id="safety:delete-system-files",
        name="Block System File Deletion",
        description="Deleting system files can render the OS unbootable.",
        resource_patterns=[r"(^|/)system32", r"(^|/)windows", r"(^|/)etc/", r"(^|/)boot"],
        action_patterns=[r"delete", r"remove", r"rm", r"unlink"],
        severity="critical",
    ),
    SafetyRule(
        id="safety:root-privilege-escalation",
        name="Block Privilege Escalation",
        description="Escalating to root/admin without explicit authorization.",
        resource_patterns=[r".*"],
        action_patterns=[r"sudo", r"runas", r"escalate", r"elevate"],
        severity="critical",
    ),
    SafetyRule(
        id="safety:mass-delete",
        name="Block Mass Deletion",
        description="Bulk deletion of files without confirmation.",
        resource_patterns=[r"\*", r"all", r"\.\.\."],
        action_patterns=[r"delete", r"remove", r"purge"],
        severity="high",
    ),
    SafetyRule(
        id="safety:network-firewall",
        name="Block Firewall Disable",
        description="Disabling the firewall exposes the system to attacks.",
        resource_patterns=[r"firewall", r"iptables", r"ufw", r"windows.defender"],
        action_patterns=[r"disable", r"stop", r"off", r"flush"],
        severity="critical",
    ),
]


class SafetyPolicyEngine:
    """Evaluates safety rules to block dangerous operations.

    Runs as a pre-check before standard policy evaluation.
    Any matching safety rule results in an immediate DENY.

    Validates: Requirements 5.1–5.6
    """

    def __init__(
        self,
        include_builtins: bool = True,
        custom_rules: Optional[List[SafetyRule]] = None,
    ) -> None:
        """Initialise the safety engine.

        Args:
            include_builtins: Whether to include built-in dangerous operation rules.
            custom_rules: Additional custom safety rules.
        """
        self._rules: Dict[str, SafetyRule] = {}

        if include_builtins:
            for rule in BUILTIN_SAFETY_RULES:
                self._rules[rule.id] = rule

        for rule in (custom_rules or []):
            self._rules[rule.id] = rule

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: SafetyRule) -> None:
        """Add or replace a safety rule."""
        self._rules[rule.id] = rule

    def remove_rule(self, rule_id: str) -> None:
        """Remove a safety rule by ID."""
        self._rules.pop(rule_id, None)

    def disable_rule(self, rule_id: str) -> None:
        """Disable a safety rule without removing it."""
        if rule_id in self._rules:
            self._rules[rule_id].active = False

    def enable_rule(self, rule_id: str) -> None:
        """Re-enable a previously disabled safety rule."""
        if rule_id in self._rules:
            self._rules[rule_id].active = True

    # ------------------------------------------------------------------
    # Safety evaluation
    # ------------------------------------------------------------------

    def check(
        self,
        principal: Principal,
        resource: Resource,
        action: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AccessDecision:
        """Check if an operation is safe to perform.

        Args:
            principal: The requesting principal.
            resource: The target resource.
            action: The requested action.
            context: Optional evaluation context.

        Returns:
            AccessDecision with ALLOW if safe, DENY if dangerous.
        """
        violations = self.get_violations(resource.id, action)
        if violations:
            v = violations[0]  # Report the first (most severe) violation
            logger.warning(
                "Safety violation [%s] blocked %s on %s by %s: %s",
                v.severity, action, resource.id, principal.id, v.description,
            )
            return AccessDecision(
                effect=PolicyEffect.DENY,
                reason=f"Safety rule '{v.rule_name}' blocked this operation: {v.description}",
                applicable_policies=[v.rule_id],
                evaluation_time_ms=0.0,
            )

        return AccessDecision(
            effect=PolicyEffect.ALLOW,
            reason="No safety rules violated",
            applicable_policies=[],
            evaluation_time_ms=0.0,
        )

    def get_violations(self, resource_id: str, action: str) -> List[SafetyViolation]:
        """Return all safety violations for the given resource and action.

        Args:
            resource_id: Resource identifier.
            action: Action to check.

        Returns:
            List of SafetyViolation objects (empty if safe).
        """
        violations = []
        for rule in self._rules.values():
            if rule.matches(resource_id, action):
                violations.append(SafetyViolation(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    severity=rule.severity,
                    description=rule.description,
                    resource_id=resource_id,
                    action=action,
                ))
        # Sort by severity: critical > high > medium > low
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        violations.sort(key=lambda v: severity_order.get(v.severity, 99))
        return violations

    def is_safe(self, resource_id: str, action: str) -> bool:
        """Return True if the operation passes all safety checks."""
        return len(self.get_violations(resource_id, action)) == 0

    @property
    def active_rules(self) -> List[SafetyRule]:
        """Return all currently active safety rules."""
        return [r for r in self._rules.values() if r.active]
