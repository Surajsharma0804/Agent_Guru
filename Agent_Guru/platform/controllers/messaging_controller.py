"""Multi-platform messaging controller for Agent Guru.

Provides async message sending across WhatsApp, Telegram, Slack, SMS, and Email
on all platforms: Windows, macOS, Linux, Android, and iOS.

Platform support:
    - Desktop (windows/macos/linux/unknown):
        WhatsApp Web via browser, Telegram Desktop, Slack via pyautogui
        SMS: not supported (returns False with guidance)
        Email: mailto: URL scheme via webbrowser
    - Android:
        adb shell am start with intent + adb input text
    - iOS:
        xcrun simctl openurl with URL scheme

Design Decisions:
    - All public methods are async (asyncio.create_subprocess_exec for I/O)
    - Returns True/False or list - never raises for normal failures
    - Works on ALL platforms - no RuntimeError for wrong platform
    - Fuzzy contact name matching (case-insensitive, partial) against a
      local, on-device contacts store (see "Contact resolution" below)
    - Message sanitization: strip null bytes, truncate to 2000 chars
    - Graceful fallback when tools (adb, xcrun, pyautogui) unavailable

Contact resolution (added 2026-09-13):
    search_contact() used to be a permanent stub that always returned an
    empty list, and send_message() passed whatever the caller gave it
    (e.g. "Rahul") straight through to the per-app URL builders. For
    WhatsApp and email specifically that was worse than just "not
    finding" the contact: a non-phone-number contact fell through to
    ``https://web.whatsapp.com/send?text=...`` with no ``phone=``
    parameter, which opens WhatsApp Web's generic compose screen with
    NO recipient selected - the message reaches nobody - yet the method
    still returned True, so a caller (including the agent's own action
    layer) had no way to know the send didn't actually go anywhere.

    This module now keeps a small local JSON address book (see
    _resolve_contacts_path(), next to memory_manager.py's memory.db, in
    the same OS-standard per-user data directory) that callers populate
    via add_contact()/remove_contact()/list_contacts(). send_message()
    resolves its `contact` argument through resolve_contact() before
    dispatching:
      - A value that already looks like a real identifier for the app
        (a phone number for whatsapp/sms, an email address for email, an
        @handle for telegram) is used as-is - unchanged from before.
      - Otherwise it is fuzzy-matched (case-insensitive substring, then
        difflib close-match) against saved contact names for that app.
      - For whatsapp/sms/email, if nothing resolves, send_message() now
        returns False with a clear log message instead of silently
        "succeeding" at reaching nobody. For telegram/slack, a bare word
        can legitimately BE the identifier itself (a Telegram username
        needs no "@"; Slack's URL scheme does not address a specific
        contact at all - see _send_desktop_slack), so those still fall
        back to using the raw value, matching the prior behavior.

Performance Characteristics:
    - Time Complexity: O(n) for fuzzy matching where n = number of known contacts
    - Space Complexity: O(1) per operation
    - Latency: <5 seconds for message send (target)

Author: Agent Guru Team
Date: 2026-03-20
"""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import re
import urllib.parse
from pathlib import Path

from Agent_Guru.platform.platform_detector import PlatformDetector
from Agent_Guru.platform.utils import normalize as _normalize

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_MESSAGE_LENGTH: int = 2_000

# Supported app names (canonical lowercase)
_SUPPORTED_APPS: frozenset[str] = frozenset({"whatsapp", "telegram", "slack", "sms", "email"})

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _looks_like_phone(value: str) -> bool:
    """Heuristic: True if *value* is already a phone number, not a display name."""
    digits_only = re.sub(r"[+\-()\s]", "", value.strip())
    return digits_only.isdigit() and len(digits_only) >= 7


def _looks_like_email(value: str) -> bool:
    """Heuristic: True if *value* is already a well-formed email address."""
    return bool(_EMAIL_RE.match(value.strip()))


def _looks_like_handle(value: str) -> bool:
    """True if *value* already looks like an @username / platform handle."""
    return value.strip().startswith("@") and len(value.strip()) > 1


# ---------------------------------------------------------------------------
# Local contacts store (JSON, on-device, no cloud sync)
# ---------------------------------------------------------------------------


def _resolve_contacts_path() -> Path:
    """Return the OS-appropriate path for the local contacts store.

    Mirrors memory/memory_manager.py's ``_resolve_db_path()`` so all of
    Agent Guru's local per-user state lives under the same
    platform-standard directory: ``%LOCALAPPDATA%\\agent_guru`` on
    Windows, ``$XDG_DATA_HOME/agent_guru`` (or ``~/.local/share/agent_guru``)
    on Linux/macOS.
    """
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:  # Linux / macOS
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    data_dir = base / "agent_guru"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "contacts.json"


def _load_contacts(path: Path) -> dict[str, dict[str, str]]:
    """Load the contacts store, keyed by lowercase contact name.

    Never raises - a missing or corrupt file is treated as an empty
    address book (with a logged warning for the corrupt case) rather
    than crashing whatever asked to send a message.
    """
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return {
            str(name).lower(): {str(k): str(v) for k, v in identifiers.items()}
            for name, identifiers in data.items()
            if isinstance(identifiers, dict)
        }
    except (OSError, ValueError) as exc:
        logger.warning(
            "Contacts store at %s is unreadable/corrupt (%s) - treating as empty",
            path, exc,
        )
        return {}


def _save_contacts(path: Path, contacts: dict[str, dict[str, str]]) -> bool:
    """Write the contacts store atomically (write-temp-then-rename)."""
    try:
        tmp_path = path.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(contacts, f, indent=2, sort_keys=True)
        tmp_path.replace(path)  # atomic on POSIX and Windows (NTFS)
        return True
    except OSError as exc:
        logger.warning("Failed to save contacts store at %s: %s", path, exc)
        return False


def _fuzzy_match_names(query: str, candidate_names: list[str]) -> list[str]:
    """Case-insensitive substring match, falling back to close-match fuzzy
    search (via difflib) when nothing contains the query as a substring.

    O(n) in the number of saved contacts - fine for a personal address
    book (tens to low hundreds of entries), not intended for a directory
    of thousands.
    """
    query_norm = query.strip().lower()
    if not query_norm:
        return []

    substring_hits = [n for n in candidate_names if query_norm in n]
    if substring_hits:
        return substring_hits

    return difflib.get_close_matches(query_norm, candidate_names, n=5, cutoff=0.6)

# ---------------------------------------------------------------------------
# Platform detection (mirrors mobile_app_controller.py)
# ---------------------------------------------------------------------------


def _detect_platform() -> str:
    """Thin wrapper - delegates to canonical PlatformDetector."""
    return PlatformDetector.detect().os_name.lower()


def _is_desktop(plat: str) -> bool:
    """Return True if *plat* is a desktop platform."""
    return plat in ("windows", "macos", "linux", "unknown")


def _is_mobile(plat: str) -> bool:
    """Return True if *plat* is a mobile platform."""
    return plat in ("android", "ios")


# ---------------------------------------------------------------------------
# Message sanitization
# ---------------------------------------------------------------------------


def _sanitize_message(message: str) -> str:
    """Strip null bytes and truncate to _MAX_MESSAGE_LENGTH.

    Args:
        message: Raw message text.

    Returns:
        Sanitized message safe for sending.

    """
    message = message.replace("\x00", "")
    if len(message) > _MAX_MESSAGE_LENGTH:
        logger.warning(
            "Message truncated from %d to %d characters",
            len(message),
            _MAX_MESSAGE_LENGTH,
        )
        message = message[:_MAX_MESSAGE_LENGTH]
    return message


# ---------------------------------------------------------------------------
# MessagingController
# ---------------------------------------------------------------------------


class MessagingController:
    """Async controller for multi-platform messaging.

    Works on ALL platforms (windows, macos, linux, android, ios, unknown).
    Never raises RuntimeError for wrong platform - returns False instead.

    Example::

        controller = MessagingController()
        await controller.initialize()

        sent = await controller.send_message("whatsapp", "+1234567890", "Hello!")
        contacts = await controller.search_contact("whatsapp", "John")

        await controller.shutdown()

    All action methods return ``True``/``False`` or ``list``.
    They never raise exceptions for normal operational failures.

    Desktop implementation:
        - WhatsApp: opens https://web.whatsapp.com via webbrowser + pyautogui automation
        - Telegram: opens Telegram Desktop via subprocess + pyautogui automation
        - Slack: opens Slack app via subprocess + pyautogui automation
        - SMS: not supported on desktop (returns False with log message)
        - Email: opens default mail client via mailto: URL scheme

    Android implementation:
        Uses ``adb shell am start`` with platform-specific intents.
        Falls back gracefully if adb is unavailable.

    iOS implementation:
        Uses ``xcrun simctl openurl booted <url-scheme>`` for simulator targets.
        Falls back gracefully if xcrun is unavailable.
    """

    def __init__(
        self,
        platform_override: str | None = None,
        contacts_path_override: str | Path | None = None,
    ) -> None:
        """Create the controller.

        Args:
            platform_override: Force a specific platform string (for testing).
                When ``None`` the platform is auto-detected.
            contacts_path_override: Use this path for the local contacts
                store instead of the OS-standard location (for testing -
                keeps tests from touching the real user's address book).

        """
        self._platform: str = platform_override or _detect_platform()
        self._initialized: bool = False
        self._contacts_path: Path = (
            Path(contacts_path_override) if contacts_path_override else _resolve_contacts_path()
        )

        logger.info("MessagingController created - platform=%s", self._platform)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the controller.

        Idempotent - safe to call multiple times.
        """
        if self._initialized:
            logger.debug("MessagingController already initialized")
            return

        self._initialized = True
        logger.info("MessagingController initialized - platform=%s", self._platform)

    async def shutdown(self) -> None:
        """Shut down the controller and release resources."""
        self._initialized = False
        logger.info("MessagingController shut down")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_message(self, app: str, contact: str, message: str) -> bool:
        """Send a message to a contact via the specified messaging app.

        Sanitizes the message (strips null bytes, truncates to 2000 chars)
        before sending.  Resolves the contact via fuzzy matching where
        applicable.

        Args:
            app: Messaging app name - one of ``"whatsapp"``, ``"telegram"``,
                ``"slack"``, ``"sms"``, ``"email"``.
            contact: Contact name, phone number, username, or email address.
            message: Message text to send.

        Returns:
            ``True`` if the send command succeeded, ``False`` otherwise.

        """
        app_norm = _normalize(app)
        if not app_norm:
            logger.warning("send_message called with empty app")
            return False

        if not contact or not contact.strip():
            logger.warning("send_message called with empty contact")
            return False

        if not message or not message.strip():
            logger.warning("send_message called with empty message")
            return False

        if app_norm not in _SUPPORTED_APPS:
            logger.warning(
                "send_message: unsupported app %r (supported: %s)",
                app,
                ", ".join(sorted(_SUPPORTED_APPS)),
            )
            return False

        message = _sanitize_message(message)
        if not message:
            logger.warning("send_message: message is empty after sanitization")
            return False

        resolved_contact = await self.resolve_contact(app_norm, contact)
        if resolved_contact is None:
            logger.warning(
                "send_message: could not resolve %r to a working %s contact - "
                "no matching saved contact (or the match was ambiguous), and "
                "the value isn't a phone number/email Agent Guru can send to "
                "directly. Save it first with add_contact(%r, %s='...'), or "
                "say the phone number/email directly.",
                contact, app_norm, contact, app_norm,
            )
            return False
        contact = resolved_contact

        logger.info(
            "send_message: app=%r contact=%r len(message)=%d platform=%s",
            app_norm,
            contact,
            len(message),
            self._platform,
        )

        try:
            if _is_mobile(self._platform):
                if self._platform == "android":
                    return await self._send_android(app_norm, contact, message)
                # ios
                return await self._send_ios(app_norm, contact, message)
            return await self._send_desktop(app_norm, contact, message)
        except Exception:
            logger.exception("send_message(%r, %r) failed", app_norm, contact)
            return False

    async def search_contact(self, app: str, query: str) -> list[str]:
        """Search for contacts matching *query* in the specified app.

        Fuzzy-matches (case-insensitive substring, then difflib close
        match) against names in the local contacts store that have a
        saved identifier for *app* - see add_contact(). Returns an
        empty list when no contacts are saved yet, none match, or
        *app*/*query* is empty; never raises.

        Args:
            app: Messaging app name.
            query: Search string (fuzzy matched against known contacts).

        Returns:
            List of matching contact display-name strings (may be empty).

        """
        app_norm = _normalize(app)
        if not app_norm or not query or not query.strip():
            return []

        logger.info(
            "search_contact: app=%r query=%r platform=%s",
            app_norm,
            query,
            self._platform,
        )

        try:
            loop = asyncio.get_running_loop()
            contacts = await loop.run_in_executor(None, _load_contacts, self._contacts_path)
            if not contacts:
                return []
            matches = _fuzzy_match_names(query, list(contacts.keys()))
            return [
                contacts[key].get("_display_name", key)
                for key in matches
                if app_norm in contacts[key] and contacts[key][app_norm]
            ]
        except Exception:
            logger.exception("search_contact(%r, %r) failed", app_norm, query)
            return []

    async def resolve_contact(self, app: str, name_or_identifier: str) -> str | None:
        """Resolve a spoken/typed contact reference to a concrete send-target.

        If *name_or_identifier* already looks like a raw identifier for
        *app* (a phone number for whatsapp/sms, an email address for
        email, an @handle for telegram) it is returned unchanged - this
        preserves send_message()'s original behavior of accepting raw
        identifiers directly.

        Otherwise it is looked up by fuzzy, case-insensitive name against
        the local contacts store (see add_contact()). Ambiguous matches
        (more than one saved contact fits) resolve to None rather than
        guessing.

        When there is still no match: for telegram and slack, the raw
        value is used as-is, because a bare word can legitimately BE the
        identifier itself (a Telegram username needs no "@"; Slack's URL
        scheme does not address a specific contact at all - see
        _send_desktop_slack) - this matches this module's pre-existing
        behavior for those two apps. For whatsapp/sms/email, a
        non-phone/non-email string was never a working identifier (wa.me
        and mailto: both need the real thing), so this returns None
        instead of building a URL that silently reaches nobody - see the
        "Contact resolution" note in this module's docstring.

        Args:
            app: Messaging app name.
            name_or_identifier: What the caller has - a saved contact's
                display name, or a raw phone number/email/handle.

        Returns:
            A concrete identifier to send to, or None if it cannot be
            resolved.

        """
        app_norm = _normalize(app)
        value = (name_or_identifier or "").strip()
        if not value:
            return None

        if app_norm in ("whatsapp", "sms") and _looks_like_phone(value):
            return value
        if app_norm == "email" and _looks_like_email(value):
            return value
        if app_norm == "telegram" and _looks_like_handle(value):
            return value

        loop = asyncio.get_running_loop()
        contacts = await loop.run_in_executor(None, _load_contacts, self._contacts_path)
        if contacts:
            matches = _fuzzy_match_names(value, list(contacts.keys()))
            resolved = list(
                dict.fromkeys(
                    contacts[key][app_norm]
                    for key in matches
                    if app_norm in contacts[key] and contacts[key][app_norm]
                ),
            )
            if len(resolved) == 1:
                return resolved[0]
            if len(resolved) > 1:
                logger.warning(
                    "resolve_contact: %r matched multiple saved contacts for "
                    "app=%s (%s) - ambiguous, refusing to guess",
                    value, app_norm, ", ".join(resolved),
                )
                return None

        if app_norm in ("telegram", "slack"):
            return value
        return None

    async def add_contact(self, name: str, **identifiers: str) -> bool:
        """Add or update a contact in the local address book.

        Args:
            name: Display name to look the contact up by later, e.g.
                ``add_contact("Rahul", whatsapp="+919876543210",
                telegram="@rahul123")``.
            **identifiers: app-name -> identifier pairs. Keys are
                normally one of "whatsapp", "telegram", "slack", "sms",
                "email", but any key is stored (forward-compatible) -
                only recognized app keys are used by resolve_contact().

        Returns:
            True if the contact was saved.

        """
        name = (name or "").strip()
        if not name:
            logger.warning("add_contact called with empty name")
            return False
        clean_identifiers = {k: str(v).strip() for k, v in identifiers.items() if str(v).strip()}
        if not clean_identifiers:
            logger.warning("add_contact(%r) called with no non-empty identifiers", name)
            return False

        loop = asyncio.get_running_loop()
        contacts = await loop.run_in_executor(None, _load_contacts, self._contacts_path)
        key = name.lower()
        entry = contacts.get(key, {})
        entry.update(clean_identifiers)
        entry["_display_name"] = name
        contacts[key] = entry

        ok = await loop.run_in_executor(None, _save_contacts, self._contacts_path, contacts)
        if ok:
            logger.info("Contact %r saved (%s)", name, ", ".join(sorted(clean_identifiers)))
        return ok

    async def remove_contact(self, name: str) -> bool:
        """Remove a contact from the local address book.

        Returns:
            True if a contact with this name existed and was removed.

        """
        key = (name or "").strip().lower()
        if not key:
            return False
        loop = asyncio.get_running_loop()
        contacts = await loop.run_in_executor(None, _load_contacts, self._contacts_path)
        if key not in contacts:
            return False
        del contacts[key]
        return await loop.run_in_executor(None, _save_contacts, self._contacts_path, contacts)

    async def list_contacts(self) -> dict[str, dict[str, str]]:
        """Return every saved contact as ``{display_name: {app: identifier}}``."""
        loop = asyncio.get_running_loop()
        contacts = await loop.run_in_executor(None, _load_contacts, self._contacts_path)
        return {
            entry.get("_display_name", name): {k: v for k, v in entry.items() if k != "_display_name"}
            for name, entry in contacts.items()
        }

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def platform(self) -> str:
        """Current platform identifier."""
        return self._platform

    @property
    def is_initialized(self) -> bool:
        """Whether the controller has been initialized."""
        return self._initialized

    # ------------------------------------------------------------------
    # Desktop implementations
    # ------------------------------------------------------------------

    async def _send_desktop(self, app: str, contact: str, message: str) -> bool:
        """Dispatch to the correct desktop send implementation."""
        if app == "whatsapp":
            return await self._send_desktop_whatsapp(contact, message)
        if app == "telegram":
            return await self._send_desktop_telegram(contact, message)
        if app == "slack":
            return await self._send_desktop_slack(contact, message)
        if app == "sms":
            logger.warning(
                "SMS is not supported on desktop platform '%s'. "
                "Use a mobile device or a third-party SMS gateway.",
                self._platform,
            )
            return False
        if app == "email":
            return await self._send_desktop_email(contact, message)
        logger.warning("send_desktop: unknown app %r", app)
        return False

    async def _send_desktop_whatsapp(self, contact: str, message: str) -> bool:
        """Open WhatsApp Web in the default browser with pre-filled message.

        Uses the wa.me URL scheme when contact looks like a phone number,
        otherwise opens web.whatsapp.com.
        """
        try:
            import asyncio

            encoded = urllib.parse.quote(message)

            # Detect phone number (digits, +, -, spaces)
            digits_only = contact.replace("+", "").replace("-", "").replace(" ", "")
            if digits_only.isdigit():
                url = f"https://wa.me/{digits_only}?text={encoded}"
            else:
                url = f"https://web.whatsapp.com/send?text={encoded}"

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._blocking_open_url, url)
            logger.info("WhatsApp Web opened: %s", url)
            return True
        except Exception:
            logger.exception("_send_desktop_whatsapp failed")
            return False

    async def _send_desktop_telegram(self, contact: str, message: str) -> bool:
        """Open Telegram with a pre-filled message via URL scheme."""
        try:
            import asyncio

            encoded = urllib.parse.quote(message)

            # Strip leading @ if present
            username = contact.lstrip("@")
            url = f"https://t.me/{username}?text={encoded}"

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._blocking_open_url, url)
            logger.info("Telegram opened: %s", url)
            return True
        except Exception:
            logger.exception("_send_desktop_telegram failed")
            return False

    async def _send_desktop_slack(self, contact: str, message: str) -> bool:
        """Open Slack via URL scheme (best-effort)."""
        try:
            loop = asyncio.get_running_loop()
            # Slack deep-link: slack://open (no direct message pre-fill in URL scheme)
            url = "slack://open"
            await loop.run_in_executor(None, self._blocking_open_url, url)
            logger.info(
                "Slack opened via URL scheme (manual navigation to %r required)",
                contact,
            )
            return True
        except Exception:
            logger.exception("_send_desktop_slack failed")
            return False

    async def _send_desktop_email(self, contact: str, message: str) -> bool:
        """Open the default mail client via mailto: URL scheme."""
        try:
            loop = asyncio.get_running_loop()
            encoded_body = urllib.parse.quote(message)
            url = f"mailto:{contact}?body={encoded_body}"
            await loop.run_in_executor(None, self._blocking_open_url, url)
            logger.info("Email client opened: mailto:%s", contact)
            return True
        except Exception:
            logger.exception("_send_desktop_email failed")
            return False

    def _blocking_open_url(self, url: str) -> None:
        """Open *url* in the default browser/handler - blocking, run in executor."""
        import webbrowser

        webbrowser.open(url)

    # ------------------------------------------------------------------
    # Android implementations
    # ------------------------------------------------------------------

    async def _send_android(self, app: str, contact: str, message: str) -> bool:
        """Dispatch to the correct Android send implementation."""
        if not await self._adb_available():
            logger.warning(
                "adb not available - cannot send %r message on Android. "
                "Ensure adb is installed and the device is connected.",
                app,
            )
            return False

        if app == "whatsapp":
            return await self._send_android_whatsapp(contact, message)
        if app == "telegram":
            return await self._send_android_telegram(contact, message)
        if app == "slack":
            return await self._send_android_slack(contact, message)
        if app == "sms":
            return await self._send_android_sms(contact, message)
        if app == "email":
            return await self._send_android_email(contact, message)
        logger.warning("send_android: unknown app %r", app)
        return False

    async def _send_android_whatsapp(self, contact: str, message: str) -> bool:
        """Send WhatsApp message on Android via adb intent."""
        encoded = urllib.parse.quote(message)
        digits_only = contact.replace("+", "").replace("-", "").replace(" ", "")
        phone = digits_only if digits_only.isdigit() else contact
        url = f"whatsapp://send?phone={phone}&text={encoded}"
        return await self._adb_start_intent(
            action="android.intent.action.VIEW",
            data=url,
        )

    async def _send_android_telegram(self, contact: str, message: str) -> bool:
        """Send Telegram message on Android via adb intent."""
        encoded = urllib.parse.quote(message)
        username = contact.lstrip("@")
        url = f"tg://resolve?domain={username}&text={encoded}"
        return await self._adb_start_intent(
            action="android.intent.action.VIEW",
            data=url,
        )

    async def _send_android_slack(self, contact: str, message: str) -> bool:
        """Open Slack on Android via adb intent."""
        return await self._adb_start_intent(
            action="android.intent.action.VIEW",
            data="slack://open",
            package="com.Slack",
        )

    async def _send_android_sms(self, contact: str, message: str) -> bool:
        """Send SMS on Android via adb intent."""
        digits_only = contact.replace("+", "").replace("-", "").replace(" ", "")
        phone = digits_only if digits_only.isdigit() else contact
        urllib.parse.quote(message)
        url = f"smsto:{phone}"
        return await self._adb_start_intent(
            action="android.intent.action.SENDTO",
            data=url,
            extras={"sms_body": message},
        )

    async def _send_android_email(self, contact: str, message: str) -> bool:
        """Send email on Android via adb intent."""
        return await self._adb_start_intent(
            action="android.intent.action.SENDTO",
            data=f"mailto:{contact}",
            extras={"subject": "", "body": message},
        )

    async def _adb_start_intent(
        self,
        action: str,
        data: str,
        package: str | None = None,
        extras: dict[str, str] | None = None,
    ) -> bool:
        """Run ``adb shell am start`` with the given intent parameters.

        Args:
            action: Android intent action string.
            data: Intent data URI.
            package: Optional package name to restrict intent.
            extras: Optional dict of string extras (--es key value).

        Returns:
            ``True`` if adb returned exit code 0, ``False`` otherwise.

        """
        cmd = ["adb", "shell", "am", "start", "-a", action, "-d", data]
        if package:
            cmd += ["-p", package]
        if extras:
            for key, value in extras.items():
                cmd += ["--es", key, value]

        try:
            proc = await asyncio.create_subprocess_exec(  # nosec B603 B607
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            success = proc.returncode == 0
            if success:
                logger.info("adb am start succeeded: action=%s data=%s", action, data)
            else:
                logger.warning(
                    "adb am start returned non-zero: action=%s data=%s rc=%s",
                    action,
                    data,
                    proc.returncode,
                )
            return success
        except Exception as exc:
            logger.debug("adb am start failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # iOS implementations
    # ------------------------------------------------------------------

    async def _send_ios(self, app: str, contact: str, message: str) -> bool:
        """Dispatch to the correct iOS send implementation."""
        if not await self._xcrun_available():
            logger.warning(
                "xcrun not available - cannot send %r message on iOS. "
                "Install Xcode to use xcrun simctl.",
                app,
            )
            return False

        if app == "whatsapp":
            return await self._send_ios_whatsapp(contact, message)
        if app == "telegram":
            return await self._send_ios_telegram(contact, message)
        if app == "slack":
            return await self._send_ios_slack(contact, message)
        if app == "sms":
            return await self._send_ios_sms(contact, message)
        if app == "email":
            return await self._send_ios_email(contact, message)
        logger.warning("send_ios: unknown app %r", app)
        return False

    async def _send_ios_whatsapp(self, contact: str, message: str) -> bool:
        """Send WhatsApp message on iOS via xcrun simctl openurl."""
        encoded = urllib.parse.quote(message)
        digits_only = contact.replace("+", "").replace("-", "").replace(" ", "")
        phone = digits_only if digits_only.isdigit() else contact
        url = f"whatsapp://send?phone={phone}&text={encoded}"
        return await self._xcrun_openurl(url)

    async def _send_ios_telegram(self, contact: str, message: str) -> bool:
        """Send Telegram message on iOS via xcrun simctl openurl."""
        encoded = urllib.parse.quote(message)
        username = contact.lstrip("@")
        url = f"tg://msg?to={username}&text={encoded}"
        return await self._xcrun_openurl(url)

    async def _send_ios_slack(self, contact: str, message: str) -> bool:
        """Open Slack on iOS via xcrun simctl openurl."""
        return await self._xcrun_openurl("slack://open")

    async def _send_ios_sms(self, contact: str, message: str) -> bool:
        """Send SMS on iOS via xcrun simctl openurl."""
        digits_only = contact.replace("+", "").replace("-", "").replace(" ", "")
        phone = digits_only if digits_only.isdigit() else contact
        encoded = urllib.parse.quote(message)
        url = f"sms:{phone}&body={encoded}"
        return await self._xcrun_openurl(url)

    async def _send_ios_email(self, contact: str, message: str) -> bool:
        """Send email on iOS via xcrun simctl openurl."""
        encoded = urllib.parse.quote(message)
        url = f"mailto:{contact}?body={encoded}"
        return await self._xcrun_openurl(url)

    async def _xcrun_openurl(self, url: str) -> bool:
        """Run ``xcrun simctl openurl booted <url>``.

        Args:
            url: URL scheme to open.

        Returns:
            ``True`` if xcrun returned exit code 0, ``False`` otherwise.

        """
        try:
            proc = await asyncio.create_subprocess_exec(  # nosec B603 B607
                "xcrun",
                "simctl",
                "openurl",
                "booted",
                url,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            success = proc.returncode == 0
            if success:
                logger.info("xcrun simctl openurl succeeded: %s", url)
            else:
                logger.warning(
                    "xcrun simctl openurl returned non-zero: url=%s rc=%s",
                    url,
                    proc.returncode,
                )
            return success
        except Exception as exc:
            logger.debug("xcrun simctl openurl failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Availability checks (cached per-instance)
    # ------------------------------------------------------------------

    _adb_cache: bool | None = None
    _xcrun_cache: bool | None = None

    async def _adb_available(self) -> bool:
        """Return True if adb is installed and reachable (cached)."""
        if MessagingController._adb_cache is not None:
            return MessagingController._adb_cache

        try:
            proc = await asyncio.create_subprocess_exec(  # nosec B603 B607
                "adb",
                "version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=3.0)
            result = proc.returncode == 0
        except Exception:
            result = False

        MessagingController._adb_cache = result
        return result

    async def _xcrun_available(self) -> bool:
        """Return True if xcrun is installed and reachable (cached)."""
        if MessagingController._xcrun_cache is not None:
            return MessagingController._xcrun_cache

        try:
            proc = await asyncio.create_subprocess_exec(  # nosec B603 B607
                "xcrun",
                "--version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=3.0)
            result = proc.returncode == 0
        except Exception:
            result = False

        MessagingController._xcrun_cache = result
        return result
