"""Rule Evaluator - Evaluates policy rule expressions against evaluation contexts.

Supports boolean logic (AND, OR, NOT) and comparison operators.
Includes optional memoization for performance within a single evaluation context.

Performance Characteristics:
    - Time Complexity: O(n) where n is number of conditions in the rule
    - Space Complexity: O(d) where d is rule nesting depth (recursion stack)

Validates: Requirement 2 (Rule Evaluation), Requirement 8 (Memoization)
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import re
from typing import Any

from Agent_Guru.policy.models import EvaluationContext, MissingAttributeStrategy

logger = logging.getLogger(__name__)

# Supported boolean operators
BOOLEAN_OPERATORS = frozenset({"AND", "OR", "NOT"})

# Supported comparison operators
COMPARISON_OPERATORS = frozenset({
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
})

# Maximum rule nesting depth. Rule expressions arrive from policy files, and
# _evaluate_node() recurses once per level -- an over-nested (or cyclic,
# hand-written) expression used to bottom out in a RecursionError, which is
# not a RuleEvaluationError and so bypassed access_controller's fail-closed
# handler. Mirrors MAX_ROLE_DEPTH in access_controller.py.
MAX_RULE_DEPTH = 50

# Bounded compiled-regex cache for the `matches` operator. Patterns come from
# policy definitions, so the set is small and stable; re-compiling on every
# evaluation was pure waste on the request path.
_REGEX_CACHE_SIZE = 256


@functools.lru_cache(maxsize=_REGEX_CACHE_SIZE)
def _compiled(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


# Precomputed once: _evaluate_node() and _validate_node() each rebuilt this
# set on every single node visit, which is O(len(COMPARISON_OPERATORS)) of
# pointless work per node on the authorization request path.
_COMPARISON_OPERATORS_UPPER = frozenset(op.upper() for op in COMPARISON_OPERATORS)


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
            # SECURITY FIX: the key used to be the hash of the RULE ALONE, so a
            # memo cache that outlived one request -- or was shared between two
            # -- would return the decision computed for one principal/resource
            # as the answer for a different one. That is an authorization
            # bypass, not a stale read. EvaluationContext.context_hash() already
            # existed for exactly this and simply was not wired in; binding the
            # key to it makes the cache safe no matter who holds it.
            # access_controller.py builds a fresh cache per request today, so
            # this closes the hole at the source rather than relying on every
            # future caller repeating that discipline.
            cache_key = f"{context.context_hash()}:{self._rule_cache_key(rule)}"
            if cache_key in memo_cache:
                return memo_cache[cache_key]

        result = self._evaluate_node(rule, context)
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

    def _evaluate_node(
        self,
        node: dict[str, Any],
        context: EvaluationContext,
        depth: int = 0,
    ) -> bool:
        """Recursively evaluate a rule node."""
        if depth > MAX_RULE_DEPTH:
            msg = (
                f"Rule nesting exceeds the maximum depth of {MAX_RULE_DEPTH}. "
                "Refusing to evaluate."
            )
            raise RuleEvaluationError(msg)
        if not isinstance(node, dict):
            msg = f"Rule node must be a mapping, got {type(node).__name__}: {node!r}"
            raise RuleEvaluationError(msg)

        raw_operator = node.get("operator", "")
        if not isinstance(raw_operator, str):
            # A non-string operator (a number or list in a hand-edited policy
            # file) used to raise AttributeError from .upper() -- which is not
            # a RuleEvaluationError, so access_controller's fail-closed handler
            # never saw it and the exception escaped the policy layer entirely.
            msg = f"Rule operator must be a string, got {type(raw_operator).__name__}"
            raise RuleEvaluationError(msg)
        operator = raw_operator.upper()

        if operator in BOOLEAN_OPERATORS:
            return self._evaluate_boolean(operator, node, context, depth)
        if operator in _COMPARISON_OPERATORS_UPPER:
            return self._evaluate_comparison(operator.lower(), node, context)
        if "attribute" in node:
            # Leaf node with implicit operator
            op = node.get("operator", "exists")
            if not isinstance(op, str):
                msg = f"Rule operator must be a string, got {type(op).__name__}"
                raise RuleEvaluationError(msg)
            return self._evaluate_comparison(op.lower(), node, context)
        msg = f"Unknown operator '{operator}' in rule node: {node}"
        raise RuleEvaluationError(msg)

    def _evaluate_boolean(
        self,
        operator: str,
        node: dict[str, Any],
        context: EvaluationContext,
        depth: int = 0,
    ) -> bool:
        """Evaluate a boolean (AND/OR/NOT) node."""
        conditions = node.get("conditions", [])
        if not isinstance(conditions, list):
            msg = f"'{operator}' requires a list of conditions, got {type(conditions).__name__}"
            raise RuleEvaluationError(msg)

        if operator == "AND":
            return all(self._evaluate_node(c, context, depth + 1) for c in conditions)
        if operator == "OR":
            return any(self._evaluate_node(c, context, depth + 1) for c in conditions)
        if operator == "NOT":
            if not conditions:
                msg = "NOT operator requires exactly one condition"
                raise RuleEvaluationError(msg)
            return not self._evaluate_node(conditions[0], context, depth + 1)
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
            # SECURITY FIX: re.match() anchors only the START of the string, so
            # a policy condition of "admin" also matched "administrator_evil",
            # and "safe" matched "safe_but_not". In an authorization predicate
            # a partial match is the wrong default -- the rule author writes
            # what the value must BE, not what it must begin with. fullmatch()
            # makes the operator mean what its name says; a prefix rule is
            # still expressible as "admin.*".
            # The operator appears in no policy or fixture in this repository,
            # so nothing currently relies on the prefix behaviour.
            try:
                return bool(_compiled(str(expected)).fullmatch(str(actual)))
            except re.error as exc:
                msg = f"Invalid regex in 'matches' rule: {expected!r} ({exc})"
                raise RuleEvaluationError(msg) from exc
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

        if not isinstance(operator, str):
            errors.append(f"{path}: 'operator' must be a string, got {type(operator).__name__}")
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
        elif op_upper in _COMPARISON_OPERATORS_UPPER:
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
