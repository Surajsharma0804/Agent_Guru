"""Deployment configuration for self-improvement engine.

This module provides configuration management for deploying the self-improvement
engine in production environments.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DeploymentConfig:
    """Configuration for self-improvement engine deployment."""

    # Storage configuration
    storage_path: str = "data/self_improvement/learning.db"
    backup_path: str = "data/self_improvement/backups"
    max_backup_age_days: int = 30

    # Git integration
    git_enabled: bool = True
    git_repo_path: str = "."
    git_auto_commit: bool = True
    git_commit_interval: int = 1  # Commit after every N tasks

    # Learning parameters
    improvement_threshold: float = 0.15  # 15% minimum improvement
    measurement_window: int = 100  # Measure every 100 tasks
    exploration_rate: float = 0.1  # 10% exploration (epsilon-greedy)

    # Performance thresholds
    max_execution_overhead_percent: float = 10.0  # Max 10% overhead
    min_success_rate: float = 0.5  # Alert if below 50%
    max_degradation_percent: float = 20.0  # Alert if 20% degradation

    # Monitoring
    health_check_interval_seconds: int = 60
    metrics_retention_days: int = 90
    alert_on_insufficient_improvement: bool = True

    # Stability
    rate_limit_prompt_evolution: int = 10  # Max 10 prompt changes per hour
    rollback_on_degradation: bool = True
    ensemble_voting_threshold: int = 3  # Use ensemble for critical tasks

    # Resource limits
    max_database_size_mb: int = 1000  # 1GB max
    max_memory_usage_mb: int = 500  # 500MB max
    max_pattern_cache_size: int = 10000

    # Environment-specific overrides
    environment: str = "production"  # production, staging, development
    debug_mode: bool = False
    test_mode: bool = False  # Disables Git commits

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.improvement_threshold < 0 or self.improvement_threshold > 1:
            msg = "improvement_threshold must be between 0 and 1"
            raise ValueError(msg)

        if self.measurement_window < 10:  # noqa: PLR2004 - Threshold

            msg = "measurement_window must be at least 10"
            raise ValueError(msg)

        if self.exploration_rate < 0 or self.exploration_rate > 1:
            msg = "exploration_rate must be between 0 and 1"
            raise ValueError(msg)

        # Create directories if they don't exist
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.backup_path).mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_environment(cls) -> "DeploymentConfig":
        """Create configuration from environment variables."""
        return cls(
            storage_path=os.getenv(
                "SELF_IMPROVEMENT_STORAGE_PATH",
                "data/self_improvement/learning.db",
            ),
            backup_path=os.getenv("SELF_IMPROVEMENT_BACKUP_PATH", "data/self_improvement/backups"),
            git_enabled=os.getenv("SELF_IMPROVEMENT_GIT_ENABLED", "true").lower() == "true",
            git_repo_path=os.getenv("SELF_IMPROVEMENT_GIT_REPO", "."),
            improvement_threshold=float(os.getenv("SELF_IMPROVEMENT_THRESHOLD", "0.15")),
            measurement_window=int(os.getenv("SELF_IMPROVEMENT_WINDOW", "100")),
            environment=os.getenv("ENVIRONMENT", "production"),
            debug_mode=os.getenv("DEBUG", "false").lower() == "true",
            test_mode=os.getenv("TEST_MODE", "false").lower() == "true",
        )

    @classmethod
    def for_production(cls) -> "DeploymentConfig":
        """Create production configuration."""
        return cls(
            environment="production",
            debug_mode=False,
            test_mode=False,
            git_enabled=True,
            git_auto_commit=True,
            alert_on_insufficient_improvement=True,
            rollback_on_degradation=True,
        )

    @classmethod
    def for_staging(cls) -> "DeploymentConfig":
        """Create staging configuration."""
        return cls(
            environment="staging",
            debug_mode=True,
            test_mode=False,
            git_enabled=True,
            git_auto_commit=False,  # Manual commits in staging
            alert_on_insufficient_improvement=True,
            rollback_on_degradation=True,
        )

    @classmethod
    def for_development(cls) -> "DeploymentConfig":
        """Create development configuration."""
        return cls(
            environment="development",
            debug_mode=True,
            test_mode=True,  # No Git commits in dev
            git_enabled=False,
            git_auto_commit=False,
            alert_on_insufficient_improvement=False,
            rollback_on_degradation=False,
            storage_path="data/dev/learning.db",
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "storage_path": self.storage_path,
            "backup_path": self.backup_path,
            "max_backup_age_days": self.max_backup_age_days,
            "git_enabled": self.git_enabled,
            "git_repo_path": self.git_repo_path,
            "git_auto_commit": self.git_auto_commit,
            "git_commit_interval": self.git_commit_interval,
            "improvement_threshold": self.improvement_threshold,
            "measurement_window": self.measurement_window,
            "exploration_rate": self.exploration_rate,
            "max_execution_overhead_percent": self.max_execution_overhead_percent,
            "min_success_rate": self.min_success_rate,
            "max_degradation_percent": self.max_degradation_percent,
            "health_check_interval_seconds": self.health_check_interval_seconds,
            "metrics_retention_days": self.metrics_retention_days,
            "alert_on_insufficient_improvement": self.alert_on_insufficient_improvement,
            "rate_limit_prompt_evolution": self.rate_limit_prompt_evolution,
            "rollback_on_degradation": self.rollback_on_degradation,
            "ensemble_voting_threshold": self.ensemble_voting_threshold,
            "max_database_size_mb": self.max_database_size_mb,
            "max_memory_usage_mb": self.max_memory_usage_mb,
            "max_pattern_cache_size": self.max_pattern_cache_size,
            "environment": self.environment,
            "debug_mode": self.debug_mode,
            "test_mode": self.test_mode,
        }


# Predefined configurations
PRODUCTION_CONFIG = DeploymentConfig.for_production()
STAGING_CONFIG = DeploymentConfig.for_staging()
DEVELOPMENT_CONFIG = DeploymentConfig.for_development()


def get_config(environment: str | None = None) -> DeploymentConfig:
    """Get deployment configuration for specified environment.

    Args:
        environment: Environment name (production, staging, development)
                    If None, uses ENVIRONMENT env var or defaults to production

    Returns:
        DeploymentConfig instance

    """
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "production")

    environment = environment.lower()

    if environment == "production":
        return PRODUCTION_CONFIG
    if environment == "staging":
        return STAGING_CONFIG
    if environment == "development":
        return DEVELOPMENT_CONFIG
    # Try to load from environment variables
    return DeploymentConfig.from_environment()
