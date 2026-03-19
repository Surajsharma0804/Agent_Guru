"""
User Feedback Loop - Task 49.

Implements feedback collection (thumbs up/down, detailed forms, implicit signals)
and feedback analysis (pattern detection, trend tracking, improvement prioritization).

Architecture:
    FeedbackLoop
        ├── FeedbackCollector   - Collect explicit and implicit feedback
        ├── FeedbackAnalyzer    - Analyze patterns and trends
        └── ImprovementPrioritizer - Prioritize improvements from feedback

Performance Requirements:
    - Time Complexity: O(1) per feedback record, O(n) for analysis
    - Space Complexity: O(max_history) bounded — no unbounded growth
    - Latency: <50ms for feedback collection

Requirements: 13.4
"""

from __future__ import annotations

import collections
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog

from Agent_Guru.reasoning.learning.feedback_store import FeedbackStore, FeedbackType, IntentFeedback

logger = structlog.get_logger(__name__)

# Maximum items kept in the in-memory history / buffer before oldest are evicted.
# Prevents unbounded memory growth in long-running production processes.
_DEFAULT_MAX_HISTORY: int = 10_000
_DEFAULT_MAX_BUFFER: int = 1_000


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime (Python 3.12+ safe)."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class FeedbackSignal(str, Enum):
    """Type of user feedback signal."""

    THUMBS_UP = "thumbs_up"           # Explicit positive
    THUMBS_DOWN = "thumbs_down"       # Explicit negative
    CORRECTION = "correction"         # User corrected the response
    RETRY = "retry"                   # User retried (implicit negative)
    TASK_COMPLETED = "task_completed" # Task completed successfully (implicit positive)
    TASK_ABANDONED = "task_abandoned" # User abandoned task (implicit negative)


@dataclass
class UserFeedback:
    """A single piece of user feedback."""

    feedback_id: str
    user_id: str
    session_id: str
    timestamp: datetime
    signal: FeedbackSignal
    original_input: str
    response: str
    intent: str
    confidence: float
    correction: Optional[str] = None
    error_description: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate fields after construction."""
        if not self.user_id or not self.user_id.strip():
            raise ValueError("user_id cannot be empty")
        if not self.session_id or not self.session_id.strip():
            raise ValueError("session_id cannot be empty")
        if not self.original_input or not self.original_input.strip():
            raise ValueError("original_input cannot be empty")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")

    @property
    def is_positive(self) -> bool:
        """True if this is a positive feedback signal."""
        return self.signal in (FeedbackSignal.THUMBS_UP, FeedbackSignal.TASK_COMPLETED)

    @property
    def is_negative(self) -> bool:
        """True if this is a negative feedback signal."""
        return self.signal in (
            FeedbackSignal.THUMBS_DOWN,
            FeedbackSignal.CORRECTION,
            FeedbackSignal.RETRY,
            FeedbackSignal.TASK_ABANDONED,
        )


@dataclass
class FailurePattern:
    """A recurring failure pattern identified from feedback."""

    pattern_id: str
    intent: str
    failure_count: int
    example_inputs: List[str]
    common_corrections: List[str]
    first_seen: datetime
    last_seen: datetime
    severity: str  # "low", "medium", "high"

    @property
    def frequency_per_day(self) -> float:
        """Average failures per day."""
        days = max((self.last_seen - self.first_seen).days, 1)
        return self.failure_count / days


@dataclass
class FeedbackTrend:
    """Trend in feedback over time."""

    period_start: datetime
    period_end: datetime
    total_feedback: int
    positive_count: int
    negative_count: int
    correction_count: int
    retry_count: int
    top_failing_intents: List[Tuple[str, int]]  # (intent, failure_count)

    @property
    def satisfaction_rate(self) -> float:
        """Positive feedback rate in [0, 1]."""
        if self.total_feedback == 0:
            return 0.0
        return self.positive_count / self.total_feedback

    @property
    def correction_rate(self) -> float:
        """Correction rate in [0, 1]."""
        if self.total_feedback == 0:
            return 0.0
        return self.correction_count / self.total_feedback


@dataclass
class ImprovementItem:
    """A prioritized improvement item."""

    priority: int          # 1 = highest priority
    intent: str
    failure_count: int
    impact_score: float    # Combined priority score in [0, 1]
    description: str
    suggested_action: str
    example_failures: List[str]


# ---------------------------------------------------------------------------
# Feedback Collector
# ---------------------------------------------------------------------------


class FeedbackCollector:
    """
    Collects explicit and implicit user feedback.

    Supports:
    - Thumbs up/down explicit feedback
    - Detailed error forms
    - Implicit signals (retries, task completion/abandonment)
    - Context capture for analysis

    The internal buffer is bounded to ``max_buffer`` items; oldest entries are
    evicted when the limit is reached to prevent unbounded memory growth.

    Time Complexity: O(1) per feedback item
    Space Complexity: O(max_buffer)
    """

    def __init__(self, store: FeedbackStore, max_buffer: int = _DEFAULT_MAX_BUFFER) -> None:
        self._store = store
        self._max_buffer = max_buffer
        self._feedback_buffer: collections.deque[UserFeedback] = collections.deque(
            maxlen=max_buffer
        )

    async def thumbs_up(
        self,
        user_id: str,
        session_id: str,
        original_input: str,
        response: str,
        intent: str,
        confidence: float,
        model_version: str = "v1.0",
    ) -> UserFeedback:
        """Record a thumbs up (positive) feedback."""
        return await self._record(
            user_id=user_id,
            session_id=session_id,
            signal=FeedbackSignal.THUMBS_UP,
            original_input=original_input,
            response=response,
            intent=intent,
            confidence=confidence,
            model_version=model_version,
        )

    async def thumbs_down(
        self,
        user_id: str,
        session_id: str,
        original_input: str,
        response: str,
        intent: str,
        confidence: float,
        error_description: Optional[str] = None,
        model_version: str = "v1.0",
    ) -> UserFeedback:
        """Record a thumbs down (negative) feedback."""
        return await self._record(
            user_id=user_id,
            session_id=session_id,
            signal=FeedbackSignal.THUMBS_DOWN,
            original_input=original_input,
            response=response,
            intent=intent,
            confidence=confidence,
            error_description=error_description,
            model_version=model_version,
        )

    async def correction(
        self,
        user_id: str,
        session_id: str,
        original_input: str,
        response: str,
        intent: str,
        confidence: float,
        correct_intent: str,
        model_version: str = "v1.0",
    ) -> UserFeedback:
        """Record a user correction and persist it to the feedback store for training."""
        if not correct_intent or not correct_intent.strip():
            raise ValueError("correct_intent cannot be empty")

        feedback = await self._record(
            user_id=user_id,
            session_id=session_id,
            signal=FeedbackSignal.CORRECTION,
            original_input=original_input,
            response=response,
            intent=intent,
            confidence=confidence,
            correction=correct_intent,
            model_version=model_version,
        )

        # Persist to store for downstream training pipeline
        await self._store.store_feedback(IntentFeedback(
            feedback_id=feedback.feedback_id,
            user_id=user_id,
            timestamp=feedback.timestamp,
            original_input=original_input,
            predicted_intent=intent,
            predicted_entities={},
            predicted_confidence=confidence,
            correct_intent=correct_intent,
            feedback_type=FeedbackType.CORRECTION,
            model_version=model_version,
        ))
        logger.info(
            "correction_stored",
            feedback_id=feedback.feedback_id,
            predicted_intent=intent,
            correct_intent=correct_intent,
        )
        return feedback

    async def implicit_retry(
        self,
        user_id: str,
        session_id: str,
        original_input: str,
        intent: str,
        confidence: float,
        model_version: str = "v1.0",
    ) -> UserFeedback:
        """Record an implicit retry signal (user repeated the command)."""
        return await self._record(
            user_id=user_id,
            session_id=session_id,
            signal=FeedbackSignal.RETRY,
            original_input=original_input,
            response="",
            intent=intent,
            confidence=confidence,
            model_version=model_version,
        )

    async def task_completed(
        self,
        user_id: str,
        session_id: str,
        original_input: str,
        intent: str,
        confidence: float,
        model_version: str = "v1.0",
    ) -> UserFeedback:
        """Record implicit positive signal from task completion."""
        return await self._record(
            user_id=user_id,
            session_id=session_id,
            signal=FeedbackSignal.TASK_COMPLETED,
            original_input=original_input,
            response="",
            intent=intent,
            confidence=confidence,
            model_version=model_version,
        )

    async def _record(
        self,
        user_id: str,
        session_id: str,
        signal: FeedbackSignal,
        original_input: str,
        response: str,
        intent: str,
        confidence: float,
        correction: Optional[str] = None,
        error_description: Optional[str] = None,
        model_version: str = "v1.0",
    ) -> UserFeedback:
        """Create, validate, buffer, and return a UserFeedback entry. O(1)."""
        feedback = UserFeedback(
            feedback_id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            timestamp=_utcnow(),
            signal=signal,
            original_input=original_input,
            response=response,
            intent=intent,
            confidence=confidence,
            correction=correction,
            error_description=error_description,
        )
        # deque with maxlen automatically evicts oldest — O(1), no memory leak
        self._feedback_buffer.append(feedback)
        logger.debug(
            "feedback_recorded",
            feedback_id=feedback.feedback_id,
            signal=signal.value,
            intent=intent,
        )
        return feedback

    def get_buffered_feedback(self) -> List[UserFeedback]:
        """Return a snapshot of all buffered feedback items."""
        return list(self._feedback_buffer)

    def clear_buffer(self) -> None:
        """Clear the feedback buffer."""
        self._feedback_buffer.clear()


# ---------------------------------------------------------------------------
# Feedback Analyzer
# ---------------------------------------------------------------------------


class FeedbackAnalyzer:
    """
    Analyzes feedback to identify patterns, trends, and failure modes.

    The history is bounded to ``max_history`` items (oldest evicted) to prevent
    unbounded memory growth in long-running services.

    Provides:
    - Failure pattern detection
    - Trend analysis over time windows
    - Top failing intents
    - Satisfaction rate tracking

    Time Complexity: O(n) for analysis, O(1) amortized for add
    Space Complexity: O(max_history)
    """

    def __init__(self, max_history: int = _DEFAULT_MAX_HISTORY) -> None:
        self._feedback_history: collections.deque[UserFeedback] = collections.deque(
            maxlen=max_history
        )

    def add_feedback(self, feedback: UserFeedback) -> None:
        """Add feedback to the analysis history. O(1) amortized."""
        self._feedback_history.append(feedback)

    def add_batch(self, feedback_list: List[UserFeedback]) -> None:
        """Add multiple feedback items. O(k) where k = len(feedback_list)."""
        for fb in feedback_list:
            self._feedback_history.append(fb)

    def detect_failure_patterns(
        self, min_occurrences: int = 3
    ) -> List[FailurePattern]:
        """
        Detect recurring failure patterns from negative feedback.

        Time Complexity: O(n) where n is history size

        Args:
            min_occurrences: Minimum failures to qualify as a pattern

        Returns:
            List of failure patterns sorted by failure count descending
        """
        intent_failures: Dict[str, List[UserFeedback]] = collections.defaultdict(list)
        for fb in self._feedback_history:
            if fb.is_negative:
                intent_failures[fb.intent].append(fb)

        patterns: List[FailurePattern] = []
        for intent, failures in intent_failures.items():
            if len(failures) < min_occurrences:
                continue

            examples = [f.original_input for f in failures[:5]]
            corrections = [f.correction for f in failures if f.correction][:5]
            timestamps = [f.timestamp for f in failures]

            failure_count = len(failures)
            if failure_count >= 20:
                severity = "high"
            elif failure_count >= 10:
                severity = "medium"
            else:
                severity = "low"

            patterns.append(FailurePattern(
                pattern_id=str(uuid.uuid4()),
                intent=intent,
                failure_count=failure_count,
                example_inputs=examples,
                common_corrections=corrections,
                first_seen=min(timestamps),
                last_seen=max(timestamps),
                severity=severity,
            ))

        patterns.sort(key=lambda p: p.failure_count, reverse=True)
        return patterns

    def compute_trend(
        self,
        window_days: int = 7,
        reference_time: Optional[datetime] = None,
    ) -> FeedbackTrend:
        """
        Compute feedback trend over a time window.

        Time Complexity: O(n)

        Args:
            window_days: Number of days to analyze
            reference_time: End of window (default: now UTC)

        Returns:
            FeedbackTrend for the specified window
        """
        end = reference_time or _utcnow()
        start = end - timedelta(days=window_days)

        window_feedback = [
            fb for fb in self._feedback_history
            if start <= fb.timestamp <= end
        ]

        positive = sum(1 for fb in window_feedback if fb.is_positive)
        negative = sum(1 for fb in window_feedback if fb.is_negative)
        corrections = sum(
            1 for fb in window_feedback if fb.signal == FeedbackSignal.CORRECTION
        )
        retries = sum(1 for fb in window_feedback if fb.signal == FeedbackSignal.RETRY)

        intent_failures: collections.Counter[str] = collections.Counter(
            fb.intent for fb in window_feedback if fb.is_negative
        )

        return FeedbackTrend(
            period_start=start,
            period_end=end,
            total_feedback=len(window_feedback),
            positive_count=positive,
            negative_count=negative,
            correction_count=corrections,
            retry_count=retries,
            top_failing_intents=intent_failures.most_common(5),
        )

    def get_satisfaction_rate(self, window_days: int = 7) -> float:
        """Get satisfaction rate over the last N days."""
        return self.compute_trend(window_days).satisfaction_rate

    def get_top_failing_intents(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """Get the most frequently failing intents across all history."""
        intent_failures: collections.Counter[str] = collections.Counter(
            fb.intent for fb in self._feedback_history if fb.is_negative
        )
        return intent_failures.most_common(top_n)


# ---------------------------------------------------------------------------
# Improvement Prioritizer
# ---------------------------------------------------------------------------


class ImprovementPrioritizer:
    """
    Prioritizes improvements based on feedback analysis.

    Scoring weights:
    - Failure frequency (0.5): how often this intent fails relative to worst
    - User impact     (0.3): fraction of total feedback affected, clamped [0,1]
    - Recency         (0.2): how recently the pattern was last seen (30-day decay)

    Time Complexity: O(n log n) for sorting
    """

    def prioritize(
        self,
        patterns: List[FailurePattern],
        total_feedback: int,
    ) -> List[ImprovementItem]:
        """
        Generate prioritized improvement items from failure patterns.

        Args:
            patterns: Detected failure patterns
            total_feedback: Total feedback count for impact calculation

        Returns:
            Prioritized list of improvements (priority 1 = most important)
        """
        if not patterns:
            return []

        max_failures = max(p.failure_count for p in patterns)
        now = _utcnow()

        scored: List[Tuple[float, FailurePattern, str]] = []
        for pattern in patterns:
            freq_score = pattern.failure_count / max(max_failures, 1)
            impact_score = min(1.0, pattern.failure_count / max(total_feedback, 1))
            days_since = (now - pattern.last_seen).days
            recency_score = max(0.0, 1.0 - days_since / 30.0)

            combined = 0.5 * freq_score + 0.3 * impact_score + 0.2 * recency_score
            scored.append((combined, pattern, self._suggest_action(pattern)))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            ImprovementItem(
                priority=i + 1,
                intent=pattern.intent,
                failure_count=pattern.failure_count,
                impact_score=round(score, 4),
                description=f"Intent '{pattern.intent}' fails {pattern.failure_count} times",
                suggested_action=action,
                example_failures=pattern.example_inputs[:3],
            )
            for i, (score, pattern, action) in enumerate(scored)
        ]

    def _suggest_action(self, pattern: FailurePattern) -> str:
        """Suggest a remediation action based on the failure pattern."""
        if pattern.common_corrections:
            return (
                f"Add training examples for '{pattern.intent}' "
                f"with corrections: {pattern.common_corrections[:2]}"
            )
        if pattern.severity == "high":
            return f"Urgent: Review and retrain '{pattern.intent}' intent model"
        return f"Add more training examples for '{pattern.intent}' intent"


# ---------------------------------------------------------------------------
# FeedbackLoop (orchestrator)
# ---------------------------------------------------------------------------


class FeedbackLoop:
    """
    Orchestrates the complete user feedback loop.

    Integrates:
    - FeedbackCollector: Collect all feedback types
    - FeedbackAnalyzer: Analyze patterns and trends
    - ImprovementPrioritizer: Generate actionable improvements

    Usage:
        loop = FeedbackLoop(store)
        await loop.thumbs_up(user_id="u1", session_id="s1", ...)
        report = loop.generate_report()
    """

    def __init__(
        self,
        store: FeedbackStore,
        max_buffer: int = _DEFAULT_MAX_BUFFER,
        max_history: int = _DEFAULT_MAX_HISTORY,
    ) -> None:
        self.collector = FeedbackCollector(store, max_buffer=max_buffer)
        self.analyzer = FeedbackAnalyzer(max_history=max_history)
        self._prioritizer = ImprovementPrioritizer()

    async def thumbs_up(
        self,
        user_id: str,
        session_id: str,
        original_input: str,
        response: str,
        intent: str,
        confidence: float,
        model_version: str = "v1.0",
    ) -> UserFeedback:
        """Record thumbs up and add to analyzer."""
        fb = await self.collector.thumbs_up(
            user_id=user_id,
            session_id=session_id,
            original_input=original_input,
            response=response,
            intent=intent,
            confidence=confidence,
            model_version=model_version,
        )
        self.analyzer.add_feedback(fb)
        return fb

    async def thumbs_down(
        self,
        user_id: str,
        session_id: str,
        original_input: str,
        response: str,
        intent: str,
        confidence: float,
        error_description: Optional[str] = None,
        model_version: str = "v1.0",
    ) -> UserFeedback:
        """Record thumbs down and add to analyzer."""
        fb = await self.collector.thumbs_down(
            user_id=user_id,
            session_id=session_id,
            original_input=original_input,
            response=response,
            intent=intent,
            confidence=confidence,
            error_description=error_description,
            model_version=model_version,
        )
        self.analyzer.add_feedback(fb)
        return fb

    async def correction(
        self,
        user_id: str,
        session_id: str,
        original_input: str,
        response: str,
        intent: str,
        confidence: float,
        correct_intent: str,
        model_version: str = "v1.0",
    ) -> UserFeedback:
        """Record correction and add to analyzer."""
        fb = await self.collector.correction(
            user_id=user_id,
            session_id=session_id,
            original_input=original_input,
            response=response,
            intent=intent,
            confidence=confidence,
            correct_intent=correct_intent,
            model_version=model_version,
        )
        self.analyzer.add_feedback(fb)
        return fb

    async def implicit_retry(
        self,
        user_id: str,
        session_id: str,
        original_input: str,
        intent: str,
        confidence: float,
        model_version: str = "v1.0",
    ) -> UserFeedback:
        """Record retry signal and add to analyzer."""
        fb = await self.collector.implicit_retry(
            user_id=user_id,
            session_id=session_id,
            original_input=original_input,
            intent=intent,
            confidence=confidence,
            model_version=model_version,
        )
        self.analyzer.add_feedback(fb)
        return fb

    async def task_completed(
        self,
        user_id: str,
        session_id: str,
        original_input: str,
        intent: str,
        confidence: float,
        model_version: str = "v1.0",
    ) -> UserFeedback:
        """Record task completion and add to analyzer."""
        fb = await self.collector.task_completed(
            user_id=user_id,
            session_id=session_id,
            original_input=original_input,
            intent=intent,
            confidence=confidence,
            model_version=model_version,
        )
        self.analyzer.add_feedback(fb)
        return fb

    def generate_report(
        self,
        window_days: int = 7,
        min_pattern_occurrences: int = 2,
        top_n: int = 5,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive feedback analysis report.

        Args:
            window_days: Analysis window in days
            min_pattern_occurrences: Minimum failures to surface a pattern
            top_n: Maximum items in each report section

        Returns:
            Report dict with trends, patterns, and prioritized improvements
        """
        trend = self.analyzer.compute_trend(window_days)
        patterns = self.analyzer.detect_failure_patterns(
            min_occurrences=min_pattern_occurrences
        )
        improvements = self._prioritizer.prioritize(patterns, trend.total_feedback)

        return {
            "period_days": window_days,
            "period_start": trend.period_start.isoformat(),
            "period_end": trend.period_end.isoformat(),
            "summary": {
                "total_feedback": trend.total_feedback,
                "satisfaction_rate": trend.satisfaction_rate,
                "correction_rate": trend.correction_rate,
                "positive_count": trend.positive_count,
                "negative_count": trend.negative_count,
            },
            "top_failing_intents": [
                {"intent": intent, "failures": count}
                for intent, count in trend.top_failing_intents
            ],
            "failure_patterns": [
                {
                    "intent": p.intent,
                    "failure_count": p.failure_count,
                    "severity": p.severity,
                    "examples": p.example_inputs[:3],
                }
                for p in patterns[:top_n]
            ],
            "prioritized_improvements": [
                {
                    "priority": item.priority,
                    "intent": item.intent,
                    "failure_count": item.failure_count,
                    "suggested_action": item.suggested_action,
                }
                for item in improvements[:top_n]
            ],
        }
