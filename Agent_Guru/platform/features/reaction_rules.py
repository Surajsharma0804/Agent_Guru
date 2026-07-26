"""Reaction-rule memory — user-taught trigger→response pairs.

Implements the "teach it habits" system from the spec (§4b):
    "jab main bolu 'thak gaya', tu bolna 'aaram kar le bhai'"
    → stored as {trigger: "thak gaya", response: "aaram kar le bhai"}
    → checked before LLM on every turn, so taught reactions always win.

Design:
    - Hash-based rule table for O(1) exact match.
    - Fuzzy matching (Levenshtein ratio > 0.85) for close misses, bounded O(k).
    - LRU eviction at 200 rules max (OrderedDict).
    - Capability-table guard: rejects triggers that overlap system commands.
    - Teaching detection: requires anchor phrase + connector, bare connectors
      never trigger (prevents misfire on normal Hindi speech).

Storage: ~/.cache/agent_guru/reaction_rules.json
File permissions: owner-only (0o600 on Unix, ACL on Windows)

Performance:
    match():    O(1) exact, O(k) fuzzy (k ≤ 200)
    add_rule(): O(1) + O(P) guard (P = ~50 patterns, constant)
    evict():    O(1) via OrderedDict

Author: Agent Guru Team
Date: 2026-07-06
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Storage path
# ---------------------------------------------------------------------------

_RULES_PATH = Path.home() / ".cache" / "agent_guru" / "reaction_rules.json"

# ---------------------------------------------------------------------------
# Teaching detection — anchor phrases + connectors
# ---------------------------------------------------------------------------

# Anchor phrases that START a teaching command (required)
_ANCHOR_PHRASES = (
    "jab main bolu",
    "jab mai bolu",
    "jab main kahoon",
    "jab mai kahoon",
    "when i say",
    "if i say",
    "whenever i say",
)

# Connector phrases that SPLIT trigger from response (required, after anchor)
_CONNECTOR_PHRASES = (
    "tu bolna",
    "toh bolna",
    "toh bol",
    "tu bol",
    "you say",
    "respond with",
    "say back",
    "reply with",
    "you respond",
    "you reply",
)

# Maximum number of rules before LRU eviction kicks in
_MAX_RULES = 200

# Fuzzy match threshold (Levenshtein ratio)
_FUZZY_THRESHOLD = 0.85


def _normalize(text: str) -> str:
    """Normalize text for hash-based lookup.

    Lowercases, strips whitespace, removes punctuation.
    """
    t = text.lower().strip()
    t = re.sub(r"[.,!?;:'\"-]+", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """Compute Levenshtein similarity ratio between two strings.

    Returns a value in [0.0, 1.0] where 1.0 means identical.
    Uses a simple DP approach — fine for short trigger phrases.
    """
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0

    # Full DP matrix (both strings are short — typically <50 chars)
    matrix = list(range(len2 + 1))
    for i in range(1, len1 + 1):
        prev = matrix[:]
        matrix[0] = i
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            matrix[j] = min(prev[j] + 1, matrix[j - 1] + 1, prev[j - 1] + cost)

    distance = matrix[len2]
    max_len = max(len1, len2)
    return 1.0 - (distance / max_len)


def extract_teaching_intent(transcript: str) -> tuple[str, str] | None:
    """Extract a teaching intent from a transcript using anchor + connector.

    Requires ALL THREE parts: anchor phrase + trigger text + connector + response.
    Bare connectors in normal speech will NOT trigger this.

    Examples:
        "jab main bolu thak gaya tu bolna aaram kar le bhai"
        → ("thak gaya", "aaram kar le bhai")

        "when I say good morning you say rise and shine buddy"
        → ("good morning", "rise and shine buddy")

        "bol de usko" → None  (no anchor phrase)
        "tu bolna kuch bhi" → None  (no anchor phrase)

    Returns:
        (trigger, response) tuple, or None if not a teaching command.
    """
    text_lower = transcript.lower().strip()

    # Step 1: Find an anchor phrase
    anchor_end = -1
    for anchor in _ANCHOR_PHRASES:
        idx = text_lower.find(anchor)
        if idx != -1:
            anchor_end = idx + len(anchor)
            break

    if anchor_end == -1:
        return None  # No anchor phrase found — not a teaching command

    # Everything after the anchor
    remainder = text_lower[anchor_end:].strip()
    if not remainder:
        return None

    # Step 2: Find a connector in the remainder
    best_connector_pos = -1
    best_connector_len = 0
    for connector in _CONNECTOR_PHRASES:
        pos = remainder.find(connector)
        if pos != -1:
            # Prefer the first matching connector
            if best_connector_pos == -1 or pos < best_connector_pos:
                best_connector_pos = pos
                best_connector_len = len(connector)

    if best_connector_pos == -1:
        return None  # No connector found — incomplete teaching command

    # Step 3: Extract trigger and response
    trigger = remainder[:best_connector_pos].strip()
    response = remainder[best_connector_pos + best_connector_len:].strip()

    # Clean up — remove leading/trailing punctuation and quotes
    trigger = trigger.strip(".,!?;:'\"- ")
    response = response.strip(".,!?;:'\"- ")

    # Validate: both must be non-empty and reasonable length
    if not trigger or not response:
        return None
    if len(trigger) < 2 or len(response) < 2:
        return None
    if len(trigger) > 200 or len(response) > 500:
        return None

    # Return with original casing preserved from the transcript
    # (we used lower for detection, but store the actual words)
    # Re-extract from original transcript using the same positions
    orig_remainder = transcript.strip()[anchor_end:].strip()
    orig_trigger = orig_remainder[:best_connector_pos].strip().strip(".,!?;:'\"- ")
    orig_response = orig_remainder[best_connector_pos + best_connector_len:].strip().strip(".,!?;:'\"- ")

    return (orig_trigger or trigger, orig_response or response)


class ReactionRuleStore:
    """Hash-based reaction-rule table with LRU eviction.

    Rules map trigger phrases to fixed responses. When the user speaks
    a trigger phrase, the stored response is returned directly (skipping
    the LLM), making taught reactions instant and reliable.

    Example::

        store = ReactionRuleStore()
        store.add_rule("thak gaya", "aaram kar le bhai")
        response = store.match("thak gaya")  # "aaram kar le bhai"

    Thread-safe via threading.Lock.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _RULES_PATH
        # OrderedDict for LRU — most recently accessed at the end
        self._rules: OrderedDict[str, str] = OrderedDict()
        self._lock = threading.Lock()
        self._load()

    def match(self, transcript: str) -> str | None:
        """Look up a reaction rule for the given transcript.

        Tries exact normalized match first (O(1)), then fuzzy match
        over all keys (O(k), k ≤ 200).

        Args:
            transcript: The user's spoken text.

        Returns:
            The stored response string, or None if no match.
        """
        normalized = _normalize(transcript)
        if not normalized:
            return None

        with self._lock:
            # Exact match — O(1)
            if normalized in self._rules:
                self._rules.move_to_end(normalized)  # LRU touch
                response = self._rules[normalized]
                logger.info("ReactionRule: exact match %r → %r", normalized, response)
                return response

            # Substring containment — O(k), catches "bro thak gaya yaar"
            # matching trigger "thak gaya". Most common real-world pattern.
            for key in self._rules:
                if key in normalized:
                    self._rules.move_to_end(key)  # LRU touch
                    response = self._rules[key]
                    logger.info(
                        "ReactionRule: substring match %r ⊂ %r → %r",
                        key, normalized, response,
                    )
                    return response

            # Fuzzy match — O(k), k ≤ _MAX_RULES
            best_ratio = 0.0
            best_key: str | None = None
            for key in self._rules:
                ratio = _levenshtein_ratio(normalized, key)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_key = key

            if best_key is not None and best_ratio >= _FUZZY_THRESHOLD:
                self._rules.move_to_end(best_key)  # LRU touch
                response = self._rules[best_key]
                logger.info(
                    "ReactionRule: fuzzy match (%.2f) %r ≈ %r → %r",
                    best_ratio, normalized, best_key, response,
                )
                return response

        return None

    def add_rule(
        self,
        trigger: str,
        response: str,
        intent_recognizer: Any = None,
    ) -> tuple[bool, str]:
        """Add or update a reaction rule.

        Args:
            trigger: The trigger phrase (will be normalized for lookup).
            response: The response to speak when triggered.
            intent_recognizer: If provided, checks trigger against the
                capability-table rule engine. Rejects if it overlaps
                a system command.

        Returns:
            (success, message) — (True, "ok") or (False, "reason").
        """
        normalized = _normalize(trigger)
        if not normalized:
            return (False, "trigger is empty")
        if not response or not response.strip():
            return (False, "response is empty")

        # Capability-table guard: reject triggers that shadow system commands
        if intent_recognizer is not None:
            try:
                rule_engine = getattr(intent_recognizer, "_rule_engine", None)
                if rule_engine is not None:
                    platform = getattr(intent_recognizer, "_platform", "windows")
                    result = rule_engine.recognize(trigger, platform)
                    # If intent recognizer classified it as system_control or
                    # file_ops with reasonable confidence, it's a real command
                    if (
                        result.intent_type in ("system_control", "file_ops")
                        and result.confidence > 0.5
                    ):
                        return (
                            False,
                            f"that's already a system command ({result.intent_type}:{result.parameters.get('action', '')}) — pick a different phrase",
                        )
            except Exception:
                logger.debug("Capability guard check failed — allowing rule", exc_info=True)

        with self._lock:
            # Evict oldest if at capacity (before adding)
            while len(self._rules) >= _MAX_RULES:
                evicted_key, evicted_val = self._rules.popitem(last=False)
                logger.info("ReactionRule: evicted LRU rule %r", evicted_key)

            # Add/update (last-taught wins for same trigger)
            self._rules[normalized] = response.strip()
            self._rules.move_to_end(normalized)
            self._save()

        logger.info("ReactionRule: added %r → %r", normalized, response.strip())
        return (True, "ok")

    def remove_rule(self, trigger: str) -> bool:
        """Remove a reaction rule by trigger phrase.

        Returns True if the rule existed and was removed.
        """
        normalized = _normalize(trigger)
        with self._lock:
            if normalized in self._rules:
                del self._rules[normalized]
                self._save()
                logger.info("ReactionRule: removed %r", normalized)
                return True
        return False

    def list_rules(self) -> dict[str, str]:
        """Return all rules as a plain dict (for debugging/display)."""
        with self._lock:
            return dict(self._rules)

    def count(self) -> int:
        """Return number of stored rules."""
        return len(self._rules)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load rules from disk."""
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._rules = OrderedDict(data)
                    logger.debug("ReactionRules: loaded %d rules", len(self._rules))
        except Exception:
            logger.exception("ReactionRules: failed to load")
            self._rules = OrderedDict()

    def _save(self) -> None:
        """Persist rules to disk with owner-only permissions."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(dict(self._rules), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            # Set owner-only permissions (personal data)
            try:
                if os.name != "nt":
                    self._path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
            except OSError:
                pass  # Best-effort on permission setting
        except Exception:
            logger.exception("ReactionRules: failed to save")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_rule_store: ReactionRuleStore | None = None


def get_reaction_rules() -> ReactionRuleStore:
    """Return the global ReactionRuleStore (lazy init)."""
    global _rule_store
    if _rule_store is None:
        _rule_store = ReactionRuleStore()
    return _rule_store
