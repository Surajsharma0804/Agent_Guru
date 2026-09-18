"""Persistent user memory for Agent Guru.

Remembers facts about the user across sessions:
  - Name / nickname ("my name is Suraj", "call me Chotu")
  - Preferences ("I prefer dark mode", "I like jazz music")
  - Code-mixing preference (defaults to Hinglish-on)
  - Generic facts via "remember that X" / "yaad rakh ki X"
  - Frequently used apps

This is what makes the assistant feel personal rather than generic.
Alexa+ and Gemini both do this — they remember who you are.

Storage: JSON file in the user's app data directory.
No cloud, no sync — fully local and private.
File permissions: owner-only (0o600 on Unix, best-effort icacls ACL
restriction on Windows — see _restrict_file_permissions()).

Memory architecture:
  - PINNED keys (nickname, name, code_mixing, etc.) are never evicted.
  - CUSTOM FACT keys (custom_fact_N) are LRU-evicted at 100 max.
  "It forgot my name" is far worse than losing an old miscellaneous fact.

Fixed (this revision):
    - self._lock previously only wrapped the disk I/O inside _save()/_load(),
      not the actual dict/OrderedDict mutations in set()/get()/delete() — so
      two concurrent calls (this module's own docstring anticipates "two
      tasks extracting facts at once" from the async pipeline) could race on
      self._facts / self._custom_facts_lru itself, not just the file write.
      _save()/_load() no longer take the lock themselves; every public
      method that touches state now wraps its whole body in `with
      self._lock:` instead, matching the pattern already used in this
      codebase's sibling module (reaction_rules.py).
    - get_user_memory()'s singleton creation had no lock at all (a real race
      if ever called from concurrent tasks — the same class of bug already
      fixed in reaction_rules.get_reaction_rules()). Added double-checked
      locking to match.
    - The module docstring claimed "ACL on Windows" for file permissions,
      but the code only ever called chmod() (a no-op on Windows), silently
      leaving personal data (name, location, family, hobbies) with default/
      inherited permissions on that platform. Added the same best-effort
      icacls-based restriction already used in reaction_rules.py.
    - _load() didn't validate that the parsed JSON was actually a dict
      before assigning it to self._facts — a corrupted or unexpected file
      (e.g. a JSON list) would silently break every subsequent .get()/.set()
      call. Now falls back to {} if the loaded value isn't a dict, matching
      reaction_rules.py's same defensive check.
    - _custom_fact_counter was a bare in-memory module global that resets to
      0 every process restart. Since it isn't persisted, the first "remember
      that X" after any restart would be assigned custom_fact_1 again —
      silently OVERWRITING whatever the user had previously asked to
      remember under that key. Replaced with a function that derives the
      next free index from what's actually persisted (via the already-
      loaded singleton), so correctness depends on saved state rather than
      an in-memory counter that doesn't survive the process it counts
      within. Residual limitation: two "remember" extractions in the same
      turn, before either is persisted, could still compute the same next
      index — same class of caveat as reaction_rules.py's documented
      leftmost-connector limitation; not fixed here since it needs the
      caller to persist between extractions, not a change to this function.
    - The generic "I am X [and/,/.]" pattern used for `name` extraction ran
      third in the pattern list — BEFORE current_goal / current_project /
      interests / age patterns — and its capture group was `.+?` with no
      constraint on content. Any sentence shaped "I am <anything> and/,/."
      (e.g. "I am trying to lose weight and get fit", "I am so tired and
      need rest") matched THIS pattern first and got stored as the user's
      `name` — a PINNED, never-evicted identity key — instead of falling
      through to the more specific pattern that actually applied. Now
      requires the captured span to look like a proper noun (1-3
      capitalized words), which the more free-form patterns don't produce.
      Known limitation: this depends on STT preserving capitalization for
      names, which isn't guaranteed for every STT backend — if names aren't
      being picked up, "my name is X" (a separate, unconstrained pattern)
      still works regardless of case.
    - The generic occupation catch-all (last of the "I am ..." patterns)
      had an optional article — `(?:a |an )?` — so any otherwise-unmatched
      "I am <filler>" sentence ("I am fine", "I am good", "I am here") was
      stored as the user's occupation. Made the article required, since
      real occupation statements are almost always phrased with one
      ("I am a teacher") while conversational filler almost never is.
    - Added a guard in set() against literally persisting the "__forget__"
      sentinel key that extract_user_fact() returns for forget-commands —
      that value is meant for the caller to interpret and act on (find +
      delete a matching fact), not to be stored as a fact itself. Cheap
      defense against a caller passing it straight through.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

# DE-DUPLICATION: this module and speech/biometric/speaker_verifier.py each
# carried a byte-identical private copy of _restrict_file_permissions (their
# docstrings even cite one another). There is now one implementation, and
# secure_write_bytes additionally closes the window in which the file sat on
# disk under the process umask before the chmod landed.
from Agent_Guru.utils.secure_file import restrict_file_permissions, secure_write_bytes

logger = logging.getLogger(__name__)

#: Back-compat alias for the former module-private helper.
_restrict_file_permissions = restrict_file_permissions

# Where we store user facts
_MEMORY_PATH = Path.home() / ".cache" / "agent_guru" / "user_memory.json"


class UserMemory:
    """Persistent key-value store for user facts.

    Two storage tiers:
      - PINNED facts (identity, preferences) — never evicted
      - CUSTOM facts (generic "remember that X") — LRU-evicted at 100 max

    Thread-safe: every public method that reads or mutates state acquires
    self._lock for its entire body (not just the disk write).

    Example::

        mem = UserMemory()
        mem.set("name", "Suraj")
        mem.set("nickname", "Chotu")  # distinct from name
        mem.set("code_mixing", "hinglish")  # default for fresh installs

        name = mem.get("name")  # "Suraj"
        summary = mem.get_summary()  # "Address the user as Chotu. ..."
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _MEMORY_PATH
        self._facts: dict[str, Any] = {}
        # LRU tracker for custom facts only (pinned keys are excluded)
        self._custom_facts_lru: OrderedDict[str, bool] = OrderedDict()
        # Thread safety: protects ALL reads/mutations of self._facts and
        # self._custom_facts_lru, not just the disk write — see the "Fixed"
        # note in the module docstring.
        self._lock = threading.Lock()
        self._load()

    def set(self, key: str, value: Any) -> None:
        """Store a fact about the user.

        For list-type keys (hobbies, interests, friends), new values are
        MERGED with existing ones instead of overwriting. This matches
        the behavior of Alexa+ and ChatGPT memory — users accumulate
        preferences over time, they don't replace them.

        Custom fact keys (not in _PINNED_KEYS) are LRU-tracked and
        evicted at _MAX_CUSTOM_FACTS to keep memory bounded.
        """
        if key == "__forget__":
            # FIX: this is a sentinel extract_user_fact() returns for the
            # caller to interpret (find + delete a matching fact) — it must
            # never be persisted as a literal fact key.
            logger.debug("UserMemory.set: ignoring literal '__forget__' key")
            return

        with self._lock:
            if key in _MERGEABLE_KEYS and key in self._facts:
                # Merge: split both old and new by separators, deduplicate
                existing = self._facts[key]
                merged = _merge_values(existing, value)
                if merged == existing:
                    return  # No change — skip disk write
                self._facts[key] = merged
            else:
                if self._facts.get(key) == value:
                    return  # No change — skip disk write
                self._facts[key] = value

            # LRU tracking for custom facts (pinned keys are exempt)
            if key not in _PINNED_KEYS:
                self._custom_facts_lru[key] = True
                self._custom_facts_lru.move_to_end(key)
                # Evict oldest custom facts if over limit
                while len(self._custom_facts_lru) > _MAX_CUSTOM_FACTS:
                    evicted_key, _ = self._custom_facts_lru.popitem(last=False)
                    self._facts.pop(evicted_key, None)
                    logger.info("UserMemory: evicted LRU custom fact %r", evicted_key)

            self._save_locked()
            logger.debug("UserMemory: set %r = %r", key, self._facts[key])

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a stored fact. Touches LRU for custom facts."""
        with self._lock:
            value = self._facts.get(key, default)
            # Touch LRU for custom facts on read (pinned keys exempt)
            if key not in _PINNED_KEYS and key in self._custom_facts_lru:
                self._custom_facts_lru.move_to_end(key)
            return value

    def delete(self, key: str) -> bool:
        """Remove a stored fact."""
        with self._lock:
            if key in self._facts:
                del self._facts[key]
                self._custom_facts_lru.pop(key, None)
                self._save_locked()
                return True
            return False

    def get_all(self) -> dict[str, Any]:
        """Return all stored facts."""
        with self._lock:
            return dict(self._facts)

    def get_summary(self, max_chars: int = 500) -> str:
        """Return a natural language summary of known user facts.

        This gets injected into the LLM system prompt so the assistant
        can refer to the user by name and remember their preferences,
        goals, relationships, and frequently discussed topics.

        Nickname takes precedence over name for addressing.
        """
        with self._lock:
            facts = dict(self._facts)

        if not facts:
            return ""

        parts = []

        # Identity — nickname takes priority over name for addressing
        if "nickname" in facts:
            parts.append(
                f"ALWAYS address the user as {facts['nickname']}, "
                f"not by their full name."
            )
        if "name" in facts:
            parts.append(f"The user's name is {facts['name']}.")
        if "preferred_language" in facts:
            parts.append(f"They prefer to speak in {facts['preferred_language']}.")
        if "code_mixing" in facts:
            cm = facts["code_mixing"]
            if cm == "hinglish":
                parts.append("They prefer Hindi-English code-mixing (Hinglish).")
            elif cm == "english":
                parts.append("They prefer pure English — no Hindi mixing.")
        if "location" in facts:
            parts.append(f"They are located in {facts['location']}.")
        if "occupation" in facts:
            parts.append(f"They work as a {facts['occupation']}.")
        if "age" in facts:
            parts.append(f"They are {facts['age']} years old.")

        # Goals and projects
        if "current_goal" in facts:
            parts.append(f"Their current goal is: {facts['current_goal']}.")
        if "current_project" in facts:
            parts.append(f"They're currently working on: {facts['current_project']}.")

        # Personal context
        if "hobbies" in facts:
            parts.append(f"Their hobbies include: {facts['hobbies']}.")
        if "interests" in facts:
            parts.append(f"They're interested in: {facts['interests']}.")
        if "friends" in facts:
            parts.append(f"Friends/people they mention: {facts['friends']}.")
        if "family" in facts:
            parts.append(f"Family context: {facts['family']}.")

        # Preferences
        if "communication_style" in facts:
            parts.append(f"They prefer a {facts['communication_style']} communication style.")

        # Any other facts (custom facts, etc.)
        for k, v in facts.items():
            if k not in _SUMMARY_SKIP_KEYS:
                parts.append(f"They mentioned: {k} = {v}.")

        summary = " ".join(parts)
        return summary[:max_chars]

    def _load(self) -> None:
        """Load facts from disk. Only called from __init__, before the
        instance is shared with any other thread/task — no lock needed
        here, matching reaction_rules.py's ReactionRuleStore._load().

        Also rebuilds the LRU tracker for custom facts.
        """
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                # FIX: previously assigned `data` to self._facts with no
                # type check — a corrupted or unexpected file (e.g. a JSON
                # list) would silently break every subsequent get()/set()
                # call. Matches reaction_rules.py's same defensive check.
                if isinstance(data, dict):
                    self._facts = data
                    # Rebuild LRU tracker for custom facts
                    self._custom_facts_lru = OrderedDict()
                    for k in self._facts:
                        if k not in _PINNED_KEYS:
                            self._custom_facts_lru[k] = True
                    logger.debug(
                        "UserMemory: loaded %d facts (%d pinned, %d custom)",
                        len(self._facts),
                        sum(1 for k in self._facts if k in _PINNED_KEYS),
                        len(self._custom_facts_lru),
                    )
                else:
                    logger.warning(
                        "UserMemory: %s did not contain a JSON object — ignoring",
                        self._path,
                    )
        except Exception:
            logger.exception("UserMemory: failed to load")
            self._facts = {}

    def _save_locked(self) -> None:
        """Persist facts to disk. Caller MUST already hold self._lock.

        FIX: previously named _save() and acquired self._lock itself, but
        set()/delete() didn't hold the lock around their own dict mutations
        before calling it — so the lock only ever protected the file write,
        not the in-memory state (see module docstring). Renamed to make the
        "caller holds the lock" contract explicit; all call sites are
        methods that already wrap their whole body in `with self._lock:`.
        threading.Lock is non-reentrant, so this must never acquire the
        lock itself.
        """
        try:
            # Owner-only from the first byte, and replaced atomically. The
            # previous write_text()-then-chmod sequence left the user's facts
            # world-readable for the duration of the write, and truncated the
            # existing file first, so a crash mid-save lost every remembered
            # fact instead of keeping the last good copy.
            secure_write_bytes(
                self._path,
                json.dumps(self._facts, indent=2, ensure_ascii=False).encode("utf-8"),
            )
        except Exception:
            logger.exception("UserMemory: failed to save")


# Module-level singleton — shared across the whole app
_user_memory: UserMemory | None = None
_user_memory_lock = threading.Lock()


def get_user_memory() -> UserMemory:
    """Return the global UserMemory instance (lazy init, thread-safe).

    FIX: previously a bare `if _user_memory is None: _user_memory = ...`
    with no lock at all — a real race if ever called from concurrent tasks
    (this module's own docstring anticipates "two tasks extracting facts at
    once"). Added double-checked locking, matching
    reaction_rules.get_reaction_rules()'s already-fixed pattern.
    """
    global _user_memory
    if _user_memory is None:
        with _user_memory_lock:
            if _user_memory is None:
                _user_memory = UserMemory()
    return _user_memory

# ── Module-level constants ────────────────────────────────────────────────

# PINNED KEYS — identity and preference keys that are NEVER LRU-evicted.
# "It forgot my name" is far worse than losing an old miscellaneous fact.
_PINNED_KEYS = frozenset({
    "nickname", "name", "preferred_language", "location", "occupation",
    "age", "current_goal", "current_project", "hobbies", "interests",
    "friends", "family", "communication_style", "code_mixing",
})

# Maximum number of custom (non-pinned) facts before LRU eviction
_MAX_CUSTOM_FACTS = 100

# Keys handled explicitly by get_summary() — hoisted from per-call set creation
_SUMMARY_SKIP_KEYS = frozenset({
    "nickname", "name", "preferred_language", "code_mixing",
    "location", "occupation", "age",
    "current_goal", "current_project", "hobbies", "interests",
    "friends", "family", "communication_style",
    "__forget__",  # never actually stored (see set()'s guard) — belt & suspenders
})

# Keys where values should MERGE instead of overwrite.
# "I love hiking" + "I love photography" → "hiking, photography"
# This is what Alexa+ and ChatGPT do — accumulate, don't replace.
_MERGEABLE_KEYS = frozenset({"hobbies", "interests", "friends"})

# Separator pattern for splitting merged values
_SPLIT_RE = re.compile(r"\s*(?:,|\band\b)\s*", re.I)


def _merge_values(existing: str, new: str) -> str:
    """Merge two fact values, deduplicating entries.

    'hiking' + 'photography' → 'hiking, photography'
    'hiking, photography' + 'hiking' → 'hiking, photography' (no dupe)
    """
    old_parts = [p.strip().lower() for p in _SPLIT_RE.split(str(existing)) if p.strip()]
    # new values are split and deduplicated in the loop below
    # Preserve original case from existing, add new ones
    seen = set(old_parts)
    merged = [p.strip() for p in _SPLIT_RE.split(str(existing)) if p.strip()]
    for part in _SPLIT_RE.split(str(new)):
        part = part.strip()
        if part and part.lower() not in seen:
            merged.append(part)
            seen.add(part.lower())
    return ", ".join(merged)

# Precompiled regex patterns for fact extraction.
# Previously: 22 raw strings compiled by re.search() on EVERY call.
# Now: compiled once at import time. re.compile() returns a cached Pattern
# object — subsequent .search() calls skip the compile step entirely.
_FACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Identity — nickname is DISTINCT from name
    (re.compile(r"my name is (.+)", re.I), "name"),
    (re.compile(r"call me (.+)", re.I), "nickname"),  # "call me" → nickname, not name
    # FIX: previously `i(?:'m| am) (.+?) (?:and|,|\.)` with an unconstrained
    # capture group — this ran BEFORE current_goal/current_project/
    # interests/age below, so ANY "I am <anything> and/,/." sentence
    # ("I am trying to lose weight and get fit", "I am so tired and need
    # rest") matched HERE first and got stored as the user's `name` (a
    # PINNED, never-evicted key) instead of falling through to the pattern
    # that actually applied. Now requires the captured span to look like a
    # proper noun (1-3 capitalized words) via a scoped case-sensitive group,
    # so free-form clauses (which are virtually never Title-Cased) no
    # longer qualify. Depends on STT preserving name capitalization; if it
    # doesn't, "my name is X" (unconstrained, above) still works.
    (re.compile(r"(?i:i(?:'m| am)) ([A-Z][a-zA-Z]*(?:\s[A-Z][a-zA-Z]*){0,2})(?:\s+and\b|,|\.)"), "name"),
    (re.compile(r"i live in (.+)", re.I), "location"),
    (re.compile(r"i(?:'m| am) from (.+)", re.I), "location"),
    (re.compile(r"i work as (?:a |an )?(.+)", re.I), "occupation"),
    (re.compile(r"i(?:'m| am) (\d+)(?: years old)?", re.I), "age"),
    # Code-mixing preference
    (re.compile(r"talk to me in (?:only )?english(?:\s+only)?", re.I), "code_mixing_english"),
    (re.compile(r"(?:talk|speak) (?:to me )?in hinglish", re.I), "code_mixing_hinglish"),
    (re.compile(r"(?:talk|speak) (?:to me )?in hindi", re.I), "code_mixing_hinglish"),
    # Hindi-phrased code-mixing preferences
    (re.compile(r"hinglish mein (?:baat|baat kar|bol)", re.I), "code_mixing_hinglish"),
    (re.compile(r"hindi mein (?:baat|baat kar|bol)", re.I), "code_mixing_hinglish"),
    (re.compile(r"(?:sirf |only )?english mein (?:baat|baat kar|bol)", re.I), "code_mixing_english"),
    (re.compile(r"sirf english", re.I), "code_mixing_english"),
    # Goals and projects — BEFORE the generic "I am a ..." occupation pattern
    (re.compile(r"my goal is (?:to )?(.+)", re.I), "current_goal"),
    (re.compile(r"i(?:'m| am) trying to (.+)", re.I), "current_goal"),
    (re.compile(r"i want to (.+)", re.I), "current_goal"),
    (re.compile(r"i(?:'m| am) (?:currently )?working on (.+)", re.I), "current_project"),
    (re.compile(r"my (?:current )?project is (.+)", re.I), "current_project"),
    (re.compile(r"i(?:'m| am) building (.+)", re.I), "current_project"),
    # Hobbies, interests, and preferences — BEFORE the generic occupation
    # fallback, because "I am into X" and "I am interested in X" would
    # otherwise match the generic "I am ..." occupation pattern.
    (re.compile(r"i (?:love|enjoy|like) (.+)", re.I), "hobbies"),
    (re.compile(r"my hobb(?:y|ies) (?:is|are|include) (.+)", re.I), "hobbies"),
    (re.compile(r"i(?:'m| am) (?:into|interested in) (.+)", re.I), "interests"),
    (re.compile(r"i prefer (?:a )?(.+?) (?:language|lang)", re.I), "preferred_language"),
    (re.compile(r"i speak (.+)", re.I), "preferred_language"),
    (re.compile(r"i prefer (?:a )?(.+?) (?:tone|style|approach)", re.I), "communication_style"),
    # Generic occupation — LAST of the "I am ..." patterns (catch-all).
    # FIX: the article `(?:a |an )?` was optional, so any otherwise-
    # unmatched "I am <filler>" ("I am fine", "I am good", "I am here")
    # was stored as occupation. Made the article required — real
    # occupation statements are almost always phrased with one ("I am a
    # teacher"), filler almost never is.
    (re.compile(r"i(?:'m| am) (?:a|an) (.+?)(?:\s+and|\s*$)", re.I), "occupation"),
    # Relationships
    (re.compile(r"my (?:best )?friend(?:s)? (?:is|are) (.+)", re.I), "friends"),
    (re.compile(r"my (?:wife|husband|partner|girlfriend|boyfriend) (?:is )?(?:named )?(.+)", re.I), "family"),
    (re.compile(r"my (?:mom|mother|dad|father|sister|brother) (?:is )?(?:named )?(.+)", re.I), "family"),
]


# Patterns for explicit "remember" / "forget" commands
_REMEMBER_RE = re.compile(
    r"(?:remember|yaad\s+rakh)\s+(?:that\s+|ki\s+)?(.+)", re.I
)
_FORGET_RE = re.compile(
    r"(?:forget|bhool\s+ja)\s+(?:that\s+|ki\s+)?(.+)", re.I
)

_CUSTOM_FACT_KEY_RE = re.compile(r"custom_fact_(\d+)$")


def _next_custom_fact_key() -> str:
    """Return the next unused custom_fact_N key.

    FIX: previously a bare module-level counter (`_custom_fact_counter`)
    that only lived in memory and reset to 0 on every process restart.
    Since it wasn't persisted, the first "remember that X" after any
    restart would be assigned custom_fact_1 again — silently OVERWRITING
    whatever the user had previously asked to remember under that key.
    Deriving the next index from what's actually persisted (via the
    already-loaded singleton) ties correctness to saved state instead of a
    counter that doesn't survive the process it's counting within.

    Residual limitation: two "remember" extractions in the same turn,
    before either has actually been persisted via UserMemory.set(), could
    still compute the same next index — fixing that needs the caller to
    persist between extractions, not a change here. Documented rather than
    speculatively patched, same spirit as reaction_rules.py's known
    leftmost-connector limitation.
    """
    existing = get_user_memory().get_all()
    max_n = 0
    for k in existing:
        m = _CUSTOM_FACT_KEY_RE.match(k)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"custom_fact_{max_n + 1}"


def extract_user_fact(transcript: str) -> tuple[str, str] | None:
    """Try to extract a user fact from a transcript.

    Covers identity, goals, projects, relationships, hobbies, preferences,
    nickname, code-mixing preference, and generic "remember that X".

    Time:  O(P × T) where P = ~25 patterns (constant), T = transcript length.
           Short-circuits on first match, so average case is much faster.
    Space: O(1) beyond the return value.

    Examples:
        "my name is Suraj" → ("name", "Suraj")
        "call me Chotu" → ("nickname", "Chotu")
        "talk to me in English only" → ("code_mixing", "english")
        "I live in Mumbai" → ("location", "Mumbai")
        "remember that my exam is on Monday" → ("custom_fact_1", "my exam is on Monday")
        "yaad rakh ki meeting 3 baje hai" → ("custom_fact_2", "meeting 3 baje hai")
        "forget that my exam is on Monday" → returns ("__forget__", "my exam is on Monday")

    Returns:
        (key, value) tuple or None if no fact found.
        For "forget" commands: ("__forget__", fact_text) — caller should search
        existing facts for a match and delete. Never pass this straight to
        UserMemory.set() — see its guard against persisting this key.

    """
    t = transcript.strip()

    # Check structured patterns first
    for compiled_pattern, key in _FACT_PATTERNS:
        m = compiled_pattern.search(t)
        if m:
            # Special handling for code-mixing preference patterns
            if key == "code_mixing_english":
                return "code_mixing", "english"
            if key == "code_mixing_hinglish":
                return "code_mixing", "hinglish"

            value = m.group(1).strip().rstrip(".,!?")
            if 1 < len(value) < 150:
                return key, value

    # Check "forget" commands (before "remember" — "forget that X" is more specific)
    fm = _FORGET_RE.search(t)
    if fm:
        fact_text = fm.group(1).strip().rstrip(".,!?")
        if 2 < len(fact_text) < 300:
            return "__forget__", fact_text

    # Check "remember" / "yaad rakh" commands (generic fact storage)
    rm = _REMEMBER_RE.search(t)
    if rm:
        fact_text = rm.group(1).strip().rstrip(".,!?")
        if 2 < len(fact_text) < 300:
            return _next_custom_fact_key(), fact_text

    return None
