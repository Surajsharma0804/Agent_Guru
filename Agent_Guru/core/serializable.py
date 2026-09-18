"""Shared serialization mixin — eliminates to_dict/serialize duplication.

Used by: ContextDelta, DeviceState, FusedIntent, HealthAlert, etc.
Time Complexity: O(n) where n = number of fields
"""

from __future__ import annotations

import json
import logging
import types
from dataclasses import asdict
from dataclasses import fields as dataclass_fields
from datetime import date, datetime
from enum import Enum
from typing import Any, Union, get_args, get_origin, get_type_hints

logger = logging.getLogger(__name__)


class Serializable:
    """Mixin providing JSON serialize/deserialize for dataclasses."""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation."""
        return asdict(self)  # type: ignore[call-overload]

    def serialize(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def deserialize(cls, data: str) -> "Serializable":  # noqa: UP037
        """Deserialize from a JSON string.

        BUG FIX (Round 25): serialize() uses ``json.dumps(..., default=str)``,
        which is a *lossy* one-way conversion for any field type JSON can't
        represent natively — most commonly ``datetime``/``date`` and
        ``Enum`` fields, both squarely expected in the dataclasses this
        mixin's own docstring names (ContextDelta, DeviceState, FusedIntent,
        HealthAlert — status/timestamp-bearing classes by nature).
        ``deserialize()`` used to just do ``cls(**json.loads(data))``,
        which loads those fields back as plain strings and hands them
        straight to the constructor — no exception, no warning, just a
        dataclass instance whose ``created_at`` (say) is silently a `str`
        instead of a `datetime`, ready to break the next `.isoformat()`,
        comparison, or arithmetic a caller performs on it. Verified this
        concretely: `Example(created_at=datetime.now(...)).serialize()` then
        `.deserialize()` returned `created_at` as `str`, not `datetime`.

        This coerces `datetime`/`date`/`Enum` fields (including
        `Optional[...]`/`X | None` forms of them) back to their declared
        type using the dataclass's own type hints, restoring what
        serialize() lost for those specific, common cases. Anything this
        can't confidently coerce (an unresolvable forward reference, a
        string that doesn't parse against the declared type, or any other
        field type) is left exactly as `json.loads()` produced it — matching
        this method's original behavior for that field — but now with a
        logged warning instead of silent corruption, so the gap stays
        visible and callers with e.g. nested-dataclass or `set`/`bytes`
        fields still know to override this method rather than discovering
        it later at some unrelated call site.

        Subclasses should still override if they need custom field mapping.
        """
        raw = json.loads(data)
        coerced = cls._coerce_fields(raw)
        return cls(**coerced)  # type: ignore[call-arg]

    @classmethod
    def _coerce_fields(cls, raw: dict[str, Any]) -> dict[str, Any]:
        """Best-effort coercion of JSON-native values back to declared types.

        See deserialize()'s docstring for why this exists.
        """
        try:
            hints = get_type_hints(cls)
        except Exception:
            # Can't resolve one or more forward references (e.g. a type
            # only importable under TYPE_CHECKING) -- fall back to passing
            # every value through unchanged, exactly this method's pre-fix
            # behavior, rather than failing the whole deserialize() call
            # over fields we can't even inspect.
            logger.debug(
                "Serializable._coerce_fields: could not resolve type hints "
                "for %s -- values will be passed through unchanged.",
                cls.__name__,
            )
            return raw

        coerced = dict(raw)
        for f in dataclass_fields(cls):  # type: ignore[arg-type]
            if f.name not in coerced:
                continue
            coerced[f.name] = cls._coerce_value(coerced[f.name], hints.get(f.name), f.name)
        return coerced

    @staticmethod
    def _coerce_value(value: Any, field_type: Any, field_name: str) -> Any:
        """Coerce one JSON-native value back to *field_type* if it's a type
        serialize() is known to lose (datetime/date/Enum). Anything else
        (including Optional[...]'s inner type once unwrapped) passes through
        unchanged.
        """
        if value is None or field_type is None:
            return value

        # Unwrap `Optional[X]` / `X | None` to X — both spellings can appear
        # depending on whether the dataclass uses `from __future__ import
        # annotations` and which Python version wrote the type hint.
        origin = get_origin(field_type)
        if origin in (Union, types.UnionType):
            non_none = [a for a in get_args(field_type) if a is not type(None)]
            field_type = non_none[0] if len(non_none) == 1 else None
            if field_type is None:
                return value

        if not isinstance(value, str) or not isinstance(field_type, type):
            return value

        try:
            if issubclass(field_type, datetime):
                return datetime.fromisoformat(value)
            if issubclass(field_type, date):
                return date.fromisoformat(value)
            if issubclass(field_type, Enum):
                return field_type(value)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Serializable.deserialize: could not coerce field %r "
                "(value=%r) to declared type %s -- leaving it as the raw "
                "JSON value (%s: %s). This may cause type errors downstream; "
                "consider a custom deserialize() override for this class.",
                field_name,
                value,
                field_type,
                type(exc).__name__,
                exc,
            )
        return value
