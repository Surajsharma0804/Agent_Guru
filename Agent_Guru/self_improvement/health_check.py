"""
Health check endpoints for self-improvement engine.

Provides monitoring and diagnostic information for production deployment.
"""

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import psutil


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    status: HealthStatus
    message: str
    details: dict[str, Any]
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class HealthChecker:
    """
    Health checker for self-improvement engine.

    Monitors system health and provides diagnostic information.
    """

    def __init__(self, storage_path: str, config: Optional[Any] = None):
        """
        Initialize health checker.

        Args:
            storage_path: Path to SQLite database
            config: Optional deployment configuration
        """
        self.storage_path = storage_path
        self.config = config

    def check_health(self) -> HealthCheckResult:
        """
        Perform comprehensive health check.

        Returns:
            HealthCheckResult with overall system health
        """
        checks = {
            "database": self._check_database(),
            "memory": self._check_memory(),
            "disk": self._check_disk(),
            "performance": self._check_performance(),
            "learning": self._check_learning(),
        }

        # Determine overall status
        if any(c.status == HealthStatus.UNHEALTHY for c in checks.values()):
            status = HealthStatus.UNHEALTHY
            message = "System is unhealthy"
        elif any(c.status == HealthStatus.DEGRADED for c in checks.values()):
            status = HealthStatus.DEGRADED
            message = "System is degraded"
        else:
            status = HealthStatus.HEALTHY
            message = "System is healthy"

        return HealthCheckResult(
            status=status,
            message=message,
            details={name: check.to_dict() for name, check in checks.items()},
            timestamp=datetime.now()
        )

    def _check_database(self) -> HealthCheckResult:
        """Check database health."""
        try:
            # Check if database exists
            if not os.path.exists(self.storage_path):
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="Database file not found",
                    details={"path": self.storage_path},
                    timestamp=datetime.now()
                )

            # Check database size
            db_size_mb = os.path.getsize(self.storage_path) / (1024 * 1024)
            max_size_mb = self.config.max_database_size_mb if self.config else 1000

            if db_size_mb > max_size_mb:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    message=f"Database size ({db_size_mb:.1f}MB) exceeds limit ({max_size_mb}MB)",
                    details={"size_mb": db_size_mb, "limit_mb": max_size_mb},
                    timestamp=datetime.now()
                )

            # Check database connectivity
            conn = sqlite3.connect(self.storage_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM task_executions")
            task_count = cursor.fetchone()[0]
            conn.close()

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Database is healthy",
                details={
                    "size_mb": db_size_mb,
                    "task_count": task_count,
                    "path": self.storage_path
                },
                timestamp=datetime.now()
            )

        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now()
            )

    def _check_memory(self) -> HealthCheckResult:
        """Check memory usage."""
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            max_memory_mb = self.config.max_memory_usage_mb if self.config else 500

            if memory_mb > max_memory_mb:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    message=f"Memory usage ({memory_mb:.1f}MB) exceeds limit ({max_memory_mb}MB)",
                    details={"memory_mb": memory_mb, "limit_mb": max_memory_mb},
                    timestamp=datetime.now()
                )

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Memory usage is normal",
                details={"memory_mb": memory_mb, "limit_mb": max_memory_mb},
                timestamp=datetime.now()
            )

        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                message=f"Memory check error: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now()
            )

    def _check_disk(self) -> HealthCheckResult:
        """Check disk space."""
        try:
            disk = psutil.disk_usage(os.path.dirname(self.storage_path) or '.')
            free_gb = disk.free / (1024 * 1024 * 1024)

            if free_gb < 1.0:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Low disk space: {free_gb:.1f}GB free",
                    details={"free_gb": free_gb, "total_gb": disk.total / (1024**3)},
                    timestamp=datetime.now()
                )
            elif free_gb < 5.0:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    message=f"Disk space running low: {free_gb:.1f}GB free",
                    details={"free_gb": free_gb, "total_gb": disk.total / (1024**3)},
                    timestamp=datetime.now()
                )

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Disk space is adequate",
                details={"free_gb": free_gb, "total_gb": disk.total / (1024**3)},
                timestamp=datetime.now()
            )

        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                message=f"Disk check error: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now()
            )

    def _check_performance(self) -> HealthCheckResult:
        """Check performance metrics."""
        try:
            conn = sqlite3.connect(self.storage_path)
            cursor = conn.cursor()

            # Get recent task execution times
            cursor.execute("""
                SELECT AVG(execution_time_ms)
                FROM task_executions
                WHERE timestamp > datetime('now', '-1 hour')
            """)
            avg_time = cursor.fetchone()[0]

            # Get success rate
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
                FROM task_executions
                WHERE timestamp > datetime('now', '-1 hour')
            """)
            success_rate = cursor.fetchone()[0]

            conn.close()

            if avg_time is None or success_rate is None:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    message="Insufficient data for performance check",
                    details={"avg_time_ms": None, "success_rate": None},
                    timestamp=datetime.now()
                )

            min_success_rate = self.config.min_success_rate * 100 if self.config else 50.0

            if success_rate < min_success_rate:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    message=f"Success rate ({success_rate:.1f}%) below threshold ({min_success_rate}%)",
                    details={"avg_time_ms": avg_time, "success_rate": success_rate},
                    timestamp=datetime.now()
                )

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Performance is good",
                details={"avg_time_ms": avg_time, "success_rate": success_rate},
                timestamp=datetime.now()
            )

        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                message=f"Performance check error: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now()
            )

    def _check_learning(self) -> HealthCheckResult:
        """Check learning progress."""
        try:
            conn = sqlite3.connect(self.storage_path)
            cursor = conn.cursor()

            # Get total task count
            cursor.execute("SELECT COUNT(*) FROM task_executions")
            total_tasks = cursor.fetchone()[0]

            # Get recent improvement
            cursor.execute("""
                SELECT relative_improvement
                FROM improvement_reports
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            result = cursor.fetchone()
            recent_improvement = result[0] if result else None

            conn.close()

            if total_tasks < 100:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    message=f"Learning in progress ({total_tasks}/100 tasks)",
                    details={"total_tasks": total_tasks, "improvement": None},
                    timestamp=datetime.now()
                )

            if recent_improvement is None:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    message="No improvement data available",
                    details={"total_tasks": total_tasks, "improvement": None},
                    timestamp=datetime.now()
                )

            threshold = self.config.improvement_threshold if self.config else 0.15

            if recent_improvement < threshold:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    message=f"Improvement ({recent_improvement:.1%}) below threshold ({threshold:.1%})",
                    details={"total_tasks": total_tasks, "improvement": recent_improvement},
                    timestamp=datetime.now()
                )

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message=f"Learning is effective ({recent_improvement:.1%} improvement)",
                details={"total_tasks": total_tasks, "improvement": recent_improvement},
                timestamp=datetime.now()
            )

        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                message=f"Learning check error: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now()
            )

    def get_metrics(self) -> dict[str, Any]:
        """
        Get current metrics for monitoring.

        Returns:
            Dictionary with key metrics
        """
        try:
            conn = sqlite3.connect(self.storage_path)
            cursor = conn.cursor()

            # Total tasks
            cursor.execute("SELECT COUNT(*) FROM task_executions")
            total_tasks = cursor.fetchone()[0]

            # Success rate (last 100 tasks)
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
                FROM (
                    SELECT success FROM task_executions
                    ORDER BY timestamp DESC
                    LIMIT 100
                )
            """)
            success_rate = cursor.fetchone()[0] or 0.0

            # Average execution time (last 100 tasks)
            cursor.execute("""
                SELECT AVG(execution_time_ms)
                FROM (
                    SELECT execution_time_ms FROM task_executions
                    ORDER BY timestamp DESC
                    LIMIT 100
                )
            """)
            avg_time = cursor.fetchone()[0] or 0.0

            # Failure counts by type
            cursor.execute("""
                SELECT failure_type, COUNT(*)
                FROM failures
                GROUP BY failure_type
            """)
            failure_counts = dict(cursor.fetchall())

            # Strategy performance
            cursor.execute("""
                SELECT strategy_id, success_rate, total_executions
                FROM strategies
                ORDER BY success_rate DESC
                LIMIT 5
            """)
            top_strategies = [
                {"strategy": row[0], "success_rate": row[1], "executions": row[2]}
                for row in cursor.fetchall()
            ]

            conn.close()

            return {
                "total_tasks": total_tasks,
                "success_rate": success_rate,
                "avg_execution_time_ms": avg_time,
                "failure_counts": failure_counts,
                "top_strategies": top_strategies,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
