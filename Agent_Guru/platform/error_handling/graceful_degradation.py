"""
Module: agent_guru.platform.error_handling.graceful_degradation
Purpose: Graceful degradation for resource-constrained environments

This module implements graceful degradation to maintain core functionality
when system resources are constrained. It automatically disables non-critical
features and recovers to normal mode when resources become available.

Performance Requirements:
- Time Complexity: O(1) for mode checks and transitions
- Space Complexity: O(1) (fixed state tracking)
- Latency: <10ms for mode transitions
- Overhead: <1% CPU in normal mode

Architecture:
    The degradation manager monitors system resources and automatically
    transitions between normal and degraded modes based on thresholds.
    In degraded mode, non-critical features are disabled to preserve
    resources for core functionality.

Features:
    - Automatic resource constraint detection
    - Configurable feature priority levels
    - Smooth mode transitions
    - Recovery to normal mode
    - Degradation event logging

Usage Example:
    >>> from agent_guru.platform.error_handling.graceful_degradation import (
    ...     DegradationManager, DegradationConfig, FeaturePriority
    ... )
    >>>
    >>> # Initialize manager
    >>> config = DegradationConfig(
    ...     cpu_threshold=80.0,
    ...     memory_threshold=85.0,
    ...     check_interval=5.0
    ... )
    >>> manager = DegradationManager(config)
    >>>
    >>> # Check if feature is enabled
    >>> if manager.is_feature_enabled("gpu_acceleration"):
    ...     use_gpu()
    >>> else:
    ...     use_cpu()
    >>>
    >>> # Manual mode control
    >>> manager.enter_degraded_mode("High memory usage detected")
    >>> manager.recover_to_normal_mode()

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import psutil

logger = logging.getLogger(__name__)


class OperationMode(Enum):
    """System operation modes."""
    NORMAL = "normal"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class FeaturePriority(Enum):
    """Feature priority levels for degradation."""
    CRITICAL = 1      # Never disabled (core functionality)
    HIGH = 2          # Disabled only in critical mode
    MEDIUM = 3        # Disabled in degraded mode
    LOW = 4           # Disabled first when resources constrained


@dataclass
class DegradationConfig:
    """Configuration for graceful degradation.

    Attributes:
        cpu_threshold: CPU usage % to trigger degraded mode (default: 80%)
        memory_threshold: Memory usage % to trigger degraded mode (default: 85%)
        disk_threshold: Disk usage % to trigger degraded mode (default: 90%)
        critical_cpu_threshold: CPU usage % for critical mode (default: 95%)
        critical_memory_threshold: Memory usage % for critical mode (default: 95%)
        check_interval: Resource check interval in seconds (default: 5.0)
        recovery_threshold: % below threshold to recover (default: 10%)
        min_degraded_duration: Minimum time in degraded mode (default: 30s)
        enable_auto_recovery: Auto-recover when resources available (default: True)
    """
    cpu_threshold: float = 80.0
    memory_threshold: float = 85.0
    disk_threshold: float = 90.0
    critical_cpu_threshold: float = 95.0
    critical_memory_threshold: float = 95.0
    check_interval: float = 5.0
    recovery_threshold: float = 10.0
    min_degraded_duration: float = 30.0
    enable_auto_recovery: bool = True


@dataclass
class FeatureConfig:
    """Configuration for a degradable feature.

    Attributes:
        name: Feature name
        priority: Feature priority level
        enabled: Whether feature is currently enabled
        description: Feature description
        disable_callback: Optional callback when feature is disabled
        enable_callback: Optional callback when feature is enabled
    """
    name: str
    priority: FeaturePriority
    enabled: bool = True
    description: str = ""
    disable_callback: Optional[Callable[[], None]] = None
    enable_callback: Optional[Callable[[], None]] = None


@dataclass
class DegradationEvent:
    """Event representing a degradation state change.

    Attributes:
        timestamp: Event timestamp
        from_mode: Previous operation mode
        to_mode: New operation mode
        reason: Reason for degradation
        resource_stats: Resource usage at time of event
        disabled_features: Features disabled in this event
    """
    timestamp: float
    from_mode: OperationMode
    to_mode: OperationMode
    reason: str
    resource_stats: dict[str, float]
    disabled_features: list[str] = field(default_factory=list)


class DegradationManager:
    """Manages graceful degradation of system features.

    Time Complexity: O(1) for all operations
    Space Complexity: O(n) where n is number of features

    This manager monitors system resources and automatically disables
    non-critical features when resources are constrained. It provides
    smooth transitions between operation modes and automatic recovery.

    Example:
        >>> manager = DegradationManager(DegradationConfig())
        >>> manager.register_feature(
        ...     "gpu_acceleration",
        ...     FeaturePriority.MEDIUM,
        ...     "GPU-accelerated processing"
        ... )
        >>> await manager.start_monitoring()
        >>> # Manager automatically handles degradation
        >>> await manager.stop_monitoring()
    """

    def __init__(self, config: DegradationConfig) -> None:
        """Initialize degradation manager.

        Args:
            config: Degradation configuration

        Raises:
            ValueError: If config parameters are invalid
        """
        self._validate_config(config)
        self.config = config
        self._mode = OperationMode.NORMAL
        self._features: dict[str, FeatureConfig] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._degraded_since: Optional[float] = None
        self._event_history: list[DegradationEvent] = []
        self._max_history_size = 100

        # Initialize default features
        self._register_default_features()

        logger.info(
            "DegradationManager initialized",
            extra={
                "mode": self._mode.value,
                "cpu_threshold": config.cpu_threshold,
                "memory_threshold": config.memory_threshold
            }
        )

    @property
    def mode(self) -> OperationMode:
        """Get current operation mode."""
        return self._mode

    @property
    def is_degraded(self) -> bool:
        """Check if system is in degraded mode."""
        return self._mode != OperationMode.NORMAL

    @property
    def degraded_duration(self) -> Optional[float]:
        """Get duration in degraded mode (seconds)."""
        if self._degraded_since is None:
            return None
        return time.time() - self._degraded_since

    def register_feature(
        self,
        name: str,
        priority: FeaturePriority,
        description: str = "",
        disable_callback: Optional[Callable[[], None]] = None,
        enable_callback: Optional[Callable[[], None]] = None
    ) -> None:
        """Register a degradable feature.

        Time Complexity: O(1)

        Args:
            name: Feature name (unique identifier)
            priority: Feature priority level
            description: Feature description
            disable_callback: Optional callback when feature is disabled
            enable_callback: Optional callback when feature is enabled

        Raises:
            ValueError: If feature already registered
        """
        if name in self._features:
            raise ValueError(f"Feature already registered: {name}")

        self._features[name] = FeatureConfig(
            name=name,
            priority=priority,
            enabled=True,
            description=description,
            disable_callback=disable_callback,
            enable_callback=enable_callback
        )

        logger.debug("Feature registered: %s", name,
            extra={
                "priority": priority.name,
                "description": description
            }
        )

    def unregister_feature(self, name: str) -> None:
        """Unregister a feature.

        Time Complexity: O(1)

        Args:
            name: Feature name

        Raises:
            KeyError: If feature not found
        """
        if name not in self._features:
            raise KeyError(f"Feature not found: {name}")

        del self._features[name]
        logger.debug("Feature unregistered: %s", name)

    def is_feature_enabled(self, name: str) -> bool:
        """Check if a feature is currently enabled.

        Time Complexity: O(1)

        Args:
            name: Feature name

        Returns:
            True if feature is enabled, False otherwise

        Raises:
            KeyError: If feature not found
        """
        if name not in self._features:
            raise KeyError(f"Feature not found: {name}")

        return self._features[name].enabled

    def get_enabled_features(self) -> list[str]:
        """Get list of currently enabled features.

        Time Complexity: O(n) where n is number of features

        Returns:
            List of enabled feature names
        """
        return [
            name for name, feature in self._features.items()
            if feature.enabled
        ]

    def get_disabled_features(self) -> list[str]:
        """Get list of currently disabled features.

        Time Complexity: O(n) where n is number of features

        Returns:
            List of disabled feature names
        """
        return [
            name for name, feature in self._features.items()
            if not feature.enabled
        ]

    def enter_degraded_mode(self, reason: str) -> None:
        """Manually enter degraded mode.

        Time Complexity: O(n) where n is number of features

        Args:
            reason: Reason for entering degraded mode
        """
        if self._mode == OperationMode.DEGRADED:
            logger.warning("Already in degraded mode")
            return

        self._transition_to_mode(OperationMode.DEGRADED, reason)

    def enter_critical_mode(self, reason: str) -> None:
        """Manually enter critical mode.

        Time Complexity: O(n) where n is number of features

        Args:
            reason: Reason for entering critical mode
        """
        if self._mode == OperationMode.CRITICAL:
            logger.warning("Already in critical mode")
            return

        self._transition_to_mode(OperationMode.CRITICAL, reason)

    def recover_to_normal_mode(self) -> None:
        """Manually recover to normal mode.

        Time Complexity: O(n) where n is number of features
        """
        if self._mode == OperationMode.NORMAL:
            logger.warning("Already in normal mode")
            return

        # Check minimum degraded duration
        if self._degraded_since is not None:
            duration = time.time() - self._degraded_since
            if duration < self.config.min_degraded_duration:
                logger.warning(
                    f"Cannot recover yet (min duration: {self.config.min_degraded_duration}s, "
                    f"current: {duration:.1f}s)"
                )
                return

        self._transition_to_mode(OperationMode.NORMAL, "Manual recovery")

    async def start_monitoring(self) -> None:
        """Start automatic resource monitoring.

        Starts a background task that periodically checks system resources
        and automatically transitions between operation modes.
        """
        if self._monitoring_task is not None:
            logger.warning("Monitoring already started")
            return

        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Resource monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop automatic resource monitoring."""
        if self._monitoring_task is None:
            logger.warning("Monitoring not started")
            return

        self._monitoring_task.cancel()
        try:
            await self._monitoring_task
        except asyncio.CancelledError:
            pass

        self._monitoring_task = None
        logger.info("Resource monitoring stopped")

    def get_resource_stats(self) -> dict[str, float]:
        """Get current resource usage statistics.

        Time Complexity: O(1)

        Returns:
            Dictionary with resource usage percentages
        """
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent
        }

    def get_event_history(self, limit: Optional[int] = None) -> list[DegradationEvent]:
        """Get degradation event history.

        Args:
            limit: Maximum number of events to return (None for all)

        Returns:
            List of degradation events (most recent first)
        """
        events = list(reversed(self._event_history))
        if limit is not None:
            events = events[:limit]
        return events

    def _register_default_features(self) -> None:
        """Register default degradable features."""
        # GPU acceleration (medium priority)
        self.register_feature(
            "gpu_acceleration",
            FeaturePriority.MEDIUM,
            "GPU-accelerated processing"
        )

        # Caching (medium priority)
        self.register_feature(
            "response_caching",
            FeaturePriority.MEDIUM,
            "Response caching for performance"
        )

        # Detailed logging (low priority)
        self.register_feature(
            "detailed_logging",
            FeaturePriority.LOW,
            "Detailed debug logging"
        )

        # Performance metrics (low priority)
        self.register_feature(
            "performance_metrics",
            FeaturePriority.LOW,
            "Performance metrics collection"
        )

        # Predictive features (low priority)
        self.register_feature(
            "predictive_features",
            FeaturePriority.LOW,
            "Predictive analysis and suggestions"
        )

    def _transition_to_mode(self, new_mode: OperationMode, reason: str) -> None:
        """Transition to a new operation mode.

        Time Complexity: O(n) where n is number of features

        Args:
            new_mode: Target operation mode
            reason: Reason for transition
        """
        old_mode = self._mode
        resource_stats = self.get_resource_stats()

        logger.info(
            f"Mode transition: {old_mode.value} -> {new_mode.value}",
            extra={
                "reason": reason,
                "cpu_percent": resource_stats["cpu_percent"],
                "memory_percent": resource_stats["memory_percent"]
            }
        )

        # Disable features based on new mode
        disabled_features = self._apply_mode_constraints(new_mode)

        # Update mode
        self._mode = new_mode

        # Track degraded duration
        if new_mode != OperationMode.NORMAL:
            if self._degraded_since is None:
                self._degraded_since = time.time()
        else:
            self._degraded_since = None

        # Record event
        event = DegradationEvent(
            timestamp=time.time(),
            from_mode=old_mode,
            to_mode=new_mode,
            reason=reason,
            resource_stats=resource_stats,
            disabled_features=disabled_features
        )
        self._add_event(event)

    def _apply_mode_constraints(self, mode: OperationMode) -> list[str]:
        """Apply feature constraints for operation mode.

        Time Complexity: O(n) where n is number of features

        Args:
            mode: Operation mode

        Returns:
            List of disabled feature names
        """
        disabled_features = []

        for name, feature in self._features.items():
            should_enable = self._should_feature_be_enabled(feature.priority, mode)

            if should_enable and not feature.enabled:
                # Enable feature
                feature.enabled = True
                if feature.enable_callback:
                    try:
                        feature.enable_callback()
                    except Exception as e:
                        logger.error("Error enabling feature %s: %s", name, e)

                logger.info("Feature enabled: %s", name)

            elif not should_enable and feature.enabled:
                # Disable feature
                feature.enabled = False
                if feature.disable_callback:
                    try:
                        feature.disable_callback()
                    except Exception as e:
                        logger.error("Error disabling feature %s: %s", name, e)

                disabled_features.append(name)
                logger.info("Feature disabled: %s", name)

        return disabled_features

    def _should_feature_be_enabled(
        self,
        priority: FeaturePriority,
        mode: OperationMode
    ) -> bool:
        """Determine if feature should be enabled in given mode.

        Time Complexity: O(1)

        Args:
            priority: Feature priority
            mode: Operation mode

        Returns:
            True if feature should be enabled
        """
        if mode == OperationMode.NORMAL:
            return True

        if mode == OperationMode.DEGRADED:
            # Disable LOW and MEDIUM priority features
            return priority in (FeaturePriority.CRITICAL, FeaturePriority.HIGH)

        if mode == OperationMode.CRITICAL:
            # Only CRITICAL features enabled
            return priority == FeaturePriority.CRITICAL

        return False

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop for automatic degradation."""
        while True:
            try:
                await asyncio.sleep(self.config.check_interval)

                # Get current resource usage
                stats = self.get_resource_stats()
                cpu = stats["cpu_percent"]
                memory = stats["memory_percent"]

                # Check for critical conditions
                if (cpu >= self.config.critical_cpu_threshold or
                    memory >= self.config.critical_memory_threshold):
                    if self._mode != OperationMode.CRITICAL:
                        self._transition_to_mode(
                            OperationMode.CRITICAL,
                            f"Critical resources: CPU={cpu:.1f}%, Memory={memory:.1f}%"
                        )

                # Check for degraded conditions
                elif (cpu >= self.config.cpu_threshold or
                      memory >= self.config.memory_threshold):
                    if self._mode == OperationMode.NORMAL:
                        self._transition_to_mode(
                            OperationMode.DEGRADED,
                            f"High resources: CPU={cpu:.1f}%, Memory={memory:.1f}%"
                        )

                # Check for recovery conditions
                elif self.config.enable_auto_recovery and self._mode != OperationMode.NORMAL:
                    # Check if resources are below recovery threshold
                    recovery_cpu = self.config.cpu_threshold - self.config.recovery_threshold
                    recovery_memory = self.config.memory_threshold - self.config.recovery_threshold

                    if cpu < recovery_cpu and memory < recovery_memory:
                        # Check minimum degraded duration
                        if self._degraded_since is not None:
                            duration = time.time() - self._degraded_since
                            if duration >= self.config.min_degraded_duration:
                                self._transition_to_mode(
                                    OperationMode.NORMAL,
                                    f"Resources recovered: CPU={cpu:.1f}%, Memory={memory:.1f}%"
                                )

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Error in monitoring loop: %s", e)

    def _add_event(self, event: DegradationEvent) -> None:
        """Add event to history with size limit.

        Time Complexity: O(1) amortized

        Args:
            event: Degradation event
        """
        self._event_history.append(event)

        # Trim history if too large
        if len(self._event_history) > self._max_history_size:
            self._event_history = self._event_history[-self._max_history_size:]

    @staticmethod
    def _validate_config(config: DegradationConfig) -> None:
        """Validate configuration parameters.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If any parameter is invalid
        """
        if not 0 < config.cpu_threshold <= 100:
            raise ValueError(f"Invalid cpu_threshold: {config.cpu_threshold}")

        if not 0 < config.memory_threshold <= 100:
            raise ValueError(f"Invalid memory_threshold: {config.memory_threshold}")

        if not 0 < config.disk_threshold <= 100:
            raise ValueError(f"Invalid disk_threshold: {config.disk_threshold}")

        if config.critical_cpu_threshold <= config.cpu_threshold:
            raise ValueError(
                f"critical_cpu_threshold ({config.critical_cpu_threshold}) must be > "
                f"cpu_threshold ({config.cpu_threshold})"
            )

        if config.critical_memory_threshold <= config.memory_threshold:
            raise ValueError(
                f"critical_memory_threshold ({config.critical_memory_threshold}) must be > "
                f"memory_threshold ({config.memory_threshold})"
            )

        if config.check_interval <= 0:
            raise ValueError(f"Invalid check_interval: {config.check_interval}")

        if not 0 <= config.recovery_threshold < config.cpu_threshold:
            raise ValueError(f"Invalid recovery_threshold: {config.recovery_threshold}")

        if config.min_degraded_duration < 0:
            raise ValueError(f"Invalid min_degraded_duration: {config.min_degraded_duration}")
