"""
Feature Flags and A/B Testing Framework - Task 48.

Provides feature flag management with gradual rollout and A/B testing
for safe experimentation without full redeployment.

Architecture:
    FeatureFlagManager
        ├── FeatureFlag         - Individual flag with rollout config
        ├── ABTestManager       - A/B experiment tracking
        ├── ExperimentTracker   - Metrics per experiment variant
        └── StatisticalAnalyzer - Significance testing

Rollout Strategy: 1% → 10% → 50% → 100%

Requirements: 13.4
"""

from __future__ import annotations

import hashlib
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class RolloutStrategy(str, Enum):
    """Feature flag rollout strategy."""
    DISABLED = "disabled"       # 0% - feature off
    CANARY = "canary"           # 1% - initial canary
    EARLY_ADOPTERS = "early"    # 10% - early adopters
    MAJORITY = "majority"       # 50% - majority rollout
    FULL = "full"               # 100% - full rollout
    CUSTOM = "custom"           # Custom percentage


@dataclass
class FeatureFlag:
    """
    A feature flag with gradual rollout support.

    Rollout is deterministic per user_id using consistent hashing,
    ensuring the same user always gets the same variant.
    """
    name: str
    description: str
    enabled: bool = False
    rollout_percentage: float = 0.0   # 0.0 to 100.0
    strategy: RolloutStrategy = RolloutStrategy.DISABLED
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_enabled_for(self, user_id: str) -> bool:
        """
        Check if flag is enabled for a specific user.

        Uses consistent hashing for deterministic assignment.
        Time Complexity: O(1)

        Args:
            user_id: User identifier for consistent assignment

        Returns:
            True if flag is enabled for this user
        """
        if not self.enabled:
            return False
        if self.rollout_percentage >= 100.0:
            return True
        if self.rollout_percentage <= 0.0:
            return False

        # Consistent hash: same user always gets same result
        hash_input = f"{self.name}:{user_id}"
        hash_value = int(hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest(), 16)  # noqa: S324
        user_bucket = (hash_value % 10000) / 100.0  # 0.0 to 99.99
        return user_bucket < self.rollout_percentage

    def set_rollout(self, percentage: float) -> None:
        """Set rollout percentage and update strategy."""
        self.rollout_percentage = max(0.0, min(100.0, percentage))
        self.updated_at = datetime.now(tz=timezone.utc)

        if percentage == 0.0:
            self.strategy = RolloutStrategy.DISABLED
        elif percentage <= 1.0:
            self.strategy = RolloutStrategy.CANARY
        elif percentage <= 10.0:
            self.strategy = RolloutStrategy.EARLY_ADOPTERS
        elif percentage <= 50.0:
            self.strategy = RolloutStrategy.MAJORITY
        elif percentage >= 100.0:
            self.strategy = RolloutStrategy.FULL
        else:
            self.strategy = RolloutStrategy.CUSTOM


# ---------------------------------------------------------------------------
# Feature Flag Manager
# ---------------------------------------------------------------------------

class FeatureFlagManager:
    """
    Manages feature flags with gradual rollout.

    Supports:
    - Flag creation and management
    - Gradual rollout (1% → 10% → 50% → 100%)
    - Per-user consistent assignment
    - Flag monitoring

    Time Complexity: O(1) for flag checks
    Space Complexity: O(n) where n is number of flags
    """

    def __init__(self) -> None:
        self._flags: dict[str, FeatureFlag] = {}

    def create_flag(
        self,
        name: str,
        description: str,
        initial_percentage: float = 0.0,
    ) -> FeatureFlag:
        """Create a new feature flag."""
        flag = FeatureFlag(
            name=name,
            description=description,
            enabled=initial_percentage > 0.0,
            rollout_percentage=initial_percentage,
        )
        flag.set_rollout(initial_percentage)
        self._flags[name] = flag
        return flag

    def get_flag(self, name: str) -> Optional[FeatureFlag]:
        """Get a feature flag by name."""
        return self._flags.get(name)

    def is_enabled(self, name: str, user_id: str) -> bool:
        """
        Check if a feature is enabled for a user.

        Time Complexity: O(1)

        Args:
            name: Feature flag name
            user_id: User identifier

        Returns:
            True if feature is enabled for this user
        """
        flag = self._flags.get(name)
        if flag is None:
            return False
        return flag.is_enabled_for(user_id)

    def set_rollout(self, name: str, percentage: float) -> bool:
        """
        Update rollout percentage for a flag.

        Args:
            name: Feature flag name
            percentage: New rollout percentage (0-100)

        Returns:
            True if flag was found and updated
        """
        flag = self._flags.get(name)
        if flag is None:
            return False


        flag.enabled = percentage > 0.0
        flag.set_rollout(percentage)
        return True

    def disable_flag(self, name: str) -> bool:
        """Disable a feature flag (0% rollout)."""
        return self.set_rollout(name, 0.0)

    def enable_flag(self, name: str) -> bool:
        """Enable a feature flag for all users (100% rollout)."""
        return self.set_rollout(name, 100.0)

    def list_flags(self) -> list[FeatureFlag]:
        """Return all registered flags."""
        return list(self._flags.values())

    def get_enabled_flags(self, user_id: str) -> list[str]:
        """Return names of all flags enabled for a user."""
        return [
            name for name, flag in self._flags.items()
            if flag.is_enabled_for(user_id)
        ]


# ---------------------------------------------------------------------------
# A/B Testing Framework
# ---------------------------------------------------------------------------

@dataclass
class ExperimentVariant:
    """A variant in an A/B experiment."""
    name: str
    description: str
    traffic_percentage: float  # 0.0 to 100.0
    is_control: bool = False


@dataclass
class ExperimentMetrics:
    """Metrics collected for an experiment variant."""
    variant_name: str
    impressions: int = 0
    conversions: int = 0
    total_latency_ms: float = 0.0
    errors: int = 0

    @property
    def conversion_rate(self) -> float:
        """Conversion rate (0.0 to 1.0)."""
        return self.conversions / self.impressions if self.impressions > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        """Average latency in milliseconds."""
        return self.total_latency_ms / self.impressions if self.impressions > 0 else 0.0

    @property
    def error_rate(self) -> float:
        """Error rate (0.0 to 1.0)."""
        return self.errors / self.impressions if self.impressions > 0 else 0.0


@dataclass
class Experiment:
    """An A/B experiment with multiple variants."""
    experiment_id: str
    name: str
    description: str
    variants: list[ExperimentVariant]
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    is_active: bool = True
    winner: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_variant_for_user(self, user_id: str) -> ExperimentVariant:
        """
        Assign a user to a variant using consistent hashing.

        Time Complexity: O(k) where k is number of variants

        Args:
            user_id: User identifier

        Returns:
            Assigned variant (deterministic per user)
        """
        hash_input = f"{self.experiment_id}:{user_id}"
        hash_value = int(hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest(), 16)  # noqa: S324
        bucket = (hash_value % 10000) / 100.0  # 0.0 to 99.99

        cumulative = 0.0
        for variant in self.variants:
            cumulative += variant.traffic_percentage
            if bucket < cumulative:
                return variant

        # Fallback to last variant (handles floating point edge cases)
        return self.variants[-1]

    @property
    def total_traffic(self) -> float:
        """Total traffic percentage across all variants."""
        return sum(v.traffic_percentage for v in self.variants)


class StatisticalAnalyzer:
    """
    Statistical significance testing for A/B experiments.

    Uses z-test for proportion comparison.
    Significance threshold: p < 0.05 (95% confidence).
    """

    SIGNIFICANCE_THRESHOLD = 0.05

    def is_significant(
        self,
        control: ExperimentMetrics,
        treatment: ExperimentMetrics,
    ) -> tuple[bool, float]:
        """
        Test if treatment is statistically significantly different from control.

        Uses two-proportion z-test.
        Time Complexity: O(1)

        Args:
            control: Control variant metrics
            treatment: Treatment variant metrics

        Returns:
            Tuple of (is_significant, p_value)
        """
        n1 = control.impressions
        n2 = treatment.impressions

        if n1 < 30 or n2 < 30:
            return False, 1.0  # Insufficient data

        p1 = control.conversion_rate
        p2 = treatment.conversion_rate

        # Pooled proportion
        p_pool = (control.conversions + treatment.conversions) / (n1 + n2)

        if p_pool == 0.0 or p_pool == 1.0:
            return False, 1.0

        # Standard error
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))

        if se == 0.0:
            return False, 1.0

        # Z-score
        z = abs(p2 - p1) / se

        # Approximate p-value using normal CDF
        p_value = 2 * (1 - self._normal_cdf(z))

        return p_value < self.SIGNIFICANCE_THRESHOLD, p_value

    def _normal_cdf(self, z: float) -> float:
        """Approximate normal CDF using error function."""
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))

    def relative_improvement(
        self,
        control: ExperimentMetrics,
        treatment: ExperimentMetrics,
    ) -> float:
        """
        Calculate relative improvement of treatment over control.

        Returns:
            Relative improvement (positive = treatment better)
        """
        if control.conversion_rate == 0.0:
            return 0.0
        return (treatment.conversion_rate - control.conversion_rate) / control.conversion_rate


class ABTestManager:
    """
    Manages A/B experiments with statistical significance testing.

    Supports:
    - Experiment creation with multiple variants
    - User assignment with consistent hashing
    - Metrics collection per variant
    - Statistical significance testing
    - Automatic winner selection

    Time Complexity: O(1) for variant assignment, O(k) for metrics
    """

    def __init__(self) -> None:
        self._experiments: dict[str, Experiment] = {}
        self._metrics: dict[str, dict[str, ExperimentMetrics]] = {}
        self._analyzer = StatisticalAnalyzer()

    def create_experiment(
        self,
        name: str,
        description: str,
        control_pct: float = 90.0,
        treatment_pct: float = 10.0,
    ) -> Experiment:
        """
        Create a new A/B experiment.

        Args:
            name: Experiment name
            description: What is being tested
            control_pct: Traffic percentage for control (default 90%)
            treatment_pct: Traffic percentage for treatment (default 10%)

        Returns:
            Created experiment
        """
        experiment = Experiment(
            experiment_id=str(uuid.uuid4()),
            name=name,
            description=description,
            variants=[
                ExperimentVariant("control", "Control group", control_pct, is_control=True),
                ExperimentVariant("treatment", "Treatment group", treatment_pct),
            ],
        )
        self._experiments[name] = experiment
        self._metrics[name] = {
            "control": ExperimentMetrics("control"),
            "treatment": ExperimentMetrics("treatment"),
        }
        return experiment

    def get_variant(self, experiment_name: str, user_id: str) -> Optional[str]:
        """
        Get the variant assigned to a user for an experiment.

        Time Complexity: O(k) where k is number of variants

        Args:
            experiment_name: Name of the experiment
            user_id: User identifier

        Returns:
            Variant name, or None if experiment not found/inactive
        """
        experiment = self._experiments.get(experiment_name)
        if experiment is None or not experiment.is_active:
            return None
        variant = experiment.get_variant_for_user(user_id)
        return variant.name

    def record_impression(self, experiment_name: str, variant_name: str) -> None:
        """Record an impression for a variant."""
        metrics = self._metrics.get(experiment_name, {}).get(variant_name)
        if metrics:
            metrics.impressions += 1

    def record_conversion(
        self,
        experiment_name: str,
        variant_name: str,
        latency_ms: float = 0.0,
    ) -> None:
        """Record a conversion (success) for a variant."""
        metrics = self._metrics.get(experiment_name, {}).get(variant_name)
        if metrics:
            metrics.conversions += 1
            metrics.total_latency_ms += latency_ms

    def record_error(self, experiment_name: str, variant_name: str) -> None:
        """Record an error for a variant."""
        metrics = self._metrics.get(experiment_name, {}).get(variant_name)
        if metrics:
            metrics.errors += 1

    def get_metrics(self, experiment_name: str) -> dict[str, ExperimentMetrics]:
        """Get metrics for all variants of an experiment."""
        return dict(self._metrics.get(experiment_name, {}))

    def analyze(self, experiment_name: str) -> dict[str, Any]:
        """
        Analyze experiment results for statistical significance.

        Args:
            experiment_name: Name of the experiment

        Returns:
            Analysis report with significance, improvement, and recommendation
        """
        metrics = self._metrics.get(experiment_name, {})
        control = metrics.get("control")
        treatment = metrics.get("treatment")

        if not control or not treatment:
            return {"error": "Experiment not found"}

        is_significant, p_value = self._analyzer.is_significant(control, treatment)
        improvement = self._analyzer.relative_improvement(control, treatment)

        recommendation = "continue_testing"
        if is_significant:
            if improvement > 0:
                recommendation = "deploy_treatment"
            else:
                recommendation = "keep_control"

        return {
            "experiment_name": experiment_name,
            "control": {
                "impressions": control.impressions,
                "conversion_rate": control.conversion_rate,
                "avg_latency_ms": control.avg_latency_ms,
                "error_rate": control.error_rate,
            },
            "treatment": {
                "impressions": treatment.impressions,
                "conversion_rate": treatment.conversion_rate,
                "avg_latency_ms": treatment.avg_latency_ms,
                "error_rate": treatment.error_rate,
            },
            "is_significant": is_significant,
            "p_value": p_value,
            "relative_improvement": improvement,
            "recommendation": recommendation,
        }

    def conclude_experiment(self, experiment_name: str) -> Optional[str]:
        """
        Conclude an experiment and select a winner.

        Returns:
            Winner variant name, or None if no significant winner
        """
        analysis = self.analyze(experiment_name)
        experiment = self._experiments.get(experiment_name)

        if not experiment or "error" in analysis:
            return None

        experiment.is_active = False
        experiment.ended_at = datetime.now(tz=timezone.utc)

        if analysis["recommendation"] == "deploy_treatment":
            experiment.winner = "treatment"
        elif analysis["recommendation"] == "keep_control":
            experiment.winner = "control"

        return experiment.winner

    def list_experiments(self) -> list[Experiment]:
        """Return all experiments."""
        return list(self._experiments.values())

    def get_active_experiments(self) -> list[Experiment]:
        """Return only active experiments."""
        return [e for e in self._experiments.values() if e.is_active]
