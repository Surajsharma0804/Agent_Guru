"""
Tool Intelligence Engine for learning and optimizing tool performance.

This module implements intelligent tool tracking, ranking, and learning based on:
- Success rates and reliability
- Execution latency and performance
- User preferences and feedback
- Degradation detection and recovery

Production-grade features:
- Comprehensive alerting with severity levels
- Structured logging for observability
- Metrics tracking for monitoring
- Alert deduplication to prevent alert fatigue
- Configurable thresholds and policies
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Configure structured logger for production observability
logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels for tool degradation."""

    INFO = "info"  # Tool recovered, informational
    WARNING = "warning"  # Tool degraded but operational
    ERROR = "error"  # Tool severely degraded
    CRITICAL = "critical"  # Tool completely failed


@dataclass
class DegradationAlert:
    """Structured alert for tool degradation.

    Attributes:
        tool_id: Tool identifier
        severity: Alert severity level
        reason: Degradation reason
        metrics: Performance metrics at time of alert
        timestamp: When alert was generated
        alert_id: Unique alert identifier
    """

    tool_id: str
    severity: AlertSeverity
    reason: str
    metrics: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    alert_id: str = field(default="")

    def __post_init__(self) -> None:
        """Generate unique alert ID."""
        if not self.alert_id:
            self.alert_id = f"{self.tool_id}_{self.timestamp.isoformat()}"

    def to_dict(self) -> dict[str, Any]:
        """Convert alert to dictionary for logging/monitoring."""
        return {
            "alert_id": self.alert_id,
            "tool_id": self.tool_id,
            "severity": self.severity.value,
            "reason": self.reason,
            "metrics": self.metrics,
            "timestamp": self.timestamp.isoformat(),
        }


class AlertManager:
    """Production-grade alert manager with deduplication and throttling.

    Prevents alert fatigue by:
    - Deduplicating identical alerts within time window
    - Throttling alerts per tool
    - Aggregating multiple alerts
    - Supporting custom alert handlers (email, Slack, PagerDuty, etc.)
    """

    def __init__(
        self,
        dedup_window_seconds: int = 300,  # 5 minutes
        max_alerts_per_tool_per_hour: int = 10,
    ) -> None:
        """Initialize alert manager.

        Args:
            dedup_window_seconds: Time window for alert deduplication
            max_alerts_per_tool_per_hour: Maximum alerts per tool per hour
        """
        self._recent_alerts: dict[str, DegradationAlert] = {}
        self._alert_counts: dict[str, list[datetime]] = {}
        self._dedup_window = timedelta(seconds=dedup_window_seconds)
        self._max_alerts_per_hour = max_alerts_per_tool_per_hour
        self._alert_handlers: list[Callable[[DegradationAlert], None]] = []
        self._lock = asyncio.Lock()

    def register_handler(self, handler: Callable[[DegradationAlert], None]) -> None:
        """Register custom alert handler.

        Args:
            handler: Callable that receives DegradationAlert
        """
        self._alert_handlers.append(handler)

    async def send_alert(self, alert: DegradationAlert) -> bool:
        """Send alert with deduplication and throttling.

        Args:
            alert: Alert to send

        Returns:
            True if alert was sent, False if deduplicated/throttled
        """
        async with self._lock:
            # Check deduplication
            if self._is_duplicate(alert):
                logger.debug(
                    f"Alert deduplicated for {alert.tool_id}",
                    extra={"alert_id": alert.alert_id},
                )
                return False

            # Check throttling
            if self._is_throttled(alert.tool_id):
                logger.warning(
                    f"Alert throttled for {alert.tool_id} (too many alerts)",
                    extra={"alert_id": alert.alert_id},
                )
                return False

            # Send alert
            self._log_alert(alert)
            self._execute_handlers(alert)

            # Track alert
            self._recent_alerts[alert.tool_id] = alert
            if alert.tool_id not in self._alert_counts:
                self._alert_counts[alert.tool_id] = []
            self._alert_counts[alert.tool_id].append(alert.timestamp)

            # Cleanup old alerts
            self._cleanup_old_alerts()

            return True

    def _is_duplicate(self, alert: DegradationAlert) -> bool:
        """Check if alert is duplicate within dedup window."""
        if alert.tool_id not in self._recent_alerts:
            return False

        recent = self._recent_alerts[alert.tool_id]
        time_diff = alert.timestamp - recent.timestamp

        # Duplicate if same tool, same severity, within window
        return (
            time_diff < self._dedup_window
            and alert.severity == recent.severity
            and alert.reason == recent.reason
        )

    def _is_throttled(self, tool_id: str) -> bool:
        """Check if alerts for tool are throttled."""
        if tool_id not in self._alert_counts:
            return False

        # Count alerts in last hour
        one_hour_ago = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        recent_count = sum(1 for ts in self._alert_counts[tool_id] if ts > one_hour_ago)

        return recent_count >= self._max_alerts_per_hour

    def _log_alert(self, alert: DegradationAlert) -> None:
        """Log alert with structured logging."""
        log_level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.ERROR: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL,
        }[alert.severity]

        logger.log(
            log_level,
            f"TOOL ALERT [{alert.severity.value.upper()}]: {alert.tool_id} - {alert.reason}",
            extra={
                "alert": alert.to_dict(),
                "tool_id": alert.tool_id,
                "severity": alert.severity.value,
                "metrics": alert.metrics,
            },
        )

    def _execute_handlers(self, alert: DegradationAlert) -> None:
        """Execute all registered alert handlers."""
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error("Alert handler failed: %s", e,
                    extra={"alert_id": alert.alert_id, "error": str(e)},
                )

    def _cleanup_old_alerts(self) -> None:
        """Remove alerts older than dedup window."""
        cutoff = datetime.now(tz=timezone.utc) - self._dedup_window

        # Cleanup recent alerts
        to_remove = [
            tool_id for tool_id, alert in self._recent_alerts.items() if alert.timestamp < cutoff
        ]
        for tool_id in to_remove:
            del self._recent_alerts[tool_id]

        # Cleanup alert counts (keep last 24 hours)
        one_day_ago = datetime.now(tz=timezone.utc) - timedelta(days=1)
        for tool_id in list(self._alert_counts.keys()):
            self._alert_counts[tool_id] = [
                ts for ts in self._alert_counts[tool_id] if ts > one_day_ago
            ]
            if not self._alert_counts[tool_id]:
                del self._alert_counts[tool_id]


# Global alert manager instance
_alert_manager = AlertManager()


class FailurePattern(str, Enum):
    """Common failure patterns for tools."""

    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    PERMISSION_DENIED = "permission_denied"
    INVALID_PARAMETERS = "invalid_parameters"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    UNKNOWN = "unknown"


class ToolStats(BaseModel):
    """Statistics and performance metrics for a tool.

    Tracks execution history, success rates, latency, user feedback,
    and degradation status for intelligent tool selection.

    Attributes:
        tool_id: Unique tool identifier
        success_rate: Success rate (0.0-1.0)
        avg_latency: Average execution latency in milliseconds
        total_executions: Total number of executions
        successful_executions: Number of successful executions
        failed_executions: Number of failed executions
        failure_patterns: Dictionary of failure pattern → count
        user_rating: Average user rating (0.0-5.0)
        user_feedback_count: Number of user feedback entries
        is_degraded: Whether tool is currently degraded
        degradation_reason: Reason for degradation if applicable
        consecutive_failures: Number of consecutive failures
        last_execution_time: Timestamp of last execution
        last_success_time: Timestamp of last successful execution
        created_at: Timestamp when stats were created
        updated_at: Timestamp when stats were last updated
    """

    tool_id: str = Field(..., description="Unique tool identifier")
    success_rate: float = Field(default=1.0, description="Success rate (0.0-1.0)", ge=0.0, le=1.0)
    avg_latency: float = Field(
        default=0.0, description="Average execution latency in milliseconds", ge=0.0
    )
    total_executions: int = Field(default=0, description="Total number of executions", ge=0)
    successful_executions: int = Field(
        default=0, description="Number of successful executions", ge=0
    )
    failed_executions: int = Field(default=0, description="Number of failed executions", ge=0)
    failure_patterns: dict[str, int] = Field(
        default_factory=dict, description="Dictionary of failure pattern → count"
    )
    user_rating: float = Field(
        default=0.0, description="Average user rating (0.0-5.0)", ge=0.0, le=5.0
    )
    user_feedback_count: int = Field(default=0, description="Number of user feedback entries", ge=0)
    is_degraded: bool = Field(default=False, description="Whether tool is currently degraded")
    degradation_reason: Optional[str] = Field(
        default=None, description="Reason for degradation if applicable"
    )
    consecutive_failures: int = Field(default=0, description="Number of consecutive failures", ge=0)
    last_execution_time: Optional[datetime] = Field(
        default=None, description="Timestamp of last execution"
    )
    last_success_time: Optional[datetime] = Field(
        default=None, description="Timestamp of last successful execution"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when stats were created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when stats were last updated",
    )

    @field_validator("total_executions", mode="after")
    @classmethod
    def validate_total_executions(cls, v: int, info: Any) -> int:
        """Validate that total executions equals sum of successful and failed."""
        # Access validated data from the model
        data = info.data
        if "successful_executions" in data and "failed_executions" in data:
            expected = data["successful_executions"] + data["failed_executions"]
            if v != expected:
                raise ValueError(
                    f"total_executions ({v}) must equal successful_executions "
                    f"({data['successful_executions']}) + failed_executions "
                    f"({data['failed_executions']})"
                )
        return v

    @model_validator(mode="after")
    def validate_execution_counts(self) -> "ToolStats":
        """Validate execution counts are consistent."""
        expected_total = self.successful_executions + self.failed_executions
        if self.total_executions != expected_total:
            raise ValueError(
                f"total_executions ({self.total_executions}) must equal "
                f"successful_executions ({self.successful_executions}) + "
                f"failed_executions ({self.failed_executions})"
            )
        return self

    def calculate_success_rate(self) -> float:
        """Calculate success rate from execution counts.

        Returns:
            Success rate (0.0-1.0)
        """
        if self.total_executions == 0:
            return 1.0  # No executions yet, assume perfect
        return self.successful_executions / self.total_executions

    def update_success_rate(self) -> None:
        """Update success rate based on current execution counts."""
        self.success_rate = self.calculate_success_rate()

    def record_success(self, latency_ms: float) -> None:
        """Record a successful execution.

        Args:
            latency_ms: Execution latency in milliseconds
        """
        self.successful_executions += 1
        self.total_executions += 1
        self.consecutive_failures = 0
        self.last_execution_time = datetime.now(tz=timezone.utc)
        self.last_success_time = datetime.now(tz=timezone.utc)

        # Update average latency (exponential moving average)
        if self.avg_latency == 0.0:
            self.avg_latency = latency_ms
        else:
            # EMA with alpha=0.2 (gives more weight to recent values)
            self.avg_latency = 0.8 * self.avg_latency + 0.2 * latency_ms

        self.update_success_rate()
        self.updated_at = datetime.now(tz=timezone.utc)

        # Check if tool should be re-enabled after degradation
        if self.is_degraded and self.consecutive_failures == 0:
            # Send recovery alert
            alert = DegradationAlert(
                tool_id=self.tool_id,
                severity=AlertSeverity.INFO,
                reason="Tool recovered after successful execution",
                metrics={
                    "success_rate": self.success_rate,
                    "consecutive_failures": self.consecutive_failures,
                    "total_executions": self.total_executions,
                    "successful_executions": self.successful_executions,
                    "avg_latency_ms": self.avg_latency,
                    "previous_degradation_reason": self.degradation_reason,
                },
            )
            # Send alert (works in both sync and async contexts)
            try:
                asyncio.get_running_loop()
                _t = asyncio.create_task(_alert_manager.send_alert(alert))
                _t.add_done_callback(lambda _: None)  # prevent GC
            except RuntimeError:
                # No event loop running, send synchronously
                asyncio.run(_alert_manager.send_alert(alert))

            self.is_degraded = False
            self.degradation_reason = None

    def record_failure(self, failure_pattern: FailurePattern) -> None:
        """Record a failed execution.

        Args:
            failure_pattern: Type of failure that occurred
        """
        self.failed_executions += 1
        self.total_executions += 1
        self.consecutive_failures += 1
        self.last_execution_time = datetime.now(tz=timezone.utc)

        # Track failure pattern
        pattern_key = failure_pattern.value
        self.failure_patterns[pattern_key] = self.failure_patterns.get(pattern_key, 0) + 1

        self.update_success_rate()
        self.updated_at = datetime.now(tz=timezone.utc)

        # Check if tool should be marked as degraded
        # Only mark as degraded if we have enough data (at least 5 executions)
        if not self.is_degraded and self.total_executions >= 5:
            # Determine severity and send alert
            severity = None
            reason = None

            # Check consecutive failures first (higher priority)
            if self.consecutive_failures >= 3:
                self.is_degraded = True
                reason = f"Consecutive failures: {self.consecutive_failures}"
                # Critical if >= 5 consecutive failures
                severity = (
                    AlertSeverity.CRITICAL
                    if self.consecutive_failures >= 5
                    else AlertSeverity.ERROR
                )
            elif self.success_rate < 0.7:
                self.is_degraded = True
                reason = f"Success rate below threshold: {self.success_rate:.2%}"
                # Error if < 0.5, Warning if < 0.7
                severity = AlertSeverity.ERROR if self.success_rate < 0.5 else AlertSeverity.WARNING

            # Send production-grade alert
            if severity and reason:
                self.degradation_reason = reason
                alert = DegradationAlert(
                    tool_id=self.tool_id,
                    severity=severity,
                    reason=reason,
                    metrics={
                        "success_rate": self.success_rate,
                        "consecutive_failures": self.consecutive_failures,
                        "total_executions": self.total_executions,
                        "failed_executions": self.failed_executions,
                        "avg_latency_ms": self.avg_latency,
                        "most_common_failure": self.get_most_common_failure(),
                        "failure_patterns": self.failure_patterns,
                    },
                )
                # Send alert (works in both sync and async contexts)
                try:
                    asyncio.get_running_loop()
                    asyncio.create_task(_alert_manager.send_alert(alert))
                except RuntimeError:
                    # No event loop running, send synchronously
                    asyncio.run(_alert_manager.send_alert(alert))

    def record_user_feedback(self, rating: float) -> None:
        """Record user feedback rating.

        Args:
            rating: User rating (0.0-5.0)
        """
        if not 0.0 <= rating <= 5.0:
            raise ValueError(f"Rating must be between 0.0 and 5.0, got {rating}")

        # Update average rating (exponential moving average)
        if self.user_feedback_count == 0:
            self.user_rating = rating
        else:
            # EMA with alpha=0.3 (gives more weight to recent feedback)
            self.user_rating = 0.7 * self.user_rating + 0.3 * rating

        self.user_feedback_count += 1
        self.updated_at = datetime.now(tz=timezone.utc)

    def get_most_common_failure(self) -> Optional[str]:
        """Get the most common failure pattern.

        Returns:
            Most common failure pattern or None if no failures
        """
        if not self.failure_patterns:
            return None

        return max(self.failure_patterns.items(), key=lambda x: x[1])[0]

    def get_reliability_score(self) -> float:
        """Calculate reliability score (0.0-1.0).

        Considers success rate and degradation status.

        Returns:
            Reliability score (0.0-1.0)
        """
        if self.is_degraded:
            return self.success_rate * 0.5  # Penalize degraded tools
        return self.success_rate

    def get_speed_score(self, max_latency: float = 5000.0) -> float:
        """Calculate speed score (0.0-1.0).

        Args:
            max_latency: Maximum expected latency in milliseconds

        Returns:
            Speed score (0.0-1.0)
        """
        if self.avg_latency == 0.0:
            return 1.0  # No executions yet, assume fast

        # Score = 1.0 - (latency / max_latency), clamped to [0.0, 1.0]
        score = 1.0 - (self.avg_latency / max_latency)
        return max(0.0, min(1.0, score))

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "tool_id": "timer.set",
                "success_rate": 0.95,
                "avg_latency": 150.0,
                "total_executions": 100,
                "successful_executions": 95,
                "failed_executions": 5,
                "failure_patterns": {"timeout": 3, "invalid_parameters": 2},
                "user_rating": 4.5,
                "user_feedback_count": 20,
                "is_degraded": False,
                "degradation_reason": None,
                "consecutive_failures": 0,
            }
        }


class UserToolPreference(BaseModel):
    """User preference for a specific tool.

    Tracks user's preference score for a tool based on selections and feedback.

    Attributes:
        user_id: User identifier
        tool_id: Tool identifier
        preference_score: Preference score (0.0-1.0)
        selection_count: Number of times user selected this tool
        feedback_count: Number of feedback entries
        last_selected: Timestamp of last selection
        created_at: Timestamp when preference was created
        updated_at: Timestamp when preference was last updated
    """

    user_id: str = Field(..., description="User identifier")
    tool_id: str = Field(..., description="Tool identifier")
    preference_score: float = Field(
        default=0.5, description="Preference score (0.0-1.0)", ge=0.0, le=1.0
    )
    selection_count: int = Field(
        default=0, description="Number of times user selected this tool", ge=0
    )
    feedback_count: int = Field(default=0, description="Number of feedback entries", ge=0)
    last_selected: Optional[datetime] = Field(
        default=None, description="Timestamp of last selection"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when preference was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when preference was last updated",
    )

    def record_selection(self) -> None:
        """Record that user selected this tool."""
        self.selection_count += 1
        self.last_selected = datetime.now(tz=timezone.utc)
        self.updated_at = datetime.now(tz=timezone.utc)

        # Increase preference score slightly (EMA with alpha=0.1)
        self.preference_score = 0.9 * self.preference_score + 0.1 * 1.0

    def record_feedback(self, positive: bool) -> None:
        """Record user feedback for this tool.

        Args:
            positive: True for positive feedback, False for negative
        """
        self.feedback_count += 1
        self.updated_at = datetime.now(tz=timezone.utc)

        # Update preference score based on feedback (EMA with alpha=0.2)
        feedback_value = 1.0 if positive else 0.0
        self.preference_score = 0.8 * self.preference_score + 0.2 * feedback_value


class ToolIntelligenceEngine:
    """Tool Intelligence Engine for tracking and learning tool performance.

    Tracks tool execution statistics, user preferences, and provides
    intelligent tool ranking and selection recommendations.

    Production features:
    - Real-time degradation detection with alerts
    - Configurable alert handlers (email, Slack, PagerDuty, etc.)
    - Alert deduplication and throttling
    - Comprehensive metrics tracking
    - Thread-safe async operations

    Attributes:
        _tool_stats: Dictionary of tool_id → ToolStats
        _user_preferences: Dictionary of (user_id, tool_id) → UserToolPreference
        _stats_file: Path to stats persistence file
        _preferences_file: Path to preferences persistence file
        _lock: Async lock for thread-safe operations
    """

    def __init__(
        self, stats_file: Optional[Path] = None, preferences_file: Optional[Path] = None
    ) -> None:
        """Initialize Tool Intelligence Engine.

        Args:
            stats_file: Path to stats persistence file (optional)
            preferences_file: Path to preferences persistence file (optional)
        """
        self._tool_stats: dict[str, ToolStats] = {}
        self._user_preferences: dict[tuple[str, str], UserToolPreference] = {}
        self._stats_file = stats_file
        self._preferences_file = preferences_file
        self._lock = asyncio.Lock()

        # Load persisted data if files exist
        if self._stats_file and self._stats_file.exists():
            self._load_stats()
        if self._preferences_file and self._preferences_file.exists():
            self._load_preferences()

    @staticmethod
    def get_alert_manager() -> AlertManager:
        """Get global alert manager for configuration.

        Returns:
            Global AlertManager instance

        Example:
            >>> engine = ToolIntelligenceEngine()
            >>> alert_mgr = engine.get_alert_manager()
            >>> alert_mgr.register_handler(send_to_slack)
            >>> alert_mgr.register_handler(send_to_pagerduty)
        """
        return _alert_manager

    async def record_execution(
        self,
        tool_id: str,
        success: bool,
        latency_ms: float,
        failure_pattern: Optional[FailurePattern] = None,
    ) -> None:
        """Record a tool execution.

        Args:
            tool_id: Tool identifier
            success: Whether execution succeeded
            latency_ms: Execution latency in milliseconds
            failure_pattern: Failure pattern if execution failed
        """
        async with self._lock:
            # Get or create tool stats
            if tool_id not in self._tool_stats:
                self._tool_stats[tool_id] = ToolStats(tool_id=tool_id)

            stats = self._tool_stats[tool_id]

            # Record execution
            if success:
                stats.record_success(latency_ms)
            else:
                if failure_pattern is None:
                    failure_pattern = FailurePattern.UNKNOWN
                stats.record_failure(failure_pattern)

            # Persist stats
            if self._stats_file:
                self._save_stats()

    async def record_user_feedback(
        self,
        tool_id: str,
        user_id: str,
        rating: Optional[float] = None,
        positive: Optional[bool] = None,
    ) -> None:
        """Record user feedback for a tool.

        Args:
            tool_id: Tool identifier
            user_id: User identifier
            rating: User rating (0.0-5.0) if provided
            positive: Positive/negative feedback if provided
        """
        async with self._lock:
            # Record rating in tool stats
            if rating is not None:
                if tool_id not in self._tool_stats:
                    self._tool_stats[tool_id] = ToolStats(tool_id=tool_id)
                self._tool_stats[tool_id].record_user_feedback(rating)

            # Record preference
            if positive is not None:
                pref_key = (user_id, tool_id)
                if pref_key not in self._user_preferences:
                    self._user_preferences[pref_key] = UserToolPreference(
                        user_id=user_id, tool_id=tool_id
                    )
                self._user_preferences[pref_key].record_feedback(positive)

            # Persist data
            if self._stats_file:
                self._save_stats()
            if self._preferences_file:
                self._save_preferences()

    async def get_tool_stats(self, tool_id: str) -> Optional[ToolStats]:
        """Get statistics for a tool.

        Args:
            tool_id: Tool identifier

        Returns:
            ToolStats if available, None otherwise
        """
        async with self._lock:
            return self._tool_stats.get(tool_id)

    async def get_all_stats(self) -> dict[str, ToolStats]:
        """Get statistics for all tools.

        Returns:
            Dictionary of tool_id → ToolStats
        """
        async with self._lock:
            return self._tool_stats.copy()

    async def rank_tools(
        self,
        tool_ids: list[str],
        user_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> list[tuple[str, float]]:
        """Rank tools by combined score.

        Ranking formula: relevance (50%) + reliability (20%) + speed (20%) + user_preference (10%)

        Time Complexity: O(n) where n = number of tools
        Target Latency: <50ms

        Args:
            tool_ids: List of tool IDs to rank
            user_id: User identifier for personalization (optional)
            context: Additional context for ranking (optional)
                - intent: Intent object for relevance calculation
                - tool_registry: ToolRegistry for metadata lookup
                - relevance_scores: Pre-calculated relevance scores (dict)

        Returns:
            List of (tool_id, score) tuples sorted by score (descending)
        """
        async with self._lock:
            ranked = []

            for tool_id in tool_ids:
                score = await self._calculate_tool_score(tool_id, user_id, context)
                ranked.append((tool_id, score))

            # Sort by score (descending)
            ranked.sort(key=lambda x: x[1], reverse=True)
            return ranked

    async def _calculate_tool_score(
        self, tool_id: str, user_id: Optional[str], context: Optional[dict[str, Any]]
    ) -> float:
        """Calculate combined score for a tool.

        Scoring formula:
        - Relevance (50%): How well tool matches intent
        - Reliability (20%): Success rate and degradation status
        - Speed (20%): Execution latency
        - User Preference (10%): Learned user preferences

        Args:
            tool_id: Tool identifier
            user_id: User identifier (optional)
            context: Additional context (optional)
                - intent: Intent object for relevance calculation
                - tool_registry: ToolRegistry for metadata lookup
                - relevance_scores: Pre-calculated relevance scores (dict)

        Returns:
            Combined score (0.0-1.0)
        """
        # Get tool stats
        stats = self._tool_stats.get(tool_id)

        # Relevance score (50%)
        relevance_score = self._calculate_relevance_score(tool_id, context)

        # Reliability score (20%)
        reliability_score = 1.0
        if stats:
            reliability_score = stats.get_reliability_score()

        # Speed score (20%)
        speed_score = 1.0
        if stats:
            speed_score = stats.get_speed_score()

        # User preference score (10%)
        preference_score = 0.5  # Default neutral
        if user_id:
            pref_key = (user_id, tool_id)
            if pref_key in self._user_preferences:
                preference_score = self._user_preferences[pref_key].preference_score

        # Combined score
        score = (
            0.5 * relevance_score
            + 0.2 * reliability_score
            + 0.2 * speed_score
            + 0.1 * preference_score
        )

        return score

    def _calculate_relevance_score(self, tool_id: str, context: Optional[dict[str, Any]]) -> float:
        """Calculate relevance score for a tool based on intent matching.

        Args:
            tool_id: Tool identifier
            context: Context containing intent and/or tool_registry

        Returns:
            Relevance score (0.0-1.0)
        """
        if not context:
            return 1.0  # No context, assume relevant

        # Check for pre-calculated relevance scores
        if "relevance_scores" in context and tool_id in context["relevance_scores"]:
            return context["relevance_scores"][tool_id]

        # Check for explicit relevance score
        if "relevance" in context:
            return context["relevance"]

        # Calculate relevance from intent and tool metadata
        if "intent" in context and "tool_registry" in context:
            intent = context["intent"]
            tool_registry = context["tool_registry"]

            # Get tool metadata (use get_metadata method)
            tool_metadata = tool_registry.get_metadata(tool_id)
            if not tool_metadata:
                return 0.5  # Unknown tool, neutral score

            # Calculate relevance based on intent matching
            return self._calculate_intent_match_score(intent, tool_metadata)

        # Default to fully relevant if no intent information
        return 1.0

    def _calculate_intent_match_score(self, intent: Any, tool_metadata: Any) -> float:
        """Calculate how well a tool matches an intent.

        Scoring factors:
        - Capability overlap: 40%
        - Parameter coverage: 30%
        - Description similarity: 30%

        Args:
            intent: Intent object
            tool_metadata: ToolMetadata object

        Returns:
            Match score (0.0-1.0)
        """
        score = 0.0

        # Extract intent keywords
        intent_keywords = set(intent.original_input.lower().split())

        # Factor 1: Capability overlap (40%)
        capability_keywords = set()
        for cap in tool_metadata.capabilities:
            capability_keywords.update(cap.lower().split("_"))

        if capability_keywords:
            overlap = len(intent_keywords & capability_keywords)
            if overlap > 0:
                capability_score = min(overlap / max(len(capability_keywords), 1), 1.0)
                score += capability_score * 0.4
            # Bonus for substring matches
            for cap_word in capability_keywords:
                for intent_word in intent_keywords:
                    if cap_word in intent_word or intent_word in cap_word:
                        score += 0.1
                        break

        # Factor 2: Parameter coverage (30%)
        available_params = set(intent.entities.keys())
        required_params = {p.name for p in tool_metadata.parameters if p.required}

        if required_params:
            coverage = len(available_params & required_params) / len(required_params)
            score += coverage * 0.3
        else:
            # No required parameters, full score
            score += 0.3

        # Factor 3: Description similarity (30%)
        description_keywords = set(tool_metadata.description.lower().split())
        if description_keywords:
            overlap = len(intent_keywords & description_keywords)
            if overlap > 0:
                description_score = min(overlap / max(len(description_keywords), 1), 1.0)
                score += description_score * 0.3

        return min(score, 1.0)

    async def detect_degraded_tools(self) -> list[str]:
        """Detect tools that are currently degraded.

        Returns:
            List of degraded tool IDs
        """
        async with self._lock:
            degraded = []
            for tool_id, stats in self._tool_stats.items():
                if stats.is_degraded:
                    degraded.append(tool_id)
            return degraded

    async def get_user_tool_preferences(self, user_id: str) -> dict[str, float]:
        """Get user's tool preferences.

        Args:
            user_id: User identifier

        Returns:
            Dictionary of tool_id → preference_score
        """
        async with self._lock:
            preferences = {}
            for (uid, tool_id), pref in self._user_preferences.items():
                if uid == user_id:
                    preferences[tool_id] = pref.preference_score
            return preferences

    async def learn_tool_preference(self, user_id: str, tool_id: str, selected: bool) -> None:
        """Learn user's tool preference from selection.

        Args:
            user_id: User identifier
            tool_id: Tool identifier
            selected: Whether user selected this tool
        """
        async with self._lock:
            pref_key = (user_id, tool_id)

            # Get or create preference
            if pref_key not in self._user_preferences:
                self._user_preferences[pref_key] = UserToolPreference(
                    user_id=user_id, tool_id=tool_id
                )

            # Record selection
            if selected:
                self._user_preferences[pref_key].record_selection()

            # Persist preferences
            if self._preferences_file:
                self._save_preferences()

    def _save_stats(self) -> None:
        """Save tool stats to file."""
        if not self._stats_file:
            return

        # Convert to JSON-serializable format
        stats_data = {
            tool_id: stats.model_dump(mode="json") for tool_id, stats in self._tool_stats.items()
        }

        # Write to file
        self._stats_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._stats_file, "w") as f:
            json.dump(stats_data, f, indent=2, default=str)

    def _load_stats(self) -> None:
        """Load tool stats from file."""
        if not self._stats_file or not self._stats_file.exists():
            return

        try:
            with open(self._stats_file) as f:
                stats_data = json.load(f)

            # Convert from JSON to ToolStats objects
            self._tool_stats = {
                tool_id: ToolStats.model_validate(data) for tool_id, data in stats_data.items()
            }
        except Exception as e:
            # If loading fails, start fresh
            self._tool_stats = {}

    def _save_preferences(self) -> None:
        """Save user preferences to file."""
        if not self._preferences_file:
            return

        # Convert to JSON-serializable format
        prefs_data = {
            f"{user_id}:{tool_id}": pref.model_dump(mode="json")
            for (user_id, tool_id), pref in self._user_preferences.items()
        }

        # Write to file
        self._preferences_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._preferences_file, "w") as f:
            json.dump(prefs_data, f, indent=2, default=str)

    def _load_preferences(self) -> None:
        """Load user preferences from file."""
        if not self._preferences_file or not self._preferences_file.exists():
            return

        try:
            with open(self._preferences_file) as f:
                prefs_data = json.load(f)

            # Convert from JSON to UserToolPreference objects
            self._user_preferences = {}
            for key, data in prefs_data.items():
                user_id, tool_id = key.split(":", 1)
                pref = UserToolPreference.model_validate(data)
                self._user_preferences[(user_id, tool_id)] = pref
        except Exception as e:
            # If loading fails, start fresh
            self._user_preferences = {}
