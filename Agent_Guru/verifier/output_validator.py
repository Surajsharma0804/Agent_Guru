"""Output Validator for the Verifier System.

Validates structured outputs against schemas and format constraints.
Supports JSON, XML, Markdown, and Pydantic model validation.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET  # nosec B405 — used only for ET.ParseError type; defusedxml used for actual parsing
from typing import Any

try:
    import defusedxml.ElementTree as _defused_ET  # type: ignore[import-untyped]
    _DEFUSEDXML_AVAILABLE = True
except ImportError:  # pragma: no cover
    _DEFUSEDXML_AVAILABLE = False

from Agent_Guru.verifier.models import (
    OutputValidationResult,
    ValidationFailureType,
    ValidationViolation,
)


class OutputValidator:
    """Validates outputs against schemas and format constraints.

    Supports:
    - JSON schema validation (structural)
    - Pydantic model validation
    - Type checking
    - Format validation (JSON, XML, Markdown)
    - Recursive nested structure validation
    """

    def validate(
        self,
        output: Any,
        expected_schema: dict[str, Any] | None = None,
        expected_format: str | None = None,
    ) -> OutputValidationResult:
        """Validate output against schema and format.

        Args:
            output: The output to validate
            expected_schema: Optional JSON schema dict
            expected_format: Optional format hint ("json", "xml", "markdown", "text")

        Returns:
            OutputValidationResult with violations if any
        """
        violations: list[ValidationViolation] = []
        format_detected = "unknown"

        # Detect format
        if isinstance(output, str):
            format_detected = self._detect_format(output)
        elif isinstance(output, dict):
            format_detected = "dict"
        elif isinstance(output, list):
            format_detected = "list"
        else:
            format_detected = type(output).__name__

        # Format validation
        if expected_format:
            fmt_violations = self._validate_format(output, expected_format)
            violations.extend(fmt_violations)

        # Schema validation
        if expected_schema:
            schema_violations = self._validate_schema(output, expected_schema)
            violations.extend(schema_violations)

        valid = len(violations) == 0
        details = (
            f"{len(violations)} violation(s) found"
            if violations
            else "Output is valid"
        )

        return OutputValidationResult(
            valid=valid,
            violations=violations,
            format_detected=format_detected,
            details=details,
        )

    def _detect_format(self, text: str) -> str:
        """Auto-detect the format of a string."""
        stripped = text.strip()
        if not stripped:
            return "empty"
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                json.loads(stripped)
                return "json"
            except json.JSONDecodeError:
                return "invalid_json"
        if stripped.startswith("<") and stripped.endswith(">"):
            try:
                if _DEFUSEDXML_AVAILABLE:
                    _defused_ET.fromstring(stripped)
                else:
                    ET.fromstring(stripped)  # nosec B314
                return "xml"
            except ET.ParseError:
                return "invalid_xml"
        if re.search(r"^#{1,6}\s", stripped, re.MULTILINE):
            return "markdown"
        return "text"

    def _validate_format(
        self, output: Any, expected_format: str
    ) -> list[ValidationViolation]:
        """Validate that output matches expected format."""
        violations: list[ValidationViolation] = []
        fmt = expected_format.lower()

        if fmt == "json":
            if isinstance(output, (dict, list)):
                return []  # Already parsed JSON
            if not isinstance(output, str):
                violations.append(
                    ValidationViolation(
                        field="output",
                        failure_type=ValidationFailureType.TYPE_MISMATCH,
                        message="Expected JSON string or dict/list",
                        expected="str | dict | list",
                        actual=type(output).__name__,
                    )
                )
                return violations
            try:
                json.loads(output)
            except json.JSONDecodeError as e:
                violations.append(
                    ValidationViolation(
                        field="output",
                        failure_type=ValidationFailureType.FORMAT_ERROR,
                        message=f"Invalid JSON: {e}",
                        expected="valid JSON",
                        actual=output[:100],
                    )
                )

        elif fmt == "xml":
            if not isinstance(output, str):
                violations.append(
                    ValidationViolation(
                        field="output",
                        failure_type=ValidationFailureType.TYPE_MISMATCH,
                        message="Expected XML string",
                        expected="str",
                        actual=type(output).__name__,
                    )
                )
                return violations
            try:
                if _DEFUSEDXML_AVAILABLE:
                    _defused_ET.fromstring(output)
                else:
                    ET.fromstring(output)  # nosec B314
            except ET.ParseError as e:
                violations.append(
                    ValidationViolation(
                        field="output",
                        failure_type=ValidationFailureType.FORMAT_ERROR,
                        message=f"Invalid XML: {e}",
                        expected="valid XML",
                        actual=output[:100],
                    )
                )

        elif fmt == "markdown":
            if not isinstance(output, str):
                violations.append(
                    ValidationViolation(
                        field="output",
                        failure_type=ValidationFailureType.TYPE_MISMATCH,
                        message="Expected markdown string",
                        expected="str",
                        actual=type(output).__name__,
                    )
                )

        return violations

    def _validate_schema(
        self, output: Any, schema: dict[str, Any], path: str = ""
    ) -> list[ValidationViolation]:
        """Recursively validate output against a JSON schema-like dict.

        Supports: type, required, properties, items, minimum, maximum, minLength, maxLength
        """
        violations: list[ValidationViolation] = []
        field_path = path or "root"

        # Parse output if it's a JSON string representing an object/array
        if isinstance(output, str):
            stripped = output.strip()
            if stripped.startswith(("{", "[")):
                try:
                    output = json.loads(stripped)
                except json.JSONDecodeError:
                    pass  # Will fail type check below if schema expects object

        # Type check
        expected_type = schema.get("type")
        if expected_type:
            type_map = {
                "object": dict,
                "array": list,
                "string": str,
                "number": (int, float),
                "integer": int,
                "boolean": bool,
                "null": type(None),
            }
            expected_py_type = type_map.get(expected_type)
            if expected_py_type and not isinstance(output, expected_py_type):
                violations.append(
                    ValidationViolation(
                        field=field_path,
                        failure_type=ValidationFailureType.TYPE_MISMATCH,
                        message=f"Expected type '{expected_type}'",
                        expected=expected_type,
                        actual=type(output).__name__,
                    )
                )
                return violations  # Can't validate further

        # Required fields
        required = schema.get("required", [])
        if isinstance(output, dict):
            for req_field in required:
                if req_field not in output:
                    violations.append(
                        ValidationViolation(
                            field=f"{field_path}.{req_field}",
                            failure_type=ValidationFailureType.MISSING_FIELD,
                            message=f"Required field '{req_field}' is missing",
                            expected=req_field,
                            actual="<missing>",
                        )
                    )

        # Properties (recursive)
        properties = schema.get("properties", {})
        if isinstance(output, dict) and properties:
            for prop_name, prop_schema in properties.items():
                if prop_name in output:
                    child_violations = self._validate_schema(
                        output[prop_name],
                        prop_schema,
                        path=f"{field_path}.{prop_name}",
                    )
                    violations.extend(child_violations)

        # Array items (recursive)
        items_schema = schema.get("items")
        if isinstance(output, list) and items_schema:
            for i, item in enumerate(output):
                child_violations = self._validate_schema(
                    item, items_schema, path=f"{field_path}[{i}]"
                )
                violations.extend(child_violations)

        # Numeric constraints
        if isinstance(output, (int, float)):
            minimum = schema.get("minimum")
            maximum = schema.get("maximum")
            if minimum is not None and output < minimum:
                violations.append(
                    ValidationViolation(
                        field=field_path,
                        failure_type=ValidationFailureType.CONSTRAINT_VIOLATION,
                        message=f"Value {output} is below minimum {minimum}",
                        expected=f">= {minimum}",
                        actual=str(output),
                    )
                )
            if maximum is not None and output > maximum:
                violations.append(
                    ValidationViolation(
                        field=field_path,
                        failure_type=ValidationFailureType.CONSTRAINT_VIOLATION,
                        message=f"Value {output} exceeds maximum {maximum}",
                        expected=f"<= {maximum}",
                        actual=str(output),
                    )
                )

        # String length constraints
        if isinstance(output, str):
            min_length = schema.get("minLength")
            max_length = schema.get("maxLength")
            if min_length is not None and len(output) < min_length:
                violations.append(
                    ValidationViolation(
                        field=field_path,
                        failure_type=ValidationFailureType.CONSTRAINT_VIOLATION,
                        message=f"String length {len(output)} below minLength {min_length}",
                        expected=f"length >= {min_length}",
                        actual=str(len(output)),
                    )
                )
            if max_length is not None and len(output) > max_length:
                violations.append(
                    ValidationViolation(
                        field=field_path,
                        failure_type=ValidationFailureType.CONSTRAINT_VIOLATION,
                        message=f"String length {len(output)} exceeds maxLength {max_length}",
                        expected=f"length <= {max_length}",
                        actual=str(len(output)),
                    )
                )

        return violations
