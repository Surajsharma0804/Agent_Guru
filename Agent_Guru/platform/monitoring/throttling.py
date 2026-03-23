"""
Module: agent_guru.platform.monitoring.throttling
Purpose: Automatic operation throttling based on resource constraints

This module implements automatic throttling with:
- Resource constraint detection
- Operation priority-based throttling
- Graceful degradation strategies
- Automatic recovery when resources become available
- Minimal overhead (<5ms per operation check)

Performance Requirements:
- Time Complexity: O(1) per throttle check
- Space Complexity: O(1) for throttle state
- Check Overhead: <5ms per operation
- Recovery Time: <1s after resources available

Design Decisions:
- Use token bucket algorithm for rate limiting (O(1) operations)
- Use priority queues for operation scheduling
- Use exponential backoff for recovery
- Preallocate data structures (minimize GC pressure)
- Thread-safe for concurrent access

Author: Agent Guru Team
Date: 2026-02-25
Version: 1.0.0
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from .resource_monitor import ResourceMonitor, ResourceSnapshot, ResourceType

# Configure logging
logger = logging.getLogger(__name__)


class OperationPriority(Enum):
    """Priority levels for operations."""
    CRITICAL = 1  # Never throttle (system critical)
    HIGH = 2  # Throttle only under severe constraints
    MEDIUM = 3  # Throttle under moderate constraints
    LOW = 4  # Throttle aggressively


class ThrottleLevel(Enum):
    """Throttle levels for graceful degradation."""
    NONE = 0  # No throttling
    LIGHT = 1  # 25% reduction
    MODERATE = 2  # 50% reduction
    HEAVY = 3  # 75% reduction
    SEVERE = 4  # 90% reduction


class ThrottleReason(Enum):
    """Reasons for throttling."""
    CPU_CONSTRAINT = "cpu_constraint"
    MEMORY_CONSTRAINT = "memory_constraint"
    DISK_CONSTRAINT = "disk_constraint"
    GPU_CONSTRAINT = "gpu_constraint"
    NETWORK_CONSTRAINT = "network_constraint"
    MULTIPLE_CONSTRAINTS = "multiple_constraints"


@dataclass
class ThrottleDecision:
    """Decision about whether to throttle an operation."""
    should_throttle: bool
    throttle_level: ThrottleLevel
    delay_seconds: float  # Suggested delay before retry
    reason: Optional[ThrottleReason]
    constrained_resources: list[ResourceType]
    message: str
    timestamp: datetime


@dataclass
class ThrottleConfig:
    """Configuration for automatic throttling."""
    # Resource thresholds for throttling (percentage)
    cpu_light_threshold: float = 70.0  # Start light throttling
    cpu_moderate_threshold: float = 80.0
    cpu_heavy_threshold: float = 90.0
    cpu_severe_threshold: float = 95.0

    memory_light_threshold: float = 70.0
    memory_moderate_threshold: float = 80.0
    memory_heavy_threshold: float = 90.0
    memory_severe_threshold: float = 95.0

    disk_light_threshold: float = 80.0  # % used
    disk_moderate_threshold: float = 90.0
    disk_heavy_threshold: float = 95.0
    disk_severe_threshold: float = 98.0

    # Throttle delays (seconds)
    light_delay: float = 0.1
    moderate_delay: float = 0.5
    heavy_delay: float = 2.0
    severe_delay: float = 5.0

    # Recovery settings
    recovery_check_interval: float = 5.0  # Check every 5 seconds
    recovery_threshold_buffer: float = 5.0  # % below threshold to recover

    # Token bucket settings (for rate limiting)
    token_bucket_capacity: int = 100  # Max tokens
    token_refill_rate: float = 10.0  # Tokens per second

    # Operation priorities
    enable_priority_based_throttling: bool = True

    # Graceful degradation
    enable_feature_disabling: bool = True
    non_critical_features: set[str] = field(default_factory=lambda: {
        "background_sync",
        "analytics",
        "telemetry",
        "auto_update_check"
    })


@dataclass
class ThrottleState:
    """Current throttling state."""
    active: bool
    level: ThrottleLevel
    reasons: list[ThrottleReason]
    constrained_resources: list[ResourceType]
    started_at: datetime
    operations_throttled: int
    operations_allowed: int
    last_check: datetime


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: int
    tokens: float
    refill_rate: float  # Tokens per second
    last_refill: float  # Timestamp

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.

        Time Complexity: O(1)

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)

        self.last_refill = now


class AutomaticThrottler:
    """
    Automatic operation throttling based on resource constraints.

    Monitors system resources and automatically throttles operations
    to prevent resource exhaustion. Supports:
    - Priority-based throttling
    - Graceful degradation
    - Automatic recovery
    - Token bucket rate limiting

    Time Complexity: O(1) per throttle check
    Space Complexity: O(1) for throttle state

    Example:
        >>> monitor = ResourceMonitor()
        >>> monitor.start_monitoring()
        >>>
        >>> config = ThrottleConfig()
        >>> throttler = AutomaticThrottler(monitor, config)
        >>> throttler.start()
        >>>
        >>> # Check if operation should be throttled
        >>> decision = throttler.should_throttle(
        ...     operation_name="process_data",
        ...     priority=OperationPriority.MEDIUM
        ... )
        >>>
        >>> if decision.should_throttle:
        ...     print(f"Throttling: {decision.message}")
        ...     time.sleep(decision.delay_seconds)
        >>> else:
        ...     # Proceed with operation
        ...     process_data()
        >>>
        >>> throttler.stop()
    """

    def __init__(
        self,
        resource_monitor: ResourceMonitor,
        config: Optional[ThrottleConfig] = None
    ):
        """
        Initialize automatic throttler.

        Args:
            resource_monitor: Resource monitor instance
            config: Throttle configuration (uses defaults if None)
        """
        self.monitor = resource_monitor
        self.config = config or ThrottleConfig()

        # Throttle state
        self._state = ThrottleState(
            active=False,
            level=ThrottleLevel.NONE,
            reasons=[],
            constrained_resources=[],
            started_at=datetime.now(),
            operations_throttled=0,
            operations_allowed=0,
            last_check=datetime.now()
        )

        # Token buckets per priority level
        self._token_buckets: dict[OperationPriority, TokenBucket] = {
            OperationPriority.CRITICAL: TokenBucket(
                capacity=self.config.token_bucket_capacity,
                tokens=self.config.token_bucket_capacity,
                refill_rate=self.config.token_refill_rate,
                last_refill=time.time()
            ),
            OperationPriority.HIGH: TokenBucket(
                capacity=self.config.token_bucket_capacity,
                tokens=self.config.token_bucket_capacity,
                refill_rate=self.config.token_refill_rate * 0.75,
                last_refill=time.time()
            ),
            OperationPriority.MEDIUM: TokenBucket(
                capacity=self.config.token_bucket_capacity,
                tokens=self.config.token_bucket_capacity,
                refill_rate=self.config.token_refill_rate * 0.5,
                last_refill=time.time()
            ),
            OperationPriority.LOW: TokenBucket(
                capacity=self.config.token_bucket_capacity,
                tokens=self.config.token_bucket_capacity,
                refill_rate=self.config.token_refill_rate * 0.25,
                last_refill=time.time()
            )
        }

        # Disabled features (for graceful degradation)
        self._disabled_features: set[str] = set()

        # Recovery monitoring
        self._recovery_thread: Optional[threading.Thread] = None
        self._running = False

        # Thread safety
        self._lock = threading.Lock()

        # Throttle history (for analysis)
        self._throttle_history: deque[ThrottleDecision] = deque(maxlen=1000)

    def start(self) -> None:
        """Start automatic throttling and recovery monitoring."""
        if self._running:
            return

        self._running = True
        self._recovery_thread = threading.Thread(
            target=self._recovery_loop,
            daemon=True,
            name="ThrottleRecovery"
        )
        self._recovery_thread.start()

        logger.info("Automatic throttler started")

    def stop(self) -> None:
        """Stop automatic throttling."""
        self._running = False
        if self._recovery_thread:
            self._recovery_thread.join(timeout=5.0)
            self._recovery_thread = None

        logger.info("Automatic throttler stopped")

    def should_throttle(
        self,
        operation_name: str,
        priority: OperationPriority = OperationPriority.MEDIUM,
        resource_types: Optional[list[ResourceType]] = None
    ) -> ThrottleDecision:
        """
        Check if operation should be throttled.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            operation_name: Name of operation to check
            priority: Operation priority level
            resource_types: Specific resources used (None = all)

        Returns:
            Throttle decision with recommendation
        """
        start_time = time.time()

        with self._lock:
            # Critical operations are never throttled
            if priority == OperationPriority.CRITICAL:
                self._state.operations_allowed += 1
                decision = ThrottleDecision(
                    should_throttle=False,
                    throttle_level=ThrottleLevel.NONE,
                    delay_seconds=0.0,
                    reason=None,
                    constrained_resources=[],
                    message="Critical operation - no throttling",
                    timestamp=datetime.now()
                )
                self._throttle_history.append(decision)
                return decision

            # Get current resource usage
            snapshot = self.monitor.get_current_usage()

            # Detect resource constraints
            throttle_level, constrained_resources, reasons = self._detect_constraints(
                snapshot,
                resource_types
            )

            # Check if throttling needed based on priority
            should_throttle = self._should_throttle_for_priority(
                priority,
                throttle_level
            )

            # Check token bucket (only if not already throttled)
            if not should_throttle and self.config.enable_priority_based_throttling:
                bucket = self._token_buckets[priority]
                if not bucket.consume():
                    # No tokens available, throttle even if resources OK
                    should_throttle = True
                    throttle_level = ThrottleLevel.LIGHT

            # Update state
            self._state.last_check = datetime.now()

            if should_throttle:
                self._state.operations_throttled += 1

                # Update throttle state if not already active
                if not self._state.active:
                    self._state.active = True
                    self._state.level = throttle_level
                    self._state.reasons = reasons
                    self._state.constrained_resources = constrained_resources
                    self._state.started_at = datetime.now()

                    # Disable non-critical features if configured
                    if self.config.enable_feature_disabling:
                        self._disable_non_critical_features()

                # Calculate delay
                delay = self._calculate_delay(throttle_level)

                # Determine reason
                if len(reasons) > 1:
                    reason = ThrottleReason.MULTIPLE_CONSTRAINTS
                elif reasons:
                    reason = reasons[0]
                else:
                    reason = None

                decision = ThrottleDecision(
                    should_throttle=True,
                    throttle_level=throttle_level,
                    delay_seconds=delay,
                    reason=reason,
                    constrained_resources=constrained_resources,
                    message=self._generate_throttle_message(
                        operation_name,
                        throttle_level,
                        constrained_resources
                    ),
                    timestamp=datetime.now()
                )
            else:
                self._state.operations_allowed += 1

                decision = ThrottleDecision(
                    should_throttle=False,
                    throttle_level=ThrottleLevel.NONE,
                    delay_seconds=0.0,
                    reason=None,
                    constrained_resources=[],
                    message=f"Operation '{operation_name}' allowed",
                    timestamp=datetime.now()
                )

            # Store in history
            self._throttle_history.append(decision)

            # Check overhead
            elapsed = (time.time() - start_time) * 1000  # Convert to ms
            if elapsed > 5.0:
                logger.warning(
                    f"Throttle check took {elapsed:.2f}ms (target: <5ms)"
                )

            return decision

    def get_throttle_state(self) -> ThrottleState:
        """
        Get current throttle state.

        Returns:
            Current throttle state
        """
        with self._lock:
            return ThrottleState(
                active=self._state.active,
                level=self._state.level,
                reasons=self._state.reasons.copy(),
                constrained_resources=self._state.constrained_resources.copy(),
                started_at=self._state.started_at,
                operations_throttled=self._state.operations_throttled,
                operations_allowed=self._state.operations_allowed,
                last_check=self._state.last_check
            )

    def get_throttle_history(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> list[ThrottleDecision]:
        """
        Get throttle decision history.

        Args:
            start_time: Filter decisions after this time
            end_time: Filter decisions before this time

        Returns:
            List of throttle decisions
        """
        with self._lock:
            decisions = list(self._throttle_history)

        if start_time:
            decisions = [d for d in decisions if d.timestamp >= start_time]

        if end_time:
            decisions = [d for d in decisions if d.timestamp <= end_time]

        return decisions

    def get_disabled_features(self) -> set[str]:
        """
        Get currently disabled features.

        Returns:
            Set of disabled feature names
        """
        with self._lock:
            return self._disabled_features.copy()

    def is_feature_enabled(self, feature_name: str) -> bool:
        """
        Check if feature is currently enabled.

        Args:
            feature_name: Name of feature to check

        Returns:
            True if feature is enabled, False if disabled
        """
        with self._lock:
            return feature_name not in self._disabled_features

    def force_recovery(self) -> None:
        """Force immediate recovery from throttling."""
        with self._lock:
            self._recover()
            logger.info("Forced recovery from throttling")

    def _detect_constraints(
        self,
        snapshot: ResourceSnapshot,
        resource_types: Optional[list[ResourceType]] = None
    ) -> tuple[ThrottleLevel, list[ResourceType], list[ThrottleReason]]:
        """
        Detect resource constraints and determine throttle level.

        Time Complexity: O(1)

        Args:
            snapshot: Current resource snapshot
            resource_types: Specific resources to check (None = all)

        Returns:
            Tuple of (throttle_level, constrained_resources, reasons)
        """
        max_level = ThrottleLevel.NONE
        constrained = []
        reasons = []

        # Check CPU
        if resource_types is None or ResourceType.CPU in resource_types:
            cpu_level = self._get_throttle_level_for_value(
                snapshot.cpu_percent,
                self.config.cpu_light_threshold,
                self.config.cpu_moderate_threshold,
                self.config.cpu_heavy_threshold,
                self.config.cpu_severe_threshold
            )

            if cpu_level != ThrottleLevel.NONE:
                max_level = max(max_level, cpu_level, key=lambda x: x.value)
                constrained.append(ResourceType.CPU)
                reasons.append(ThrottleReason.CPU_CONSTRAINT)

        # Check memory
        if resource_types is None or ResourceType.MEMORY in resource_types:
            memory_level = self._get_throttle_level_for_value(
                snapshot.memory_percent,
                self.config.memory_light_threshold,
                self.config.memory_moderate_threshold,
                self.config.memory_heavy_threshold,
                self.config.memory_severe_threshold
            )

            if memory_level != ThrottleLevel.NONE:
                max_level = max(max_level, memory_level, key=lambda x: x.value)
                constrained.append(ResourceType.MEMORY)
                reasons.append(ThrottleReason.MEMORY_CONSTRAINT)

        # Check disk
        if resource_types is None or ResourceType.DISK in resource_types:
            # Check root partition
            disk_percent = 0.0
            if "/" in snapshot.disk_usage:
                disk_percent = snapshot.disk_usage["/"].percent
            elif "C:\\" in snapshot.disk_usage:
                disk_percent = snapshot.disk_usage["C:\\"].percent

            disk_level = self._get_throttle_level_for_value(
                disk_percent,
                self.config.disk_light_threshold,
                self.config.disk_moderate_threshold,
                self.config.disk_heavy_threshold,
                self.config.disk_severe_threshold
            )

            if disk_level != ThrottleLevel.NONE:
                max_level = max(max_level, disk_level, key=lambda x: x.value)
                constrained.append(ResourceType.DISK)
                reasons.append(ThrottleReason.DISK_CONSTRAINT)

        return max_level, constrained, reasons

    def _get_throttle_level_for_value(
        self,
        value: float,
        light_threshold: float,
        moderate_threshold: float,
        heavy_threshold: float,
        severe_threshold: float
    ) -> ThrottleLevel:
        """
        Determine throttle level based on value and thresholds.

        Args:
            value: Current value
            light_threshold: Threshold for light throttling
            moderate_threshold: Threshold for moderate throttling
            heavy_threshold: Threshold for heavy throttling
            severe_threshold: Threshold for severe throttling

        Returns:
            Appropriate throttle level
        """
        if value >= severe_threshold:
            return ThrottleLevel.SEVERE
        elif value >= heavy_threshold:
            return ThrottleLevel.HEAVY
        elif value >= moderate_threshold:
            return ThrottleLevel.MODERATE
        elif value >= light_threshold:
            return ThrottleLevel.LIGHT
        else:
            return ThrottleLevel.NONE

    def _should_throttle_for_priority(
        self,
        priority: OperationPriority,
        throttle_level: ThrottleLevel
    ) -> bool:
        """
        Determine if operation should be throttled based on priority.

        Args:
            priority: Operation priority
            throttle_level: Current throttle level

        Returns:
            True if operation should be throttled
        """
        if throttle_level == ThrottleLevel.NONE:
            return False

        # Critical operations never throttled
        if priority == OperationPriority.CRITICAL:
            return False

        # High priority only throttled under severe constraints
        if priority == OperationPriority.HIGH:
            return throttle_level == ThrottleLevel.SEVERE

        # Medium priority throttled under heavy or severe constraints
        if priority == OperationPriority.MEDIUM:
            return throttle_level.value >= ThrottleLevel.HEAVY.value

        # Low priority throttled under any constraint
        return True

    def _calculate_delay(self, throttle_level: ThrottleLevel) -> float:
        """
        Calculate delay based on throttle level.

        Args:
            throttle_level: Current throttle level

        Returns:
            Delay in seconds
        """
        if throttle_level == ThrottleLevel.LIGHT:
            return self.config.light_delay
        elif throttle_level == ThrottleLevel.MODERATE:
            return self.config.moderate_delay
        elif throttle_level == ThrottleLevel.HEAVY:
            return self.config.heavy_delay
        elif throttle_level == ThrottleLevel.SEVERE:
            return self.config.severe_delay
        else:
            return 0.0

    def _generate_throttle_message(
        self,
        operation_name: str,
        throttle_level: ThrottleLevel,
        constrained_resources: list[ResourceType]
    ) -> str:
        """Generate human-readable throttle message."""
        resource_names = ", ".join(r.value.upper() for r in constrained_resources)

        return (
            f"Operation '{operation_name}' throttled ({throttle_level.name}) "
            f"due to constrained resources: {resource_names}"
        )

    def _disable_non_critical_features(self) -> None:
        """Disable non-critical features for graceful degradation."""
        for feature in self.config.non_critical_features:
            self._disabled_features.add(feature)

        if self._disabled_features:
            logger.info(
                f"Disabled non-critical features: {', '.join(self._disabled_features)}"
            )

    def _enable_all_features(self) -> None:
        """Re-enable all features after recovery."""
        if self._disabled_features:
            logger.info(
                f"Re-enabled features: {', '.join(self._disabled_features)}"
            )
            self._disabled_features.clear()

    def _recovery_loop(self) -> None:
        """Background loop to check for recovery conditions."""
        while self._running:
            try:
                time.sleep(self.config.recovery_check_interval)

                with self._lock:
                    if self._state.active:
                        self._check_recovery()

            except Exception as e:
                logger.error(f"Error in recovery loop: {e}", exc_info=True)

    def _check_recovery(self) -> None:
        """Check if resources have recovered and throttling can be lifted."""
        snapshot = self.monitor.get_current_usage()

        # Check if all constrained resources are now below threshold
        can_recover = True

        for resource_type in self._state.constrained_resources:
            if resource_type == ResourceType.CPU:
                threshold = self.config.cpu_light_threshold - self.config.recovery_threshold_buffer
                if snapshot.cpu_percent > threshold:
                    can_recover = False
                    break

            elif resource_type == ResourceType.MEMORY:
                threshold = self.config.memory_light_threshold - self.config.recovery_threshold_buffer
                if snapshot.memory_percent > threshold:
                    can_recover = False
                    break

            elif resource_type == ResourceType.DISK:
                threshold = self.config.disk_light_threshold - self.config.recovery_threshold_buffer
                disk_percent = 0.0
                if "/" in snapshot.disk_usage:
                    disk_percent = snapshot.disk_usage["/"].percent
                elif "C:\\" in snapshot.disk_usage:
                    disk_percent = snapshot.disk_usage["C:\\"].percent

                if disk_percent > threshold:
                    can_recover = False
                    break

        if can_recover:
            self._recover()

    def _recover(self) -> None:
        """Recover from throttling state."""
        duration = datetime.now() - self._state.started_at

        logger.info(
            f"Recovering from throttling after {duration.total_seconds():.1f}s. "
            f"Throttled: {self._state.operations_throttled}, "
            f"Allowed: {self._state.operations_allowed}"
        )

        # Reset state
        self._state.active = False
        self._state.level = ThrottleLevel.NONE
        self._state.reasons = []
        self._state.constrained_resources = []

        # Re-enable features
        self._enable_all_features()

        # Refill token buckets
        for bucket in self._token_buckets.values():
            bucket.tokens = bucket.capacity
