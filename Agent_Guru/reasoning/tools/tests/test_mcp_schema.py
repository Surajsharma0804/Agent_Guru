"""An external tool's schema is either checked completely or the tool is not offered."""

from __future__ import annotations

import pytest

from Agent_Guru.reasoning.tools.mcp_schema import (
    MAX_DEPTH,
    UnsupportedSchema,
    check_schema,
    validate,
)


@pytest.mark.parametrize("schema", [
    {"type": "object", "properties": {"x": {"anyOf": [{"type": "string"}]}}},
    {"type": "object", "properties": {"x": {"$ref": "#/$defs/x"}}},
    {"type": "object", "properties": {"x": {"type": "string", "pattern": "(a+)+$"}}},
    {"type": "object", "properties": {"x": {"type": "date"}}},
    {"type": "object", "properties": "x"},
    {"type": "object", "required": "x"},
    {"type": "object", "additionalProperties": "no"},
    {"type": "object", "properties": {"x": {"type": "string", "maxLength": "10"}}},
    {"type": "object", "properties": {"x": {"type": "number", "minimum": True}}},
    {"type": "object", "properties": {"x": {"enum": "ab"}}},
    "not a schema",
])
def test_a_schema_that_cannot_be_fully_checked_is_refused(schema):
    with pytest.raises(UnsupportedSchema):
        check_schema(schema)


def test_descriptive_keywords_are_allowed():
    check_schema({
        "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "title": "t",
        "properties": {"when": {"type": "string", "format": "date-time", "description": "d", "default": "now"}},
    })


def test_nesting_is_bounded():
    schema: dict = {"type": "object"}
    for _ in range(MAX_DEPTH + 2):
        schema = {"type": "object", "properties": {"x": schema}}
    with pytest.raises(UnsupportedSchema, match="deeper"):
        check_schema(schema)


SCHEMA = {
    "type": "object",
    "properties": {
        "count": {"type": "integer", "minimum": 1, "exclusiveMaximum": 10},
        "ratio": {"type": "number"},
        "flag": {"type": "boolean"},
        "name": {"type": ["string", "null"], "minLength": 2},
        "kind": {"const": "file"},
        "ids": {"type": "array", "items": {"type": "integer"}, "minItems": 1, "uniqueItems": True},
        "meta": {"type": "object", "additionalProperties": {"type": "string"}, "maxProperties": 2},
    },
    "required": ["count"],
    "additionalProperties": False,
}


@pytest.mark.parametrize(("value", "problem"), [
    ({"count": 1}, None),
    ({"count": 3.0, "name": None, "kind": "file", "ids": [1, 2], "meta": {"a": "b"}}, None),
    ({"count": True}, "expected integer"),  # a boolean is not a number in JSON Schema
    ({"count": 10}, "not below 10"),
    ({"count": 0}, "below 1"),
    ({"count": 1, "ratio": float("nan")}, "expected number"),
    ({"count": 1, "name": "a"}, "shorter than 2"),
    ({"count": 1, "kind": "dir"}, "must be 'file'"),
    ({"count": 1, "ids": []}, "fewer than 1"),
    ({"count": 1, "ids": [1, 1]}, "items repeat"),
    ({"count": 1, "ids": ["1"]}, "ids[0]: expected integer"),
    ({"count": 1, "meta": {"a": 1}}, "meta.a: expected string"),
    ({"count": 1, "meta": {"a": "1", "b": "2", "c": "3"}}, "more than 2 fields"),
    ({"count": 1, "other": 1}, "other is not an argument"),
    ([], "expected object"),
])
def test_values_are_checked_against_the_schema(value, problem):
    check_schema(SCHEMA)
    problems = validate(value, SCHEMA)
    if problem is None:
        assert problems == []  # nosec B101
    else:
        assert any(problem in p for p in problems), problems  # nosec B101


def test_deeply_nested_arguments_are_refused():
    value: dict = {}
    for _ in range(MAX_DEPTH + 2):
        value = {"x": value}
    assert any("deeper" in p for p in validate(value, {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": True}}))  # nosec B101
