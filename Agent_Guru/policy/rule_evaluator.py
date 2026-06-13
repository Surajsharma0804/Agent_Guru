"""Rule Evaluator - Evaluates policy rule expressions against evaluation contexts.

Supports boolean logic (AND, OR, NOT) and comparison operators.
Includes optional memoization for performance within a single evaluation context.

Performance Characteristics:
    - Time Complexity: O(n) where n is number of conditions in the rule
    - Space Complexity: O(d) where d is rule nesting depth (recursion stack)

Validates: Requirement 2 (Rule Evaluation), Requirement 8 (Memoization)
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

from Agent_Guru.policy.models import EvaluationContext, MissingAttributeStrategy

logger = logging.getLogger(__name__)

# Supported boolean operators
BOOLEAN_OPERATORS = {"AND", "OR", "NOT"}

# Supported comparison operators
COMPARISON_OPERATORS = {
    "equals",
    "not_equals",
    "greater_than",
    "less_than",
    "greater_or_equal",
    "less_or_equal",
    "in",
    "not_in",
    "contains",
    "not_contains",
    "starts_with",
    "ends_with",
    "matches",
    "exists",
    "not_exists",
}


class RuleEvaluationError(Exception):
    """Raised when a rule cannot be evaluated."""


class RuleEvaluator:
    """Evaluates policy rule expressions against evaluation contexts.

    Supports:
    - Boolean operators: AND, OR, NOT
    - Comparison operators: equals, not_equals, greater_than, less_than,
      greater_or_equal, less_or_equal, in, not_in, contains, not_contains,
      starts_with, ends_with, matches (regex), exists, not_exists
    - Nested conditions with arbitrary depth
    - Optional memoization within a request context

    Example rule expression::

        {
            "operator": "AND",
            "conditions": [
                {"attribute": "principal.department", "operator": "equals", "value": "engineering"},
                {"attribute": "resource.classification", "operator": "in", "value": ["public", "internal"]}
            ]
        }

    Validates: Requirements 2.1–2.6, 8.1–8.5
    """

    def __init__(
        self,
        enable_memoization: bool = True,
        missing_attribute_strategy: MissingAttributeStrategy = MissingAttributeStrategy.DENY,
    ) -> None:
        """Initialise the rule evaluator.

        Args:
            enable_memoization: Whether to memoize results within a context.
            missing_attribute_strategy: How to handle missing attributes.

        """
        self.enable_memoization = enable_memoization
        self.missing_attribute_strategy = missing_attribute_strategy

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        rule: dict[str, Any],
        context: EvaluationContext,
        memo_cache: dict[str, bool] | None = None,
    ) -> bool:
        """Evaluate a rule against a context.

        Args:
            rule: Rule expression dict.
            context: Evaluation context.
            memo_cache: Optional shared memoization cache for this request.

        Returns:
            True if the rule matches, False otherwise.

        Raises:
            RuleEvaluationError: If the rule is malformed or evaluation fails.

        """
        if not rule:
            return True  # Empty rule always matches

        cache_key: str | None = None
        if self.enable_memoization and memo_cache is not None:
            cache_key = self._rule_cache_key(rule)
            if cache_key in memo_cache:
                return memo_cache[cache_key]

        try:
            result = self._evaluate_node(rule, context)
        except RuleEvaluationError as exc:
            raise
            msg = f"Rule evaluation error: {exc}"
            logger.exception(msg)
            raise RuleEvaluationError(msg) from exc
        if cache_key is not None and memo_cache is not None:
            memo_cache[cache_key] = result

        return result

    def validate_rule(self, rule: dict[str, Any]) -> list[str]:
        """Validate rule structure.

        Args:
            rule: Rule expression dict to validate.

        Returns:
            List of error messages (empty if valid).

        """
        errors: list[str] = []
        self._validate_node(rule, errors, path="rule")
        return errors

    # ------------------------------------------------------------------
    # Internal evaluation
    # ------------------------------------------------------------------

    def _evaluate_node(self, node: dict[str, Any], context: EvaluationContext) -> bool:
        """Recursively evaluate a rule node."""
        operator = node.get("operator", "").upper()

        if operator in BOOLEAN_OPERATORS:
            return self._evaluate_boolean(operator, node, context)
        if operator in {op.upper() for op in COMPARISON_OPERATORS}:
            return self._evaluate_comparison(operator.lower(), node, context)
        if "attribute" in node:
            # Leaf node with implicit operator
            op = node.get("operator", "exists").lower()
            return self._evaluate_comparison(op, node, context)
        msg = f"Unknown operator '{operator}' in rule node: {node}"
        raise RuleEvaluationError(msg)

    def _evaluate_boolean(
        self,
        operator: str,
        node: dict[str, Any],
        context: EvaluationContext,
    ) -> bool:
        """Evaluate a boolean (AND/OR/NOT) node."""
        conditions = node.get("conditions", [])

        if operator == "AND":
            return all(self._evaluate_node(c, context) for c in conditions)
        if operator == "OR":
            return any(self._evaluate_node(c, context) for c in conditions)
        if operator == "NOT":
            if not conditions:
                msg = "NOT operator requires exactly one condition"
                raise RuleEvaluationError(msg)
            return not self._evaluate_node(conditions[0], context)
        msg = f"Unknown boolean operator: {operator}"
        raise RuleEvaluationError(msg)

    def _evaluate_comparison(
        self,
        operator: str,
        node: dict[str, Any],
        context: EvaluationContext,
    ) -> bool:
        """Evaluate a comparison leaf node."""
        attribute_path = node.get("attribute")
        if not attribute_path:
            msg = f"Comparison node missing 'attribute': {node}"
            raise RuleEvaluationError(msg)

        # Resolve attribute value
        attr_value = context.get_attribute(attribute_path)
        missing = attr_value is None

        # Handle existence checks first
        if operator == "exists":
            return not missing
        if operator == "not_exists":
            return missing

        # Handle missing attribute
        if missing:
            return self._handle_missing_attribute(attribute_path)

        expected = node.get("value")

        try:
            return self._compare(operator, attr_value, expected)
        except Exception as exc:
            msg = (
                f"Comparison failed for attribute '{attribute_path}' "
                f"with operator '{operator}': {exc}"
            )
            raise RuleEvaluationError(
                msg,
            ) from exc

    def _compare(self, operator: str, actual: Any, expected: Any) -> bool:
        """Apply a comparison operator."""
        if operator == "equals":
            return actual == expected
        if operator == "not_equals":
            return actual != expected
        if operator == "greater_than":
            return actual > expected
        if operator == "less_than":
            return actual < expected
        if operator == "greater_or_equal":
            return actual >= expected
        if operator == "less_or_equal":
            return actual <= expected
        if operator == "in":
            return actual in (expected or [])
        if operator == "not_in":
            return actual not in (expected or [])
        if operator == "contains":
            return expected in actual
        if operator == "not_contains":
            return expected not in actual
        if operator == "starts_with":
            return str(actual).startswith(str(expected))
        if operator == "ends_with":
            return str(actual).endswith(str(expected))
        if operator == "matches":
            return bool(re.match(str(expected), str(actual)))
        msg = f"Unknown comparison operator: {operator}"
        raise RuleEvaluationError(msg)

    def _handle_missing_attribute(self, attribute_path: str) -> bool:
        """Handle a missing attribute according to the configured strategy."""
        if self.missing_attribute_strategy == MissingAttributeStrategy.ALLOW:
            return True
        if self.missing_attribute_strategy == MissingAttributeStrategy.ERROR:
            msg = f"Required attribute '{attribute_path}' is missing"
            raise RuleEvaluationError(msg)
        return False

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_node(self, node: Any, errors: list[str], path: str) -> None:
        """Recursively validate a rule node."""
        if not isinstance(node, dict):
            errors.append(f"{path}: expected dict, got {type(node).__name__}")
            return

        operator = node.get("operator", "")
        if not operator:
            errors.append(f"{path}: missing 'operator' field")
            return

        op_upper = operator.upper()

        if op_upper in BOOLEAN_OPERATORS:
            conditions = node.get("conditions")
            if not isinstance(conditions, list):
                errors.append(f"{path}: boolean operator requires 'conditions' list")
                return
            if op_upper == "NOT" and len(conditions) != 1:
                errors.append(f"{path}: NOT operator requires exactly one condition")
            for i, child in enumerate(conditions):
                self._validate_node(child, errors, path=f"{path}.conditions[{i}]")
        elif op_upper in {op.upper() for op in COMPARISON_OPERATORS}:
            if "attribute" not in node:
                errors.append(f"{path}: comparison operator requires 'attribute' field")
            if op_upper not in {"EXISTS", "NOT_EXISTS"} and "value" not in node:
                errors.append(f"{path}: operator '{operator}' requires 'value' field")
        else:
            errors.append(f"{path}: unknown operator '{operator}'")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rule_cache_key(rule: dict[str, Any]) -> str:
        """Compute a stable cache key for a rule expression."""
        serialized = json.dumps(rule, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()
