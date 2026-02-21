"""Action sensitivity classifier for safety gate."""

import re
from dataclasses import dataclass
from typing import Any

from Agent_Guru.reasoning.models.action import ActionSensitivity, Tool


@dataclass
class SensitivityRule:
    """Rule for classifying action sensitivity.

    Attributes:
        tool_pattern: Regex pattern to match tool IDs
        parameter_checks: Dict of parameter name to value patterns
        sensitivity: Sensitivity level to assign if rule matches
        reason: Human-readable reason for classification
        priority: Rule priority (higher = checked first)
    """

    tool_pattern: str
    parameter_checks: dict[str, str]
    sensitivity: ActionSensitivity
    reason: str
    priority: int = 0

    def matches(self, tool_id: str, parameters: dict[str, Any]) -> bool:
        """
        Check if rule matches the given tool and parameters.

        Args:
            tool_id: Tool identifier
            parameters: Tool parameters

        Returns:
            True if rule matches, False otherwise
        """
        # Check tool pattern
        if not re.match(self.tool_pattern, tool_id):
            return False

        # Check parameter patterns
        for param_name, param_pattern in self.parameter_checks.items():
            if param_name not in parameters:
                return False

            param_value = str(parameters[param_name])
            if not re.match(param_pattern, param_value):
                return False

        return True


class ActionSensitivityClassifier:
    """Classifies actions by sensitivity level using configurable rules.

    This classifier uses a rule-based approach to determine if an action is
    safe, sensitive, or dangerous. Rules are checked in priority order.

    Time Complexity: O(n) where n is number of rules
    Space Complexity: O(n) for storing rules
    """

    def __init__(self) -> None:
        """Initialize classifier with default rules."""
        self._rules: list[SensitivityRule] = []
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """Load default sensitivity rules."""
        # Dangerous actions (highest priority)
        self.add_rule(
            SensitivityRule(
                tool_pattern=r".*delete.*file.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.DANGEROUS,
                reason="File deletion can cause data loss",
                priority=100,
            )
        )

        self.add_rule(
            SensitivityRule(
                tool_pattern=r".*delete.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.DANGEROUS,
                reason="Deletion operations can cause data loss",
                priority=90,
            )
        )

        self.add_rule(
            SensitivityRule(
                tool_pattern=r".*system.*config.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.DANGEROUS,
                reason="System configuration changes can affect stability",
                priority=90,
            )
        )

        self.add_rule(
            SensitivityRule(
                tool_pattern=r".*execute.*command.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.DANGEROUS,
                reason="Command execution can be harmful",
                priority=90,
            )
        )

        # Sensitive actions (medium priority)
        self.add_rule(
            SensitivityRule(
                tool_pattern=r".*send.*message.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.SENSITIVE,
                reason="Messaging involves external communication",
                priority=50,
            )
        )

        self.add_rule(
            SensitivityRule(
                tool_pattern=r".*send.*email.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.SENSITIVE,
                reason="Email involves external communication",
                priority=50,
            )
        )

        self.add_rule(
            SensitivityRule(
                tool_pattern=r".*call.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.SENSITIVE,
                reason="Phone calls involve external communication",
                priority=50,
            )
        )

        self.add_rule(
            SensitivityRule(
                tool_pattern=r".*smart.*home.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.SENSITIVE,
                reason="Smart home control affects physical devices",
                priority=50,
            )
        )

        self.add_rule(
            SensitivityRule(
                tool_pattern=r".*payment.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.SENSITIVE,
                reason="Financial transactions require confirmation",
                priority=50,
            )
        )

        self.add_rule(
            SensitivityRule(
                tool_pattern=r".*purchase.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.SENSITIVE,
                reason="Purchases involve financial transactions",
                priority=50,
            )
        )

        self.add_rule(
            SensitivityRule(
                tool_pattern=r".*share.*data.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.SENSITIVE,
                reason="Data sharing involves privacy concerns",
                priority=50,
            )
        )

        self.add_rule(
            SensitivityRule(
                tool_pattern=r".*export.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.SENSITIVE,
                reason="Data export involves privacy concerns",
                priority=50,
            )
        )

        self.add_rule(
            SensitivityRule(
                tool_pattern=r".*modify.*file.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.SENSITIVE,
                reason="File modification can affect data",
                priority=40,
            )
        )

        self.add_rule(
            SensitivityRule(
                tool_pattern=r".*write.*file.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.SENSITIVE,
                reason="File writing can affect data",
                priority=40,
            )
        )

    def add_rule(self, rule: SensitivityRule) -> None:
        """
        Add a sensitivity rule.

        Args:
            rule: Sensitivity rule to add
        """
        self._rules.append(rule)
        # Keep rules sorted by priority (highest first)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rule(self, tool_pattern: str) -> bool:
        """
        Remove a sensitivity rule by tool pattern.

        Args:
            tool_pattern: Tool pattern to remove

        Returns:
            True if rule was removed, False if not found
        """
        initial_count = len(self._rules)
        self._rules = [r for r in self._rules if r.tool_pattern != tool_pattern]
        return len(self._rules) < initial_count

    def classify(
        self,
        tool: Tool,
        parameters: dict[str, Any],
    ) -> tuple[ActionSensitivity, str]:
        """
        Classify action sensitivity based on tool and parameters.

        Time Complexity: O(n) where n is number of rules
        Space Complexity: O(1)

        Args:
            tool: Tool to classify
            parameters: Tool parameters

        Returns:
            Tuple of (sensitivity_level, reason)
        """
        # First check tool's declared sensitivity
        if tool.sensitivity != ActionSensitivity.SAFE:
            return tool.sensitivity, f"Tool declared as {tool.sensitivity.value}"

        # Check rules in priority order
        for rule in self._rules:
            if rule.matches(tool.tool_id, parameters):
                return rule.sensitivity, rule.reason

        # Default to safe if no rules match
        return ActionSensitivity.SAFE, "No sensitivity rules matched"

    def get_rules(self) -> list[SensitivityRule]:
        """
        Get all sensitivity rules.

        Returns:
            List of sensitivity rules sorted by priority
        """
        return self._rules.copy()

    def clear_rules(self) -> None:
        """Clear all sensitivity rules."""
        self._rules.clear()

    def load_rules_from_config(self, config: dict[str, Any]) -> None:
        """
        Load sensitivity rules from configuration.

        Args:
            config: Configuration dictionary with rules
        """
        self.clear_rules()

        for rule_config in config.get("rules", []):
            rule = SensitivityRule(
                tool_pattern=rule_config["tool_pattern"],
                parameter_checks=rule_config.get("parameter_checks", {}),
                sensitivity=ActionSensitivity(rule_config["sensitivity"]),
                reason=rule_config["reason"],
                priority=rule_config.get("priority", 0),
            )
            self.add_rule(rule)
