"""
Module: Agent_Guru.vision.training.failure_analysis
Purpose: Categorize and analyze model failures to guide improvements.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger("guruvision.training.failure_analysis")

FAILURE_CATEGORIES = [
    "pose", "lighting", "blur", "occlusion", "aging", "accessories", "unknown"
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkMetadata:
    """Metadata for benchmark dataset pairs."""
    pair_indices: list[tuple[int, int]] = field(default_factory=list)
    pose_angles: Optional[dict[int, float]] = None
    age_differences: Optional[dict[tuple[int, int], int]] = None
    has_accessories: Optional[dict[int, bool]] = None
    lighting_conditions: Optional[dict[int, str]] = None
    blur_scores: Optional[dict[int, float]] = None
    occlusion_masks: Optional[dict[int, np.ndarray]] = None


@dataclass
class FailureCategory:
    """A single failure instance with category assignment."""
    category: str
    pair_idx: int
    score: float
    ground_truth: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CategoryStats:
    """Statistics for failure categories."""
    category_counts: dict[str, int] = field(default_factory=dict)
    category_rates: dict[str, float] = field(default_factory=dict)
    total_failures: int = 0


@dataclass
class FailureAnalysis:
    """Complete failure analysis result."""
    total_failures: int = 0
    category_counts: dict[str, int] = field(default_factory=dict)
    category_rates: dict[str, float] = field(default_factory=dict)
    top_categories: list[str] = field(default_factory=list)
    failure_examples: dict[str, list[FailureCategory]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# FailureAnalyzer
# ---------------------------------------------------------------------------

class FailureAnalyzer:
    """Categorize and analyze model failures.

    Args:
        top_k: Number of top failure categories to report.
    """

    def __init__(self, top_k: int = 3) -> None:
        self.top_k = top_k

    def analyze_failures(
        self,
        predictions: np.ndarray,
        labels: np.ndarray,
        metadata: Optional[BenchmarkMetadata] = None,
        scores: Optional[np.ndarray] = None,
    ) -> FailureAnalysis:
        """Analyze failures from evaluation predictions.

        Args:
            predictions: Binary predictions (0 or 1).
            labels: Ground truth labels (0 or 1).
            metadata: Optional benchmark metadata for categorization.
            scores: Optional similarity scores.

        Returns:
            FailureAnalysis with category breakdown.
        """
        failure_indices = np.where(predictions != labels)[0]
        failures: list[FailureCategory] = []

        for idx in failure_indices:
            score = float(scores[idx]) if scores is not None else 0.0
            category = self.categorize_failure(int(idx), metadata)
            failures.append(FailureCategory(
                category=category,
                pair_idx=int(idx),
                score=score,
                ground_truth=bool(labels[idx]),
            ))

        stats = self.compute_category_stats(failures)
        top_cats = self.identify_top_failures(stats, self.top_k)

        # Group examples by category
        examples: dict[str, list[FailureCategory]] = {c: [] for c in FAILURE_CATEGORIES}
        for f in failures:
            examples.setdefault(f.category, []).append(f)

        return FailureAnalysis(
            total_failures=len(failures),
            category_counts=stats.category_counts,
            category_rates=stats.category_rates,
            top_categories=top_cats,
            failure_examples=examples,
        )

    def categorize_failure(
        self,
        pair_idx: int,
        metadata: Optional[BenchmarkMetadata] = None,
    ) -> str:
        """Assign a failure to a category based on metadata.

        Args:
            pair_idx: Index of the failing pair.
            metadata: Optional benchmark metadata.

        Returns:
            Category string.
        """
        if metadata is None:
            return "unknown"

        # Check pose
        if metadata.pose_angles is not None:
            angle = metadata.pose_angles.get(pair_idx)
            if angle is not None and abs(angle) > 30:
                return "pose"

        # Check accessories
        if metadata.has_accessories is not None:
            has_acc = metadata.has_accessories.get(pair_idx)
            if has_acc:
                return "accessories"

        # Check blur
        if metadata.blur_scores is not None:
            blur = metadata.blur_scores.get(pair_idx)
            if blur is not None and blur > 0.5:
                return "blur"

        # Check lighting
        if metadata.lighting_conditions is not None:
            lighting = metadata.lighting_conditions.get(pair_idx)
            if lighting in {"low", "dark", "overexposed"}:
                return "lighting"

        # Check age difference
        if metadata.age_differences is not None:
            for (i, j), diff in metadata.age_differences.items():
                if i == pair_idx or j == pair_idx:
                    if diff > 10:
                        return "aging"

        # Check occlusion
        if metadata.occlusion_masks is not None:
            mask = metadata.occlusion_masks.get(pair_idx)
            if mask is not None and np.mean(mask) > 0.2:
                return "occlusion"

        return "unknown"

    def compute_category_stats(
        self, failures: list[FailureCategory]
    ) -> CategoryStats:
        """Compute failure rates per category.

        Args:
            failures: List of FailureCategory instances.

        Returns:
            CategoryStats with counts and rates.
        """
        counts: dict[str, int] = dict.fromkeys(FAILURE_CATEGORIES, 0)
        for f in failures:
            counts[f.category] = counts.get(f.category, 0) + 1

        total = len(failures)
        rates: dict[str, float] = {
            c: counts[c] / max(total, 1) for c in counts
        }

        return CategoryStats(
            category_counts=counts,
            category_rates=rates,
            total_failures=total,
        )

    def identify_top_failures(
        self, stats: CategoryStats, top_k: int = 3
    ) -> list[str]:
        """Rank categories by failure frequency.

        Args:
            stats: CategoryStats from compute_category_stats().
            top_k: Number of top categories to return.

        Returns:
            List of category names sorted by frequency (descending).
        """
        sorted_cats = sorted(
            stats.category_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [cat for cat, count in sorted_cats[:top_k] if count > 0]

    def generate_failure_report(
        self,
        analysis: FailureAnalysis,
        output_path: str,
    ) -> None:
        """Generate a failure analysis report as JSON.

        Args:
            analysis: FailureAnalysis result.
            output_path: Path to write the report.
        """
        import json

        report = {
            "total_failures": analysis.total_failures,
            "category_counts": analysis.category_counts,
            "category_rates": {k: round(v, 4) for k, v in analysis.category_rates.items()},
            "top_categories": analysis.top_categories,
            "examples_per_category": {
                cat: [
                    {
                        "pair_idx": f.pair_idx,
                        "score": round(f.score, 4),
                        "ground_truth": f.ground_truth,
                    }
                    for f in examples[:5]  # max 5 examples per category
                ]
                for cat, examples in analysis.failure_examples.items()
                if examples
            },
        }

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        logger.info("Failure report written to '%s'", output_path)

    def generate_failure_distribution_plot(
        self, analysis: FailureAnalysis, output_path: str
    ) -> None:
        """Generate a bar chart of failure distribution.

        Args:
            analysis: FailureAnalysis result.
            output_path: Path to save the plot image.
        """
        try:
            import matplotlib.pyplot as plt  # type: ignore[import]

            categories = list(analysis.category_counts.keys())
            counts = [analysis.category_counts[c] for c in categories]

            fig, ax = plt.subplots(figsize=(10, 5))
            ax.bar(categories, counts, color="steelblue")
            ax.set_xlabel("Failure Category")
            ax.set_ylabel("Count")
            ax.set_title("Failure Distribution by Category")
            ax.tick_params(axis="x", rotation=45)
            plt.tight_layout()

            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(str(path))
            plt.close(fig)
            logger.info("Failure distribution plot saved to '%s'", output_path)
        except ImportError:
            logger.warning("matplotlib not available; skipping failure distribution plot")
