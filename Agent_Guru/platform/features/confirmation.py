"""Verbal confirmation for destructive OS actions.

Before executing destructive actions (delete, shutdown, uninstall, etc.),
speaks a confirmation prompt and listens for the user's response.

Design:
    - Checks the RESOLVED intent action name, not raw transcript text.
      This means "don't shutdown the laptop" won't trigger false confirmation
      (because the intent resolver won't classify it as a shutdown action).
    - Speaks: "{description}, pakka?" (Hinglish) or "are you sure?" (English)
    - Listens for 5s via STT
    - Confirm: "haan", "yes", "do it", "pakka", "kar do"
    - Deny: "nahi", "no", "cancel", "ruk", "mat kar"
    - Timeout, TTS failure, or no callbacks wired → deny (safe default)

Performance:
    - DESTRUCTIVE_ACTIONS membership check: O(1) via frozenset
    - Confirmation flow adds ~3-5s latency (TTS + listening) — acceptable
      for destructive actions where caution is the priority

Integration:
    orchestrator.py's destructive-action gate calls
    get_confirmation_manager() (a process-wide singleton, same pattern as
    get_user_memory() / get_reaction_rules() / get_speaker_verifier()
    elsewhere in this codebase) and checks .is_wired before calling
    .request_confirmation(). Call .wire(tts_fn=..., stt_fn=...) once during
    startup with real speak/listen callbacks — until that happens, is_wired
    stays False and the gate denies destructive actions rather than
    guessing. Note: this codebase doesn't yet have a generic "listen for N
    seconds on demand" capture function outside of wake-word-triggered STT —
    stt_fn needs that built before wire() can be called with something real.

Fixed (this revision):
    - _parse_confirmation used plain substring containment (`word in text`)
      for short fragments like "ok"/"no", which false-positives on ordinary
      words containing those letters (e.g. "smoke" contains "ok" — a false
      CONFIRM on a destructive action). Switched to regex word-boundary
      matching.
    - Bare "na" was in the deny-word set. In natural Hindi, "na" is a very
      common sentence-final filler/tag ("haan na" = "yeah, right?" — usually
      affirmative), not a denial. Since deny-words were checked first, "haan
      na, kar do" would misparse as DENY before "kar do" was ever considered.
      Removed bare "na"; kept the unambiguous "nahi"/"nai".
    - TTS failure used to log and "continue anyway" into the listening
      phase — meaning the user's next words (in response to a question they
      never actually heard) got fed into the confirm/deny parser. Now fails
      closed (denies) immediately if the prompt couldn't be spoken.
    - Added get_confirmation_manager() / is_wired / wire() — previously
      absent, which meant orchestrator.py's destructive-action gate had no
      way to reach a live instance and always fell back to its safe-deny
      path by construction, not by design.
    - Confirm/deny vocabulary deliberately NOT extended to Tamil/Telugu/
      Kannada/Urdu — unlike casual chat phrasing, a misjudged yes/no here
      gates a destructive action. Kept scoped to well-verified Hindi/English
      rather than guessing at unverified vocabulary for a safety-critical
      parse.

Author: Agent Guru Team
Date: 2026-07-07
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Destructive actions — checked against the resolved intent action field
# ---------------------------------------------------------------------------

DESTRUCTIVE_ACTIONS = frozenset({
    "delete_file",
    "delete_folder",
    "delete",
    "remove",
    "shutdown",
    "restart",
    "reboot",
    "uninstall",
    "format",
    "wipe",
    "empty_trash",
    "force_quit",
})

# Words/phrases that confirm the action.
# Scoped to Hindi + English only (see module docstring "Fixed" note) — this
# is the yes/no vocabulary that gates a DESTRUCTIVE action, so it stays
# narrow and well-verified rather than covering every language this product
# otherwise supports for casual chat.
_CONFIRM_WORDS = frozenset({
    "haan", "han", "haa", "yes", "yeah", "yep", "yup",
    "do it", "kar do", "kardo", "karo", "kar de",
    "pakka", "sure", "confirm", "okay", "ok",
    "go ahead", "proceed",
})

# Words/phrases that deny/cancel the action.
# NOTE: bare "na" intentionally excluded — see module docstring "Fixed" note.
_DENY_WORDS = frozenset({
    "nahi", "nai", "naa", "no", "nope", "nah",
    "cancel", "ruk", "ruko", "mat kar", "mat karo",
    "stop", "don't", "abort", "never mind",
})

# Human-readable descriptions for common destructive actions
_ACTION_DESCRIPTIONS: dict[str, str] = {
    "delete_file": "delete this file",
    "delete_folder": "delete this folder",
    "delete": "delete this",
    "remove": "remove this",
    "shutdown": "shut down the computer",
    "restart": "restart the computer",
    "reboot": "restart the computer",
    "uninstall": "uninstall this",
    "format": "format this",
    "wipe": "wipe this",
    "empty_trash": "empty the trash",
    "force_quit": "force quit this app",
}


def is_destructive_action(action: str) -> bool:
    """Check if an action name is destructive. O(1) frozenset lookup."""
    return action.lower() in DESTRUCTIVE_ACTIONS


def _matches_any(normalized_text: str, terms: frozenset[str]) -> bool:
    """Whole-word/whole-phrase match, not substring containment.

    FIX: the previous implementation used `word in normalized_text`, which
    matches short fragments like "ok" or "no" *inside* unrelated words —
    e.g. "smoke" contains "ok", "known" contains "no". For a destructive-
    action yes/no gate, a false-positive CONFIRM from an unrelated word is
    a real safety problem, not a cosmetic one. `\\b...\\b` requires the term
    to be its own word (or, for multi-word phrases like "do it", to appear
    as that exact word sequence), so it won't fire on substrings of other
    words.
    """
    for term in terms:
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, normalized_text):
            return True
    return False


def _parse_confirmation(text: str) -> bool | None:
    """Parse a confirmation response from STT output.

    Returns:
        True if confirmed, False if denied, None if ambiguous/unrecognized.
    """
    if not text:
        return None

    normalized = text.lower().strip()

    # Check deny words first (safety — deny takes priority over confirm
    # in case of ambiguous responses like "no, do it")
    if _matches_any(normalized, _DENY_WORDS):
        return False

    if _matches_any(normalized, _CONFIRM_WORDS):
        return True

    return None


class ConfirmationManager:
    """Manages verbal confirmation for destructive OS actions.

    Usage (direct construction, e.g. in a test or a standalone script)::

        mgr = ConfirmationManager(tts_fn=speak, stt_fn=listen)

        if is_destructive_action(action):
            confirmed = await mgr.request_confirmation(
                action="delete_file",
                param="important.txt",
                code_mixing="hinglish",
            )
            if confirmed:
                # proceed with deletion
                ...
            else:
                # action cancelled
                ...

    Usage (shared singleton, e.g. from orchestrator.py)::

        mgr = get_confirmation_manager()
        mgr.wire(tts_fn=..., stt_fn=...)   # once, at startup
        # later, per destructive action:
        if mgr.is_wired:
            confirmed = await mgr.request_confirmation(action=action)
    """

    def __init__(
        self,
        tts_fn: Any = None,
        stt_fn: Any = None,
        listen_timeout_s: float = 5.0,
    ) -> None:
        """Initialize the confirmation manager.

        Args:
            tts_fn: Async or sync function that speaks text. Signature: fn(text: str).
            stt_fn: Async or sync function that listens and returns text.
                    Signature: fn(timeout_s: float) -> str.
            listen_timeout_s: How long to listen for confirmation (seconds).
        """
        self._tts_fn = tts_fn
        self._stt_fn = stt_fn
        self._timeout_s = listen_timeout_s

    @property
    def is_wired(self) -> bool:
        """True once real speak/listen callbacks have been injected.

        Checked by orchestrator.py's destructive-action gate before it ever
        calls request_confirmation(). An unwired manager (the default state
        until wire() is called with real callbacks) means "fail safe: deny
        the action," not "try anyway with nothing to speak or listen with."
        """
        return self._tts_fn is not None and self._stt_fn is not None

    def wire(
        self,
        tts_fn: Any,
        stt_fn: Any,
        listen_timeout_s: float | None = None,
    ) -> None:
        """Inject real TTS/STT callbacks after construction.

        Intended to be called once, during startup, before any pipeline
        activity begins — e.g.:

            get_confirmation_manager().wire(
                tts_fn=my_speak_only_fn,
                stt_fn=my_listen_for_n_seconds_fn,
            )

        Until this is called, is_wired stays False and the destructive-
        action gate denies rather than guessing.

        Args:
            tts_fn: Same contract as the constructor's tts_fn.
            stt_fn: Same contract as the constructor's stt_fn.
            listen_timeout_s: Optionally override the listen timeout.
        """
        self._tts_fn = tts_fn
        self._stt_fn = stt_fn
        if listen_timeout_s is not None:
            self._timeout_s = listen_timeout_s

    async def request_confirmation(
        self,
        action: str,
        param: str = "",
        code_mixing: str = "hinglish",
    ) -> bool:
        """Request verbal confirmation for a destructive action.

        Speaks a confirmation prompt, listens for response, returns True/False.
        Times out to False (deny) after listen_timeout_s. Also denies
        immediately (without listening) if the prompt itself couldn't be
        spoken — see the module docstring's "Fixed" note.

        Args:
            action: The resolved intent action name (e.g. "delete_file").
                    Pass this UNMODIFIED — don't pre-humanize it (e.g. don't
                    replace underscores with spaces) before calling, or the
                    _ACTION_DESCRIPTIONS lookup below will miss and you'll
                    get a less natural prompt.
            param: The action parameter (e.g. filename, app name).
            code_mixing: "hinglish" or "english" — affects prompt language.

        Returns:
            True if user confirmed, False if denied, timed out, or if the
            confirmation flow couldn't run (no callbacks wired, TTS failed).
        """
        # Build the confirmation prompt
        description = _ACTION_DESCRIPTIONS.get(action.lower(), action)
        if param:
            description = f"{description} ({param})"

        if code_mixing == "hinglish":
            prompt = f"{description}, pakka?"
        else:
            prompt = f"{description} — are you sure?"

        logger.info("Confirmation requested: %r", prompt)

        # ── Speak the prompt ────────────────────────────────────────────
        # FIX: previously, a TTS failure logged and fell through to the
        # listening phase anyway — meaning the user's next words (in
        # response to a question they never actually heard) got parsed as
        # confirm/deny. Now this fails closed immediately instead.
        if self._tts_fn is None:
            logger.warning(
                "Confirmation: no TTS function available — can't ask the "
                "question, so denying rather than listening blindly",
            )
            return False

        try:
            if asyncio.iscoroutinefunction(self._tts_fn):
                await self._tts_fn(prompt)
            else:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._tts_fn, prompt)
        except Exception:
            logger.exception(
                "Confirmation TTS failed — the user never heard the prompt, "
                "so denying rather than listening for a response to a "
                "question that was never actually asked",
            )
            return False

        # ── Listen for response ─────────────────────────────────────────
        if self._stt_fn is None:
            logger.warning("Confirmation: no STT function available → deny")
            return False

        try:
            if asyncio.iscoroutinefunction(self._stt_fn):
                response_text = await asyncio.wait_for(
                    self._stt_fn(self._timeout_s),
                    timeout=self._timeout_s + 2.0,  # extra grace period
                )
            else:
                loop = asyncio.get_running_loop()
                response_text = await asyncio.wait_for(
                    loop.run_in_executor(None, self._stt_fn, self._timeout_s),
                    timeout=self._timeout_s + 2.0,
                )

            if response_text:
                result = _parse_confirmation(response_text)
                if result is True:
                    logger.info("Confirmation: CONFIRMED (%r)", response_text)
                    return True
                elif result is False:
                    logger.info("Confirmation: DENIED (%r)", response_text)
                    return False
                else:
                    logger.info("Confirmation: AMBIGUOUS (%r) → deny", response_text)
                    return False

            logger.info("Confirmation: empty response → deny (safe default)")
            return False

        except TimeoutError:
            logger.info("Confirmation: TIMEOUT → deny (safe default)")
            return False
        except Exception:
            logger.exception("Confirmation listen failed → deny (safe default)")
            return False


# ---------------------------------------------------------------------------
# Process-wide singleton — same get_X() pattern as get_user_memory(),
# get_reaction_rules(), get_speaker_verifier() elsewhere in this codebase.
# ---------------------------------------------------------------------------

_default_manager: ConfirmationManager | None = None


def get_confirmation_manager() -> ConfirmationManager:
    """Return the process-wide ConfirmationManager singleton.

    Returned unwired (is_wired=False, since no callbacks are known at import
    time) until something calls .wire(tts_fn=..., stt_fn=...) — typically
    once, during orchestrator startup. orchestrator.py's destructive-action
    gate checks .is_wired before calling .request_confirmation(), so an
    un-wired manager correctly results in "deny," not an error.
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = ConfirmationManager()
    return _default_manager
