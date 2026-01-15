"""
Intent Pre-Filter Layer with Deterministic-First Guarantee

Production-grade intent pre-filtering system that enforces deterministic routing
for high-confidence commands, bypassing LLM processing when possible. This ensures
fast, predictable command execution for simple, unambiguous commands.

Requirement 31: Deterministic-First Guarantee
- Confidence >= 0.7 threshold for deterministic routing
- LLM bypass tracking and logging
- Bypass rate monitoring (target >= 80%)
- LLM only for genuine ambiguity
"""

import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import RLock
from typing import Any, Dict, List, Optional, Pattern, Tuple

from .intent import IntentType, StructuredIntent


class RoutingDecision(Enum):
    """Routing decision for intent processing."""

    DETERMINISTIC = "deterministic"  # Bypass LLM, route directly to executor
    LLM_REQUIRED = "llm_required"  # Requires LLM processing
    AMBIGUOUS = "ambiguous"  # Ambiguous, needs LLM clarification


@dataclass
class ActionPattern:
    """Pattern for detecting deterministic actions."""

    pattern: str  # Regex pattern
    intent_type: IntentType
    parameter_extractors: Dict[str, str] = field(default_factory=dict)  # param_name -> regex group
    confidence: float = 1.0
    priority: int = 0  # Higher priority patterns are checked first

    # Compiled pattern (cached)
    _compiled_pattern: Optional[Pattern] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Compile regex pattern after initialization."""
        try:
            self._compiled_pattern = re.compile(self.pattern, re.IGNORECASE | re.UNICODE)
        except re.error as e:
            raise ValueError(f"Invalid action pattern regex: {self.pattern} - {e}")

    def matches(self, text: str) -> Optional[re.Match]:
        """Check if text matches this pattern."""
        if not self._compiled_pattern:
            return None
        return self._compiled_pattern.search(text.strip())

    def extract_parameters(self, match: re.Match) -> Dict[str, Any]:
        """Extract parameters from regex match."""
        parameters = {}

        for param_name, group_name in self.parameter_extractors.items():
            try:
                value = match.group(group_name)
                if value:
                    parameters[param_name] = value.strip()
            except (IndexError, AttributeError):
                # Group not found, skip
                pass

        return parameters


@dataclass
class PreFilterResult:
    """Result of intent pre-filtering."""

    # Routing decision
    routing_decision: RoutingDecision
    confidence: float

    # Deterministic intent (if applicable)
    intent: Optional[StructuredIntent] = None
    bypass_llm: bool = False

    # Pattern matching details
    pattern_matched: Optional[str] = None
    parameters_extracted: Dict[str, Any] = field(default_factory=dict)
    parameters_complete: bool = False

    # Ambiguity details
    ambiguity_reason: Optional[str] = None
    requires_clarification: bool = False

    # Processing metadata
    processing_time_ms: int = 0
    patterns_evaluated: int = 0

    # Error information
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if pre-filtering was successful."""
        return self.error is None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "routing_decision": self.routing_decision.value,
            "confidence": self.confidence,
            "bypass_llm": self.bypass_llm,
            "pattern_matched": self.pattern_matched,
            "parameters_extracted": self.parameters_extracted,
            "parameters_complete": self.parameters_complete,
            "ambiguity_reason": self.ambiguity_reason,
            "requires_clarification": self.requires_clarification,
            "processing_time_ms": self.processing_time_ms,
            "patterns_evaluated": self.patterns_evaluated,
            "success": self.success,
            "error": self.error,
            "warnings": self.warnings,
        }


@dataclass
class BypassStatistics:
    """Statistics for LLM bypass tracking."""

    total_commands: int = 0
    bypassed_commands: int = 0
    llm_required_commands: int = 0
    ambiguous_commands: int = 0

    # Rolling window for bypass rate
    recent_decisions: deque = field(default_factory=lambda: deque(maxlen=100))

    # Timing statistics
    average_processing_time_ms: float = 0.0

    # Alert tracking
    low_bypass_rate_alerts: int = 0
    last_alert_time: Optional[datetime] = None

    def record_decision(self, decision: RoutingDecision, processing_time_ms: int):
        """Record a routing decision."""
        self.total_commands += 1
        self.recent_decisions.append(decision)

        if decision == RoutingDecision.DETERMINISTIC:
            self.bypassed_commands += 1
        elif decision == RoutingDecision.LLM_REQUIRED:
            self.llm_required_commands += 1
        elif decision == RoutingDecision.AMBIGUOUS:
            self.ambiguous_commands += 1

        # Update average processing time
        current_avg = self.average_processing_time_ms
        total = self.total_commands
        self.average_processing_time_ms = ((current_avg * (total - 1)) + processing_time_ms) / total

    def get_bypass_rate(self) -> float:
        """Get current bypass rate (0.0 to 1.0)."""
        if self.total_commands == 0:
            return 0.0
        return self.bypassed_commands / self.total_commands

    def get_recent_bypass_rate(self) -> float:
        """Get bypass rate for recent commands (rolling window)."""
        if len(self.recent_decisions) == 0:
            return 0.0

        bypassed = sum(1 for d in self.recent_decisions if d == RoutingDecision.DETERMINISTIC)
        return bypassed / len(self.recent_decisions)

    def check_bypass_rate_alert(self, threshold: float = 0.7) -> bool:
        """Check if bypass rate is below threshold and alert is needed."""
        recent_rate = self.get_recent_bypass_rate()

        # Only alert if we have enough data
        if len(self.recent_decisions) < 50:
            return False

        # Check if below threshold
        if recent_rate < threshold:
            # Don't alert too frequently (max once per 5 minutes)
            if self.last_alert_time:
                time_since_last_alert = datetime.utcnow() - self.last_alert_time
                if time_since_last_alert.total_seconds() < 300:  # 5 minutes
                    return False

            self.low_bypass_rate_alerts += 1
            self.last_alert_time = datetime.utcnow()
            return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            "total_commands": self.total_commands,
            "bypassed_commands": self.bypassed_commands,
            "llm_required_commands": self.llm_required_commands,
            "ambiguous_commands": self.ambiguous_commands,
            "bypass_rate": self.get_bypass_rate(),
            "recent_bypass_rate": self.get_recent_bypass_rate(),
            "average_processing_time_ms": self.average_processing_time_ms,
            "low_bypass_rate_alerts": self.low_bypass_rate_alerts,
            "last_alert_time": self.last_alert_time.isoformat() if self.last_alert_time else None,
        }


class ActionPatternRegistry:
    """Registry of deterministic action patterns."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._patterns: List[ActionPattern] = []
        self._lock = RLock()

        # Initialize with default patterns
        self._initialize_default_patterns()

    def _initialize_default_patterns(self):
        """Initialize default action patterns for common commands."""

        default_patterns = [
            # Application launching patterns
            ActionPattern(
                pattern=r"^(?:open|launch|start|run)\s+(?P<app_name>[\w\s]+?)(?:\s+and\s+|$)",
                intent_type=IntentType.LAUNCH_APP,
                parameter_extractors={"app_name": "app_name"},
                confidence=0.95,
                priority=10,
            ),
            # Application closing patterns
            ActionPattern(
                pattern=r"^(?:close|quit|exit)\s+(?P<app_name>[\w\s]+?)(?:\s+|$)",
                intent_type=IntentType.CLOSE_APP,
                parameter_extractors={"app_name": "app_name"},
                confidence=0.95,
                priority=10,
            ),
            # Text typing patterns (with "and write/type" clause)
            ActionPattern(
                pattern=r"^(?:open|launch)\s+(?P<app_name>[\w\s]+?)\s+and\s+(?:write|type)\s+(?P<text>.+)$",
                intent_type=IntentType.TYPE_TEXT,
                parameter_extractors={"app_name": "app_name", "text": "text"},
                confidence=0.90,
                priority=9,
            ),
            # Direct typing patterns
            ActionPattern(
                pattern=r"^(?:type|write)\s+(?P<text>.+)$",
                intent_type=IntentType.TYPE_TEXT,
                parameter_extractors={"text": "text"},
                confidence=0.85,
                priority=8,
            ),
            # Search patterns
            ActionPattern(
                pattern=r"^(?:search|google|find)\s+(?:for\s+)?(?P<query>.+)$",
                intent_type=IntentType.LAUNCH_APP,
                parameter_extractors={"query": "query"},
                confidence=0.90,
                priority=9,
            ),
            # Key press patterns
            ActionPattern(
                pattern=r"^(?:press|hit)\s+(?P<key>[\w\s]+?)(?:\s+key)?$",
                intent_type=IntentType.PRESS_KEY,
                parameter_extractors={"key": "key"},
                confidence=0.85,
                priority=7,
            ),
            # Mouse click patterns
            ActionPattern(
                pattern=r"^(?:click|tap)\s+(?:on\s+)?(?P<target>.+)$",
                intent_type=IntentType.MOUSE_ACTION,
                parameter_extractors={"target": "target", "action": "click"},
                confidence=0.80,
                priority=6,
            ),
            # File operations
            ActionPattern(
                pattern=r"^(?:open|load)\s+(?:file\s+)?(?P<file_path>.+)$",
                intent_type=IntentType.OPEN_FILE,
                parameter_extractors={"file_path": "file_path"},
                confidence=0.85,
                priority=7,
            ),
            ActionPattern(
                pattern=r"^(?:save|store)\s+(?:file\s+)?(?:as\s+)?(?P<file_path>.+)$",
                intent_type=IntentType.SAVE_FILE,
                parameter_extractors={"file_path": "file_path"},
                confidence=0.85,
                priority=7,
            ),
        ]

        # Sort by priority (highest first)
        default_patterns.sort(key=lambda p: p.priority, reverse=True)

        with self._lock:
            self._patterns = default_patterns

        self.logger.info(f"Initialized {len(default_patterns)} default action patterns")

    def get_patterns(self) -> List[ActionPattern]:
        """Get all registered patterns."""
        with self._lock:
            return self._patterns.copy()

    def add_pattern(self, pattern: ActionPattern):
        """Add a custom pattern."""
        with self._lock:
            self._patterns.append(pattern)
            # Re-sort by priority
            self._patterns.sort(key=lambda p: p.priority, reverse=True)

        self.logger.info(f"Added custom action pattern: {pattern.pattern}")

    def remove_pattern(self, pattern_str: str) -> bool:
        """Remove a pattern by its regex string."""
        with self._lock:
            initial_count = len(self._patterns)
            self._patterns = [p for p in self._patterns if p.pattern != pattern_str]
            removed = len(self._patterns) < initial_count

        if removed:
            self.logger.info(f"Removed action pattern: {pattern_str}")
        return removed


class IntentPreFilter:
    """
    Production-grade intent pre-filter with deterministic-first guarantee.

    Enforces Requirement 31: Deterministic-First Guarantee
    - Confidence ≥ 0.7 threshold for deterministic routing
    - LLM bypass tracking and logging
    - Bypass rate monitoring (target ≥ 80%)
    - LLM only for genuine ambiguity
    """

    # Confidence threshold for deterministic routing (Requirement 31.1)
    CONFIDENCE_THRESHOLD = 0.7

    # Target bypass rate (Requirement 31.6)
    TARGET_BYPASS_RATE = 0.80

    # Alert threshold for low bypass rate (Requirement 31.5)
    ALERT_BYPASS_THRESHOLD = 0.70

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Pattern registry
        self.pattern_registry = ActionPatternRegistry()

        # Bypass statistics (Requirement 31.4, 31.5)
        self.bypass_stats = BypassStatistics()
        self._stats_lock = RLock()

        # Ambiguity detection patterns
        self._ambiguous_indicators = [
            r"\b(?:it|that|this|them|those|these)\b",  # Vague pronouns
            r"\b(?:something|anything|somewhere)\b",  # Vague references
            r"\b(?:maybe|perhaps|possibly)\b",  # Uncertainty
            r"\b(?:which|what|where|who)\b",  # Questions
        ]
        self._ambiguous_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self._ambiguous_indicators]

        self.logger.info("Intent Pre-Filter initialized with deterministic-first guarantee")

    def classify(self, text: str) -> PreFilterResult:
        """
        Classify intent and determine routing decision.

        Args:
            text: Input command text

        Returns:
            PreFilterResult with routing decision and optional intent
        """

        start_time = time.time()

        try:
            # Validate input
            if not text or not text.strip():
                return PreFilterResult(
                    routing_decision=RoutingDecision.LLM_REQUIRED,
                    confidence=0.0,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    error="Empty input text",
                )

            # Check for ambiguity first (Requirement 31.3)
            ambiguity_check = self._check_ambiguity(text)
            if ambiguity_check:
                _result = PreFilterResult(
                    routing_decision=RoutingDecision.AMBIGUOUS,
                    confidence=0.3,
                    ambiguity_reason=ambiguity_check,
                    requires_clarification=True,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                )
                self._record_decision(result)
                return result

            # Try pattern matching for deterministic routing
            match_result = self._match_patterns(text)

            if match_result:
                pattern, match, parameters = match_result

                # Check if parameters are complete (Requirement 31.2)
                parameters_complete = self._check_parameters_complete(pattern.intent_type, parameters)

                # Check confidence threshold (Requirement 31.1)
                if pattern.confidence >= self.CONFIDENCE_THRESHOLD and parameters_complete:
                    # Create deterministic intent
                    intent = StructuredIntent(
                        intent_type=pattern.intent_type, parameters=parameters, confidence=pattern.confidence
                    )

                    _result = PreFilterResult(
                        routing_decision=RoutingDecision.DETERMINISTIC,
                        confidence=pattern.confidence,
                        intent=intent,
                        bypass_llm=True,  # Requirement 31.1
                        pattern_matched=pattern.pattern,
                        parameters_extracted=parameters,
                        parameters_complete=True,
                        processing_time_ms=int((time.time() - start_time) * 1000),
                    )

                    self._record_decision(result)
                    self.logger.info(
                        f"Deterministic routing: {pattern.intent_type.value} (confidence: {pattern.confidence:.2f})"
                    )
                    return result
                else:
                    # Confidence too low or parameters incomplete, requires LLM
                    _result = PreFilterResult(
                        routing_decision=RoutingDecision.LLM_REQUIRED,
                        confidence=pattern.confidence,
                        bypass_llm=False,
                        pattern_matched=pattern.pattern,
                        parameters_extracted=parameters,
                        parameters_complete=parameters_complete,
                        processing_time_ms=int((time.time() - start_time) * 1000),
                        warnings=[
                            (
                                f"Confidence below threshold: {pattern.confidence:.2f} < {self.CONFIDENCE_THRESHOLD}"
                                if pattern.confidence < self.CONFIDENCE_THRESHOLD
                                else ""
                            ),
                            "Parameters incomplete" if not parameters_complete else "",
                        ],
                    )

                    self._record_decision(result)
                    return result
            else:
                # No pattern matched, requires LLM
                _result = PreFilterResult(
                    routing_decision=RoutingDecision.LLM_REQUIRED,
                    confidence=0.0,
                    bypass_llm=False,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    warnings=["No deterministic pattern matched"],
                )

                self._record_decision(result)
                return result

        except Exception as e:
            self.logger.error(f"Intent pre-filter error: {e}", exc_info=True)
            return PreFilterResult(
                routing_decision=RoutingDecision.LLM_REQUIRED,
                confidence=0.0,
                processing_time_ms=int((time.time() - start_time) * 1000),
                error=f"Pre-filter error: {str(e)}",
            )

    def _check_ambiguity(self, text: str) -> Optional[str]:
        """
        Check if text contains ambiguous references requiring LLM clarification.

        Requirement 31.3: LLM only for ambiguous targets, vague pronouns, or clarification
        """

        for pattern in self._ambiguous_patterns:
            match = pattern.search(text)
            if match:
                return f"Ambiguous reference detected: '{match.group()}'"

        return None

    def _match_patterns(self, text: str) -> Optional[Tuple[ActionPattern, re.Match, Dict[str, Any]]]:
        """Match text against registered patterns."""

        patterns = self.pattern_registry.get_patterns()

        for pattern in patterns:
            match = pattern.matches(text)
            if match:
                parameters = pattern.extract_parameters(match)
                return (pattern, match, parameters)

        return None

    def _check_parameters_complete(self, intent_type: IntentType, parameters: Dict[str, Any]) -> bool:
        """
        Check if all required parameters are present for the intent type.

        Requirement 31.2: Complete parameters bypass LLM
        """

        required_params = {
            IntentType.TYPE_TEXT: ["text"],
            IntentType.PRESS_KEY: ["key"],
            IntentType.MOUSE_ACTION: ["action"],
            IntentType.LAUNCH_APP: ["app_name"],  # Note: 'query' is optional for search
            IntentType.CLOSE_APP: ["app_name"],
            IntentType.OPEN_FILE: ["file_path"],
            IntentType.SAVE_FILE: ["file_path"],
            IntentType.EXECUTE_SKILL: ["skill_id"],
        }

        required = required_params.get(intent_type, [])

        # Special case: search queries have 'query' instead of 'app_name'
        if intent_type == IntentType.LAUNCH_APP and "query" in parameters and "app_name" not in parameters:
            # Search query is complete if query is present
            return "query" in parameters and bool(parameters["query"])

        for param in required:
            if param not in parameters or not parameters[param]:
                return False

        return True

    def _record_decision(self, result: PreFilterResult):
        """
        Record routing decision for statistics tracking.

        Requirement 31.4: Log whether LLM was bypassed
        Requirement 31.5: Track bypass rate over rolling window
        """

        with self._stats_lock:
            self.bypass_stats.record_decision(result.routing_decision, result.processing_time_ms)

            # Check for low bypass rate alert (Requirement 31.5)
            if self.bypass_stats.check_bypass_rate_alert(self.ALERT_BYPASS_THRESHOLD):
                recent_rate = self.bypass_stats.get_recent_bypass_rate()
                self.logger.warning(
                    f"LOW BYPASS RATE ALERT: Recent bypass rate is {recent_rate:.1%}, "
                    f"below threshold of {self.ALERT_BYPASS_THRESHOLD:.1%}. "
                    f"Target is {self.TARGET_BYPASS_RATE:.1%}."
                )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get bypass statistics.

        Requirement 31.4, 31.5: Bypass tracking and monitoring
        """

        with self._stats_lock:
            stats = self.bypass_stats.to_dict()

        # Add threshold information
        stats["confidence_threshold"] = self.CONFIDENCE_THRESHOLD
        stats["target_bypass_rate"] = self.TARGET_BYPASS_RATE
        stats["alert_bypass_threshold"] = self.ALERT_BYPASS_THRESHOLD

        return stats

    def reset_statistics(self):
        """Reset bypass statistics."""
        with self._stats_lock:
            self.bypass_stats = BypassStatistics()
        self.logger.info("Reset intent pre-filter statistics")

    def add_custom_pattern(self, pattern: ActionPattern):
        """Add a custom action pattern."""
        self.pattern_registry.add_pattern(pattern)

    def remove_pattern(self, pattern_str: str) -> bool:
        """Remove an action pattern."""
        return self.pattern_registry.remove_pattern(pattern_str)

    def get_patterns(self) -> List[ActionPattern]:
        """Get all registered patterns."""
        return self.pattern_registry.get_patterns()
