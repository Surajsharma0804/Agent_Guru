"""Checking an external tool's arguments against the JSON Schema the tool declares.

An MCP server describes each tool's arguments with a JSON Schema. Arguments a
model wrote are checked against it here, before anything is sent, so a
malformed call never reaches the server: a missing field, a number where text
belongs, an extra field the tool did not ask for.

Only the part of JSON Schema that tool schemas use is understood: types (one,
or a list such as ["string", "null"] for a nullable field), properties,
required, additionalProperties, items, enum, const, and the length, size and
range limits. Keywords that only describe (title, description, default,
examples, format, $schema) are skipped, as the standard allows. Anything else
($ref, anyOf, oneOf, pattern, conditionals) makes the schema unsupported, and
check_schema says so: a tool whose arguments cannot be fully checked is not
offered at all, rather than checked in part. pattern is in that list on
purpose, since a regular expression written by the server could take
unbounded time to match.
"""

from __future__ import annotations

import math
from typing import Any

_DESCRIPTIVE = frozenset(
    {"title", "description", "default", "examples", "format", "$schema", "$comment", "deprecated", "readOnly", "writeOnly"},
)
_CHECKED = frozenset(
    {
        "type", "properties", "required", "additionalProperties", "items", "enum", "const",
        "minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
        "minItems", "maxItems", "minProperties", "maxProperties", "uniqueItems",
    },
)
_TYPES = frozenset({"string", "number", "integer", "boolean", "object", "array", "null"})

#: Deepest nesting of objects and arrays a schema or an argument may have.
MAX_DEPTH = 16


class UnsupportedSchema(ValueError):
    """The schema uses something this checker does not understand."""


def check_schema(schema: Any, *, where: str = "arguments", depth: int = 0) -> None:
    """Raise UnsupportedSchema if *schema* cannot be checked completely; return None if it can."""
    if depth > MAX_DEPTH:
        msg = f"{where}: nested deeper than {MAX_DEPTH} levels"
        raise UnsupportedSchema(msg)
    if not isinstance(schema, dict):
        msg = f"{where}: schema is not an object"
        raise UnsupportedSchema(msg)
    unknown = set(schema) - _CHECKED - _DESCRIPTIVE
    if unknown:
        msg = f"{where}: uses {', '.join(sorted(unknown))}, which cannot be checked"
        raise UnsupportedSchema(msg)
    types = schema.get("type")
    if types is not None:
        listed = types if isinstance(types, list) else [types]
        if not listed or any(t not in _TYPES for t in listed):
            msg = f"{where}: unknown type {types!r}"
            raise UnsupportedSchema(msg)
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        msg = f"{where}: properties is not an object"
        raise UnsupportedSchema(msg)
    for name, sub in properties.items():
        check_schema(sub, where=f"{where}.{name}", depth=depth + 1)
    required = schema.get("required", [])
    if not isinstance(required, list) or not all(isinstance(r, str) for r in required):
        msg = f"{where}: required is not a list of names"
        raise UnsupportedSchema(msg)
    extra = schema.get("additionalProperties", True)
    if isinstance(extra, dict):
        check_schema(extra, where=f"{where}.*", depth=depth + 1)
    elif not isinstance(extra, bool):
        msg = f"{where}: additionalProperties is neither true, false nor a schema"
        raise UnsupportedSchema(msg)
    if "items" in schema:
        check_schema(schema["items"], where=f"{where}[]", depth=depth + 1)
    if "enum" in schema and not isinstance(schema["enum"], list):
        msg = f"{where}: enum is not a list"
        raise UnsupportedSchema(msg)
    for limit in ("minLength", "maxLength", "minItems", "maxItems", "minProperties", "maxProperties"):
        if limit in schema and (isinstance(schema[limit], bool) or not isinstance(schema[limit], int)):
            msg = f"{where}: {limit} is not a whole number"
            raise UnsupportedSchema(msg)
    for limit in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
        if limit in schema and (isinstance(schema[limit], bool) or not isinstance(schema[limit], int | float)):
            msg = f"{where}: {limit} is not a number"
            raise UnsupportedSchema(msg)


def _is_type(value: Any, name: str) -> bool:
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or (
            isinstance(value, float) and value.is_integer()
        )
    if name == "number":
        return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)
    if name == "string":
        return isinstance(value, str)
    if name == "array":
        return isinstance(value, list)
    return isinstance(value, dict)


def _type_name(value: Any) -> str:
    for name in ("null", "boolean", "integer", "number", "string", "array", "object"):
        if _is_type(value, name):
            return name
    return type(value).__name__


def _nesting(value: Any) -> int:
    """How deeply *value* nests lists and objects, without recursion."""
    deepest, stack = 0, [(value, 0)]
    while stack:
        item, level = stack.pop()
        if isinstance(item, dict | list):
            level += 1
            deepest = max(deepest, level)
            if deepest > MAX_DEPTH:
                return deepest
            stack.extend((child, level) for child in (item.values() if isinstance(item, dict) else item))
    return deepest


def validate(value: Any, schema: dict[str, Any], *, where: str = "arguments", depth: int = 0) -> list[str]:
    """What is wrong with *value* against a schema check_schema accepted; empty if nothing is."""
    if depth > MAX_DEPTH or (depth == 0 and _nesting(value) > MAX_DEPTH):
        # Measured over the whole value, not only where the schema looks: a
        # field the schema leaves open could hold nesting deep enough to
        # make encoding the arguments fail with RecursionError.
        return [f"{where}: nested deeper than {MAX_DEPTH} levels"]
    problems: list[str] = []
    types = schema.get("type")
    if types is not None:
        listed = types if isinstance(types, list) else [types]
        if not any(_is_type(value, t) for t in listed):
            return [f"{where}: expected {' or '.join(listed)}, got {_type_name(value)}"]
    if "const" in schema and value != schema["const"]:
        problems.append(f"{where}: must be {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{where}: must be one of {schema['enum']!r}")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            problems.append(f"{where}: shorter than {schema['minLength']} characters")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            problems.append(f"{where}: longer than {schema['maxLength']} characters")
    elif isinstance(value, int | float) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            problems.append(f"{where}: below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            problems.append(f"{where}: above {schema['maximum']}")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            problems.append(f"{where}: not above {schema['exclusiveMinimum']}")
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            problems.append(f"{where}: not below {schema['exclusiveMaximum']}")
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            problems.append(f"{where}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            problems.append(f"{where}: more than {schema['maxItems']} items")
        if schema.get("uniqueItems") and len({repr(v) for v in value}) != len(value):
            problems.append(f"{where}: items repeat")
        if "items" in schema:
            for n, item in enumerate(value):
                problems += validate(item, schema["items"], where=f"{where}[{n}]", depth=depth + 1)
    elif isinstance(value, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                problems.append(f"{where}: {name} is required")
        extra = schema.get("additionalProperties", True)
        for name, item in value.items():
            if name in properties:
                problems += validate(item, properties[name], where=f"{where}.{name}", depth=depth + 1)
            elif extra is False:
                problems.append(f"{where}: {name} is not an argument this tool takes")
            elif isinstance(extra, dict):
                problems += validate(item, extra, where=f"{where}.{name}", depth=depth + 1)
        if len(value) < schema.get("minProperties", 0):
            problems.append(f"{where}: fewer than {schema['minProperties']} fields")
        if "maxProperties" in schema and len(value) > schema["maxProperties"]:
            problems.append(f"{where}: more than {schema['maxProperties']} fields")
    return problems
