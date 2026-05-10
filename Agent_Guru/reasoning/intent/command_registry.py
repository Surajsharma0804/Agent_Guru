"""CommandRegistry - Command Pattern Registry for Agent Guru.

Manages the registry of voice command patterns, aliases, and variations.
Provides O(1) lookup by intent type and supports dynamic registration.

Performance:
    - Pattern lookup: O(1) by intent type
    - Pattern match: O(n) via FastIntentRouter
    - Registration: O(k) where k = pattern length

Author: Agent Guru Team
Date: 2026-03-19
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class CommandPattern:
    """A single registered command pattern.

    Attributes:
        pattern: Pattern string with optional {entity} placeholders
        intent: Intent type this pattern maps to
        entities: Entity name → EntityType mapping
        aliases: Alternative phrasings for the same command
        examples: Example utterances for documentation

    """

    pattern: str
    intent: str
    entities: dict[str, str] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


class CommandRegistry:
    """Registry of voice command patterns with alias support.

    Stores all registered patterns indexed by intent type for fast
    retrieval. Supports loading from YAML and dynamic registration.

    Example:
        >>> registry = CommandRegistry()
        >>> registry.load_from_yaml("data/intent_patterns.yaml")
        >>> patterns = registry.get_patterns_for_intent("open_app")
        >>> len(patterns) > 0
        True
        >>> registry.register(CommandPattern(
        ...     pattern="boot up {app}",
        ...     intent="open_app",
        ...     entities={"app": "APP"},
        ...     aliases=["fire up {app}", "run {app}"],
        ... ))

    """

    def __init__(self) -> None:
        """Initialize an empty command registry."""
        # intent_type → list of patterns (O(1) lookup by intent)
        self._by_intent: dict[str, list[CommandPattern]] = {}
        # flat list of all patterns (for router reload)
        self._all_patterns: list[CommandPattern] = []

    def load_from_yaml(self, path: str | Path) -> None:
        """Load patterns from a YAML file.

        Args:
            path: Path to intent_patterns.yaml

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the YAML structure is invalid.

        """
        path = Path(path)
        if not path.exists():
            msg = f"Patterns file not found: {path}"
            raise FileNotFoundError(msg)

        with open(path, encoding="utf-8") as f:  # noqa: PTH123
            data = yaml.safe_load(f)

        if "patterns" not in data:
            msg = "YAML must contain a 'patterns' key"
            raise ValueError(msg)

        for entry in data["patterns"]:
            cmd = CommandPattern(
                pattern=entry["pattern"],
                intent=entry["intent"],
                entities=entry.get("entities") or {},
            )
            self._register_internal(cmd)

    def register(self, command: CommandPattern) -> None:
        """Register a new command pattern and its aliases.

        Args:
            command: CommandPattern to register.

        """
        self._register_internal(command)
        # Also register each alias as a separate pattern
        for alias in command.aliases:
            alias_cmd = CommandPattern(
                pattern=alias,
                intent=command.intent,
                entities=command.entities,
            )
            self._register_internal(alias_cmd)

    def _register_internal(self, command: CommandPattern) -> None:
        """Internal registration without alias expansion."""
        intent = command.intent
        if intent not in self._by_intent:
            self._by_intent[intent] = []
        self._by_intent[intent].append(command)
        self._all_patterns.append(command)

    def get_patterns_for_intent(self, intent: str) -> list[CommandPattern]:
        """Return all patterns registered for a given intent type.

        Args:
            intent: Intent type string (e.g. "open_app")

        Returns:
            List of CommandPattern objects, empty if none registered.

        """
        return self._by_intent.get(intent, [])

    def get_all_intents(self) -> list[str]:
        """Return sorted list of all registered intent types."""
        return sorted(self._by_intent.keys())

    def get_all_patterns(self) -> list[CommandPattern]:
        """Return all registered patterns."""
        return list(self._all_patterns)

    def count(self) -> int:
        """Return total number of registered patterns."""
        return len(self._all_patterns)

    def to_dict_list(self) -> list[dict[str, Any]]:
        """Serialize all patterns to list of dicts (for router reload).

        Returns:
            List of dicts compatible with FastIntentRouter.load_patterns().

        """
        return [
            {
                "pattern": cmd.pattern,
                "intent": cmd.intent,
                "entities": cmd.entities,
            }
            for cmd in self._all_patterns
        ]

    def __len__(self) -> int:
        """Return total number of registered patterns."""
        return self.count()

    def __contains__(self, intent: str) -> bool:
        """Check if an intent type has any registered patterns."""
        return intent in self._by_intent
