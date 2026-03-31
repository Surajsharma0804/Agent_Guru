"""
Module: Agent_Guru.platform.permissions.quota_manager
Purpose: Operation quota tracking and enforcement system

This module implements comprehensive quota management with:
- Per-operation-type quota tracking
- Per-hour and per-day limits
- Automatic quota reset logic
- Quota exceeded handling
- Thread-safe operations
- Persistent quota storage (optional)

Performance Characteristics:
    - Time Complexity: O(1) for quota checks and updates
    - Space Complexity: O(u * o) where u=users, o=operation types
    - Reset Logic: O(u * o) but runs infrequently (hourly/daily)

Author: Agent Guru Team
Date: 2026-02-26
Version: 1.0.0
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Operation types for quota tracking."""
    FILE_OPERATION = "file_operation"
    COMMAND_EXECUTION = "command_execution"
    NETWORK_REQUEST = "network_request"


@dataclass
class QuotaConfig:
    """
    Quota configuration for an operation type.

    Attributes:
        per_hour: Maximum operations allowed per hour
        per_day: Maximum operations allowed per day
    """
    per_hour: int
    per_day: int

    def __post_init__(self):
        """Validate quota configuration."""
        if self.per_hour <= 0:
            raise ValueError(f"per_hour must be positive, got {self.per_hour}")
        if self.per_day <= 0:
            raise ValueError(f"per_day must be positive, got {self.per_day}")
        if self.per_day < self.per_hour:
            raise ValueError(
                f"per_day ({self.per_day}) must be >= per_hour ({self.per_hour})"
            )


@dataclass
class QuotaStatus:
    """
    Current quota status for an operation type.

    Attributes:
        operation_type: Type of operation
        current_hour: Operations used this hour
        current_day: Operations used today
        limit_hour: Maximum operations per hour
        limit_day: Maximum operations per day
        available: Whether quota is available
        reset_hour_at: When hourly quota resets
        reset_day_at: When daily quota resets
    """
    operation_type: OperationType
    current_hour: int
    current_day: int
    limit_hour: int
    limit_day: int
    available: bool
    reset_hour_at: datetime
    reset_day_at: datetime

    @property
    def hour_remaining(self) -> int:
        """Remaining operations this hour."""
        return max(0, self.limit_hour - self.current_hour)

    @property
    def day_remaining(self) -> int:
        """Remaining operations today."""
        return max(0, self.limit_day - self.current_day)

    @property
    def hour_exceeded(self) -> bool:
        """Check if hourly quota exceeded."""
        return self.current_hour >= self.limit_hour

    @property
    def day_exceeded(self) -> bool:
        """Check if daily quota exceeded."""
        return self.current_day >= self.limit_day

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "operation_type": self.operation_type.value,
            "current_hour": self.current_hour,
            "current_day": self.current_day,
            "limit_hour": self.limit_hour,
            "limit_day": self.limit_day,
            "available": self.available,
            "hour_remaining": self.hour_remaining,
            "day_remaining": self.day_remaining,
            "hour_exceeded": self.hour_exceeded,
            "day_exceeded": self.day_exceeded,
            "reset_hour_at": self.reset_hour_at.isoformat(),
            "reset_day_at": self.reset_day_at.isoformat()
        }


@dataclass
class UserQuotaCounters:
    """
    Quota counters for a single user.

    Tracks hourly and daily usage for each operation type.
    """
    counters: dict[OperationType, dict[str, int]] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize counters for all operation types."""
        for op_type in OperationType:
            if op_type not in self.counters:
                self.counters[op_type] = {"hour": 0, "day": 0}

    def get_hour_count(self, operation_type: OperationType) -> int:
        """Get hourly count for operation type."""
        return self.counters[operation_type]["hour"]

    def get_day_count(self, operation_type: OperationType) -> int:
        """Get daily count for operation type."""
        return self.counters[operation_type]["day"]

    def increment(self, operation_type: OperationType) -> None:
        """Increment counters for operation type."""
        self.counters[operation_type]["hour"] += 1
        self.counters[operation_type]["day"] += 1

    def reset_hour(self) -> None:
        """Reset hourly counters for all operation types."""
        for op_counters in self.counters.values():
            op_counters["hour"] = 0

    def reset_day(self) -> None:
        """Reset daily counters for all operation types."""
        for op_counters in self.counters.values():
            op_counters["hour"] = 0
            op_counters["day"] = 0


class QuotaExceededError(Exception):
    """Raised when operation quota is exceeded."""

    def __init__(self, status: QuotaStatus):
        self.status = status
        if status.hour_exceeded:
            message = (
                f"Hourly quota exceeded for {status.operation_type.value}: "
                f"{status.current_hour}/{status.limit_hour} used. "
                f"Resets at {status.reset_hour_at.strftime('%H:%M:%S')}"
            )
        else:
            message = (
                f"Daily quota exceeded for {status.operation_type.value}: "
                f"{status.current_day}/{status.limit_day} used. "
                f"Resets at {status.reset_day_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        super().__init__(message)


# Backward-compatible alias
QuotaExceededException = QuotaExceededError


class QuotaManager:
    """
    Operation quota manager with automatic reset and enforcement.

    Features:
    - Per-user quota tracking
    - Per-operation-type limits
    - Automatic hourly/daily reset
    - Thread-safe operations
    - Optional persistent storage
    - Quota status reporting

    Time Complexity: O(1) for all operations
    Space Complexity: O(u * o) where u=users, o=operation types

    Example:
        >>> config = {
        ...     OperationType.FILE_OPERATION: QuotaConfig(per_hour=1000, per_day=10000),
        ...     OperationType.COMMAND_EXECUTION: QuotaConfig(per_hour=500, per_day=5000),
        ...     OperationType.NETWORK_REQUEST: QuotaConfig(per_hour=10000, per_day=100000)
        ... }
        >>> manager = QuotaManager(config)
        >>>
        >>> # Check and consume quota
        >>> status = manager.check_and_consume("user123", OperationType.FILE_OPERATION)
        >>> print(f"Available: {status.available}, Remaining: {status.hour_remaining}")
        >>>
        >>> # Get current status without consuming
        >>> status = manager.get_status("user123", OperationType.FILE_OPERATION)
        >>> print(f"Used: {status.current_hour}/{status.limit_hour}")
    """

    def __init__(
        self,
        quota_configs: dict[OperationType, QuotaConfig],
        storage_path: Optional[Path] = None
    ):
        """
        Initialize quota manager.

        Args:
            quota_configs: Quota configuration per operation type
            storage_path: Optional path for persistent storage

        Raises:
            ValueError: If quota_configs is empty or invalid
        """
        if not quota_configs:
            raise ValueError("quota_configs cannot be empty")

        self.quota_configs = quota_configs
        self.storage_path = storage_path
        self._lock = RLock()

        # User quota counters: {user_id: UserQuotaCounters}
        self._user_quotas: dict[str, UserQuotaCounters] = {}

        # Track last reset times
        now = datetime.now()
        self._last_hour_reset = now.replace(minute=0, second=0, microsecond=0)
        self._last_day_reset = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Load persisted quotas if storage path provided
        if self.storage_path:
            self._load_from_storage()

        logger.info(
            f"QuotaManager initialized with {len(quota_configs)} operation types, "
            f"storage: {storage_path is not None}"
        )

    def check_and_consume(
        self,
        user_id: str,
        operation_type: OperationType,
        raise_on_exceeded: bool = False
    ) -> QuotaStatus:
        """
        Check quota availability and consume if available.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            user_id: User identifier
            operation_type: Type of operation
            raise_on_exceeded: If True, raise exception when quota exceeded

        Returns:
            Quota status with availability and remaining counts

        Raises:
            QuotaExceededException: If quota exceeded and raise_on_exceeded=True
        """
        with self._lock:
            # Reset counters if needed
            self._reset_quotas_if_needed()

            # Get or create user counters
            if user_id not in self._user_quotas:
                self._user_quotas[user_id] = UserQuotaCounters()

            user_counters = self._user_quotas[user_id]
            quota_config = self.quota_configs[operation_type]

            # Get current counts
            current_hour = user_counters.get_hour_count(operation_type)
            current_day = user_counters.get_day_count(operation_type)

            # Check availability
            hour_available = current_hour < quota_config.per_hour
            day_available = current_day < quota_config.per_day
            available = hour_available and day_available

            # Increment counters if available
            if available:
                user_counters.increment(operation_type)
                current_hour += 1
                current_day += 1

            # Calculate reset times
            reset_hour_at = self._last_hour_reset + timedelta(hours=1)
            reset_day_at = self._last_day_reset + timedelta(days=1)

            # Create status
            status = QuotaStatus(
                operation_type=operation_type,
                current_hour=current_hour,
                current_day=current_day,
                limit_hour=quota_config.per_hour,
                limit_day=quota_config.per_day,
                available=available,
                reset_hour_at=reset_hour_at,
                reset_day_at=reset_day_at
            )

            # Log and optionally raise exception
            if not available:
                logger.warning(
                    f"Quota exceeded for user={user_id}, operation={operation_type.value}: "
                    f"hour={status.current_hour}/{status.limit_hour}, "
                    f"day={status.current_day}/{status.limit_day}"
                )
                if raise_on_exceeded:
                    raise QuotaExceededException(status)

            # Persist if storage enabled
            if self.storage_path and available:
                self._save_to_storage()

            return status

    def get_status(
        self,
        user_id: str,
        operation_type: OperationType
    ) -> QuotaStatus:
        """
        Get current quota status without consuming.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            user_id: User identifier
            operation_type: Type of operation

        Returns:
            Current quota status
        """
        with self._lock:
            # Reset counters if needed
            self._reset_quotas_if_needed()

            # Get or create user counters
            if user_id not in self._user_quotas:
                self._user_quotas[user_id] = UserQuotaCounters()

            user_counters = self._user_quotas[user_id]
            quota_config = self.quota_configs[operation_type]

            # Get current counts
            current_hour = user_counters.get_hour_count(operation_type)
            current_day = user_counters.get_day_count(operation_type)

            # Check availability
            hour_available = current_hour < quota_config.per_hour
            day_available = current_day < quota_config.per_day
            available = hour_available and day_available

            # Calculate reset times
            reset_hour_at = self._last_hour_reset + timedelta(hours=1)
            reset_day_at = self._last_day_reset + timedelta(days=1)

            return QuotaStatus(
                operation_type=operation_type,
                current_hour=current_hour,
                current_day=current_day,
                limit_hour=quota_config.per_hour,
                limit_day=quota_config.per_day,
                available=available,
                reset_hour_at=reset_hour_at,
                reset_day_at=reset_day_at
            )

    def get_all_statuses(self, user_id: str) -> dict[OperationType, QuotaStatus]:
        """
        Get quota status for all operation types.

        Args:
            user_id: User identifier

        Returns:
            Dictionary mapping operation type to quota status
        """
        with self._lock:
            return {
                op_type: self.get_status(user_id, op_type)
                for op_type in OperationType
            }

    def reset_user_quotas(self, user_id: str) -> None:
        """
        Reset all quotas for a specific user.

        Args:
            user_id: User identifier
        """
        with self._lock:
            if user_id in self._user_quotas:
                self._user_quotas[user_id].reset_day()
                logger.info("Reset all quotas for user: %s", user_id)

                if self.storage_path:
                    self._save_to_storage()

    def _reset_quotas_if_needed(self) -> None:
        """
        Reset quota counters if hour or day has changed.

        Time Complexity: O(u * o) where u=users, o=operation types
        Space Complexity: O(1)
        """
        now = datetime.now()
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        current_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Reset hourly counters
        if current_hour > self._last_hour_reset:
            for user_counters in self._user_quotas.values():
                user_counters.reset_hour()
            self._last_hour_reset = current_hour
            logger.info("Hourly quota counters reset at %s", current_hour)

            if self.storage_path:
                self._save_to_storage()

        # Reset daily counters
        if current_day > self._last_day_reset:
            for user_counters in self._user_quotas.values():
                user_counters.reset_day()
            self._last_day_reset = current_day
            logger.info("Daily quota counters reset at %s", current_day)

            if self.storage_path:
                self._save_to_storage()

    def _save_to_storage(self) -> None:
        """
        Save quota counters to persistent storage.

        Storage format (JSON):
        {
            "last_hour_reset": "2026-02-26T10:00:00",
            "last_day_reset": "2026-02-26T00:00:00",
            "user_quotas": {
                "user123": {
                    "file_operation": {"hour": 50, "day": 500},
                    "command_execution": {"hour": 25, "day": 250},
                    "network_request": {"hour": 1000, "day": 10000}
                }
            }
        }
        """
        if not self.storage_path:
            return

        try:
            data = {
                "last_hour_reset": self._last_hour_reset.isoformat(),
                "last_day_reset": self._last_day_reset.isoformat(),
                "user_quotas": {}
            }

            for user_id, user_counters in self._user_quotas.items():
                data["user_quotas"][user_id] = {
                    op_type.value: counters
                    for op_type, counters in user_counters.counters.items()
                }

            # Write atomically (write to temp file, then rename)
            temp_path = self.storage_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            temp_path.replace(self.storage_path)

            logger.debug("Quota counters saved to %s", self.storage_path)

        except Exception as e:
            logger.error("Failed to save quota counters: %s", e)

    def _load_from_storage(self) -> None:
        """Load quota counters from persistent storage."""
        if not self.storage_path or not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            # Load reset times
            self._last_hour_reset = datetime.fromisoformat(data["last_hour_reset"])
            self._last_day_reset = datetime.fromisoformat(data["last_day_reset"])

            # Load user quotas
            for user_id, user_data in data["user_quotas"].items():
                user_counters = UserQuotaCounters()
                for op_type_str, counters in user_data.items():
                    op_type = OperationType(op_type_str)
                    user_counters.counters[op_type] = counters
                self._user_quotas[user_id] = user_counters

            logger.info(
                f"Quota counters loaded from {self.storage_path}: "
                f"{len(self._user_quotas)} users"
            )

        except Exception as e:
            logger.error("Failed to load quota counters: %s", e)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get quota usage statistics.

        Returns:
            Dictionary with statistics:
            - total_users: Number of users tracked
            - last_hour_reset: Last hourly reset time
            - last_day_reset: Last daily reset time
            - per_operation_stats: Usage stats per operation type
        """
        with self._lock:
            stats = {
                "total_users": len(self._user_quotas),
                "last_hour_reset": self._last_hour_reset.isoformat(),
                "last_day_reset": self._last_day_reset.isoformat(),
                "per_operation_stats": {}
            }

            # Calculate per-operation statistics
            for op_type in OperationType:
                total_hour = sum(
                    user.get_hour_count(op_type)
                    for user in self._user_quotas.values()
                )
                total_day = sum(
                    user.get_day_count(op_type)
                    for user in self._user_quotas.values()
                )

                stats["per_operation_stats"][op_type.value] = {
                    "total_hour": total_hour,
                    "total_day": total_day,
                    "limit_hour": self.quota_configs[op_type].per_hour,
                    "limit_day": self.quota_configs[op_type].per_day
                }

            return stats
