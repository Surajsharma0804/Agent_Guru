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
    - Confidence scoring: 0.0–1.0

Architecture:
    IntentRecognizer
    ├── LLMManager  — primary structured intent extraction
    └── _RuleEngine — regex fallback when LLM unavailable

Author: Agent Guru Team
Date: 2026-03-20
"""
from __future__ import annotations

import json
import logging
import platform
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent types
# ---------------------------------------------------------------------------

INTENT_TYPES: List[str] = [
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
        import objc_util  # type: ignore[import]
        return "ios"
    except ImportError:
        pass
    try:
        import Foundation  # type: ignore[import]
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
        method: ``"llm"`` or ``"rule_based"`` — which engine produced this.
    """

    intent_type: str
    parameters: Dict[str, Any]
    confidence: float
    raw_text: str
    platform: str
    method: str = "rule_based"

    def __post_init__(self) -> None:
        if self.intent_type not in INTENT_TYPES:
            raise ValueError(
                f"Unknown intent_type '{self.intent_type}'. "
                f"Must be one of: {INTENT_TYPES}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be in [0.0, 1.0], got {self.confidence}"
            )


# ---------------------------------------------------------------------------
# Rule-based fallback engine
# ---------------------------------------------------------------------------

# Each entry: (pattern, intent_type, param_extractor_fn)
# param_extractor_fn receives the re.Match and returns a dict of parameters.

_SYSTEM_CONTROL_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(open|launch|start|run)\b.+", re.I), "open_app"),
    (re.compile(r"\b(close|quit|exit|kill)\b.+", re.I), "close_app"),
    (re.compile(r"\b(volume|sound)\b.*(up|down|mute|unmute|\d+)", re.I), "volume"),
    (re.compile(r"\b(mute|unmute)\b", re.I), "volume"),
    (re.compile(r"\b(brightness)\b.*(up|down|\d+)", re.I), "brightness"),
    (re.compile(r"\b(shutdown|restart|reboot|sleep|hibernate)\b", re.I), "power"),
    (re.compile(r"\b(minimize|maximise|maximize|restore|fullscreen)\b", re.I), "window"),
    (re.compile(r"\b(screenshot|screen shot|capture screen)\b", re.I), "screenshot"),
    (re.compile(r"\b(switch|alt.?tab)\b", re.I), "switch_app"),
    (re.compile(r"\b(wifi|bluetooth|airplane mode|do not disturb)\b", re.I), "settings"),
]

_INFORMATION_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(what|who|where|when|why|how)\b.+\??\s*$", re.I), "question"),
    (re.compile(r"\b(search|look up|find|google)\b.+", re.I), "search"),
    (re.compile(r"\b(weather|temperature|forecast)\b", re.I), "weather"),
    (re.compile(r"\b(news|headlines|latest)\b", re.I), "news"),
    (re.compile(r"\b(time|date|day|today)\b", re.I), "time_date"),
    (re.compile(r"\b(calculate|compute|math|how much)\b.+", re.I), "calculation"),
    (re.compile(r"\b(translate|translation)\b.+", re.I), "translation"),
    (re.compile(r"\b(define|definition|meaning of)\b.+", re.I), "definition"),
]

_COMMUNICATION_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(send|write|compose)\b.*(message|text|sms|whatsapp|telegram|email|mail)\b", re.I), "send_message"),
    (re.compile(r"\b(call|phone|dial|ring)\b.+", re.I), "make_call"),
    (re.compile(r"\b(reply|respond|answer)\b.+", re.I), "reply"),
    (re.compile(r"\b(email|mail)\b.+", re.I), "email"),
    (re.compile(r"\b(message|text)\b.+", re.I), "send_message"),
]

_FILE_OPS_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(create|make|new)\b.*(file|folder|directory|document)\b", re.I), "create"),
    (re.compile(r"\b(delete|remove|trash)\b.*(file|folder|directory)\b", re.I), "delete"),
    (re.compile(r"\b(move|cut)\b.*(file|folder)\b", re.I), "move"),
    (re.compile(r"\b(copy|duplicate)\b.*(file|folder)\b", re.I), "copy"),
    (re.compile(r"\b(rename)\b.+", re.I), "rename"),
    (re.compile(r"\b(open|show|list)\b.*(file|folder|directory|documents|downloads)\b", re.I), "open_file"),
    (re.compile(r"\b(save|export)\b.+", re.I), "save"),
]

_CONVERSATION_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(hello|hi|hey|good morning|good evening|good night)\b", re.I), "greeting"),
    (re.compile(r"\b(thank|thanks|thank you)\b", re.I), "thanks"),
    (re.compile(r"\b(joke|funny|laugh|humor)\b", re.I), "joke"),
    (re.compile(r"\b(how are you|how do you do|how's it going)\b", re.I), "small_talk"),
    (re.compile(r"\b(bye|goodbye|see you|later|farewell)\b", re.I), "farewell"),
    (re.compile(r"\b(help|assist|support|can you)\b.+", re.I), "help"),
]


def _extract_app_name(text: str) -> str:
    """Extract application name from a command string."""
    # Remove leading action words
    cleaned = re.sub(
        r"^\s*(open|launch|start|run|close|quit|exit|kill)\s+",
        "",
        text,
        flags=re.I,
    ).strip()
    # Take first meaningful word(s) up to 3 words
    words = cleaned.split()
    return " ".join(words[:3]) if words else ""


def _extract_contact_name(text: str) -> str:
    """Extract contact name from a communication command."""
    # Patterns like "send message to John" or "call Sarah"
    match = re.search(r"\b(?:to|call|phone|dial|ring)\s+([A-Za-z][A-Za-z\s]{0,30})", text, re.I)
    if match:
        return match.group(1).strip()
    return ""


def _extract_file_path(text: str) -> str:
    """Extract file/folder name from a file operation command."""
    # Look for quoted strings first
    quoted = re.search(r'["\']([^"\']+)["\']', text)
    if quoted:
        return quoted.group(1)
    # Otherwise take words after action verb
    cleaned = re.sub(
        r"^\s*(create|make|new|delete|remove|trash|move|copy|rename|open|save)\s+",
        "",
        text,
        flags=re.I,
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
            self._try_system_control(stripped, platform_name)
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

    def _try_system_control(self, text: str, plat: str) -> Optional[IntentResult]:
        for pattern, action in _SYSTEM_CONTROL_PATTERNS:
            if pattern.search(text):
                params: Dict[str, Any] = {"action": action}
                if action in ("open_app", "close_app", "switch_app"):
                    params["app"] = _extract_app_name(text)
                return IntentResult(
                    intent_type="system_control",
                    parameters=params,
                    confidence=0.75,
                    raw_text=text,
                    platform=plat,
                    method="rule_based",
                )
        return None

    def _try_communication(self, text: str, plat: str) -> Optional[IntentResult]:
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

    def _try_file_ops(self, text: str, plat: str) -> Optional[IntentResult]:
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

    def _try_information(self, text: str, plat: str) -> Optional[IntentResult]:
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

    def _try_conversation(self, text: str, plat: str) -> Optional[IntentResult]:
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


def _parse_llm_response(
    raw: str, text: str, platform_name: str
) -> Optional[IntentResult]:
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
        platform_override: Optional[str] = None,
        llm_manager: Optional[Any] = None,
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

        logger.info(
            "IntentRecognizer created — platform=%s", self._platform
        )

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
                from Agent_Guru.llm.llm_manager import LLMManager, LLMConfig  # type: ignore[import]

                self._llm_manager = LLMManager()
                await self._llm_manager.initialize()
                self._llm_available = True
                logger.info("IntentRecognizer: LLM initialized successfully")
            except Exception as exc:
                logger.warning(
                    "IntentRecognizer: LLM unavailable (%s) — using rule-based fallback",
                    exc,
                )
                self._llm_manager = None
                self._llm_available = False
        else:
            # Caller provided a manager — assume it's ready
            self._llm_available = True

        self._initialized = True
        logger.info(
            "IntentRecognizer initialized — platform=%s, llm_available=%s",
            self._platform,
            self._llm_available,
        )

    async def shutdown(self) -> None:
        """Release resources held by the recognizer."""
        if self._llm_manager is not None and self._llm_available:
            try:
                await self._llm_manager.shutdown()
            except Exception as exc:
                logger.warning("IntentRecognizer: LLM shutdown error: %s", exc)
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
        platform: Optional[str] = None,
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

        # Empty / whitespace-only input → conversation with low confidence
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

    async def _recognize_with_llm(
        self, text: str, platform_name: str
    ) -> Optional[IntentResult]:
        """Attempt LLM-based intent recognition.

        Args:
            text: Input text.
            platform_name: Platform identifier.

        Returns:
            :class:`IntentResult` or ``None`` on failure.
        """
        assert self._llm_manager is not None

        prompt = _INTENT_PROMPT_TEMPLATE.format(
            text=text, platform=platform_name
        )

        try:
            response = await self._llm_manager.generate_response(
                query=prompt,
                personality="guru",
                session_id="intent_recognizer",
                max_tokens=200,
                temperature=0.0,
            )
            raw_content: str = response.content if hasattr(response, "content") else str(response)
            result = _parse_llm_response(raw_content, text, platform_name)
            if result is not None:
                logger.debug(
                    "LLM intent: %s (confidence=%.2f)",
                    result.intent_type,
                    result.confidence,
                )
            return result
        except Exception as exc:
            logger.warning("LLM intent recognition failed: %s", exc)
            return None

    @staticmethod
    def _apply_platform_constraints(
        result: IntentResult, platform_name: str
    ) -> IntentResult:
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
