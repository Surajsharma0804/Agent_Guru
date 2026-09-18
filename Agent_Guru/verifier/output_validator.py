"""Output Validator for the Verifier System.

Validates structured outputs against schemas and format constraints.
Supports JSON, XML, Markdown, and Pydantic model validation.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET  # nosec B405
from typing import Any

try:
    import defusedxml.ElementTree as _defused_ET  # type: ignore[import-untyped]
except ImportError as _defusedxml_import_error:  # pragma: no cover
    msg = "defusedxml is required for safe XML parsing. Install it with: pip install defusedxml"
    raise ImportError(
        msg,
    ) from _defusedxml_import_error

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
        details = f"{len(violations)} violation(s) found" if violations else "Output is valid"

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
        if stripped.startswith(("{", "[")):
            try:
                json.loads(stripped)
                return "json"
            except json.JSONDecodeError:
                return "invalid_json"
        if stripped.startswith("<") and stripped.endswith(">"):
            try:
                _defused_ET.fromstring(stripped)
                return "xml"
            except ET.ParseError:
                return "invalid_xml"
        if re.search(r"^#{1,6}\s", stripped, re.MULTILINE):
            return "markdown"
        return "text"

    def _validate_format(self, output: Any, expected_format: str) -> list[ValidationViolation]:
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
                    ),
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
                    ),
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
                    ),
                )
                return violations
            try:
                _defused_ET.fromstring(output)
            except ET.ParseError as e:
                violations.append(
                    ValidationViolation(
                        field="output",
                        failure_type=ValidationFailureType.FORMAT_ERROR,
                        message=f"Invalid XML: {e}",
                        expected="valid XML",
                        actual=output[:100],
                    ),
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
                    ),
                )

        return violations

    def _validate_schema(
        self,
        output: Any,
        schema: dict[str, Any],
        path: str = "",
    ) -> list[ValidationViolation]:
        """Recursively validate output against a JSON schema-like dict.

        Supports: type, required, properties, items, minimum, maximum, minLength, maxLength
        """
        violations: list[ValidationViolation] = []
        field_path = path or "root"

        # Parse output if it's a JSON string representing an object/array
        output = self._maybe_parse_json(output)

        # Type check (early return if mismatch)
        type_violations = self._check_type(output, schema, field_path)
        if type_violations:
            return type_violations

        # Structural checks
        violations.extend(self._check_required_fields(output, schema, field_path))
        violations.extend(self._check_properties(output, schema, field_path))
        violations.extend(self._check_array_items(output, schema, field_path))

        # Constraint checks
        violations.extend(self._check_numeric_constraints(output, schema, field_path))
        violations.extend(self._check_string_constraints(output, schema, field_path))

        return violations

    # ------------------------------------------------------------------
    # _validate_schema helpers (extracted for complexity reduction)
    # ------------------------------------------------------------------

    @staticmethod
    def _maybe_parse_json(output: Any) -> Any:
        """Parse JSON string to object if it looks like JSON."""
        if isinstance(output, str):
            stripped = output.strip()
            if stripped.startswith(("{", "[")):
                try:
                    return json.loads(stripped)
                except json.JSONDecodeError:
                    # "Looks like JSON but is not" is a legitimate input, not a
                    # validation failure: the original string is returned
                    # unchanged and validated as a string. The caller's own
                    # rules decide whether that is acceptable.
                    pass
        return output

    @staticmethod
    def _check_type(
        output: Any, schema: dict[str, Any], field_path: str,
    ) -> list[ValidationViolation]:
        """Validate output type against schema. Returns violations if mismatch."""
        expected_type = schema.get("type")
        if not expected_type:
            return []

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
            return [
                ValidationViolation(
                    field=field_path,
                    failure_type=ValidationFailureType.TYPE_MISMATCH,
                    message=f"Expected type '{expected_type}'",
                    expected=expected_type,
                    actual=type(output).__name__,
                ),
            ]
        return []

    @staticmethod
    def _check_required_fields(
        output: Any, schema: dict[str, Any], field_path: str,
    ) -> list[ValidationViolation]:
        """Validate that all required fields are present."""
        violations: list[ValidationViolation] = []
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
                        ),
                    )
        return violations

    def _check_properties(
        self, output: Any, schema: dict[str, Any], field_path: str,
    ) -> list[ValidationViolation]:
        """Recursively validate object properties."""
        violations: list[ValidationViolation] = []
        properties = schema.get("properties", {})
        if isinstance(output, dict) and properties:
            for prop_name, prop_schema in properties.items():
                if prop_name in output:
                    violations.extend(
                        self._validate_schema(
                            output[prop_name],
                            prop_schema,
                            path=f"{field_path}.{prop_name}",
                        ),
                    )
        return violations

    def _check_array_items(
        self, output: Any, schema: dict[str, Any], field_path: str,
    ) -> list[ValidationViolation]:
        """Recursively validate array items."""
        violations: list[ValidationViolation] = []
        items_schema = schema.get("items")
        if isinstance(output, list) and items_schema:
            for i, item in enumerate(output):
                violations.extend(
                    self._validate_schema(
                        item,
                        items_schema,
                        path=f"{field_path}[{i}]",
                    ),
                )
        return violations

    @staticmethod
    def _check_numeric_constraints(
        output: Any, schema: dict[str, Any], field_path: str,
    ) -> list[ValidationViolation]:
        """Validate numeric minimum/maximum constraints."""
        violations: list[ValidationViolation] = []
        if not isinstance(output, (int, float)):
            return violations

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
                ),
            )
        if maximum is not None and output > maximum:
            violations.append(
                ValidationViolation(
                    field=field_path,
                    failure_type=ValidationFailureType.CONSTRAINT_VIOLATION,
                    message=f"Value {output} exceeds maximum {maximum}",
                    expected=f"<= {maximum}",
                    actual=str(output),
                ),
            )
        return violations

    @staticmethod
    def _check_string_constraints(
        output: Any, schema: dict[str, Any], field_path: str,
    ) -> list[ValidationViolation]:
        """Validate string minLength/maxLength constraints."""
        violations: list[ValidationViolation] = []
        if not isinstance(output, str):
            return violations

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
                ),
            )
        if max_length is not None and len(output) > max_length:
            violations.append(
                ValidationViolation(
                    field=field_path,
                    failure_type=ValidationFailureType.CONSTRAINT_VIOLATION,
                    message=f"String length {len(output)} exceeds maxLength {max_length}",
                    expected=f"length <= {max_length}",
                    actual=str(len(output)),
                ),
            )
        return violations

