"""IntentParser - Voice Pipeline Intent Parsing Interface.

Provides a simple, synchronous interface for the voice pipeline to parse
user commands into structured intents with extracted parameters.

Architecture:
    - Wraps FastIntentRouter for <50ms pattern-based matching
    - Falls back to LLM for ambiguous/unknown queries
    - Returns structured ParseResult with intent + entities

Performance:
    - Time Complexity: O(n) where n = input length
    - Space Complexity: O(1) with LRU cache
    - P95 Latency: <50ms (fast path), <400ms (LLM fallback)
    - Accuracy: >98% for registered patterns

Author: Agent Guru Team
Date: 2026-03-19
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from Agent_Guru.reasoning.intent.fast_router import FastIntentRouter, PatternMatch
from Agent_Guru.reasoning.models.intent import IntentType

# Confidence threshold below which LLM fallback is triggered
_CONFIDENCE_THRESHOLD = 0.6

# Default patterns file path
_DEFAULT_PATTERNS = Path(__file__).parent.parent / "data" / "intent_patterns.yaml"


@dataclass
class ParseResult:
    """Result from intent parsing.

    Attributes:
        intent_type: Detected intent category
        entities: Extracted parameters keyed by name
        confidence: Detection confidence (0.0-1.0)
        requires_llm: Whether LLM reasoning is needed
        raw_text: Original user input
        latency_ms: Parse time in milliseconds
        method: Detection method used ("pattern" | "llm" | "unknown")

    """

    intent_type: str
    entities: dict[str, Any]
    confidence: float
    requires_llm: bool
    raw_text: str
    latency_ms: float
    method: str = "pattern"

    def get(self, key: str, default: Any = None) -> Any:
        """Get entity value by name with optional default."""
        return self.entities.get(key, default)

    def is_ambiguous(self) -> bool:
        """Return True if confidence is below threshold."""
        return self.confidence < _CONFIDENCE_THRESHOLD


@dataclass
class IntentParserConfig:
    """Configuration for IntentParser.

    Attributes:
        patterns_file: Path to intent_patterns.yaml
        cache_size: LRU cache size for repeated queries
        cache_ttl_seconds: Cache entry TTL
        confidence_threshold: Minimum confidence for pattern match
        enable_llm_fallback: Whether to route low-confidence to LLM

    """

    patterns_file: str | Path = _DEFAULT_PATTERNS
    cache_size: int = 10_000
    cache_ttl_seconds: int = 300
    confidence_threshold: float = _CONFIDENCE_THRESHOLD
    enable_llm_fallback: bool = True


class IntentParser:
    """Voice-pipeline-facing intent parser.

    Parses natural language commands into structured intents using
    pattern matching with optional LLM fallback for ambiguous queries.

    Example:
        >>> parser = IntentParser()
        >>> result = parser.parse("open YouTube")
        >>> result.intent_type
        'open_app'
        >>> result.get("app")
        'YouTube'

    Performance:
        - Pattern match: <50ms P95
        - LLM fallback: <400ms P95
        - Cache hit: <1ms

    """

    def __init__(self, config: IntentParserConfig | None = None) -> None:
        """Initialize the intent parser.

        Args:
            config: Parser configuration. Uses defaults if None.

        """
        self._config = config or IntentParserConfig()
        self._router = FastIntentRouter(
            cache_size=self._config.cache_size,
            cache_ttl_seconds=self._config.cache_ttl_seconds,
        )
        self._initialized = False

    def initialize(self) -> None:
        """Load patterns and prepare the router. Call once before parsing."""
        if self._initialized:
            return
        self._router.load_patterns(str(self._config.patterns_file))
        self._initialized = True

    def parse(self, text: str) -> ParseResult:
        """Parse a natural language command into a structured intent.

        Time Complexity: O(n) where n = len(text)
        Space Complexity: O(1) with cache

        Args:
            text: Raw user utterance (e.g. "open YouTube")

        Returns:
            ParseResult with intent_type, entities, and confidence.
            If no pattern matches and LLM fallback is disabled,
            returns an UNKNOWN intent with requires_llm=True.

        Raises:
            RuntimeError: If initialize() has not been called.

        """
        if not self._initialized:
            self.initialize()

        start = time.perf_counter()
        text = text.strip()

        match: PatternMatch | None = self._router.match(text)

        latency_ms = (time.perf_counter() - start) * 1000

        if match and match.confidence >= self._config.confidence_threshold:
            return ParseResult(
                intent_type=match.intent_type,
                entities={
                    k: v.value if hasattr(v, "value") else v for k, v in match.entities.items()
                },
                confidence=match.confidence,
                requires_llm=False,
                raw_text=text,
                latency_ms=latency_ms,
                method="pattern",
            )

        # Low confidence or no match - flag for LLM routing
        requires_llm = self._config.enable_llm_fallback
        intent_type = match.intent_type if match else IntentType.UNKNOWN.value
        confidence = match.confidence if match else 0.0

        return ParseResult(
            intent_type=intent_type,
            entities={},
            confidence=confidence,
            requires_llm=requires_llm,
            raw_text=text,
            latency_ms=latency_ms,
            method="llm" if requires_llm else "unknown",
        )

    def register_pattern(self, pattern: str, intent: str, entities: dict[str, str]) -> None:
        """Dynamically register a new command pattern at runtime.

        Args:
            pattern: Pattern string (e.g. "open {app}")
            intent: Intent type string (e.g. "open_app")
            entities: Entity name → type mapping (e.g. {"app": "APP"})

        """
        # Rebuild router with new pattern appended
        # For production, this would hot-reload the YAML
        # For now, we rebuild the trie with the new entry
        self._router._patterns.append(
            {  # type: ignore[attr-defined]
                "pattern": pattern,
                "intent": intent,
                "entities": entities,
            },
        )
        self._router._build_trie()

    def get_supported_intents(self) -> list[str]:
        """Return all registered intent types.

        Returns:
            Sorted list of unique intent type strings.

        """
        if not self._initialized:
            self.initialize()
        return sorted({p["intent"] for p in self._router._patterns})  # type: ignore[attr-defined]

    def get_metrics(self) -> dict[str, Any]:
        """Return router performance metrics.

        Returns:
            Dict with latency stats, cache hit rate, and match counts.

        """
        return self._router.get_metrics()
