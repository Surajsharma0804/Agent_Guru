"""Deictic reference resolution using visual context."""

from __future__ import annotations

from typing import Any


class DeicticResolver:
    """Resolves deictic references ('this', 'that', 'it') using visual context."""

    DEICTIC_WORDS = {"this", "that", "it", "here", "there"}

    def resolve(self, reference: str, context: dict[str, Any]) -> str | None:
        """Resolve a deictic reference to a concrete entity.

        In production, uses CLIP embeddings for visual grounding.
        """
        if reference.lower() not in self.DEICTIC_WORDS:
            return reference
        # Stub: return last focused object from context
        return context.get("focused_object") or context.get("last_object")
