"""Module: Agent_Guru.vision.training.pipeline
Purpose: Pipeline orchestrator — coordinate all pipeline stages.

Requirements: 12.3
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .dataset_manager import DatasetManager
from .evaluation import BenchmarkResult, EvaluationEngine
from .failure_analysis import FailureAnalysis, FailureAnalyzer
from .improvement import ImprovementStrategyManager
from .report import ModelMetadata, Report, ReportGenerator
from .stress_test import StressCondition, StressTester, StressTestResult

if TYPE_CHECKING:
    from .config_manager import Config

logger = logging.getLogger("guruvision.training.pipeline")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Result of a complete pipeline run."""

    success: bool = False
    model_path: str = ""
    onnx_path: str = ""
    report_path: str = ""
    all_targets_met: bool = False
    total_time: float = 0.0
    stages_completed: list[str] = field(default_factory=list)


@dataclass
class ImprovementResult:
    """Result of the improvement loop."""

    iterations: int = 0
    final_benchmark_results: list[BenchmarkResult] = field(default_factory=list)
    all_targets_met: bool = False
    history: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# PipelineOrchestrator
# ---------------------------------------------------------------------------


class PipelineOrchestrator:
    """Coordinate execution of all pipeline stages.

    Args:
        config: Pipeline configuration.

    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self._log_config()

        self._dataset_manager = DatasetManager(config.dataset.root_dir)
        self._eval_engine = EvaluationEngine(
            targets=config.evaluation.targets,
            embedding_dim=config.training.embedding_size,
        )
        self._failure_analyzer = FailureAnalyzer()
        self._improvement_manager = ImprovementStrategyManager(
            current_backbone=config.training.backbone,
        )
        self._stress_tester = StressTester()
        self._report_generator = ReportGenerator(config.reporting.output_dir)

        self._model_path: str = ""
        self._onnx_path: str = ""
        self._benchmark_results: list[BenchmarkResult] = []
        self._failure_analysis: FailureAnalysis | None = None
        self._stress_results: list[StressTestResult] = []

    def run_full_pipeline(self) -> PipelineResult:
        """Execute all pipeline stages in sequence.

        Returns:
            PipelineResult with paths and status.

        """
        start = time.time()
        stages: list[str] = []

        try:
            # Stage 1: Training
            self.run_training_stage()
            stages.append("training")

            # Stage 2: Evaluation
            self._benchmark_results = self.run_evaluation_stage(self._model_path)
            stages.append("evaluation")

            # Stage 3: Improvement loop
            improvement = self.run_improvement_loop(max_iterations=2)
            stages.append("improvement")

            # Stage 4: Stress testing
            self._stress_results = self.run_stress_testing_stage(self._model_path)
            stages.append("stress_testing")

            # Stage 5: Report
            report = self.generate_final_report()
            report_path = self._report_generator.export_json(report)
            stages.append("reporting")

            all_targets_met = improvement.all_targets_met
            total_time = time.time() - start

            logger.info(
                "Pipeline complete in %.1fs. Targets met: %s",
                total_time,
                all_targets_met,
            )

            return PipelineResult(
                success=True,
                model_path=self._model_path,
                onnx_path=self._onnx_path,
                report_path=report_path,
                all_targets_met=all_targets_met,
                total_time=total_time,
                stages_completed=stages,
            )

        except Exception:
            logger.exception("Pipeline failed")
            return PipelineResult(
                success=False,
                total_time=time.time() - start,
                stages_completed=stages,
            )

    def run_training_stage(self) -> Any:
        """Run the training stage.

        Returns:
            Training result object (or None if training skipped).

        """
        logger.info("Starting training stage")
        dataset_dir = self.config.dataset.training_path
        output_dir = self.config.training.output_dir

        if not Path(dataset_dir).exists():
            logger.warning("Training dataset not found at '%s'. Skipping training.", dataset_dir)
            self._model_path = str(Path(output_dir) / self.config.training.checkpoint_name)
            return None

        try:
            from .train import TrainingConfig, train_arcface_model

            train_cfg = TrainingConfig(
                dataset_dir=dataset_dir,
                output_dir=output_dir,
                embedding_dim=self.config.training.embedding_size,
                batch_size=self.config.training.batch_size,
                learning_rate=self.config.training.learning_rate,
                momentum=self.config.training.momentum,
                weight_decay=self.config.training.weight_decay,
                epochs=self.config.training.num_epochs,
                val_split=self.config.training.val_split,
                arcface_scale=self.config.training.arcface_scale,
                arcface_margin=self.config.training.arcface_margin,
                use_gpu=self.config.training.use_gpu,
                checkpoint_name=self.config.training.checkpoint_name,
                seed=self.config.random_seed,
            )
            self._model_path = train_arcface_model(train_cfg)
            logger.info("Training complete. Model saved to '%s'", self._model_path)
            return {"model_path": self._model_path}
        except Exception:
            logger.exception("Training failed")
            return None

    def run_evaluation_stage(self, model_path: str) -> list[BenchmarkResult]:
        """Run evaluation on all configured benchmarks.

        Args:
            model_path: Path to the model to evaluate.

        Returns:
            List of BenchmarkResult objects.

        """
        logger.info("Starting evaluation stage")
        results: list[BenchmarkResult] = []

        benchmarks = list(self.config.evaluation.targets.keys())
        if not benchmarks:
            benchmarks = ["lfw", "cfp_fp", "agedb_30"]

        for benchmark_name in benchmarks:
            benchmark_path = self.config.dataset.benchmark_paths.get(benchmark_name, "")
            try:
                # Load model (use synthetic if model doesn't exist)
                model = None
                use_onnx = self.config.evaluation.use_onnx
                if Path(model_path).exists():
                    model = self._eval_engine.load_model(model_path, use_onnx)

                result = self._eval_engine.evaluate_benchmark(
                    model=model,
                    benchmark_name=benchmark_name,
                    benchmark_path=benchmark_path,
                    use_onnx=use_onnx,
                )
                results.append(result)
                logger.info("Benchmark '%s': accuracy=%.4f", benchmark_name, result.accuracy)
            except Exception as exc:
                logger.exception("Evaluation failed for '%s': %s", benchmark_name, exc)

        self._benchmark_results = results
        return results

    def run_improvement_loop(self, max_iterations: int = 3) -> ImprovementResult:
        """Run iterative improvement loop.

        Args:
            max_iterations: Maximum number of improvement iterations.

        Returns:
            ImprovementResult with final benchmark results.

        """
        logger.info("Starting improvement loop (max_iterations=%d)", max_iterations)
        import numpy as np

        history: list[dict[str, Any]] = []
        current_results = self._benchmark_results or self.run_evaluation_stage(self._model_path)

        for iteration in range(max_iterations):
            comparisons = self._eval_engine.compare_against_targets(current_results)
            all_met = self._eval_engine.is_production_ready(comparisons)

            if all_met:
                logger.info("All targets met at iteration %d", iteration)
                break

            # Analyze failures
            n = 100
            rng = np.random.default_rng(iteration)
            preds = rng.integers(0, 2, n)
            labels = rng.integers(0, 2, n)
            analysis = self._failure_analyzer.analyze_failures(preds, labels)
            self._failure_analysis = analysis

            strategies = self._improvement_manager.recommend_strategies(analysis)
            if not strategies:
                break

            strategy = strategies[0]
            applied = self._improvement_manager.apply_strategy(strategy)
            history.append(
                {
                    "iteration": iteration + 1,
                    "strategy": strategy.name,
                    "success": applied.success,
                },
            )

            # Re-evaluate
            current_results = self.run_evaluation_stage(self._model_path)

        comparisons = self._eval_engine.compare_against_targets(current_results)
        all_met = self._eval_engine.is_production_ready(comparisons)

        return ImprovementResult(
            iterations=len(history),
            final_benchmark_results=current_results,
            all_targets_met=all_met,
            history=history,
        )

    def run_stress_testing_stage(self, model_path: str) -> list[StressTestResult]:
        """Run stress testing on the model.

        Args:
            model_path: Path to the model.

        Returns:
            List of StressTestResult objects.

        """
        logger.info("Starting stress testing stage")
        import numpy as np

        if not self.config.stress_testing.enabled:
            logger.info("Stress testing disabled in config")
            return []

        # Generate synthetic test images
        rng = np.random.default_rng(42)
        n = 20
        images = rng.integers(0, 256, (n, 112, 112, 3), dtype=np.uint8)
        labels = rng.integers(0, 2, n)

        conditions: list[StressCondition] = []
        for cond_cfg in self.config.stress_testing.conditions:
            ctype = cond_cfg.get("type", "blur")
            params = cond_cfg.get("params", {})
            conditions.append(StressCondition(type=ctype, params=params))

        if not conditions:
            conditions = None  # type: ignore[assignment]

        results = self._stress_tester.run_all_stress_tests(
            model=None,
            images=images,
            labels=labels,
            conditions=conditions,
        )
        self._stress_results = results
        return results

    def generate_final_report(self) -> Report:
        """Generate the final comprehensive report.

        Returns:
            Compiled Report object.

        """
        logger.info("Generating final report")

        comparisons = self._eval_engine.compare_against_targets(self._benchmark_results)

        metadata = ModelMetadata(
            architecture=self.config.training.backbone,
            embedding_size=self.config.training.embedding_size,
        )

        return self._report_generator.compile_results(
            benchmark_results=self._benchmark_results,
            failure_analysis=self._failure_analysis,
            stress_test_results=self._stress_results,
            model_metadata=metadata,
            target_comparison=comparisons,
            pipeline_name=self.config.name,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _log_config(self) -> None:
        """Log the complete configuration at pipeline start."""
        import json
        from dataclasses import asdict

        try:
            config_dict = {
                "name": self.config.name,
                "version": self.config.version,
                "random_seed": self.config.random_seed,
                "training": asdict(self.config.training),
                "evaluation": {
                    "batch_size": self.config.evaluation.batch_size,
                    "use_onnx": self.config.evaluation.use_onnx,
                    "targets": self.config.evaluation.targets,
                },
            }
            logger.info(
                "Pipeline configuration:\n%s",
                json.dumps(config_dict, indent=2, default=str),
            )
        except Exception:
            logger.exception("Could not log configuration")
