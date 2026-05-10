"""Multi-platform Intent Recognition System for Agent Guru.

Extracts structured intent from natural language text using:
- Primary: LLM (LLMManager) for accurate natural language understanding
- Fallback: Rule-based regex pattern matching when LLM unavailable

Intent Categories:
    - system_control: Open/close apps, volume, brightness, window management
    - information: Search, weather, news, facts, questions
    - communication: Send messages, make calls, email
    - file_ops: Create, delete, move, copy, rename files (desktop only)
    - conversation: Chat, jokes, general conversation

Platform Behaviour:
    - Desktop (windows/macos/linux/unknown): All intent types supported
    - Mobile (android/ios): communication-focused; file_ops mapped to conversation

Performance Requirements:
    - Intent recognition latency: <500ms (95th percentile)
    - Accuracy: >90% on standard command set
    - Confidence scoring: 0.0â€“1.0

Architecture:
    IntentRecognizer
    â”œâ”€â”€ LLMManager  â€” primary structured intent extraction
    â””â”€â”€ _RuleEngine â€” regex fallback when LLM unavailable

Author: Agent Guru Team
Date: 2026-03-20
"""

from __future__ import annotations

import json
import logging
import platform
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent types
# ---------------------------------------------------------------------------

INTENT_TYPES: list[str] = [
    "system_control",
    "information",
    "communication",
    "file_ops",
    "conversation",
]

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


def _detect_platform() -> str:
    """Return a normalised platform identifier.

    Returns:
        One of ``"windows"``, ``"macos"``, ``"linux"``, ``"android"``,
        ``"ios"``, or ``"unknown"``.

    """
    import os

    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    if system == "linux":
        if os.environ.get("ANDROID_ROOT") or os.environ.get("ANDROID_DATA"):
            return "android"
        return "linux"
    if system == "java":
        return "android"
    try:
        import objc_util  # type: ignore[import]  # noqa: F401

        return "ios"
    except ImportError:
        pass
    try:
        import Foundation  # type: ignore[import]  # noqa: F401

        return "ios"
    except ImportError:
        pass
    return "unknown"


def _is_desktop(plat: str) -> bool:
    """Return True for desktop platforms."""
    return plat in ("windows", "macos", "linux", "unknown")


def _is_mobile(plat: str) -> bool:
    """Return True for mobile platforms."""
    return plat in ("android", "ios")


# ---------------------------------------------------------------------------
# IntentResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class IntentResult:
    """Structured result from intent recognition.

    Attributes:
        intent_type: One of the five intent categories.
        parameters: Extracted parameters (e.g. ``{"app": "notepad"}``).
        confidence: Confidence score in [0.0, 1.0].
        raw_text: Original input text.
        platform: Platform the recognition ran on.
        method: ``"llm"`` or ``"rule_based"`` â€” which engine produced this.

    """

    intent_type: str
    parameters: dict[str, Any]
    confidence: float
    raw_text: str
    platform: str
    method: str = "rule_based"

    def __post_init__(self) -> None:
        if self.intent_type not in INTENT_TYPES:
            msg = f"Unknown intent_type '{self.intent_type}'. Must be one of: {INTENT_TYPES}"
            raise ValueError(
                msg,
            )
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"confidence must be in [0.0, 1.0], got {self.confidence}"
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Rule-based fallback engine
# ---------------------------------------------------------------------------

# Each entry: (pattern, intent_type, param_extractor_fn)
# param_extractor_fn receives the re.Match and returns a dict of parameters.

_SYSTEM_CONTROL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # App control — handles "open", "launch", "can you open", "I want to open", "open up"
    (re.compile(r"\b(open|launch|start|run|open up|fire up)\b.+", re.IGNORECASE), "open_app"),
    (re.compile(r"\b(close|quit|exit|kill|shut down|terminate)\b.+", re.IGNORECASE), "close_app"),
    (re.compile(r"\b(uninstall|remove app|delete app)\b.+", re.IGNORECASE), "uninstall_app"),
    # Volume — handles "louder", "quieter", "make it louder", "turn up", "turn down"
    (re.compile(r"\b(volume|sound)\b.*(up|down|mute|unmute|\d+)", re.IGNORECASE), "volume"),
    (re.compile(r"\b(mute|unmute|silence)\b", re.IGNORECASE), "volume"),
    (
        re.compile(r"\b(louder|turn up|increase volume|raise volume|volume up)\b", re.IGNORECASE),
        "volume",
    ),
    (
        re.compile(
            r"\b(quieter|softer|turn down|lower volume|decrease volume|volume down)\b",
            re.IGNORECASE,
        ),
        "volume",
    ),
    (re.compile(r"\b(make it louder|make it quieter|make it softer)\b", re.IGNORECASE), "volume"),
    # Brightness — handles "brighter", "dimmer", "make it brighter"
    (re.compile(r"\b(brightness)\b.*(up|down|\d+)", re.IGNORECASE), "brightness"),
    (re.compile(r"\b(brighter|increase brightness|brightness up)\b", re.IGNORECASE), "brightness"),
    (
        re.compile(r"\b(dimmer|dim|darker|decrease brightness|brightness down)\b", re.IGNORECASE),
        "brightness",
    ),
    (re.compile(r"\bset\s+brightness\s+to\s+\d+", re.IGNORECASE), "brightness"),
    # Power
    (
        re.compile(
            r"\b(shutdown|turn off|power off)\b.*\b(pc|computer|laptop|system)\b", re.IGNORECASE,
        ),
        "shutdown",
    ),
    (
        re.compile(r"\b(restart|reboot|reset)\b.*\b(pc|computer|laptop|system)\b", re.IGNORECASE),
        "restart",
    ),
    (re.compile(r"\b(sleep|hibernate)\b", re.IGNORECASE), "power"),
    # Window management
    (
        re.compile(r"\b(minimize|minimise|maximize|maximise|restore|fullscreen)\b", re.IGNORECASE),
        "window",
    ),
    # Screenshot — handles "take a screenshot", "snap a screenshot", "grab a screenshot"
    (
        re.compile(
            r"\b(screenshot|screen shot|capture screen|take screenshot|snap screenshot|grab screenshot)\b",
            re.IGNORECASE,
        ),
        "screenshot",
    ),
    (
        re.compile(
            r"\b(take a screenshot|take screenshot|snap a screenshot|grab a screenshot)\b",
            re.IGNORECASE,
        ),
        "screenshot",
    ),
    # App switching
    (re.compile(r"\b(switch to|switch app|alt.?tab|go to app)\b.+", re.IGNORECASE), "switch_app"),
    # Media controls
    (re.compile(r"\b(next track|skip track|next song|skip song)\b", re.IGNORECASE), "next_track"),
    (
        re.compile(
            r"\b(previous track|prev track|previous song|last song|go back)\b", re.IGNORECASE,
        ),
        "previous_track",
    ),
    (
        re.compile(r"\b(stop music|stop media|stop playing|stop song)\b", re.IGNORECASE),
        "stop_media",
    ),
    (
        re.compile(r"\b(play|resume)\b.*(music|song|media|video|audio|track)\b", re.IGNORECASE),
        "play_pause",
    ),
    (
        re.compile(r"\b(pause)\b.*(music|song|media|video|audio|track|playing)\b", re.IGNORECASE),
        "play_pause",
    ),
    # Text input / dictation
    (re.compile(r"\b(type|write|input)\b.+\b(in|into|on)\b.+", re.IGNORECASE), "type_text"),
    (re.compile(r"\b(type|write|input)\b\s+[\"']?.+[\"']?", re.IGNORECASE), "type_text"),
    # Settings
    (re.compile(r"\b(wifi|wi-fi|wireless)\b", re.IGNORECASE), "settings"),
    (re.compile(r"\b(bluetooth)\b", re.IGNORECASE), "settings"),
    (re.compile(r"\b(airplane mode|do not disturb|dnd)\b", re.IGNORECASE), "settings"),
    # Reminders and timers
    (
        re.compile(r"\b(remind me|set a reminder|reminder|don.t let me forget)\b", re.IGNORECASE),
        "reminder",
    ),
    (
        re.compile(r"\b(set a timer|timer for|countdown|in \d+ minutes? remind)\b", re.IGNORECASE),
        "reminder",
    ),
    # Voice dictation
    (re.compile(r"^(dictate|type this|write this|paste this)[:\s]", re.IGNORECASE), "dictate"),
    # Clipboard
    (
        re.compile(
            r"\b(clipboard|what.s in my clipboard|read my clipboard|summarize my clipboard|fix my clipboard|correct my clipboard)\b",
            re.IGNORECASE,
        ),
        "clipboard",
    ),
    # Screen reading
    (
        re.compile(
            r"\b(what.s on my screen|read my screen|what do you see|summarize my screen|what am i looking at|describe my screen)\b",
            re.IGNORECASE,
        ),
        "screen_read",
    ),
    # System status
    (
        re.compile(
            r"\b(cpu usage|processor usage|ram usage|memory usage|battery|battery level|disk space|storage space|ip address|system status|how much ram|how much memory|how much storage)\b",
            re.IGNORECASE,
        ),
        "system_status",
    ),
    # Morning briefing
    (
        re.compile(
            r"\b(good morning|morning briefing|daily briefing|brief me|start my day|what.s my day|today.s summary)\b",
            re.IGNORECASE,
        ),
        "briefing",
    ),
]

# Known desktop application names â€” these should NEVER be treated as websites.
# When "open X" matches one of these, it's an app launch, not a URL open.
_KNOWN_DESKTOP_APPS: frozenset[str] = frozenset(
    {
        # Windows built-ins
        "notepad",
        "notepad++",
        "wordpad",
        "paint",
        "calculator",
        "calc",
        "cmd",
        "command prompt",
        "powershell",
        "terminal",
        "task manager",
        "file explorer",
        "explorer",
        "control panel",
        "settings",
        "snipping tool",
        "snip",
        "magnifier",
        "narrator",
        "on-screen keyboard",
        "registry editor",
        "regedit",
        "device manager",
        "disk management",
        "event viewer",
        "services",
        "task scheduler",
        # Browsers (open as apps, not URLs)
        "chrome",
        "google chrome",
        "firefox",
        "mozilla firefox",
        "edge",
        "microsoft edge",
        "msedge",
        "opera",
        "brave",
        "safari",
        "internet explorer",
        "ie",
        # Office / productivity
        "word",
        "excel",
        "powerpoint",
        "outlook",
        "onenote",
        "access",
        "teams",
        "skype",
        "onedrive",
        "libreoffice",
        "openoffice",
        "writer",
        "impress",
        # Dev tools
        "vscode",
        "visual studio code",
        "visual studio",
        "vs code",
        "pycharm",
        "intellij",
        "eclipse",
        "netbeans",
        "android studio",
        "sublime text",
        "sublime",
        "atom",
        "vim",
        "emacs",
        "nano",
        "git",
        "github desktop",
        "sourcetree",
        "gitkraken",
        "postman",
        "insomnia",
        "docker",
        "virtualbox",
        "vmware",
        "wsl",
        "ubuntu",
        "kali",
        # Media
        "vlc",
        "media player",
        "windows media player",
        "itunes",
        "spotify",
        "audacity",
        "obs",
        "obs studio",
        "handbrake",
        "photoshop",
        "illustrator",
        "premiere",
        "after effects",
        "gimp",
        "inkscape",
        "blender",
        "figma",
        # Communication
        "discord",
        "slack",
        "zoom",
        "telegram",
        "whatsapp",
        # System tools
        "antivirus",
        "malwarebytes",
        "ccleaner",
        "7zip",
        "winrar",
        "steam",
        "epic games",
        "origin",
        "battle.net",
        "textedit",
    },
)

# Web / browser patterns â€” matched before information to catch "open youtube", "play X on youtube"
# The catch-all at the end handles ANY "open X" where X looks like a website.
_WEB_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Explicit URL
    (re.compile(r"\b(open|go to|visit)\s+(https?://\S+)", re.IGNORECASE), "open_url"),
    # Known popular sites
    (
        re.compile(
            r"\b(open|go to|navigate to|visit)\b.*(youtube|google|gmail|github|reddit|twitter|"
            r"facebook|instagram|linkedin|amazon|netflix|spotify|wikipedia|stackoverflow|"
            r"leetcode|hackerrank|codechef|codeforces|geeksforgeeks|w3schools|mdn|"
            r"udemy|coursera|edx|khan\s*academy|medium|dev\.to|hashnode|"
            r"whatsapp|telegram|discord|slack|zoom|teams|meet|"
            r"flipkart|myntra|snapdeal|paytm|phonepe|gpay|"
            r"hotstar|primevideo|jiocinema|zee5|sonyliv|"
            r"irctc|makemytrip|goibibo|booking|airbnb|"
            r"naukri|linkedin|indeed|glassdoor|"
            r"openai|anthropic|huggingface|kaggle|"
            r"twitch|tiktok|pinterest|tumblr|quora|"
            r"maps|translate|drive|docs|sheets|slides|calendar|keep)\b",
            re.IGNORECASE,
        ),
        "open_url",
    ),
    # Play X on youtube/spotify
    (re.compile(r"\bplay\b.+\bon\s+(youtube|spotify)\b", re.IGNORECASE), "web_search"),
    # "play X" without engine â€” default to youtube search
    (re.compile(r"^\s*play\s+\S", re.IGNORECASE), "web_search"),
    # Search X on engine
    (
        re.compile(r"\b(search|look up|find)\b.+\bon\s+(youtube|google|bing)\b", re.IGNORECASE),
        "web_search",
    ),
    (re.compile(r"\b(youtube|google)\b.*(search|find|look up)\b.+", re.IGNORECASE), "web_search"),
    # "open X.com" / "open X.org" / "open X.io" / "open X.net" â€” any domain
    (
        re.compile(
            r"\b(open|go to|visit|navigate to)\s+\S+\.(com|org|io|net|in|co|edu|gov|app|dev)\b",
            re.IGNORECASE,
        ),
        "open_url",
    ),
    # Catch-all: "open X" where X is NOT a known desktop app
    # This is the last resort â€” matches anything after "open" that wasn't caught above
    (
        re.compile(r"\b(open|go to|visit|navigate to)\s+(\w[\w\s]{1,40})\s*$", re.IGNORECASE),
        "open_url",
    ),
]

_INFORMATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(time|date|day|today|what time|what day)\b", re.IGNORECASE), "time_date"),
    (re.compile(r"\b(weather|temperature|forecast)\b", re.IGNORECASE), "weather"),
    (re.compile(r"\b(news|headlines|latest)\b", re.IGNORECASE), "news"),
    (re.compile(r"\b(search|look up|find|google)\b.+", re.IGNORECASE), "search"),
    (re.compile(r"\b(calculate|compute|math|how much)\b.+", re.IGNORECASE), "calculation"),
    (re.compile(r"\b(translate|translation)\b.+", re.IGNORECASE), "translation"),
    (re.compile(r"\b(define|definition|meaning of)\b.+", re.IGNORECASE), "definition"),
    (re.compile(r"\b(what|who|where|when|why|how|which)\b.+\??\s*$", re.IGNORECASE), "question"),
    (
        re.compile(
            r"\b(best|top|recommend|suggest)\b.+\b(language|framework|tool|library|app|software)\b",
            re.IGNORECASE,
        ),
        "question",
    ),
    (
        re.compile(
            r"\b(prime minister|president|capital|population|currency|founder|ceo|owner)\b",
            re.IGNORECASE,
        ),
        "question",
    ),
]

_COMMUNICATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(send|write|compose)\b.*(message|text|sms|whatsapp|telegram|email|mail)\b",
            re.IGNORECASE,
        ),
        "send_message",
    ),
    (re.compile(r"\b(call|phone|dial|ring)\b.+", re.IGNORECASE), "make_call"),
    (re.compile(r"\b(reply|respond|answer)\b.+", re.IGNORECASE), "reply"),
    (re.compile(r"\b(email|mail)\b.+", re.IGNORECASE), "email"),
    (re.compile(r"\b(message|text)\b.+", re.IGNORECASE), "send_message"),
]

_FILE_OPS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(create|make|new)\b.*(file|folder|directory|document)\b", re.IGNORECASE),
        "create",
    ),
    (re.compile(r"\b(delete|remove|trash)\b.*(file|folder|directory)\b", re.IGNORECASE), "delete"),
    (re.compile(r"\b(move|cut)\b.*(file|folder)\b", re.IGNORECASE), "move"),
    (re.compile(r"\b(copy|duplicate)\b.*(file|folder)\b", re.IGNORECASE), "copy"),
    (re.compile(r"\b(rename)\b.+", re.IGNORECASE), "rename"),
    (
        re.compile(
            r"\b(open|show|list)\b.*(file|folder|directory|documents|downloads)\b", re.IGNORECASE,
        ),
        "open_file",
    ),
    (re.compile(r"\b(save|export)\b.+", re.IGNORECASE), "save"),
]

_CONVERSATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(hello|hi|hey|good morning|good evening|good night)\b", re.IGNORECASE),
        "greeting",
    ),
    (re.compile(r"\b(thank|thanks|thank you)\b", re.IGNORECASE), "thanks"),
    (re.compile(r"\b(joke|funny|laugh|humor)\b", re.IGNORECASE), "joke"),
    (re.compile(r"\b(how are you|how do you do|how's it going)\b", re.IGNORECASE), "small_talk"),
    (re.compile(r"\b(bye|goodbye|see you|later|farewell)\b", re.IGNORECASE), "farewell"),
    (re.compile(r"\b(help|assist|support|can you)\b.+", re.IGNORECASE), "help"),
]


def _extract_web_query(text: str) -> dict[str, str]:
    """Extract URL/query and engine from a web command.

    Handles:
    - "play despacito on youtube" â†’ query="despacito", engine="youtube"
    - "play chak de india" â†’ query="chak de india", engine="youtube" (default for play)
    - "open leetcode" â†’ query="leetcode", engine="direct" (will be resolved to URL)
    - "open leetcode.com" â†’ query="leetcode.com", engine="direct"
    - "search python on google" â†’ query="python", engine="google"
    - "open X" (any unknown name) â†’ query="X", engine="google" (will search)

    Returns:
        dict with keys 'query' and 'engine'

    """
    # "play despacito on youtube" â†’ query="despacito", engine="youtube"
    m = re.search(r"\bplay\s+(.+?)\s+on\s+(youtube|spotify)\b", text, re.IGNORECASE)
    if m:
        return {"query": m.group(1).strip(), "engine": m.group(2).lower()}

    # "play X" without "on youtube" â†’ default to youtube search
    m = re.search(r"^\s*play\s+(.+?)(?:\s+(?:on|in)\s+\w+)?$", text, re.IGNORECASE)
    if m:
        query = m.group(1).strip().rstrip(".,!?")
        return {"query": query, "engine": "youtube"}

    # "search python tutorials on google/youtube/bing"
    m = re.search(
        r"\b(?:search|look up|find)\s+(.+?)\s+on\s+(youtube|google|bing)\b", text, re.IGNORECASE,
    )
    if m:
        return {"query": m.group(1).strip(), "engine": m.group(2).lower()}

    # "open X.com" / "go to X.org" â€” explicit domain
    m = re.search(
        r"\b(?:open|go to|navigate to|visit)\s+(\S+\.(com|org|io|net|in|co|edu|gov|app|dev)\S*)",
        text,
        re.IGNORECASE,
    )
    if m:
        domain = m.group(1).strip()
        return {"query": domain, "engine": "direct"}

    # "open youtube" / "go to github" â€” known site names
    m = re.search(
        r"\b(?:open|go to|navigate to|visit)\s+"
        r"(youtube|google|gmail|github|reddit|twitter|facebook|instagram|linkedin|"
        r"amazon|netflix|spotify|wikipedia|stackoverflow|leetcode|hackerrank|"
        r"codechef|codeforces|geeksforgeeks|w3schools|udemy|coursera|edx|"
        r"whatsapp|telegram|discord|slack|zoom|teams|meet|flipkart|myntra|"
        r"hotstar|primevideo|irctc|makemytrip|openai|huggingface|kaggle|"
        r"twitch|tiktok|pinterest|quora|maps|translate|drive|docs|sheets|"
        r"slides|calendar|keep|medium|hashnode|naukri|indeed|glassdoor|"
        r"paytm|phonepe|gpay|jiocinema|zee5|sonyliv|airbnb|booking)\b",
        text,
        re.IGNORECASE,
    )
    if m:
        return {"query": m.group(1).strip(), "engine": "direct"}

    # "open X" â€” any unknown name â†’ treat as web search on Google
    m = re.search(
        r"\b(?:open|go to|visit|navigate to)\s+(.+?)(?:\s+(?:and|then|in|on)\b.*)?$",
        text,
        re.IGNORECASE,
    )
    if m:
        query = m.group(1).strip().rstrip(".,!?")
        return {"query": query, "engine": "direct"}

    # Fallback: everything after the action verb
    cleaned = re.sub(
        r"^\s*(open|go to|visit|search|look up|find|play)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return {"query": cleaned, "engine": "google"}


def _extract_app_name(text: str) -> str:
    """Extract application name from a command string.

    Handles:
    - "open notepad" â†’ "notepad"
    - "open google chrome" â†’ "google chrome"
    - "open notepad and write something" â†’ "notepad" (stops at "and")
    - "Open Notepad. Himaya Open Notepad." â†’ "notepad" (stops at punctuation)
    """
    # Remove leading action words
    cleaned = re.sub(
        r"^\s*(open|launch|start|run|close|quit|exit|kill)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    # Stop at sentence boundaries (period, comma, exclamation)
    cleaned = re.split(r"[.,!?;]", cleaned)[0].strip()
    # Stop at conjunctions/prepositions that indicate a second action
    cleaned = re.split(r"\s+(?:and|then|after|&|in|on|with)\s+", cleaned, maxsplit=1)[0].strip()
    # Take first meaningful word(s) up to 3 words
    words = cleaned.split()
    # Filter out wake word fragments that Whisper might include
    wake_fragments = {"hey", "hi", "guru", "maya", "himaya"}
    words = [w for w in words if w.lower() not in wake_fragments]
    return " ".join(words[:3]) if words else ""


def _extract_contact_name(text: str) -> str:
    """Extract contact name from a communication command."""
    # Patterns like "send message to John" or "call Sarah"
    match = re.search(
        r"\b(?:to|call|phone|dial|ring)\s+([A-Za-z][A-Za-z\s]{0,30})", text, re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return ""


def _extract_file_path(text: str) -> str:
    """Extract file/folder name from a file operation command."""
    # Look for quoted strings first
    quoted = re.search(r'["\']([^"\']+)["\']', text)
    if quoted:
        return quoted.group(1)
    # Otherwise take words after action verb, stripping "file"/"folder"/"directory" keywords
    cleaned = re.sub(
        r"^\s*(create|make|new|delete|remove|trash|move|copy|rename|open|save)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    # Strip leading "file", "folder", "directory", "document" keywords
    cleaned = re.sub(
        r"^(file|folder|directory|document)\s+", "", cleaned, flags=re.IGNORECASE,
    ).strip()
    return cleaned[:100]  # Limit length


class _RuleEngine:
    """Regex-based fallback intent recognizer.

    Provides deterministic, low-latency intent classification when the
    LLM is unavailable.  Accuracy is lower than LLM-based recognition
    but sufficient for common commands.
    """

    def recognize(self, text: str, platform_name: str) -> IntentResult:
        """Classify *text* using regex rules.

        Args:
            text: Input text to classify.
            platform_name: Current platform identifier.

        Returns:
            :class:`IntentResult` with rule-based classification.

        """
        stripped = text.strip()
        if not stripped:
            return IntentResult(
                intent_type="conversation",
                parameters={},
                confidence=0.5,
                raw_text=text,
                platform=platform_name,
                method="rule_based",
            )

        # Try each category in priority order
        result = (
            self._try_web(stripped, platform_name)
            or self._try_system_control(stripped, platform_name)
            or self._try_communication(stripped, platform_name)
            or self._try_file_ops(stripped, platform_name)
            or self._try_information(stripped, platform_name)
            or self._try_conversation(stripped, platform_name)
        )

        if result is not None:
            return result

        # Default fallback
        return IntentResult(
            intent_type="conversation",
            parameters={"raw": stripped},
            confidence=0.3,
            raw_text=text,
            platform=platform_name,
            method="rule_based",
        )

    # ------------------------------------------------------------------
    # Category matchers
    # ------------------------------------------------------------------

    def _try_web(self, text: str, plat: str) -> IntentResult | None:
        """Try to match a web/URL intent.

        The catch-all pattern at the end of _WEB_PATTERNS would match
        "open notepad" as a web URL. We skip it for known desktop apps.
        """
        for pattern, action in _WEB_PATTERNS:
            if pattern.search(text):
                web_params = _extract_web_query(text)
                query = web_params.get("query", "").lower().strip()

                # Skip the catch-all if the target is a known desktop app
                if query and query in _KNOWN_DESKTOP_APPS:
                    continue

                params: dict[str, Any] = {"action": action, **web_params}
                return IntentResult(
                    intent_type="system_control",
                    parameters=params,
                    confidence=0.80,
                    raw_text=text,
                    platform=plat,
                    method="rule_based",
                )
        return None

    def _try_system_control(self, text: str, plat: str) -> IntentResult | None:
        for pattern, action in _SYSTEM_CONTROL_PATTERNS:
            if pattern.search(text):
                params: dict[str, Any] = {"action": action}
                if action in ("open_app", "close_app", "switch_app"):
                    params["app"] = _extract_app_name(text)
                elif action == "uninstall_app":
                    app = re.sub(
                        r"^\s*(uninstall|remove app|delete app)\s+",
                        "",
                        text,
                        flags=re.IGNORECASE,
                    ).strip()
                    params["app"] = app
                    params["requires_confirmation"] = True
                elif action in ("shutdown", "restart"):
                    params["requires_confirmation"] = True
                elif action == "volume":
                    num = re.search(r"\d+", text)
                    if num:
                        params["level"] = int(num.group())
                    elif re.search(r"\bup\b", text, re.IGNORECASE):
                        params["direction"] = "up"
                    elif re.search(r"\bdown\b", text, re.IGNORECASE):
                        params["direction"] = "down"
                    elif re.search(r"\b(mute|unmute)\b", text, re.IGNORECASE):
                        params["direction"] = (
                            re.search(r"\b(mute|unmute)\b", text, re.IGNORECASE).group(1).lower()
                        )
                elif action == "brightness":
                    num = re.search(r"\d+", text)
                    if num:
                        params["level"] = int(num.group())
                elif action == "window":
                    if re.search(r"\bminimize\b|\bminimise\b", text, re.IGNORECASE):
                        params["direction"] = "minimize"
                    elif re.search(r"\bmaximize\b|\bmaximise\b", text, re.IGNORECASE):
                        params["direction"] = "maximize"
                elif action in ("switch_app",):
                    # Extract app name after "switch to"
                    m = re.search(r"\b(?:switch to|go to app)\s+(.+)", text, re.IGNORECASE)
                    if m:
                        params["app"] = m.group(1).strip()
                    else:
                        params["app"] = _extract_app_name(text)
                elif action == "type_text":
                    # Extract the text to type â€” everything after the verb and optional target
                    m = re.search(
                        r'\b(?:type|write|input)\b\s+["\']?(.+?)["\']?\s*(?:\b(?:in|into|on)\b.+)?$',
                        text,
                        re.IGNORECASE,
                    )
                    params["text"] = m.group(1).strip() if m else ""
                return IntentResult(
                    intent_type="system_control",
                    parameters=params,
                    confidence=0.75,
                    raw_text=text,
                    platform=plat,
                    method="rule_based",
                )
        return None

    def _try_communication(self, text: str, plat: str) -> IntentResult | None:
        for pattern, action in _COMMUNICATION_PATTERNS:
            if pattern.search(text):
                params = {"action": action, "contact": _extract_contact_name(text)}
                return IntentResult(
                    intent_type="communication",
                    parameters=params,
                    confidence=0.75,
                    raw_text=text,
                    platform=plat,
                    method="rule_based",
                )
        return None

    def _try_file_ops(self, text: str, plat: str) -> IntentResult | None:
        # File ops only on desktop; map to conversation on mobile
        for pattern, action in _FILE_OPS_PATTERNS:
            if pattern.search(text):
                if _is_mobile(plat):
                    return IntentResult(
                        intent_type="conversation",
                        parameters={"note": "file_ops not supported on mobile"},
                        confidence=0.6,
                        raw_text=text,
                        platform=plat,
                        method="rule_based",
                    )
                params = {"action": action, "path": _extract_file_path(text)}
                return IntentResult(
                    intent_type="file_ops",
                    parameters=params,
                    confidence=0.75,
                    raw_text=text,
                    platform=plat,
                    method="rule_based",
                )
        return None

    def _try_information(self, text: str, plat: str) -> IntentResult | None:
        for pattern, action in _INFORMATION_PATTERNS:
            if pattern.search(text):
                params = {"action": action, "query": text}
                return IntentResult(
                    intent_type="information",
                    parameters=params,
                    confidence=0.70,
                    raw_text=text,
                    platform=plat,
                    method="rule_based",
                )
        return None

    def _try_conversation(self, text: str, plat: str) -> IntentResult | None:
        for pattern, action in _CONVERSATION_PATTERNS:
            if pattern.search(text):
                return IntentResult(
                    intent_type="conversation",
                    parameters={"action": action},
                    confidence=0.80,
                    raw_text=text,
                    platform=plat,
                    method="rule_based",
                )
        return None


# ---------------------------------------------------------------------------
# LLM prompt
# ---------------------------------------------------------------------------

_INTENT_PROMPT_TEMPLATE = """\
You are an intent classifier for a voice assistant. Classify the following command.

Command: "{text}"
Platform: {platform}

Return ONLY valid JSON (no markdown, no explanation) in this exact format:
{{
  "intent_type": "<one of: system_control, information, communication, file_ops, conversation>",
  "parameters": {{}},
  "confidence": <float 0.0-1.0>
}}

Rules:
- intent_type MUST be exactly one of: system_control, information, communication, file_ops, conversation
- parameters should contain relevant extracted values (app name, contact, file path, query, etc.)
- confidence should reflect how certain you are (0.9+ for clear commands, 0.5-0.7 for ambiguous)
- On mobile platforms (android, ios), file_ops should be mapped to conversation
- Desktop platforms (windows, macos, linux) support all intent types
"""


def _parse_llm_response(raw: str, text: str, platform_name: str) -> IntentResult | None:
    """Parse LLM JSON response into an IntentResult.

    Args:
        raw: Raw LLM response string.
        text: Original input text.
        platform_name: Platform identifier.

    Returns:
        :class:`IntentResult` or ``None`` if parsing fails.

    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    # Extract first JSON object
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return None

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    intent_type = str(data.get("intent_type", "conversation")).strip()
    if intent_type not in INTENT_TYPES:
        intent_type = "conversation"

    raw_confidence = data.get("confidence", 0.7)
    try:
        confidence = float(raw_confidence)
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.7

    parameters = data.get("parameters", {})
    if not isinstance(parameters, dict):
        parameters = {}

    return IntentResult(
        intent_type=intent_type,
        parameters=parameters,
        confidence=confidence,
        raw_text=text,
        platform=platform_name,
        method="llm",
    )


# ---------------------------------------------------------------------------
# IntentRecognizer
# ---------------------------------------------------------------------------


class IntentRecognizer:
    """Multi-platform intent recognizer with LLM primary and rule-based fallback.

    Lifecycle::

        recognizer = IntentRecognizer()
        await recognizer.initialize()

        result = await recognizer.recognize("open notepad", platform="windows")
        print(result.intent_type)   # "system_control"
        print(result.parameters)    # {"action": "open_app", "app": "notepad"}
        print(result.confidence)    # 0.92

        await recognizer.shutdown()

    Platform behaviour:
        - Desktop (windows/macos/linux/unknown): All intent types supported.
        - Mobile (android/ios): ``file_ops`` mapped to ``conversation``.

    Performance:
        - LLM path: <500ms (95th percentile)
        - Rule-based path: <5ms
    """

    def __init__(
        self,
        platform_override: str | None = None,
        llm_manager: Any | None = None,  # noqa: ANN401
    ) -> None:
        """Initialise the intent recognizer.

        Args:
            platform_override: Override auto-detected platform (for testing).
            llm_manager: Pre-built :class:`~Agent_Guru.llm.llm_manager.LLMManager`
                instance.  When ``None``, the recognizer will attempt to create
                one during :meth:`initialize`.

        """
        self._platform = platform_override or _detect_platform()
        self._llm_manager = llm_manager
        self._rule_engine = _RuleEngine()
        self._initialized: bool = False
        self._llm_available: bool = False

        logger.info("IntentRecognizer created â€” platform=%s", self._platform)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the recognizer and attempt to connect to LLM.

        If the LLM is unavailable (no API key, network error, etc.) the
        recognizer falls back to rule-based recognition transparently.

        Raises:
            RuntimeError: If already initialized.

        """
        if self._initialized:
            logger.warning("IntentRecognizer already initialized")
            return

        if self._llm_manager is None:
            try:
                from Agent_Guru.llm.llm_manager import LLMManager  # type: ignore[import]

                self._llm_manager = LLMManager()
                await self._llm_manager.initialize()
                self._llm_available = True
                logger.info("IntentRecognizer: LLM initialized successfully")
            except Exception as exc:
                logger.exception(
                    "IntentRecognizer: LLM unavailable (%s) â€” using rule-based fallback",
                    exc,
                )
                self._llm_manager = None
                self._llm_available = False
        else:
            # Caller provided a manager â€” assume it's ready
            self._llm_available = True

        self._initialized = True
        logger.info(
            "IntentRecognizer initialized â€” platform=%s, llm_available=%s",
            self._platform,
            self._llm_available,
        )

    async def shutdown(self) -> None:
        """Release resources held by the recognizer."""
        if self._llm_manager is not None and self._llm_available:
            try:
                await self._llm_manager.shutdown()
            except Exception:
                logger.exception("IntentRecognizer: LLM shutdown error")
        self._llm_manager = None
        self._llm_available = False
        self._initialized = False
        logger.info("IntentRecognizer shut down")

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    async def recognize(
        self,
        text: str,
        platform: str | None = None,
    ) -> IntentResult:
        """Extract intent from *text*.

        Tries the LLM first; falls back to rule-based recognition on any
        LLM error or when the LLM is unavailable.

        Args:
            text: Natural language command or query.
            platform: Platform override for this call.  Defaults to the
                platform detected at construction time.

        Returns:
            :class:`IntentResult` with intent type, parameters, and
            confidence score.

        """
        effective_platform = platform or self._platform

        # Empty / whitespace-only input â†’ conversation with low confidence
        if not text or not text.strip():
            return IntentResult(
                intent_type="conversation",
                parameters={},
                confidence=0.5,
                raw_text=text or "",
                platform=effective_platform,
                method="rule_based",
            )

        # Try LLM path
        if self._llm_available and self._llm_manager is not None:
            llm_result = await self._recognize_with_llm(text, effective_platform)
            if llm_result is not None:
                # Apply platform constraints
                return self._apply_platform_constraints(llm_result, effective_platform)

        # Rule-based fallback
        rule_result = self._rule_engine.recognize(text, effective_platform)
        return self._apply_platform_constraints(rule_result, effective_platform)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _recognize_with_llm(self, text: str, platform_name: str) -> IntentResult | None:
        """Attempt LLM-based intent recognition.

        Args:
            text: Input text.
            platform_name: Platform identifier.

        Returns:
            :class:`IntentResult` or ``None`` on failure.

        """
        if not (self._llm_manager is not None):
            msg = "self._llm_manager is not None assertion failed"
            raise AssertionError(msg)

        prompt = _INTENT_PROMPT_TEMPLATE.format(text=text, platform=platform_name)

        try:
            # Support both LLMManager.generate_response() and LLMRuntime.complete()
            if hasattr(self._llm_manager, "generate_response"):
                response = await self._llm_manager.generate_response(
                    query=prompt,
                    personality="guru",
                    session_id="intent_recognizer",
                    max_tokens=200,
                    temperature=0.0,
                )
                raw_content: str = (
                    response.content if hasattr(response, "content") else str(response)
                )
            elif hasattr(self._llm_manager, "complete"):
                from Agent_Guru.llm.models import CompletionRequest, Message

                request = CompletionRequest(
                    model="gemma3:4b",
                    messages=[Message(role="user", content=prompt)],
                    max_tokens=200,
                    temperature=0.0,
                )
                response = await self._llm_manager.complete(request)
                raw_content = response.content if hasattr(response, "content") else str(response)
            else:
                logger.warning("LLM manager has no usable generation method")
                return None
            result = _parse_llm_response(raw_content, text, platform_name)
            if result is not None:
                logger.debug(
                    "LLM intent: %s (confidence=%.2f)",
                    result.intent_type,
                    result.confidence,
                )
            return result
        except Exception:
            logger.exception("LLM intent recognition failed")
            return None

    @staticmethod
    def _apply_platform_constraints(result: IntentResult, platform_name: str) -> IntentResult:
        """Enforce platform-specific intent constraints.

        On mobile platforms, ``file_ops`` is not supported and is remapped
        to ``conversation``.

        Args:
            result: Raw intent result.
            platform_name: Platform identifier.

        Returns:
            Possibly modified :class:`IntentResult`.

        """
        if _is_mobile(platform_name) and result.intent_type == "file_ops":
            return IntentResult(
                intent_type="conversation",
                parameters={
                    **result.parameters,
                    "note": "file_ops not supported on mobile",
                },
                confidence=result.confidence,
                raw_text=result.raw_text,
                platform=platform_name,
                method=result.method,
            )
        return result

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def platform(self) -> str:
        """Detected platform name."""
        return self._platform

    @property
    def is_initialized(self) -> bool:
        """True when the recognizer has been initialized."""
        return self._initialized

    @property
    def llm_available(self) -> bool:
        """True when LLM-based recognition is available."""
        return self._llm_available
