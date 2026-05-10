"""CRDT-based conflict resolution for cross-device sync."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CRDTEntry:
    """A single CRDT entry with vector clock."""

    key: str
    value: Any
    device_id: str
    timestamp: float
    vector_clock: dict[str, int] = field(default_factory=dict)


class LWWRegister:
    """Last-Write-Wins Register CRDT."""

    def __init__(self) -> None:
        self._entries: dict[str, CRDTEntry] = {}

    def set(self, entry: CRDTEntry) -> None:
        existing = self._entries.get(entry.key)
        if existing is None or entry.timestamp > existing.timestamp:
            self._entries[entry.key] = entry

    def get(self, key: str) -> CRDTEntry | None:
        return self._entries.get(key)

    def merge(self, other: LWWRegister) -> LWWRegister:
        """Merge two LWW registers."""
        merged = LWWRegister()
        all_keys = set(self._entries) | set(other._entries)
        for key in all_keys:
            a = self._entries.get(key)
            b = other._entries.get(key)
            if a is None:
                merged._entries[key] = b  # type: ignore[assignment]
            elif b is None:
                merged._entries[key] = a
            else:
                merged._entries[key] = a if a.timestamp >= b.timestamp else b
        return merged

    def to_list(self) -> list[CRDTEntry]:
        return list(self._entries.values())


def resolve_conflict(local: list[CRDTEntry], remote: list[CRDTEntry]) -> list[CRDTEntry]:
    """Resolve conflicts using LWW CRDT."""
    reg_local = LWWRegister()
    reg_remote = LWWRegister()
    for e in local:
        reg_local.set(e)
    for e in remote:
        reg_remote.set(e)
    merged = reg_local.merge(reg_remote)
    return merged.to_list()
