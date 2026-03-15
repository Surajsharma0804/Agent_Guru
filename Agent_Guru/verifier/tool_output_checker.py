"""Tool Output Checker for the Verifier System.

Validates tool execution results before they are used by agents.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""

from __future__ import annotations

import re
from typing import Any

from Agent_Guru.verifier.models import ToolOutputCheckResult

# Common error indicator patterns in tool outputs
_ERROR_PATTERNS = [
    re.compile(r"\b(error|exception|traceback|failed|failure|fatal|critical)\b", re.IGNORECASE),
    re.compile(r"\b(errno|oserror|ioerror|valueerror|typeerror|keyerror|indexerror)\b", re.IGNORECASE),
    re.compile(r"(Traceback \(most recent call last\)|File \".*\", line \d+)", re.IGNORECASE),
    re.compile(r"\b(null|undefined|none)\b.*\b(error|exception)\b", re.IGNORECASE),
    re.compile(r"HTTP [45]\d{2}", re.IGNORECASE),  # HTTP error codes
]

# Success indicator patterns
_SUCCESS_PATTERNS = [
    re.compile(r"\b(success|ok|done|completed|finished|200)\b", re.IGNORECASE),
]


class ToolOutputChecker:
    """Validates tool execution results.

    Checks:
    1. Error indicator detection in output
    2. Schema-based validation (if schema registered)
    3. Semantic consistency validation
    """

    def __init__(self) -> None:
        # Registered tool schemas: tool_name -> schema dict
        self._tool_schemas: dict[str, dict[str, Any]] = {}

    def register_tool_schema(self, tool_name: str, schema: dict[str, Any]) -> None:
        """Register expected output schema for a tool."""
        self._tool_schemas[tool_name] = schema

    def check(
        self,
        tool_name: str,
        output: Any,
        input_params: dict[str, Any] | None = None,
    ) -> ToolOutputCheckResult:
        """Check tool output for errors and consistency.

        Args:
            tool_name: Name of the tool that produced the output
            output: The tool's output
            input_params: Optional input parameters for semantic consistency check

        Returns:
            ToolOutputCheckResult
        """
        error_indicators: list[str] = []
        schema_valid = True
        semantically_consistent = True
        details_parts: list[str] = []

        # 1. Error indicator detection
        output_str = str(output) if not isinstance(output, str) else output
        for pattern in _ERROR_PATTERNS:
            matches = pattern.findall(output_str)
            if matches:
                error_indicators.extend([str(m) for m in matches[:3]])

        if error_indicators:
            details_parts.append(f"Error indicators found: {error_indicators[:3]}")

        # 2. Schema-based checking
        if tool_name in self._tool_schemas:
            schema = self._tool_schemas[tool_name]
            schema_valid = self._check_schema(output, schema)
            if not schema_valid:
                details_parts.append(f"Schema validation failed for tool '{tool_name}'")

        # 3. Semantic consistency
        if input_params:
            semantically_consistent = self._check_semantic_consistency(
                output, input_params
            )
            if not semantically_consistent:
                details_parts.append("Semantic inconsistency detected between input and output")

        safe = (
            len(error_indicators) == 0
            and schema_valid
            and semantically_consistent
        )

        return ToolOutputCheckResult(
            safe=safe,
            error_indicators=error_indicators,
            schema_valid=schema_valid,
            semantically_consistent=semantically_consistent,
            details="; ".join(details_parts) if details_parts else "Tool output is safe",
        )

    def _check_schema(self, output: Any, schema: dict[str, Any]) -> bool:
        """Simple schema check: verify required fields present."""
        if not isinstance(output, dict):
            return schema.get("type") != "object"

        required = schema.get("required", [])
        for field in required:
            if field not in output:
                return False

        # Check field types
        properties = schema.get("properties", {})
        for field, field_schema in properties.items():
            if field in output:
                expected_type = field_schema.get("type")
                if expected_type:
                    type_map = {
                        "string": str,
                        "number": (int, float),
                        "integer": int,
                        "boolean": bool,
                        "array": list,
                        "object": dict,
                    }
                    py_type = type_map.get(expected_type)
                    if py_type and not isinstance(output[field], py_type):
                        return False

        return True

    def _check_semantic_consistency(
        self, output: Any, input_params: dict[str, Any]
    ) -> bool:
        """Check if output is semantically consistent with inputs.

        Heuristic: if input specifies a count/limit, output shouldn't exceed it.
        """
        output_str = str(output).lower()

        # Check for explicit error in output when input was valid
        has_error = any(p.search(output_str) for p in _ERROR_PATTERNS)
        has_success = any(p.search(output_str) for p in _SUCCESS_PATTERNS)

        # If output has errors but no success signals, flag it
        if has_error and not has_success and len(output_str) < 500:
            return False

        # Check limit consistency
        limit = input_params.get("limit") or input_params.get("count") or input_params.get("max")
        if limit and isinstance(output, list):
            if len(output) > int(limit):
                return False

        return True
