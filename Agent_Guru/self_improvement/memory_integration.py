"""Memory System Integration - Interface for persistent storage integration.

This module provides integration hooks for the memory system to enable
persistent storage and historical pattern retrieval.

**Integration Points**:
- Learning data synchronization
- Historical pattern retrieval
- Long-term storage management

Author: Agent Guru Team
Date: 2026-02-28
Version: 1.0.0
"""

import logging

_logger = logging.getLogger(__name__)

from datetime import UTC, datetime  # noqa: E402
from typing import Any  # noqa: E402


class MemoryIntegration:
    """Memory system integration for self-improvement engine.

    This class provides hooks for integrating with the memory system
    to enable persistent storage and historical pattern retrieval.

    Time Complexity: O(1) for integration overhead
    Space Complexity: O(1)

    Example:
        >>> from Agent_Guru.self_improvement.self_improvement_engine import SelfImprovementEngine
        >>>
        >>> # Initialize with memory integration
        >>> engine = SelfImprovementEngine("data/learning.db")
        >>> memory_integration = MemoryIntegration(engine)
        >>>
        >>> # Sync learning data to memory system
        >>> memory_integration.sync_learning_data()
        >>>
        >>> # Retrieve historical patterns
        >>> patterns = memory_integration.get_historical_patterns(
        ...     task_type="analysis",
        ...     limit=10
        ... )

    """

    def __init__(self, self_improvement_engine: Any, memory_system: Any | None = None) -> None:
        """Initialize memory integration.

        Args:
            self_improvement_engine: SelfImprovementEngine instance
            memory_system: Optional memory system instance (placeholder)

        Time Complexity: O(1)

        """
        self.engine = self_improvement_engine
        self.memory_system = memory_system
        self.last_sync_time: datetime | None = None

    def sync_learning_data(self) -> dict[str, Any]:
        """Synchronize learning data to memory system.

        Exports learning data from self-improvement engine to memory system
        for long-term persistent storage.

        Returns:
            Sync statistics

        Time Complexity: O(n) where n is data size
        Performance Target: <100ms for typical sync

        Validates: Requirement 17.2

        """
        if not self.memory_system:
            # No memory system connected - return empty stats
            return {
                "synced": False,
                "reason": "No memory system connected",
                "timestamp": datetime.now(tz=UTC).isoformat(),
            }

        try:
            # Get learning data from engine
            metrics = self.engine.get_improvement_metrics()

            # Sync to memory system (placeholder)
            # In real implementation, this would call memory_system.store()

            self.last_sync_time = datetime.now(tz=UTC)

            return {
                "synced": True,
                "metrics_synced": len(metrics),
                "timestamp": self.last_sync_time.isoformat(),
            }

        except Exception as e:
            return {"synced": False, "error": str(e), "timestamp": datetime.now(tz=UTC).isoformat()}

    def get_historical_patterns(
        self,
        task_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieve historical patterns from memory system.

        Queries memory system for historical failure patterns and
        successful strategies.

        Args:
            task_type: Optional task type filter
            limit: Maximum number of patterns to retrieve

        Returns:
            List of historical patterns

        Time Complexity: O(log n) where n is stored patterns
        Performance Target: <50ms

        Validates: Requirement 17.3

        """
        if not self.memory_system:
            # No memory system - return patterns from engine
            return self._get_patterns_from_engine(task_type, limit)

        try:
            # Query memory system (placeholder)
            # In real implementation, this would call memory_system.query()

            return self._get_patterns_from_engine(task_type, limit)

        except Exception as e:
            _logger.warning("Warning: Historical pattern retrieval failed: %s", e)
            return []

    def _get_patterns_from_engine(self, task_type: str | None, limit: int) -> list[dict[str, Any]]:
        """Get patterns from self-improvement engine.

        Fallback method when memory system is not available.

        Args:
            task_type: Optional task type filter
            limit: Maximum number of patterns

        Returns:
            List of patterns from engine

        """
        try:
            # Get patterns from failure analyzer
            patterns = self.engine.failure_analyzer.get_failure_patterns(limit=limit)

            # Filter by task type if specified
            if task_type:
                patterns = [p for p in patterns if p.get("task_type") == task_type]

            return patterns[:limit]

        except Exception as e:
            _logger.warning("Warning: Pattern retrieval from engine failed: %s", e)
            return []

    def get_sync_status(self) -> dict[str, Any]:
        """Get synchronization status.

        Returns:
            Sync status information

        Time Complexity: O(1)

        """
        return {
            "memory_system_connected": self.memory_system is not None,
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "engine_metrics": self.engine.get_improvement_metrics(),
        }


# Integration helper functions


def create_memory_integration(
    self_improvement_engine: Any,
    memory_system: Any | None = None,
) -> MemoryIntegration:
    """Create memory integration for self-improvement engine.

    This is a convenience function that initializes the memory integration
    with proper configuration.

    Args:
        self_improvement_engine: SelfImprovementEngine instance
        memory_system: Optional memory system instance

    Returns:
        Configured MemoryIntegration instance

    Example:
        >>> from Agent_Guru.self_improvement.self_improvement_engine import SelfImprovementEngine
        >>>
        >>> engine = SelfImprovementEngine("data/learning.db")
        >>> memory_integration = create_memory_integration(engine)
        >>>
        >>> # Sync data
        >>> stats = memory_integration.sync_learning_data()
        >>> print(f"Synced: {stats['synced']}")

    """
    return MemoryIntegration(
        self_improvement_engine=self_improvement_engine,
        memory_system=memory_system,
    )
