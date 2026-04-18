"""
Module: Agent_Guru.vision.training.report
Purpose: Generate comprehensive performance reports in multiple formats.

Requirements: 10.1-10.9
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .evaluation import BenchmarkResult, TargetComparison
from .failure_analysis import FailureAnalysis
from .stress_test import StressTestResult

logger = logging.getLogger("guruvision.training.report")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ModelMetadata:
    """Model metadata for reporting."""
    architecture: str = "resnet50"
    embedding_size: int = 512
    num_parameters: int = 0
    flops: int = 0
    model_size_mb: float = 0.0
    training_dataset: str = ""
    training_time: float = 0.0


@dataclass
class TrainingSummary:
    """Summary of training run."""
    final_loss: float = 0.0
    num_epochs: int = 0
    total_time: float = 0.0
    hardware: str = "CPU"
    distributed: bool = False


@dataclass
class Report:
    """Complete pipeline report."""
    pipeline_name: str = "guruvision-pipeline"
    timestamp: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    model_metadata: ModelMetadata = field(default_factory=ModelMetadata)
    training_summary: TrainingSummary = field(default_factory=TrainingSummary)
    benchmark_results: list[BenchmarkResult] = field(default_factory=list)
    target_comparison: dict[str, TargetComparison] = field(default_factory=dict)
    failure_analysis: Optional[FailureAnalysis] = None
    stress_test_results: list[StressTestResult] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    visualizations: dict[str, Any] = field(default_factory=dict)
    production_ready: bool = False


# ---------------------------------------------------------------------------
# ReportGenerator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Generate comprehensive performance reports.

    Args:
        output_dir: Directory to write reports.
    """

    def __init__(self, output_dir: str = "Agent_Guru/vision/data/reports") -> None:
        self.output_dir = output_dir

    def compile_results(
        self,
        training_result: Optional[Any] = None,
        benchmark_results: Optional[list[BenchmarkResult]] = None,
        failure_analysis: Optional[FailureAnalysis] = None,
        stress_test_results: Optional[list[StressTestResult]] = None,
        model_metadata: Optional[ModelMetadata] = None,
        target_comparison: Optional[dict[str, TargetComparison]] = None,
        pipeline_name: str = "guruvision-pipeline",
    ) -> Report:
        """Compile all results into a Report.

        Args:
            training_result: Optional training result with metrics.
            benchmark_results: List of benchmark evaluation results.
            failure_analysis: Optional failure analysis.
            stress_test_results: Optional stress test results.
            model_metadata: Optional model metadata.
            target_comparison: Optional target comparison dict.
            pipeline_name: Name of the pipeline run.

        Returns:
            Compiled Report object.
        """
        report = Report(pipeline_name=pipeline_name)

        if model_metadata is not None:
            report.model_metadata = model_metadata

        if training_result is not None:
            report.training_summary = TrainingSummary(
                final_loss=getattr(training_result, "final_loss", 0.0),
                num_epochs=getattr(training_result, "num_epochs", 0),
                total_time=getattr(training_result, "training_time", 0.0),
                hardware=getattr(training_result, "hardware", "CPU"),
                distributed=getattr(training_result, "distributed", False),
            )

        if benchmark_results:
            report.benchmark_results = benchmark_results

        if target_comparison:
            report.target_comparison = target_comparison
            report.production_ready = all(
                tc.passed for tc in target_comparison.values()
            )

        if failure_analysis is not None:
            report.failure_analysis = failure_analysis

        if stress_test_results:
            report.stress_test_results = stress_test_results

        report.recommendations = self.generate_recommendations(report)

        logger.info(
            "Report compiled: %d benchmarks, production_ready=%s",
            len(report.benchmark_results),
            report.production_ready,
        )
        return report

    def generate_recommendations(self, report: Report) -> list[str]:
        """Generate recommendations based on report results.

        Args:
            report: Compiled report.

        Returns:
            List of recommendation strings.
        """
        recommendations: list[str] = []

        if report.production_ready:
            recommendations.append(
                "Model meets all performance targets. Ready for production deployment."
            )
        else:
            recommendations.append(
                "Model does not meet all performance targets. Further improvement required."
            )
            for name, tc in report.target_comparison.items():
                if not tc.passed:
                    recommendations.append(
                        f"Benchmark '{name}': achieved {tc.achieved:.4f}, "
                        f"target {tc.target:.4f} (gap: {tc.gap:.4f}). "
                        "Consider additional training or architecture upgrade."
                    )

        if report.failure_analysis and report.failure_analysis.top_categories:
            top = report.failure_analysis.top_categories[:3]
            recommendations.append(
                f"Top failure categories: {', '.join(top)}. "
                "Apply targeted data augmentation for these conditions."
            )

        if report.stress_test_results:
            worst = max(
                report.stress_test_results,
                key=lambda r: r.degradation,
                default=None,
            )
            if worst and worst.degradation > 0.05:
                recommendations.append(
                    f"Significant degradation under '{worst.condition.type}' "
                    f"({worst.degradation:.2%}). Consider robustness training."
                )

        return recommendations

    def generate_visualizations(self, report: Report) -> dict[str, Any]:
        """Generate visualization figures for the report.

        Args:
            report: Compiled report.

        Returns:
            Dict mapping figure name to matplotlib Figure.
        """
        figures: dict[str, Any] = {}

        try:
            import matplotlib.pyplot as plt  # type: ignore[import]

            # ROC curves
            if report.benchmark_results:
                fig, ax = plt.subplots(figsize=(8, 6))
                for result in report.benchmark_results:
                    roc = result.roc_curve
                    if len(roc.fpr) > 0:
                        ax.plot(roc.fpr, roc.tpr, label=f"{result.benchmark_name} (AUC={result.auc:.3f})")
                ax.plot([0, 1], [0, 1], "k--", label="Random")
                ax.set_xlabel("False Positive Rate")
                ax.set_ylabel("True Positive Rate")
                ax.set_title("ROC Curves")
                ax.legend()
                figures["roc_curves"] = fig
                plt.close(fig)

            # Benchmark accuracy bar chart
            if report.benchmark_results:
                fig, ax = plt.subplots(figsize=(8, 5))
                names = [r.benchmark_name for r in report.benchmark_results]
                accs = [r.accuracy for r in report.benchmark_results]
                ax.bar(names, accs, color="steelblue")
                ax.set_ylim(0, 1)
                ax.set_ylabel("Accuracy")
                ax.set_title("Benchmark Accuracies")
                figures["benchmark_accuracies"] = fig
                plt.close(fig)

            # Failure distribution
            if report.failure_analysis:
                fa = report.failure_analysis
                cats = list(fa.category_counts.keys())
                counts = [fa.category_counts[c] for c in cats]
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.bar(cats, counts, color="coral")
                ax.set_xlabel("Category")
                ax.set_ylabel("Count")
                ax.set_title("Failure Distribution")
                ax.tick_params(axis="x", rotation=45)
                plt.tight_layout()
                figures["failure_distribution"] = fig
                plt.close(fig)

        except ImportError as e:
            logger.warning("matplotlib not available; skipping visualizations: %s", e)

        return figures

    def export_json(self, report: Report, output_path: Optional[str] = None) -> str:
        """Export report as JSON.

        Args:
            report: Report to export.
            output_path: Optional output path. Defaults to output_dir/report.json.

        Returns:
            Path to the written JSON file.
        """
        if output_path is None:
            output_path = str(Path(self.output_dir) / "report.json")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        data = self._report_to_dict(report)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=self._json_default)

        logger.info("JSON report written to '%s'", output_path)
        return output_path

    def export_html(self, report: Report, output_path: Optional[str] = None) -> str:
        """Export report as HTML.

        Args:
            report: Report to export.
            output_path: Optional output path.

        Returns:
            Path to the written HTML file.
        """
        if output_path is None:
            output_path = str(Path(self.output_dir) / "report.html")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        html = self._render_html(report)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info("HTML report written to '%s'", output_path)
        return output_path

    def export_pdf(self, report: Report, output_path: Optional[str] = None) -> str:
        """Export report as PDF using ReportLab if available.

        Falls back to HTML if ReportLab is not installed.

        Args:
            report: Report to export.
            output_path: Optional output path.

        Returns:
            Path to the written PDF (or HTML fallback) file.
        """
        if output_path is None:
            output_path = str(Path(self.output_dir) / "report.pdf")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            from reportlab.lib.pagesizes import letter  # type: ignore[import]
            from reportlab.lib.styles import getSampleStyleSheet  # type: ignore[import]
            from reportlab.platypus import Paragraph, SimpleDocTemplate  # type: ignore[import]

            doc = SimpleDocTemplate(output_path, pagesize=letter)
            styles = getSampleStyleSheet()
            story = [
                Paragraph(f"<b>{report.pipeline_name}</b>", styles["Title"]),
                Paragraph(f"Generated: {report.timestamp}", styles["Normal"]),
                Paragraph(
                    f"Production Ready: {report.production_ready}", styles["Normal"]
                ),
            ]
            for rec in report.recommendations:
                story.append(Paragraph(f"• {rec}", styles["Normal"]))
            doc.build(story)
            logger.info("PDF report written to '%s'", output_path)
        except ImportError as e:
            # Fallback to HTML
            html_path = output_path.replace(".pdf", ".html")
            self.export_html(report, html_path)
            logger.warning(
                "ReportLab not available; PDF fallback written as HTML to '%s'",
                html_path,
            )
            return html_path

        return output_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _report_to_dict(report: Report) -> dict[str, Any]:
        """Convert Report to a JSON-serializable dict."""
        import numpy as np

        def _safe(v: Any) -> Any:
            if isinstance(v, np.ndarray):
                return v.tolist()
            if isinstance(v, np.floating):
                return float(v)
            if isinstance(v, np.integer):
                return int(v)
            return v

        benchmarks = []
        for r in report.benchmark_results:
            benchmarks.append({
                "benchmark_name": r.benchmark_name,
                "accuracy": _safe(r.accuracy),
                "auc": _safe(r.auc),
                "optimal_threshold": _safe(r.optimal_threshold),
                "num_pairs": r.num_pairs,
                "inference_time": _safe(r.inference_time),
                "far_at_frr": {str(k): _safe(v) for k, v in r.far_at_frr.items()},
            })

        targets = {
            k: {
                "achieved": _safe(v.achieved),
                "target": _safe(v.target),
                "gap": _safe(v.gap),
                "passed": v.passed,
            }
            for k, v in report.target_comparison.items()
        }

        stress = []
        for s in report.stress_test_results:
            stress.append({
                "condition": s.condition.type,
                "description": s.condition.description,
                "baseline_accuracy": _safe(s.baseline_accuracy),
                "stressed_accuracy": _safe(s.stressed_accuracy),
                "degradation": _safe(s.degradation),
                "num_samples": s.num_samples,
            })

        failure = None
        if report.failure_analysis:
            fa = report.failure_analysis
            failure = {
                "total_failures": fa.total_failures,
                "category_counts": fa.category_counts,
                "category_rates": {k: _safe(v) for k, v in fa.category_rates.items()},
                "top_categories": fa.top_categories,
            }

        return {
            "pipeline_name": report.pipeline_name,
            "timestamp": report.timestamp,
            "production_ready": report.production_ready,
            "model_metadata": {
                "architecture": report.model_metadata.architecture,
                "embedding_size": report.model_metadata.embedding_size,
                "num_parameters": report.model_metadata.num_parameters,
                "flops": report.model_metadata.flops,
                "model_size_mb": _safe(report.model_metadata.model_size_mb),
                "training_dataset": report.model_metadata.training_dataset,
                "training_time": _safe(report.model_metadata.training_time),
            },
            "training_summary": {
                "final_loss": _safe(report.training_summary.final_loss),
                "num_epochs": report.training_summary.num_epochs,
                "total_time": _safe(report.training_summary.total_time),
                "hardware": report.training_summary.hardware,
                "distributed": report.training_summary.distributed,
            },
            "benchmark_results": benchmarks,
            "target_comparison": targets,
            "failure_analysis": failure,
            "stress_test_results": stress,
            "recommendations": report.recommendations,
        }

    @staticmethod
    def _json_default(obj: Any) -> Any:
        import numpy as np
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.floating, float)):
            return float(obj)
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        return str(obj)

    @staticmethod
    def _render_html(report: Report) -> str:
        """Render a simple HTML report."""
        benchmarks_html = ""
        for r in report.benchmark_results:
            status = "✅" if report.target_comparison.get(
                r.benchmark_name.lower().replace("-", "_"), TargetComparison()
            ).passed else "❌"
            benchmarks_html += (
                f"<tr><td>{r.benchmark_name}</td>"
                f"<td>{r.accuracy:.4f}</td>"
                f"<td>{r.auc:.4f}</td>"
                f"<td>{status}</td></tr>\n"
            )

        recs_html = "".join(f"<li>{r}</li>" for r in report.recommendations)

        return f"""<!DOCTYPE html>
<html>
<head><title>{report.pipeline_name} Report</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 40px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background-color: #4472C4; color: white; }}
  tr:nth-child(even) {{ background-color: #f2f2f2; }}
  .pass {{ color: green; }} .fail {{ color: red; }}
</style>
</head>
<body>
<h1>{report.pipeline_name}</h1>
<p>Generated: {report.timestamp}</p>
<p>Production Ready: <strong>{'Yes ✅' if report.production_ready else 'No ❌'}</strong></p>

<h2>Model Metadata</h2>
<ul>
  <li>Architecture: {report.model_metadata.architecture}</li>
  <li>Embedding Size: {report.model_metadata.embedding_size}</li>
  <li>Parameters: {report.model_metadata.num_parameters:,}</li>
  <li>Model Size: {report.model_metadata.model_size_mb:.1f} MB</li>
  <li>Training Dataset: {report.model_metadata.training_dataset}</li>
</ul>

<h2>Benchmark Results</h2>
<table>
  <tr><th>Benchmark</th><th>Accuracy</th><th>AUC</th><th>Target Met</th></tr>
  {benchmarks_html}
</table>

<h2>Recommendations</h2>
<ul>{recs_html}</ul>
</body>
</html>"""


# Avoid circular import
from .evaluation import TargetComparison  # noqa: E402
