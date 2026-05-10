"""Graceful degradation system.

Provides intelligent degradation when services fail:
- Multiple degradation levels
- Feature disabling based on level
- Automatic recovery when services available
- User notification of degraded functionality
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class DegradationLevel(str, Enum):
    """System degradation levels."""

    NORMAL = "normal"  # All features available
    DEGRADED = "degraded"  # Some features disabled
    MINIMAL = "minimal"  # Only essential features


class FeatureCategory(str, Enum):
    """Feature categories for degradation."""

    # Essential features (always available)
    BASIC_INTENT_DETECTION = "basic_intent_detection"
    SIMPLE_COMMANDS = "simple_commands"
    ERROR_RESPONSES = "error_responses"

    # Standard features (disabled in minimal mode)
    NEURAL_INTENT_DETECTION = "neural_intent_detection"
    TOOL_EXECUTION = "tool_execution"
    CONVERSATION_CONTEXT = "conversation_context"

    # Advanced features (disabled in degraded mode)
    LLM_REASONING = "llm_reasoning"
    MEMORY_RETRIEVAL = "memory_retrieval"
    KNOWLEDGE_SYNTHESIS = "knowledge_synthesis"
    PROACTIVE_SUGGESTIONS = "proactive_suggestions"
    MULTI_STEP_TASKS = "multi_step_tasks"
    BEHAVIORAL_LEARNING = "behavioral_learning"


@dataclass
class DegradationConfig:
    """Configuration for degradation behavior."""

    # Features available at each level
    normal_features: set[FeatureCategory] = field(default_factory=lambda: set(FeatureCategory))
    degraded_features: set[FeatureCategory] = field(
        default_factory=lambda: {
            FeatureCategory.BASIC_INTENT_DETECTION,
            FeatureCategory.SIMPLE_COMMANDS,
            FeatureCategory.ERROR_RESPONSES,
            FeatureCategory.NEURAL_INTENT_DETECTION,
            FeatureCategory.TOOL_EXECUTION,
            FeatureCategory.CONVERSATION_CONTEXT,
        },
    )
    minimal_features: set[FeatureCategory] = field(
        default_factory=lambda: {
            FeatureCategory.BASIC_INTENT_DETECTION,
            FeatureCategory.SIMPLE_COMMANDS,
            FeatureCategory.ERROR_RESPONSES,
        },
    )

    # Thresholds for automatic degradation
    error_rate_threshold: float = 0.10  # 10% error rate
    timeout_rate_threshold: float = 0.15  # 15% timeout rate
    service_unavailable_threshold: int = 3  # 3 consecutive failures

    # Recovery thresholds
    recovery_success_threshold: int = 5  # 5 consecutive successes
    recovery_check_interval: int = 60  # seconds


class DegradationManager:
    """Manager for graceful degradation."""

    def __init__(self, config: DegradationConfig | None = None) -> None:
        """Initialize degradation manager.

        Args:
            config: Degradation configuration

        """
        self.config = config or DegradationConfig()
        self._current_level = DegradationLevel.NORMAL
        self._disabled_features: set[FeatureCategory] = set()
        self._service_failures: dict[str, int] = {}
        self._service_successes: dict[str, int] = {}
        self._degradation_history: list[dict] = []
        self._last_level_change = datetime.now(tz=UTC)

    def get_current_level(self) -> DegradationLevel:
        """Get current degradation level.

        Returns:
            Current degradation level

        """
        return self._current_level

    def is_feature_available(self, feature: FeatureCategory) -> bool:
        """Check if a feature is available.

        Args:
            feature: Feature to check

        Returns:
            True if feature is available

        """
        if self._current_level == DegradationLevel.NORMAL:
            return feature in self.config.normal_features

        if self._current_level == DegradationLevel.DEGRADED:
            return feature in self.config.degraded_features

        # MINIMAL
        return feature in self.config.minimal_features

    def degrade_to_level(self, level: DegradationLevel, reason: str) -> None:
        """Degrade system to specified level.

        Args:
            level: Target degradation level
            reason: Reason for degradation

        """
        if level == self._current_level:
            return

        old_level = self._current_level
        self._current_level = level
        self._last_level_change = datetime.now(tz=UTC)

        # Update disabled features
        self._update_disabled_features()

        # Log degradation
        logger.warning(
            "system_degraded",
            old_level=old_level.value,
            new_level=level.value,
            reason=reason,
            disabled_features=[f.value for f in self._disabled_features],
        )

        # Record in history
        self._degradation_history.append(
            {
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "old_level": old_level.value,
                "new_level": level.value,
                "reason": reason,
            },
        )

        # Keep only last 100 entries
        if len(self._degradation_history) > 100:
            self._degradation_history = self._degradation_history[-100:]

    def recover_to_level(self, level: DegradationLevel, reason: str) -> None:
        """Recover system to specified level.

        Args:
            level: Target recovery level
            reason: Reason for recovery

        """
        if level == self._current_level:
            return

        # Can only recover to better level
        level_order = [
            DegradationLevel.MINIMAL,
            DegradationLevel.DEGRADED,
            DegradationLevel.NORMAL,
        ]

        current_index = level_order.index(self._current_level)
        target_index = level_order.index(level)

        if target_index <= current_index:
            logger.warning(
                "invalid_recovery",
                current_level=self._current_level.value,
                target_level=level.value,
            )
            return

        old_level = self._current_level
        self._current_level = level
        self._last_level_change = datetime.now(tz=UTC)

        # Update disabled features
        self._update_disabled_features()

        # Log recovery
        logger.info(
            "system_recovered",
            old_level=old_level.value,
            new_level=level.value,
            reason=reason,
            enabled_features=[f.value for f in self._get_available_features()],
        )

        # Record in history
        self._degradation_history.append(
            {
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "old_level": old_level.value,
                "new_level": level.value,
                "reason": reason,
                "recovery": True,
            },
        )

    def record_service_failure(self, service_name: str) -> None:
        """Record a service failure.

        Args:
            service_name: Name of service that failed

        """
        self._service_failures[service_name] = self._service_failures.get(service_name, 0) + 1
        self._service_successes[service_name] = 0

        # Check if should degrade
        failures = self._service_failures[service_name]

        if failures >= self.config.service_unavailable_threshold:
            if self._current_level == DegradationLevel.NORMAL:
                self.degrade_to_level(
                    DegradationLevel.DEGRADED,
                    f"Service {service_name} failed {failures} times",
                )
            elif self._current_level == DegradationLevel.DEGRADED:
                self.degrade_to_level(
                    DegradationLevel.MINIMAL,
                    f"Service {service_name} failed {failures} times",
                )

    def record_service_success(self, service_name: str) -> None:
        """Record a service success.

        Args:
            service_name: Name of service that succeeded

        """
        self._service_successes[service_name] = self._service_successes.get(service_name, 0) + 1
        self._service_failures[service_name] = 0

        # Check if should recover
        successes = self._service_successes[service_name]

        if successes >= self.config.recovery_success_threshold:
            if self._current_level == DegradationLevel.MINIMAL:
                self.recover_to_level(
                    DegradationLevel.DEGRADED,
                    f"Service {service_name} recovered with {successes} successes",
                )
            elif self._current_level == DegradationLevel.DEGRADED:
                self.recover_to_level(
                    DegradationLevel.NORMAL,
                    f"Service {service_name} recovered with {successes} successes",
                )

    def get_user_notification(self) -> str | None:
        """Get user notification message for current degradation.

        Returns:
            Notification message or None if normal

        """
        if self._current_level == DegradationLevel.NORMAL:
            return None

        if self._current_level == DegradationLevel.DEGRADED:
            return (
                "Some advanced features are temporarily unavailable. "
                "Basic functionality is still working."
            )

        # MINIMAL
        return "System is running in minimal mode. Only essential features are available."

    def get_status(self) -> dict:
        """Get degradation status.

        Returns:
            Status dictionary

        """
        return {
            "current_level": self._current_level.value,
            "available_features": [f.value for f in self._get_available_features()],
            "disabled_features": [f.value for f in self._disabled_features],
            "service_health": {
                service: {
                    "failures": self._service_failures.get(service, 0),
                    "successes": self._service_successes.get(service, 0),
                }
                for service in set(
                    list(self._service_failures.keys()) + list(self._service_successes.keys()),
                )
            },
            "last_level_change": self._last_level_change.isoformat(),
            "user_notification": self.get_user_notification(),
        }

    def _update_disabled_features(self) -> None:
        """Update set of disabled features based on current level."""
        available = self._get_available_features()
        all_features = set(FeatureCategory)
        self._disabled_features = all_features - available

    def _get_available_features(self) -> set[FeatureCategory]:
        """Get set of available features for current level.

        Returns:
            Set of available features

        """
        if self._current_level == DegradationLevel.NORMAL:
            return self.config.normal_features

        if self._current_level == DegradationLevel.DEGRADED:
            return self.config.degraded_features

        # MINIMAL
        return self.config.minimal_features

    def get_degradation_history(self, limit: int = 10) -> list[dict]:
        """Get recent degradation history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of degradation events

        """
        return self._degradation_history[-limit:]


# Global degradation manager
_global_degradation_manager: DegradationManager | None = None


def get_degradation_manager() -> DegradationManager:
    """Get the global degradation manager instance.

    Returns:
        Global DegradationManager instance

    """
    global _global_degradation_manager
    if _global_degradation_manager is None:
        _global_degradation_manager = DegradationManager()
    return _global_degradation_manager
