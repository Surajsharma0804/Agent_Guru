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
from typing import Any

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

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _MEMORY_PATH
        self._facts: dict[str, Any] = {}
        self._load()

    def set(self, key: str, value: Any) -> None:  # noqa: ANN401
        """Store a fact about the user."""
        self._facts[key] = value
        self._save()
        logger.debug("UserMemory: set %r = %r", key, value)

    def get(self, key: str, default: Any = None) -> Any:  # noqa: ANN401
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

    def get_summary(self, max_chars: int = 300) -> str:
        """Return a natural language summary of known user facts.

        This gets injected into the LLM system prompt so the assistant
        can refer to the user by name and remember their preferences.
        """
        if not self._facts:
            return ""

        parts = []
        if "name" in self._facts:
            parts.append(f"The user's name is {self._facts['name']}.")
        if "preferred_language" in self._facts:
            parts.append(f"They prefer to speak in {self._facts['preferred_language']}.")
        if "location" in self._facts:
            parts.append(f"They are located in {self._facts['location']}.")
        if "occupation" in self._facts:
            parts.append(f"They work as a {self._facts['occupation']}.")

        # Add any other facts
        skip = {"name", "preferred_language", "location", "occupation"}
        for k, v in self._facts.items():
            if k not in skip:
                parts.append(f"They mentioned: {k} = {v}.")

        summary = " ".join(parts)
        return summary[:max_chars]

    def _load(self) -> None:
        """Load facts from disk."""
        try:
            if self._path.exists():
                self._facts = json.loads(self._path.read_text(encoding="utf-8"))
                logger.debug("UserMemory: loaded %d facts", len(self._facts))
        except Exception:
            logger.exception("UserMemory: failed to load")
            self._facts = {}

    def _save(self) -> None:
        """Persist facts to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._facts, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("UserMemory: failed to save")


# Module-level singleton — shared across the whole app
_user_memory: UserMemory | None = None


def get_user_memory() -> UserMemory:
    """Return the global UserMemory instance (lazy init)."""
    global _user_memory
    if _user_memory is None:
        _user_memory = UserMemory()
    return _user_memory


def extract_user_fact(transcript: str) -> tuple[str, str] | None:
    """Try to extract a user fact from a transcript.

    Examples:
        "my name is Suraj" → ("name", "Suraj")
        "I live in Mumbai" → ("location", "Mumbai")
        "I am a software engineer" → ("occupation", "software engineer")
        "I prefer Hindi" → ("preferred_language", "Hindi")

    Returns:
        (key, value) tuple or None if no fact found.

    """
    t = transcript.strip()

    patterns = [
        (r"my name is (.+)", "name"),
        (r"call me (.+)", "name"),
        (r"i(?:'m| am) (.+?) (?:and|,|\.)", "name"),  # "I'm Suraj and..."
        (r"i live in (.+)", "location"),
        (r"i(?:'m| am) from (.+)", "location"),
        (r"i(?:'m| am) (?:a |an )?(.+?)(?:\s+and|\s*$)", "occupation"),
        (r"i work as (?:a |an )?(.+)", "occupation"),
        (r"i prefer (.+?) (?:language|lang)", "preferred_language"),
        (r"i speak (.+)", "preferred_language"),
    ]

    for pattern, key in patterns:
        m = re.search(pattern, t, re.IGNORECASE)
        if m:
            value = m.group(1).strip().rstrip(".,!?")
            if len(value) > 1 and len(value) < 100:  # noqa: PLR2004 - Percentage/large threshold

                return key, value

    return None
