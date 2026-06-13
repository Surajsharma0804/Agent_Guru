"""Persistent user memory for Agent Guru.

Remembers facts about the user across sessions:
  - Name ("my name is Suraj" → remembered forever)
  - Preferences ("I prefer dark mode", "I like jazz music")
  - Frequently used apps
  - Custom shortcuts ("when I say 'work mode', open VS Code and Slack")

This is what makes the assistant feel personal rather than generic.
Alexa+ and Gemini both do this — they remember who you are.

Storage: JSON file in the user's app data directory.
No cloud, no sync — fully local and private.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Where we store user facts
_MEMORY_PATH = Path.home() / ".cache" / "agent_guru" / "user_memory.json"


class UserMemory:
    """Persistent key-value store for user facts.

    Facts are stored as a flat dict and persisted to disk immediately
    on every write. Reads are from the in-memory cache (fast).

    Example::

        mem = UserMemory()
        mem.set("name", "Suraj")
        mem.set("preferred_language", "Hindi")

        name = mem.get("name")  # "Suraj"
        summary = mem.get_summary()  # "User's name is Suraj. ..."
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or _MEMORY_PATH
        self._facts: dict[str, Any] = {}
        self._load()

    def set(self, key: str, value: Any) -> None:
        """Store a fact about the user."""
        self._facts[key] = value
        self._save()
        logger.debug("UserMemory: set %r = %r", key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a stored fact."""
        return self._facts.get(key, default)

    def delete(self, key: str) -> bool:
        """Remove a stored fact."""
        if key in self._facts:
            del self._facts[key]
            self._save()
            return True
        return False

    def get_all(self) -> dict[str, Any]:
        """Return all stored facts."""
        return dict(self._facts)

    def get_summary(self, max_chars: int = 500) -> str:
        """Return a natural language summary of known user facts.

        This gets injected into the LLM system prompt so the assistant
        can refer to the user by name and remember their preferences,
        goals, relationships, and frequently discussed topics.
        """
        if not self._facts:
            return ""

        parts = []

        # Identity
        if "name" in self._facts:
            parts.append(f"The user's name is {self._facts['name']}.")
        if "preferred_language" in self._facts:
            parts.append(f"They prefer to speak in {self._facts['preferred_language']}.")
        if "location" in self._facts:
            parts.append(f"They are located in {self._facts['location']}.")
        if "occupation" in self._facts:
            parts.append(f"They work as a {self._facts['occupation']}.")
        if "age" in self._facts:
            parts.append(f"They are {self._facts['age']} years old.")

        # Goals and projects
        if "current_goal" in self._facts:
            parts.append(f"Their current goal is: {self._facts['current_goal']}.")
        if "current_project" in self._facts:
            parts.append(f"They're currently working on: {self._facts['current_project']}.")

        # Personal context
        if "hobbies" in self._facts:
            parts.append(f"Their hobbies include: {self._facts['hobbies']}.")
        if "interests" in self._facts:
            parts.append(f"They're interested in: {self._facts['interests']}.")
        if "friends" in self._facts:
            parts.append(f"Friends/people they mention: {self._facts['friends']}.")
        if "family" in self._facts:
            parts.append(f"Family context: {self._facts['family']}.")

        # Preferences
        if "communication_style" in self._facts:
            parts.append(f"They prefer a {self._facts['communication_style']} communication style.")

        # Any other facts
        for k, v in self._facts.items():
            if k not in _SUMMARY_SKIP_KEYS:
                parts.append(f"They mentioned: {k} = {v}.")

        summary = " ".join(parts)
        return summary[:max_chars]

    def _load(self) -> None:
        """Load facts from disk."""
        try:
            if self._path.exists():
                self._facts = json.loads(self._path.read_text(encoding="utf-8"))
                logger.debug("UserMemory: loaded %d facts", len(self._facts))
        except Exception as exc:
            logger.warning("UserMemory: failed to load: %s", exc)
            self._facts = {}

    def _save(self) -> None:
        """Persist facts to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._facts, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("UserMemory: failed to save: %s", exc)


# Module-level singleton — shared across the whole app
_user_memory: Optional[UserMemory] = None


def get_user_memory() -> UserMemory:
    """Return the global UserMemory instance (lazy init)."""
    global _user_memory
    if _user_memory is None:
        _user_memory = UserMemory()
    return _user_memory

# ── Module-level constants ────────────────────────────────────────────────

# Keys handled explicitly by get_summary() — hoisted from per-call set creation
_SUMMARY_SKIP_KEYS = frozenset({
    "name", "preferred_language", "location", "occupation", "age",
    "current_goal", "current_project", "hobbies", "interests",
    "friends", "family", "communication_style",
})

# Precompiled regex patterns for fact extraction.
# Previously: 22 raw strings compiled by re.search() on EVERY call.
# Now: compiled once at import time. re.compile() returns a cached Pattern
# object — subsequent .search() calls skip the compile step entirely.
_FACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Identity
    (re.compile(r"my name is (.+)", re.I), "name"),
    (re.compile(r"call me (.+)", re.I), "name"),
    (re.compile(r"i(?:'m| am) (.+?) (?:and|,|\.)", re.I), "name"),
    (re.compile(r"i live in (.+)", re.I), "location"),
    (re.compile(r"i(?:'m| am) from (.+)", re.I), "location"),
    (re.compile(r"i work as (?:a |an )?(.+)", re.I), "occupation"),
    (re.compile(r"i(?:'m| am) (\d+)(?: years old)?", re.I), "age"),
    # Goals and projects — BEFORE the generic "I am a ..." occupation pattern
    (re.compile(r"my goal is (?:to )?(.+)", re.I), "current_goal"),
    (re.compile(r"i(?:'m| am) trying to (.+)", re.I), "current_goal"),
    (re.compile(r"i want to (.+)", re.I), "current_goal"),
    (re.compile(r"i(?:'m| am) (?:currently )?working on (.+)", re.I), "current_project"),
    (re.compile(r"my (?:current )?project is (.+)", re.I), "current_project"),
    (re.compile(r"i(?:'m| am) building (.+)", re.I), "current_project"),
    # Generic occupation — after project patterns
    (re.compile(r"i(?:'m| am) (?:a |an )?(.+?)(?:\s+and|\s*$)", re.I), "occupation"),
    (re.compile(r"i prefer (.+?) (?:language|lang)", re.I), "preferred_language"),
    (re.compile(r"i speak (.+)", re.I), "preferred_language"),
    # Hobbies and interests
    (re.compile(r"i (?:love|enjoy|like) (.+)", re.I), "hobbies"),
    (re.compile(r"my hobb(?:y|ies) (?:is|are|include) (.+)", re.I), "hobbies"),
    (re.compile(r"i(?:'m| am) (?:into|interested in) (.+)", re.I), "interests"),
    # Relationships
    (re.compile(r"my (?:best )?friend(?:s)? (?:is|are) (.+)", re.I), "friends"),
    (re.compile(r"my (?:wife|husband|partner|girlfriend|boyfriend) (?:is )?(?:named )?(.+)", re.I), "family"),
    (re.compile(r"my (?:mom|mother|dad|father|sister|brother) (?:is )?(?:named )?(.+)", re.I), "family"),
    # Communication style
    (re.compile(r"i prefer (?:a )?(.+?) (?:tone|style|approach)", re.I), "communication_style"),
]


def extract_user_fact(transcript: str) -> Optional[tuple[str, str]]:
    """Try to extract a user fact from a transcript.

    Covers identity, goals, projects, relationships, hobbies, and preferences.

    Time:  O(P × T) where P = 22 patterns (constant), T = transcript length.
           Short-circuits on first match, so average case is much faster.
    Space: O(1) beyond the return value.

    Examples:
        "my name is Suraj" → ("name", "Suraj")
        "I live in Mumbai" → ("location", "Mumbai")
        "I am a software engineer" → ("occupation", "software engineer")
        "I prefer Hindi" → ("preferred_language", "Hindi")
        "my goal is to launch my app this month" → ("current_goal", "launch my app this month")
        "I'm working on a Django project" → ("current_project", "a Django project")
        "I love hiking and photography" → ("hobbies", "hiking and photography")
        "my best friend is Arjun" → ("friends", "Arjun")

    Returns:
        (key, value) tuple or None if no fact found.
    """
    t = transcript.strip()

    for compiled_pattern, key in _FACT_PATTERNS:
        m = compiled_pattern.search(t)
        if m:
            value = m.group(1).strip().rstrip(".,!?")
            if 1 < len(value) < 150:
                return key, value

    return None
