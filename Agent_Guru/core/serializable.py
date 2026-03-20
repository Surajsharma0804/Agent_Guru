"""Shared serialization mixin — eliminates to_dict/serialize duplication.

Used by: ContextDelta, DeviceState, FusedIntent, HealthAlert, etc.
Time Complexity: O(n) where n = number of fields
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any


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

        Subclasses should override if they need custom field mapping.
        """
        return cls(**json.loads(data))  # type: ignore[call-arg]
